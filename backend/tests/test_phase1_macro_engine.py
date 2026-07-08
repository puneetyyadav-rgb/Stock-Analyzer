"""Unit tests for Phase 1 Core Macro Monte Carlo Engine.

Verifies:
1. Synthetic covariance check.
2. Positive-definite covariance and Cholesky check.
3. Deterministic seed repeatability.
4. Output dictionary shape and exact keys check.
"""

import pytest
import numpy as np
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from global_macro_monte_carlo import GlobalMacroMonteCarloEngine, ASSET_ORDER


def test_synthetic_covariance():
    """Verifies EWMA covariance generation produces a valid 6x6 matrix with positive variance diagonal."""
    engine = GlobalMacroMonteCarloEngine(n_paths=500, horizon_days=10, seed=123)
    # Force use of synthetic price generator for deterministic unit testing
    synth_prices = engine._generate_synthetic_prices(lookback_days=200)
    assert synth_prices.shape[1] == 6, "Synthetic universe must contain exactly 6 macro assets"
    assert list(synth_prices.columns) == ASSET_ORDER

    cov = engine.compute_ewma_covariance(returns_df=engine.compute_log_returns(synth_prices))
    assert cov.shape == (6, 6), "Covariance matrix must be 6x6"
    for i in range(6):
        assert cov[i, i] > 0, f"Diagonal variance for asset {ASSET_ORDER[i]} must be strictly positive"


def test_positive_definite_covariance():
    """Verifies that Cholesky decomposition L L^T reconstructs covariance without LinAlgError."""
    engine = GlobalMacroMonteCarloEngine(n_paths=500, horizon_days=10, seed=123)
    synth_prices = engine._generate_synthetic_prices(lookback_days=200)
    cov = engine.compute_ewma_covariance(returns_df=engine.compute_log_returns(synth_prices))

    # Compute Cholesky L
    L = engine.compute_cholesky(cov_matrix=cov)
    assert L.shape == (6, 6)

    # Check lower triangular property
    assert np.allclose(L, np.tril(L)), "Cholesky matrix L must be lower-triangular"

    # Check reconstruction accuracy L @ L.T approx equal to cov
    reconstructed = L @ L.T
    assert np.allclose(cov, reconstructed, atol=1e-5), "L @ L.T must reconstruct the covariance matrix"


def test_deterministic_seed():
    """Verifies that running two simulations with identical seeds yields identical numerical metrics."""
    engine_a = GlobalMacroMonteCarloEngine(n_paths=1000, horizon_days=15, seed=999)
    res_a = engine_a.run_simulation()

    engine_b = GlobalMacroMonteCarloEngine(n_paths=1000, horizon_days=15, seed=999)
    res_b = engine_b.run_simulation()

    assert res_a["expected_return"] == res_b["expected_return"], "Expected return mismatch with identical seeds"
    assert res_a["var_95"] == res_b["var_95"], "VaR 95 mismatch with identical seeds"
    assert res_a["cvar_95"] == res_b["cvar_95"], "CVaR 95 mismatch with identical seeds"
    assert res_a["path_percentiles"]["p50"] == res_b["path_percentiles"]["p50"], "Percentile p50 mismatch"


def test_output_shape_and_keys():
    """Verifies exact output schema required by Phase 1 specification."""
    engine = GlobalMacroMonteCarloEngine(n_paths=500, horizon_days=10, seed=42)
    result = engine.run_simulation()

    assert isinstance(result, dict)
    required_keys = [
        "expected_return",
        "var_95",
        "var_99",
        "cvar_95",
        "path_percentiles",
        "asset_correlation_matrix",
        "dominant_risk_driver"
    ]
    for k in required_keys:
        assert k in result, f"Required key '{k}' missing from engine output dict"

    # Verify nested types
    assert isinstance(result["path_percentiles"], dict)
    assert "p10" in result["path_percentiles"] and "p50" in result["path_percentiles"] and "p90" in result["path_percentiles"]

    assert isinstance(result["asset_correlation_matrix"], dict)
    assert "NIFTY" in result["asset_correlation_matrix"]

    assert isinstance(result["dominant_risk_driver"], str)
    assert result["dominant_risk_driver"] in ASSET_ORDER
