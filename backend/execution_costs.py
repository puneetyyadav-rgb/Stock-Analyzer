"""
execution_costs.py — exact Indian transaction frictions + square-root market-impact model.

Pure math, no I/O. Used by backtest_engine (and reusable by a future live-execution scheduler) to turn
a paper strategy into a net-of-cost one. A strategy that looks great on gross returns routinely dies
once India's STT + DP charges + illiquidity slippage are subtracted — this module makes that explicit.

All rates are TUNABLE via COSTS. Defaults reflect NSE/SEBI schedules as of 2024-25; verify before live use.
"""
import math
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Fractions of traded notional unless noted. Sources: SEBI/NSE circulars (approx, tunable).
COSTS: Dict[str, float] = {
    # Securities Transaction Tax
    "STT_DELIVERY_BUY": 0.001,     # 0.1% on buy  (equity delivery)
    "STT_DELIVERY_SELL": 0.001,    # 0.1% on sell (equity delivery)
    "STT_FUT_SELL": 0.0002,        # 0.02% on sell only (stock/index futures; hiked from 0.0125% Oct-2024)
    # Exchange transaction charge (NSE)
    "EXCH_TXN_CASH": 0.0000297,    # 0.00297% per side (cash)
    "EXCH_TXN_FUT": 0.0000173,     # 0.00173% per side (futures)
    # SEBI turnover fee (₹10 / crore) per side
    "SEBI_FEE": 0.000001,
    # Stamp duty (buy side only)
    "STAMP_DELIVERY_BUY": 0.00015,  # 0.015%
    "STAMP_FUT_BUY": 0.00002,       # 0.002%
    # GST 18% on (brokerage + exchange txn + SEBI fee)
    "GST": 0.18,
    # Brokerage (fraction/side). Discount brokers charge ₹0 on delivery; futures ~₹20 flat → tiny frac.
    "BROKERAGE_FRAC": 0.0,
    # Depository participant charge — FIXED ₹ per sell scrip (demat debit). Bites small positions hard.
    "DP_PER_SELL": 15.0,
}

# Square-root market-impact coefficient γ by liquidity tier.
_GAMMA_TIER = {1: 0.20, 2: 0.40, 3: 0.80}   # tier1 = top-50 liquid, tier2 = top-200, tier3 = rest
_MAX_IMPACT = 0.25                            # clip one-way impact at 25% (illiquid trash)


def roundtrip_cost_frac(notional: float, instrument: str = "delivery",
                        brokerage_frac: float = None) -> float:
    """
    Round-trip (buy+sell) transaction cost as a FRACTION of one-way notional.
    instrument: 'delivery' (long cash) or 'futures' (short leg — no overnight equity short in India).
    """
    if not notional or notional <= 0:
        return 0.0
    c = COSTS
    brk = c["BROKERAGE_FRAC"] if brokerage_frac is None else brokerage_frac
    exch = c["EXCH_TXN_FUT"] if instrument == "futures" else c["EXCH_TXN_CASH"]

    if instrument == "futures":
        stt = c["STT_FUT_SELL"]
        stamp = c["STAMP_FUT_BUY"]
        dp = 0.0
    else:  # delivery
        stt = c["STT_DELIVERY_BUY"] + c["STT_DELIVERY_SELL"]
        stamp = c["STAMP_DELIVERY_BUY"]
        dp = c["DP_PER_SELL"] / notional      # fixed ₹ → fraction

    exch_both = exch * 2.0
    sebi_both = c["SEBI_FEE"] * 2.0
    brk_both = brk * 2.0
    gst = c["GST"] * (brk_both + exch_both + sebi_both)   # GST on brokerage + txn charges
    return stt + stamp + dp + exch_both + sebi_both + brk_both + gst


def market_impact_frac(order_shares: float, adv_shares: float, daily_vol: float, gamma: float) -> float:
    """
    One-way slippage as a fraction of price via the square-root law:  impact = γ · σ · √(order/ADV).
    Apply on BOTH entry and exit. Clipped so an illiquid name can't produce a nonsensical number.
    """
    if not order_shares or order_shares <= 0 or not adv_shares or adv_shares <= 0:
        return 0.0
    participation = order_shares / adv_shares
    impact = gamma * max(daily_vol, 0.0) * math.sqrt(participation)
    return min(impact, _MAX_IMPACT)


def gamma_for_liquidity(turnover_rank: int) -> float:
    """γ by turnover rank (0 = most liquid). Illiquid names push harder against the book."""
    if turnover_rank < 50:
        return _GAMMA_TIER[1]
    if turnover_rank < 200:
        return _GAMMA_TIER[2]
    return _GAMMA_TIER[3]


if __name__ == "__main__":  # offline cost checks
    # Delivery round-trip on ₹1L ≈ 0.24% (STT 0.2% dominates + ₹15 stamp + ₹15 DP)
    d = roundtrip_cost_frac(100000.0, "delivery")
    assert 0.0020 < d < 0.0030, d
    # Futures cheaper (single-side STT, no DP, tiny stamp)
    f = roundtrip_cost_frac(100000.0, "futures")
    assert f < d and f < 0.001, (f, d)
    # DP fixed charge bites small positions much harder (fraction rises as notional shrinks)
    assert roundtrip_cost_frac(10000.0, "delivery") > roundtrip_cost_frac(1000000.0, "delivery")

    # Impact rises with participation and is clipped
    i_small = market_impact_frac(1000, 100000, 0.02, 0.4)     # 1% of ADV
    i_big = market_impact_frac(40000, 100000, 0.02, 0.4)      # 40% of ADV
    assert 0 < i_small < i_big <= _MAX_IMPACT, (i_small, i_big)
    # γ=0.4, σ=0.02, part=0.25 → 0.4*0.02*0.5 = 0.004
    assert abs(market_impact_frac(25000, 100000, 0.02, 0.4) - 0.004) < 1e-9
    assert gamma_for_liquidity(10) < gamma_for_liquidity(100) < gamma_for_liquidity(500)
    print("ok execution_costs  delivery_rt=%.4f%%  futures_rt=%.4f%%  impact@40%%ADV=%.3f%%" % (
        d * 100, f * 100, i_big * 100))
