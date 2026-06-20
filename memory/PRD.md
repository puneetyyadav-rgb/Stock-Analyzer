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

## Phase 2 Implementation (2026-02-19)
### Added
- **FII/DII Daily Flows** widget — Moneycontrol scrape via Next.js __NEXT_DATA__ JSON. 15-day chart + table.
- **Concall Transcripts** — Screener.in scrape with Transcript/PPT/Recording links per quarter.
- **AI Concall Summary** — Gemini-powered structured summary (sentiment, highlights, guidance, concerns, Q&A). Auto-fallback to "alternative" mode using news+screener+about when BSE PDF is geo-blocked.
- **Peer Comparison** — Sector-based peer table (8 peers per sector) with click-to-navigate.
- **Options Chain & PCR** — NSE API integration with cookie warming. Gracefully degrades when NSE blocks.
- **Insider Transactions** — Improved labeling from yfinance Text field (Sale/Other/Purchase).
- **Watchlist** — localStorage-based, no auth required. Star toggle in stock header, sidebar list with live prices (60s polling).
- **Price Alerts** — localStorage-based threshold alerts, browser notifications + sonner toasts when triggered.
- **PDF Export** — html2canvas + jsPDF client-side full-dashboard export.
- **Sidebar Toggle** — Collapsible watchlist/alerts sidebar.

### Bug Fixes
- Technicals 500 ValueError: NaN/Inf float values now sanitized via `_safe_float`.
- `majorHoldersBreakdown` parsed correctly: insidersPercentHeld %, institutionsPercentHeld %, institutionsCount.
- Insider `Transaction` field — fallback to `Text` field-derived label.
- Dividend yield no longer multiplied by 100 (yfinance returns it as percentage already).

### Known Limitations
- BSE PDF downloads geo-blocked from foreign server IPs → concall summary uses "alternative" fallback automatically.
- NSE options chain API geo-blocks foreign IPs → panel shows graceful "unavailable" with NSE link.
- Moneycontrol scraping intermittent 403 → FII/DII panel falls back to "Data unavailable".

## Phase 3 Implementation (2026-02-20) — Gap Closure per uploaded spec
### Added
- **P0-1 Social Sentiment** — Reddit (praw, 3 subreddits) + StockTwits + X/Twitter "not integrated" note. VADER scoring on post titles. Graceful degradation when REDDIT_CLIENT_ID/SECRET not set.
- **P0-2 Legal & Regulatory** — NSE corporate-announcements scrape filtered by 14 legal keywords, then Gemini-classified into category + severity + factual summary.
- **P0-3 News VADER Sentiment** — Every news item carries `sentimentScore`/`sentimentLabel` (Positive/Negative/Neutral). AI verdict prompt now passes news with sentiment instead of raw titles.
- **P0-4 Disclaimer** — Shared `DISCLAIMER_TEXT` constant rendered: footer, under AI verdict badge, at top of PDF export.
- **P1-1 Sector-Specific Factor Branching** — 10 sector buckets × 2-4 hints each. Gemini explicitly asked to address sector hints from existing data; new `sectorSpecific` array with `dataAvailable` flag per factor (UI shows "No data available" chip when AI honestly couldn't answer).
- **P1-2 Events Calendar** — Combined yfinance earnings/dividend dates + NSE board-meeting regex extracts. De-duped + chronologically sorted.
- **P1-3 Structured Red Flags** — Aggregator endpoint combining: Screener cons (Medium), promoter pledge % (severity by % bracket), Critical/High legal classified items, and special-event keyword news (succession/cybersecurity).
- **P2 Special-event keywords** — Scans news for `succession`, `founder health`, `data breach`, `ransomware`, `cyberattack`, `phishing` and surfaces flagged items.

### Honest limitations called out in UI
- Reddit panel shows config instructions when keys missing
- Twitter/X block explicitly says "Not Integrated — X discontinued free read tier Feb 2026"
- Legal panel footer reads "Source: NSE scrape, not an official SEBI API"
- Sector-specific items show "No data available" chip rather than fabricating

### Files
- New backend: `social_service.py`, `legal_service.py`, `events_service.py`
- New frontend: `SocialPanel.jsx`, `LegalPanel.jsx`, `EventsPanel.jsx`, `RedFlagsPanel.jsx`, `Disclaimer.jsx`
- Modified: `stock_service.py` (VADER + promoter pledge + special tags), `ai_service.py` (sector branching + sectorSpecific schema), `server.py` (4 new routes), `Dashboard.jsx`, `AIVerdict.jsx`, `PdfExportButton.jsx`
