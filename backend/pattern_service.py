"""Candlestick pattern detection — shape rules on OHLC data already fetched
elsewhere in the app. No ML, no training, no extra dependencies."""
from stock_service import get_chart


def _classify_candle(o, h, l, c):
    body, rng = abs(c - o), h - l
    if rng == 0:
        return None
    upper_wick, lower_wick = h - max(o, c), min(o, c) - l
    if body <= 0.1 * rng:
        return "Doji"
    if lower_wick >= 2 * body and upper_wick <= 0.3 * body:
        return "Hammer" if c >= o else "Hanging Man"
    if upper_wick >= 2 * body and lower_wick <= 0.3 * body:
        return "Shooting Star" if c <= o else "Inverted Hammer"
    return None


def _check_engulfing(prev, cur):
    prev_bull, cur_bull = prev["close"] > prev["open"], cur["close"] > cur["open"]
    prev_lo, prev_hi = min(prev["open"], prev["close"]), max(prev["open"], prev["close"])
    cur_lo, cur_hi = min(cur["open"], cur["close"]), max(cur["open"], cur["close"])
    engulfs = cur_lo <= prev_lo and cur_hi >= prev_hi
    if engulfs and not prev_bull and cur_bull:
        return "Bullish Engulfing"
    if engulfs and prev_bull and not cur_bull:
        return "Bearish Engulfing"
    return None


SIGNAL_MAP = {
    "Hammer": "Bullish", "Inverted Hammer": "Bullish",
    "Hanging Man": "Bearish", "Shooting Star": "Bearish",
    "Doji": "Neutral",
}


def get_candlestick_patterns(symbol: str, lookback_days: int = 10) -> dict:
    chart = get_chart(symbol, period="6mo")
    rows = chart.get("data", [])
    if len(rows) < 10:
        return {"patterns": [], "note": "Not enough price history."}

    detected = []
    start_idx = max(1, len(rows) - lookback_days)
    for i in range(start_idx, len(rows)):
        row = rows[i]
        # We need OHLC data. If any is missing, skip
        if any(row.get(k) is None for k in ["open", "high", "low", "close"]):
            continue
        
        single = _classify_candle(row["open"], row["high"], row["low"], row["close"])
        if single:
            detected.append({"date": row["date"], "pattern": single, "signal": SIGNAL_MAP.get(single, "Neutral")})
        
        if i > 0:
            prev = rows[i - 1]
            if all(prev.get(k) is not None for k in ["open", "close"]) and all(row.get(k) is not None for k in ["open", "close"]):
                eng = _check_engulfing(prev, row)
                if eng:
                    detected.append({"date": row["date"], "pattern": eng, "signal": "Bullish" if "Bullish" in eng else "Bearish"})

    # Sort descending by date (newest first)
    detected.reverse()

    return {
        "patterns": detected,
        "note": "Shape-based labels describing what recent candles look like — descriptive, not predictive. Academic evidence for single-candle patterns as standalone signals is weak; treat as context/vocabulary, not a trigger on its own.",
    }
