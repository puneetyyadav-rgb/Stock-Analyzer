"""Events calendar (yfinance earnings + NSE board-meeting announcements)."""
import re
import logging
from datetime import date, datetime
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
