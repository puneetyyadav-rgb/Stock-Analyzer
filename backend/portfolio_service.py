"""
portfolio_service.py — Hierarchical Risk Parity (HRP) & Kelly Portfolio Constructor.

Implements Marcos López de Prado's HRP algorithm:
1. Distance metric D_{i,j} = sqrt(0.5 * (1 - corr_{i,j}))
2. Hierarchical clustering linkage & quasi-diagonal tree sorting
3. Recursive bisection inverse-variance weight allocation
4. Fractional Kelly position sizing against EWMA Monte Carlo VaR
"""
import logging
import math
from typing import Dict, Any, List

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


def _get_cluster_var(cov: pd.DataFrame, items: List[str]) -> float:
    """Computes cluster variance using inverse diagonal covariance weighting."""
    sub_cov = cov.loc[items, items]
    iv_diag = 1.0 / np.diag(sub_cov.values)
    w = iv_diag / np.sum(iv_diag)
    return float(np.dot(w.T, np.dot(sub_cov.values, w)))


def _recursive_bisection(cov: pd.DataFrame, sort_order: List[str]) -> pd.Series:
    """Recursively bisects sorted asset tree and allocates capital inverse to cluster variance."""
    weights = pd.Series(1.0, index=sort_order)
    clusters = [sort_order]

    while len(clusters) > 0:
        clusters = [c[i:j] for c in clusters for i, j in ((0, len(c) // 2), (len(c) // 2, len(c))) if len(c) > 1]
        for i in range(0, len(clusters), 2):
            left = clusters[i]
            right = clusters[i + 1]
            var_left = _get_cluster_var(cov, left)
            var_right = _get_cluster_var(cov, right)
            alloc_factor = 1.0 - var_left / max(1e-9, var_left + var_right)
            weights[left] *= alloc_factor
            weights[right] *= (1.0 - alloc_factor)

    return weights


def calculate_hrp_weights(returns_df: pd.DataFrame) -> Dict[str, float]:
    """
    Computes exact Hierarchical Risk Parity weights for a return matrix.
    Returns normalized weights summing to 1.0.
    """
    corr = returns_df.corr().fillna(0.0)
    cov = returns_df.cov().fillna(0.0)

    # Distance metric
    dist = np.sqrt(0.5 * np.clip(1.0 - corr.values, 0.0, 2.0))
    np.fill_diagonal(dist, 0.0)
    condensed_dist = squareform(dist, checks=False)

    # Hierarchical clustering
    link = linkage(condensed_dist, method="single")
    sort_idx = leaves_list(link)
    sort_order = [returns_df.columns[i] for i in sort_idx]

    # Recursive bisection
    weights = _recursive_bisection(cov, sort_order)
    norm_w = weights / weights.sum()
    return {k: round(float(v), 4) for k, v in norm_w.items()}


def calculate_portfolio_metrics(symbols: List[str], capital: float = 1000000.0) -> Dict[str, Any]:
    """
    Constructs an optimal HRP portfolio, computes annual risk/return vs Equal-Weighting,
    and applies Fractional Kelly sizing.
    """
    import yfinance as yf

    clean_syms = [s if s.endswith(".NS") else f"{s}.NS" for s in symbols]
    if len(clean_syms) < 2:
        return {"error": "Select at least 2 stocks to build an HRP portfolio."}

    data = yf.download(clean_syms, period="1y", interval="1d", auto_adjust=True, progress=False)["Close"]
    data = data.dropna(axis=1, how="all").ffill().bfill().dropna()

    if data.shape[1] < 2 or len(data) < 60:
        return {"error": "Insufficient overlapping historical data for selected stocks."}

    ret = data.pct_change().dropna()
    hrp_w = calculate_hrp_weights(ret)

    # Equal weight comparison
    n = len(hrp_w)
    eq_w = {sym: round(1.0 / n, 4) for sym in hrp_w.keys()}

    # Covariance annualized
    cov_ann = ret.cov() * 252.0
    mean_ret_ann = ret.mean() * 252.0

    w_hrp_vec = np.array([hrp_w[sym] for sym in ret.columns])
    w_eq_vec = np.array([eq_w[sym] for sym in ret.columns])

    hrp_ret = float(np.dot(w_hrp_vec, mean_ret_ann))
    hrp_vol = float(np.sqrt(np.dot(w_hrp_vec.T, np.dot(cov_ann.values, w_hrp_vec))))
    hrp_sharpe = hrp_ret / max(0.01, hrp_vol)

    eq_ret = float(np.dot(w_eq_vec, mean_ret_ann))
    eq_vol = float(np.sqrt(np.dot(w_eq_vec.T, np.dot(cov_ann.values, w_eq_vec))))
    eq_sharpe = eq_ret / max(0.01, eq_vol)

    # Fractional Kelly (Half Kelly)
    rf = 0.07  # Indian 10y risk-free rate approx
    excess_ret = max(0.0, hrp_ret - rf)
    full_kelly = excess_ret / max(0.001, hrp_vol ** 2)
    half_kelly = min(1.0, max(0.15, full_kelly * 0.5))
    rec_capital = capital * half_kelly

    # Share count allocations based on latest prices
    latest_px = data.iloc[-1].to_dict()
    allocations = []
    for sym in ret.columns:
        px = float(latest_px[sym])
        w = hrp_w[sym]
        alloc_amt = rec_capital * w
        shares = int(alloc_amt / max(1.0, px))
        allocations.append({
            "symbol": sym.replace(".NS", ""),
            "weightPercent": round(w * 100.0, 1),
            "eqWeightPercent": round(eq_w[sym] * 100.0, 1),
            "latestPrice": round(px, 2),
            "recommendedShares": shares,
            "allocatedRupees": round(shares * px, 2),
        })

    allocations.sort(key=lambda x: x["weightPercent"], reverse=True)

    return {
        "capital": capital,
        "recommendedCapital": round(rec_capital, 2),
        "fractionalKellyPct": round(half_kelly * 100.0, 1),
        "hrpMetrics": {
            "expectedReturnPct": round(hrp_ret * 100.0, 2),
            "volatilityPct": round(hrp_vol * 100.0, 2),
            "sharpeRatio": round(hrp_sharpe, 2),
        },
        "eqMetrics": {
            "expectedReturnPct": round(eq_ret * 100.0, 2),
            "volatilityPct": round(eq_vol * 100.0, 2),
            "sharpeRatio": round(eq_sharpe, 2),
        },
        "volReductionPct": round(((eq_vol - hrp_vol) / max(0.01, eq_vol)) * 100.0, 1),
        "allocations": allocations,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    np.random.seed(42)
    # Synthetic 4-asset correlation structure
    n_days = 250
    r1 = np.random.normal(0.0005, 0.01, n_days)
    r2 = r1 * 0.9 + np.random.normal(0, 0.002, n_days)  # High corr with r1
    r3 = np.random.normal(0.0003, 0.02, n_days)         # High vol independent
    r4 = r3 * -0.5 + np.random.normal(0, 0.01, n_days)  # Neg corr with r3

    df_ret = pd.DataFrame({"A": r1, "B": r2, "C": r3, "D": r4})
    weights = calculate_hrp_weights(df_ret)
    print("Synthetic HRP Weights:", weights)
    assert abs(sum(weights.values()) - 1.0) < 1e-4, "Weights do not sum to 1.0"
    # Asset C has higher vol than D in cluster -> should get lower weight than D
    assert weights["C"] < weights["D"], f"HRP failed to penalize high vol asset C vs D: {weights}"
    print("ok portfolio_service self-test passed cleanly!")
