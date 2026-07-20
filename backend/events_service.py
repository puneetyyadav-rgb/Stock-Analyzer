"""Events calendar (yfinance earnings + NSE board-meeting announcements)."""
import os
import re
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from dateutil import parser as date_parser
import pandas as pd
import yfinance as yf
from legal_service import get_nse_announcements

logger = logging.getLogger(__name__)


def _normalize_date(d) -> str:
    if not d:
        return ""
    if hasattr(d, "isoformat"):
        return d.isoformat()[:10]
    s = str(d)
    return s[:10]


def _parse_date(value):
    if not value:
        return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except (TypeError, ValueError):
            pass
    text = str(value).strip()
    try:
        if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", text):
            return date.fromisoformat(text[:10].replace("/", "-"))
        return date_parser.parse(text, dayfirst=True).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _future_event(event: str, value, event_type: str, source: str, today) -> dict | None:
    event_date = _parse_date(value)
    if not event_date or event_date < today:
        return None
    return {
        "event": event,
        "date": event_date.isoformat(),
        "type": event_type,
        "source": source,
    }


def _date_from_subject(subject: str):
    patterns = (
        r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, subject, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def get_events(symbol: str, today=None) -> list:
    sym = symbol if symbol.endswith(".NS") or symbol.endswith(".BO") else f"{symbol}.NS"
    events = []
    today = today or datetime.now().astimezone().date()
    # yfinance calendar
    try:
        t = yf.Ticker(sym)
        cal = t.calendar
        if isinstance(cal, dict):
            for key, val in cal.items():
                if "Earnings Date" in key and val:
                    if isinstance(val, list):
                        for v in val:
                            event = _future_event("Earnings Release", v, "Earnings", "yfinance", today)
                            if event:
                                events.append(event)
                    else:
                        event = _future_event("Earnings Release", val, "Earnings", "yfinance", today)
                        if event:
                            events.append(event)
                elif "Dividend Date" in key and val:
                    event = _future_event("Dividend Date", val, "Dividend", "yfinance", today)
                    if event:
                        events.append(event)
                elif "Ex-Dividend Date" in key and val:
                    event = _future_event("Ex-Dividend Date", val, "Dividend", "yfinance", today)
                    if event:
                        events.append(event)
    except Exception as e:
        logger.error(f"events yf error: {e}")
    # NSE board meetings from announcements
    try:
        ann = get_nse_announcements(symbol)
        for a in ann[:50]:
            subj = (a.get("subject") or "").lower()
            if "board meeting" in subj or "intimation of meeting" in subj:
                # Announcement date is not the meeting date. Only publish an
                # event when the subject contains an explicit future date.
                meeting_date = _date_from_subject(a.get("subject") or "")
                event = _future_event(
                    a.get("subject", "")[:140], meeting_date,
                    "Board Meeting", "NSE announcement", today,
                )
                if event:
                    events.append(event)
    except Exception as e:
        logger.error(f"events nse error: {e}")
    # de-dupe & sort
    seen = set()
    unique = []
    for ev in events:
        key = (ev.get("event"), ev.get("date"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)
    unique.sort(key=lambda x: x.get("date") or "9999")
    return unique[:20]


# =====================================================================
# PHASE 2: DETERMINISTIC DATE EXTRACTION (Catalyst Radar Backfill)
# =====================================================================

TRIGGER_PHRASES = [
    "scheduled for", "expected by", "record date", "hearing on", "due by",
    "targeted completion", "expected in", "targeted for", "slated for",
    "likely by", "timeline is", "completion by", "listed on", "board meeting on"
]


def init_catalyst_events_table() -> None:
    """Initializes the Phase 2 catalyst_events table inside catalyst_archive.db."""
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "data", "catalyst_archive.db")
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS catalyst_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    extracted_date TEXT NOT NULL,
                    raw_snippet TEXT NOT NULL,
                    date_confidence TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, source_type, source_ref, extracted_date, raw_snippet)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cat_ev_sym ON catalyst_events(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cat_ev_date ON catalyst_events(extracted_date)")
    finally:
        conn.close()


def run_catalyst_extraction(symbol: str = None, days_forward: int = 180) -> dict:
    """Runs deterministic Phase 2 regex date extraction over archived NSE announcements and concall transcripts.
    Stores raw extracted future dates and snippets into catalyst_events. Zero AI calls.
    Returns: {'extracted': N, 'inserted': M}
    """
    import sqlite3
    from extra_service import _strip_symbol
    init_catalyst_events_table()

    db_path = os.path.join(os.path.dirname(__file__), "data", "catalyst_archive.db")
    if not os.path.exists(db_path):
        return {"extracted": 0, "inserted": 0}

    today = datetime.now().astimezone().date()
    max_date = today + timedelta(days=days_forward)
    stats = {"extracted": 0, "inserted": 0}

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        # 1. Scan announcements_archive (High confidence)
        query_ann = "SELECT symbol, announcement_id, subject, full_text FROM announcements_archive"
        params_ann = []
        if symbol:
            query_ann += " WHERE symbol = ?"
            params_ann.append(_strip_symbol(symbol))

        rows_ann = conn.execute(query_ann, params_ann).fetchall()
        for row in rows_ann:
            sym = row["symbol"]
            ann_id = str(row["announcement_id"])
            text = row["full_text"] or row["subject"] or ""
            if not text:
                continue

            # Split into manageable sentences or paragraphs
            sentences = re.split(r'(?<=[.!?\n])\s+', text)
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) < 15 or len(s_clean) > 500:
                    continue
                
                matched_date_str = _date_from_subject(s_clean)
                if matched_date_str:
                    parsed = _parse_date(matched_date_str)
                    if parsed and today <= parsed <= max_date:
                        stats["extracted"] += 1
                        snippet = s_clean[:280]
                        with conn:
                            conn.execute("""
                                INSERT OR IGNORE INTO catalyst_events (
                                    symbol, source_type, source_ref, extracted_date,
                                    raw_snippet, date_confidence, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                sym, "NSE_ANNOUNCEMENT", ann_id, parsed.isoformat(),
                                snippet, "High", datetime.now().isoformat()
                            ))
                            if conn.total_changes > 0:
                                stats["inserted"] += 1

        # 2. Scan concalls_archive (Medium confidence, strictly gated to trigger phrases)
        query_conc = "SELECT symbol, quarter_label, full_text FROM concalls_archive"
        params_conc = []
        if symbol:
            query_conc += " WHERE symbol = ?"
            params_conc.append(_strip_symbol(symbol))

        rows_conc = conn.execute(query_conc, params_conc).fetchall()
        for row in rows_conc:
            sym = row["symbol"]
            q_label = str(row["quarter_label"])
            text = row["full_text"] or ""
            if not text:
                continue

            sentences = re.split(r'(?<=[.!?\n])\s+', text)
            for s in sentences:
                s_clean = s.strip()
                if len(s_clean) < 20 or len(s_clean) > 500:
                    continue
                
                # Check trigger phrase first!
                s_lower = s_clean.lower()
                if not any(tp in s_lower for tp in TRIGGER_PHRASES):
                    continue

                matched_date_str = _date_from_subject(s_clean)
                if matched_date_str:
                    parsed = _parse_date(matched_date_str)
                    if parsed and today <= parsed <= max_date:
                        stats["extracted"] += 1
                        snippet = s_clean[:280]
                        with conn:
                            conn.execute("""
                                INSERT OR IGNORE INTO catalyst_events (
                                    symbol, source_type, source_ref, extracted_date,
                                    raw_snippet, date_confidence, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                sym, "CONCALL_TRANSCRIPT", q_label, parsed.isoformat(),
                                snippet, "Medium", datetime.now().isoformat()
                            ))
                            if conn.total_changes > 0:
                                stats["inserted"] += 1
    finally:
        conn.close()

    logger.info(f"Phase 2 extraction completed: Extracted {stats['extracted']} future snippets, Inserted {stats['inserted']} new rows.")
    return stats


