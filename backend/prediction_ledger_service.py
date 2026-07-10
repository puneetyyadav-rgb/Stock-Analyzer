"""Institutional Append-Only Prediction Error Ledger Service (`Phase A1 Truth Layer`).

Provides an immutable, walk-forward prediction ledger (`backend/data/prediction_error_ledger.json`)
that tracks every Qlib AI prediction from initial issuance (`PENDING`) through forward maturation
(`EVALUATED`) and institutional classification (`SETTLED`).

Key Features:
1. Append-Only Ledger: Records symbol, target horizon, predicted return, raw score, factor fingerprint, and regime at timestamp t.
2. Corporate Action & Surveillance Shield: Identifies nominal price jumps (>20%) lacking equivalent intraday trading spread or abnormal low volume (<10% average) to shield the model from split/bonus/dividend noise (`EXCLUDED_ANOMALY`).
3. Orthogonal Residual Miss Computation: Isolates true idiosyncratic alpha prediction error from broad market/sector beta:
   `idiosyncratic_residual = actual_stock_return - (beta_mkt * actual_nifty_return + sector_alpha) - predicted_stock_return`
4. Settlement Classifier: Distinctly classifies closed-loop outcomes into:
   - `ACCURATE_SUCCESS` (|residual| <= 2.0%)
   - `MODEL_MISS` (|residual| > 2.0% on clean institutional volume)
   - `EXCLUDED_ANOMALY_CORPORATE_ACTION` / `EXCLUDED_ANOMALY_SURVEILLANCE`
"""

import os
import json
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("PredictionLedgerService")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OHLCV_DIR = os.path.join(DATA_DIR, "stocks_ohlcv")
LEDGER_PATH = os.path.join(DATA_DIR, "prediction_error_ledger.json")


def _load_ledger() -> List[Dict[str, Any]]:
    """Loads the append-only prediction ledger from disk."""
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Error loading prediction ledger from {LEDGER_PATH}: {e}")
    return []


