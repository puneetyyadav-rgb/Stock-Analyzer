import yfinance as yf
import pandas as pd
import requests
import logging
import asyncio
import json
from datetime import datetime, timezone
import ai_service as ai
from tvDatafeed import TvDatafeed, Interval

logger = logging.getLogger(__name__)

# ─── GLOBAL INDICES UNIVERSE ─────────────────────────────────────────────────
# These are strictly "overnight" markets that close before 9:15 AM IST
YF_TICKERS = {
    # US Markets
    "S&P 500":       {"symbol": "^GSPC",    "category": "us"},
    "Nasdaq":        {"symbol": "^IXIC",    "category": "us"},
    "Dow Jones":     {"symbol": "^DJI",     "category": "us"},
    "Russell 2000":  {"symbol": "^RUT",     "category": "us"},
    # Asia (ex-India — domestic sectoral fetched separately from MACRO_UNIVERSE)
    "Nikkei 225":    {"symbol": "^N225",    "category": "asia"},
    "Hang Seng":     {"symbol": "^HSI",     "category": "asia"},
    "KOSPI":         {"symbol": "^KS11",    "category": "asia"},
    "TWSE (Taiwan)": {"symbol": "^TWII",    "category": "asia"},
    "STI (Singapore)":{"symbol": "^STI",   "category": "asia"},
    # Europe (closes ~1h before Indian open — real overnight signal)
    "DAX":           {"symbol": "^GDAXI",   "category": "europe"},
    "CAC 40":        {"symbol": "^FCHI",    "category": "europe"},
    "FTSE 100":      {"symbol": "^FTSE",    "category": "europe"},
    # Commodities
    "Brent Crude":   {"symbol": "BZ=F",     "category": "commodity"},
    "WTI Crude":     {"symbol": "CL=F",     "category": "commodity"},
    "Gold":          {"symbol": "GC=F",     "category": "commodity"},
    "Silver":        {"symbol": "SI=F",     "category": "commodity"},
    "Copper":        {"symbol": "HG=F",     "category": "commodity"},
    "Natural Gas":   {"symbol": "NG=F",     "category": "commodity"},
    # FX — correctly quoted (USD per foreign unit or standard convention)
    "US Dollar Index":{"symbol": "DX-Y.NYB","category": "fx"},
    "USD/INR":       {"symbol": "USDINR=X", "category": "fx"},
    "EUR/USD":       {"symbol": "EURUSD=X", "category": "fx"},
    "GBP/USD":       {"symbol": "GBPUSD=X", "category": "fx"},
    "USD/JPY":       {"symbol": "USDJPY=X", "category": "fx"},  # standard: USD per JPY
    "USD/CNY":       {"symbol": "USDCNY=X", "category": "fx"},  # standard: USD per CNY
    # Yield Curve — 5Y/10Y/30Y (Yahoo). Real 2Y fetched from FRED separately.
    "US 10-Year":    {"symbol": "^TNX",     "category": "rates"},
    "US 5-Year":     {"symbol": "^FVX",     "category": "rates"},
    "US 30-Year":    {"symbol": "^TYX",     "category": "rates"},
    "US 3M T-Bill":  {"symbol": "^IRX",     "category": "rates"},
    # Volatility / Risk
    "India VIX":     {"symbol": "^INDIAVIX","category": "vol"},
    "US VIX":        {"symbol": "^VIX",     "category": "vol"},
    "Bitcoin":       {"symbol": "BTC-USD",  "category": "crypto"},
    "Ethereum":      {"symbol": "ETH-USD",  "category": "crypto"},
}

# Indian Sectoral — day-session only, reused from MACRO_UNIVERSE in global_macro_monte_carlo
INDIA_SECTORAL_SYMBOLS = {
    "Nifty 50":       "^NSEI",
    "Bank Nifty":     "^NSEBANK",
    "Nifty IT":       "^CNXIT",
    "Nifty Pharma":   "^CNXPHARMA",
    "Nifty FMCG":     "^CNXFMCG",
    "Nifty Metal":    "^CNXMETAL",
    "Nifty Auto":     "^CNXAUTO",
}