def get_extracted_catalyst_events(symbol: str = None, days_forward: int = 30) -> list:
    """Retrieves extracted future catalyst events from SQLite archive sorted chronologically."""
    import sqlite3
    from extra_service import _strip_symbol
    init_catalyst_events_table()
    db_path = os.path.join(os.path.dirname(__file__), "data", "catalyst_archive.db")
    if not os.path.exists(db_path):
        return []

    today = datetime.now().astimezone().date()
    max_date = today + timedelta(days=days_forward)

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM catalyst_events WHERE extracted_date >= ? AND extracted_date <= ?"
        params = [today.isoformat(), max_date.isoformat()]
        if symbol:
            query += " AND symbol = ?"
            params.append(_strip_symbol(symbol))
        query += " ORDER BY extracted_date ASC, date_confidence DESC LIMIT 100"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# =====================================================================
# PHASE 3: CLASSIFICATION, NOT PREDICTION (Catalyst Radar Labeling)
# =====================================================================

CATALYST_CLASSIFY_PROMPT = """You are classifying Indian corporate disclosure events for a Catalyst Radar dashboard.
For each event given (a raw snippet extracted from an official NSE/BSE filing), output one JSON object with:
{
  "category": "Legal/Regulatory | Corporate Action | Board/Governance | Debt/Refinancing | Regulatory Approval | Dividend | AGM/EGM | Other",
  "summary": "one factual sentence paraphrased from the snippet — cite what is scheduled, not what might happen"
}

HARD RULES:
1. Do NOT predict the outcome of this event.
2. Do NOT output a probability, score, percentage, or bullish/bearish label.
3. State ONLY what is scheduled and cite the source filing.
4. If the snippet is vague or unclear, say so honestly in the summary rather than guessing.
5. Do NOT invent details not present in the raw snippet.

Return a JSON array, same order as input. If input is empty, return [].
"""


