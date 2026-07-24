"""
backtest_concall_ic.py — Formal Information Coefficient backtest for the Concall Divergence factor.

Reads real scored data from concall_factor_store.json and computes:
  - Spearman Rank IC (divergence vs 3-month forward NSE return)
  - Hit Rate (% of quarters where signal direction was correct)
  - Full reasoning table with WHY each score was given
"""

import os
import json
import sys
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(r'E:\Website\Stock Analysis\stock ticker v2\backend\.env')

STORE_PATH = r'E:\Website\Stock Analysis\stock ticker v2\MISC\concall_factor_store.json'
FORWARD_MONTHS = 3

# Map concall date strings to approximate NSE concall announcement dates
# These are the actual INFY quarterly result dates (used to fetch prices)
DATE_MAP = {
    "Apr 2026": "2026-04-17",
    "Feb 2026": "2026-02-04",
    "Jan 2026": "2026-01-16",
    "Oct 2025": "2025-10-17",
    "Jul 2025": "2025-07-17",
    "Apr 2025": "2025-04-17",
    "Jan 2025": "2025-01-16",
    "Oct 2024": "2024-10-17",
    "Jul 2024": "2024-07-18",
    "Apr 2024": "2024-04-18",
}

NS_SUFFIX = {
    "INFY": "INFY.NS",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "WIPRO": "WIPRO.NS",
    "LTIM": "LTIM.NS",
    "HCLTECH": "HCLTECH.NS",
}

def get_price_on_or_after(symbol_ns: str, date_str: str) -> float | None:
    """Get NSE closing price on concall date or next available trading day."""
    try:
        start = pd.to_datetime(date_str)
        end = start + pd.DateOffset(days=7)
        df = yf.download(symbol_ns, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        if df.empty:
            return None
        val = df["Close"].iloc[0]
        return float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)
    except Exception as e:
        return None

def get_forward_price(symbol_ns: str, date_str: str, months: int = 3) -> float | None:
    """Get NSE closing price ~3 months after the concall date."""
    try:
        start = pd.to_datetime(date_str) + pd.DateOffset(months=months)
        end = start + pd.DateOffset(days=7)
        df = yf.download(symbol_ns, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        if df.empty:
            return None
        val = df["Close"].iloc[0]
        return float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)
    except Exception as e:
        return None

