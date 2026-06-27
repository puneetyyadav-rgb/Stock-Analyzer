"""Data validation and cross-source divergence detection.

Intercepts scraped financial data before it reaches the AI prompt or UI,
flagging impossible values and highlighting disagreements between sources.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Ratio sanity bounds ───────────────────────────────────────────────
# Values outside these ranges are almost certainly scraping artefacts.
RATIO_BOUNDS = {
    "peRatio":        (0, 500),
    "pbRatio":        (0, 100),
    "roe":            (-2, 3),       # expressed as fraction (-200% to 300%)
    "roa":            (-1, 1),
    "profitMargin":   (-5, 5),
    "operatingMargin":(-5, 5),
    "debtToEquity":   (0, 50),
    "revenueGrowth":  (-1, 10),
    "earningsGrowth": (-10, 50),
    "beta":           (-2, 5),
    "dividendYield":  (0, 1),
}

DIVERGENCE_THRESHOLD_PCT = 30  # flag if two sources differ by > 30%


def _is_outlier(key: str, value) -> bool:
    """Return True if value falls outside the expected bounds for this metric."""
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return True  # non-numeric where numeric expected
    bounds = RATIO_BOUNDS.get(key)
    if bounds and (v < bounds[0] or v > bounds[1]):
        return True
    return False


def sanitize_overview(overview: dict) -> tuple[dict, list]:
    """Clean a stock overview dict.

    Returns (sanitized_overview, list_of_flagged_items).
    Each flagged item is a dict: {"field", "value", "reason"}.
    """
    if not overview:
        return {}, []

    sanitized = dict(overview)
    flags = []

    for key, bounds in RATIO_BOUNDS.items():
        val = sanitized.get(key)
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            flags.append({"field": key, "value": val, "reason": "Non-numeric value"})
            sanitized[key] = None
            continue
        if v < bounds[0] or v > bounds[1]:
            flags.append({
                "field": key,
                "value": v,
                "reason": f"Outside expected range [{bounds[0]}, {bounds[1]}]"
            })
            sanitized[key] = None  # null it so the AI doesn't use garbage

    if flags:
        logger.warning(f"Sanitized {len(flags)} outlier(s) in overview: {flags}")

    return sanitized, flags


def detect_divergences(overview: dict, external_data: dict) -> list:
    """Compare metrics across yfinance overview vs external scraped sources.

    Returns a list of divergence dicts:
      {"metric", "source_a", "value_a", "source_b", "value_b", "diff_pct"}
    """
    divergences = []
    if not overview or not external_data:
        return divergences

    # ── yfinance vs Trendlyne ──
    trendlyne = external_data.get("trendlyne", {})
    if trendlyne.get("available"):
        fundamentals = trendlyne.get("fundamentals", {})
        _compare(divergences, "P/E Ratio",
                 overview.get("peRatio"), "yfinance",
                 fundamentals.get("PE_Ratio"), "Trendlyne")
        _compare(divergences, "P/B Ratio",
                 overview.get("pbRatio"), "yfinance",
                 fundamentals.get("PB_Ratio"), "Trendlyne")
        _compare(divergences, "ROE",
                 _pct_to_abs(overview.get("roe")), "yfinance",
                 fundamentals.get("ROE"), "Trendlyne")

    # ── yfinance vs Tickertape ──
    tickertape = external_data.get("tickertape", {})
    if tickertape.get("available"):
        ratios = tickertape.get("ratios", {})
        _compare(divergences, "P/E Ratio",
                 overview.get("peRatio"), "yfinance",
                 ratios.get("pe"), "Tickertape")
        _compare(divergences, "P/B Ratio",
                 overview.get("pbRatio"), "yfinance",
                 ratios.get("pb"), "Tickertape")
        _compare(divergences, "ROE",
                 _pct_to_abs(overview.get("roe")), "yfinance",
                 ratios.get("roe"), "Tickertape")

    if divergences:
        logger.info(f"Detected {len(divergences)} cross-source divergence(s)")

    return divergences


def _pct_to_abs(val) -> Optional[float]:
    """Convert a fractional ratio (e.g. 0.15 for 15%) to absolute (15.0)."""
    if val is None:
        return None
    try:
        v = float(val)
        if -5 < v < 5:  # likely a fraction, convert to percentage
            return round(v * 100, 2)
        return v
    except (TypeError, ValueError):
        return None


def _compare(divergences: list, metric: str,
             val_a, src_a: str, val_b, src_b: str):
    """Append to divergences if values differ by more than threshold."""
    if val_a is None or val_b is None:
        return
    try:
        a, b = float(val_a), float(val_b)
    except (TypeError, ValueError):
        return
    if a == 0 and b == 0:
        return
    denom = abs(a) if a != 0 else abs(b)
    diff_pct = abs(a - b) / denom * 100
    if diff_pct > DIVERGENCE_THRESHOLD_PCT:
        divergences.append({
            "metric": metric,
            "source_a": src_a,
            "value_a": round(a, 2),
            "source_b": src_b,
            "value_b": round(b, 2),
            "diff_pct": round(diff_pct, 1),
        })


def build_divergence_note(divergences: list) -> str:
    """Build a human-readable note for embedding in AI prompts."""
    if not divergences:
        return ""
    lines = ["CROSS-SOURCE DIVERGENCE ALERT (flag these in your analysis):"]
    for d in divergences:
        lines.append(
            f"  - {d['metric']}: {d['source_a']} reports {d['value_a']} "
            f"vs {d['source_b']} reports {d['value_b']} "
            f"(diff {d['diff_pct']}%)"
        )
    return "\n".join(lines)
