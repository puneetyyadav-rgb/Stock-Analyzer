"""Events calendar (yfinance earnings + NSE board-meeting announcements)."""
import re
import logging
from datetime import datetime
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


def get_events(symbol: str) -> list:
    sym = symbol if symbol.endswith(".NS") or symbol.endswith(".BO") else f"{symbol}.NS"
    events = []
    # yfinance calendar
    try:
        t = yf.Ticker(sym)
        cal = t.calendar
        if isinstance(cal, dict):
            for key, val in cal.items():
                if "Earnings Date" in key and val:
                    if isinstance(val, list):
                        for v in val:
                            events.append({"event": "Earnings Release", "date": _normalize_date(v), "type": "Earnings", "source": "yfinance"})
                    else:
                        events.append({"event": "Earnings Release", "date": _normalize_date(val), "type": "Earnings", "source": "yfinance"})
                elif "Dividend Date" in key and val:
                    events.append({"event": "Dividend Date", "date": _normalize_date(val), "type": "Dividend", "source": "yfinance"})
                elif "Ex-Dividend Date" in key and val:
                    events.append({"event": "Ex-Dividend Date", "date": _normalize_date(val), "type": "Dividend", "source": "yfinance"})
    except Exception as e:
        logger.error(f"events yf error: {e}")
    # NSE board meetings from announcements
    try:
        ann = get_nse_announcements(symbol)
        for a in ann[:50]:
            subj = (a.get("subject") or "").lower()
            if "board meeting" in subj or "intimation of meeting" in subj:
                date_match = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})", a.get("subject") or "")
                meeting_date = date_match.group(1) if date_match else _normalize_date(a.get("date"))
                events.append({
                    "event": a.get("subject", "")[:140],
                    "date": meeting_date,
                    "type": "Board Meeting",
                    "source": "NSE announcement",
                })
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
