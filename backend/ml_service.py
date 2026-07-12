import yfinance as yf
import pandas as pd
import numpy as np
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def _run_monte_carlo(current_price: float, mu: float, sigma: float, days: int, num_simulations: int = 1000) -> np.ndarray:
    """
    Returns a numpy array of shape (num_simulations, days)
    Simulates Geometric Brownian Motion.
    """
    dt = 1 # 1 day step
    # Precompute the drift term
    drift = (mu - 0.5 * sigma**2) * dt
    # Generate random shocks for all paths and all days at once
    Z = np.random.normal(0, 1, (num_simulations, days))
    # Daily returns multiplier
    daily_returns = np.exp(drift + sigma * np.sqrt(dt) * Z)
    
    # Cumulative product to get price paths
    price_paths = np.zeros_like(daily_returns)
    price_paths[:, 0] = current_price * daily_returns[:, 0]
    for t in range(1, days):
        price_paths[:, t] = price_paths[:, t-1] * daily_returns[:, t]
        
    return price_paths

def generate_ml_prediction(symbol: str) -> dict:
    try:
        # 1. Fetch Data with Automatic .BO -> .NS Fallback
        clean_s = symbol.strip().upper()
        ticker_sym = clean_s if clean_s.endswith(".NS") or clean_s.endswith(".BO") else f"{clean_s}.NS"
        ticker = yf.Ticker(ticker_sym)
        df = ticker.history(period="2y", auto_adjust=True)
        
        # Automatic BSE (.BO) fallback to NSE (.NS) if data is missing or <100 rows
        if (df.empty or len(df) < 100) and ticker_sym.endswith(".BO"):
            nse_proxy = ticker_sym[:-3] + ".NS"
            logger.info(f"BSE ticker {ticker_sym} has <100 rows for ML Forecast. Auto-falling back to {nse_proxy}...")
            df_nse = yf.Ticker(nse_proxy).history(period="2y", auto_adjust=True)
            if not df_nse.empty and len(df_nse) >= 50:
                df = df_nse
                logger.info(f"Retrieved {len(df)} clean rows from {nse_proxy}.")
                
        if df.empty or len(df) < 50:
            return {"error": "Not enough historical data for ML prediction."}
        
        df = df.reset_index()
        date_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
        df = df.rename(columns={date_col: 'date'})
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # Calculate daily log returns for the Monte Carlo model
        df['log_return'] = np.log(df['Close'] / df['Close'].shift(1))
        df_clean = df.dropna().copy()
        
        if len(df_clean) < 50:
            return {"error": "Not enough data."}
            
        # 2. Robust Backtesting across 10 rolling windows
        test_days = 30
        num_windows = min(10, (len(df_clean) - 60) // test_days)
        if num_windows < 1:
            num_windows = 1
            
        mapes = []
        coverages = []
        
        # Loop over historical windows from oldest to newest
        for i in range(num_windows):
            # Window slicing
            end_idx = len(df_clean) - (test_days * i)
            start_idx = end_idx - test_days
            
            # Data strictly before the test window to prevent lookahead bias
            train_df = df_clean.iloc[:start_idx]
            test_df = df_clean.iloc[start_idx:end_idx]
            
            if len(train_df) < 30:
                continue
                
            train_mu = train_df['log_return'].mean()
            train_sigma = train_df['log_return'].std()
            bt_start_price = train_df.iloc[-1]['Close']
            
            bt_sims = _run_monte_carlo(bt_start_price, train_mu, train_sigma, test_days, num_simulations=1000)
            bt_median_path = np.median(bt_sims, axis=0)
            bt_lower_bound = np.percentile(bt_sims, 10, axis=0)
            bt_upper_bound = np.percentile(bt_sims, 90, axis=0)
            
            actuals = test_df['Close'].values
            
            # Metric 1: Median accuracy (MAPE)
            window_mape = np.mean(np.abs((actuals - bt_median_path) / actuals)) * 100
            mapes.append(window_mape)
            
            # Metric 2: Coverage (How often did reality land inside the 80% band?)
            inside_band = (actuals >= bt_lower_bound) & (actuals <= bt_upper_bound)
            window_coverage = np.mean(inside_band) * 100
            coverages.append(window_coverage)
            
        avg_mape = np.mean(mapes) if mapes else 0.0
        avg_coverage = np.mean(coverages) if coverages else 0.0
        backtest_accuracy = max(0, 100 - avg_mape)
        
        # 3. Final Future Forecast (Coupled with 10,000-Path Cholesky Macro Engine)
        full_mu = df_clean['log_return'].mean()
        full_sigma = df_clean['log_return'].std()
        current_price = df_clean.iloc[-1]['Close']
        last_date = pd.to_datetime(df_clean.iloc[-1]['date'])
        
        # Couple with Tier 2 Cholesky Global Macro Simulation Engine for maximum institutional accuracy
        macro_coupling = {}
        try:
            import macro_service as ms
            macro_res = ms.get_beta_coupled_simulation(clean_s, horizon_days=30, paths=10000, lookback=252)
            if isinstance(macro_res, dict) and macro_res.get("status") == "success":
                up_b = macro_res.get("upside_beta", 1.0)
                down_b = macro_res.get("downside_beta", 1.0)
                macro_move = macro_res.get("expected_stock_move", 0.0) / 100.0
                macro_cvar = macro_res.get("downside_cvar", 0.0)
                macro_coupling = {
                    "upsideBeta": round(up_b, 2) if up_b is not None else 1.0,
                    "downsideBeta": round(down_b, 2) if down_b is not None else 1.0,
                    "macroExpectedMovePct": round(macro_move * 100.0, 2),
                    "choleskyCVaR95": round(macro_cvar, 2),
                    "engineSource": "10,000-Path Cholesky Macro Coupled Engine"
                }
                # Adjust expected drift using macro conditioning
                if abs(macro_move) < 0.20:
                    full_mu = (full_mu * 0.5) + ((macro_move / 30.0) * 0.5)
        except Exception as e_m:
            logger.warning(f"Cholesky macro coupling warning inside ML Forecast: {e_m}")
        
        # Scenario A: Historical & Macro Coupled Drift
        future_sims = _run_monte_carlo(current_price, full_mu, full_sigma, 30, num_simulations=1000)
        median_path = np.median(future_sims, axis=0)
        lower_bound = np.percentile(future_sims, 10, axis=0)
        upper_bound = np.percentile(future_sims, 90, axis=0)
        
        # Scenario B: Zero Drift (Pure Volatility)
        future_sims_zero = _run_monte_carlo(current_price, 0.0, full_sigma, 30, num_simulations=1000)
        median_path_zero = np.median(future_sims_zero, axis=0)
        
        # Pick 5 random paths from the primary simulation for visual texture
        random_indices = np.random.choice(1000, 5, replace=False)
        sample_paths_array = future_sims[random_indices] # shape (5, 30)
        
        # 4. Format Output
        hist_slice = df.tail(60)[['date', 'Close']].rename(columns={'Close': 'close'})
        historical_data = hist_slice.to_dict(orient='records')
        
        forecast_data = []
        for i in range(30):
            future_date = last_date + timedelta(days=i + 1)
            day_data = {
                "date": future_date.strftime('%Y-%m-%d'),
                "forecast": round(median_path[i], 2),
                "forecastZeroDrift": round(median_path_zero[i], 2),
                "lowerBound": round(lower_bound[i], 2),
                "upperBound": round(upper_bound[i], 2)
            }
            # Add sample paths (path1, path2... path5)
            for j in range(5):
                day_data[f"path{j+1}"] = round(sample_paths_array[j][i], 2)
                
            forecast_data.append(day_data)
            
        # Determine trend signal based on historical drift model
        price_30d = forecast_data[-1]['forecast']
        pct_change_30d = ((price_30d - current_price) / current_price) * 100
        
        if pct_change_30d > 2:
            trend_signal = "BULLISH BREAKOUT (Macro Coupled)"
        elif pct_change_30d < -2:
            trend_signal = "BEARISH DRIFT (Macro Coupled)"
        else:
            trend_signal = "NEUTRAL CONSOLIDATION"

        return {
            "backtestAccuracy": round(backtest_accuracy, 1),
            "mape": round(avg_mape, 2),
            "bandCoverage": round(avg_coverage, 1),
            "historical": historical_data,
            "forecast": forecast_data,
            "trendSignal": trend_signal,
            "currentPrice": round(current_price, 2),
            "projected7D": round(forecast_data[6]['forecast'], 2),
            "projected30D": round(price_30d, 2),
            "macroCoupledMetrics": macro_coupling
        }
        
    except Exception as e:
        logger.error(f"ML Predictor Error: {e}")
        return {"error": str(e)}
