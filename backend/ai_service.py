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

def _has_any_ai_key() -> bool:
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY"))

import time

def _call_groq_fallback(prompt: str) -> str:
    _has_any_ai_key()
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        logger.error("Groq fallback triggered, but GROQ_API_KEY is not set.")
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key
        )
        models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b", "mixtral-8x7b-32768"]
        for model in models:
            try:
                logger.info(f"Attempting Groq fallback using model: {model}")
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                    )
                except Exception as json_mode_err:
                    logger.warning(f"Failed with JSON mode on model {model}: {json_mode_err}. Retrying without JSON mode constraint...")
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,
                    )
                val = response.choices[0].message.content
                if val:
                    logger.info(f"Groq fallback succeeded with model: {model}")
                    return val
            except Exception as ex:
                logger.warning(f"Groq model {model} failed: {ex}. Trying next fallback...")
                continue
    except Exception as e:
        logger.error(f"Failed to initialize or call Groq client: {e}")
    return ""

def _call_gemini_with_retry(client, prompt: str, retries=3, backoff=2) -> str:
    has_groq = bool(os.environ.get("GROQ_API_KEY"))
    for i in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            return response.text
        except Exception as e:
            if has_groq:
                logger.warning(f"Gemini API error ({e}). Fast-switching directly to Groq fallback...")
                raise e
            if "503" in str(e) or "429" in str(e):
                if i < retries - 1:
                    logger.warning(f"Gemini API rate limit/503 hit. Retrying in {backoff} seconds... (Attempt {i+1}/{retries})")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
            raise e
    return ""

def _execute_ai_call_with_fallback(prompt: str, use_pdf_key: bool = False) -> str:
    _has_any_ai_key()

    if use_pdf_key:
        key = os.environ.get("GEMINI_API_KEY_PDF") or os.environ.get("GEMINI_API_KEY")
    else:
        key = os.environ.get("GEMINI_API_KEY")
        
    if not key:
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            logger.info("Gemini API key not found. Routing directly to Groq fallback.")
            return _call_groq_fallback(prompt)
        return ""
        
    client = genai.Client(api_key=key, http_options={'timeout': 15000})
    try:
        return _call_gemini_with_retry(client, prompt)
    except Exception as e:
        logger.warning(f"Gemini API failed: {e}. Trying Groq fallback...")
        groq_val = _call_groq_fallback(prompt)
        if groq_val:
            return groq_val
        raise e

def sync_generate_verdict(prompt: str, use_pdf_key: bool = False) -> str:
    return _execute_ai_call_with_fallback(prompt, use_pdf_key)

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
1. FUNDAMENTALS — financials, valuation, governance, promoter pledging, macro/sector context
2. NEWS & SENTIMENT — official headlines, legal filings vs retail Twitter/FinTwit sentiment
3. TECHNICAL — trend regime, relative strength vs Nifty 50, candlestick patterns, RSI/MACD
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
    "newsAndSentiment": {"bias": "Bullish" | "Bearish" | "Neutral", "text": "1-2 sentences explicitly comparing Official News vs Retail Twitter chatter."},
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


