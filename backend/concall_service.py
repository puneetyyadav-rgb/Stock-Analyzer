"""Concall transcript summarization using Gemini 3 Flash via Emergent Universal Key."""
import os
import json
import logging
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

CONCALL_SYSTEM = """You are an Indian equity research analyst specializing in earnings call analysis.
Extract structured insights from a quarterly earnings concall transcript.
Output STRICT JSON only — no markdown fences, no commentary.
Schema:
{
  "highlights": ["3-6 bullet headline points from the quarter"],
  "guidance": ["3-5 bullets on forward guidance, FY-targets, capex plans"],
  "newOrders": ["any big order/deal/contract wins mentioned, else empty array"],
  "concerns": ["3-5 bullets on management-flagged risks or weak areas"],
  "qaInsights": ["3-5 key questions/answers from analyst Q&A"],
  "sentimentScore": -10 to 10,
  "sentimentLabel": "Strongly Bullish" | "Bullish" | "Cautious" | "Neutral" | "Bearish",
  "managementTone": "1-2 sentence assessment of management confidence/tone",
  "verdict": "1-2 sentence overall takeaway",
  "keyMetricsMentioned": {"revenue": "string", "margins": "string", "growth": "string", "other": "string"}
}"""


ALTERNATIVE_SYSTEM = """You are an Indian equity research analyst. The official concall transcript PDF is unavailable
from the server's location, so synthesize a 'Management & Business Insights' summary using ONLY the provided
recent news headlines, business description, Screener.in pros/cons, and key metrics. Be honest that this is
indirect (not from the transcript itself). Output STRICT JSON only — no markdown.
Schema is same as transcript schema:
{
  "highlights": [...],
  "guidance": [...],
  "newOrders": [...],
  "concerns": [...],
  "qaInsights": [],
  "sentimentScore": -10 to 10,
  "sentimentLabel": "...",
  "managementTone": "1-2 sentences",
  "verdict": "1-2 sentence overall takeaway prefixed with '[INDIRECT — synthesized from news/Screener]'",
  "keyMetricsMentioned": {"revenue": "...", "margins": "...", "growth": "...", "other": "..."}
}"""


async def summarize_alternative(symbol: str, date_str: str, context: dict) -> dict:
    if not EMERGENT_LLM_KEY:
        return {"error": "LLM key missing"}
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"alt-concall-{symbol}-{date_str}",
        system_message=ALTERNATIVE_SYSTEM,
    ).with_model("gemini", "gemini-3-flash-preview")
    user_msg = UserMessage(
        text=f"Symbol: {symbol}\nApprox quarter: {date_str}\n\nContext:\n{json.dumps(context, default=str)[:8000]}"
    )
    try:
        resp = await chat.send_message(user_msg)
        text = resp if isinstance(resp, str) else str(resp)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text else text
            if text.lower().startswith("json"):
                text = text[4:].strip()
            text = text.rstrip("`").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]
        result = json.loads(text)
        result["source"] = "alternative"
        return result
    except Exception as e:
        logger.error(f"alt summary error: {e}")
        return {"error": str(e)}


async def summarize_concall(symbol: str, transcript_text: str, date_str: str) -> dict:
    if not EMERGENT_LLM_KEY:
        return {"error": "LLM key missing"}
    if not transcript_text or len(transcript_text) < 500:
        return {"error": "Transcript text too short or unavailable"}

    # truncate to fit context
    trimmed = transcript_text[:25000]

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"concall-{symbol}-{date_str}",
        system_message=CONCALL_SYSTEM,
    ).with_model("gemini", "gemini-3-flash-preview")

    user_msg = UserMessage(
        text=f"Symbol: {symbol}\nConcall date: {date_str}\n\nTranscript:\n{trimmed}\n\nAnalyze and respond as JSON."
    )

    try:
        resp = await chat.send_message(user_msg)
        text = resp if isinstance(resp, str) else str(resp)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text else text
            if text.lower().startswith("json"):
                text = text[4:].strip()
            text = text.rstrip("`").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]
        result = json.loads(text)
        result["source"] = "transcript"
        return result
    except Exception as e:
        logger.error(f"concall summary error: {e}")
        return {"error": str(e)}
