r"""
institutional_flow_service.py — Alpha 24 Institutional Flow & FII/DII Net Positioning Engine

Ingests daily Foreign Institutional Investor (FII) and Domestic Institutional Investor (DII) flows across
cash equities and derivatives (index/stock futures and options) to compute Bayesian Whale Flow Imbalances ($\Phi_{\text{whale}}$)
and directional return drift adjustments ($\Delta \mu_{\text{whale}}$).

Institutional Mathematics:
1. Net Cash Flow Absorption:
   NetCash_t = FII_Cash_t + DII_Cash_t
2. FII Derivatives & Futures Imbalance:
   DerivImbalance_t = FII_IdxFut_t + FII_StkFut_t
3. Bayesian Drift Calibration (Delta mu_whale):
   Delta_mu = clip(0.0015 * ((FII_Cash_t + 0.5 * FII_IdxFut_t) / 1000.0), -0.015, +0.015)
4. Institutional Conviction Multiplier:
   Maps net institutional absorption to a [0.85 -> 1.15] multiplier applied to Alpha composite scores.
"""

import os
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("InstitutionalFlowService")

# Local persistence path for resilient fallback when external scrapers return 403 / offline
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FLOW_HISTORY_FILE = os.path.join(DATA_DIR, "institutional_flow_history.json")


