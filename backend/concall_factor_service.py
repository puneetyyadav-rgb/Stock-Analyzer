"""
concall_factor_service.py — Concall Hesitation & Divergence Factor

Produces two IC-ready signals per stock per quarter from REAL Screener.in transcript PDFs:
  - concall_divergence  : float [-1, +1]  (Q&A sentiment minus Prepared Remarks sentiment)
  - concall_hesitation  : float [0, 100]  (frequency of hedging/uncertainty language in Q&A)

Architecture:
  1. Pulls PDF links from extra_service.get_concalls()  (live Screener.in scrape — no hardcoded data)
  2. Extracts text via extra_service.fetch_pdf_text()   (PyMuPDF / pypdf — real PDF bytes)
  3. Caches extracted .txt to MISC/transcripts/         (re-downloads only NEW quarters)
  4. Scores with gemini-3.5-flash-lite at 15 RPM       (hard throttle + 60s catch-and-pause on 429)
  5. Persists scored results to MISC/concall_factor_store.json
  6. Exposes get_latest_concall_factor(symbol) for consumption by factor_service.py

Pinned scoring config (DO NOT change mid-backtest — breaks IC comparability):
  MODEL      = gemini-3.5-flash-lite
  TEMPERATURE = 0.0
  SCHEMA_VERSION = "v1"
"""

import os
import json
import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ─── PINNED CONFIG (change = new schema version, never silently mutate) ──────
_MODEL          = "gemini-3.5-flash-lite"
_TEMPERATURE    = 0.0
_SCHEMA_VERSION = "v1"
_MAX_QUARTERS   = 8
_TRANSCRIPT_CHARS = 30000          # chars sent to LLM per segment
_RPM_SLEEP      = 4.5              # seconds between each API call (15 RPM => 4s/req)
_RATE_LIMIT_PAUSE = 65             # seconds to sleep when 429 fires

# ─── PATHS ───────────────────────────────────────────────────────────────────
_BASE_DIR      = os.path.join(os.path.dirname(__file__), "..", "stock ticker v2", "MISC")
_BASE_DIR      = os.path.normpath(os.path.join(os.path.dirname(__file__), r"..\MISC"))
_TRANSCRIPT_DIR = os.path.join(_BASE_DIR, "transcripts")
_STORE_PATH     = os.path.join(_BASE_DIR, "concall_factor_store.json")

# ─── PROMPTS (PINNED — never change without bumping _SCHEMA_VERSION) ────────
_SEGMENTATION_PROMPT = """You are a financial NLP parser analyzing an Indian earnings call transcript.
Identify the EXACT sentence that marks the transition from Management Prepared Remarks to the Q&A session.
Look for moderator hand-offs, phrases like "open the floor for questions", "begin Q&A", "first question is from".
Output ONLY strict JSON, no markdown fences:
{"boundary_phrase": "the exact transition sentence from the transcript"}"""

_SCORING_PROMPT = """You are a Quantitative NLP scoring engine for Indian equity research.
Analyze the provided earnings call segment and score it rigorously.
Hesitation phrases include: "challenging macro", "limited visibility", "subject to", "working through",
"deferred", "wait and see", "uncertain environment", "headwinds", "we will have to see", "not fully settled",
"remain cautious", "softer demand", "muted growth", "we will monitor", "too early to say", "contingent on".
Output ONLY strict JSON, no markdown fences, no commentary:
{
  "sentiment_score": <float from -1.0 (extremely bearish) to 1.0 (extremely bullish)>,
  "hesitation_index": <float from 0.0 (zero hedging) to 100.0 (extreme hedging)>,
  "key_hedging_phrases_found": ["exact phrase 1", "exact phrase 2"],
  "reasoning": "2-3 sentences explaining WHY this score was given — cite the specific statements that drove the score"
}"""


# ─── STORE HELPERS ───────────────────────────────────────────────────────────

def _load_store() -> Dict[str, Any]:
    """Load the persisted factor store from disk. Returns empty dict on first run."""
    if os.path.exists(_STORE_PATH):
        try:
            with open(_STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"concall_factor_store corrupt, resetting: {e}")
    return {}


