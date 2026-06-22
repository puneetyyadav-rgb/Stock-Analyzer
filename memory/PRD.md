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

## Phase 4 Implementation (2026-02-22)
### Added per user spec
- **News Split (3 tabs)** — `/api/stock/{symbol}/news-split` returns `{company, sector_news, market}` buckets. Frontend `NewsSplitPanel` shows tabbed UI with counts and VADER sentiment per card. Old monolithic news panel removed from StockDetails.
- **Sectoral Analysis** — `/api/stock/{symbol}/sector-analysis` returns sector NSE index performance (today/1M/3M) vs Nifty 50 benchmark, peer aggregates (avg P/E, P/B, ROE, margins, growth + top gainer/loser), stock-vs-peer P/E delta, and a verdict bar.
- **External deep-links** — Sectoral Analysis panel includes 5 colored buttons → Trendlyne, StockEdge, Aftermarkets, MC Sector News, NSE Indices. Trendlyne/StockEdge/Aftermarkets are anti-bot/SPA so deep-linked rather than scraped (called out in UI).
- **Sector news source** — Moneycontrol `/news/tags/<slug>.html` (server-rendered) mapped from Yahoo sectors. 25 items per request for major sectors.

### Files added
- `/app/backend/sector_service.py` (categorize_news, get_sector_news, get_sector_analysis)
- `/app/frontend/src/components/NewsSplitPanel.jsx`, `SectorAnalysisPanel.jsx`

## Phase 5 Implementation (2026-02-23)
### Added
- **Playwright headless scraper** (`scraper_service.py`) — singleton Chromium launched lazily, reused across calls. PLAYWRIGHT_BROWSERS_PATH=/pw-browsers set at module load.
- **Aftermarkets full scrape** — structured: editorialQuote, marketView, businessScore (0-100), 4 sub-scores (valuation/growth/returnsMargins/financialHealth with rating+score+description), 5 safetyChecks (Promoter pledge / ASM / GSM / F&O ban / Default probability), live price, day range, sectorTag.
- **Trendlyne & StockEdge** — confirmed blocked even with playwright-stealth (AWS WAF and login-wall respectively); now return honest `available:false` with reason text + deep-link to open in user's browser.
- `/api/stock/{symbol}/external-scrape` endpoint with 30-min cache (TTL parameterized in `_cache_get`).
- `ExternalScrapePanel.jsx` — renders Aftermarkets primary card + two "Anti-bot blocked" honest cards.

### Sector Keyword Library Expansion
- Sector keyword map grew from ~5 keywords/sector to **15-30+ per sector** (250 total terms).
- Mid-cap industries covered: specialty chemicals, agrochemicals, jewellery, gold loans, asset management, exchanges, ports, defence, drones, solar, hydrogen, batteries, EV, QSR, hotels, multiplexes, REITs, footwear, etc.
- SUNPHARMA / TATAMOTORS verified: sector_news bucket consistently populated with 25 sector-specific items.

### Known limits documented in UI
- Trendlyne — AWS WAF "Human Verification" page blocks headless Chromium even with stealth plugins. Genuinely unscrapable from any server. UI says so.
- StockEdge — per-share pages require auth or internal numeric stock IDs. UI says so.