def fetch_fred_2y_yield() -> float | None:
    """Fetches the real US 2-Year Treasury yield from FRED (free, no API key)."""
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            lines = r.text.strip().split("\n")
            # Last row is the latest data point: "YYYY-MM-DD,value"
            for line in reversed(lines[1:]):
                parts = line.split(",")
                if len(parts) == 2 and parts[1].strip() not in ("", "."):
                    return float(parts[1].strip())
    except Exception as e:
        logger.warning(f"Failed to fetch FRED DGS2 (2Y yield): {e}")
    return None


def fetch_gift_nifty() -> dict | None:
    """
    Fetches GIFT Nifty via TradingView datafeed.
    MUST use exchange='NSEIX' — NOT 'NSE'.
    NSE:NIFTY1! is the domestic futures contract (day-session only).
    NSEIX:NIFTY1! is the GIFT City international contract (trades overnight).
    """
    try:
        tv = TvDatafeed()
        df = tv.get_hist('NIFTY1!', 'NSEIX', interval=Interval.in_daily, n_bars=2)
        if df is not None and not df.empty and len(df) >= 1:
            latest_close = float(df['close'].iloc[-1])
            change_pct = 0.0
            if len(df) > 1:
                prev_close = float(df['close'].iloc[-2])
                change_pct = ((latest_close - prev_close) / prev_close) * 100
            return {
                "name": "GIFT Nifty",
                "symbol": "NSEIX:NIFTY1!",
                "price": round(latest_close, 2),
                "change_pct": round(change_pct, 2),
                "category": "gift_nifty"
            }
    except Exception as e:
        logger.warning(f"Failed to fetch GIFT Nifty from NSEIX: {e}")
    return None


def fetch_india_sectoral() -> list:
    """
    Fetches Indian sectoral indices for context (yesterday's domestic close).
    These are NOT overnight data — they are labeled clearly as such.
    Reuses the same tickers as MACRO_UNIVERSE in global_macro_monte_carlo.py.
    """
    results = []
    try:
        tickers = list(INDIA_SECTORAL_SYMBOLS.values())
        data = yf.download(tickers, period="5d", group_by="ticker", progress=False)
        for name, symbol in INDIA_SECTORAL_SYMBOLS.items():
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    df = data[symbol].dropna()
                else:
                    df = data.dropna()
                if len(df) >= 2:
                    latest = float(df['Close'].iloc[-1])
                    prev = float(df['Close'].iloc[-2])
                    chg = ((latest - prev) / prev) * 100
                    results.append({
                        "name": name,
                        "symbol": symbol,
                        "price": round(latest, 2),
                        "change_pct": round(chg, 2),
                        "category": "india_sectoral",
                        "note": "Yesterday's domestic close (not overnight data)"
                    })
            except Exception as e:
                logger.debug(f"Skipping Indian sectoral {name}: {e}")
    except Exception as e:
        logger.error(f"India sectoral batch fetch failed: {e}")
    return results


