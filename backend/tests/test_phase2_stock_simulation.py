"""Unit tests for Phase 2 Stock Beta-Coupled Simulation.

Verifies:
1. Synthetic stock with known symmetric/asymmetric beta.
2. Downside beta higher than upside beta case.
3. Missing macro asset fallback check.
4. Insufficient history response check.
"""

import sys
import os
import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from global_macro_monte_carlo import GlobalMacroMonteCarloEngine, ASSET_ORDER


@pytest.fixture
def engine():
    eng = GlobalMacroMonteCarloEngine(n_paths=500, horizon_days=10, seed=42)
    # Pre-populate synthetic macro data for fast/deterministic testing
    eng.compute_ewma_covariance(returns_df=eng.compute_log_returns(eng._generate_synthetic_prices(lookback_days=250)))
    return eng


def test_synthetic_stock_known_beta(engine):
    """Verifies OLS estimation accurately recovers synthetic up/down beta values (~1.2)."""
    nifty = engine.macro_returns["NIFTY"]
    np.random.seed(1234)
    # R_stock = 0.0 + 1.2 * max(R_nifty, 0) + 1.2 * min(R_nifty, 0) + tiny noise
    synth_ret = 1.2 * np.maximum(nifty, 0.0) + 1.2 * np.minimum(nifty, 0.0) + np.random.normal(0, 1e-5, len(nifty))
    stock_s = pd.Series(synth_ret, index=engine.macro_returns.index, name="SYNTH_KNOWN")

    fit = engine.fit_asymmetric_beta(stock_s, assigned_factors=[])
    assert fit["status"] == "success"
    assert abs(fit["upside_beta"] - 1.20) < 0.05, f"Upside beta expected ~1.20, got {fit['upside_beta']}"
    assert abs(fit["downside_beta"] - 1.20) < 0.05, f"Downside beta expected ~1.20, got {fit['downside_beta']}"


def test_downside_beta_higher_than_upside_case(engine):
    """Verifies asymmetric estimation when downside beta (1.8) strictly exceeds upside beta (0.8)."""
    nifty = engine.macro_returns["NIFTY"]
    np.random.seed(5678)
    synth_ret = 0.8 * np.maximum(nifty, 0.0) + 1.8 * np.minimum(nifty, 0.0) + np.random.normal(0, 1e-4, len(nifty))
    stock_s = pd.Series(synth_ret, index=engine.macro_returns.index, name="SYNTH_ASYMMETRIC")

    sim = engine.simulate_stock_paths("SYNTH_ASYMMETRIC", stock_returns=stock_s, assigned_factors=[])
    assert sim["status"] == "success"
    assert sim["downside_beta"] > sim["upside_beta"], f"Downside beta ({sim['downside_beta']}) must exceed upside beta ({sim['upside_beta']})"
    assert sim["probability_of_large_drawdown"] >= 0.0


def test_missing_macro_asset_fallback(engine):
    """Verifies that requesting a non-existent macro factor cleanly falls back without crashing."""
    nifty = engine.macro_returns["NIFTY"]
    stock_s = pd.Series(nifty * 1.1, index=engine.macro_returns.index, name="SYNTH_FALLBACK")

    # Pass valid CRUDE and non-existent FAKE_FACTOR_XYZ
    sim = engine.simulate_stock_paths(
        "SYNTH_FALLBACK",
        stock_returns=stock_s,
        assigned_factors=["CRUDE", "FAKE_FACTOR_XYZ"]
    )
    assert sim["status"] == "success"
    assert "CRUDE" in sim["macro_factor_contribution"]
    assert "FAKE_FACTOR_XYZ" not in sim["macro_factor_contribution"]


def test_insufficient_history_response(engine):
    """Verifies that passing <20 overlapping days returns clean insufficient_history status instead of throwing exception."""
    nifty = engine.macro_returns["NIFTY"]
    # Only pass 10 days of history
    tiny_stock = pd.Series(nifty.iloc[:10] * 1.0, index=engine.macro_returns.index[:10], name="TINY_STOCK")

    fit = engine.fit_asymmetric_beta(tiny_stock, assigned_factors=["CRUDE"])
    assert fit["status"] == "insufficient_history"
    assert fit["upside_beta"] == 1.0 and fit["downside_beta"] == 1.0
    assert fit["n_observations"] == 10