TECHNICAL_SYSTEM_PROMPT = """You are an elite Chartered Market Technician (CMT) and Institutional Flow Analyst specializing in Indian equity markets (NSE/BSE).
You specialize in multi-timeframe price action, dynamic support/resistance zones, candlestick morphology, Relative Strength (RS) versus Nifty 50, and NSE Bhavcopy Delivery Volume analysis.
CRITICAL INDIAN MARKET RULE: Pay immense attention to the Delivery Percentage payload. In Indian equity markets, high delivery volume (>50-60%) accompanied by price advances signifies strong institutional accumulation (bullish conviction), whereas price advances on low delivery (<30%) indicate speculative intraday froth.

Output STRICT JSON only. No markdown fences, no commentary outside JSON.
Schema:
{
  "trend_summary": "2-3 comprehensive sentences evaluating multi-timeframe technical posture, moving average alignment (SMA 50/200), and Relative Strength vs Nifty 50",
  "volume_and_delivery_insight": "2-3 analytical sentences explicitly evaluating the NSE Bhavcopy delivery percentage and traded volume. State clearly whether volume action confirms bullish institutional accumulation or speculative distribution",
  "support_levels": [ {"price": number, "strength": "Strong" | "Weak", "rationale": "Detailed technical rationale"} ],
  "resistance_levels": [ {"price": number, "strength": "Strong" | "Weak", "rationale": "Detailed technical rationale"} ],
  "setup_recommendation": "2 precise, actionable sentences on trade execution, optimal entry zone, and strict stop-loss placement",
  "monte_carlo_insight": "1-2 sentences interpreting the Monte Carlo 80% confidence distribution and implied volatility risk"
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
    return _execute_ai_call_with_fallback(prompt, False)

async def analyze_options(options_data: dict) -> dict:
    if not _has_any_ai_key():
        return {"error": "Neither GEMINI_API_KEY nor GROQ_API_KEY is configured"}

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
    return _execute_ai_call_with_fallback(prompt, False)

async def generate_technical_analysis(tech_data: dict) -> dict:
    if not _has_any_ai_key():
        return {"error": "Neither GEMINI_API_KEY nor GROQ_API_KEY is configured"}

    prompt = (
        f"{TECHNICAL_SYSTEM_PROMPT}\n\n"
        f"Analyze this technical data and provide the JSON response:\n"
        f"```json\n{json.dumps(tech_data, default=str)}\n```"
    )

    try:
        text = await asyncio.to_thread(sync_generate_technical_analysis, prompt)
        text = text.strip()
        result = json.loads(text)
        if isinstance(result, list):
            result = result[0] if result else {}
        result["disclaimer"] = DISCLAIMER_TEXT
        return result
    except Exception as e:
        logger.error(f"AI technical error: {e}")
        return {"error": str(e)}


def sync_generate_news_analysis(prompt: str) -> str:
    return _execute_ai_call_with_fallback(prompt, False)

async def generate_news_analysis(news_items: list, stock_context: dict) -> dict:
    if not _has_any_ai_key():
        return {"error": "Neither GEMINI_API_KEY nor GROQ_API_KEY is configured"}

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
        if isinstance(result, list):
            result = result[0] if result else {}
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
    if not _has_any_ai_key():
        return {"error": "Neither GEMINI_API_KEY nor GROQ_API_KEY is configured"}

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
                "macro_snapshot": macro_data.get("indicators", [])[:4],
                "sector_bucket": bucket,
                "financials_quarterly": stock_data.get("financials", {}).get("quarterly", [])[:2],
                "screener_ratios": stock_data.get("screener", {}).get("ratios", {}),
                "screener_pros": stock_data.get("screener", {}).get("pros", [])[:4],
                "screener_cons": stock_data.get("screener", {}).get("cons", [])[:4],
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
                    for n in news_items[:8]
                ],
                "legal_announcements": stock_data.get("legal", {}).get("items", [])[:3],
                "upcoming_events": stock_data.get("events", {}).get("items", [])[:3],
                "social_sentiment": stock_data.get("social", {}),
                "red_flags": stock_data.get("red_flags", {}).get("items", [])[:3],
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
        if isinstance(result, list):
            result = result[0] if result else {}
        result["analysisAsOf"] = analysis_as_of.isoformat()
        result["disclaimer"] = DISCLAIMER_TEXT
        result["sectorBucket"] = bucket
        return result
    except Exception as e:
        logger.error(f"AI verdict error: {e}")
        return {"error": str(e)}

async def generate_external_intelligence_verdict(aftermarkets: dict, tickertape: dict) -> dict:
    if not _has_any_ai_key():
        return {"error": "Neither GEMINI_API_KEY nor GROQ_API_KEY is configured"}

    prompt = f"""You are a specialized financial AI extracting a 'Raw Conclusion' from external data sources.
Analyze the following scraped data from Aftermarkets and Tickertape, and provide a synthesized raw conclusion.
Output STRICT JSON only. No markdown fences.
Schema:
{{
  "verdict": "Bullish" | "Bearish" | "Neutral",
  "summary": "2-3 sentences synthesizing the raw external data conclusion.",
  "key_drivers": ["string", "string"],
  "risk_factors": ["string", "string"]
}}

Data:
Aftermarkets: {json.dumps(aftermarkets, default=str)}
Tickertape: {json.dumps(tickertape, default=str)}
"""

    try:
        text = await asyncio.to_thread(sync_generate_verdict, prompt)
        text = text.strip()
        result = json.loads(text)
        return result
    except Exception as e:
        logger.error(f"AI external verdict error: {e}")
        return {"error": str(e)}


async def extract_ratios_from_source(text: str) -> dict:
    """Intelligently parse source material text to extract ratios and competitor comparisons in ONE call to save quota."""
    import time
    
    # Take up to 40,000 characters (roughly 10,000 tokens) to save tokens and ensure it fits well
    truncated_text = text[:40000]

    merged_result = {
        "company_ratios": [],
        "competitor_comparison": {"metrics": [], "companies": []},
        "other_fields": {}
    }

    prompt = f"""You are a specialized financial AI extracting ratios and peer comparison data from raw PDF text.
