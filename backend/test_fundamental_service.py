# -*- coding: utf-8 -*-
"""
Unit tests for Fundamental Service (10-Pillar & Forensic Accounting Engine).
Covers core calculation rules, sector routing, gates, and escalation logic (Task 25).
"""
import os
import sys
import unittest
from typing import Dict, Any

# Ensure backend directory is in path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import fundamental_service as fs
import fundamental_constants as fc


class TestFundamentalService(unittest.TestCase):
    """Test suite for fundamental_service.py verifying accounting rules and forensic routers."""

    def test_01_financial_debt_vs_lease_liabilities_additive_check(self):
        """
        Task 9: Verify financialDebt and leaseLiabilities are captured separately and added
        together in totalDebtReference for debt-to-equity and net-debt-to-EBITDA ratios.
        """
        frames = {
            "fiscal_year_ends": ["2026-03-31"],
            "balance_sheet": {
                "Long Term Debt": [1000 * 1e7],
                "Short Term Debt": [500 * 1e7],
                "Lease Liabilities": [300 * 1e7],
                "Stockholders Equity": [2000 * 1e7],
                "Cash And Cash Equivalents": [200 * 1e7],
            },
            "financials": {
                "EBITDA": [800 * 1e7],
            },
            "info": {"sector": "Technology", "industry": "Software"},
        }
        res = fs._pillar_balance_sheet(frames)
        self.assertTrue(res["available"])
        liab = res["liabilities"]
        self.assertEqual(liab["financialDebt"], [1500.0])  # 1000 + 500
        self.assertEqual(liab["leaseLiabilities"], [300.0])
        self.assertEqual(liab["totalDebtReference"], [1800.0])  # 1500 + 300
        
        # Check debtToEquity
        self.assertAlmostEqual(liab["debtToEquity"]["financialPrimary"][0], 0.75, places=2)  # 1500 / 2000
        self.assertAlmostEqual(liab["debtToEquity"]["totalSecondary"][0], 0.90, places=2)  # 1800 / 2000
        
        # Check netDebtEbitda
        self.assertAlmostEqual(liab["netDebtEbitda"]["reported"][0], 2.0, places=2)  # (1800 - 200) / 800
        self.assertAlmostEqual(liab["netDebtEbitda"]["exLease"][0], 1.62, places=2)  # (1500 - 200) / 800

    def test_02_holding_company_gate_boolean_split(self):
        """
        Task 6: Verify holding companies are detected via ratio gates and keyword matching,
        and that operating ROIC/ROE and turnover/CCC metrics are suppressed with explanatory reasons.
        """
        # Test 1: Keyword detection + investment ratio > 50%
        info_holding = {
            "sector": "Financial Services",
            "industry": "Asset Management & Holding Companies",
            "longName": "Bajaj Holdings"
        }
        bs_holding = {
            "Investments And Advances": [600 * 1e7],
            "Total Assets": [1000 * 1e7]
        }
        is_hc = fs._is_holding_company(info_holding, {}, bs_holding)
        self.assertTrue(is_hc)

        # Test 2: Suppression in Profitability Pillar
        p4_hc = fs._pillar_profitability({}, is_holding_comp=True)
        self.assertFalse(p4_hc["available"])
        self.assertIn("Suppressed by Holding Company gate", p4_hc["reason"])

        # Test 3: Suppression in Efficiency Pillar
        p6_hc = fs._pillar_efficiency({}, is_holding_comp=True)
        self.assertFalse(p6_hc["available"])
        self.assertIn("Suppressed for Holding Companies", p6_hc["reason"])

    def test_03_altman_router_model_selection(self):
        """
        Task 16: Verify Altman Z-Score priority-ordered sector router selects the correct model
        across IT services (Z''), Pharma API (Z'), manufacturing (Z 1968), and Telecom/BFSI suppressions.
        """
        frames_it = {
            "fiscal_year_ends": ["2026-03-31"],
            "balance_sheet": {"Stockholders Equity": [1000 * 1e7], "Total Assets": [2000 * 1e7]},
            "financials": {"Total Revenue": [1500 * 1e7]},
            "info": {"marketCap": 50000 * 1e7}
        }
        # Test 1: IT Software -> Z'' Non-Mfg
        res_it = fs._altman_z_router(frames_it, sector_bucket="IT_SOFTWARE_SERVICES")
        self.assertEqual(res_it.get("modelUsed"), "Z_DOUBLE_PRIME_NON_MFG")

        # Test 2: Pharma API asset heavy (PPE/TA > 0.40) -> Z' 1983
        frames_pharma = {
            "fiscal_year_ends": ["2026-03-31"],
            "balance_sheet": {"Stockholders Equity": [1000 * 1e7], "Total Assets": [1000 * 1e7], "Net PPE": [500 * 1e7]},
            "financials": {"Total Revenue": [1000 * 1e7]},
            "info": {"marketCap": 50000 * 1e7}
        }
        res_pharma = fs._altman_z_router(frames_pharma, sector_bucket="PHARMA_API_CDMO_CHEMICALS")
        self.assertEqual(res_pharma.get("modelUsed"), "Z_PRIME_1983")

        # Test 3: Standard Manufacturing large cap -> Z 1968
        res_mfg = fs._altman_z_router(frames_it, sector_bucket="AUTO_MANUFACTURING")
        self.assertEqual(res_mfg.get("modelUsed"), "Z_1968")

        # Test 4: Telecom -> Rolling FCF and Net Debt replacement
        res_tel = fs._altman_z_router(frames_it, sector_bucket="TELECOM_MEDIA")
        self.assertEqual(res_tel.get("modelUsed"), "ALTMAN_REPLACED_BY_ROLLING_FCF_AND_NET_DEBT")

        # Test 5: BFSI -> Suppressed
        res_bfsi = fs._altman_z_router(frames_it, is_bfsi=True)
        self.assertFalse(res_bfsi.get("available"))
        self.assertIn("Suppressed for BFSI", res_bfsi.get("selectionReason", ""))

    def test_04_sloan_growth_band_selection(self):
        """
        Task 17: Verify Sloan Accrual Ratio calculator selects correct growth bands (<10%, 10-20%, >20%)
        and applies growth-adjusted moderate/severe thresholds.
        """
        frames = {
            "fiscal_year_ends": ["2026-03-31"],
            "balance_sheet": {"Total Assets": [1000 * 1e7]},
            "financials": {"Net Income": [100 * 1e7], "Total Revenue": [500 * 1e7]},
            "cashflow": {"Investing Cash Flow": [-50 * 1e7]}
        }
        p3 = {"ocfQuality": {"ocf": [80 * 1e7]}}  # accrual ratio = (100 - 80 - 0) / 1000 = 2%

        # Band 1: >20% growth
        res_high = fs._sloan_accrual(frames, {"revenue3yCagr": 25.0}, p3)
        self.assertEqual(res_high.get("revenue3yCagrBand"), ">20%")
        self.assertEqual(res_high.get("moderateThresholdPct"), 15.0)
        self.assertEqual(res_high.get("severeThresholdPct"), 30.0)
        self.assertTrue(res_high.get("growthAdjustedThresholdApplied"))

        # Band 2: 10-20% growth
        res_mid = fs._sloan_accrual(frames, {"revenue3yCagr": 15.0}, p3)
        self.assertEqual(res_mid.get("revenue3yCagrBand"), "10-20%")
        self.assertEqual(res_mid.get("moderateThresholdPct"), 12.0)
        self.assertEqual(res_mid.get("severeThresholdPct"), 27.0)

        # Band 3: <10% growth
        res_low = fs._sloan_accrual(frames, {"revenue3yCagr": 5.0}, p3)
        self.assertEqual(res_low.get("revenue3yCagrBand"), "<10%")
        self.assertEqual(res_low.get("moderateThresholdPct"), 10.0)
        self.assertEqual(res_low.get("severeThresholdPct"), 25.0)
        self.assertFalse(res_low.get("growthAdjustedThresholdApplied"))

    def test_05_beneish_corroboration_escalation_rule(self):
        """
        Task 18: Verify Beneish corroboration wiring in the Red Flag Engine escalates
        m-score risk to Red when 2 or more quantitative red flags are triggered.
        """
        # Setup mock pillars dict where 2 specific flags trigger:
        # Flag 1: revenue growth 10%, receivables growth 50% (> 10 + 15 = 25%) -> triggers Flag 1
        p1_flag1 = {"revenueYoyGrowthPct": [10.0]}
        p2_flag1 = {"assets": {"receivables": [150.0, 100.0]}}
        p4_clean = {"returns": {"roic": [12.0, 11.0, 10.0], "wacc": [10.0, 10.0, 10.0]}}
        
        # Flag 16: promoter holding decline -5.0% (< -3.0%) -> triggers Flag 16
        frames_flag16 = {"info": {"promoterHoldingChange": -5.0}}

        beneish_dict = {
            "available": True,
            "mScore": [-1.90],
            "riskBand": ["Moderate"],
            "corroboratingFlagCount": 0,
            "escalatedToRed": False
        }

        # Call with 2 flags triggering
        rfe_res = fs._red_flag_engine(
            {"incomeStatement": p1_flag1, "balanceSheet": p2_flag1, "profitability": p4_clean},
            sector_bucket="GENERAL_OTHER",
            beneish=beneish_dict,
            altman_result={"available": False},
            sloan_result={"available": False},
            frames=frames_flag16
        )
        self.assertGreaterEqual(beneish_dict.get("corroboratingFlagCount", 0), 2)
        self.assertTrue(beneish_dict.get("escalatedToRed"))

        # Call with 0 flags triggering
        beneish_clean = {
            "available": True,
            "mScore": [-1.90],
            "riskBand": ["Moderate"],
            "corroboratingFlagCount": 0,
            "escalatedToRed": False
        }
        rfe_clean = fs._red_flag_engine(
            {"profitability": p4_clean},
            sector_bucket="GENERAL_OTHER",
            beneish=beneish_clean,
            altman_result={"available": False},
            sloan_result={"available": False},
            frames={"info": {"promoterHoldingChange": 0.0}}
        )
        self.assertEqual(beneish_clean.get("corroboratingFlagCount"), 0)
        self.assertFalse(beneish_clean.get("escalatedToRed"))


if __name__ == "__main__":
    unittest.main()
