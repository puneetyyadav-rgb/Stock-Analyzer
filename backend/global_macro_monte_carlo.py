"""Core Global Macro Cross-Asset Monte Carlo Engine (Phase 1).

Implements:
1. 6-Asset Macro Universe (NIFTY, USDINR, CRUDE, GOLD, INDIA_VIX, US10Y).
2. Historical price fetching via `yfinance` with robust alignment and log returns.
3. Exponentially Weighted Moving Average (EWMA) Covariance Matrix (decay=0.94).
4. Ledoit-Wolf Diagonal Covariance Shrinkage (delta=0.05).
5. Cholesky Decomposition with automatic diagonal jitter for positive-definiteness.
6. Correlated Brownian Motion 10,000-Path Simulator with deterministic seed support.
7. Comprehensive output metrics: Expected Return, VaR 95/99, CVaR 95, Percentiles,
   Correlation Matrix, and Dominant Risk Driver identification.
"""

import os
import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("GlobalMacroEngine")

# Phase 1 Required Macro Asset Universe
MACRO_UNIVERSE = {
    "NIFTY": "^NSEI",
    "USDINR": "USDINR=X",
    "CRUDE": "CL=F",
    "GOLD": "GC=F",
    "INDIA_VIX": "^INDIAVIX",
    "US10Y": "^TNX"
}

ASSET_ORDER = list(MACRO_UNIVERSE.keys())

SECTOR_FACTOR_MAPPINGS = {
    "IT Services": ["USDINR", "US10Y"],
    "Banking & Finance": ["INDIA_VIX", "US10Y"],
    "Automobile": ["CRUDE", "USDINR"],
    "Energy & Oil": ["CRUDE", "USDINR"],
    "Metals & Mining": ["CRUDE", "GOLD", "USDINR"],
    "Pharma & Healthcare": ["USDINR"],
    "FMCG": ["CRUDE", "INDIA_VIX"],
    "Conglomerate": ["CRUDE", "USDINR", "INDIA_VIX"],
}


