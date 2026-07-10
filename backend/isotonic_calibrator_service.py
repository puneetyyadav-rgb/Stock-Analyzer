"""Isotonic Probability Calibrator Service (`Phase B`).

Fits a 1D non-decreasing `IsotonicRegression` curve (`y_min=0.05, y_max=0.95`) mapping raw composite AI
scores (0-100) to empirical win-rate probabilities across `SETTLED` out-of-sample ledger records.

Enforces institutional sample threshold `N >= 50` before returning calibrated confidence metrics to
prevent false confidence during initial accumulation phases.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger("IsotonicCalibratorService")


def calibrate_alpha_score(raw_score: float) -> Dict[str, Any]:
    """Calibrates a raw Qlib composite AI quant score against empirical OOS trade accuracy.

    Args:
        raw_score: Candidate raw composite AI score (0-100)

    Returns:
        Dictionary containing `calibrated` boolean, `calibrated_win_rate_pct`, `expected_value_pct`,
        `sample_count`, `threshold_required` (50), and formatted `status_badge`.
    """
    clean_score = float(np.clip(raw_score, 0.0, 100.0))
    threshold = 50

    try:
        import prediction_ledger_service as pls
        settled = pls.get_settled_predictions()
        # Exclude corporate action / surveillance anomalies
        clean_records = [r for r in settled if r.get("settlement_verdict") in ["ACCURATE_SUCCESS", "MODEL_MISS"]]
    except Exception as e:
        logger.warning(f"Error reading prediction ledger for calibration: {e}")
        clean_records = []

    sample_count = len(clean_records)

    # Guardrail: Strict N >= 50 OOS Sample Threshold
    if sample_count < threshold:
        return {
            "calibrated": False,
            "raw_score": clean_score,
            "calibrated_win_rate_pct": None,
            "expected_value_pct": None,
            "sample_count": sample_count,
            "threshold_required": threshold,
            "status_badge": f"Sample: {sample_count}/{threshold} (Collecting OOS Truth)"
        }

    # Fit Isotonic Regression over clean OOS records
    try:
        from sklearn.isotonic import IsotonicRegression

        X_scores = []
        y_outcomes = []
        success_rets = []
        miss_rets = []

        for r in clean_records:
            s = float(r.get("raw_alpha_score", 50.0))
            verdict = r.get("settlement_verdict")
            ret = float(r.get("actual_return_pct", 0.0))

            X_scores.append(s)
            if verdict == "ACCURATE_SUCCESS":
                y_outcomes.append(1.0)
                success_rets.append(ret)
            else:
                y_outcomes.append(0.0)
                miss_rets.append(ret)

        iso = IsotonicRegression(y_min=0.05, y_max=0.95, out_of_bounds="clip")
        iso.fit(X_scores, y_outcomes)

        win_prob = float(iso.predict([clean_score])[0])
        win_rate_pct = float(np.round(win_prob * 100.0, 1))

        # Compute empirical Expected Value (EV)
        avg_win = float(np.mean(success_rets)) if success_rets else 3.5
        avg_loss = float(np.mean(miss_rets)) if miss_rets else -3.0
        ev_pct = float(np.round((win_prob * avg_win) + ((1.0 - win_prob) * avg_loss), 2))

        return {
            "calibrated": True,
            "raw_score": clean_score,
            "calibrated_win_rate_pct": win_rate_pct,
            "expected_value_pct": ev_pct,
            "sample_count": sample_count,
            "threshold_required": threshold,
            "status_badge": f"{win_rate_pct}% Win Rate (N={sample_count} Calibrated)"
        }

    except ImportError:
        logger.error("scikit-learn not installed, cannot fit Isotonic Regression")
        return {
            "calibrated": False,
            "raw_score": clean_score,
            "calibrated_win_rate_pct": None,
            "expected_value_pct": None,
            "sample_count": sample_count,
            "threshold_required": threshold,
            "status_badge": "Error: scikit-learn required for Isotonic Calibration"
        }
    except Exception as ex:
        logger.warning(f"Isotonic calibration fitting error: {ex}")
        return {
            "calibrated": False,
            "raw_score": clean_score,
            "calibrated_win_rate_pct": None,
            "expected_value_pct": None,
            "sample_count": sample_count,
            "threshold_required": threshold,
            "status_badge": f"Sample: {sample_count}/{threshold} (Collecting OOS Truth)"
        }
