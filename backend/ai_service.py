"""AI verdict generator using Gemini 3 Flash via Emergent Universal Key."""
import os
import json
import logging
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")


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
  }
}"""


async def generate_verdict(stock_data: dict, macro_data: dict) -> dict:
    if not EMERGENT_LLM_KEY:
        return {"error": "EMERGENT_LLM_KEY not configured"}

    overview = stock_data.get("overview", {})
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
        "recent_news_headlines": [n.get("title") for n in stock_data.get("news", [])[:10]],
        "macro_snapshot": macro_data.get("indicators", []),
    }

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"stock-{overview.get('symbol', 'unknown')}",
        system_message=SYSTEM_PROMPT,
    ).with_model("gemini", "gemini-3-flash-preview")

    user_msg = UserMessage(
        text=f"Analyze this Indian stock and provide a verdict. Data:\n```json\n{json.dumps(payload, default=str)[:8000]}\n```"
    )

    try:
        resp = await chat.send_message(user_msg)
        text = resp if isinstance(resp, str) else str(resp)
        # strip markdown fences if any
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text else text
            if text.lower().startswith("json"):
                text = text[4:].strip()
            text = text.rstrip("`").strip()
        # find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]
        return json.loads(text)
    except Exception as e:
        logger.error(f"AI verdict error: {e}")
        return {"error": str(e)}
