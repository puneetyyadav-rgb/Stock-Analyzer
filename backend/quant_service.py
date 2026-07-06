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
            
        # Fit log(lags) vs log(tau); cov gives the slope's standard error → an honest CI
        log_lags = np.log(lags[:len(tau)])
        log_tau = np.log(tau)
        if len(tau) >= 4:
            poly, cov = np.polyfit(log_lags, log_tau, 1, cov=True)
            std_err = float(np.sqrt(max(cov[0, 0], 0.0)))
        else:
            poly = np.polyfit(log_lags, log_tau, 1)
            std_err = 0.10  # too few lags to estimate dispersion → treat as noisy
        hurst = float(poly[0])
        hurst = max(0.05, min(0.95, hurst))   # clamp

        # Adaptive dead-band: only assign a regime if H is at least ~1 SE (floor 0.05) clear of
        # 0.5, so a noisy H≈0.5 stops flip-flopping between Trending/Mean-Reverting each refresh.
        margin = max(0.05, std_err)
        regime = "Random Walk (No Edge)"
        if hurst < 0.5 - margin:
            regime = "Mean-Reverting (Anti-Persistent)"
        elif hurst > 0.5 + margin:
            regime = "Trending (Momentum Persistence)"

        return {
            "hurst": round(hurst, 3),
            "regime": regime,
            "stdErr": round(std_err, 3),
            "ci95": round(1.96 * std_err, 3),
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


def _tf_close_array(values) -> np.ndarray:
    try:
        arr = np.asarray([] if values is None else values, dtype=float)
        return arr[np.isfinite(arr)]
    except Exception:
        return np.array([], dtype=float)


def _timeframe_state(name: str, closes) -> Dict[str, Any]:
    arr = _tf_close_array(closes)
    if len(arr) < 20:
        return {"timeframe": name, "available": False, "reason": "insufficient bars"}
    kalman = calculate_adaptive_kalman_1d(arr)
    pos = arr[arr > 0]
    hurst = calculate_hurst_exponent(np.log(pos)) if len(pos) >= 2 else {"hurst": 0.50, "regime": "Insufficient Data"}
    velocity = float(kalman.get("kalmanVelocity") or 0.0)
    noise = float(np.std(np.diff(arr[-20:]))) if len(arr) >= 21 else 0.0
    deadband = max(noise * 0.03, 1e-9)
    if velocity > deadband:
        direction = "bullish"
    elif velocity < -deadband:
        direction = "bearish"
    else:
        direction = "neutral"
    return {
        "timeframe": name,
        "available": True,
        "bars": int(len(arr)),
        "direction": direction,
        "kalmanVelocity": round(velocity, 4),
        "kalmanTrend": kalman.get("kalmanTrend"),
        "hurst": hurst.get("hurst"),
        "hurstRegime": hurst.get("regime"),
    }


def timeframe_confirmation(daily, h1=None, m15=None) -> Dict[str, Any]:
    """
    Weighted agreement across daily / 60m / 15m trends.
    Score is conviction, not direction: 100 means the available timeframes agree,
    50 means mixed or neutral, and unavailable means no multiplier should be applied.
    """
    weights = {"daily": 0.5, "60m": 0.3, "15m": 0.2}
    states = {
        "daily": _timeframe_state("daily", daily),
        "60m": _timeframe_state("60m", h1),
        "15m": _timeframe_state("15m", m15),
    }
    available = [s for s in states.values() if s.get("available")]
    directional = [s for s in available if s.get("direction") in ("bullish", "bearish")]
    if len(directional) < 2:
        return {
            "available": False,
            "confirmationScore": 50.0,
            "convictionMultiplier": 1.0,
            "label": "insufficient multi-timeframe data",
            "states": states,
        }

    bull_w = sum(weights[s["timeframe"]] for s in directional if s["direction"] == "bullish")
    bear_w = sum(weights[s["timeframe"]] for s in directional if s["direction"] == "bearish")
    used_w = bull_w + bear_w
    dominant_w = max(bull_w, bear_w)
    opposing_w = min(bull_w, bear_w)
    direction = "bullish" if bull_w > bear_w else "bearish" if bear_w > bull_w else "mixed"
    aligned_count = sum(1 for s in directional if s["direction"] == direction) if direction != "mixed" else 0
    total_count = len(directional)
    agreement = (dominant_w - opposing_w) / used_w if used_w else 0.0
    score = 50.0 + 50.0 * agreement
    if direction == "mixed":
        score = 50.0
        label = "conflicting timeframes"
    elif aligned_count == total_count:
        label = f"{total_count}/{total_count} aligned {direction}"
    else:
        label = f"{aligned_count}/{total_count} aligned {direction}"

    return {
        "available": True,
        "confirmationScore": round(float(np.clip(score, 50.0, 100.0)), 1),
        "convictionMultiplier": round(float(np.clip(score / 100.0, 0.5, 1.0)), 3),
        "direction": direction,
        "label": label,
        "states": states,
    }


def _ewma_vol(returns: np.ndarray, lam: float = 0.94) -> np.ndarray:
    """RiskMetrics EWMA per-step volatility series σ_t. Deterministic; σ_t depends only on the past."""
    var = np.empty(len(returns))
    var[0] = returns[0] ** 2
    for i in range(1, len(returns)):
        var[i] = lam * var[i - 1] + (1.0 - lam) * returns[i - 1] ** 2
    return np.sqrt(np.maximum(var, 1e-12))


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

        # Volatility-adjusted historical simulation (Hull-White): re-anchor every past return to
        # TODAY's EWMA vol, so the tail reflects the CURRENT regime — not a now-calm stock's
        # year-old crash — while block sampling still preserves clustering. Ratio clipped so a
        # tiny early-sample σ can't blow up a return.
        ewv = _ewma_vol(clean_returns)
        adj_returns = clean_returns * np.clip(ewv[-1] / ewv, 0.25, 4.0)

        rng = np.random.default_rng(12345)
        num_sims = 10000
        block = 5  # ponytail: fixed 5-day blocks; switch to stationary bootstrap if regimes vary widely
        n = len(adj_returns)
        n_blocks = -(-horizon_days // block)  # ceil

        # Build (num_sims, horizon) paths from contiguous wrapped blocks → preserves clustering
        starts = rng.integers(0, n, size=(num_sims, n_blocks))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
        idx = idx.reshape(num_sims, n_blocks * block)[:, :horizon_days]
        paths = adj_returns[idx]

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
            "horizonDays": horizon_days,
            "currentVolPct": round(float(ewv[-1]) * 100.0, 2),
            "volAdjusted": True
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
        }, skip_montecarlo=True)   # IC needs only the score; VaR doesn't feed it → skip 10k sims/step
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


