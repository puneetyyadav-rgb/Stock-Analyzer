import yfinance as yf
import pandas as pd

tkr = yf.Ticker("INFY.NS")
df = tkr.history(start="2024-09-01", end="2026-07-24")
df.index = df.index.tz_localize(None)

dates = {
    "Oct 2024": "2024-10-15",
    "Jan 2025": "2025-01-15",
    "Apr 2025": "2025-04-15",
    "Jul 2025": "2025-07-15",
    "Oct 2025": "2025-10-15",
    "Jan 2026": "2026-01-15",
    "Feb 2026": "2026-02-15",
    "Apr 2026": "2026-04-15"
}

scores = {
    "Oct 2024": -0.40,
    "Jan 2025": -0.20,
    "Apr 2025": 0.00,
    "Jul 2025": 0.00,
    "Oct 2025": -0.10,
    "Jan 2026": 0.10,
    "Feb 2026": 0.10,
    "Apr 2026": -0.20
}

print("Quarter    | Divergence Score | 3-Month Forward Stock Return")
print("-" * 65)

for q, d in dates.items():
    try:
        start_date = pd.to_datetime(d)
        end_date = start_date + pd.DateOffset(months=3)
        
        start_slice = df[df.index >= start_date]
        if start_slice.empty: continue
        start_px = start_slice['Close'].iloc[0]
        
        end_slice = df[df.index <= end_date]
        if end_slice.empty: continue
        end_px = end_slice['Close'].iloc[-1]
        
        ret = (end_px - start_px) / start_px * 100
        print(f"{q:10} | {scores[q]:16.2f} | {ret:6.2f}%")
    except Exception as e:
        print(f"{q:10} | {scores[q]:16.2f} | Error")