def run_ic_backtest():
    print("\n" + "="*78)
    print("  CONCALL DIVERGENCE FACTOR — INFORMATION COEFFICIENT BACKTEST")
    print("  Data: Real Screener.in PDFs | Model: gemini-3.5-flash-lite | schema_version=v1")
    print("="*78)

    if not os.path.exists(STORE_PATH):
        print(f"\nERROR: Store not found at {STORE_PATH}")
        print("Run: python concall_factor_service.py INFY   first.")
        return

    with open(STORE_PATH, "r", encoding="utf-8") as f:
        store = json.load(f)

    rows = []
    print(f"\nLoaded {len(store)} scored quarters from store.\n")

    for key, val in store.items():
        if val.get("schema_version") != "v1":
            continue
        if "error" in val:
            continue
        if "concall_divergence" not in val:
            continue

        symbol   = val["symbol"]
        date_str = val["date"]
        div      = val["concall_divergence"]
        hes      = val.get("concall_hesitation", 0.0)
        reasoning = val.get("divergence_reasoning", "N/A")
        hedges   = val.get("qa_hedging_phrases", [])

        # Map concall month string to actual date
        concall_date = DATE_MAP.get(date_str)
        if not concall_date:
            print(f"  SKIP {symbol} {date_str}: no date mapping (add to DATE_MAP)")
            continue

        ns = NS_SUFFIX.get(symbol, f"{symbol}.NS")

        # Fetch real prices from yfinance (NSE)
        p0 = get_price_on_or_after(ns, concall_date)
        p3 = get_forward_price(ns, concall_date, FORWARD_MONTHS)

        if p0 is None or p3 is None:
            print(f"  SKIP {symbol} {date_str}: price data unavailable (future date or delisted)")
            continue

        fwd_ret = (p3 - p0) / p0 * 100

        rows.append({
            "symbol":      symbol,
            "quarter":     date_str,
            "divergence":  div,
            "hesitation":  hes,
            "entry_price": round(p0, 2),
            "exit_price":  round(p3, 2),
            "fwd_return":  round(fwd_ret, 2),
            "direction_correct": (div < 0 and fwd_ret < 0) or (div > 0 and fwd_ret > 0),
            "hedges":      hedges[:3],
            "reasoning":   reasoning[:250],
        })

    if not rows:
        print("\nNo data points with available NSE price history. Add more symbols or wait for future quarters.")
        return

    df = pd.DataFrame(rows)

    # ── FULL DETAILED TABLE ──────────────────────────────────────────────────
    print(f"\n{'Quarter':<10} {'Sym':<10} {'Div':>7} {'Hes':>7} {'FwdRet':>9}  {'Correct?':<10}  Key Q&A Hedges")
    print("-"*95)
    for _, r in df.iterrows():
        correct_str = "[YES]" if r["direction_correct"] else "[NO] "
        hedges_str  = " | ".join(r["hedges"]) if r["hedges"] else "none"
        print(f"{r['quarter']:<10} {r['symbol']:<10} {r['divergence']:>+7.2f} {r['hesitation']:>7.1f}"
              f" {r['fwd_return']:>+8.2f}%  {correct_str:<8}  {hedges_str[:55]}")

    # ── WHY THIS CONCLUSION ──────────────────────────────────────────────────
    print(f"\n{'-'*78}")
    print("  REASONING — Why each divergence score was drawn:")
    print(f"{'-'*78}")
    for _, r in df.iterrows():
        signal = "BEARISH SIGNAL" if r["divergence"] < -0.05 else ("BULLISH SIGNAL" if r["divergence"] > 0.05 else "NEUTRAL")
        outcome = f"Stock moved {r['fwd_return']:+.1f}% in 3M -> {'CORRECT [YES]' if r['direction_correct'] else 'WRONG [NO]'}"
        print(f"\n  [{r['quarter']} | {r['symbol']}]  Divergence={r['divergence']:+.2f}  ({signal})")
        print(f"  {outcome}")
        print(f"  Reasoning: {r['reasoning'][:280]}...")

    # ── IC COMPUTATION ────────────────────────────────────────────────────────
    print(f"\n{'='*78}")
    print("  INFORMATION COEFFICIENT (IC) COMPUTATION")
    print(f"{'='*78}")

    divs = df["divergence"].values
    rets = df["fwd_return"].values

    if len(divs) >= 4:
        ic, pvalue = stats.spearmanr(divs, rets)
        hit_rate   = df["direction_correct"].mean()
        mean_ret_when_negative = df.loc[df["divergence"] < -0.05, "fwd_return"].mean()
        mean_ret_when_positive = df.loc[df["divergence"] > 0.05, "fwd_return"].mean()

        print(f"\n  Observations (quarters with real price data): {len(df)}")
        print(f"  Spearman Rank IC:       {ic:+.4f}   (>0.05 = signal has edge)")
        print(f"  p-value:                {pvalue:.4f}   (<0.05 = statistically significant)")
        print(f"  Hit Rate:               {hit_rate*100:.1f}%     (>55% = directionally useful)")
        print(f"  Avg 3M return when DIV < -0.05 (bearish): {mean_ret_when_negative:+.2f}%")
        print(f"  Avg 3M return when DIV > +0.05 (bullish): {mean_ret_when_positive:+.2f}%")

        print(f"\n  {'─'*40}")
        if ic > 0.05 and hit_rate > 0.55:
            print(f"  VERDICT: [PASS] SIGNAL IS REAL -- IC={ic:.4f}, HitRate={hit_rate*100:.0f}%")
            print(f"           Concall Divergence earns its seat in _WEIGHTS at 0.10 weight.")
        elif ic > 0.02:
            print(f"  VERDICT: [WEAK] Need more stocks/quarters for confirmation.")
            print(f"           Add TCS, HDFCBANK, WIPRO to the universe and re-run.")
        else:
            print(f"  VERDICT: [FAIL] NO EDGE -- IC={ic:.4f}. Drop from _WEIGHTS.")
        print(f"  {'─'*40}")
    else:
        print(f"\n  Only {len(df)} data points — need at least 4 to compute IC.")
        print("  Run: python concall_factor_service.py TCS")
        print("  Run: python concall_factor_service.py HDFCBANK")

    print(f"\n{'='*78}\n")

if __name__ == "__main__":
    run_ic_backtest()
