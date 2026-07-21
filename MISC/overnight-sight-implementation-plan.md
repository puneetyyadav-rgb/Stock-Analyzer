# Overnight Sight — Implementation Plan

*Pre-market morning briefing feature for StockSentinel India*

## 1. Overview

Every morning before the 9:15 AM market open, opening the dashboard with no stock selected currently shows a generic hero banner and popular-stock shortcuts. This feature replaces that first view with a live pre-market briefing: whether the setup for NIFTY looks bullish, bearish, or neutral today, backed by what actually moved overnight — US and Asian index closes, crude, gold, DXY, USDINR, US yields, and the GIFT Nifty futures gap — plus an AI-written rationale, which sectors have tailwinds vs. headwinds, and two or three trade ideas. No navigation and no stock search required — it's the first thing visible.

## 2. Architecture

Two independent data sources feed one backend module, which does two independent jobs, exposed as two independent endpoints, rendered by one frontend panel. Independence at every layer is the actual design principle — it's what lets the AI step be optional instead of load-bearing.

```
Data sources
  yfinance             → 19 tickers: global indices, commodities, FX, yields, vol, crypto
  TradingView scanner  → GIFT Nifty (NSEIX:NIFTY1!)
        │
        ▼
overnight_service.py
  fetch layer          → raw numbers, normalized
  AI synthesis layer   → Groq interprets the raw numbers into a bias
        │
        ▼
Two FastAPI endpoints  →  api.js  →  OvernightSightPanel.jsx  →  Dashboard.jsx (no-stock-selected view)
```

**Two sources, because one can't do it.** yfinance covers 19 of the tickers needed — every global index, commodity, FX pair, and yield except GIFT Nifty, which yfinance doesn't carry at all. GIFT Nifty comes from TradingView's scanner API instead (see §3). Both sources are fetched independently, each behind its own try/except, so a failure in one never touches the other.

**Two jobs, because fetching and interpreting fail differently.** Pulling prices is fast and rarely fails outright — worst case, one ticker is empty on a holiday. Asking an LLM to synthesize a market view is slower and occasionally fails completely (the whole Groq fallback chain can come back empty). So there are two functions: one that only fetches and normalizes data, and one that takes that data and asks Groq to interpret it — built so an AI failure still returns the fetched data, not an error.

**Two endpoints, because the frontend needs both speeds.** A raw-data endpoint returns just the numbers, cached 15 minutes. A briefing endpoint returns the numbers plus the AI layer, cached 2 hours, with a `force_refresh` flag to bypass the cache on demand.

**One panel, mounted where it's actually seen.** The frontend calls the briefing endpoint once and renders it as the first thing in the no-stock-selected view — above the existing empty state, not gated behind a tab.

## 3. Key decisions & corrections

| Question | Decision | Why |
|---|---|---|
| GIFT Nifty data source | TradingView scanner API via the `tradingview-screener` package, symbol `NSEIX:NIFTY1!`; `tvDatafeed` as fallback if the scanner doesn't carry it | yfinance has no ticker for GIFT Nifty at all. A "previous NIFTY close" proxy isn't structurally capable of predicting an overnight gap — it's just yesterday's number. |
| Exact GIFT Nifty symbol | `NSEIX:NIFTY1!` — **not** `NSE:NIFTY1!` | `NSE:NIFTY1!` is a real, different, separate symbol — the domestic Nifty futures contract that only trades during regular NSE hours. Using it by mistake wouldn't error; it would silently track a flat, closed contract during the exact overnight window this feature exists to watch. |
| "US 2-Year Yield" ticker | Relabeled as "US 3-month T-bill" (`^IRX`) | `^IRX` is Yahoo's 13-week Treasury bill ticker, not the 2-year note. Yahoo doesn't publish a 2-year yield ticker at all — its only rate tickers are `^IRX` (13-week), `^FVX` (5-year), `^TNX` (10-year), `^TYX` (30-year). |
| Endpoint count | Two (`raw-data`, `briefing?force_refresh=`), not three | `force_refresh` on `briefing` already does what a separate `refresh` endpoint would do. |
| UI placement | Full panel in the no-stock-selected default view | Needs to be visible with zero navigation, every morning — not behind a tab. |

## 4. Data contract

`GET /overnight/briefing` returns two independent halves in one object — either can be absent without breaking the other:

- **`raw`** — generation timestamp; the 19 yfinance assets, each with last price and % change; a `gift_nifty` field that's either a populated snapshot or `null` if the TradingView fetch failed.
- **`ai`** — `null` if Groq's entire fallback chain failed, otherwise: bias (bullish / bearish / neutral), confidence, rationale, sector tailwinds, sector headwinds, trade ideas, key risks, disclaimer.

The frontend always renders `raw`; it conditionally renders `ai`. A failed AI call should never produce an error screen — only a quieter version of the panel.

## 5. Task list

### 0. Environment
- [ ] Install `tradingview-screener` (`pip install tradingview-screener --break-system-packages`)
- [ ] No new `.env` keys needed unless the anonymous scanner call gets blocked — if so, add `TRADINGVIEW_USERNAME` / `TRADINGVIEW_PASSWORD` and switch that one function to `tvDatafeed`

### 1. Backend — new file `overnight_service.py`

Define the 19-ticker yfinance universe:

