import os
import sys
import unittest
from datetime import datetime

# Ensure backend directory is in path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import institutional_flow_service as ifs
from institutional_flow_service import InstitutionalFlowService


class MockExtraService:
    @staticmethod
    def get_fii_dii():
        return {
            "rows": [
                {
                    "date": "2026-07-10",
                    "displayDate": "10-Jul-2026",
                    "fiiCash": 3150.50,
                    "diiCash": 1420.25,
                    "fiiIdxFut": 850.0,
                    "fiiStkFut": -200.0,
                    "niftyClose": 24500.0,
                    "niftyChangePct": 1.25
                },
                {
                    "date": "2026-07-09",
                    "displayDate": "09-Jul-2026",
                    "fiiCash": -4500.0,
                    "diiCash": 2100.0,
                    "fiiIdxFut": -1200.0,
                    "fiiStkFut": -500.0,
                    "niftyClose": 24200.0,
                    "niftyChangePct": -0.85
                }
            ],
            "updatedAt": datetime.now().isoformat()
        }


class TestInstitutionalFlowService(unittest.TestCase):
    def test_01_fetch_and_update_flows_with_mock(self):
        """Verifies ingestion of mock FII/DII data into institutional flow service and computation of whale metrics."""
        service = InstitutionalFlowService()
        metrics = service.fetch_and_update_flows(MockExtraService)
        
        self.assertEqual(metrics["status"], "active")
        self.assertEqual(metrics["fii_cash_net_cr"], 3150.50)
        self.assertEqual(metrics["dii_cash_net_cr"], 1420.25)
        self.assertGreater(metrics["institutional_conviction_multiplier"], 1.0, "Heavy joint FII/DII buying should boost conviction > 1.0x!")
        self.assertEqual(metrics["regime_signal"], "INSTITUTIONAL_STRONG_ACCUMULATION")

    def test_02_exodus_warning_discount(self):
        """Verifies that severe FII selling triggers FII_EXODUS_WARNING and discounts conviction multiplier."""
        service = InstitutionalFlowService()
        # Inject artificial severe selloff row at top of history
        service.history = [{
            "date": "2026-07-11",
            "fiiCash": -5200.0,
            "diiCash": 1100.0,
            "fiiIdxFut": -2500.0,
            "fiiStkFut": -1000.0
        }] + service.history
        
        metrics = service.compute_institutional_flow_metrics()
        self.assertEqual(metrics["regime_signal"], "FII_EXODUS_WARNING")
        self.assertEqual(metrics["institutional_conviction_multiplier"], 0.85)
        self.assertLess(metrics["whale_drift_bps"], 0.0, "Severe FII futures dumping should create negative Bayesian drift!")


if __name__ == "__main__":
    unittest.main()