def fetch_overnight_data() -> dict:
    """
    Fetches the full global macro universe:
    - 32 international tickers via yfinance (US, Asia, Europe, Commodities, FX, Rates, Vol)
    - Real 2Y yield from FRED
    - GIFT Nifty from TradingView NSEIX
    - Indian sectoral (yesterday's close, for context only)
    """
    results = []
    tickers_list = [v["symbol"] for v in YF_TICKERS.values()]

    try:
        data = yf.download(tickers_list, period="5d", group_by="ticker", progress=False)
    except Exception as e:
        logger.error(f"yfinance batch download failed: {e}")
        data = None

    for name, meta in YF_TICKERS.items():
        symbol = meta["symbol"]
        category = meta["category"]
        try:
            if data is not None:
                if isinstance(data.columns, pd.MultiIndex):
                    df = data[symbol].dropna()
                else:
                    df = data.dropna()

                if len(df) >= 2:
                    latest = float(df['Close'].iloc[-1])
                    prev = float(df['Close'].iloc[-2])
                    chg = ((latest - prev) / prev) * 100

                    # Safety: ^TNX sometimes returns x10 scaled values
                    if symbol == "^TNX" and latest > 20.0:
                        latest = latest / 10.0
                    # Same safety for other CBOE rate tickers
                    if symbol in ("^FVX", "^TYX", "^IRX") and latest > 20.0:
                        latest = latest / 10.0

                    decimal_precision = 4 if category in ("rates", "vol", "fx") else 2
                    results.append({
                        "name": name,
                        "symbol": symbol,
                        "price": round(latest, decimal_precision),
                        "change_pct": round(chg, 2),
                        "category": category
                    })
        except Exception as e:
            logger.debug(f"Skipped {name} ({symbol}): {e}")

    # Fetch real 2Y yield from FRED
    us_2y = fetch_fred_2y_yield()

    # Fetch GIFT Nifty (NSEIX — not NSE)
    gift_nifty = fetch_gift_nifty()

    # Fetch Indian sectoral (labeled as yesterday's close)
    india_sectoral = fetch_india_sectoral()

    # Compute yield curve spreads if we have the data
    yield_curve = {}
    try:
        r10 = next((x["price"] for x in results if x["symbol"] == "^TNX"), None)
        r5  = next((x["price"] for x in results if x["symbol"] == "^FVX"), None)
        r30 = next((x["price"] for x in results if x["symbol"] == "^TYX"), None)
        if r10 and us_2y:
            yield_curve["spread_10y_2y"] = round(r10 - us_2y, 3)
            yield_curve["inverted"] = (r10 - us_2y) < 0
        if r10 and r5:
            yield_curve["spread_10y_5y"] = round(r10 - r5, 3)
        if r30 and r10:
            yield_curve["spread_30y_10y"] = round(r30 - r10, 3)
        yield_curve["us_2y_fred"] = us_2y
        yield_curve["us_5y"] = r5
        yield_curve["us_10y"] = r10
        yield_curve["us_30y"] = r30
    except Exception as e:
        logger.debug(f"Yield curve computation failed: {e}")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": results,
        "gift_nifty": gift_nifty,
        "india_sectoral": india_sectoral,
        "yield_curve": yield_curve,
    }


# ─── AI PROMPT ────────────────────────────────────────────────────────────────

OVERNIGHT_PROMPT = """You are a Chief Investment Officer (CIO) at a top Mumbai hedge fund.
It is pre-market (8:30 AM IST). Analyze the complete overnight global market data below and produce a structured Morning Briefing.

OVERNIGHT GLOBAL DATA:
{data_dump}

YIELD CURVE:
{yield_curve_dump}

LATEST FII/DII INSTITUTIONAL FLOW (actual data from NSE):
{fii_dump}

INSTRUCTIONS:
1. market_bias: exactly "BULLISH", "BEARISH", or "NEUTRAL"
2. Provide exactly 3 sector_tailwinds and 3 sector_headwinds for the Indian market
3. Provide exactly 3 trade_ideas, each with entry_trigger, stop_concept, and target_concept
4. fii_interpretation: interpret the ACTUAL FII net flow numbers provided above — do NOT guess or infer from DXY
5. commodity_alert and yield_curve_signal: null if not significant
6. Output STRICT JSON ONLY. No markdown code fences. No prose outside the JSON object.

JSON SCHEMA:
{{
  "market_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "bias_confidence": <0-100>,
  "bias_rationale": "<2-3 sentences — cite specific data points>",
  "nifty_expected_gap": "<e.g. '+0.4% to +0.6%' or 'Flat to -0.2%'>",
  "global_cues_summary": "<What happened in US and Asia overnight, 2 sentences>",
  "sector_tailwinds": [
    {{"sector": "<name>", "reason": "<specific data-backed reason>"}},
    {{"sector": "<name>", "reason": "<specific data-backed reason>"}},
    {{"sector": "<name>", "reason": "<specific data-backed reason>"}}
  ],
  "sector_headwinds": [
    {{"sector": "<name>", "reason": "<specific data-backed reason>"}},
    {{"sector": "<name>", "reason": "<specific data-backed reason>"}},
    {{"sector": "<name>", "reason": "<specific data-backed reason>"}}
  ],
  "trade_ideas": [
    {{
      "direction": "LONG" | "SHORT" | "AVOID",
      "sector": "<sector>",
      "rationale": "<why based on overnight data>",
      "entry_trigger": "<what to watch for on open>",
      "stop_concept": "<what would invalidate this thesis>",
      "target_concept": "<where this trade targets>"
    }}
  ],
  "fii_interpretation": "<Interpret the actual FII net flow number: buyer/seller, magnitude, trend>",
  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "commodity_alert": "<crude/gold/metals note if significant, else null>",
  "yield_curve_signal": "<yield curve interpretation if significant, else null>",
  "intraday_watch": ["<sector/asset to watch>", "<sector/asset to watch>"]
}}
"""