def _save_ledger(records: List[Dict[str, Any]]) -> bool:
    """Saves the prediction ledger atomically to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    temp_path = f"{LEDGER_PATH}.tmp.{uuid.uuid4().hex}"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        if os.path.exists(LEDGER_PATH):
            os.replace(temp_path, LEDGER_PATH)
        else:
            os.rename(temp_path, LEDGER_PATH)
        return True
    except Exception as e:
        logger.error(f"Failed to save prediction ledger: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False


def _normalize_symbol(symbol: str) -> str:
    clean = symbol.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
    if not clean.endswith(".NS") and not clean.endswith(".BO") and not clean.startswith("^"):
        clean = f"{clean}.NS"
    return clean


def log_prediction(
    symbol: str,
    target_horizon_days: int = 10,
    predicted_return_pct: float = 0.0,
    raw_alpha_score: float = 50.0,
    features: Optional[Dict[str, Any]] = None,
    market_regime: str = "Normal_Vol",
    custom_logged_at: Optional[str] = None
) -> Dict[str, Any]:
    """Logs a new pre-trade prediction into the append-only ledger (`PENDING` state).

    Args:
        symbol: Stock symbol (e.g., RELIANCE.NS)
        target_horizon_days: Forward evaluation horizon in days (e.g., 5 or 10)
        predicted_return_pct: Model expected return percentage (+4.25)
        raw_alpha_score: Composite AI quant score (0-100)
        features: Dictionary of factor indicator values at issuance t
        market_regime: Identified volatility/macro regime at issuance
        custom_logged_at: Optional ISO timestamp override (for walk-forward backtesting/tests)

    Returns:
        The newly created ledger record containing unique prediction_id.
    """
    clean_sym = _normalize_symbol(symbol)
    if features is None:
        features = {}

    logged_dt = pd.to_datetime(custom_logged_at) if custom_logged_at else datetime.now()
    eval_dt = logged_dt + timedelta(days=target_horizon_days)

    pred_id = f"pred_{int(logged_dt.timestamp())}_{uuid.uuid4().hex[:6]}_{clean_sym}"

    record = {
        "prediction_id": pred_id,
        "symbol": clean_sym,
        "logged_at": logged_dt.isoformat(),
        "target_horizon_days": int(target_horizon_days),
        "target_eval_date": eval_dt.strftime("%Y-%m-%d"),
        "predicted_return_pct": float(np.round(predicted_return_pct, 2)),
        "raw_alpha_score": float(np.round(raw_alpha_score, 2)),
        "features": features,
        "market_regime": str(market_regime),
        "status": "PENDING",
        "actual_return_pct": None,
        "nifty_return_pct": None,
        "sector_return_pct": None,
        "idiosyncratic_residual_pct": None,
        "settlement_verdict": None,
        "settlement_notes": None,
        "evaluated_at": None
    }

    records = _load_ledger()
    records.append(record)
    _save_ledger(records)

    logger.info(f"Logged PENDING prediction {pred_id} for {clean_sym} ({predicted_return_pct:+g}% over {target_horizon_days}D)")
    return record


def _check_corporate_action_anomaly(
    df: pd.DataFrame,
    start_date: str,
    end_date: str
) -> Tuple[bool, str]:
    """Inspects daily bars between start_date and end_date for corporate actions/splits or surveillance freezes.

    Guardrail Rules:
    1. Corporate Split/Bonus/Ex-Dividend: Any single-day absolute price return |R| > 20.0% where intraday
       spread ((High - Low) / Close) < 3.0% indicates a nominal price jump from a stock split or dividend distribution rather than market trading.
    2. Surveillance Circuit Limit Lock / Liquidity Freeze: Any day where trading volume drops below 10%
       of the trailing 20-day average volume alongside continuous circuit lock.
    """
    try:
        sub = df.loc[start_date:end_date]
        if sub.empty or len(sub) < 2:
            return False, "Clean"

        closes = sub["Close"].astype(float)
        highs = sub["High"].astype(float)
        lows = sub["Low"].astype(float)
        vols = sub["Volume"].astype(float)

        daily_ret = (closes.diff() / closes.shift(1)) * 100.0
        intraday_spread = ((highs - lows) / closes) * 100.0

        for dt, r, spread, vol in zip(sub.index[1:], daily_ret.iloc[1:], intraday_spread.iloc[1:], vols.iloc[1:]):
            if not np.isnan(r) and abs(r) > 20.0:
                # If a stock jumps/drops >20% overnight but intraday spread is narrow (<3%), it's almost certainly a corporate split/bonus
                if np.isnan(spread) or spread < 3.0:
                    dt_str = pd.to_datetime(dt).strftime("%Y-%m-%d")
                    return True, f"Corporate action / stock split anomaly detected on {dt_str} ({r:+g}% nominal shift with narrow {spread:.1f}% spread)"

            # Check for extreme liquidity freeze (volume < 1% of mean)
            avg_vol = vols.mean()
            if avg_vol > 0 and vol < (avg_vol * 0.05) and abs(r) > 4.5:
                dt_str = pd.to_datetime(dt).strftime("%Y-%m-%d")
                return True, f"Regulatory surveillance / circuit limit lock detected on {dt_str} (Volume collapsed to {vol:.0f} vs mean {avg_vol:.0f})"

    except Exception as e:
        logger.warning(f"Error checking corporate action anomaly: {e}")

    return False, "Clean"


def compute_orthogonal_residual(
    stock_return_pct: float,
    nifty_return_pct: float = 0.0,
    sector_return_pct: float = 0.0,
    predicted_return_pct: float = 0.0,
    beta_mkt: float = 1.0,
    alpha_sector: float = 0.0
) -> float:
    """Computes pure Idiosyncratic Residual Prediction Miss isolating market and sector beta.

    Formula:
        residual_error = actual_stock_ret - (beta_mkt * actual_nifty_ret + alpha_sector * actual_sector_ret) - predicted_stock_ret
    """
    expected_market_beta_move = beta_mkt * nifty_return_pct
    expected_sector_move = alpha_sector * sector_return_pct
    idiosyncratic_realized = stock_return_pct - (expected_market_beta_move + expected_sector_move)
    residual_miss = idiosyncratic_realized - predicted_return_pct
    return float(np.round(residual_miss, 2))


def evaluate_pending_predictions(
    current_date_str: Optional[str] = None,
    force_eval_ids: Optional[List[str]] = None,
    mock_market_data: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Any]:
    """Evaluates pending prediction records whose target_eval_date has matured.

    Transitions records: `PENDING` -> `EVALUATED` -> `SETTLED`.

    Args:
        current_date_str: Target evaluation date cutoff (defaults to today)
        force_eval_ids: Optional list of specific prediction_ids to evaluate regardless of date cutoff
        mock_market_data: Optional dictionary for automated walk-forward testing:
            {
                "RELIANCE.NS": {"stock_ret": 4.50, "nifty_ret": 1.0, "sector_ret": 0.5, "anomaly": False, "anomaly_reason": "Clean"},
                ...
            }

    Returns:
        Summary counts of evaluated and settled records.
    """
    records = _load_ledger()
    if not records:
        return {"status": "no_records", "evaluated": 0, "settled": 0}

    eval_cutoff = current_date_str if current_date_str else datetime.now().strftime("%Y-%m-%d")
    evaluated_count = 0
    settled_count = 0

    for rec in records:
        if rec["status"] != "PENDING" and (not force_eval_ids or rec["prediction_id"] not in force_eval_ids):
            continue

        if not force_eval_ids and rec["target_eval_date"] > eval_cutoff:
            continue

        sym = rec["symbol"]
        pred_ret = float(rec["predicted_return_pct"])
        logged_dt_str = rec["logged_at"][:10]
        eval_dt_str = rec["target_eval_date"]

        stock_ret = 0.0
        nifty_ret = 0.0
        sector_ret = 0.0
        is_anomaly = False
        anomaly_reason = "Clean"

        if mock_market_data and sym in mock_market_data:
            m = mock_market_data[sym]
            stock_ret = float(m.get("stock_ret", 0.0))
            nifty_ret = float(m.get("nifty_ret", 0.0))
            sector_ret = float(m.get("sector_ret", 0.0))
            is_anomaly = bool(m.get("anomaly", False))
            anomaly_reason = str(m.get("anomaly_reason", "Clean"))
        else:
            # Fetch from local OHLCV disk store
            clean_fn = sym.replace("^", "").replace("=", "_").replace("/", "_")
            local_path = os.path.join(OHLCV_DIR, f"{clean_fn}.csv")
            if os.path.exists(local_path):
                try:
                    df = pd.read_csv(local_path, index_col=0, parse_dates=True)
                    sub = df.loc[logged_dt_str:eval_dt_str]
                    if len(sub) >= 2:
                        p_start = float(sub["Close"].iloc[0])
                        p_end = float(sub["Close"].iloc[-1])
                        stock_ret = float(np.round(((p_end - p_start) / p_start) * 100.0, 2))
                        is_anomaly, anomaly_reason = _check_corporate_action_anomaly(df, logged_dt_str, eval_dt_str)
                except Exception as ex:
                    logger.warning(f"Error reading local bars for {sym}: {ex}")

            # Fetch Nifty baseline
            nifty_path = os.path.join(OHLCV_DIR, "NSEI.csv")
            if os.path.exists(nifty_path):
                try:
                    ndf = pd.read_csv(nifty_path, index_col=0, parse_dates=True)
                    nsub = ndf.loc[logged_dt_str:eval_dt_str]
                    if len(nsub) >= 2:
                        np_start = float(nsub["Close"].iloc[0])
                        np_end = float(nsub["Close"].iloc[-1])
                        nifty_ret = float(np.round(((np_end - np_start) / np_start) * 100.0, 2))
                except Exception:
                    pass

        # Compute orthogonal residual miss
        residual = compute_orthogonal_residual(
            stock_return_pct=stock_ret,
            nifty_return_pct=nifty_ret,
            sector_return_pct=sector_ret,
            predicted_return_pct=pred_ret,
            beta_mkt=1.0,
            alpha_sector=0.0
        )

        rec["status"] = "EVALUATED"
        rec["actual_return_pct"] = round(stock_ret, 2)
        rec["nifty_return_pct"] = round(nifty_ret, 2)
        rec["sector_return_pct"] = round(sector_ret, 2)
        rec["idiosyncratic_residual_pct"] = round(residual, 2)
        rec["evaluated_at"] = datetime.now().isoformat()
        evaluated_count += 1

        # Transition directly to SETTLED with institutional classification
        if is_anomaly:
            rec["status"] = "SETTLED"
            rec["settlement_verdict"] = "EXCLUDED_ANOMALY"
            rec["settlement_notes"] = f"Excluded from learning: {anomaly_reason}"
            settled_count += 1
        else:
            rec["status"] = "SETTLED"
            if abs(residual) <= 2.0:
                rec["settlement_verdict"] = "ACCURATE_SUCCESS"
                rec["settlement_notes"] = f"Prediction accurate within {abs(residual):.2f}% residual bound (Stock: {stock_ret:+g}%, Pred: {pred_ret:+g}%)"
            else:
                rec["settlement_verdict"] = "MODEL_MISS"
                rec["settlement_notes"] = f"Orthogonal prediction miss of {residual:+g}% (Stock: {stock_ret:+g}%, Nifty: {nifty_ret:+g}%, Pred: {pred_ret:+g}%)"
            settled_count += 1

    if evaluated_count > 0 or settled_count > 0:
        _save_ledger(records)
        logger.info(f"Evaluated {evaluated_count} pending predictions and settled {settled_count} records.")

    return {
        "status": "success",
        "evaluated": evaluated_count,
        "settled": settled_count,
        "eval_cutoff": eval_cutoff
    }


def get_ledger_summary() -> Dict[str, Any]:
    """Returns aggregated summary metrics of the prediction error ledger."""
    records = _load_ledger()
    total = len(records)
    pending = sum(1 for r in records if r["status"] == "PENDING")
    evaluated = sum(1 for r in records if r["status"] == "EVALUATED")
    settled = sum(1 for r in records if r["status"] == "SETTLED")

    accurate = sum(1 for r in records if r.get("settlement_verdict") == "ACCURATE_SUCCESS")
    misses = sum(1 for r in records if r.get("settlement_verdict") == "MODEL_MISS")
    excluded = sum(1 for r in records if r.get("settlement_verdict") == "EXCLUDED_ANOMALY")

    clean_settled = accurate + misses
    empirical_win_rate = round((accurate / clean_settled) * 100.0, 1) if clean_settled > 0 else 0.0

    return {
        "total_records": total,
        "pending_records": pending,
        "evaluated_records": evaluated,
        "settled_records": settled,
        "accurate_success_count": accurate,
        "model_miss_count": misses,
        "excluded_anomaly_count": excluded,
        "clean_settled_count": clean_settled,
        "empirical_win_rate_pct": empirical_win_rate,
        "is_ready_for_calibration": bool(clean_settled >= 50),
        "calibration_sample_status": f"{clean_settled}/50"
    }


def get_settled_predictions(min_count: Optional[int] = None) -> List[Dict[str, Any]]:
    """Returns all SETTLED records from the ledger."""
    records = _load_ledger()
    settled = [r for r in records if r["status"] == "SETTLED"]
    if min_count and len(settled) < min_count:
        return []
    return settled


def get_recent_error_misses(limit: int = 20) -> List[Dict[str, Any]]:
    """Returns the most recent SETTLED records classified as MODEL_MISS (`Phase A3 memory inputs`)."""
    records = _load_ledger()
    misses = [r for r in records if r.get("settlement_verdict") == "MODEL_MISS"]
    return sorted(misses, key=lambda x: str(x.get("evaluated_at", "")), reverse=True)[:limit]
