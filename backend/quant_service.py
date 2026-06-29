"""
quant_service.py — Pure numpy Institutional Quantitative Math Engine
Bypasses heavy C-compiled dependencies (statsmodels, pykalman, arch) for serverless compatibility.
Computes Adaptive Kalman Filter, Hurst Exponent, Fat-Tail Bootstrap Monte Carlo VaR/CVaR, Level-2 OBI, and Fibonacci Pivots.
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def calculate_fibonacci_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    """Calculates standard Fibonacci Pivot Points (P, R1-R3, S1-S3)."""
    try:
        p = (high + low + close) / 3.0
        diff = high - low
        return {
            "pivot": round(p, 2),
            "r1": round(p + 0.382 * diff, 2),
            "r2": round(p + 0.618 * diff, 2),
            "r3": round(p + 1.000 * diff, 2),
            "s1": round(p - 0.382 * diff, 2),
            "s2": round(p - 0.618 * diff, 2),
            "s3": round(p - 1.000 * diff, 2),
        }
    except Exception as e:
        logger.error(f"Error calculating Fibonacci pivots: {e}")
        return {}


def calculate_bollinger_squeeze(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Dict[str, Any]:
    """Computes Bollinger Band Width and ATR 14 to detect impending volatility squeeze breakouts."""
    try:
        if len(closes) < 20:
            return {"status": "Unknown", "bandWidth": 0.0, "atr14": 0.0}
        
        recent_closes = closes[-20:]
        sma20 = float(np.mean(recent_closes))
        std20 = float(np.std(recent_closes))
        
        upper = sma20 + (2.0 * std20)
        lower = sma20 - (2.0 * std20)
        band_width = (upper - lower) / sma20 if sma20 > 0 else 0.0
        
        # Calculate ATR 14
        trs = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            trs.append(tr)
        atr14 = float(np.mean(trs[-14:])) if len(trs) >= 14 else float(np.mean(trs)) if trs else 0.0
        
        status = "Normal"
        if band_width < 0.06:
            status = "SQUEEZE (High Breakout Probability)"
        elif band_width > 0.18:
            status = "EXPANDING (Active Volatility)"
            
        return {
            "status": status,
            "bandWidth": round(band_width, 4),
            "atr14": round(atr14, 2),
            "upperBand": round(upper, 2),
            "lowerBand": round(lower, 2),
            "sma20": round(sma20, 2)
        }
    except Exception as e:
        logger.error(f"Error calculating Bollinger Squeeze: {e}")
        return {"status": "Error", "bandWidth": 0.0, "atr14": 0.0}


def calculate_hurst_exponent(log_prices: np.ndarray) -> Dict[str, Any]:
    """
    Computes Hurst Exponent (H) via pure numpy variance scaling.
    Operates on the LOG-PRICE level series (NOT returns) — the std-of-lagged-
    differences estimator is only valid on the level series; feeding returns
    differences it twice and biases H toward the anti-persistent zone.
    Classifies regime into Mean-Reverting (<0.45), Random Walk (~0.50), or Trending (>0.55).
    """
    try:
        series = log_prices[~np.isnan(log_prices)]
        if len(series) < 60:
            return {"hurst": 0.50, "regime": "Insufficient Data"}

        lags = [2, 4, 8, 16, 32]
        tau = []
        for lag in lags:
            if lag >= len(series):
                continue
            # Std-dev of lagged differences of the level series
            diffs = series[lag:] - series[:-lag]
            tau.append(np.std(diffs))
            
        if len(tau) < 3:
            return {"hurst": 0.50, "regime": "Random Walk"}
            
        # Fit log(lags) vs log(tau)
        log_lags = np.log(lags[:len(tau)])
        log_tau = np.log(tau)
        poly = np.polyfit(log_lags, log_tau, 1)
        hurst = float(poly[0])
        
        # Clamp H between 0.05 and 0.95
        hurst = max(0.05, min(0.95, hurst))
        
        regime = "Random Walk (No Edge)"
        if hurst < 0.45:
            regime = "Mean-Reverting (Anti-Persistent)"
        elif hurst > 0.55:
            regime = "Trending (Momentum Persistence)"
            
        return {
            "hurst": round(hurst, 3),
            "regime": regime
        }
    except Exception as e:
        logger.error(f"Error calculating Hurst Exponent: {e}")
        return {"hurst": 0.50, "regime": "Error"}


def calculate_adaptive_kalman_1d(closes: np.ndarray) -> Dict[str, Any]:
    """
    Local-Linear-Trend Kalman filter (2-state: level + slope) in bare-metal numpy.
    Tracks trend without the lag of a level-only filter and exposes a velocity
    (slope) signal. Genuinely adaptive: measurement noise R is the LOCAL rolling
    variance while process noise Q is a fixed fraction of the GLOBAL variance, so
    the Kalman gain actually varies over time. (The old level-only filter scaled
    both Q and R by the same rolling variance → constant Q/R ratio → it was just a
    fixed-gain EMA, not adaptive and unable to track trends.)
    """
    try:
        n = len(closes)
        if n < 20:
            return {"smoothedPrice": float(closes[-1]) if n > 0 else 0.0, "kalmanTrend": "Unknown",
                    "kalmanVelocity": 0.0, "noiseDivergence": 0.0}

        F = np.array([[1.0, 1.0], [0.0, 1.0]])   # level advances by slope each step
        global_var = float(np.var(np.diff(closes))) or 1.0
        Q = np.array([[global_var * 0.05, 0.0], [0.0, global_var * 0.005]])

        x = np.array([float(closes[0]), 0.0])     # [level, slope]
        P = np.eye(2) * global_var
        smoothed = np.zeros(n)
        smoothed[0] = x[0]

        for i in range(1, n):
            window = closes[max(0, i - 20):i]
            r = max(float(np.var(window)) if len(window) > 1 else global_var, 1e-6)

            # Predict
            x = F @ x
            P = F @ P @ F.T + Q
            # Update (measurement matrix is [1, 0] → observed value is just the level)
            y = float(closes[i]) - x[0]
            S = P[0, 0] + r
            K = P[:, 0] / S                       # Kalman gain, shape (2,)
            x = x + K * y
            P = P - np.outer(K, P[0, :])
            smoothed[i] = x[0]

        latest_smoothed = float(smoothed[-1])
        slope = float(x[1])
        trend = "Bullish Kalman State" if slope > 0 else "Bearish Kalman State"

        return {
            "smoothedPrice": round(latest_smoothed, 2),
            "kalmanTrend": trend,
            "kalmanVelocity": round(slope, 4),
            "noiseDivergence": round(float(closes[-1]) - latest_smoothed, 2)
        }
    except Exception as e:
        logger.error(f"Error calculating Kalman Filter: {e}")
        return {"smoothedPrice": 0.0, "kalmanTrend": "Error", "kalmanVelocity": 0.0, "noiseDivergence": 0.0}


def calculate_fat_tail_var(returns: np.ndarray, portfolio_val: float = 100000.0, horizon_days: int = 10) -> Dict[str, Any]:
    """
    Block-bootstrap Monte Carlo simulation (10,000 paths over 10 days).
    Samples contiguous BLOCKS of empirical LOG returns so volatility clustering
    (GARCH-style crash persistence) survives — IID resampling destroys it and
    understates multi-day tail risk. Deterministic (seeded) so the deck doesn't
    jitter between calls. Outputs 95%/99% VaR and 95% Expected Shortfall (CVaR).
    """
    try:
        clean_returns = returns[~np.isnan(returns)]
        if len(clean_returns) < 30:
            return {"var95Pct": 0.0, "var99Pct": 0.0, "cvar95Pct": 0.0, "var95Cash": 0.0}

        rng = np.random.default_rng(12345)
        num_sims = 10000
        block = 5  # ponytail: fixed 5-day blocks; switch to stationary bootstrap if regimes vary widely
        n = len(clean_returns)
        n_blocks = -(-horizon_days // block)  # ceil

        # Build (num_sims, horizon) paths from contiguous wrapped blocks → preserves clustering
        starts = rng.integers(0, n, size=(num_sims, n_blocks))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
        idx = idx.reshape(num_sims, n_blocks * block)[:, :horizon_days]
        paths = clean_returns[idx]

        # Inputs are LOG returns → horizon return is exp(sum) - 1, NOT prod(1 + r)
        cumulative_returns = np.expm1(paths.sum(axis=1))

        var_95 = float(np.percentile(cumulative_returns, 5.0))
        var_99 = float(np.percentile(cumulative_returns, 1.0))

        # Expected Shortfall (CVaR) at 95%: mean of worst 5% outcomes
        tail_95 = cumulative_returns[cumulative_returns <= var_95]
        cvar_95 = float(np.mean(tail_95)) if len(tail_95) > 0 else var_95
        
        return {
            "var95Pct": round(var_95 * 100.0, 2),
            "var99Pct": round(var_99 * 100.0, 2),
            "cvar95Pct": round(cvar_95 * 100.0, 2),
            "var95Cash": round(abs(var_95) * portfolio_val, 2),
            "cvar95Cash": round(abs(cvar_95) * portfolio_val, 2),
            "horizonDays": horizon_days
        }
    except Exception as e:
        logger.error(f"Error calculating Monte Carlo VaR: {e}")
        return {"var95Pct": 0.0, "var99Pct": 0.0, "cvar95Pct": 0.0, "var95Cash": 0.0}


def calculate_microstructure_obi(bid_size: float, ask_size: float) -> Dict[str, Any]:
    """Calculates Level-2 Order Book Imbalance (OBI) ratio from Kotak depth data."""
    try:
        total = bid_size + ask_size
        if total <= 0:
            return {"obiRatio": 0.0, "flowSignal": "Neutral / No Data"}
            
        obi = (bid_size - ask_size) / total
        
        signal = "Balanced Liquidity"
        if obi > 0.25:
            signal = "Strong Institutional Accumulation (Bid Dominance)"
        elif obi < -0.25:
            signal = "Strong Institutional Distribution (Ask Dominance)"
            
        return {
            "obiRatio": round(obi, 3),
            "flowSignal": signal,
            "totalBidQty": int(bid_size),
            "totalAskQty": int(ask_size)
        }
    except Exception as e:
        logger.error(f"Error calculating OBI: {e}")
        return {"obiRatio": 0.0, "flowSignal": "Error"}


def _rank_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation in pure numpy (ties broken by argsort order)."""
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / denom) if denom > 0 else 0.0