def _save_store(store: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


def _store_key(symbol: str, date_str: str) -> str:
    return f"{symbol.upper()}::{date_str}"


# ─── TRANSCRIPT CACHE ────────────────────────────────────────────────────────

def _cache_path(symbol: str, date_str: str) -> str:
    os.makedirs(_TRANSCRIPT_DIR, exist_ok=True)
    safe = date_str.replace(" ", "_").replace(",", "")
    return os.path.join(_TRANSCRIPT_DIR, f"{symbol.upper()}_{safe}.txt")


def _load_cached_transcript(symbol: str, date_str: str) -> Optional[str]:
    p = _cache_path(symbol, date_str)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    return None


def _save_transcript(symbol: str, date_str: str, text: str) -> None:
    p = _cache_path(symbol, date_str)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


# ─── LLM CALL WITH 15-RPM THROTTLE AND 429 RETRY ────────────────────────────

def _get_gemini_client():
    from google import genai
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=key)


def _call_llm_sync(client, prompt: str, text_segment: str) -> Dict[str, Any]:
    """
    Single synchronous LLM call.
    Enforces _RPM_SLEEP before every call.
    On 429, sleeps _RATE_LIMIT_PAUSE seconds and retries ONCE.
    Returns parsed dict or {"error": "..."}.
    """
    from google.genai import types

    content = f"{prompt}\n\nTranscript Segment:\n{text_segment[:_TRANSCRIPT_CHARS]}"
    config = types.GenerateContentConfig(
        temperature=_TEMPERATURE,
        response_mime_type="application/json"
    )

    for attempt in range(2):
        time.sleep(_RPM_SLEEP)  # hard throttle before EVERY call
        try:
            resp = client.models.generate_content(
                model=_MODEL,
                contents=content,
                config=config
            )
            raw = resp.text.strip()
            return json.loads(raw)
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                logger.warning(
                    f"[concall_factor] 429 hit — pausing {_RATE_LIMIT_PAUSE}s then retrying "
                    f"(attempt {attempt + 1}/2)"
                )
                time.sleep(_RATE_LIMIT_PAUSE)
                continue
            else:
                logger.error(f"[concall_factor] LLM error: {e}")
                return {"error": err}

    return {"error": "Rate limit exceeded after retry"}


# ─── CORE SCORER ─────────────────────────────────────────────────────────────