class GlobalMacroMonteCarloEngine:
    """Institutional Cross-Asset Monte Carlo Simulator for Nifty & Macro Drivers."""

    def __init__(
        self,
        n_paths: int = 10000,
        horizon_days: int = 20,
        ewma_decay: float = 0.94,
        shrinkage_delta: float = 0.05,
        seed: Optional[int] = None,
        vol_scale: float = 1.0,
        regime_override: str = "normal"
    ):
        self.n_paths = n_paths
        self.horizon_days = horizon_days
        self.ewma_decay = ewma_decay
        self.shrinkage_delta = shrinkage_delta
        self.seed = seed
        self.vol_scale = vol_scale
        self.regime_override = regime_override.lower() if regime_override else "normal"

        # State storage
        self.macro_prices: Optional[pd.DataFrame] = None
        self.macro_returns: Optional[pd.DataFrame] = None
        self.macro_means: Optional[pd.Series] = None
        self.ewma_cov: Optional[np.ndarray] = None
        self.cholesky_L: Optional[np.ndarray] = None
        self.corr_matrix: Optional[pd.DataFrame] = None

    def fetch_historical_prices(self, lookback_days: int = 500) -> pd.DataFrame:
        """Fetches historical close prices via yfinance or local disk store, incrementally updating live ticks."""
        import yfinance as yf
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        local_store_path = os.path.join(data_dir, "macro_history_2009.csv")

        end_dt = datetime.now()
        symbols = list(MACRO_UNIVERSE.values())
        inv_map = {v: k for k, v in MACRO_UNIVERSE.items()}

        try:
            local_df = None
            if os.path.exists(local_store_path):
                try:
                    local_df = pd.read_csv(local_store_path, index_col=0, parse_dates=True)
                    # Check if all required assets are present
                    if all(asset in local_df.columns for asset in ASSET_ORDER) and len(local_df) > 100:
                        last_dt = pd.to_datetime(local_df.index[-1]).date()
                        today_dt = end_dt.date()
                        if today_dt > last_dt:
                            start_fetch = last_dt + timedelta(days=1)
                            logger.info(f"Incrementally fetching new live macro data from {start_fetch} to {today_dt}...")
                            new_df = yf.download(
                                symbols,
                                start=start_fetch.strftime("%Y-%m-%d"),
                                end=end_dt.strftime("%Y-%m-%d"),
                                progress=False
                            )["Close"]
                            if isinstance(new_df, pd.DataFrame) and not new_df.empty:
                                new_df.rename(columns=inv_map, inplace=True)
                                for asset in ASSET_ORDER:
                                    if asset not in new_df.columns:
                                        new_df[asset] = local_df[asset].iloc[-1]
                                new_df = new_df[ASSET_ORDER]
                                local_df = pd.concat([local_df, new_df]).drop_duplicates().sort_index()
                                local_df = local_df.ffill().bfill().dropna()
                                local_df.to_csv(local_store_path)
                                logger.info(f"Locally stored updated macro history: {len(local_df)} rows total.")
                        else:
                            logger.info(f"Loaded {len(local_df)} historical macro rows directly from local disk store without network call.")
                    else:
                        local_df = None
                except Exception as e:
                    logger.warning(f"Error reading local macro store ({e}), re-downloading complete history.")
                    local_df = None

            if local_df is None:
                # First time: Download full deep historical dataset starting from 2009
                logger.info(f"Downloading initial full historical macro prices starting 2009-01-01 for symbols: {symbols}")
                df = yf.download(
                    symbols,
                    start="2009-01-01",
                    end=end_dt.strftime("%Y-%m-%d"),
                    progress=False
                )["Close"]
                if isinstance(df, pd.DataFrame):
                    df.rename(columns=inv_map, inplace=True)
                    for asset in ASSET_ORDER:
                        if asset not in df.columns:
                            logger.warning(f"Asset {asset} missing from download, generating synthetic proxy.")
                            df[asset] = np.linspace(100.0, 105.0, len(df))
                    df = df[ASSET_ORDER]
                    local_df = df.ffill().bfill().dropna()
                    if len(local_df) >= 60:
                        local_df.to_csv(local_store_path)
                        logger.info(f"Saved {len(local_df)} rows to local disk store: {local_store_path}")

            if local_df is None or len(local_df) < 60:
                raise ValueError("Insufficient overlapping history.")

            # Slice and return based on requested lookback_days
            if lookback_days >= 4000:
                return local_df
            else:
                return local_df.iloc[-min(lookback_days, len(local_df)):]

        except Exception as e:
            logger.warning(f"yf.download / local store failed ({e}), generating high-fidelity synthetic baseline.")
            return self._generate_synthetic_prices(lookback_days=lookback_days)

    def _generate_synthetic_prices(self, lookback_days: int = 500) -> pd.DataFrame:
        """Generates realistic correlated synthetic baseline data if offline/test mode."""
        if self.seed is not None:
            np.random.seed(self.seed)
        n_days = min(lookback_days, 300)
        dates = pd.date_range(end=datetime.now(), periods=n_days, freq="B")

        # Base covariance structure between [NIFTY, USDINR, CRUDE, GOLD, INDIA_VIX, US10Y]
        base_means = [0.0004, 0.0001, 0.0002, 0.0003, 0.0, 0.0001]
        base_stds = [0.012, 0.003, 0.020, 0.010, 0.040, 0.015]

        # Synthetic correlation matrix (Nifty vs VIX negative, Nifty vs Crude negative, etc.)
        C = np.array([
            [ 1.00, -0.20, -0.30,  0.10, -0.75, -0.35],
            [-0.20,  1.00,  0.25,  0.30,  0.40,  0.50],
            [-0.30,  0.25,  1.00,  0.20,  0.30,  0.40],
            [ 0.10,  0.30,  0.20,  1.00,  0.15, -0.10],
            [-0.75,  0.40,  0.30,  0.15,  1.00,  0.45],
            [-0.35,  0.50,  0.40, -0.10,  0.45,  1.00]
        ])
        D = np.diag(base_stds)
        cov = D @ C @ D

        shocks = np.random.multivariate_normal(base_means, cov, size=n_days)
        prices = np.zeros((n_days, len(ASSET_ORDER)))
        base_prices = [24000.0, 84.5, 78.0, 2350.0, 14.2, 4.25]
        prices[0, :] = base_prices

        for t in range(1, n_days):
            prices[t, :] = prices[t - 1, :] * np.exp(shocks[t, :])

        return pd.DataFrame(prices, index=dates, columns=ASSET_ORDER)

    def compute_log_returns(self, prices_df: pd.DataFrame) -> pd.DataFrame:
        """Computes daily log returns from price levels."""
        self.macro_prices = prices_df[ASSET_ORDER]
        log_ret = np.log(prices_df / prices_df.shift(1)).dropna()
        self.macro_returns = log_ret[ASSET_ORDER]
        self.macro_means = self.macro_returns.mean()
        return self.macro_returns

    def compute_ewma_covariance(self, returns_df: Optional[pd.DataFrame] = None) -> np.ndarray:
        """Computes EWMA covariance matrix with Ledoit-Wolf diagonal shrinkage."""
        if returns_df is not None:
            self.macro_returns = returns_df[ASSET_ORDER]
            self.macro_means = self.macro_returns.mean()
        elif self.macro_returns is None:
            prices = self.fetch_historical_prices()
            self.compute_log_returns(prices)

        ret_mat = self.macro_returns.values
        T, K = ret_mat.shape
        means = self.macro_means.values

        # EWMA weights
        weights = np.array([self.ewma_decay ** (T - 1 - t) for t in range(T)])
        weights = weights / weights.sum()

        centered = ret_mat - means
        ewma_cov = np.zeros((K, K))
        for t in range(T):
            row = centered[t, :].reshape(K, 1)
            ewma_cov += weights[t] * (row @ row.T)

        # Diagonal Shrinkage (Ledoit-Wolf style towards diagonal variance)
        diag_target = np.diag(np.diag(ewma_cov))
        shrunk_cov = (1.0 - self.shrinkage_delta) * ewma_cov + self.shrinkage_delta * diag_target

        self.ewma_cov = shrunk_cov

        # Compute Correlation Matrix for output reporting
        stds = np.sqrt(np.diag(shrunk_cov))
        outer_stds = np.outer(stds, stds)
        # Avoid division by zero
        outer_stds[outer_stds == 0] = 1e-9
        corr_arr = shrunk_cov / outer_stds
        self.corr_matrix = pd.DataFrame(corr_arr, index=ASSET_ORDER, columns=ASSET_ORDER)

        return self.ewma_cov

    def compute_cholesky(self, cov_matrix: Optional[np.ndarray] = None) -> np.ndarray:
        """Performs Cholesky decomposition L L^T = Sigma, applying diagonal jitter if needed."""
        if cov_matrix is None:
            if self.ewma_cov is None:
                self.compute_ewma_covariance()
            cov_matrix = self.ewma_cov

        K = cov_matrix.shape[0]
        try:
            self.cholesky_L = np.linalg.cholesky(cov_matrix)
        except np.linalg.LinAlgError:
            logger.warning("Covariance not strictly positive-definite during Cholesky. Injecting diagonal jitter.")
            jitter = np.eye(K) * 1e-8
            self.cholesky_L = np.linalg.cholesky(cov_matrix + jitter)

        return self.cholesky_L

    def run_simulation(self) -> Dict[str, Any]:
        """Executes the complete 10,000-path correlated simulation and calculates risk metrics."""
        if self.cholesky_L is None:
            self.compute_cholesky()

        if self.seed is not None:
            np.random.seed(self.seed)

        K = len(ASSET_ORDER)
        # Generate independent standard normal random shocks [Paths x Horizon x Assets]
        Z_indep = np.random.normal(0.0, 1.0, size=(self.n_paths, self.horizon_days, K))

        # Project via Cholesky: Z_corr = Z_indep @ L^T
        Z_corr = np.einsum("ij,mhj->mhi", self.cholesky_L, Z_indep)
        if self.vol_scale != 1.0:
            Z_corr = Z_corr * self.vol_scale

        # Simulate price paths starting from index level 100.0 for comparison
        means = self.macro_means.values.copy() if self.macro_means is not None else np.zeros(K)
        diags = np.diag(self.ewma_cov) if self.ewma_cov is not None else np.zeros(K)
        if self.vol_scale != 1.0:
            diags = diags * (self.vol_scale ** 2)

        # Apply institutional regime stress overrides to daily drift (mu)
        if self.regime_override == "crisis":
            means[0] -= 0.0015  # NIFTY -37% annualized stress
            if "INDIA_VIX" in ASSET_ORDER:
                means[ASSET_ORDER.index("INDIA_VIX")] += 0.010
        elif self.regime_override == "bull":
            means[0] += 0.0008  # NIFTY +20% annualized expansion
        elif self.regime_override == "oil_shock":
            if "CRUDE" in ASSET_ORDER:
                means[ASSET_ORDER.index("CRUDE")] += 0.0030
            means[0] -= 0.0006  # NIFTY inflation drag

        if self.macro_prices is not None and not self.macro_prices.empty:
            base_prices = self.macro_prices.iloc[-1].values
        else:
            base_prices = np.array([23880.0, 85.50, 75.50, 2400.0, 14.60, 4.30])

        paths = np.zeros((self.n_paths, self.horizon_days + 1, K))
        paths[:, 0, :] = base_prices

        for h in range(1, self.horizon_days + 1):
            # Geometric Brownian Motion step: r = (mu - 0.5*sigma^2) + shock
            step_ret = (means - 0.5 * diags) + Z_corr[:, h - 1, :]
            paths[:, h, :] = paths[:, h - 1, :] * np.exp(step_ret)

        # Analyze primary asset (NIFTY - index 0)
        nifty_term_ret = (paths[:, -1, 0] - base_prices[0]) / base_prices[0] * 100.0
        sorted_ret = np.sort(nifty_term_ret)

        exp_ret = float(np.mean(nifty_term_ret))
        var_95 = float(np.percentile(sorted_ret, 5.0))
        var_99 = float(np.percentile(sorted_ret, 1.0))
        cvar_95 = float(sorted_ret[sorted_ret <= var_95].mean()) if np.any(sorted_ret <= var_95) else var_95

        asset_path_percentiles = {}
        for asset_idx, asset_name in enumerate(ASSET_ORDER):
            base_p = float(base_prices[asset_idx])
            term_prices = paths[:, -1, asset_idx]
            term_ret = (term_prices - base_p) / base_p * 100.0

            p10_p = float(np.percentile(term_prices, 10.0))
            p50_p = float(np.percentile(term_prices, 50.0))
            p90_p = float(np.percentile(term_prices, 90.0))

            ret10 = float(np.percentile(term_ret, 10.0))
            ret50 = float(np.percentile(term_ret, 50.0))
            ret90 = float(np.percentile(term_ret, 90.0))

            asset_path_percentiles[asset_name] = {
                "base_price": round(base_p, 2),
                "p10": round(p10_p, 2),
                "p50": round(p50_p, 2),
                "p90": round(p90_p, 2),
                "return_10": round(ret10, 2),
                "return_50": round(ret50, 2),
                "return_90": round(ret90, 2)
            }

        # Identify dominant risk driver (asset with most negative correlation or highest volatility spillover)
        dominant_driver = "INDIA_VIX"
        max_risk_score = -999.0
        if self.corr_matrix is not None:
            for asset in ASSET_ORDER[1:]:
                # Check correlation to Nifty + relative volatility
                nifty_corr = float(self.corr_matrix.loc["NIFTY", asset])
                asset_idx = ASSET_ORDER.index(asset)
                asset_vol = math.sqrt(float(diags[asset_idx])) * math.sqrt(252)
                # Risk driver score: high negative correlation to Nifty OR high volatility in VIX/Crude
                risk_score = (-nifty_corr * 1.5) + (asset_vol * 2.0)
                if risk_score > max_risk_score:
                    max_risk_score = risk_score
                    dominant_driver = asset

        corr_dict = self.corr_matrix.to_dict() if self.corr_matrix is not None else {}

        return {
            "status": "success",
            "universe": ASSET_ORDER,
            "horizon_days": self.horizon_days,
            "paths_simulated": self.n_paths,
            "expected_return": round(exp_ret, 2),
            "var_95": round(var_95, 2),
            "var_99": round(var_99, 2),
            "cvar_95": round(cvar_95, 2),
            "path_percentiles": {
                "p10": asset_path_percentiles["NIFTY"]["p10"],
                "p50": asset_path_percentiles["NIFTY"]["p50"],
                "p90": asset_path_percentiles["NIFTY"]["p90"],
                "return_10": asset_path_percentiles["NIFTY"]["return_10"],
                "return_50": asset_path_percentiles["NIFTY"]["return_50"],
                "return_90": asset_path_percentiles["NIFTY"]["return_90"],
            },
            "asset_path_percentiles": asset_path_percentiles,
            "asset_correlation_matrix": corr_dict,
            "dominant_risk_driver": dominant_driver
        }

    def run_simulation_paths(self) -> np.ndarray:
        """Runs the 10,000-path macro simulation and returns the 3D price path tensor [paths x horizon+1 x assets]."""
        if self.cholesky_L is None:
            self.compute_cholesky()

        if self.seed is not None:
            np.random.seed(self.seed)

        K = len(ASSET_ORDER)
        Z_indep = np.random.normal(0.0, 1.0, size=(self.n_paths, self.horizon_days, K))
        Z_corr = np.einsum("ij,mhj->mhi", self.cholesky_L, Z_indep)

        means = self.macro_means.values if self.macro_means is not None else np.zeros(K)
        diags = np.diag(self.ewma_cov) if self.ewma_cov is not None else np.zeros(K)

        paths = np.zeros((self.n_paths, self.horizon_days + 1, K))
        paths[:, 0, :] = 100.0

        for h in range(1, self.horizon_days + 1):
            step_ret = (means - 0.5 * diags) + Z_corr[:, h - 1, :]
            paths[:, h, :] = paths[:, h - 1, :] * np.exp(step_ret)

        return paths

    def fit_asymmetric_beta(
        self,
        stock_returns: pd.Series,
        macro_returns: Optional[pd.DataFrame] = None,
        assigned_factors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Fits Upside/Downside Beta and macro factor sensitivities via OLS with robust fallback."""
        if macro_returns is None:
            if self.macro_returns is None:
                self.compute_ewma_covariance()
            macro_returns = self.macro_returns

        # Filter out missing factors cleanly (fallback requirement #3)
        if assigned_factors is None:
            assigned_factors = ["CRUDE", "USDINR"]
        valid_factors = [fac for fac in assigned_factors if fac in macro_returns.columns and fac != "NIFTY"]

        # Align stock returns with macro returns on index overlap
        aligned = pd.concat([stock_returns, macro_returns], axis=1, join="inner").dropna()

        # Insufficient history response check (fallback requirement #4)
        if len(aligned) < 20:
            logger.warning(f"Insufficient overlapping history ({len(aligned)} days). Returning safe baseline regression.")
            return {
                "status": "insufficient_history",
                "alpha": 0.0,
                "upside_beta": 1.0,
                "downside_beta": 1.0,
                "residual_volatility": 0.015,
                "macro_factor_sensitivities": {fac: 0.0 for fac in valid_factors},
                "n_observations": len(aligned)
            }

        r_stock = aligned.iloc[:, 0].values
        r_nifty = aligned["NIFTY"].values

        # Split Nifty into positive and negative regimes
        r_nifty_up = np.maximum(r_nifty, 0.0)
        r_nifty_down = np.minimum(r_nifty, 0.0)

        factor_cols = [aligned[fac].values for fac in valid_factors]
        X_list = [np.ones_like(r_stock), r_nifty_up, r_nifty_down] + factor_cols
        X_mat = np.column_stack(X_list)

        try:
            beta_vec, residuals, _, _ = np.linalg.lstsq(X_mat, r_stock, rcond=None)
        except Exception as e:
            logger.warning(f"OLS lstsq failed ({e}), returning safe baseline.")
            beta_vec = np.array([0.0, 1.0, 1.0] + [0.0] * len(valid_factors))
            residuals = r_stock - r_nifty

        alpha = float(beta_vec[0])
        up_beta = float(beta_vec[1])
        down_beta = float(beta_vec[2])
        sensitivities = {fac: round(float(beta_vec[3 + idx]), 4) for idx, fac in enumerate(valid_factors)}

        res_std = float(np.std(residuals)) if len(residuals) > 0 else 0.015

        # Extract up to 250 real daily log-return data points for Nifty vs Stock scatter plot
        scatter_sample = []
        try:
            sample_df = aligned.tail(250)
            stock_col = stock_returns.name if stock_returns.name in sample_df.columns else sample_df.columns[0]
            for idx, row in sample_df.iterrows():
                scatter_sample.append({
                    "date": str(idx.date()) if hasattr(idx, "date") else str(idx)[:10],
                    "nifty": round(float(row["NIFTY"]) * 100.0, 3),
                    "stock": round(float(row[stock_col]) * 100.0, 3)
                })
        except Exception as e:
            logger.warning(f"Failed to format scatter sample ({e})")

        return {
            "status": "success",
            "alpha": round(alpha, 6),
            "upside_beta": round(up_beta, 4),
            "downside_beta": round(down_beta, 4),
            "residual_volatility": round(res_std, 6),
            "macro_factor_sensitivities": sensitivities,
            "scatter_data": scatter_sample,
            "n_observations": len(aligned)
        }

    def simulate_stock_paths(
        self,
        stock_symbol: str,
        stock_returns: Optional[pd.Series] = None,
        assigned_factors: Optional[List[str]] = None,
        macro_paths: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """Runs conditional 10,000-path stock simulation coupled to macro drivers."""
        if macro_paths is None:
            macro_paths = self.run_simulation_paths()

        if stock_returns is None:
            # Generate synthetic stock return series if not provided or offline
            if self.seed is not None:
                np.random.seed(self.seed + 100)
            if self.macro_returns is None:
                self.compute_ewma_covariance()
            nifty_ret = self.macro_returns["NIFTY"]
            # Default synthetic stock with 1.2 up beta and 1.5 down beta
            synth_stock = (
                0.0001
                + 1.2 * np.maximum(nifty_ret, 0.0)
                + 1.5 * np.minimum(nifty_ret, 0.0)
                + np.random.normal(0, 0.012, size=len(nifty_ret))
            )
            stock_returns = pd.Series(synth_stock, index=self.macro_returns.index, name=stock_symbol)

        fit = self.fit_asymmetric_beta(
            stock_returns=stock_returns,
            macro_returns=self.macro_returns,
            assigned_factors=assigned_factors
        )

        up_beta = fit["upside_beta"]
        down_beta = fit["downside_beta"]
        alpha = fit["alpha"]
        res_vol = fit["residual_volatility"]
        sensitivities = fit["macro_factor_sensitivities"]

        # Track factor index positions in macro_paths [paths x horizon+1 x assets]
        nifty_idx = ASSET_ORDER.index("NIFTY")
        factor_indices = {fac: ASSET_ORDER.index(fac) for fac in sensitivities.keys() if fac in ASSET_ORDER}

        if self.seed is not None:
            np.random.seed(self.seed + 200)

        stock_paths = np.zeros((self.n_paths, self.horizon_days + 1))
        stock_paths[:, 0] = 100.0

        # Track factor cumulative percentage contribution across horizon
        factor_contrib_acc = {fac: np.zeros(self.n_paths) for fac in sensitivities.keys()}

        for h in range(1, self.horizon_days + 1):
            nifty_step_ret = np.log(macro_paths[:, h, nifty_idx] / macro_paths[:, h - 1, nifty_idx])
            active_beta = np.where(nifty_step_ret >= 0.0, up_beta, down_beta)

            factor_step_sum = np.zeros(self.n_paths)
            for fac, f_idx in factor_indices.items():
                fac_ret = np.log(macro_paths[:, h, f_idx] / macro_paths[:, h - 1, f_idx])
                contrib = sensitivities[fac] * fac_ret
                factor_step_sum += contrib
                factor_contrib_acc[fac] += contrib

            idio_noise = np.random.normal(0.0, res_vol, size=self.n_paths)
            total_step_ret = alpha + active_beta * nifty_step_ret + factor_step_sum + idio_noise
            stock_paths[:, h] = stock_paths[:, h - 1] * np.exp(total_step_ret)

        terminal_ret = (stock_paths[:, -1] - 100.0) / 100.0 * 100.0
        sorted_ret = np.sort(terminal_ret)

        exp_move = float(np.mean(terminal_ret))
        var_95 = float(np.percentile(sorted_ret, 5.0))
        var_99 = float(np.percentile(sorted_ret, 1.0))
        cvar_95 = float(sorted_ret[sorted_ret <= var_95].mean()) if np.any(sorted_ret <= var_95) else var_95

        prob_loss = float(np.mean(terminal_ret < 0.0) * 100.0)
        prob_large_drawdown = float(np.mean(terminal_ret <= -5.0) * 100.0)

        # Average contribution per factor in percentage terms across all paths
        avg_factor_contrib = {fac: round(float(np.mean(arr) * 100.0), 3) for fac, arr in factor_contrib_acc.items()}

        # Create 30 histogram bins across terminal_ret for probability density visualization
        counts, bin_edges = np.histogram(terminal_ret, bins=30)
        return_distribution = [
            {
                "ret": round(float((bin_edges[i] + bin_edges[i + 1]) / 2.0), 2),
                "count": int(counts[i]),
                "density": round(float(counts[i] / len(terminal_ret) * 100.0), 2)
            }
            for i in range(len(counts))
        ]

        return {
            "symbol": stock_symbol,
            "status": fit["status"],
            "horizon_days": self.horizon_days,
            "paths_simulated": self.n_paths,
            "expected_stock_move": round(exp_move, 2),
            "downside_var": {
                "var95": round(var_95, 2),
                "var99": round(var_99, 2)
            },
            "downside_cvar": round(cvar_95, 2),
            "upside_beta": round(up_beta, 3),
            "downside_beta": round(down_beta, 3),
            "macro_factor_contribution": avg_factor_contrib,
            "macro_factor_sensitivities": fit.get("macro_factor_sensitivities", {}),
            "scatter_data": fit.get("scatter_data", []),
            "return_distribution": return_distribution,
            "probability_of_loss": round(prob_loss, 1),
            "probability_of_large_drawdown": round(prob_large_drawdown, 1)
        }