def _score_forward_pairs(px: np.ndarray, volumes: Optional[np.ndarray], start: int, stop: int,
                         lookback: int, fwd_days: int, step: int) -> tuple:
    scores, fwd = [], []
    last_t = min(stop, len(px) - fwd_days)
    for t in range(max(start, lookback), last_t, step):
        win = px[t - lookback:t]
        if len(win) < 20:
            continue
        deck = compute_complete_quant_deck("WF", {
            "close": win.tolist(),
            "high": win.tolist(),
            "low": win.tolist(),
            "volume": volumes[t - lookback:t].tolist() if volumes is not None and len(volumes) >= t else [],
        }, skip_montecarlo=True)
        score = deck.get("quantScore")
        if score is None:
            continue
        ret = px[t + fwd_days] / px[t] - 1.0 if px[t] else np.nan
        if np.isfinite(ret):
            scores.append(float(score))
            fwd.append(float(ret))
    return np.asarray(scores, dtype=float), np.asarray(fwd, dtype=float)


def _ic_summary(scores: np.ndarray, fwd: np.ndarray) -> Dict[str, Any]:
    if len(scores) < 5 or len(fwd) < 5:
        return {"available": False, "samples": int(min(len(scores), len(fwd)))}
    return {
        "available": True,
        "ic": round(_rank_corr(scores, fwd), 4),
        "hitRate": round(float(np.mean((scores > 50) == (fwd > 0))), 3),
        "samples": int(len(scores)),
    }


