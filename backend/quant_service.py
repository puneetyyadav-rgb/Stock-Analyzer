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


def calculate_hurst_exponent(returns: np.ndarray) -> Dict[str, Any]:
    """
    Computes Hurst Exponent (H) via pure numpy variance scaling.
    Classifies regime into Mean-Reverting (<0.45), Random Walk (~0.50), or Trending (>0.55).
    """
    try:
        clean_returns = returns[~np.isnan(returns)]
        if len(clean_returns) < 60:
            return {"hurst": 0.50, "regime": "Insufficient Data"}
        
        lags = [2, 4, 8, 16, 32]
        tau = []
        for lag in lags:
            if lag >= len(clean_returns):
                continue
            # Calculate standard deviation of lagged differences
            diffs = clean_returns[lag:] - clean_returns[:-lag]
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
    Adaptive 1D Kalman Filter state smoother implemented in bare-metal numpy.
    Dynamically scales process noise (Q) and measurement noise (R) from rolling variance.
    """
    try:
        n = len(closes)
        if n < 20:
            return {"smoothedPrice": float(closes[-1]) if n > 0 else 0.0, "trendOverlay": "Unknown"}
            
        x_est = float(closes[0])
        p_est = 1.0
        
        smoothed = np.zeros(n)
        smoothed[0] = x_est
        
        # Rolling variance calculation for adaptive Q and R
        for i in range(1, n):
            window = closes[max(0, i - 20):i]
            roll_var = float(np.var(window)) if len(window) > 1 else 1.0
            
            # Adaptive noise scaling
            q = roll_var * 0.01  # Process noise
            r = roll_var * 0.50  # Measurement noise
            
            # Prediction step
            x_pred = x_est
            p_pred = p_est + q
            
            # Update step
            k_gain = p_pred / (p_pred + r) if (p_pred + r) > 0 else 0.5
            x_est = x_pred + k_gain * (closes[i] - x_pred)
            p_est = (1.0 - k_gain) * p_pred
            
            smoothed[i] = x_est
            
        latest_smoothed = float(smoothed[-1])
        prev_smoothed = float(smoothed[-5]) if n >= 5 else float(smoothed[0])
        
        trend = "Bullish Kalman State" if latest_smoothed > prev_smoothed else "Bearish Kalman State"
        
        return {
            "smoothedPrice": round(latest_smoothed, 2),
            "kalmanTrend": trend,
            "noiseDivergence": round(float(closes[-1]) - latest_smoothed, 2)
        }
    except Exception as e:
        logger.error(f"Error calculating Kalman Filter: {e}")
        return {"smoothedPrice": 0.0, "kalmanTrend": "Error", "noiseDivergence": 0.0}


def calculate_fat_tail_var(returns: np.ndarray, portfolio_val: float = 100000.0, horizon_days: int = 10) -> Dict[str, Any]:
    """
    Empirical Bootstrap Monte Carlo simulation (1,000 paths over 10 days).
    Samples directly from empirical returns to capture realistic fat tails (market crashes).
    Outputs 95% and 99% Value at Risk (VaR) and Expected Shortfall (CVaR).
    """
    try:
        clean_returns = returns[~np.isnan(returns)]
        if len(clean_returns) < 30:
            return {"var95Pct": 0.0, "var99Pct": 0.0, "cvar95Pct": 0.0, "var95Cash": 0.0}
            
        num_sims = 1000
        # Bootstrap resampling: shape (1000, horizon_days)
        random_paths = np.random.choice(clean_returns, size=(num_sims, horizon_days), replace=True)
        
        # Compound returns across the horizon
        cumulative_returns = np.prod(1.0 + random_paths, axis=1) - 1.0
        
        # Calculate empirical percentiles
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
        
        # Calculate daily log returns
        returns = np.diff(np.log(closes[closes > 0])) if len(closes) > 1 else np.array([])
        
        pivots = calculate_fibonacci_pivots(latest_high, latest_low, latest_close)
        squeeze = calculate_bollinger_squeeze(closes, highs, lows)
        hurst = calculate_hurst_exponent(returns)
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
            score += 10.0 if score > 50 else -10.0
            
        if obi.get("obiRatio", 0) > 0.20:
            score += 15.0
        elif obi.get("obiRatio", 0) < -0.20:
            score -= 15.0
            
        if rvol > 1.5 and score > 50:
            score += 10.0
            
        score = max(5.0, min(95.0, score))
        
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
            "relativeVolumeRVOL": round(rvol, 2)
        }
    except Exception as e:
        logger.error(f"Error computing quant deck for {symbol}: {e}")
        return {"error": str(e)}