| Category | Name | yfinance symbol |
|---|---|---|
| Index | S&P 500 | `^GSPC` |
| Index | Nasdaq | `^IXIC` |
| Index | Dow Jones | `^DJI` |
| Index | Nikkei 225 | `^N225` |
| Index | Hang Seng | `^HSI` |
| Index | FTSE 100 | `^FTSE` |
| Commodity | Brent crude | `BZ=F` |
| Commodity | WTI crude | `CL=F` |
| Commodity | Gold | `GC=F` |
| Commodity | Silver | `SI=F` |
| Commodity | Copper | `HG=F` |
| Commodity | Natural gas | `NG=F` |
| FX / rates | US Dollar Index | `DX-Y.NYB` |
| FX / rates | USD/INR | `USDINR=X` |
| FX / rates | US 10-year yield | `^TNX` |
| FX / rates | US 3-month T-bill | `^IRX` |
| Vol / risk | India VIX | `^INDIAVIX` |
| Vol / risk | US VIX | `^VIX` |
| Vol / risk | Bitcoin | `BTC-USD` |

- [ ] `fetch_overnight_data()` — one batched `yf.download` call across all 19 tickers rather than 19 sequential calls; each ticker's prior-close-vs-latest-close computation wrapped in its own try/except so one bad ticker (e.g. empty data on a market holiday) doesn't drop the rest
- [ ] `fetch_gift_nifty()` — separate function, queries `tradingview-screener` for `NSEIX:NIFTY1!`, returns close + % change, in its own try/except, returns `None` on any failure rather than raising
- [ ] Combine both into one raw structure per the data contract in §4
- [ ] `generate_morning_briefing(force_refresh=False)` — calls both fetch functions, builds the CIO-persona prompt against the existing JSON-schema convention, calls `ai._call_groq_fallback` directly (skip Gemini — this feature doesn't need it, and Gemini's rate limits are better reserved for the rest of the app), parses defensively (strip stray code fences, unwrap if the model wraps JSON in a list — same pattern already used in `generate_technical_analysis` / `generate_news_analysis`), attaches `ai.DISCLAIMER_TEXT`, returns `raw` and `ai` separately per §4 so a Groq failure degrades to raw-only instead of losing everything
- [ ] Check whether `global_macro_monte_carlo.py` or `macro_service.py` already expose a reusable fetch for the 8 tickers that overlap with the existing `MACRO_UNIVERSE` (crude, gold, copper, DXY, USDINR, US10Y, India VIX, natgas) — reuse if so, otherwise a second batched fetch is cheap enough to not matter

### 2. Backend — two endpoints in `server.py`
- [ ] `GET /overnight/raw-data` — 15-minute cache, no AI
- [ ] `GET /overnight/briefing?force_refresh=` — 2-hour cache; doesn't cache the result if the AI layer came back empty, so a Groq outage self-heals on the next check instead of freezing a null bias for two hours
- [ ] Both added directly above `app.include_router(api_router)` at line 1479, matching the existing `get_management_guidance` endpoint's shape: cache-check → service call → cache-set → return

### 3. Frontend — `api.js` additions
- [ ] `getOvernightRawData(forceRefresh)` — plain style, matching the existing `getManagementGuidance`
- [ ] `getOvernightBriefing(forceRefresh, options)` — defensive try/catch style with abort-signal support, matching the existing `getGlobalMacroMonteCarlo`, since this one chains 19 tickers plus a scanner call plus an AI call

### 4. Frontend — new file `OvernightSightPanel.jsx`
- [ ] Fetches `getOvernightBriefing()` on mount, shows a loading skeleton
- [ ] GIFT Nifty gets the single most prominent slot — the headline "will Nifty gap up or down" number, not just another grid card
- [ ] Bias indicator (bullish / bearish / neutral + confidence) from `ai`, then the index/commodity/FX/vol grid from `raw`
- [ ] If `ai` is `null`, still renders the raw grid with a quiet "AI synthesis unavailable" note instead of erroring
- [ ] Manual refresh button (`force_refresh=true`); 30-minute auto-refresh optional
- [ ] Self-contained Bloomberg-dark styling, not wrapped in the generic `<Panel>` component — matches how `GlobalMacroSimulationPanel` is already built

### 5. Frontend — `Dashboard.jsx` integration
- [ ] Import `OvernightSightPanel`
- [ ] Render `<OvernightSightPanel />` as the very first thing inside the `!symbol` branch of the stock tab — before the existing `<EmptyState />` — so it's the first thing visible, directly under the header search bar
- [ ] Existing `EmptyState`, `MacroPanel`, `FiiDiiPanel` stay exactly where they are, unmodified, just pushed below it
- [ ] No new tab button, no conditional render elsewhere in the file

### 6. Verification checklist
- [ ] Confirm `NSEIX:NIFTY1!` actually returns data from `tradingview-screener`'s default scan before trusting it in production — if empty, switch to `tvDatafeed` with real credentials
- [ ] Sanity-check `^TNX`'s raw fetched value against a known current 10-year yield the first time it runs — yfinance has a history of returning CBOE rate indices scaled ×10 in some code paths; `global_macro_monte_carlo.py` may already handle this correctly elsewhere, worth reusing rather than re-deriving
- [ ] Confirm a market holiday (empty yfinance history for one ticker) degrades that one asset instead of throwing
- [ ] Confirm a Groq outage returns raw-only data instead of a 500

---

*Next step once this is approved: generate the actual file contents — `overnight_service.py`, the two route functions for `server.py`, the `api.js` additions, `OvernightSightPanel.jsx`, and the exact `Dashboard.jsx` diff.*
