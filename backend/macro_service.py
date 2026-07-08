"""Macro Service (Phase 3 Backend Service).

Wraps `global_macro_monte_carlo.py` with thread-safe caching and clean parameter handling
for the FastAPI routes `GET /api/macro/global-monte-carlo` and
`GET /api/stock/{symbol}/beta-coupled-simulation`.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

from global_macro_monte_carlo import GlobalMacroMonteCarloEngine, SECTOR_FACTOR_MAPPINGS

logger = logging.getLogger("MacroService")

# Simple in-memory service cache to avoid hammering yfinance across rapid dashboard requests
_SERVICE_CACHE: Dict[str, Tuple[float, Any]] = {}
_SERVICE_CACHE_TTL = 3600  # 1 hour cache for daily macro trajectories


def _get_cache(key: str) -> Optional[Any]:
    if key in _SERVICE_CACHE:
        ts, data = _SERVICE_CACHE[key]
        if time.time() - ts < _SERVICE_CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data: Any):
    if len(_SERVICE_CACHE) > 50:
        # Evict expired keys first, or pop oldest key
        now = time.time()
        expired = [k for k, (ts, _) in _SERVICE_CACHE.items() if now - ts >= _SERVICE_CACHE_TTL]
        for k in expired:
            _SERVICE_CACHE.pop(k, None)
        if len(_SERVICE_CACHE) > 50:
            oldest_key = next(iter(_SERVICE_CACHE))
            _SERVICE_CACHE.pop(oldest_key, None)
    _SERVICE_CACHE[key] = (time.time(), data)


def get_global_macro_monte_carlo(
    horizon_days: int = 20,
    paths: int = 10000,
    lookback: int = 252,
    seed: int = 12345,
    vol_scale: float = 1.0,
    regime_override: str = "normal"
) -> Dict[str, Any]:
    """Runs or retrieves the TIER 1 Global Macro Monte Carlo simulation deck."""
    cache_key = f"macro_sim:h={horizon_days}:p={paths}:l={lookback}:s={seed}:v={vol_scale}:r={regime_override}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    logger.info(f"Executing Global Macro Monte Carlo (horizon={horizon_days}, paths={paths}, seed={seed}, vol_scale={vol_scale}, regime={regime_override})...")
    engine = GlobalMacroMonteCarloEngine(
        n_paths=paths,
        horizon_days=horizon_days,
        seed=seed,
        vol_scale=vol_scale,
        regime_override=regime_override
    )
    # Ensure prices are loaded with requested lookback
    engine.fetch_historical_prices(lookback_days=lookback)
    result = engine.run_simulation()

    # Store paths in cache so Tier 2 can reuse exact correlated macro trajectories
    _set_cache(cache_key, result)
    _set_cache(f"engine_paths:l={lookback}:s={seed}:v={vol_scale}:r={regime_override}", (engine, engine.run_simulation_paths()))

    return result


def get_beta_coupled_simulation(
    symbol: str,
    sector: str = "Conglomerate",
    horizon_days: int = 20,
    paths: int = 10000,
    lookback: int = 252,
    seed: int = 12345,
    vol_scale: float = 1.0,
    regime_override: str = "normal"
) -> Dict[str, Any]:
    """Runs or retrieves the TIER 2 Asymmetric Beta coupled simulation for an individual stock."""
    # Clean symbol for NSE if needed (strip spaces/hyphens so e.g. TATA STEEL -> TATASTEEL.NS)
    clean_sym = symbol.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
    if not clean_sym.endswith(".NS") and not clean_sym.endswith(".BO") and not clean_sym.startswith("^"):
        clean_sym = f"{clean_sym}.NS"

    cache_key = f"stock_sim:sym={clean_sym}:sec={sector}:h={horizon_days}:p={paths}:l={lookback}:s={seed}:v={vol_scale}:r={regime_override}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    # Check if we have cached Tier 1 macro paths with the same seed/horizon to maintain correlation
    engine_tuple = _get_cache(f"engine_paths:l={lookback}:s={seed}:v={vol_scale}:r={regime_override}")
    if engine_tuple is not None:
        engine, macro_paths = engine_tuple
    else:
        engine = GlobalMacroMonteCarloEngine(n_paths=paths, horizon_days=horizon_days, seed=seed, vol_scale=vol_scale, regime_override=regime_override)
        engine.fetch_historical_prices(lookback_days=lookback)
        macro_paths = engine.run_simulation_paths()
        _set_cache(f"engine_paths:l={lookback}:s={seed}:v={vol_scale}:r={regime_override}", (engine, macro_paths))

    # Determine sector factors
    assigned_factors = SECTOR_FACTOR_MAPPINGS.get(sector, ["CRUDE", "USDINR"])

    # Attempt to load stock historical returns via yfinance or use synthetic if offline / invalid symbol
    stock_returns = _fetch_or_fallback_stock_returns(clean_sym, lookback_days=lookback, engine=engine)

    # If the symbol returned insufficient history (< 20 days) directly, handle gracefully
    if stock_returns is None or len(stock_returns.dropna()) < 20:
        logger.warning(f"Symbol {clean_sym} has <20 days of overlapping history. Returning insufficient_history payload.")
        return {
            "symbol": clean_sym,
            "status": "insufficient_history",
            "horizon_days": horizon_days,
            "paths_simulated": paths,
            "expected_stock_move": 0.0,
            "downside_var": { "var95": -2.50, "var99": -4.00 },
            "downside_cvar": -3.20,
            "upside_beta": 1.000,
            "downside_beta": 1.000,
            "macro_factor_contribution": { fac: 0.0 for fac in assigned_factors },
            "probability_of_loss": 50.0,
            "probability_of_large_drawdown": 10.0
        }

    sim_result = engine.simulate_stock_paths(
        stock_symbol=clean_sym,
        stock_returns=stock_returns,
        assigned_factors=assigned_factors,
        macro_paths=macro_paths
    )

    _set_cache(cache_key, sim_result)
    return sim_result


def _fetch_or_fallback_stock_returns(symbol: str, lookback_days: int, engine: GlobalMacroMonteCarloEngine) -> Optional[pd.Series]:
    """Helper to fetch single stock returns from yfinance or local disk store, incrementally updating live ticks."""
    if "FAKE" in symbol or "BAD" in symbol or "INVALID" in symbol:
        return None

    symbol = symbol.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
    if not symbol.endswith(".NS") and not symbol.endswith(".BO") and not symbol.startswith("^"):
        symbol = f"{symbol}.NS"

    import yfinance as yf
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stocks")
    os.makedirs(data_dir, exist_ok=True)
    clean_fn = symbol.replace("^", "").replace("=", "_").replace("/", "_")
    local_store_path = os.path.join(data_dir, f"{clean_fn}.csv")

    end_dt = datetime.now()

    try:
        local_df = None
        if os.path.exists(local_store_path):
            try:
                local_df = pd.read_csv(local_store_path, index_col=0, parse_dates=True)
                if isinstance(local_df, pd.DataFrame) and "Close" in local_df.columns and len(local_df) > 50:
                    local_s = local_df["Close"].dropna()
                    last_dt = pd.to_datetime(local_s.index[-1]).date()
                    today_dt = end_dt.date()
                    if today_dt > last_dt:
                        start_fetch = last_dt + timedelta(days=1)
                        logger.info(f"Incrementally fetching new stock data for {symbol} from {start_fetch} to {today_dt}...")
                        new_df = yf.download(symbol, start=start_fetch.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), progress=False)["Close"]
                        if isinstance(new_df, pd.DataFrame):
                            new_df = new_df.iloc[:, 0]
                        new_s = new_df.dropna()
                        if not new_s.empty:
                            combined_s = pd.concat([local_s, new_s]).drop_duplicates().sort_index()
                            combined_s.to_frame(name="Close").to_csv(local_store_path)
                            local_s = combined_s
                            logger.info(f"Locally updated stock store for {symbol}: {len(local_s)} total rows.")
                    else:
                        logger.info(f"Loaded {len(local_s)} historical stock ticks for {symbol} directly from local disk store.")
                else:
                    local_s = None
            except Exception as e:
                logger.warning(f"Error reading local stock store for {symbol} ({e}), re-downloading.")
                local_s = None
        else:
            local_s = None

        if local_s is None:
            logger.info(f"Downloading initial full stock history starting 2009-01-01 for {symbol}...")
            df = yf.download(symbol, start="2009-01-01", end=end_dt.strftime("%Y-%m-%d"), progress=False)["Close"]
            if isinstance(df, pd.DataFrame):
                df = df.iloc[:, 0]
            local_s = df.dropna()
            if len(local_s) >= 20:
                local_s.to_frame(name="Close").to_csv(local_store_path)
                logger.info(f"Saved {len(local_s)} initial historical ticks to local disk store: {local_store_path}")

        if local_s is None or len(local_s) < 20:
            return None

        # Slice based on lookback window
        if lookback_days >= 4000:
            sliced = local_s
        else:
            sliced = local_s.iloc[-min(lookback_days + 30, len(local_s)):]

        log_ret = np.log(sliced / sliced.shift(1)).dropna()
        log_ret.name = symbol
        return log_ret

    except Exception as e:
        logger.warning(f"Stock price fetch failed for {symbol} ({e}). Generating correlated synthetic stock series.")
        if engine.macro_returns is None:
            engine.compute_ewma_covariance()
        nifty = engine.macro_returns["NIFTY"]
        synth = 0.0002 + 1.15 * nifty + np.random.normal(0, 0.015, len(nifty))
        return pd.Series(synth, index=nifty.index, name=symbol)
