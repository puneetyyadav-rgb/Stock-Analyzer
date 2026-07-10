"""Automated Verification Test Suite for Phase A1 Prediction Error Ledger (`prediction_ledger_service.py`).

Tests:
1. Append-Only Ledger Integrity & Persistence (`log_prediction`)
2. Orthogonal Residual Miss Formula Verification (`compute_orthogonal_residual`)
3. Corporate Action & Surveillance Shield (`_check_corporate_action_anomaly`)
4. Walk-Forward Lifecycle Settlement (`evaluate_pending_predictions`)
"""

import os
import sys
import json
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add backend dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prediction_ledger_service as pls


class TestPredictionLedgerService(unittest.TestCase):

    def setUp(self):
        """Use a clean temporary test ledger for isolated verification."""
        self.orig_ledger_path = pls.LEDGER_PATH
        self.test_ledger_path = os.path.join(pls.DATA_DIR, "test_prediction_ledger_temp.json")
        pls.LEDGER_PATH = self.test_ledger_path
        if os.path.exists(self.test_ledger_path):
            os.remove(self.test_ledger_path)

    def tearDown(self):
        """Restore original ledger path and clean up test file."""
        if os.path.exists(self.test_ledger_path):
            os.remove(self.test_ledger_path)
        pls.LEDGER_PATH = self.orig_ledger_path

    def test_01_append_only_logging(self):
        """Verify log_prediction appends correctly without data loss or overwriting."""
        rec1 = pls.log_prediction("RELIANCE.NS", target_horizon_days=10, predicted_return_pct=4.5, raw_alpha_score=78.2)
        rec2 = pls.log_prediction("TCS.NS", target_horizon_days=5, predicted_return_pct=-2.1, raw_alpha_score=31.0)

        self.assertEqual(rec1["status"], "PENDING")
        self.assertEqual(rec2["status"], "PENDING")

        summary = pls.get_ledger_summary()
        self.assertEqual(summary["total_records"], 2)
        self.assertEqual(summary["pending_records"], 2)
        self.assertEqual(summary["settled_records"], 0)

    def test_02_orthogonal_residual_formula(self):
        """Verify exact math of compute_orthogonal_residual."""
        # Case A: Stock moves +5.0%, Nifty moves +2.0% (Beta 1.0), Predicted return was +3.0%
        # Residual = 5.0 - (1.0 * 2.0 + 0) - 3.0 = 0.0% -> Perfect prediction!
        res_a = pls.compute_orthogonal_residual(stock_return_pct=5.0, nifty_return_pct=2.0, predicted_return_pct=3.0, beta_mkt=1.0)
        self.assertAlmostEqual(res_a, 0.0, places=2)

        # Case B: Stock moves -4.0%, Nifty flat 0.0%, Predicted was +3.5%
        # Residual = -4.0 - 0 - 3.5 = -7.5% -> Severe model miss!
        res_b = pls.compute_orthogonal_residual(stock_return_pct=-4.0, nifty_return_pct=0.0, predicted_return_pct=3.5, beta_mkt=1.0)
        self.assertAlmostEqual(res_b, -7.5, places=2)

    def test_03_corporate_action_anomaly_shield(self):
        """Verify that overnight stock splits/bonuses (>20% move with narrow spread) are flagged as anomalies."""
        dates = pd.date_range("2026-06-01", periods=10, freq="D")
        # Create simulated dataframe where price drops 50% on June 5 (1:2 split) with narrow intraday spread
        closes = [1000, 1010, 1005, 1020, 510, 512, 515, 514, 518, 520]
        highs  = [1015, 1020, 1012, 1025, 515, 516, 518, 519, 522, 525]
        lows   = [995,  1002, 998,  1012, 505, 508, 510, 510, 514, 516]
        vols   = [100000] * 10

        df = pd.DataFrame({"Close": closes, "High": highs, "Low": lows, "Volume": vols}, index=dates)
        is_anomaly, reason = pls._check_corporate_action_anomaly(df, "2026-06-01", "2026-06-10")
        self.assertTrue(is_anomaly)
        self.assertIn("Corporate action / stock split anomaly detected", reason)

    def test_04_walk_forward_evaluation_and_settlement(self):
        """Verify evaluate_pending_predictions correctly transitions PENDING -> EVALUATED -> SETTLED."""
        # Log 3 pending predictions with past dates so they mature immediately
        rec_acc = pls.log_prediction("INFY.NS", target_horizon_days=5, predicted_return_pct=2.0, custom_logged_at="2026-06-01T10:00:00")
        rec_miss = pls.log_prediction("HDFCBANK.NS", target_horizon_days=5, predicted_return_pct=6.0, custom_logged_at="2026-06-01T10:00:00")
        rec_anom = pls.log_prediction("TATAMOTORS.NS", target_horizon_days=5, predicted_return_pct=1.0, custom_logged_at="2026-06-01T10:00:00")

        # Mock market data for evaluation
        mock_data = {
            "INFY.NS": {"stock_ret": 3.0, "nifty_ret": 1.0, "sector_ret": 0.0, "anomaly": False, "anomaly_reason": "Clean"},
            # Residual = 3.0 - 1.0 - 2.0 = 0.0% -> ACCURATE_SUCCESS
            "HDFCBANK.NS": {"stock_ret": -2.0, "nifty_ret": 0.5, "sector_ret": 0.0, "anomaly": False, "anomaly_reason": "Clean"},
            # Residual = -2.0 - 0.5 - 6.0 = -8.5% -> MODEL_MISS (>2%)
            "TATAMOTORS.NS": {"stock_ret": -50.0, "nifty_ret": 0.0, "sector_ret": 0.0, "anomaly": True, "anomaly_reason": "Corporate split 1:2 detected"}
            # Corporate Action -> EXCLUDED_ANOMALY
        }

        eval_res = pls.evaluate_pending_predictions(current_date_str="2026-06-15", mock_market_data=mock_data)
        self.assertEqual(eval_res["evaluated"], 3)
        self.assertEqual(eval_res["settled"], 3)

        summary = pls.get_ledger_summary()
        self.assertEqual(summary["total_records"], 3)
        self.assertEqual(summary["pending_records"], 0)
        self.assertEqual(summary["accurate_success_count"], 1)
        self.assertEqual(summary["model_miss_count"], 1)
        self.assertEqual(summary["excluded_anomaly_count"], 1)
        self.assertEqual(summary["empirical_win_rate_pct"], 50.0) # 1 accurate out of 2 clean settled


if __name__ == "__main__":
    unittest.main()
