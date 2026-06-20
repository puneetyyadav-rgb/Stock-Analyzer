"""AI verdict generator using Gemini 3.5 Flash."""
import os
import json
import logging
import asyncio
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

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
4. Market/Technical factors (FII/DII, charts, RSI, MACD)
5. News & sentiment
6. Global shocks
7. Government/Regulatory policy
8. Demand-supply & trade data
9. Management commentary, big orders, court cases

Provide a structured, terse, data-driven verdict. Use Indian context (Rs/Cr, NSE, SEBI, RBI).
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


async def generate_verdict(stock_data: dict, macro_data: dict) -> dict:
    client = get_gemini_client()
    if not client:
        return {"error": "GEMINI_API_KEY not configured"}

    overview = stock_data.get("overview", {})
    bucket = map_sector(overview.get("sector"))
    hints = SECTOR_FACTOR_HINTS.get(bucket, [])

    payload = {
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
            {"title": n.get("title"), "sentiment": n.get("sentimentLabel")}
            for n in stock_data.get("news", [])[:10]
        ],
        "social_sentiment": stock_data.get("social", {}),
        "legal_announcements": stock_data.get("legal", {}).get("items", [])[:5],
        "upcoming_events": stock_data.get("events", {}).get("items", [])[:5],
        "red_flags": stock_data.get("red_flags", {}).get("items", [])[:5],
        "macro_snapshot": macro_data.get("indicators", []),
        "sector_bucket": bucket,
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
        f"Analyze this Indian stock and provide a verdict. Data:\n"
        f"```json\n{json.dumps(payload, default=str)[:15000]}\n```{sector_instruction}"
    )

    try:
        text = await asyncio.to_thread(sync_generate_verdict, prompt)
        text = text.strip()
        result = json.loads(text)
        result["disclaimer"] = DISCLAIMER_TEXT
        result["sectorBucket"] = bucket
        return result
    except Exception as e:
        logger.error(f"AI verdict error: {e}")
        return {"error": str(e)}