class InstitutionalFlowService:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.history = self._load_flow_history()

    def _load_flow_history(self) -> List[Dict[str, Any]]:
        """Loads historical FII/DII records from disk."""
        if not os.path.exists(FLOW_HISTORY_FILE):
            return []
        try:
            with open(FLOW_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return isinstance(data, list) and data or []
        except Exception as e:
            logger.warning(f"Failed to load institutional flow history: {e}")
            return []

    def _save_flow_history(self, records: List[Dict[str, Any]]) -> None:
        """Safely saves flow records using atomic write pattern."""
        try:
            temp_path = FLOW_HISTORY_FILE + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            os.replace(temp_path, FLOW_HISTORY_FILE)
            self.history = records
        except Exception as e:
            logger.error(f"Failed to save institutional flow history: {e}")

    def fetch_and_update_flows(self, extra_service_module=None) -> Dict[str, Any]:
        """
        Fetches fresh daily FII/DII data from extra_service (or uses existing cache),
        merges with historical logbook, and returns comprehensive institutional metrics.
        """
        raw_data = {"rows": []}
        if extra_service_module is not None and hasattr(extra_service_module, "get_fii_dii"):
            try:
                raw_data = extra_service_module.get_fii_dii()
            except Exception as e:
                logger.warning(f"extra_service.get_fii_dii failed: {e}")

        new_rows = raw_data.get("rows", [])
        if new_rows:
            # Deduplicate by date string
            existing_dates = {r.get("date") for r in self.history if r.get("date")}
            updated = list(self.history)
            added_count = 0
            for row in new_rows:
                row_date = row.get("date")
                if row_date and row_date not in existing_dates:
                    updated.append(row)
                    existing_dates.add(row_date)
                    added_count += 1
            if added_count > 0 or not self.history:
                # Sort by date descending
                updated.sort(key=lambda x: str(x.get("date", "")), reverse=True)
                # Keep up to 250 trading days
                self._save_flow_history(updated[:250])

        return self.compute_institutional_flow_metrics()

    def compute_institutional_flow_metrics(self) -> Dict[str, Any]:
        """
        Evaluates active historical logbook and computes real-time institutional whale metrics,
        Bayesian drift adjustments, and regime conviction warnings.
        """
        if not self.history:
            # Fallback default baseline if no records exist yet
            return {
                "status": "accumulating",
                "latest_date": None,
                "fii_cash_net_cr": 0.0,
                "dii_cash_net_cr": 0.0,
                "net_institutional_cash_cr": 0.0,
                "fii_derivatives_imbalance_cr": 0.0,
                "fii_5d_cash_momentum_cr": 0.0,
                "whale_drift_bps": 0.0,
                "institutional_conviction_multiplier": 1.0,
                "regime_signal": "NEUTRAL_FLOW",
                "regime_description": "Insufficient institutional flow history; operating at neutral 1.0x conviction baseline."
            }

        latest = self.history[0]
        fii_cash = float(latest.get("fiiCash") or 0.0)
        dii_cash = float(latest.get("diiCash") or 0.0)
        fii_idx_fut = float(latest.get("fiiIdxFut") or 0.0)
        fii_stk_fut = float(latest.get("fiiStkFut") or 0.0)

        net_cash = fii_cash + dii_cash
        deriv_imbalance = fii_idx_fut + fii_stk_fut

        # Calculate 5-day FII cash momentum if available
        fii_5d_sum = sum(float(r.get("fiiCash") or 0.0) for r in self.history[:5])

        # Bayesian Drift Calibration (Delta mu_whale): +/- 150 bps max clip
        # Normalized by 1000 Crores unit scale
        drift_raw = 0.0015 * ((fii_cash + 0.5 * fii_idx_fut) / 1000.0)
        whale_drift_bps = max(-150.0, min(150.0, drift_raw * 10000.0))

        # Institutional Conviction Multiplier [0.85 -> 1.15]
        # Multiplies alpha scores when institutional absorption strongly aligns with or diverges from market
        if fii_cash > 2500.0 and dii_cash > 0.0:
            conviction_mult = 1.15
            regime_signal = "INSTITUTIONAL_STRONG_ACCUMULATION"
            regime_desc = f"Heavy FII (+{fii_cash:.0f} Cr) & DII (+{dii_cash:.0f} Cr) joint buying. Alpha upside conviction boosted to 1.15x."
        elif fii_cash > 1000.0 or net_cash > 2000.0:
            conviction_mult = 1.08
            regime_signal = "INSTITUTIONAL_ACCUMULATION"
            regime_desc = f"Net positive institutional absorption (+{net_cash:.0f} Cr). Alpha conviction boosted to 1.08x."
        elif fii_cash < -4000.0 and dii_cash < abs(fii_cash) * 0.6:
            conviction_mult = 0.85
            regime_signal = "FII_EXODUS_WARNING"
            regime_desc = f"Severe FII selling (-{abs(fii_cash):.0f} Cr) outpaces DII support (+{dii_cash:.0f} Cr). Alpha conviction discounted to 0.85x."
        elif fii_cash < -1500.0:
            conviction_mult = 0.92
            regime_signal = "FII_DISTRIBUTION"
            regime_desc = f"Moderate FII selling pressure (-{abs(fii_cash):.0f} Cr). Alpha conviction discounted to 0.92x."
        else:
            conviction_mult = 1.00
            regime_signal = "NEUTRAL_FLOW"
            regime_desc = f"Balanced or mixed institutional positioning (Net: {net_cash:+.0f} Cr). Baseline 1.00x conviction applied."

        return {
            "status": "active",
            "latest_date": latest.get("date") or latest.get("displayDate"),
            "fii_cash_net_cr": round(fii_cash, 2),
            "dii_cash_net_cr": round(dii_cash, 2),
            "net_institutional_cash_cr": round(net_cash, 2),
            "fii_derivatives_imbalance_cr": round(deriv_imbalance, 2),
            "fii_5d_cash_momentum_cr": round(fii_5d_sum, 2),
            "whale_drift_bps": round(whale_drift_bps, 2),
            "institutional_conviction_multiplier": round(conviction_mult, 3),
            "regime_signal": regime_signal,
            "regime_description": regime_desc,
            "historical_sample_days": len(self.history)
        }

    def get_flow_adjusted_alpha_multiplier(self, symbol: str = "") -> float:
        """
        Returns the active institutional conviction multiplier [0.85 -> 1.15]
        to be applied to cross-sectional alpha scores in qlib_service / server.
        """
        metrics = self.compute_institutional_flow_metrics()
        return float(metrics.get("institutional_conviction_multiplier", 1.0))


# Global singleton instance
institutional_flow_service = InstitutionalFlowService()
