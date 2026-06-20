"""Regime classification — pure arithmetic on data already computed elsewhere.
No ML. No training. No model file."""
import statistics
from stock_service import get_chart, compute_technicals


def classify_trend(technicals: dict) -> str:
    price = technicals.get("currentPrice")
    sma50 = technicals.get("sma50")
    sma200 = technicals.get("sma200")
    if price is None or sma50 is None:
        return "Unknown"
    if sma200 is None:  # less than ~200 trading days of history available
        return "Uptrend" if price > sma50 else "Downtrend"
    if price > sma50 > sma200:
        return "Strong Uptrend"
    if price < sma50 < sma200:
        return "Strong Downtrend"
    return "Sideways/Mixed"


def classify_volatility(closes: list) -> str:
    if len(closes) < 30:
        return "Unknown"
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]
    recent, longer = returns[-10:], returns[-60:] if len(returns) >= 60 else returns
    if len(recent) < 5 or len(longer) < 10:
        return "Unknown"
    recent_vol, longer_vol = statistics.pstdev(recent), statistics.pstdev(longer)
    if longer_vol == 0:
        return "Unknown"
    ratio = recent_vol / longer_vol
    if ratio > 1.3:
        return "Expanding"
    if ratio < 0.7:
        return "Contracting"
    return "Stable"


REGIME_NOTES = {
    ("Strong Uptrend", "Contracting"): "Healthy trend cooling off — often a continuation setup, not a warning sign on its own.",
    ("Strong Uptrend", "Expanding"): "Strong move, but rising volatility inside an uptrend can mean a breakout OR exhaustion — context matters more here than usual.",
    ("Strong Downtrend", "Expanding"): "Often what panic/capitulation selling looks like — volatility tends to peak before downtrends stabilize.",
    ("Strong Downtrend", "Contracting"): "Downtrend losing momentum — could be basing, not yet a reversal signal on its own.",
    ("Sideways/Mixed", "Contracting"): "Classic 'coiling' state — low-volatility sideways moves often precede a breakout in either direction.",
    ("Sideways/Mixed", "Expanding"): "Choppy and indecisive — higher whipsaw risk, lower reliability of any single signal right now.",
}


def classify_regime(symbol: str) -> dict:
    technicals = compute_technicals(symbol)
    chart = get_chart(symbol, period="6mo")
    closes = [d["close"] for d in chart.get("data", []) if d.get("close") is not None]

    trend = classify_trend(technicals)
    volatility = classify_volatility(closes)
    note = REGIME_NOTES.get((trend, volatility), "Not enough data for a confident regime read.")

    return {
        "trend": trend,
        "volatility_state": volatility,
        "regime_label": f"{trend} / Volatility {volatility}",
        "note": note,
        "supporting_data": {
            "currentPrice": technicals.get("currentPrice"),
            "sma50": technicals.get("sma50"),
            "sma200": technicals.get("sma200"),
        },
    }