Extract the key financial ratios of the primary company. Also extract any peer comparison grid/table available in the text.
If you find extra notable fields (e.g., target price, estimates), include them in 'other_fields'.
Output STRICT JSON only. Do not use markdown blocks like ```json.
Schema:
{{
  "company_ratios": [
     {{"name": "string", "value": "string/number", "unit": "string/null"}}
  ],
  "competitor_comparison": {{
     "metrics": ["string", "string"],
     "companies": [
        {{
           "name": "string",
           "ratios": {{"metric_name": "value"}}
        }}
     ]
  }},
  "other_fields": {{"key": "value"}}
}}

Raw text:
{truncated_text}
"""
    max_retries = 3
    chunk_result = None
    for attempt in range(max_retries):
        try:
            res = await asyncio.to_thread(sync_generate_verdict, prompt, True)
            res = res.strip()
            if res.startswith("```json"):
                res = res[7:]
            if res.startswith("```"):
                res = res[3:]
            if res.endswith("```"):
                res = res[:-3]
            res = res.strip()
            chunk_result = json.loads(res)
            break
        except Exception as e:
            if attempt < max_retries - 1 and ("503" in str(e) or "429" in str(e) or "quota" in str(e).lower()):
                delay = 3 ** (attempt + 1)
                logger.warning(f"Hit rate limit (429/503), retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Parsing error: {e}")
                break

    if chunk_result:
        merged_result = chunk_result

    # Ensure keys exist
    if "company_ratios" not in merged_result:
        merged_result["company_ratios"] = []
    if "competitor_comparison" not in merged_result:
        merged_result["competitor_comparison"] = {"metrics": [], "companies": []}
    if "other_fields" not in merged_result:
        merged_result["other_fields"] = {}

    # If absolutely nothing was extracted, return an error
    if not merged_result["company_ratios"] and not merged_result.get("competitor_comparison", {}).get("companies") and not merged_result["other_fields"]:
        return {"error": "Failed to extract data. The PDF may not contain readable financial text, or the AI API limit was completely exhausted."}

    return merged_result

RATIO_ANALYZER_PROMPT = """You are a senior equity research analyst specializing in ratio analysis. You read financial ratios the way an experienced analyst does — never one ratio in isolation, always in combination, and always relative to the sector/peers, never against fixed universal thresholds (a P/E of 25 is expensive for a bank, normal for IT, and cheap for a hot growth name — context decides, not the raw number).

DATA YOU WILL RECEIVE:
- This stock's own ratios (valuation, profitability, leverage, growth — whichever are available; some may be missing, that's expected)
- Peer/sector average ratios, if provided
- A list of individual peer companies with their own ratios, if provided
- Historical values for this stock's own ratios (e.g. last few years), if provided

GROUNDING RULES — do not violate these:
- Use ONLY the ratios and peer data actually provided. Do not estimate or recall a ratio you weren't given — mark it "N/A" in dataCompleteness instead.
- Never compare a ratio against a fixed universal "good/bad" number. Always compare against the provided sector/peer data. If no peer data is provided for a given ratio, say so explicitly rather than falling back to a generic rule of thumb.
- Read ratios in combination, not isolation — this is the entire point of your job. A single ratio stated alone is not analysis.
- Plain text only — no markdown, no asterisks.
- No "Buy/Sell" instruction. Output a view and reasoning, not a directive.
- Qualitative confidence only (High/Medium/Low) — never invent a specific target price or exact percentage upside/downside.

HOW TO READ RATIOS IN COMBINATION (apply these checks wherever the underlying data is available; skip silently if the needed ratios for a given check are missing):
1. RETURNS vs. LEVERAGE: A high ROE/ROCE alongside high debt-to-equity often means returns are leverage-amplified, not purely operational quality. Flag this combination explicitly — don't credit "strong ROE" without checking what's funding it.
2. VALUATION vs. GROWTH: A high P/E is not automatically "expensive" if revenue/earnings growth is also high relative to peers (implied PEG logic) — but a high P/E alongside flat or declining growth, especially when peers trade cheaper for similar growth, is a real overvaluation flag.
3. MARGIN TREND vs. GROWTH TREND: Revenue growing while margins are flat or improving suggests genuine operating leverage; revenue growing while margins are shrinking suggests growth bought at a cost (discounting, rising input costs, weak pricing power) — flag which pattern is present if historical data allows it.
4. SOLVENCY CHECK: Low or declining interest coverage alongside rising debt-to-equity is a combination worth flagging on its own regardless of how other ratios look — this is a risk check, not a valuation call.
5. BOOK VALUE vs. EARNINGS VALUATION DIVERGENCE: If P/E and P/B send different signals (e.g. cheap on earnings, expensive on book, or vice versa), say so explicitly rather than picking one — this divergence itself is often informative (e.g. asset-heavy vs. asset-light business model differences).

Output STRICT JSON only. No markdown fences, no commentary outside JSON.
Schema:
{
  "dataCompleteness": {"ratiosAvailable": ["..."], "ratiosMissing": ["..."], "peerDataAvailable": true | false},
  "categoryReads": {
    "valuation": {"verdict": "Cheap" | "Fair" | "Expensive" | "Unclear - insufficient peer data", "vsSectorReasoning": "explicitly reference the peer/sector numbers used"},
    "profitability": {"verdict": "Strong" | "Average" | "Weak" | "Unclear - insufficient peer data", "vsSectorReasoning": "..."},
    "leverage": {"verdict": "Conservative" | "Moderate" | "Aggressive" | "Unclear - insufficient peer data", "vsSectorReasoning": "..."},
    "growth": {"verdict": "Above peers" | "In line" | "Below peers" | "Unclear - insufficient peer data", "vsSectorReasoning": "..."}
  },
  "crossRatioInsights": [
    {"ratiosInvolved": ["...", "..."], "pattern": "which of the 5 combination checks above this matches, or 'Other'", "interpretation": "plain-language explanation of what this combination actually means for the business"}
  ],
  "redFlagCombos": [
    {"ratiosInvolved": ["...", "..."], "severity": "High" | "Medium" | "Low", "explanation": "..."}
  ],
  "peerStanding": {
    "position": "Above peer average" | "In line with peers" | "Below peer average" | "Insufficient peer data",
    "strongestRelativeMetric": "the one ratio where this stock most clearly beats peers, or N/A",
    "weakestRelativeMetric": "the one ratio where this stock most clearly lags peers, or N/A"
  },
  "synthesis": {
    "view": "Bullish" | "Bearish" | "Neutral" | "Mixed",
    "conviction": "High" | "Medium" | "Low",
    "narrative": "3-5 sentences written the way an analyst actually talks — connect the categories to each other explicitly (e.g. 'cheap on earnings but that's likely because growth has slowed relative to peers, not a clean bargain'), do not just restate the category verdicts as a list",
    "watchItem": "the one ratio or combination most likely to change this view if it shifts next quarter"
  }
}"""