def _classify_sync(prompt: str) -> str:
    """Synchronous wrapper for Gemini classification call."""
    from ai_service import sync_generate_verdict
    return sync_generate_verdict(prompt)


async def classify_catalyst_events(events: list) -> list:
    """Phase 3: Classify extracted catalyst events using Gemini with strict anti-hallucination rules.
    Takes raw catalyst_events rows and returns classified events with category + factual summary.
    """
    import asyncio as _asyncio
    import json as _json
    from ai_service import _has_any_ai_key

    if not events or not _has_any_ai_key():
        return events

    # Build classification input from raw snippets
    classify_input = []
    for ev in events:
        classify_input.append({
            "symbol": ev.get("symbol", ""),
            "extracted_date": ev.get("extracted_date", ""),
            "raw_snippet": ev.get("raw_snippet", ""),
            "source_type": ev.get("source_type", ""),
            "date_confidence": ev.get("date_confidence", ""),
        })

    prompt = f"{CATALYST_CLASSIFY_PROMPT}\n\n{_json.dumps(classify_input[:30], default=str)}"

    try:
        text = await _asyncio.to_thread(_classify_sync, prompt)
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        classified = _json.loads(text)
        if isinstance(classified, list) and len(classified) == 1 and isinstance(classified[0], list):
            classified = classified[0]

        # Merge classification back into original events
        result = []
        for i, ev in enumerate(events):
            merged = dict(ev)
            if i < len(classified) and isinstance(classified[i], dict):
                merged["category"] = classified[i].get("category", "Other")
                merged["summary"] = classified[i].get("summary", merged.get("raw_snippet", "")[:120])
            else:
                merged["category"] = "Other"
                merged["summary"] = merged.get("raw_snippet", "")[:120]
            result.append(merged)
        return result

    except Exception as e:
        logger.error(f"Phase 3 classify catalyst error: {e}")
        # Fallback: return events with category=Other and snippet as summary
        for ev in events:
            ev["category"] = "Other"
            ev["summary"] = ev.get("raw_snippet", "")[:120]
        return events