async def generate_morning_briefing(force_refresh: bool = False, fii_data: dict = None) -> dict:
    """Fetches raw data and synthesizes a morning briefing via Groq AI."""

    # 1. Fetch Raw Data
    raw_payload = await asyncio.to_thread(fetch_overnight_data)

    # 2. Build data dump string for AI prompt
    data_lines = []
    if raw_payload.get("gift_nifty"):
        gn = raw_payload["gift_nifty"]
        data_lines.append(f"- GIFT Nifty (NSEIX): {gn['price']} ({gn['change_pct']:+.2f}%)")

    # Group by category for readable prompt
    by_cat = {}
    for item in raw_payload.get("data", []):
        cat = item.get("category", "other")
        by_cat.setdefault(cat, []).append(item)

    cat_labels = {"us": "US Markets", "asia": "Asian Markets", "europe": "European Markets",
                  "commodity": "Commodities", "fx": "FX", "rates": "US Rates", "vol": "Volatility", "crypto": "Crypto"}
    for cat, label in cat_labels.items():
        if cat in by_cat:
            data_lines.append(f"\n{label}:")
            for item in by_cat[cat]:
                data_lines.append(f"  - {item['name']}: {item['price']} ({item['change_pct']:+.2f}%)")

    data_dump = "\n".join(data_lines)

    # 3. Build yield curve dump
    yc = raw_payload.get("yield_curve", {})
    yc_lines = []
    if yc.get("us_2y_fred"):
        yc_lines.append(f"- US 2Y (FRED): {yc['us_2y_fred']:.3f}%")
    if yc.get("us_5y"):
        yc_lines.append(f"- US 5Y: {yc['us_5y']:.3f}%")
    if yc.get("us_10y"):
        yc_lines.append(f"- US 10Y: {yc['us_10y']:.3f}%")
    if yc.get("us_30y"):
        yc_lines.append(f"- US 30Y: {yc['us_30y']:.3f}%")
    if "spread_10y_2y" in yc:
        inv = " ← INVERTED CURVE" if yc.get("inverted") else ""
        yc_lines.append(f"- 10Y–2Y Spread: {yc['spread_10y_2y']:+.3f}%{inv}")
    if "spread_10y_5y" in yc:
        yc_lines.append(f"- 10Y–5Y Spread: {yc['spread_10y_5y']:+.3f}%")
    yield_curve_dump = "\n".join(yc_lines) if yc_lines else "Yield curve data unavailable."

    # 4. Build FII dump — feed REAL numbers, not DXY vibes
    fii_lines = []
    if fii_data:
        fii_lines.append(f"- FII Cash Net (latest session): ₹{fii_data.get('fii_cash_net_cr', 0):+.1f} Cr")
        fii_lines.append(f"- DII Cash Net (latest session): ₹{fii_data.get('dii_cash_net_cr', 0):+.1f} Cr")
        fii_lines.append(f"- FII Derivatives Imbalance: ₹{fii_data.get('fii_derivatives_imbalance_cr', 0):+.1f} Cr")
        fii_lines.append(f"- FII 5-Day Cash Momentum: ₹{fii_data.get('fii_5d_cash_momentum_cr', 0):+.1f} Cr")
        fii_lines.append(f"- Regime Signal: {fii_data.get('regime_signal', 'N/A')}")
    else:
        fii_lines.append("FII/DII flow data not yet available for this session.")
    fii_dump = "\n".join(fii_lines)

    prompt = OVERNIGHT_PROMPT.format(
        data_dump=data_dump,
        yield_curve_dump=yield_curve_dump,
        fii_dump=fii_dump
    )

    # 5. Call Groq (skip Gemini — rate limits better reserved for stock analysis)
    ai_result = None
    try:
        text = await asyncio.to_thread(ai._call_groq_fallback, prompt)

        # Defensive parsing — strip stray code fences, find the JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end >= start:
            text = text[start: end + 1]

        ai_result = json.loads(text)
        ai_result["disclaimer"] = ai.DISCLAIMER_TEXT

    except Exception as e:
        logger.error(f"AI morning briefing failed: {e}")
        ai_result = None

    return {
        "raw": raw_payload,
        "ai": ai_result
    }
