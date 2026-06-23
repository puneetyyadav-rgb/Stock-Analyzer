"""Concall transcript summarization using Gemini 3.5 Flash."""
import os
import json
import logging
import asyncio
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def get_gemini_client():
    key = os.environ.get("GEMINI_API_KEY")
    return genai.Client(api_key=key) if key else None

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


def sync_generate_concall(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return ""
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    return response.text

async def summarize_alternative(symbol: str, date_str: str, context: dict) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return {"error": "GEMINI_API_KEY missing"}
    
    prompt = f"{ALTERNATIVE_SYSTEM}\n\nSymbol: {symbol}\nApprox quarter: {date_str}\n\nContext:\n{json.dumps(context, default=str)[:8000]}"
    try:
        text = await asyncio.to_thread(sync_generate_concall, prompt)
        text = text.strip()
        result = json.loads(text)
        result["source"] = "alternative"
        return result
    except Exception as e:
        logger.error(f"Alt concall error: {e}")
        return {"error": str(e)}


async def summarize_concall(symbol: str, transcript_text: str, date_str: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return {"error": "GEMINI_API_KEY missing"}
    if not transcript_text or len(transcript_text) < 500:
        return {"error": "Transcript text too short or unavailable"}

    trimmed = transcript_text[:25000]

    prompt = f"{CONCALL_SYSTEM}\n\nSymbol: {symbol}\nConcall date: {date_str}\n\nTranscript:\n{trimmed}\n\nAnalyze and respond as JSON."

    try:
        text = await asyncio.to_thread(sync_generate_concall, prompt)
        text = text.strip()
        result = json.loads(text)
        result["source"] = "transcript"
        return result
    except Exception as e:
        logger.error(f"concall summary error: {e}")
        return {"error": str(e)}