_RESULTS_DUE_CACHE = {"timestamp": 0, "days": -1, "data": None}
_YF_CAL_CACHE = {}


def get_forthcoming_board_meetings(symbol: Optional[str] = None) -> list:
    """Hits NSE's structured /api/event-calendar endpoint to pull exact upcoming board meetings
    and forthcoming corporate actions without free-text or regex mining.
    """
    try:
        import catalyst_archive_service as cas
        session = cas._nse_session()
        res = session.get("https://www.nseindia.com/api/event-calendar", timeout=12).json()
        if not isinstance(res, list):
            return []
        if symbol:
            clean = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
            return [r for r in res if str(r.get("symbol", "")).upper() == clean]
        return res
    except Exception as e:
        logger.error(f"Error fetching forthcoming board meetings from NSE: {e}")
        return []


def _get_yf_consensus(clean_sym: str) -> dict:
    import time
    now = time.time()
    if clean_sym in _YF_CAL_CACHE:
        entry = _YF_CAL_CACHE[clean_sym]
        if now - entry["time"] < 3600:
            return entry["data"]
    data = {}
    try:
        t = yf.Ticker(f"{clean_sym}.NS")
        cal = t.calendar
        if isinstance(cal, dict):
            if cal.get("Earnings Average") is not None:
                data["eps_avg"] = round(float(cal["Earnings Average"]), 2)
            if cal.get("Earnings High") is not None:
                data["eps_high"] = round(float(cal["Earnings High"]), 2)
            if cal.get("Earnings Low") is not None:
                data["eps_low"] = round(float(cal["Earnings Low"]), 2)
            if cal.get("Revenue Average") is not None:
                data["rev_avg_cr"] = round(float(cal["Revenue Average"]) / 1e7, 2)
    except Exception:
        pass
    _YF_CAL_CACHE[clean_sym] = {"time": now, "data": data}
    return data


# =====================================================================
# PHASE 5: RESULT EXPECTATIONS & SENTIMENT TRACKER — fast math layer
# =====================================================================

_YF_TARGET_CACHE = {}
_RUNUP_CACHE = {}


def _get_yf_target_data(clean_sym: str) -> dict:
    """Analyst target price + recommendation, 1h cache. Deliberately reuses
    stock_service.get_overview() instead of issuing a second yfinance .info
    call — that function already fetches targetMeanPrice/recommendationKey."""
    import time
    now = time.time()
    if clean_sym in _YF_TARGET_CACHE:
        entry = _YF_TARGET_CACHE[clean_sym]
        if now - entry["time"] < 3600:
            return entry["data"]

    data = {
        "current_price": None,
        "target_mean_price": None,
        "recommendation_key": None,
        "num_analysts": None,
        "target_upside_pct": None,
    }
    try:
        import stock_service as ss
        ov = ss.get_overview(clean_sym)
        price = ov.get("price")
        target = ov.get("targetMeanPrice")
        data["current_price"] = price
        data["target_mean_price"] = target
        data["recommendation_key"] = ov.get("recommendation")
        data["num_analysts"] = ov.get("numAnalysts")
        if price and target and price > 0:
            data["target_upside_pct"] = round(((target - price) / price) * 100.0, 2)
    except Exception as e:
        logger.error(f"yf target data error for {clean_sym}: {e}")

    _YF_TARGET_CACHE[clean_sym] = {"time": now, "data": data}
    return data


def _classify_runup(pct) -> dict:
    """Maps the 10-day pre-earnings run-up to the brief's three badge tiers."""
    if pct is None:
        return {"label": "Unknown", "emoji": "❔", "tone": "gray"}
    if pct > 8.0:
        return {"label": "High Hype / Run-up", "emoji": "🔥", "tone": "red"}
    if pct < -5.0:
        return {"label": "Low Bar / Depressed", "emoji": "❄️", "tone": "blue"}
    return {"label": "Neutral", "emoji": "⚖️", "tone": "gray"}