def backtest_signal_ic(closes: List[float], volumes: Optional[List[float]] = None,
                       fwd_days: int = 5, step: int = 5, lookback: int = 120) -> Dict[str, Any]:
    """
    Walk-forward Information Coefficient for the composite quantScore.
    At each sampled bar it recomputes the deck on the trailing `lookback` window and
    correlates the live quantScore with the realized forward `fwd_days` return.
    IC is the rank correlation: >0 means real predictive edge (|IC| ~0.03-0.10 is
    meaningful in equities); hitRate is the directional agreement of score>50 vs an up-move.
    Without this, quantScore is an unvalidated number — same trap as the AI verdict.
    """
    px = np.asarray(closes, dtype=float)
    n = len(px)
    if n < lookback + fwd_days + step:
        return {"available": False, "reason": "insufficient history"}

    vol = np.asarray(volumes, dtype=float) if volumes is not None else None
    scores, fwd = [], []
    for t in range(lookback, n - fwd_days, step):
        win = px[t - lookback:t]
        # no intraday H/L in a close-only backtest → close proxies (ATR-driven terms degrade gracefully)
        deck = compute_complete_quant_deck("BT", {
            "close": win.tolist(), "high": win.tolist(), "low": win.tolist(),
            "volume": vol[t - lookback:t].tolist() if vol is not None else [],
        })
        s = deck.get("quantScore")
        if s is None:
            continue
        scores.append(s)
        fwd.append(px[t + fwd_days] / px[t] - 1.0)

    if len(scores) < 10:
        return {"available": False, "reason": "too few samples"}
    scores, fwd = np.array(scores), np.array(fwd)
    return {
        "available": True,
        "ic": round(_rank_corr(scores, fwd), 4),
        "hitRate": round(float(np.mean((scores > 50) == (fwd > 0))), 3),
        "samples": len(scores),
        "fwdDays": fwd_days,
    }