async def _score_transcript(
    client,
    symbol: str,
    date_str: str,
    text: str
) -> Dict[str, Any]:
    """
    Runs 3 LLM calls on a real transcript:
      1. Segmentation — find the Q&A boundary phrase
      2. Score Prepared Remarks
      3. Score Q&A

    Returns a fully populated result dict including reasoning.
    """
    logger.info(f"[concall_factor] Scoring {symbol} ({date_str}) — {len(text)} chars")

    # ── 1. Segmentation ──────────────────────────────────────────────────────
    seg = await asyncio.to_thread(_call_llm_sync, client, _SEGMENTATION_PROMPT, text)
    if "error" in seg:
        return {
            "symbol": symbol, "date": date_str,
            "schema_version": _SCHEMA_VERSION,
            "error": f"Segmentation failed: {seg['error']}"
        }

    boundary = (seg.get("boundary_phrase") or "").strip()
    logger.info(f"[concall_factor]   boundary: {boundary[:80]}...")

    # Split on boundary; fall back to 50/50 split if phrase not found in text
    if boundary and boundary in text:
        parts = text.split(boundary, 1)
        prep_text = parts[0]
        qa_text   = boundary + parts[1]
    else:
        logger.warning(f"[concall_factor]   boundary not found verbatim, using 50/50 split")
        mid       = len(text) // 2
        prep_text = text[:mid]
        qa_text   = text[mid:]

    # ── 2. Score Prepared Remarks ─────────────────────────────────────────────
    prep_score = await asyncio.to_thread(_call_llm_sync, client, _SCORING_PROMPT, prep_text)
    if "error" in prep_score:
        return {
            "symbol": symbol, "date": date_str,
            "schema_version": _SCHEMA_VERSION,
            "error": f"Prepared Remarks scoring failed: {prep_score['error']}"
        }

    # ── 3. Score Q&A ─────────────────────────────────────────────────────────
    qa_score = await asyncio.to_thread(_call_llm_sync, client, _SCORING_PROMPT, qa_text)
    if "error" in qa_score:
        return {
            "symbol": symbol, "date": date_str,
            "schema_version": _SCHEMA_VERSION,
            "error": f"Q&A scoring failed: {qa_score['error']}"
        }

    # ── 4. Compute divergence ─────────────────────────────────────────────────
    s_prep = float(prep_score.get("sentiment_score", 0.0))
    s_qa   = float(qa_score.get("sentiment_score",  0.0))
    divergence = round(s_qa - s_prep, 4)

    return {
        "symbol":              symbol,
        "date":                date_str,
        "schema_version":      _SCHEMA_VERSION,
        "scored_at":           datetime.now(timezone.utc).isoformat(),
        "model":               _MODEL,
        "segmentation_boundary": boundary,
        "prepared_remarks":    prep_score,
        "qa":                  qa_score,
        "concall_divergence":  divergence,
        "concall_hesitation":  float(qa_score.get("hesitation_index", 0.0)),
        # Reasoning for human review — not used in IC math, but readable in terminal
        "divergence_reasoning": (
            f"Prepared Remarks sentiment={s_prep:.2f} (hesitation={prep_score.get('hesitation_index',0):.1f}). "
            f"Q&A sentiment={s_qa:.2f} (hesitation={qa_score.get('hesitation_index',0):.1f}). "
            f"Divergence={divergence:+.2f}. "
            f"Prepared Remarks rationale: {prep_score.get('reasoning', 'N/A')} "
            f"Q&A rationale: {qa_score.get('reasoning', 'N/A')}"
        ),
        "qa_hedging_phrases":  qa_score.get("key_hedging_phrases_found", []),
    }


# ─── PUBLIC: RUN FACTOR REFRESH FOR A SYMBOL ────────────────────────────────

async def refresh_concall_factor(symbol: str) -> Dict[str, Any]:
    """
    Fetch, cache, and score up to _MAX_QUARTERS concall transcripts for `symbol`.
    - Transcripts already cached on disk are NOT re-scored (only new quarters are hit).
    - Results are merged into the persistent store and saved.
    Returns list of quarter results for the symbol.
    """
    from extra_service import get_concalls, fetch_pdf_text

    clean = symbol.upper().replace(".NS", "").replace(".BO", "")
    store = _load_store()

    try:
        client = _get_gemini_client()
    except RuntimeError as e:
        return {"error": str(e), "symbol": clean}

    concalls = await asyncio.to_thread(get_concalls, clean)
    if not concalls:
        logger.warning(f"[concall_factor] No concalls found for {clean}")
        return {"symbol": clean, "quarters": [], "warning": "No concalls found on Screener.in"}

    results = []
    count   = 0

    for cc in concalls:
        if count >= _MAX_QUARTERS:
            break
        if not cc.get("transcript"):
            continue

        date_str = cc["date"]
        url      = cc["transcript"]
        key      = _store_key(clean, date_str)

        # Already scored? Return from store — skip all API calls
        if key in store and store[key].get("schema_version") == _SCHEMA_VERSION:
            logger.info(f"[concall_factor] Cache hit: {clean} {date_str}")
            results.append(store[key])
            count += 1
            continue

        # Load transcript text — local cache first, then live PDF download
        text = _load_cached_transcript(clean, date_str)
        if text is None:
            logger.info(f"[concall_factor] Downloading PDF: {url}")
            text = await asyncio.to_thread(fetch_pdf_text, url)
            if text and len(text) > 500:
                _save_transcript(clean, date_str, text)
            else:
                logger.warning(f"[concall_factor] PDF too short or geo-blocked: {url}")
                count += 1
                continue

        # Score the transcript
        result = await _score_transcript(client, clean, date_str, text)
        store[key] = result
        _save_store(store)         # persist after every quarter (crash-safe)
        results.append(result)
        count += 1
        logger.info(
            f"[concall_factor] {clean} {date_str} → divergence={result.get('concall_divergence')}, "
            f"hesitation={result.get('concall_hesitation')}"
        )

    return {"symbol": clean, "quarters": results}


