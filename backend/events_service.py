"""Events calendar (yfinance earnings + NSE board-meeting announcements)."""
import os
import re
import logging
from datetime import date, datetime, timedelta
from dateutil import parser as date_parser
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

