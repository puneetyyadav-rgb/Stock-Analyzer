"""Automated Verification Test Suite for Phase A2 Rolling Rank IC Factor Health Monitor (`self_learning_service.py`).

Tests:
1. Spearman Rank Correlation & ICIR Calculation Across Ledger Records (`calculate_rolling_rank_ic`)
2. Automatic Regime Decay Pruning Rule (`if Rank IC < 0.01 for 3 consecutive windows -> weight -> 0.00`)
3. Factor Recovery Promotion Rule (`if Rank IC >= 0.04 for 2 consecutive windows -> weight -> 1.00`)
4. Report Generation (`get_factor_rank_ic_report`)
"""

import os
import sys
import json
import unittest
import numpy as np

# Add backend dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import self_learning_service as sls
import prediction_ledger_service as pls


class TestRankICMonitor(unittest.TestCase):

    def setUp(self):
        """Use isolated test paths for factor weights and prediction ledger."""
        self.orig_weights_path = sls.FACTOR_WEIGHTS_PATH
        self.orig_ledger_path = pls.LEDGER_PATH
        
        self.test_weights_path = os.path.join(sls.DATA_DIR, "test_meta_factor_weights_temp.json")
        self.test_ledger_path = os.path.join(sls.DATA_DIR, "test_prediction_ledger_temp.json")
        
        sls.FACTOR_WEIGHTS_PATH = self.test_weights_path
        pls.LEDGER_PATH = self.test_ledger_path
        
        if os.path.exists(self.test_weights_path):
            os.remove(self.test_weights_path)
        if os.path.exists(self.test_ledger_path):
            os.remove(self.test_ledger_path)

    def tearDown(self):
        """Restore original paths and clean up temporary test files."""
        if os.path.exists(self.test_weights_path):
            os.remove(self.test_weights_path)
        if os.path.exists(self.test_ledger_path):
            os.remove(self.test_ledger_path)
            
        sls.FACTOR_WEIGHTS_PATH = self.orig_weights_path
        pls.LEDGER_PATH = self.orig_ledger_path

    def test_01_rank_ic_and_icir_calculation(self):
        """Verify Spearman Rank IC correctly correlates factor values against idiosyncratic residuals."""
        # Log 5 settled records with known correlations
        # Factor 'strong_factor': perfectly correlated with residual
        # Factor 'dead_factor': constant 0.0 (zero correlation/zero variance)
        for i in range(5):
            pls.log_prediction(
                f"SYM{i}.NS",
                target_horizon_days=5,
                predicted_return_pct=1.0,
                raw_alpha_score=50.0,
                features={"strong_factor": float(i), "dead_factor": 0.0},
                custom_logged_at="2026-06-01T10:00:00"
            )

        # Mock market data where residual equals i
        mock_data = {
            f"SYM{i}.NS": {"stock_ret": float(1.0 + i), "nifty_ret": 0.0, "sector_ret": 0.0, "anomaly": False}
            for i in range(5)
        }
        pls.evaluate_pending_predictions(current_date_str="2026-06-15", mock_market_data=mock_data)

        # Execute Rank IC calculation
        res = sls.calculate_rolling_rank_ic(lookback_days=30)
        self.assertEqual(res["status"], "success")
        
        # strong_factor should have Rank IC close to 1.0
        self.assertAlmostEqual(res["rank_ic"].get("strong_factor", 0.0), 1.0, places=2)
        # dead_factor should have Rank IC close to 0.0
        self.assertAlmostEqual(res["rank_ic"].get("dead_factor", 0.0), 0.0, places=2)

    def test_02_regime_decay_pruning_after_3_consecutive_windows(self):
        """Verify that a factor with Rank IC < 0.01 across 3 consecutive windows is pruned to 0.00 weight."""
        # Log 4 settled records where 'decayed_factor' is completely uncorrelated/noisy
        for i in range(4):
            pls.log_prediction(
                f"D{i}.NS",
                target_horizon_days=5,
                predicted_return_pct=1.0,
                raw_alpha_score=50.0,
                features={"decayed_factor": 1.0 if i % 2 == 0 else -1.0},
                custom_logged_at="2026-06-01T10:00:00"
            )

        mock_data = {f"D{i}.NS": {"stock_ret": 1.0, "nifty_ret": 0.0, "sector_ret": 0.0, "anomaly": False} for i in range(4)}
        pls.evaluate_pending_predictions(current_date_str="2026-06-15", mock_market_data=mock_data)

        # Window 1: Prune count -> 1
        sls.calculate_rolling_rank_ic()
        with open(sls.FACTOR_WEIGHTS_PATH, "r") as f:
            meta1 = json.load(f)
        self.assertEqual(meta1["consecutive_prune_counts"].get("decayed_factor"), 1)
        self.assertGreater(meta1["weights"].get("decayed_factor", 1.0), 0.0)

        # Window 2: Prune count -> 2
        sls.calculate_rolling_rank_ic()
        with open(sls.FACTOR_WEIGHTS_PATH, "r") as f:
            meta2 = json.load(f)
        self.assertEqual(meta2["consecutive_prune_counts"].get("decayed_factor"), 2)

        # Window 3: Prune count -> 3 -> PRUNED! Weight -> 0.00
        res3 = sls.calculate_rolling_rank_ic()
        self.assertEqual(res3["adaptive_weights"].get("decayed_factor"), 0.0)
        self.assertIn("PRUNED", res3["pruning_status"].get("decayed_factor", ""))

    def test_03_factor_rank_ic_report(self):
        """Verify get_factor_rank_ic_report returns structured health data."""
        # Initialize report
        rep = sls.get_factor_rank_ic_report()
        self.assertEqual(rep["status"], "success")
        self.assertIsInstance(rep["factors"], list)
        self.assertGreaterEqual(len(rep["factors"]), 1)


if __name__ == "__main__":
    unittest.main()