def compute_complete_quant_deck(symbol: str, ohlcv: Dict[str, List[float]], kotak_depth: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Master quantitative aggregator feeding the AI prompt and UI dashboard."""
    try:
        closes = np.array(ohlcv.get("close", []), dtype=float)
        highs = np.array(ohlcv.get("high", []), dtype=float)
        lows = np.array(ohlcv.get("low", []), dtype=float)
        volumes = np.array(ohlcv.get("volume", []), dtype=float)
        
        if len(closes) < 5:
            return {"status": "Insufficient Data"}
            
        latest_close = float(closes[-1])
        latest_high = float(highs[-1])
        latest_low = float(lows[-1])
        
        # Log-price level series (for Hurst) + daily log returns (for VaR)
        pos = closes[closes > 0]
        log_prices = np.log(pos) if len(pos) > 1 else np.array([])
        returns = np.diff(log_prices) if len(log_prices) > 1 else np.array([])

        pivots = calculate_fibonacci_pivots(latest_high, latest_low, latest_close)
        squeeze = calculate_bollinger_squeeze(closes, highs, lows)
        hurst = calculate_hurst_exponent(log_prices)
        kalman = calculate_adaptive_kalman_1d(closes)
        var_risk = calculate_fat_tail_var(returns)
        
        # Calculate Relative Volume (RVOL)
        rvol = 1.0
        if len(volumes) >= 20:
            avg_vol = float(np.mean(volumes[-20:]))
            rvol = float(volumes[-1]) / avg_vol if avg_vol > 0 else 1.0
            
        # Extract OBI from Kotak depth if available
        bid_qty = 0.0
        ask_qty = 0.0
        if kotak_depth and isinstance(kotak_depth, dict):
            bids = kotak_depth.get("bids", [])
            asks = kotak_depth.get("asks", [])
            bid_qty = sum(float(b.get("quantity", 0)) for b in bids if isinstance(b, dict))
            ask_qty = sum(float(a.get("quantity", 0)) for a in asks if isinstance(a, dict))
            
        obi = calculate_microstructure_obi(bid_qty, ask_qty)
        
        # Compute overall Institutional Quant Score (0 - 100)
        score = 50.0
        if kalman.get("kalmanTrend", "").startswith("Bullish"):
            score += 15.0
        elif kalman.get("kalmanTrend", "").startswith("Bearish"):
            score -= 15.0
            
        if hurst.get("regime", "").startswith("Trending"):
            # trending regime amplifies the Kalman directional read (no path dependence on running score)
            score += 10.0 if kalman.get("kalmanTrend", "").startswith("Bullish") else -10.0
            
        if obi.get("obiRatio", 0) > 0.20:
            score += 15.0
        elif obi.get("obiRatio", 0) < -0.20:
            score -= 15.0
            
        if rvol > 1.5 and score > 50:
            score += 10.0
            
        score = max(5.0, min(95.0, score))
        
        backtest = {"available": False}
        if symbol != "BT" and len(closes) >= 140:
            try:
                backtest = backtest_signal_ic(closes.tolist(), volumes.tolist() if len(volumes) == len(closes) else None, fwd_days=5, step=5, lookback=100)
            except Exception as bte:
                logger.warning(f"Backtest IC failed for {symbol}: {bte}")

        return {
            "symbol": symbol,
            "currentPrice": round(latest_close, 2),
            "quantScore": round(score, 1),
            "pivots": pivots,
            "bollingerSqueeze": squeeze,
            "hurstRegime": hurst,
            "kalmanState": kalman,
            "monteCarloRisk": var_risk,
            "orderFlowOBI": obi,
            "relativeVolumeRVOL": round(rvol, 2),
            "signalBacktest": backtest
        }
    except Exception as e:
        logger.error(f"Error computing quant deck for {symbol}: {e}")
        return {"error": str(e)}


if __name__ == "__main__":  # offline sanity check of the fixed math
    _rng = np.random.default_rng(0)
    _n = 300
    # low-noise uptrend (drift dominates) → Kalman slope must read positive
    _closes = 100 * np.exp(np.cumsum(_rng.normal(0.004, 0.0015, _n)))
    _ohlcv = {
        "close": _closes.tolist(),
        "high": (_closes * 1.01).tolist(),
        "low": (_closes * 0.99).tolist(),
        "volume": (_rng.random(_n) * 1e6).tolist(),
    }
    deck = compute_complete_quant_deck("TEST", _ohlcv)
    assert 5 <= deck["quantScore"] <= 95, deck
    assert deck["kalmanState"]["kalmanVelocity"] > 0, deck["kalmanState"]   # uptrend → positive slope
    _mc = deck["monteCarloRisk"]
    # drift-independent VaR invariants: deeper percentile is worse, and CVaR ≤ VaR
    assert _mc["var99Pct"] <= _mc["var95Pct"] and _mc["cvar95Pct"] <= _mc["var95Pct"], _mc
    assert np.isfinite(_mc["var95Pct"]), _mc
    assert compute_complete_quant_deck("TEST", _ohlcv)["monteCarloRisk"] == _mc, "VaR must be deterministic"
    print("ok  score=%.1f  hurst=%.3f (%s)  vel=%.4f  var95=%.2f%%" % (
        deck["quantScore"], deck["hurstRegime"]["hurst"], deck["hurstRegime"]["regime"],
        deck["kalmanState"]["kalmanVelocity"], _mc["var95Pct"]))

    # Backtest IC: alternating 60-day trend regimes (drift flips sign) → a momentum-
    # following quantScore must show clearly positive predictive IC + hitRate>0.5.
    # A pure random walk would give IC ~0; this validates the no-look-ahead machinery.
    _drift = np.where((np.arange(900) // 60) % 2 == 0, 0.005, -0.005)
    _reg_closes = (100 * np.exp(np.cumsum(_drift + _rng.normal(0, 0.004, 900)))).tolist()
    _bt = backtest_signal_ic(_reg_closes, fwd_days=5, lookback=80)
    assert _bt["available"] and _bt["samples"] >= 10, _bt
    assert _bt["ic"] > 0 and _bt["hitRate"] > 0.5, _bt   # trend regimes → score has real edge
    print("backtest  ic=%.4f  hitRate=%.3f  n=%d" % (_bt["ic"], _bt["hitRate"], _bt["samples"]))
