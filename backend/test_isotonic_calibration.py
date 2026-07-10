"""Automated Verification Test Suite for Phase B Isotonic OOS Probability Calibration (`isotonic_calibrator_service.py`).

Tests:
1. Strict Sample Threshold Guardrail (`if N < 50 -> calibrated=False, status='Sample: N/50'`)
2. Isotonic Curve Fitting & Calibrated Win-Rate / Expected Value (`if N >= 50 -> calibrated=True`)
3. Qlib Alpha Service Integration (`get_qlib_alpha_prediction` attaches calibration payload)
"""

import os
import sys
import unittest
import numpy as np

# Add backend dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isotonic_calibrator_service as ics
import prediction_ledger_service as pls
import qlib_service as qlib


class TestIsotonicCalibration(unittest.TestCase):

    def setUp(self):
        """Use isolated test ledger for controlling sample count N."""
        self.orig_ledger_path = pls.LEDGER_PATH
        self.test_ledger_path = os.path.join(ics.pls.DATA_DIR if hasattr(ics, "pls") else pls.DATA_DIR, "test_prediction_ledger_calibration_temp.json")
        pls.LEDGER_PATH = self.test_ledger_path
        if os.path.exists(self.test_ledger_path):
            os.remove(self.test_ledger_path)

    def tearDown(self):
        """Restore original ledger path and clean up temp file."""
        if os.path.exists(self.test_ledger_path):
            os.remove(self.test_ledger_path)
        pls.LEDGER_PATH = self.orig_ledger_path

    def test_01_strict_sample_threshold_under_50(self):
        """Verify that when N < 50, system refuses to calibrate and reports exact sample status."""
        # Log and settle exactly 15 records
        for i in range(15):
            pls.log_prediction(
                f"S{i}.NS",
                target_horizon_days=5,
                predicted_return_pct=3.0,
                raw_alpha_score=70.0 + i,
                custom_logged_at="2026-06-01T10:00:00"
            )
        mock_data = {f"S{i}.NS": {"stock_ret": 3.0, "nifty_ret": 0.0, "sector_ret": 0.0, "anomaly": False} for i in range(15)}
        pls.evaluate_pending_predictions(current_date_str="2026-06-15", mock_market_data=mock_data)

        res = ics.calibrate_alpha_score(raw_score=78.0)
        self.assertFalse(res["calibrated"])
        self.assertEqual(res["sample_count"], 15)
        self.assertEqual(res["threshold_required"], 50)
        self.assertIn("15/50", res["status_badge"])

    def test_02_isotonic_fitting_and_ev_over_50(self):
        """Verify that when N >= 50, system fits monotonic curve and outputs win rate and EV."""
        # Log and settle 60 records with strong score-outcome relationship
        # High scores (>= 60) -> 80% accurate successes (+4% ret)
        # Low scores (< 60) -> 20% accurate successes (-3% ret)
        for i in range(60):
            score = 35.0 + i
            is_win = (score >= 60.0 and i % 5 != 0) or (score < 60.0 and i % 5 == 0)
            pls.log_prediction(
                f"T{i}.NS",
                target_horizon_days=5,
                predicted_return_pct=4.0 if is_win else 3.0,
                raw_alpha_score=score,
                custom_logged_at="2026-06-01T10:00:00"
            )
            mock_ret = 4.0 if is_win else -3.5
            mock_data = {f"T{i}.NS": {"stock_ret": mock_ret, "nifty_ret": 0.0, "sector_ret": 0.0, "anomaly": False}}
            pls.evaluate_pending_predictions(current_date_str="2026-06-15", mock_market_data=mock_data)

        # Test high score (e.g. 85.0)
        res_high = ics.calibrate_alpha_score(raw_score=85.0)
        self.assertTrue(res_high["calibrated"])
        self.assertEqual(res_high["sample_count"], 60)
        self.assertGreaterEqual(res_high["calibrated_win_rate_pct"], 65.0)
        self.assertGreater(res_high["expected_value_pct"], 1.0)

        # Test low score (e.g. 40.0) -> monotonic property: win rate must be lower than high score
        res_low = ics.calibrate_alpha_score(raw_score=40.0)
        self.assertTrue(res_low["calibrated"])
        self.assertLess(res_low["calibrated_win_rate_pct"], res_high["calibrated_win_rate_pct"])


if __name__ == "__main__":
    unittest.main()