def _get_preearnings_runup_from_panel(clean_sym: str, window: int = 10):
    """PRIMARY path. factor_service already loads the full NSE Bhavcopy close-price
    panel in memory for the Factor Profile block on this same card — reusing it here
    means zero extra network calls, and the run-up figure is methodologically
    consistent with the mom_20d figure shown a few pixels away on the UI."""
    try:
        import factor_service as fs
        panel = fs.load_panel()
        wc = fs._wide(panel, "close")
        if clean_sym not in wc.columns:
            return None
        series = wc[clean_sym].dropna()
        if len(series) <= window:
            return None
        latest, prior = series.iloc[-1], series.iloc[-1 - window]
        if not prior or pd.isna(prior) or pd.isna(latest):
            return None
        return round(((latest / prior) - 1.0) * 100.0, 2)
    except Exception as e:
        logger.debug(f"panel run-up lookup failed for {clean_sym}: {e}")
        return None


def _get_preearnings_runup_from_yfinance(clean_sym: str, window: int = 10):
    """FALLBACK path — only hit when the symbol isn't in the local Bhavcopy universe
    yet (e.g. a very recent listing). Mirrors the auto_adjust=True convention used
    elsewhere in stock_service.py for return-style (not level-style) calculations."""
    try:
        hist = yf.Ticker(f"{clean_sym}.NS").history(period="1mo", interval="1d", auto_adjust=True)
        closes = hist["Close"].dropna() if not hist.empty else hist
        if len(closes) <= window:
            return None
        latest, prior = float(closes.iloc[-1]), float(closes.iloc[-1 - window])
        if not prior:
            return None
        return round(((latest / prior) - 1.0) * 100.0, 2)
    except Exception as e:
        logger.debug(f"yfinance run-up fallback failed for {clean_sym}: {e}")
        return None


def _get_preearnings_runup(clean_sym: str) -> dict:
    import time
    now = time.time()
    if clean_sym in _RUNUP_CACHE:
        entry = _RUNUP_CACHE[clean_sym]
        if now - entry["time"] < 3600:
            return entry["data"]

    pct = _get_preearnings_runup_from_panel(clean_sym)
    source = "bhavcopy_panel"
    if pct is None:
        pct = _get_preearnings_runup_from_yfinance(clean_sym)
        source = "yfinance_fallback"

    data = {"runup_pct": pct, "source": source if pct is not None else None, **_classify_runup(pct)}
    _RUNUP_CACHE[clean_sym] = {"time": now, "data": data}
    return data


