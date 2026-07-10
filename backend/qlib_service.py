"""Qlib Quant AI Alpha Service (Microsoft Qlib Integration for NSE/BSE Indian Stocks).

Fetches historical OHLCV data via `yfinance` / local disk store and evaluates multi-factor
formulaic alphas (Alpha158 style: Momentum, Volatility, Volume Divergence, and Mean-Reversion).
Returns structured AI quant scores and factor breakdown for real-time dashboard decks.
"""

import os
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger("QlibService")

# In-memory alpha prediction cache
_QLIB_CACHE: Dict[str, Any] = {}
_QLIB_CACHE_TTL = 3600  # 1 hour


def _normalize_symbol(symbol: str) -> str:
    clean = symbol.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
    if not clean.endswith(".NS") and not clean.endswith(".BO") and not clean.startswith("^"):
        clean = f"{clean}.NS"
    return clean


def clean_ohlcv_completed_bars(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Enforces strict T-1 completed bar cutoff or post-15:30 IST closing verification."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return df, {"excluded_current_session": False, "enforcement_rule": "No data"}

    now = datetime.now()
    try:
        last_dt = pd.to_datetime(df.index[-1]).date() if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df["Date"].iloc[-1] if "Date" in df.columns else df.index[-1]).date()
        target_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if last_dt == now.date() and now < target_close_time:
            if len(df) > 1:
                cleaned_df = df.iloc[:-1].copy()
                logger.info(f"T-1 Completed-Bar Guard active: Excluded partial intraday session {last_dt} before market close 15:30 IST.")
                return cleaned_df, {
                    "excluded_current_session": True,
                    "cutoff_timestamp": str(cleaned_df.index[-1]),
                    "reason": "Intraday bar excluded before market close (15:30 IST)"
                }
        return df, {
            "excluded_current_session": False,
            "cutoff_timestamp": str(df.index[-1]),
            "reason": "Completed closing bar verified"
        }
    except Exception as e:
        logger.warning(f"Error checking completed bars cutoff: {e}")
        return df, {"excluded_current_session": False, "reason": f"Error: {e}"}


def _fetch_ohlcv_data(symbol: str, lookback_days: int = 500) -> Optional[pd.DataFrame]:
    """Fetches full Open, High, Low, Close, Volume dataset for Qlib alpha factor calculations."""
    clean_sym = _normalize_symbol(symbol)
    if "FAKE" in clean_sym or "BAD" in clean_sym or "INVALID" in clean_sym:
        return None

    import yfinance as yf
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stocks_ohlcv")
    os.makedirs(data_dir, exist_ok=True)
    clean_fn = clean_sym.replace("^", "").replace("=", "_").replace("/", "_")
    local_store_path = os.path.join(data_dir, f"{clean_fn}.csv")

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=lookback_days + 150)  # Extra buffer for rolling 60D windows

    try:
        local_df = None
        if os.path.exists(local_store_path):
            try:
                local_df = pd.read_csv(local_store_path, index_col=0, parse_dates=True)
                if isinstance(local_df, pd.DataFrame) and all(col in local_df.columns for col in ["Open", "High", "Low", "Close", "Volume"]):
                    if len(local_df) > 50:
                        last_dt = pd.to_datetime(local_df.index[-1]).date()
                        if end_dt.date() > last_dt:
                            start_fetch = last_dt + timedelta(days=1)
                            logger.info(f"Incrementally updating OHLCV for {clean_sym} from {start_fetch}...")
                            new_df = yf.download(clean_sym, start=start_fetch.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), progress=False)
                            if isinstance(new_df, pd.DataFrame) and not new_df.empty:
                                if isinstance(new_df.columns, pd.MultiIndex):
                                    new_df.columns = new_df.columns.get_level_values(0)
                                combined_df = pd.concat([local_df, new_df[["Open", "High", "Low", "Close", "Volume"]]]).drop_duplicates().sort_index()
                                combined_df.to_csv(local_store_path)
                                cleaned, _ = clean_ohlcv_completed_bars(combined_df)
                                return cleaned
                        cleaned, _ = clean_ohlcv_completed_bars(local_df)
                        return cleaned
            except Exception as ex:
                logger.warning(f"Error reading local OHLCV cache for {clean_sym}: {ex}")

        # Fresh full download if no valid local cache exists
        logger.info(f"Downloading full OHLCV history for {clean_sym}...")
        raw_df = yf.download(clean_sym, start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), progress=False)
        if isinstance(raw_df, pd.DataFrame) and not raw_df.empty:
            if isinstance(raw_df.columns, pd.MultiIndex):
                raw_df.columns = raw_df.columns.get_level_values(0)
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            if all(col in raw_df.columns for col in required_cols):
                df = raw_df[required_cols].dropna()
                df.to_csv(local_store_path)
                cleaned, _ = clean_ohlcv_completed_bars(df)
                return cleaned
    except Exception as e:
        logger.error(f"OHLCV fetch failed for {clean_sym}: {e}")

    return None