async def generate_ratio_analysis(stock_data: dict) -> dict:
    if not _has_any_ai_key():
        return {"error": "Neither GEMINI_API_KEY nor GROQ_API_KEY is configured"}

    prompt = (
        f"{RATIO_ANALYZER_PROMPT}\n\n"
        f"Analyze this ratio data and provide the JSON response:\n"
        f"```json\n{json.dumps(stock_data, default=str)}\n```"
    )

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = await asyncio.to_thread(sync_generate_verdict, prompt)
            res = res.strip()
            result = json.loads(res)
            result["disclaimer"] = DISCLAIMER_TEXT
            return result
        except Exception as e:
            if attempt < max_retries - 1 and "503" in str(e):
                logger.warning(f"AI ratio analysis 503 error, retrying in {2**(attempt+1)} seconds...")
                await asyncio.sleep(2 ** (attempt + 1))
            else:
                logger.error(f"AI ratio analysis error: {e}")
                return {"error": str(e)}


SOURCE_QA_SYSTEM = """You are a strict, source-locked financial Q&A assistant.
ABSOLUTE RULES — VIOLATION IS UNACCEPTABLE:
1. You may ONLY use the data payload provided below to answer the user's question. You have ZERO access to outside knowledge, training data, or the internet.
2. If the answer is not explicitly present in the provided source data, you MUST respond EXACTLY: "The provided source data does not contain information about this."
3. Do NOT speculate, infer from general knowledge, or hallucinate facts that are not in the payload.
4. Keep answers concise: 2-5 sentences maximum. Use specific numbers, dates, and names from the payload.
5. If the user asks about a metric or event, quote the exact value from the source data.

Source Section: {source_name}
Source Data Payload:
{source_json}
"""


def sync_ask_source(prompt: str) -> str:
    return _execute_ai_call_with_fallback(prompt, False)


async def ask_source_qa(source_name: str, source_data: dict, question: str) -> dict:
    if not _has_any_ai_key():
        return {"error": "Neither GEMINI_API_KEY nor GROQ_API_KEY is configured"}

    source_json = json.dumps(source_data, default=str)[:12000]
    prompt = SOURCE_QA_SYSTEM.format(source_name=source_name, source_json=source_json)
    prompt += f"\n\nUser Question: {question}\n\nAnswer (strict source-only):"

    try:
        text = await asyncio.to_thread(sync_ask_source, prompt)
        text = text.strip()
        return {"answer": text, "sourceName": source_name}
    except Exception as e:
        logger.error(f"Source QA error: {e}")
        return {"error": str(e)}
