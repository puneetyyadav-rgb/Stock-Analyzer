import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest
from global_macro_monte_carlo import GlobalMacroMonteCarloEngine

def test_vol_scale_multiplier_impact():
    """Verify that vol_scale > 1.0 expands the simulated Value at Risk (VaR)."""
    engine_base = GlobalMacroMonteCarloEngine(n_paths=2000, horizon_days=20, seed=42, vol_scale=1.0)
    res_base = engine_base.run_simulation()
    
    engine_high_vol = GlobalMacroMonteCarloEngine(n_paths=2000, horizon_days=20, seed=42, vol_scale=2.0)
    res_high_vol = engine_high_vol.run_simulation()
    
    # Higher vol multiplier should produce a more negative (worse) VaR 95%
    assert res_high_vol["var_95"] < res_base["var_95"], f"Expected higher vol ({res_high_vol['var_95']}) to be worse than base ({res_base['var_95']})"
    assert res_high_vol["var_99"] < res_base["var_99"], f"Expected higher 99% VaR ({res_high_vol['var_99']}) to be worse than base ({res_base['var_99']})"

def test_regime_override_impact():
    """Verify that regime_override='crisis' drastically lowers expected return vs normal."""
    engine_normal = GlobalMacroMonteCarloEngine(n_paths=2000, horizon_days=20, seed=42, regime_override="normal")
    res_normal = engine_normal.run_simulation()
    
    engine_crisis = GlobalMacroMonteCarloEngine(n_paths=2000, horizon_days=20, seed=42, regime_override="crisis")
    res_crisis = engine_crisis.run_simulation()
    
    assert res_crisis["expected_return"] < res_normal["expected_return"], (
        f"Expected crisis return ({res_crisis['expected_return']}) < normal ({res_normal['expected_return']})"
    )