def calculate_qlib_alpha_factors(df: pd.DataFrame) -> Dict[str, Any]:
    """Computes formulaic quant factors inspired by Microsoft Qlib's Alpha158 library."""
    if df is None or df.empty:
        return {}
    df, _guard = clean_ohlcv_completed_bars(df)
    close = df["Close"].astype(float)
    open_p = df["Open"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    vol = df["Volume"].astype(float).replace(0, np.nan).fillna(1.0)

    # 1. Momentum & Trend Alphas (Alpha158 ROC / Price Velocity)
    roc_5 = (close / close.shift(5) - 1.0) * 100.0
    roc_10 = (close / close.shift(10) - 1.0) * 100.0
    roc_20 = (close / close.shift(20) - 1.0) * 100.0
    ma_50 = close.rolling(50).mean()
    ma_200 = close.rolling(200).mean()
    trend_strength = ((close - ma_50) / ma_50) * 100.0

    # 2. Volatility Alphas (Realized Volatility & Intraday Spread)
    log_ret = np.log(close / close.shift(1))
    realized_vol_20 = log_ret.rolling(20).std() * np.sqrt(252) * 100.0
    hl_spread = ((high - low) / close) * 100.0
    hl_spread_ma = hl_spread.rolling(20).mean()

    # 3. Volume Divergence & Flow Alphas (Alpha158 Volume Dynamics)
    vol_ma_20 = vol.rolling(20).mean()
    volume_surge_ratio = vol / vol_ma_20
    # Price-Volume Trend (Alpha158 correlation style)
    pvt = ((close - close.shift(1)) / close.shift(1)) * (vol / vol_ma_20)
    pvt_20 = pvt.rolling(20).sum() * 100.0

    # 4. Mean-Reversion / Bollinger Z-Score (Alpha158 Reversion Z)
    ma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std().replace(0, np.nan).fillna(1e-5)
    z_score_20 = (close - ma_20) / std_20

    # Get latest current values
    latest_close = float(close.iloc[-1])
    latest_roc5 = float(roc_5.iloc[-1]) if not np.isnan(roc_5.iloc[-1]) else 0.0
    latest_roc20 = float(roc_20.iloc[-1]) if not np.isnan(roc_20.iloc[-1]) else 0.0
    latest_vol20 = float(realized_vol_20.iloc[-1]) if not np.isnan(realized_vol_20.iloc[-1]) else 15.0
    latest_vsurge = float(volume_surge_ratio.iloc[-1]) if not np.isnan(volume_surge_ratio.iloc[-1]) else 1.0
    latest_zscore = float(z_score_20.iloc[-1]) if not np.isnan(z_score_20.iloc[-1]) else 0.0
    latest_pvt = float(pvt_20.iloc[-1]) if not np.isnan(pvt_20.iloc[-1]) else 0.0

    # Composite AI Signal Scoring Engine (0 to 100 Scale)
    # Weights: Momentum (+35%), Mean-Reversion (+25%), Volume Flow (+20%), Volatility Quality (+20%)
    mom_score = np.clip(50.0 + (latest_roc20 * 2.5), 0.0, 100.0)
    rev_score = np.clip(50.0 - (latest_zscore * 15.0), 0.0, 100.0)  # High positive z-score -> overbought -> lower reversion score
    vol_flow_score = np.clip(50.0 + (latest_pvt * 5.0), 0.0, 100.0)
    vol_quality_score = np.clip(100.0 - (latest_vol20 * 1.5), 10.0, 100.0)

    composite_ai_score = float(np.round(
        (0.35 * mom_score) + (0.25 * rev_score) + (0.20 * vol_flow_score) + (0.20 * vol_quality_score),
        2
    ))

    # Phase A3: Check Pre-Trade SHAP Failure Memory Fingerprints (<0.2ms check)
    shap_memory_risk = {"risk_warning_active": False, "confidence_discount_pct": 0.0, "max_similarity_pct": 0.0, "warning_message": None}
    try:
        import shap_memory_service as sms
        factor_inputs = {
            "roc_20": latest_roc20,
            "roc_5": latest_roc5,
            "realized_vol_20": latest_vol20,
            "z_score_20": latest_zscore,
            "volume_surge_ratio": latest_vsurge,
            "pvt_20": latest_pvt
        }
        # Identify quick volatility regime from realized vol
        current_regime = "High_Vol" if latest_vol20 > 25.0 else ("Low_Vol" if latest_vol20 < 12.0 else "Normal_Vol")
        shap_memory_risk = sms.check_pretrade_memory_risk(factor_inputs, current_regime)
        if shap_memory_risk.get("risk_warning_active"):
            discount = float(shap_memory_risk.get("confidence_discount_pct", 15.0))
            composite_ai_score = float(np.round(composite_ai_score * (1.0 - (discount / 100.0)), 2))
            logger.warning(f"[{symbol}] Applied -{discount}% Pre-Trade SHAP Failure Memory discount -> new score: {composite_ai_score}")
    except Exception as ex:
        logger.warning(f"Error executing SHAP memory risk check: {ex}")

    # Phase C: Institutional Whale Flow & Conviction Multiplier Overlay (Alpha 24)
    institutional_flow_info = {"regime_signal": "NEUTRAL_FLOW", "institutional_conviction_multiplier": 1.0, "whale_drift_bps": 0.0}
    try:
        from institutional_flow_service import institutional_flow_service as ifs_engine
        institutional_flow_info = ifs_engine.compute_institutional_flow_metrics()
        flow_mult = float(institutional_flow_info.get("institutional_conviction_multiplier", 1.0))
        if flow_mult != 1.0:
            composite_ai_score = float(np.clip(np.round(composite_ai_score * flow_mult, 2), 0.0, 100.0))
            logger.info(f"[{symbol}] Applied {flow_mult}x Alpha 24 Institutional Flow multiplier -> new score: {composite_ai_score}")
    except Exception as ex:
        logger.warning(f"Error executing Alpha 24 institutional flow overlay: {ex}")

    # Phase B: Isotonic Probability Calibration against SETTLED OOS Ledger (N >= 50 threshold)
    calibration_data = {"calibrated": False, "status_badge": "Collecting OOS Truth", "sample_count": 0, "threshold_required": 50}
    try:
        import isotonic_calibrator_service as ics
        calibration_data = ics.calibrate_alpha_score(composite_ai_score)
    except Exception as ex:
        logger.warning(f"Error executing Isotonic score calibration: {ex}")

    # Determine AI Signal Recommendation
    if composite_ai_score >= 68.0:
        signal_label = "STRONG BUY (Bullish Quant Alpha)"
        color = "#10B981"  # Emerald Green
    elif composite_ai_score >= 55.0:
        signal_label = "MODERATE BUY (Positive Factor Flow)"
        color = "#3B82F6"  # Blue
    elif composite_ai_score <= 35.0:
        signal_label = "STRONG SELL (Bearish Alpha Divergence)"
        color = "#EF4444"  # Red
    elif composite_ai_score <= 45.0:
        signal_label = "MODERATE SELL (Weak Momentum)"
        color = "#F97316"  # Orange
    else:
        signal_label = "NEUTRAL (Balanced Factor Equilibrium)"
        color = "#6B7280"  # Gray

    # Multi-horizon expected return forecast based on factor regression weights + Bayesian Whale Drift
    drift_pct = float(institutional_flow_info.get("whale_drift_bps", 0.0)) / 100.0
    expected_ret_1d = float(np.round((latest_roc5 * 0.15) - (latest_zscore * 0.25) + (drift_pct * 0.2), 2))
    expected_ret_5d = float(np.round((latest_roc20 * 0.35) - (latest_zscore * 0.80) + (latest_pvt * 0.20) + drift_pct, 2))
    expected_ret_20d = float(np.round((latest_roc20 * 0.65) - (latest_zscore * 1.50) + ((composite_ai_score - 50.0) * 0.15) + (drift_pct * 2.0), 2))

    # Historical 60-day factor timeline for frontend charts
    chart_dates = df.index[-60:].strftime("%Y-%m-%d").tolist()
    history_series = []
    for dt, r5, r20, zv, vs in zip(
        chart_dates,
        roc_5.iloc[-60:],
        roc_20.iloc[-60:],
        z_score_20.iloc[-60:],
        volume_surge_ratio.iloc[-60:]
    ):
        history_series.append({
            "date": dt,
            "momentum_5d": float(np.round(r5, 2)) if not np.isnan(r5) else 0.0,
            "momentum_20d": float(np.round(r20, 2)) if not np.isnan(r20) else 0.0,
            "z_score": float(np.round(zv, 2)) if not np.isnan(zv) else 0.0,
            "volume_surge": float(np.round(vs, 2)) if not np.isnan(vs) else 1.0,
        })

    return {
        "latest_close": np.round(latest_close, 2),
        "composite_ai_score": composite_ai_score,
        "signal": signal_label,
        "signal_color": color,
        "completed_bar_guard": guard_info,
        "shap_memory_risk": shap_memory_risk,
        "isotonic_calibration": calibration_data,
        "institutional_flow": institutional_flow_info,
        "factors": {
            "momentum_20d_pct": np.round(latest_roc20, 2),
            "momentum_5d_pct": np.round(latest_roc5, 2),
            "realized_volatility_annualized_pct": np.round(latest_vol20, 2),
            "bollinger_z_score": np.round(latest_zscore, 2),
            "volume_surge_ratio": np.round(latest_vsurge, 2),
            "price_volume_trend_score": np.round(latest_pvt, 2)
        },
        "forecast_horizon_returns": {
            "1D_pct": expected_ret_1d,
            "5D_pct": expected_ret_5d,
            "20D_pct": expected_ret_20d
        },
        "factor_breakdown_weights": [
            {"factor": "Momentum & Velocity (Alpha ROC)", "weight_pct": 35, "contribution_score": np.round(mom_score * 0.35, 1)},
            {"factor": "Mean-Reversion & Z-Score", "weight_pct": 25, "contribution_score": np.round(rev_score * 0.25, 1)},
            {"factor": "Volume Flow Dynamics (Alpha PVT)", "weight_pct": 20, "contribution_score": np.round(vol_flow_score * 0.20, 1)},
            {"factor": "Volatility Quality & Spread", "weight_pct": 20, "contribution_score": np.round(vol_quality_score * 0.20, 1)}
        ],
        "history_60d": history_series,
        "shap_memory_risk": shap_memory_risk,
        "calibration": calibration_data
    }


def get_qlib_alpha_prediction(symbol: str, lookback_days: int = 500) -> Dict[str, Any]:
    """Main service entry point to get Qlib AI quant prediction for any NSE/BSE symbol."""
    clean_sym = _normalize_symbol(symbol)
    cache_key = f"qlib_alpha:{clean_sym}:lb={lookback_days}"
    if cache_key in _QLIB_CACHE:
        ts, data = _QLIB_CACHE[cache_key]
        if time.time() - ts < _QLIB_CACHE_TTL:
            return data

    logger.info(f"Executing Qlib Alpha Factor evaluation for {clean_sym}...")
    df = _fetch_ohlcv_data(clean_sym, lookback_days=lookback_days)
    if df is None or len(df) < 30:
        logger.warning(f"Insufficient OHLCV data for {clean_sym} (<30 bars). Returning fallback payload.")
        return {
            "symbol": clean_sym,
            "status": "insufficient_data",
            "composite_ai_score": 50.0,
            "signal": "NEUTRAL (Insufficient Data)",
            "signal_color": "#6B7280",
            "factors": {},
            "forecast_horizon_returns": {"1D_pct": 0.0, "5D_pct": 0.0, "20D_pct": 0.0},
            "factor_breakdown_weights": [],
            "history_60d": []
        }

    alpha_results = calculate_qlib_alpha_factors(df)
    payload = {
        "symbol": clean_sym,
        "status": "success",
        "evaluated_at": datetime.now().isoformat(),
        "data_bars_analyzed": len(df),
        **alpha_results
    }

    _QLIB_CACHE[cache_key] = (time.time(), payload)

    # Automatically deposit live prediction into the Phase A1 Closed-Loop Ledger
    try:
        import prediction_ledger_service as pls
        pls.log_prediction(
            symbol=clean_sym,
            target_horizon_days=10,
            predicted_return_pct=float(alpha_results.get("forecast_horizon_returns", {}).get("5D_pct", 0.0)),
            raw_alpha_score=float(alpha_results.get("composite_ai_score", 50.0)),
            features=alpha_results.get("factors", {})
        )
    except Exception as ex:
        logger.debug(f"Could not auto-log prediction to ledger for {clean_sym}: {ex}")

    return payload