def get_results_due(days: int = 30, force_refresh: bool = False) -> dict:
    """Builds the institutional 'Results Due' & forthcoming corporate actions tracker:
    1. structured board meetings from NSE /api/event-calendar
    2. filtered & tagged by purpose (Financial Results vs Dividend/Rights/Bonus)
    3. enriched with yfinance consensus EPS/revenue estimates
    4. enriched with factual 9-factor snapshots (delivery%, vol trend, 20d momentum, composite rank)
    """
    import time
    from concurrent.futures import ThreadPoolExecutor
    import factor_service as fs

    now_ts = time.time()
    if not force_refresh and _RESULTS_DUE_CACHE["data"] and _RESULTS_DUE_CACHE["days"] == days and (now_ts - _RESULTS_DUE_CACHE["timestamp"] < 600):
        return _RESULTS_DUE_CACHE["data"]
    if force_refresh:
        logger.info(f"Bypassing internal _RESULTS_DUE_CACHE and fetching live from NSE API (days={days})")

    today = datetime.now().astimezone().date()
    max_date = today + timedelta(days=days)

    raw_items = get_forthcoming_board_meetings()
    cards = []
    unique_symbols = []

    for item in raw_items:
        date_str = str(item.get("date", "")).strip()
        meeting_date = _parse_date(date_str)
        if not meeting_date or meeting_date < today or meeting_date > max_date:
            continue

        sym = str(item.get("symbol", "")).upper().strip()
        if not sym:
            continue

        purpose = str(item.get("purpose", "")).strip()
        p_low = purpose.lower()

        if "result" in p_low or "unaudited" in p_low or "audited" in p_low:
            event_type = "Financial Results"
            badge_color = "red"
        elif "dividend" in p_low:
            event_type = "Dividend / Payout"
            badge_color = "green"
        elif "fund raising" in p_low or "rights" in p_low or "bonus" in p_low or "split" in p_low:
            event_type = "Corporate Action (Bonus/Rights/Split)"
            badge_color = "purple"
        else:
            event_type = "Board Meeting / Governance"
            badge_color = "blue"

        cards.append({
            "symbol": sym,
            "company": str(item.get("company", sym)),
            "purpose": purpose,
            "description": str(item.get("bm_desc", purpose)),
            "meeting_date": meeting_date.isoformat(),
            "countdown_days": (meeting_date - today).days,
            "event_type": event_type,
            "badge_color": badge_color
        })
        if sym not in unique_symbols:
            unique_symbols.append(sym)

    # Sort ascending by nearest meeting date
    cards.sort(key=lambda x: (x["meeting_date"], x["symbol"]))

    # Pre-load all factor scores once in memory for instantaneous lookup across all cards
    z_frame = None
    rank_col = "composite"
    comp_series = None
    try:
        z, as_of, n, meta = fs._latest_scores()
        if z is not None:
            z_frame = z
            rank_col = fs._ranking_col(z)
            comp_series = z[rank_col].dropna()
    except Exception as e:
        logger.debug(f"Factor scores pre-load warning in get_results_due: {e}")

    # Fast factor snapshot assignment for ALL cards instantly
    for card in cards:
        sym = card["symbol"]
        if z_frame is not None and sym in z_frame.index:
            try:
                row = z_frame.loc[sym]
                if pd.notna(row.get(rank_col)):
                    pctile = round(float((comp_series < comp_series[sym]).mean()) * 100.0, 1) if comp_series is not None and sym in comp_series else None
                    decile = int(min(9, int(pctile // 10)) + 1) if pctile is not None else None
                    card["factor_snapshot"] = {
                        "composite": round(float(row.get(rank_col, 0)), 3),
                        "decile": decile,
                        "percentile": pctile,
                        "deliv_pct": round(float(row.get("deliv_pct", 0)), 3) if pd.notna(row.get("deliv_pct")) else None,
                        "vol_trend": round(float(row.get("vol_trend", 0)), 3) if pd.notna(row.get("vol_trend")) else None,
                        "mom_20d": round(float(row.get("m_20d", 0)), 3) if pd.notna(row.get("m_20d")) else None,
                        "adv_cr": round(float(row.get("advTurnoverCr", 0)), 2) if pd.notna(row.get("advTurnoverCr")) else None
                    }
                else:
                    card["factor_snapshot"] = None
            except Exception:
                card["factor_snapshot"] = None
        else:
            card["factor_snapshot"] = None

        # Default consensus to null, enrich top 25 quickly with threadpool
        card["consensus"] = None
        card["target_data"] = None
        card["runup"] = None

    # Enrich top 25 nearest cards with yfinance consensus + target upside +
    # pre-earnings run-up, concurrently (~1-2s total; run-up prefers the
    # in-memory Bhavcopy panel so it adds almost no extra latency)
    def _fetch_expectations(card):
        sym = card["symbol"]
        c = _get_yf_consensus(sym)
        card["consensus"] = c if c else None
        card["target_data"] = _get_yf_target_data(sym)
        card["runup"] = _get_preearnings_runup(sym)
        return card

    with ThreadPoolExecutor(max_workers=8) as pool:
        cards[:25] = list(pool.map(_fetch_expectations, cards[:25]))

    res = {
        "total": len(cards),
        "days_horizon": days,
        "as_of": today.isoformat(),
        "results_due": cards
    }
    _RESULTS_DUE_CACHE["timestamp"] = now_ts
    _RESULTS_DUE_CACHE["days"] = days
    _RESULTS_DUE_CACHE["data"] = res
    return res


# =====================================================================
# PHASE 5: DUAL-SOURCE GATED GUIDANCE EXTRACTION
# =====================================================================

def _select_latest_by_parsed_date(rows: list, date_key: str):
    """SQL ORDER BY on date_published isn't reliable (raw NSE text, not ISO).
    Pull a small batch, then use the module's own _parse_date() to find the
    true most-recent row."""
    best, best_date = None, None
    for row in rows:
        d = _parse_date(row.get(date_key))
        if d and (best_date is None or d > best_date):
            best_date, best = d, row
    return best or (rows[0] if rows else None)


def _fetch_guidance_source_text(symbol: str) -> dict:
    """Dual-source fetch per Addendum #1: latest concall transcript tail +
    latest Investor Presentation / Press Release. Both tables are already
    populated by catalyst_archive_service.archive_nse_announcements() and
    the concall archival job — this function is read-only, no network calls."""
    import sqlite3
    from extra_service import _strip_symbol
    import catalyst_archive_service as cas

    clean_sym = _strip_symbol(symbol)
    conn = cas.get_db_connection()   # existing helper — sqlite3.Row factory already set
    try:
        transcript_rows = conn.execute(
            """SELECT quarter_label, full_text, date_published
               FROM concalls_archive WHERE symbol = ?
               ORDER BY date_published DESC, id DESC LIMIT 5""",
            (clean_sym,)
        ).fetchall()
        transcript_row = _select_latest_by_parsed_date([dict(r) for r in transcript_rows], "date_published")

        ann_rows = conn.execute(
            """SELECT subject, full_text, date_published FROM announcements_archive
               WHERE symbol = ? AND (subject LIKE '%Investor Presentation%'
                                      OR subject LIKE '%Press Release%')
               ORDER BY date_published DESC, id DESC LIMIT 10""",
            (clean_sym,)
        ).fetchall()
        ann_row = _select_latest_by_parsed_date([dict(r) for r in ann_rows], "date_published")
    finally:
        conn.close()

    if not transcript_row or not transcript_row.get("full_text"):
        try:
            import extra_service as ex
            concalls = ex.get_concalls(clean_sym)
            if concalls and concalls[0].get("transcript"):
                t_url = concalls[0]["transcript"]
                t_date = concalls[0].get("date") or "Latest"
                text = ex.fetch_pdf_text(t_url, 30000)
                if text and len(text) > 500:
                    transcript_row = {"full_text": text, "quarter_label": t_date}
                    with cas.get_db_connection() as c:
                        c.execute(
                            """INSERT OR REPLACE INTO concalls_archive (symbol, quarter_label, full_text, date_published, created_at)
                               VALUES (?, ?, ?, ?, ?)""",
                            (clean_sym, t_date, text, datetime.now().strftime("%Y-%m-%d"), datetime.now().isoformat())
                        )
        except Exception as auto_err:
            logger.debug(f"Auto-fetch concall failed for {clean_sym}: {auto_err}")

    transcript_excerpt = ""
    if transcript_row and transcript_row.get("full_text"):
        text = transcript_row["full_text"]
        if len(text) > 22000:
            transcript_excerpt = "=== MANAGEMENT OPENING REMARKS & GUIDANCE ===\n" + text[:11000] + "\n\n=== Q&A SESSION EXCERPTS ===\n" + text[-11000:]
        else:
            transcript_excerpt = text

    announcement_excerpt, announcement_label = "", None
    if ann_row and ann_row.get("full_text"):
        announcement_excerpt = ann_row["full_text"][:6000]
        subj_lower = (ann_row.get("subject") or "").lower()
        announcement_label = "Investor Presentation" if "presentation" in subj_lower else "Press Release"

    return {
        "transcript_excerpt": transcript_excerpt,
        "transcript_quarter": transcript_row.get("quarter_label") if transcript_row else None,
        "announcement_excerpt": announcement_excerpt,
        "announcement_label": announcement_label,
        "announcement_subject": ann_row.get("subject") if ann_row else None,
    }


GUIDANCE_EXTRACTION_PROMPT = """You are a STRICT DATA EXTRACTION engine for an Indian equity research terminal.
You are NOT a financial analyst. You must not summarize, interpret, or predict.

SOURCE MATERIAL below is (a) an excerpt from the company's most recent earnings call
transcript (opening remarks + Q&A tail), and/or (b) the most recent Investor
Presentation or Press Release filed with the exchange. Either source may be empty.

TASK: Extract ONLY officially, explicitly stated numerical targets or guidance for the
NEXT quarter, NEXT fiscal year, or multi-year strategic targets (e.g. FY28/FY29 targets,
3-5 year goals, revenue growth %, margin target, capex, capacity expansion targets,
volume guidance, EPS target, etc).

HARD RULES:
1. Do NOT infer, calculate, round, or extrapolate any number not stated verbatim.
2. Do NOT summarize sentiment, tone, or outlook in prose.
3. Do NOT invent a target because the text "sounds bullish" or "sounds bearish."
4. If a target appears in both sources, list both occurrences separately with their source.
5. If NO explicit numerical guidance exists in the text provided, set "guidance_found"
   to false and "statements" to an empty array. Do not guess.
6. Output STRICT JSON only. No markdown fences, no commentary outside the JSON object.

Schema:
{
  "guidance_found": true | false,
  "statements": [
    {
      "source": "Earnings Call Transcript" | "Investor Presentation" | "Press Release",
      "metric": "short label, e.g. Revenue Growth Target",
      "quote": "the exact sentence stating the target, verbatim from the source text"
    }
  ]
}

SOURCE TEXT:
{combined_text}
"""


async def extract_management_guidance(symbol: str, force_refresh: bool = False) -> dict:
    """Strictly-gated dual-source guidance extraction (Addendum #1). The only
    network call is the single AI request — both sources are local archive
    reads, so this is cheap to retry and safe to cache hard.
    """
    clean_sym = symbol.upper().split(".")[0]
    src = _fetch_guidance_source_text(clean_sym)
    if not src["transcript_excerpt"] and not src["announcement_excerpt"]:
        return {
            "guidance_found": False,
            "statements": [],
            "error": "No concall transcript or presentation/press release archived locally.",
            "concall_checked": False,
        }

    parts = []
    if src["transcript_excerpt"]:
        header = f"=== Earnings Call Transcript ({src.get('transcript_quarter') or 'Latest Quarter'}) ==="
        parts.append(f"{header}\n{src['transcript_excerpt']}")
    if src["announcement_excerpt"]:
        header = f"=== {src['announcement_label']} ({src.get('announcement_subject') or 'Latest'}) ==="
        parts.append(f"{header}\n{src['announcement_excerpt']}")

    prompt = GUIDANCE_EXTRACTION_PROMPT.replace("{combined_text}", "\n\n".join(parts))

    try:
        import asyncio
        import json as _json
        import ai_service as ai
        # Run synchronous AI call in a background thread so we don't block Uvicorn event loop
        text = await asyncio.to_thread(ai._call_groq_fallback, prompt)

        # Bulletproof slice: extract exactly what is between the first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end >= start:
            text = text[start : end + 1]

        result = _json.loads(text)
        raw_stmts = result.get("statements") or []
        unique_stmts = []
        seen = set()
        for s in raw_stmts:
            if not isinstance(s, dict):
                continue
            quote = (s.get("quote") or "").strip()
            metric = (s.get("metric") or "").strip()
            if not quote or not metric:
                continue
            k = (metric.lower(), quote.lower())
            if k not in seen:
                seen.add(k)
                unique_stmts.append({"source": s.get("source") or "Transcript", "metric": metric, "quote": quote})
        result["statements"] = unique_stmts
        result["guidance_found"] = bool(unique_stmts) if result.get("guidance_found") else False
        result["concall_checked"] = bool(src["transcript_excerpt"])
        result["concall_quarter"] = src.get("transcript_quarter") or "Latest"
        return result
    except Exception as e:
        logger.error(f"guidance extraction error for {symbol}: {e}")
        return {"error": str(e), "guidance_found": False, "statements": []}