# ─── PUBLIC: GET LATEST FACTOR VALUE FOR A SYMBOL (called by factor_service) ─

def get_latest_concall_factor(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Returns the most recent VALID scored quarter for `symbol` from the store.
    Returns None if no data available yet (factor_service handles the missing-factor case).

    Output dict keys used by factor_service:
      - concall_divergence  : float [-1, +1]
      - concall_hesitation  : float [0, 100]
      - date                : str  (e.g. "Apr 2026")
      - divergence_reasoning: str  (human-readable explanation)
      - qa_hedging_phrases  : list[str]
    """
    clean = symbol.upper().replace(".NS", "").replace(".BO", "")
    store = _load_store()

    # Collect all valid quarters for this symbol
    candidates = []
    for key, val in store.items():
        if not key.startswith(f"{clean}::"):
            continue
        if val.get("schema_version") != _SCHEMA_VERSION:
            continue
        if "error" in val:
            continue
        if "concall_divergence" not in val:
            continue
        candidates.append(val)

    if not candidates:
        return None

    # Sort by scored_at descending — most recent quarter first
    candidates.sort(key=lambda x: x.get("scored_at", ""), reverse=True)
    return candidates[0]


# ─── PUBLIC: BULK REFRESH (called by overnight pipeline) ────────────────────

async def bulk_refresh(symbols: list) -> Dict[str, Any]:
    """
    Refreshes concall factors for a list of symbols sequentially.
    Sequential (not parallel) to respect the 15 RPM API limit.
    Saves results to the persistent store after each symbol.
    """
    summary = {}
    for sym in symbols:
        logger.info(f"[concall_factor] bulk_refresh starting: {sym}")
        result = await refresh_concall_factor(sym)
        quarters = result.get("quarters", [])
        new_scored = sum(1 for q in quarters if "scored_at" in q)
        summary[sym] = {
            "quarters_processed": len(quarters),
            "newly_scored": new_scored,
            "error": result.get("error")
        }
    return summary


# ─── CLI SELF-CHECK (runs only via: python concall_factor_service.py SYMBOL) ─

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sym = sys.argv[1] if len(sys.argv) > 1 else "INFY"

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

    async def _run():
        print(f"\nRunning concall factor refresh for: {sym}")
        result = await refresh_concall_factor(sym)
        quarters = result.get("quarters", [])
        print(f"\n{'='*70}")
        print(f"SYMBOL: {sym}  |  Quarters processed: {len(quarters)}")
        print(f"{'='*70}")
        for q in quarters:
            if "error" in q:
                print(f"\n  [{q.get('date')}]  ERROR: {q['error']}")
                continue
            print(f"\n  Quarter  : {q.get('date')}")
            print(f"  Boundary : {q.get('segmentation_boundary', 'N/A')[:80]}...")
            print(f"  Prep Sent: {q.get('prepared_remarks', {}).get('sentiment_score'):.2f}  "
                  f"Hesitation: {q.get('prepared_remarks', {}).get('hesitation_index'):.1f}")
            print(f"  Q&A  Sent: {q.get('qa', {}).get('sentiment_score'):.2f}  "
                  f"Hesitation: {q.get('qa', {}).get('hesitation_index'):.1f}")
            print(f"  Divergence: {q.get('concall_divergence'):+.4f}")
            print(f"  Hedging phrases: {q.get('qa_hedging_phrases', [])}")
            print(f"  Reasoning: {q.get('divergence_reasoning', '')[:300]}...")

    asyncio.run(_run())
