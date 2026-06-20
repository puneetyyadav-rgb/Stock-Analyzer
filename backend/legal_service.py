"""Legal / regulatory disclosures — sourced from NSE corporate-announcements (scraped,
reusing the same session/cookie pattern as the options chain). There is no official
SEBI developer API; do not represent this as one anywhere in the UI."""
import os
import json
import logging
from extra_service import _nse_session, _strip_symbol
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

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


async def classify_legal_announcements(items: list) -> list:
    if not items or not EMERGENT_LLM_KEY:
        return []
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id="legal-classify",
        system_message=CLASSIFY_PROMPT,
    ).with_model("gemini", "gemini-3-flash-preview")
    msg = UserMessage(text=json.dumps(items[:20], default=str))
    try:
        resp = await chat.send_message(msg)
        text = str(resp).strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text else text
            if text.lower().startswith("json"):
                text = text[4:].strip()
            text = text.rstrip("`").strip()
        start, end = text.find("["), text.rfind("]")
        return json.loads(text[start:end + 1]) if start != -1 else []
    except Exception as e:
        logger.error(f"classify legal error: {e}")
        return []
