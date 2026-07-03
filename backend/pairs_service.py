"""
pairs_service.py — Statistical Arbitrage & Cointegration Scanner Engine.

Implements the Engle-Granger two-step cointegration test across sector peer stocks:
1. OLS regression on log prices: ln(P_A) = beta * ln(P_B) + alpha + epsilon
2. Ornstein-Uhlenbeck AR(1) mean-reversion analysis on residuals epsilon:
   d(epsilon) = lambda * epsilon_{t-1} + u
   Half-life tau = -ln(2) / lambda
3. Live Spread Z-score calculation for market-neutral signals:
   Z < -2.0 -> Long A / Short B
   Z > +2.0 -> Short A / Long B
"""
import logging
import math
import time
from functools import lru_cache
from typing import Dict, Any, List, Tuple, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Core NSE Sector Peer Pairs for Statistical Arbitrage Scanning
SECTOR_PAIRS = [
    ("HDFCBANK.NS", "ICICIBANK.NS", "Banking"),
    ("SBIN.NS", "AXISBANK.NS", "Banking"),
    ("KOTAKBANK.NS", "INDUSINDBK.NS", "Banking"),
    ("TCS.NS", "INFY.NS", "IT Services"),
    ("WIPRO.NS", "HCLTECH.NS", "IT Services"),
    ("TECHM.NS", "LTIM.NS", "IT Services"),
    ("RELIANCE.NS", "ONGC.NS", "Energy"),
    ("TATAMOTORS.NS", "M&M.NS", "Auto"),
    ("MARUTI.NS", "BAJAJ-AUTO.NS", "Auto"),
    ("SUNPHARMA.NS", "CIPLA.NS", "Pharma"),
    ("DRREDDY.NS", "DIVISLAB.NS", "Pharma"),
    ("LT.NS", "SIEMENS.NS", "Capital Goods"),
    ("ULTRACEMCO.NS", "GRASIM.NS", "Cement/Materials"),
    ("TATASTEEL.NS", "JSWSTEEL.NS", "Metals"),
]


def calculate_cointegration(series_a: List[float], series_b: List[float]) -> Dict[str, Any]:
    """
    Evaluates cointegration between two price series using vectorized NumPy math.
    Returns beta (hedge ratio), half_life (days), z_score, p_value approximation, and status.
    """
    a = np.asarray(series_a, dtype=float)
    b = np.asarray(series_b, dtype=float)
    n = min(len(a), len(b))
    if n < 60:
        return {"cointegrated": False, "reason": "insufficient data"}

    a = a[-n:]
    b = b[-n:]

    # Work in log prices for constant proportional hedge ratio
    log_a = np.log(a)
    log_b = np.log(b)

    # Step 1: OLS Regression log_a = beta * log_b + alpha
    X = np.vstack([log_b, np.ones(n)]).T
    beta, alpha = np.linalg.lstsq(X, log_a, rcond=None)[0]

    # Spread residuals
    spread = log_a - (beta * log_b + alpha)

    # Step 2: ADF stationarity check on spread via AR(1) difference regression
    # d(spread) = gamma * spread_{t-1} + e
    ds = np.diff(spread)
    s_lag = spread[:-1]
    
    # OLS for ds = gamma * s_lag + c
    X_adf = np.vstack([s_lag, np.ones(n - 1)]).T
    gamma, c_adf = np.linalg.lstsq(X_adf, ds, rcond=None)[0]

    # Standard error of gamma
    res_adf = ds - (gamma * s_lag + c_adf)
    sigma_res = np.std(res_adf, ddof=2)
    s_xx = np.sum((s_lag - np.mean(s_lag)) ** 2)
    se_gamma = sigma_res / np.sqrt(max(1e-9, s_xx))
    t_stat = gamma / max(1e-9, se_gamma)

    # Approximate Engle-Granger critical values for n ~ 250
    # 1% critical ~ -3.43, 5% ~ -2.86, 10% ~ -2.57
    if t_stat <= -3.43:
        p_val = 0.005
    elif t_stat <= -2.86:
        p_val = 0.03
    elif t_stat <= -2.57:
        p_val = 0.08
    else:
        p_val = 0.25

    # Step 3: Ornstein-Uhlenbeck Half-Life calculation
    # If gamma < 0, spread mean-reverts with speed -gamma
    if gamma < -1e-5:
        half_life = -np.log(2.0) / gamma
    else:
        half_life = 999.0  # Non-reverting / explosive

    # Step 4: Rolling Z-Score of the spread over recent 30-day window
    roll_win = min(30, n)
    recent_spread = spread[-roll_win:]
    mu_roll = np.mean(recent_spread)
    sig_roll = np.std(recent_spread, ddof=1)
    z_score = float((spread[-1] - mu_roll) / max(1e-6, sig_roll))

    is_coint = bool(p_val < 0.05 and 2.0 <= half_life <= 45.0)

    # Signal direction
    signal = "NEUTRAL"
    if is_coint:
        if z_score < -2.0:
            signal = "BUY_A_SELL_B"  # Spread is too low -> Long A, Short B
        elif z_score > 2.0:
            signal = "SELL_A_BUY_B"  # Spread is too high -> Short A, Long B
        elif abs(z_score) < 0.5:
            signal = "CONVERGED_CLOSE"

    return {
        "cointegrated": is_coint,
        "beta": round(float(beta), 4),
        "alpha": round(float(alpha), 4),
        "tStat": round(float(t_stat), 2),
        "pValue": p_val,
        "halfLifeDays": round(float(half_life), 1),
        "currentSpreadZ": round(z_score, 2),
        "signal": signal,
        "lastPriceA": round(float(a[-1]), 2),
        "lastPriceB": round(float(b[-1]), 2),
    }


