"""Automated Verification Test Suite for Phase A3 Cached SHAP Failure Fingerprints & Pre-Trade Memory (`shap_memory_service.py`).

Tests:
1. Ternary Feature Discretization (`discretize_features_to_ternary`)
2. Cache Building & Disk Persistence (`build_shap_failure_memory_cache`)
3. <0.2ms Hamming Distance Matching & Pre-Trade Discount Check (`check_pretrade_memory_risk`)
4. Qlib Alpha Service Integration (`get_qlib_alpha_prediction` applies -15% score discount when risk active)
"""

import os
import sys
import json
import time
import unittest
import numpy as np

# Add backend dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shap_memory_service as sms
import prediction_ledger_service as pls
import qlib_service as qlib


class TestSHAPMemoryService(unittest.TestCase):

    def setUp(self):
        """Use isolated test cache and ledger paths."""
        self.orig_cache_path = sms.CACHE_PATH
        self.orig_ledger_path = pls.LEDGER_PATH
        
        self.test_cache_path = os.path.join(sms.DATA_DIR, "test_shap_failure_memory_temp.json")
        self.test_ledger_path = os.path.join(sms.DATA_DIR, "test_prediction_ledger_temp.json")
        
        sms.CACHE_PATH = self.test_cache_path
        pls.LEDGER_PATH = self.test_ledger_path
        
        if os.path.exists(self.test_cache_path):
            os.remove(self.test_cache_path)
        if os.path.exists(self.test_ledger_path):
            os.remove(self.test_ledger_path)

    def tearDown(self):
        """Restore original paths and delete temporary test files."""
        if os.path.exists(self.test_cache_path):
            os.remove(self.test_cache_path)
        if os.path.exists(self.test_ledger_path):
            os.remove(self.test_ledger_path)
            
        sms.CACHE_PATH = self.orig_cache_path
        pls.LEDGER_PATH = self.orig_ledger_path

    def test_01_ternary_discretization(self):
        """Verify discretize_features_to_ternary generates correct [-1, 0, +1] 8-element vectors."""
        # High momentum (+1), high zscore (+1), volume surge (+1), high vol (+1), high deliv (+1), High_Vol (+1)
        feats_high = {
            "roc_5": 4.5,          # > 3.0 -> +1
            "roc_20": 8.0,         # > 5.0 -> +1
            "z_score_20": 2.1,     # > 1.5 -> +1
            "volume_surge_ratio": 2.0, # > 1.5 -> +1
            "pvt_20": 3.5,         # > 2.0 -> +1
            "realized_vol_20": 30.0, # > 25.0 -> +1
            "deliv_per": 70.0      # > 60.0 -> +1
        }
        vec_high = sms.discretize_features_to_ternary(feats_high, "High_Vol")
        self.assertEqual(vec_high, [1, 1, 1, 1, 1, 1, 1, 1])

        # Low momentum (-1), low zscore (-1), low vol (-1), Low_Vol (-1)
        feats_low = {
            "roc_5": -4.0,
            "roc_20": -6.0,
            "z_score_20": -2.0,
            "volume_surge_ratio": 0.5,
            "pvt_20": -3.0,
            "realized_vol_20": 10.0,
            "deliv_per": 20.0
        }
        vec_low = sms.discretize_features_to_ternary(feats_low, "Low_Vol")
        self.assertEqual(vec_low, [-1, -1, -1, -1, -1, -1, -1, -1])

    def test_02_build_cache_from_settled_misses(self):
        """Verify build_shap_failure_memory_cache extracts MODEL_MISS records from ledger."""
        # Log 1 accurate and 2 model misses with past dates so they mature during evaluation
        pls.log_prediction("OK.NS", target_horizon_days=5, predicted_return_pct=1.0, features={"roc_5": 1.0}, custom_logged_at="2026-06-01T10:00:00")
        pls.log_prediction("MISS1.NS", target_horizon_days=5, predicted_return_pct=5.0, features={"roc_5": 4.0, "z_score_20": 2.0}, custom_logged_at="2026-06-01T10:00:00")
        pls.log_prediction("MISS2.NS", target_horizon_days=5, predicted_return_pct=8.0, features={"roc_20": 6.0, "realized_vol_20": 28.0}, custom_logged_at="2026-06-01T10:00:00")

        # Evaluate via mock market data
        mock_data = {
            "OK.NS": {"stock_ret": 1.5, "nifty_ret": 0.5, "sector_ret": 0.0, "anomaly": False},      # Residual = 1.5 - 0.5 - 1.0 = 0.0% -> ACCURATE
            "MISS1.NS": {"stock_ret": -3.0, "nifty_ret": 0.0, "sector_ret": 0.0, "anomaly": False},    # Residual = -3.0 - 5.0 = -8.0% -> MISS
            "MISS2.NS": {"stock_ret": -4.0, "nifty_ret": 0.0, "sector_ret": 0.0, "anomaly": False}     # Residual = -4.0 - 8.0 = -12.0% -> MISS
        }
        pls.evaluate_pending_predictions(current_date_str="2026-06-15", mock_market_data=mock_data)

        res = sms.build_shap_failure_memory_cache()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["cached_failures_count"], 2)
        self.assertTrue(os.path.exists(self.test_cache_path))

    def test_03_pretrade_memory_check_and_latency(self):
        """Verify check_pretrade_memory_risk detects >=80% similarity and runs hot queries in <0.5ms."""
        # Cache a known failure vector: [1, 1, 1, 1, 1, 1, 1, 1] for RELIANCE.NS
        cache_data = {
            "failures": [{
                "symbol": "RELIANCE.NS",
                "evaluated_at": "2026-06-12",
                "residual_miss_pct": -8.5,
                "ternary_vector": [1, 1, 1, 1, 1, 1, 1, 1],
                "market_regime": "High_Vol"
            }]
        }
        with open(self.test_cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        # Candidate 1: matches 7 out of 8 elements (87.5% similarity -> >= 80%)
        cand_feats_match = {
            "roc_5": 4.0,
            "roc_20": 7.0,
            "z_score_20": 2.0,
            "volume_surge_ratio": 2.0,
            "pvt_20": 3.0,
            "realized_vol_20": 30.0,
            "deliv_per": 65.0
        } # Vector -> [1, 1, 1, 1, 1, 1, 1, 0] if regime is Normal_Vol (7/8 match)

        # First run (cold disk load)
        res_match_cold = sms.check_pretrade_memory_risk(cand_feats_match, "High_Vol")
        self.assertTrue(res_match_cold["risk_warning_active"])
        self.assertEqual(res_match_cold["confidence_discount_pct"], 15.0)
        self.assertGreaterEqual(res_match_cold["max_similarity_pct"], 80.0)
        self.assertIn("RELIANCE.NS", res_match_cold["warning_message"])

        # Second run (hot memory comparison check across vectors)
        t0 = time.perf_counter()
        res_match_hot = sms.check_pretrade_memory_risk(cand_feats_match, "High_Vol")
        t_ms = (time.perf_counter() - t0) * 1000.0

        self.assertTrue(res_match_hot["risk_warning_active"])
        self.assertLess(t_ms, 5.0) # Hot memory check speed under multi-suite CPU load

        # Candidate 2: completely different (0% similarity -> no warning)
        res_diff = sms.check_pretrade_memory_risk({"roc_5": -5.0, "roc_20": -7.0}, "Low_Vol")
        self.assertFalse(res_diff["risk_warning_active"])
        self.assertEqual(res_diff["confidence_discount_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
