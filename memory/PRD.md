# Stock Sentinel IN — PRD

## Problem Statement
AI app for Indian stock market analysis (NSE/BSE). User enters a stock name and gets comprehensive analysis covering 9 categories: macro factors, sector dynamics, company fundamentals, technicals, news/sentiment, global shocks, government policy, demand-supply, management commentary.

## User Personas
- Indian retail investors / traders
- Analysts wanting a Bloomberg-terminal style quick view
- Anyone tracking NSE/BSE listed companies

## Architecture
- **Backend**: FastAPI + MongoDB + yfinance + BeautifulSoup (scraping Moneycontrol + Screener.in) + Gemini 3 Flash via Emergent Universal Key
- **Frontend**: React + recharts + Tailwind + Shadcn UI (Bloomberg terminal aesthetic — dark, IBM Plex Sans + JetBrains Mono)
- **Auth**: None (open access)

## Core Requirements
1. Stock search across NSE/BSE listed stocks
2. Live price, OHLC, volume, market cap, 52w range
3. Valuation/ratios (PE, PB, EPS, ROE, ROA, D/E, margins, growth)
4. Technicals: RSI, MACD, SMA 50/200, support/resistance, trend
5. Quarterly financials + corporate actions (dividends, splits) + shareholding
6. News scraping (Yahoo + Moneycontrol) — sentiment
7. Screener.in pros/cons + key ratios + about
8. Macro snapshot (Nifty, Sensex, Bank Nifty, IT, USD/INR, DXY, crude, gold, US10Y, VIX, Dow, Nasdaq)
9. Sector heatmap (10 NSE sectors)
10. AI verdict using Gemini 3 Flash — Buy/Hold/Sell with confidence, target price, bull/bear cases, risks, catalysts, 9-factor breakdown

## What's Been Implemented (Phase 1 — 2026-02-19)
- All backend APIs (search, overview, chart, technicals, financials, corporate, holders, news, screener, macro, sectors, AI verdict)
- Full dashboard UI with all panels
- Dark terminal aesthetic with sharp borders
- 60s in-memory cache for data sources

## Backlog / Next Tasks
- P1: FII/DII daily flows widget (NSE/BSE data)
- P1: Concall transcripts integration (PDF parsing)
- P1: Watchlist with persistence (requires auth later)
- P2: Comparison view (peer stocks side-by-side)
- P2: Options chain & put-call ratio
- P2: Insider trading specifically (SEBI disclosures)
- P2: Custom alerts (price/news triggers)
- P2: Export AI report as PDF
