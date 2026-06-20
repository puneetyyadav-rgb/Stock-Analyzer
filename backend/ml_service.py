import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Basic technical indicators
    df['sma_5'] = df['Close'].rolling(window=5).mean()
    df['sma_20'] = df['Close'].rolling(window=20).mean()
    df['sma_50'] = df['Close'].rolling(window=50).mean()
    df['rsi'] = _compute_rsi(df['Close'], 14)
    
    # Lagged features to capture momentum
    df['lag_1'] = df['Close'].shift(1)
    df['lag_2'] = df['Close'].shift(2)
    df['lag_3'] = df['Close'].shift(3)
    df['lag_5'] = df['Close'].shift(5)
    
    # Rolling volatility (standard deviation of daily returns)
    daily_returns = df['Close'].pct_change()
    df['volatility_20'] = daily_returns.rolling(window=20).std()
    
    # Target: Tomorrow's close
    df['target'] = df['Close'].shift(-1)
    
    return df

def _recursive_predict(model, last_row: pd.Series, steps: int) -> list:
    """Predict future steps recursively using a single trained model."""
    predictions = []
    current_features = last_row.copy()
    
    # History queues for moving averages & lags
    # For a robust approach, we will simulate the lagged features over `steps` days.
    # To keep it simple, we use a naive carry-forward for long-term indicators (SMA50)
    # and update short-term lags directly.
    history_close = [current_features['lag_5'], current_features['lag_3'], current_features['lag_2'], current_features['lag_1'], current_features['Close']]
    
    for i in range(steps):
        # Prepare feature vector for prediction
        # Feature columns must match training exactly:
        features = ['sma_5', 'sma_20', 'sma_50', 'rsi', 'lag_1', 'lag_2', 'lag_3', 'lag_5', 'volatility_20']
        x = current_features[features].to_frame().T
        
        # Predict tomorrow
        next_close = float(model.predict(x)[0])
        predictions.append(next_close)
        
        # Update history
        history_close.append(next_close)
        history_close.pop(0) # Keep 5 elements
        
        # Update current_features for the next step
        current_features['lag_5'] = history_close[0]
        current_features['lag_3'] = history_close[2]
        current_features['lag_2'] = history_close[3]
        current_features['lag_1'] = history_close[4]
        current_features['Close'] = next_close
        
        # Naive update of SMAs (just blending new value slightly)
        current_features['sma_5'] = (current_features['sma_5'] * 4 + next_close) / 5
        current_features['sma_20'] = (current_features['sma_20'] * 19 + next_close) / 20
        # keep sma_50, rsi, and volatility relatively constant to avoid wild extrapolations
        
    return predictions

def generate_ml_prediction(symbol: str) -> dict:
    try:
        # 1. Fetch Data
        ticker = yf.Ticker(symbol if symbol.endswith(".NS") or symbol.endswith(".BO") else f"{symbol}.NS")
        df = ticker.history(period="2y", auto_adjust=True)
        if df.empty or len(df) < 100:
            return {"error": "Not enough historical data for ML prediction."}
        
        df = df.reset_index()
        # Ensure column names are standard
        date_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
        df = df.rename(columns={date_col: 'date'})
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # 2. Feature Engineering
        df_feat = _prepare_features(df)
        df_clean = df_feat.dropna().copy()
        
        if len(df_clean) < 50:
            return {"error": "Not enough data after feature engineering."}
            
        features = ['sma_5', 'sma_20', 'sma_50', 'rsi', 'lag_1', 'lag_2', 'lag_3', 'lag_5', 'volatility_20']
        
        # 3. Backtesting (Hold out last 30 days)
        test_days = 30
        train_df = df_clean.iloc[:-test_days]
        test_df = df_clean.iloc[-test_days:]
        
        model_bt = Ridge(alpha=1.0)
        model_bt.fit(train_df[features], train_df['target'])
        
        # Predict the 30-day test set recursively
        bt_last_row = train_df.iloc[-1]
        bt_predictions = _recursive_predict(model_bt, bt_last_row, test_days)
        
        actuals = test_df['Close'].values
        # Calculate MAPE (Mean Absolute Percentage Error)
        mape = np.mean(np.abs((actuals - bt_predictions) / actuals)) * 100
        backtest_accuracy = max(0, 100 - mape)
        
        # 4. Final Future Forecast (Train on ALL data)
        model_final = Ridge(alpha=1.0)
        model_final.fit(df_clean[features], df_clean['target'])
        
        last_row = df_clean.iloc[-1]
        future_predictions = _recursive_predict(model_final, last_row, 30)
        
        # Calculate daily volatility for the confidence cone
        daily_returns = df_clean['Close'].pct_change().dropna()
        std_dev = daily_returns.std()
        
        # 5. Format Output
        last_date = pd.to_datetime(last_row['date'])
        
        # Historical slice (last 60 days for charting)
        hist_slice = df.tail(60)[['date', 'Close']].rename(columns={'Close': 'close'})
        historical_data = hist_slice.to_dict(orient='records')
        
        forecast_data = []
        current_price = last_row['Close']
        
        for i, pred_price in enumerate(future_predictions):
            # Calendar days forward
            future_date = last_date + timedelta(days=i + 1)
            # Confidence cone widens over time (sqrt(t))
            # Z = 1.645 for 90% confidence interval
            cone_width = current_price * (1.645 * std_dev * np.sqrt(i + 1))
            
            forecast_data.append({
                "date": future_date.strftime('%Y-%m-%d'),
                "forecast": round(pred_price, 2),
                "lowerBound": round(pred_price - cone_width, 2),
                "upperBound": round(pred_price + cone_width, 2)
            })
            
        # Determine trend signal
        price_7d = forecast_data[6]['forecast']
        price_30d = forecast_data[-1]['forecast']
        pct_change_30d = ((price_30d - current_price) / current_price) * 100
        
        if pct_change_30d > 2:
            trend_signal = "BULLISH BREAKOUT"
        elif pct_change_30d < -2:
            trend_signal = "BEARISH DRIFT"
        else:
            trend_signal = "NEUTRAL CONSOLIDATION"

        return {
            "backtestAccuracy": round(backtest_accuracy, 1),
            "mape": round(mape, 2),
            "historical": historical_data,
            "forecast": forecast_data,
            "trendSignal": trend_signal,
            "currentPrice": round(current_price, 2),
            "projected7D": round(price_7d, 2),
            "projected30D": round(price_30d, 2)
        }
        
    except Exception as e:
        logger.error(f"ML Predictor Error: {e}")
        return {"error": str(e)}
