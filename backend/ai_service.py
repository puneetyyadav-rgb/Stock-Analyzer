"""AI verdict generator using Gemini 3.5 Flash."""
import os
import json
import logging
import asyncio
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from dateutil import parser as date_parser
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_gemini_client():
    key = os.environ.get("GEMINI_API_KEY")
    return genai.Client(api_key=key) if key else None

def sync_generate_verdict(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return ""
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    return response.text

DISCLAIMER_TEXT = (
    "AI-generated analysis from public data sources. Not investment advice. "
    "Confidence and target-price figures reflect qualitative AI reasoning, not "
    "statistical or regulatory-grade forecasts. Verify independently before any financial decision."
)


SECTOR_MAP = {
    "Financial Services": "Banking/NBFC",
    "Healthcare": "Pharma",
    "Technology": "IT Services",
    "Communication Services": "Telecom",
    "Consumer Cyclical": "Auto",
    "Basic Materials": "Cement/Metals",
    "Real Estate": "Real Estate",
    "Energy": "Oil & Gas",
    "Industrials": "Conglomerate",
}

SECTOR_FACTOR_HINTS = {
    "Banking/NBFC": [
        "gross/net NPA trend",
        "CASA ratio & deposit growth",
        "credit cost & provisioning",
        "any RBI regulatory action",
    ],
    "Pharma": [
        "USFDA inspection/warning-letter status if mentioned in news/screener",
        "US generics pricing pressure",
        "plant compliance history",
    ],
    "IT Services": [
        "client concentration & attrition",
        "deal pipeline/TCV commentary",
        "US/Europe BFSI demand",
    ],
    "Telecom": [
        "ARPU trend",
        "AGR dues/spectrum payment status",
        "subscriber net adds",
    ],
    "Auto": [
        "monthly dispatch/volume trend",
        "EV transition capex",
        "semiconductor supply commentary",
    ],
    "Cement/Metals": [
        "capacity utilization & realization",
        "input cost trend (coal/limestone/ore)",
        "anti-dumping duty exposure",
    ],
    "Real Estate": [
        "launch pipeline & pre-sales momentum",
        "RERA compliance status",
    ],
    "Oil & Gas": [
        "refining/marketing margin (GRM)",
        "windfall tax exposure",
    ],
    "Conglomerate": [
        "sum-of-parts vs. current valuation (holding-company discount)",
        "subsidiary listing/demerger catalysts",
    ],
}


def map_sector(yahoo_sector: str) -> str:
    return SECTOR_MAP.get(yahoo_sector or "", "Other")


SYSTEM_PROMPT = """You are the Head of Research at an institutional merchant bank. Four desks have submitted independent reads on this stock. A junior analyst would list each desk's verdict and tally agreement vs. disagreement. You are senior — your job is to trace the actual chain of cause and effect connecting them, the way an experienced banker reasons out loud in an investment committee.

THE FOUR DESKS (data for each provided below):
1. FUNDAMENTALS — financials, valuation, governance, macro/sector context
2. NEWS & SENTIMENT — recent headlines, corporate/legal filings, social sentiment
3. TECHNICAL — trend regime, volatility state, candlestick patterns, RSI/MACD
4. QUANTITATIVE — Monte Carlo median forecast, confidence band, sector ranking

STEP 1: THE 9-FACTOR ASSESSMENT
Before writing your synthesis, you MUST systematically assess the stock across these 9 specific categories to establish your base facts.
CRITICAL GUARDRAIL: Base every single 9-factor assessment STRICTLY on the JSON payload provided. If the payload contains no official data for a specific factor (e.g. Global Shocks or Trade Data), you MUST state "No data available" instead of guessing or inventing an assessment.

STEP 2: THE CENTRAL QUESTION (Master Synthesis)
Does the market's current price ALREADY reflect what Fundamentals/News suggest — or is there a lag? Specifically:
- If Fundamentals/News point one direction but Technical/Quantitative haven't moved yet, that gap is usually the most important finding in the whole analysis — not a contradiction to smooth over.
- If Technical/Quantitative already show the move, then Fundamentals/News may just be confirming what's already priced in — meaning the easy money, if any, is already gone.
- Trace WHY: what specific event or data point would explain the lag or the confirmation. Name the mechanism, not just the correlation.
- Only state a causal link between two desks if the data actually supports one. When in doubt, say the link is unclear rather than inventing one.

OTHER GROUNDING RULES:
- Use ONLY the data provided per desk. Do not draw on outside knowledge of the company.
- Never invent a specific price, percentage, or date — qualitative magnitude and named time horizons only.
- No "Buy/Sell" instruction — directional bias and reasoning only. You are diagnosing, not directing.
- Plain text only, no markdown or asterisks.

Output STRICT JSON only. No markdown fences, no commentary outside JSON.
Schema:
{
  "nineFactorAssessment": {
    "macroeconomic": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences. State 'No data available' if missing."},
    "industryAndSector": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences."},
    "companyFinancials": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences."},
    "technicalAndMarket": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences."},
    "newsAndSentiment": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences."},
    "globalShocks": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences. State 'No data available' if missing."},
    "regulatoryPolicy": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences. State 'No data available' if missing."},
    "demandSupplyTrade": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences. State 'No data available' if missing."},
    "managementAndCorporate": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences."}
  },
  "deskSignals": {
    "fundamentals": {"bias": "Bullish" | "Bearish" | "Neutral", "dataSufficient": true | false, "keyFact": "the single most important input from this desk"},
    "news": {"bias": "Bullish" | "Bearish" | "Neutral", "dataSufficient": true | false, "keyFact": "the single most important input from this desk"},
    "technical": {"bias": "Bullish" | "Bearish" | "Neutral", "dataSufficient": true | false, "keyFact": "the single most important input from this desk"},
    "quantitative": {"bias": "Bullish" | "Bearish" | "Neutral", "dataSufficient": true | false, "keyFact": "the single most important input from this desk"}
  },
  "catalystChain": "3-5 sentences tracing the actual cause-and-effect: what happened, why it matters financially, and whether the market (technical/quant) has reacted to it yet. Write this the way an analyst reasons out loud, not as a list.",
  "pricedInAssessment": {
    "status": "Not Yet Priced In" | "Already Priced In" | "Partially Priced In" | "Unclear",
    "reasoning": "Specifically compare what Fundamentals+News justify against what Technical+Quantitative show has already happened in the price."
  },
  "unexplainedTensions": [
    {"desks": ["desk1", "desk2"], "description": "a genuine disagreement with NO clear causal explanation found — only include this if you actually could not connect them"}
  ],
  "thesis": {
    "bias": "Bullish" | "Bearish" | "Neutral",
    "conviction": "High" | "Medium" | "Low",
    "coreArgument": "2-4 sentences — the actual smart conclusion, written in a senior banker's voice, built directly on the catalystChain and pricedInAssessment above",
    "whatWouldChangeThisView": "the specific evidence that would flip this conclusion if it showed up next"
  }
}"""


TECHNICAL_SYSTEM_PROMPT = """You are a Chartered Market Technician (CMT) analyzing Indian stocks.
You specialize in price action, support/resistance, candlestick patterns, and volatility (Monte Carlo) analysis.
Output STRICT JSON only. No markdown fences, no commentary outside JSON.
Schema:
{
  "trend_summary": "2-3 sentences describing the overall technical posture",
  "support_levels": [ {"price": number, "strength": "Strong" | "Weak", "rationale": "string"} ],
  "resistance_levels": [ {"price": number, "strength": "Strong" | "Weak", "rationale": "string"} ],
  "setup_recommendation": "1-2 sentences on how to trade this setup",
  "monte_carlo_insight": "1 sentence interpreting the 80% confidence band and volatility"
}"""


NEWS_SYSTEM_PROMPT = """You are a senior News Desk Financial Analyst.
You process raw financial headlines and corporate announcements, synthesizing them into actionable insights.
CRITICAL INSTRUCTION: You must base your analysis ONLY on the headlines provided. Do not use background knowledge to hallucinate events that are not in the payload.
If there are fewer than 2 recent substantive news items, or they are just routine updates, set "dataSufficient": false.

Output STRICT JSON only. No markdown fences, no commentary outside JSON.
Schema:
{
  "dataSufficient": true | false,
  "headlinesAnalyzed": number,
  "dateRange": {"oldest": "string", "newest": "string"},
  "summary": "2-3 plain-text sentences summarizing the recent news cycle. No markdown.",
  "crux": "1 plain-text sentence stating the single most important takeaway. No markdown.",
  "mainPointers": [
    {"point": "string", "sourceDate": "string"}
  ],
  "directionalBias": {
    "bias": "Bullish" | "Bearish" | "Neutral",
    "magnitude": "High" | "Medium" | "Low",
    "basis": "1 sentence explaining why"
  },
  "scenarios": [
    {"trigger": "If X happens", "expectedImpact": "Y expected impact", "probability": "High" | "Medium" | "Low", "category": "string"}
  ]
}"""


def sync_analyze_options(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return ""
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    return response.text

async def analyze_options(options_data: dict) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return {"error": "GEMINI_API_KEY not configured"}

    prompt = f"""You are an Indian F&O analyst. Analyze this Option Chain data.
Identify immediate Support (highest PE OI), immediate Resistance (highest CE OI), trend (based on PCR and LTP), and draw a clear, concise conclusion (Bullish, Bearish, or Neutral).
Output STRICT JSON. No markdown fences.
Schema:
{{
  "support": number,
  "resistance": number,
  "trend": "Bullish" | "Bearish" | "Neutral",
  "conclusion": "2-3 sentences"
}}

Option Chain Data:
{json.dumps(options_data, default=str)[:15000]}
"""
    try:
        text = await asyncio.to_thread(sync_analyze_options, prompt)
        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"Options analysis error: {e}")
        return {"error": str(e)}


def sync_generate_technical_analysis(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return ""
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    return response.text

async def generate_technical_analysis(tech_data: dict) -> dict:
    client = get_gemini_client()
    if not client:
        return {"error": "GEMINI_API_KEY not configured"}

    prompt = (
        f"{TECHNICAL_SYSTEM_PROMPT}\n\n"
        f"Analyze this technical data and provide the JSON response:\n"
        f"```json\n{json.dumps(tech_data, default=str)}\n```"
    )

    try:
        text = await asyncio.to_thread(sync_generate_technical_analysis, prompt)
        text = text.strip()
        result = json.loads(text)
        result["disclaimer"] = DISCLAIMER_TEXT
        return result
    except Exception as e:
        logger.error(f"AI technical error: {e}")
        return {"error": str(e)}


def sync_generate_news_analysis(prompt: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return ""
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    return response.text

async def generate_news_analysis(news_items: list, stock_context: dict) -> dict:
    client = get_gemini_client()
    if not client:
        return {"error": "GEMINI_API_KEY not configured"}

    prompt = (
        f"{NEWS_SYSTEM_PROMPT}\n\n"
        f"Stock Context:\n{json.dumps(stock_context, default=str)}\n\n"
        f"Analyze these news items and provide the JSON response:\n"
        f"```json\n{json.dumps(news_items, default=str)}\n```"
    )

    try:
        text = await asyncio.to_thread(sync_generate_news_analysis, prompt)
        text = text.strip()
        result = json.loads(text)
        result["disclaimer"] = DISCLAIMER_TEXT
        return result
    except Exception as e:
        logger.error(f"AI news error: {e}")
        return {"error": str(e)}


def _remove_past_catalysts(catalysts: list, analysis_date) -> list:
    """Drop model-produced catalysts that contain an explicit past date."""
    month = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    )
    patterns = (
        rf"\b{month}\s+\d{{1,2}},?\s+\d{{4}}\b",
        rf"\b\d{{1,2}}\s+{month}\s+\d{{4}}\b",
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
    )
    current = []
    for catalyst in catalysts or []:
        text = str(catalyst)
        dated_past = False
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                try:
                    matched_date = match.group(0)
                    if re.match(r"^\d{4}-", matched_date):
                        event_date = datetime.strptime(matched_date, "%Y-%m-%d").date()
                    else:
                        event_date = date_parser.parse(matched_date, dayfirst=True).date()
                    dated_past = dated_past or event_date < analysis_date
                except (TypeError, ValueError, OverflowError):
                    pass
        if not dated_past:
            current.append(catalyst)
    return current


async def generate_verdict(stock_data: dict, macro_data: dict) -> dict:
    client = get_gemini_client()
    if not client:
        return {"error": "GEMINI_API_KEY not configured"}

    overview = stock_data.get("overview", {})
    analysis_as_of = datetime.now(INDIA_TIMEZONE).date()
    news_items = stock_data.get("news", [])
    bucket = map_sector(overview.get("sector"))
    hints = SECTOR_FACTOR_HINTS.get(bucket, [])

    payload = {
        "analysisAsOf": analysis_as_of.isoformat(),
        "desks": {
            "fundamentals": {
                "stock": {
                    "symbol": overview.get("symbol"),
                    "name": overview.get("name"),
                    "sector": overview.get("sector"),
                    "industry": overview.get("industry"),
                    "price": overview.get("price"),
                    "marketCap": overview.get("marketCap"),
                    "peRatio": overview.get("peRatio"),
                    "pbRatio": overview.get("pbRatio"),
                    "roe": overview.get("roe"),
                    "debtToEquity": overview.get("debtToEquity"),
                    "revenueGrowth": overview.get("revenueGrowth"),
                    "earningsGrowth": overview.get("earningsGrowth"),
                },
                "macro_snapshot": macro_data.get("indicators", []),
                "sector_bucket": bucket,
                "financials_quarterly": stock_data.get("financials", {}).get("quarterly", [])[:4],
                "screener_ratios": stock_data.get("screener", {}).get("ratios", {}),
                "screener_pros": stock_data.get("screener", {}).get("pros", [])[:5],
                "screener_cons": stock_data.get("screener", {}).get("cons", [])[:5],
                "promoterPledge": stock_data.get("screener", {}).get("promoterPledge"),
                "holders": stock_data.get("holders", {}).get("majorHoldersBreakdown", {}),
            },
            "news": {
                "recent_news_with_sentiment": [
                    {
                        "title": n.get("title"),
                        "source": n.get("source"),
                        "publishedAt": n.get("publishedAt"),
                        "sentiment": n.get("sentimentLabel"),
                    }
                    for n in news_items[:20]
                ],
                "legal_announcements": stock_data.get("legal", {}).get("items", [])[:5],
                "upcoming_events": stock_data.get("events", {}).get("items", [])[:5],
                "social_sentiment": stock_data.get("social", {}),
                "red_flags": stock_data.get("red_flags", {}).get("items", [])[:5],
            },
            "technical": {
                "technicals": stock_data.get("technicals", {}),
                "regime": stock_data.get("regime", {}),
                "patterns": stock_data.get("patterns", {}),
            },
            "quantitative": {
                "ml_forecast": stock_data.get("ml_forecast", {}),
            }
        }
    }

    sector_instruction = ""
    if hints:
        sector_instruction = (
            f"\n\nFor this stock's sector ({bucket}), specifically address: {hints}, "
            f"using only the financials/screener/news data already provided above. "
            f"If a hint can't be addressed from the given data, say so explicitly rather than "
            f"guessing a number. Populate 'sectorSpecific' array with one object per hint above."
        )

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Analyze this Indian stock as of {analysis_as_of.isoformat()} and provide a verdict. Data:\n"
        f"```json\n{json.dumps(payload, default=str)}\n```{sector_instruction}"
    )

    try:
        text = await asyncio.to_thread(sync_generate_verdict, prompt)
        text = text.strip()
        result = json.loads(text)
        result["analysisAsOf"] = analysis_as_of.isoformat()
        result["disclaimer"] = DISCLAIMER_TEXT
        result["sectorBucket"] = bucket
        return result
    except Exception as e:
        logger.error(f"AI verdict error: {e}")
        return {"error": str(e)}
