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


SYSTEM_PROMPT = """You are a senior Indian equity research analyst with deep expertise in NSE/BSE markets.
You analyze stocks using a 9-factor framework:
1. Macroeconomic factors (rates, inflation, GDP, currency, commodities, geopolitics)
2. Sector/Industry dynamics
3. Company financials & corporate actions
4. Market/Technical factors (FII/DII, charts, RSI, MACD, Patterns, Regime)
5. News & sentiment
6. Global shocks
7. Government/Regulatory policy
8. Demand-supply & trade data
9. Management commentary, big orders, court cases

Provide a structured, terse, data-driven verdict. Use Indian context (Rs/Cr, NSE, SEBI, RBI).
The supplied analysisAsOf date is authoritative. Base the conclusion on information available as of that date.
Use publication/period dates to distinguish current evidence from historical context. Never describe an event
before analysisAsOf as upcoming or as a catalyst. Do not invent board, earnings, dividend, policy, or macro dates.
Only list a dated catalyst when an explicit future date exists in upcoming_events or recent news; otherwise label
it as conditional and undated. Past events may be cited only in past tense as evidence. When data is missing or
stale, say so instead of filling the gap from memory.
Output STRICT JSON only. No markdown fences, no commentary outside JSON.
Schema:
{
  "verdict": "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL",
  "confidence": 0-100,
  "targetPrice": number or null,
  "timeHorizon": "Short-term (1-3M)" | "Medium-term (3-12M)" | "Long-term (1Y+)",
  "summary": "2-3 sentence executive summary",
  "bullCase": ["3-5 bullets"],
  "bearCase": ["3-5 bullets"],
  "keyRisks": ["3-5 bullets"],
  "catalysts": ["3-5 upcoming catalysts/events"],
  "factorAnalysis": {
    "macro": "1-2 sentences",
    "sector": "1-2 sentences",
    "fundamentals": "1-2 sentences",
    "technicals": "1-2 sentences",
    "sentiment": "1-2 sentences",
    "regulatory": "1-2 sentences",
    "management": "1-2 sentences"
  },
  "sectorSpecific": [{"factor": "...", "assessment": "...", "dataAvailable": true}]
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
You process raw financial headlines and synthesize them into actionable insights.
Output STRICT JSON only. No markdown fences, no commentary outside JSON.
Schema:
{
  "summary": "2-3 sentences summarizing the recent news cycle",
  "crux": "1 bold sentence stating the single most important takeaway",
  "main_pointers": ["bullet 1", "bullet 2", "bullet 3"],
  "buy_sell_target": "Directional bias (Bullish/Bearish/Neutral) and estimated price impact based ONLY on the news",
  "scenarios": [
    {"if_this_happens": "string", "then_expected_impact": "string"}
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
        "dataFreshness": {
            "latestNewsPublishedAt": news_items[0].get("publishedAt") if news_items else None,
            "macroUpdatedAt": macro_data.get("updatedAt"),
            "eventsFilteredAsOf": analysis_as_of.isoformat(),
        },
        "stock": {
            "symbol": overview.get("symbol"),
            "name": overview.get("name"),
            "sector": overview.get("sector"),
            "industry": overview.get("industry"),
            "price": overview.get("price"),
            "changePercent": overview.get("changePercent"),
            "marketCap": overview.get("marketCap"),
            "peRatio": overview.get("peRatio"),
            "pbRatio": overview.get("pbRatio"),
            "roe": overview.get("roe"),
            "debtToEquity": overview.get("debtToEquity"),
            "profitMargin": overview.get("profitMargin"),
            "revenueGrowth": overview.get("revenueGrowth"),
            "earningsGrowth": overview.get("earningsGrowth"),
            "dividendYield": overview.get("dividendYield"),
            "yearHigh": overview.get("yearHigh"),
            "yearLow": overview.get("yearLow"),
            "analystTarget": overview.get("targetMeanPrice"),
            "analystRec": overview.get("recommendation"),
            "summary": (overview.get("longBusinessSummary") or "")[:600],
        },
        "technicals": stock_data.get("technicals", {}),
        "financials_quarterly": stock_data.get("financials", {}).get("quarterly", [])[:4],
        "corporate_actions": stock_data.get("corporate", {}),
        "holders": stock_data.get("holders", {}).get("majorHoldersBreakdown", {}),
        "screener_pros": stock_data.get("screener", {}).get("pros", [])[:5],
        "screener_cons": stock_data.get("screener", {}).get("cons", [])[:5],
        "screener_ratios": stock_data.get("screener", {}).get("ratios", {}),
        "promoterPledge": stock_data.get("screener", {}).get("promoterPledge"),
        "recent_news_with_sentiment": [
            {
                "title": n.get("title"),
                "source": n.get("source"),
                "publishedAt": n.get("publishedAt"),
                "sentiment": n.get("sentimentLabel"),
            }
            for n in news_items[:20]
        ],
        "social_sentiment": stock_data.get("social", {}),
        "legal_announcements": stock_data.get("legal", {}).get("items", [])[:5],
        "upcoming_events": stock_data.get("events", {}).get("items", [])[:5],
        "red_flags": stock_data.get("red_flags", {}).get("items", [])[:5],
        "macro_snapshot": macro_data.get("indicators", []),
        "sector_bucket": bucket,
        "ml_forecast": stock_data.get("ml_forecast", {}),
        "regime": stock_data.get("regime", {}),
        "patterns": stock_data.get("patterns", {}),
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
        result["catalysts"] = _remove_past_catalysts(result.get("catalysts", []), analysis_as_of)
        result["analysisAsOf"] = analysis_as_of.isoformat()
        result["disclaimer"] = DISCLAIMER_TEXT
        result["sectorBucket"] = bucket
        return result
    except Exception as e:
        logger.error(f"AI verdict error: {e}")
        return {"error": str(e)}