def walk_forward_validate(closes: List[float], volumes: Optional[List[float]] = None,
                          train: int = 252, test: int = 42, step: int = 42,
                          fwd_days: int = 5) -> Dict[str, Any]:
    """
    Out-of-sample validation for the quant deck score.
    Each window estimates score/return behavior on a train slice, then scores only
    holdout bars for OOS IC and hit rate. A large IS-minus-OOS gap is overfit risk.
    """
    px = np.asarray(closes, dtype=float)
    px = px[np.isfinite(px)]
    if len(px) < train + test + fwd_days:
        return {"available": False, "reason": "insufficient history", "bars": int(len(px))}

    vol = None
    if volumes is not None:
        raw_vol = np.asarray(volumes, dtype=float)
        if len(raw_vol) == len(closes):
            vol = raw_vol[np.isfinite(np.asarray(closes, dtype=float))]

    lookback = min(120, max(60, train // 2))
    windows = []
    for start in range(0, len(px) - train - test - fwd_days + 1, step):
        train_end = start + train
        test_end = train_end + test
        is_scores, is_fwd = _score_forward_pairs(px, vol, start + lookback, train_end, lookback, fwd_days, max(1, fwd_days))
        oos_scores, oos_fwd = _score_forward_pairs(px, vol, train_end, test_end, lookback, fwd_days, max(1, fwd_days))
        is_summary = _ic_summary(is_scores, is_fwd)
        oos_summary = _ic_summary(oos_scores, oos_fwd)
        if not oos_summary.get("available"):
            continue
        windows.append({
            "trainStart": int(start),
            "trainEnd": int(train_end - 1),
            "testStart": int(train_end),
            "testEnd": int(test_end - 1),
            "inSampleIC": is_summary.get("ic"),
            "inSampleHitRate": is_summary.get("hitRate"),
            "inSampleSamples": is_summary.get("samples", 0),
            "oosIC": oos_summary.get("ic"),
            "oosHitRate": oos_summary.get("hitRate"),
            "oosSamples": oos_summary.get("samples", 0),
        })

    if not windows:
        return {"available": False, "reason": "too few holdout samples", "bars": int(len(px))}

    is_vals = [w["inSampleIC"] for w in windows if w.get("inSampleIC") is not None]
    oos_vals = [w["oosIC"] for w in windows if w.get("oosIC") is not None]
    mean_is = float(np.mean(is_vals)) if is_vals else None
    mean_oos = float(np.mean(oos_vals)) if oos_vals else None
    decay = (mean_is - mean_oos) if mean_is is not None and mean_oos is not None else None
    return {
        "available": True,
        "trainBars": int(train),
        "testBars": int(test),
        "stepBars": int(step),
        "fwdDays": int(fwd_days),
        "lookbackBars": int(lookback),
        "windows": windows,
        "meanIS_IC": round(mean_is, 4) if mean_is is not None else None,
        "meanOOS_IC": round(mean_oos, 4) if mean_oos is not None else None,
        "meanOOSHitRate": round(float(np.mean([w["oosHitRate"] for w in windows])), 3),
        "isMinusOosDecay": round(float(decay), 4) if decay is not None else None,
        "overfitWarning": bool(decay is not None and mean_is is not None and decay > max(0.05, abs(mean_is) * 0.5)),
        "samples": int(sum(w["oosSamples"] for w in windows)),
    }


def cross_sectional_rank(symbol: str, universe_df) -> Dict[str, Any]:
    """
    Percentile-rank this name's single-day factors against the WHOLE NSE universe (bhavcopy).
    A desk reads relative, not absolute: 80%ile delivery means more than "55% delivery". Pure
    numpy on the passed DataFrame (no pandas import here). composite = accumulation+strength read.
    """
    clean = symbol.replace(".NS", "").replace(".BO", "").upper()
    try:
        if universe_df is None or clean not in universe_df.index:
            return {"available": False}

        def pctile(col: str) -> Optional[float]:
            vals = np.asarray(universe_df[col].values, dtype=float)
            vals = vals[np.isfinite(vals)]
            v = float(universe_df.loc[clean, col])
            if not np.isfinite(v) or len(vals) == 0:
                return None
            return round(float((vals < v).mean()) * 100.0, 1)

        deliv = pctile("delivPct")
        turn = pctile("turnover")
        rng_ = pctile("rangePct")
        ret = pctile("oneDayRet")
        # composite: delivery (quality) + turnover (institutional liquidity) + 1-day strength
        parts = [p for p in (deliv, turn, ret) if p is not None]
        composite = round(float(np.mean(parts)), 1) if parts else None
        return {
            "available": True,
            "deliveryPctile": deliv,
            "turnoverPctile": turn,
            "rangePctile": rng_,
            "oneDayRetPctile": ret,
            "composite": composite,
            "universeSize": int(len(universe_df)),
        }
    except Exception as e:
        logger.error(f"Error in cross-sectional rank for {symbol}: {e}")
        return {"available": False}


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def _composite_score(kalman: Dict[str, Any], hurst: Dict[str, Any], obi: Dict[str, Any],
                     rvol: float, squeeze: Dict[str, Any], delivery: Optional[Dict[str, Any]],
                     cross_sectional: Optional[Dict[str, Any]], latest_close: float,
                     has_depth: bool) -> tuple:
    """
    Regime-conditional factor model → 0-100. Each factor is a signed strength in ~[-1,1]; weights
    shift with the Hurst regime; RVOL is a symmetric conviction multiplier; logistic squash maps to
    a score. Missing factors (no depth/bhavcopy, e.g. in the backtest) drop out and the remaining
    weights renormalize — they do NOT silently bias the score toward neutral. Returns (score, factors).
    """
    f: Dict[str, float] = {}

    # Momentum — Kalman velocity, vol-normalized by ATR; tanh gives a built-in dead-band
    vel = kalman.get("kalmanVelocity")
    scale = max(float(squeeze.get("atr14") or 0.0), 1e-9)
    if vel is not None and latest_close:
        f["momentum"] = float(np.tanh(vel / (0.5 * scale)))

    # Mean-reversion — price stretch vs the SMA20 band → expect snap-back (only weighted in MR regime)
    sma20, upper, lower = squeeze.get("sma20"), squeeze.get("upperBand"), squeeze.get("lowerBand")
    if sma20 and upper and lower and upper > lower and latest_close:
        z = (latest_close - sma20) / ((upper - lower) / 2.0)
        f["meanrev"] = float(np.clip(-z, -1.0, 1.0))

    # Order-flow imbalance (already [-1,1]) — only when real Level-2 depth was supplied
    if has_depth and obi.get("obiRatio") is not None:
        f["obi"] = float(np.clip(obi["obiRatio"], -1.0, 1.0))

    # Delivery quality — high delivery % = real ownership transfer, not intraday churn
    if delivery and delivery.get("available") and delivery.get("deliveryPercentage") is not None:
        f["delivery"] = float(np.clip((delivery["deliveryPercentage"] - 50.0) / 30.0, -1.0, 1.0))

    # Cross-sectional standing vs the whole market
    if cross_sectional and cross_sectional.get("available") and cross_sectional.get("composite") is not None:
        f["crosssec"] = float(np.clip((cross_sectional["composite"] - 50.0) / 50.0, -1.0, 1.0))

    # meanrev is ONLY weighted in the Mean-Reverting regime — that's the only regime where fading a
    # stretch has statistical edge. Note Hurst variance-scaling can't see drift (it reads the noise
    # structure), so a drift-up stock often lands in Random Walk; there we ride momentum (which DOES
    # see the drift) + flow + quality, and never short the stretch.
    regime = hurst.get("regime", "")
    if regime.startswith("Trending"):
        W = {"momentum": 0.45, "obi": 0.22, "crosssec": 0.20, "delivery": 0.13}
    elif regime.startswith("Mean-Reverting"):
        W = {"momentum": 0.12, "obi": 0.25, "crosssec": 0.13, "delivery": 0.10, "meanrev": 0.40}
    else:                                        # random walk / unknown → momentum + flow + quality
        W = {"momentum": 0.34, "obi": 0.28, "crosssec": 0.20, "delivery": 0.18}

    used = {k: W[k] for k in f if k in W}
    wsum = sum(used.values()) or 1.0
    signal = sum(f[k] * used[k] for k in used) / wsum        # weighted mean of available factors ~[-1,1]

    # RVOL = symmetric conviction multiplier: thin participation pulls the read toward neutral 50
    conf = float(np.clip(0.6 + 0.4 * rvol, 0.6, 1.6))
    signal = float(np.clip(signal * conf, -1.5, 1.5))

    score = float(np.clip(100.0 * _logistic(3.0 * signal), 2.0, 98.0))
    return round(score, 1), {k: round(v, 3) for k, v in f.items()}


def compute_complete_quant_deck(symbol: str, ohlcv: Dict[str, List[float]], kotak_depth: Optional[Dict[str, Any]] = None,
                                delivery: Optional[Dict[str, Any]] = None, cross_sectional: Optional[Dict[str, Any]] = None,
                                skip_montecarlo: bool = False,
                                timeframes: Optional[Dict[str, List[float]]] = None,
                                market_regime: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Master quantitative aggregator feeding the AI prompt and UI dashboard."""
    try:
        closes = np.array(ohlcv.get("close", []), dtype=float)   # RAW prices → levels/pivots/bands/RVOL
        highs = np.array(ohlcv.get("high", []), dtype=float)
        lows = np.array(ohlcv.get("low", []), dtype=float)
        volumes = np.array(ohlcv.get("volume", []), dtype=float)
        # Adjusted (total-return) closes → return-based stats only; falls back to raw if not supplied
        adj = np.array(ohlcv.get("adj_close", ohlcv.get("close", [])), dtype=float)

        if len(closes) < 5:
            return {"status": "Insufficient Data"}

        latest_close = float(closes[-1])
        latest_high = float(highs[-1])
        latest_low = float(lows[-1])

        # Log-price level series (for Hurst) + daily log returns (for VaR) — both on the ADJUSTED series
        pos = adj[adj > 0]
        log_prices = np.log(pos) if len(pos) > 1 else np.array([])
        returns = np.diff(log_prices) if len(log_prices) > 1 else np.array([])

        pivots = calculate_fibonacci_pivots(latest_high, latest_low, latest_close)
        squeeze = calculate_bollinger_squeeze(closes, highs, lows)
        hurst = calculate_hurst_exponent(log_prices)
        kalman = calculate_adaptive_kalman_1d(closes)
        var_risk = {"skipped": True} if skip_montecarlo else calculate_fat_tail_var(returns)

        # Calculate Relative Volume (RVOL)
        rvol = 1.0
        if len(volumes) >= 20:
            avg_vol = float(np.mean(volumes[-20:]))
            rvol = float(volumes[-1]) / avg_vol if avg_vol > 0 else 1.0
            
        # Extract OBI from Kotak depth — prefer the exchange's FULL-book totals over the 5 visible levels
        bid_qty = 0.0
        ask_qty = 0.0
        has_depth = False
        if kotak_depth and isinstance(kotak_depth, dict):
            bid_qty = float(kotak_depth.get("totalBidQty") or 0.0)
            ask_qty = float(kotak_depth.get("totalAskQty") or 0.0)
            if bid_qty <= 0 and ask_qty <= 0:        # fall back to summing the visible levels
                bids = kotak_depth.get("bids", [])
                asks = kotak_depth.get("asks", [])
                bid_qty = sum(float(b.get("quantity", 0)) for b in bids if isinstance(b, dict))
                ask_qty = sum(float(a.get("quantity", 0)) for a in asks if isinstance(a, dict))
            has_depth = (bid_qty + ask_qty) > 0

        obi = calculate_microstructure_obi(bid_qty, ask_qty)

        # Institutional Quant Score (0-100): regime-conditional factor model, RVOL conviction, logistic squash
        score, score_factors = _composite_score(kalman, hurst, obi, rvol, squeeze,
                                                 delivery, cross_sectional, latest_close, has_depth)
        raw_score = score
        tf_confirmation = {"available": False}
        if timeframes:
            tf_confirmation = timeframe_confirmation(
                timeframes.get("daily") or closes.tolist(),
                timeframes.get("60m") or timeframes.get("h1"),
                timeframes.get("15m") or timeframes.get("m15"),
            )
            if tf_confirmation.get("available"):
                mult = float(tf_confirmation.get("convictionMultiplier") or 1.0)
                score = round(float(np.clip(50.0 + (score - 50.0) * mult, 2.0, 98.0)), 1)

        backtest = {"available": False}
        if symbol != "BT" and len(closes) >= 80:
            try:
                backtest = backtest_signal_ic(closes.tolist(), volumes.tolist() if len(volumes) == len(closes) else None, fwd_days=5, step=5, lookback=60)
            except Exception as bte:
                logger.warning(f"Backtest IC failed for {symbol}: {bte}")

        return {
            "symbol": symbol,
            "currentPrice": round(latest_close, 2),
            "quantScore": round(score, 1),
            "rawQuantScore": round(raw_score, 1),
            "scoreFactors": score_factors,
            "timeframeConfirmation": tf_confirmation,
            "pivots": pivots,
            "bollingerSqueeze": squeeze,
            "hurstRegime": hurst,
            "kalmanState": kalman,
            "monteCarloRisk": var_risk,
            "orderFlowOBI": obi,
            "relativeVolumeRVOL": round(rvol, 2),
            "deliverySignal": delivery,
            "crossSectional": cross_sectional,
            "signalBacktest": backtest,
            "marketRegime": market_regime
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
    assert 0 <= deck["quantScore"] <= 100, deck
    assert deck["quantScore"] > 55, ("uptrend must read bullish", deck["quantScore"], deck["scoreFactors"])
    assert deck["kalmanState"]["kalmanVelocity"] > 0, deck["kalmanState"]   # uptrend → positive slope
    assert deck["hurstRegime"]["ci95"] >= 0, deck["hurstRegime"]            # Hurst now reports a CI
    _mc = deck["monteCarloRisk"]
    # drift-independent VaR invariants: deeper percentile is worse, and CVaR ≤ VaR
    assert _mc["var99Pct"] <= _mc["var95Pct"] and _mc["cvar95Pct"] <= _mc["var95Pct"], _mc
    assert np.isfinite(_mc["var95Pct"]) and _mc["volAdjusted"] and _mc["currentVolPct"] > 0, _mc
    assert compute_complete_quant_deck("TEST", _ohlcv)["monteCarloRisk"] == _mc, "VaR must be deterministic"
    assert compute_complete_quant_deck("TEST", _ohlcv, skip_montecarlo=True)["monteCarloRisk"] == {"skipped": True}
    print("ok  score=%.1f  hurst=%.3f±%.3f (%s)  vel=%.4f  var95=%.2f%%  vol=%.2f%%" % (
        deck["quantScore"], deck["hurstRegime"]["hurst"], deck["hurstRegime"]["ci95"],
        deck["hurstRegime"]["regime"], deck["kalmanState"]["kalmanVelocity"],
        _mc["var95Pct"], _mc["currentVolPct"]))

    # Cross-sectional rank on a tiny synthetic universe → percentiles bounded, missing name → unavailable
    import pandas as _pd
    _uni = _pd.DataFrame({
        "delivPct":  [10, 30, 55, 90],
        "turnover":  [5,  50, 200, 1000],
        "rangePct":  [1,  2,  3,   4],
        "oneDayRet": [-2, 0,  1,   3],
    }, index=["A", "B", "TEST", "Z"])
    _cs = cross_sectional_rank("TEST.NS", _uni)
    assert _cs["available"] and 0 <= _cs["composite"] <= 100, _cs
    assert _cs["deliveryPctile"] == 50.0, _cs                          # 2 of 4 names below 55 → 50th pctile
    assert cross_sectional_rank("NOPE.NS", _uni)["available"] is False
    # folding delivery + cross-sectional into the deck score must not error and stays in range
    _deck2 = compute_complete_quant_deck("TEST", _ohlcv,
                                         delivery={"available": True, "deliveryPercentage": 85.0},
                                         cross_sectional=_cs)
    assert 0 <= _deck2["quantScore"] <= 100 and _deck2["deliverySignal"]["deliveryPercentage"] == 85.0, _deck2
    print("cross-sectional  composite=%.1f  deliveryPctile=%.1f  score(+factors)=%.1f" % (
        _cs["composite"], _cs["deliveryPctile"], _deck2["quantScore"]))

    # Backtest IC: alternating 60-day trend regimes (drift flips sign) → a momentum-
    # following quantScore must show clearly positive predictive IC + hitRate>0.5.
    # A pure random walk would give IC ~0; this validates the no-look-ahead machinery.
    _drift = np.where((np.arange(900) // 60) % 2 == 0, 0.005, -0.005)
    _reg_closes = (100 * np.exp(np.cumsum(_drift + _rng.normal(0, 0.004, 900)))).tolist()
    _bt = backtest_signal_ic(_reg_closes, fwd_days=5, lookback=80)
    assert _bt["available"] and _bt["samples"] >= 10, _bt
    assert _bt["ic"] > 0 and _bt["hitRate"] > 0.5, _bt   # trend regimes → score has real edge
    print("backtest  ic=%.4f  hitRate=%.3f  n=%d" % (_bt["ic"], _bt["hitRate"], _bt["samples"]))

    _aligned = timeframe_confirmation(_closes, _closes[-140:], _closes[-120:])
    assert _aligned["available"] and _aligned["confirmationScore"] >= 95, _aligned
    _conflict = timeframe_confirmation(_closes, _closes[-140:][::-1], _closes[-120:])
    assert _conflict["available"] and _conflict["confirmationScore"] < _aligned["confirmationScore"], _conflict
    _tf_deck = compute_complete_quant_deck("TEST", _ohlcv,
                                           timeframes={"daily": _closes.tolist(),
                                                       "60m": _closes[-140:][::-1].tolist(),
                                                       "15m": _closes[-120:].tolist()},
                                           skip_montecarlo=True)
    assert _tf_deck["quantScore"] <= _tf_deck["rawQuantScore"], _tf_deck
    print("timeframes  aligned=%.1f  conflict=%.1f  adjustedScore=%.1f raw=%.1f" % (
        _aligned["confirmationScore"], _conflict["confirmationScore"],
        _tf_deck["quantScore"], _tf_deck["rawQuantScore"]))

    _wf = walk_forward_validate(_reg_closes, train=180, test=45, step=45, fwd_days=5)
    assert _wf["available"] and _wf["samples"] > 0 and _wf["meanOOS_IC"] is not None, _wf
    _noise = (100 * np.exp(np.cumsum(_rng.normal(0, 0.01, 700)))).tolist()
    _wf_noise = walk_forward_validate(_noise, train=180, test=45, step=45, fwd_days=5)
    assert _wf_noise["available"], _wf_noise
    assert abs(_wf_noise["meanOOS_IC"]) < 0.5, _wf_noise
    print("walk-forward  oosIC=%.4f  hitRate=%.3f  decay=%s  noiseOOS=%.4f" % (
        _wf["meanOOS_IC"], _wf["meanOOSHitRate"], _wf["isMinusOosDecay"], _wf_noise["meanOOS_IC"]))
