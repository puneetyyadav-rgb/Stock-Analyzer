"""Legal / regulatory disclosures — sourced from NSE corporate-announcements (scraped,
reusing the same session/cookie pattern as the options chain). There is no official
SEBI developer API; do not represent this as one anywhere in the UI."""
import os
import json
import logging
import asyncio
from extra_service import _nse_session, _strip_symbol
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_gemini_client():
    key = os.environ.get("GEMINI_API_KEY")
    return genai.Client(api_key=key) if key else None

LEGAL_KEYWORDS = [
    "court", "litigation", "sebi", "arbitration", "nclt", "tribunal",
    "show cause", "show-cause", "sast", "insider trading", "winding up",
    "suit filed", "adjudication", "penalty",
]


def get_nse_announcements(symbol: str) -> list:
    clean = _strip_symbol(symbol)
    s = _nse_session()
    try:
        url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={clean}"
        r = s.get(url, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", [])
        return [
            {
                "subject": d.get("subject") or d.get("desc") or "",
                "date": d.get("an_dt") or d.get("date"),
                "attachment": d.get("attchmntFile"),
            }
            for d in items
        ]
    except Exception:
        return []


def filter_legal_relevant(announcements: list) -> list:
    return [
        a for a in announcements
        if any(k in (a.get("subject") or "").lower() for k in LEGAL_KEYWORDS)
    ]


CLASSIFY_PROMPT = """You are tagging Indian corporate disclosure announcements.
For each announcement given, output one JSON object with:
{"announcement": "", "category": "Litigation | SAST/Insider | Related-Party | Regulatory Action | Board/Governance | Other", "severity": "Critical | High | Medium | Low", "summary": "one factual sentence, no speculation"}
Return a JSON array, same order as input. If the input array is empty, return [].
Do not invent details not present in the announcement subject — if a subject is vague, say so in summary rather than guessing."""


def sync_classify(prompt: str) -> str:
    from ai_service import sync_generate_verdict
    return sync_generate_verdict(prompt)

async def classify_legal_announcements(items: list) -> list:
    from ai_service import _has_any_ai_key
    if not items or not _has_any_ai_key():
        return []
    
    prompt = f"{CLASSIFY_PROMPT}\n\n{json.dumps(items[:20], default=str)}"
    try:
        text = await asyncio.to_thread(sync_classify, prompt)
        text = text.strip()
        result = json.loads(text)
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], list):
            result = result[0]
        return result
    except Exception as e:
        logger.error(f"classify legal error: {e}")
        return []