_cache_pairs: Dict[str, Any] = {}
_cache_ts: float = 0.0


def scan_market_pairs() -> List[Dict[str, Any]]:
    """
    Scans the SECTOR_PAIRS universe using historical daily data.
    Caches results for 30 minutes to ensure fast API responses.
    """
    global _cache_pairs, _cache_ts
    now = time.time()
    if _cache_pairs and (now - _cache_ts) < 1800:
        return _cache_pairs.get("results", [])

    import yfinance as yf

    results = []
    # Batch fetch tickers
    unique_syms = list(set([sym for pair in SECTOR_PAIRS for sym in pair[:2]]))
    try:
        data = yf.download(unique_syms, period="1y", interval="1d", auto_adjust=True, progress=False)["Close"]
    except Exception as e:
        logger.error(f"Pairs scan yfinance download failed: {e}")
        return _cache_pairs.get("results", [])

    for sym_a, sym_b, sector in SECTOR_PAIRS:
        try:
            if sym_a not in data or sym_b not in data:
                continue
            df_pair = data[[sym_a, sym_b]].dropna()
            if len(df_pair) < 80:
                continue
            res = calculate_cointegration(df_pair[sym_a].tolist(), df_pair[sym_b].tolist())
            res["pair"] = f"{sym_a.replace('.NS','')} / {sym_b.replace('.NS','')}"
            res["symbolA"] = sym_a
            res["symbolB"] = sym_b
            res["sector"] = sector
            results.append(res)
        except Exception as ex:
            logger.debug(f"Pair evaluation failed for {sym_a}/{sym_b}: {ex}")

    # Sort: cointegrated first, then by absolute Z-score descending
    results.sort(key=lambda x: (not x["cointegrated"], -abs(x["currentSpreadZ"])))
    _cache_pairs = {"results": results}
    _cache_ts = now
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    np.random.seed(42)
    # Generate synthetic cointegrated series
    n_pts = 250
    b_syn = 100.0 + np.cumsum(np.random.normal(0, 1, n_pts))
    # Spread is OU process
    ou_spread = np.zeros(n_pts)
    for t in range(1, n_pts):
        ou_spread[t] = ou_spread[t - 1] - 0.15 * ou_spread[t - 1] + np.random.normal(0, 0.5)
    a_syn = b_syn * 1.2 + ou_spread

    c_res = calculate_cointegration(a_syn, b_syn)
    print("Synthetic Cointegrated Pair Result:", c_res)
    assert c_res["cointegrated"] is True, "Failed to detect synthetic cointegration"
    assert 3.0 <= c_res["halfLifeDays"] <= 12.0, f"Unexpected half-life: {c_res['halfLifeDays']}"
    print("ok pairs_service self-test passed cleanly!")
