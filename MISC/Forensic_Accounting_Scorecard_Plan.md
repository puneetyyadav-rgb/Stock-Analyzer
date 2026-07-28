# Forensic_Accounting_Scorecard_Plan.md
### Master Architectural Plan — Fundamental & Forensic Equity Research Deck
### Extension to StockSentinel India (puneetyyadav-rgb/Stock-Analyzer)
**Version 3.1 — Repository-Grounded, Audit-Corrected. Zero source code. For direct hand-off to an autonomous coding agent.**

---

This document is the single deliverable requested: a complete technical blueprint for a new "Fundamental & Forensic Equity Research Deck" module, incorporating all 14 mandatory audit findings, all 5 missing institutional metrics, and every sector override from the brief — **with one difference from the brief you pasted: every architectural claim below has been checked against the actual `puneetyyadav-rgb/Stock-Analyzer` repository rather than assumed.** Section 1.0 lays out exactly what that check found, because it changes several "reuse, don't duplicate" instructions in the original brief into "build new" instructions. Everything downstream (Sections 2–6) is written against the corrected picture, not the assumed one.

---

## SECTION 1: EXECUTIVE ARCHITECTURAL BLUEPRINT

### 1.0 Repository Grounding Audit — Read This Before Anything Else

The repo was cloned and inspected directly (`backend/`, `frontend/src/`, git history, `requirements.txt`, `package.json`, `README.md`, `features.md`). Findings below are load-bearing for the rest of this plan.

**A. The brief's "Existing Forensic Engine" does not exist. It must be built new.**
There is no `backend/forensic_service.py` in the repository, in the current tree or anywhere in git history. There is no `_val()` helper, no `_annual_frames()` helper, no `forensic_cache.json`, and no Piotroski / Beneish / ROIC-vs-WACC / `analyze_forensics()` computation anywhere in the codebase (verified by exhaustive grep across all `.py` files and full git log search). The only hit for the word "forensic" in the entire backend is a persona label inside an LLM prompt string in `ai_service.py` ("You are an investigative News & Forensic Desk Analyst...") — unrelated to quantitative forensic accounting.
→ **Consequence:** Section 6 below builds this from scratch as new core infrastructure (`fundamental_service.py`). It does **not** "import and invoke" a pre-existing module, contrary to the brief's assumption. This is the single most important correction in this document — treating it as "reuse" would hand the coding agent a first step that fails immediately on `ModuleNotFoundError`.

**B. `sector_map.py` is real, but its actual signature is different from the brief's assumption.**
The real function is `get_sector_map(symbols: Iterable[str], max_refresh=None, force_refresh=False) -> Dict[str, str]` — a **batch** function, keyed by cleaned symbol, backed by a 7-day-TTL JSON disk cache (`sector_map_cache.json`), returning yfinance's **raw Yahoo sector taxonomy** (`Technology`, `Financial Services`, `Industrials`, `Healthcare`, `Consumer Cyclical`, `Consumer Defensive`, `Energy`, `Basic Materials`, `Real Estate`, `Utilities`, `Communication Services`) via `.info["sector"]`. There is no `get_sector(symbol)` singular function, and — critically — **there is no existing mapping anywhere in the codebase from Yahoo's sector taxonomy to the bespoke buckets this brief needs** (EPC/Capital Goods, Real Estate/Construction, Pharma/API/CDMO, Telecom/Airlines, Banks/NBFC, Holding Companies, etc.). That mapping is new design work; Section 4.1 resolves it exhaustively.

**C. Real, reusable infrastructure that the brief correctly assumed exists (confirmed, safe to build on):**
| Module | Confirmed real capability |
|---|---|
| `bhavcopy_service.py` | `universe_factors()`, `delivery_signal(symbol)`, `cross_check(...)` — full NSE universe + delivery-quality context |
| `factor_service.py` | `get_factor_profile(symbol)` → percentile, decile, universeSize, tradableUniverse, liquidityFilter, advTurnoverCr, rawComposite, sectorAdjustedComposite, sectorOverlay, factors |
| `extra_service.py` | `get_peers(symbol)` — a real, already-built **4-tier cascading peer engine** (Screener.in scrape → AI synthesizer → Yahoo industry tag → NSE CSV classification), returning up to 8 peers pre-hydrated with `symbol, name, price, changePercent, marketCap, peRatio, pbRatio, roe, profitMargin, revenueGrowth, dividendYield, peerSource` |
| `stock_service.py` | `_safe_float(v)` helper; `get_financials(symbol)` — a lightweight existing precedent that confirms real, working yfinance field names (see Section 2 note) |
| `server.py` | FastAPI app titled `"StockSentinel India"`, `api_router = APIRouter(prefix="/api")`, route pattern `@api_router.get("/stock/{symbol}/<feature>")`, a 3-tier cache (`_CACHE` in-memory 60s default → `custom_ttl` override, e.g. an existing `custom_ttl=3600` precedent on the factor-IC route → disk-persisted 24h cache for a named tuple of "expensive" key prefixes) |
| `frontend/src/components/Panel.jsx` | Exports `Panel` and `KV` — the exact shared UI primitives the brief's "Existing UI Integration Pattern" describes (confirmed real, not aspirational) |
| Color convention | `text-emerald-400` / `text-amber-400` / `text-red-400` confirmed in live use in `StockDetails.jsx` |
| Env-flag gating | `os.environ.get("ENABLE_X", "true").lower() != "false"` confirmed real, currently used by `ENABLE_INTRADAY_CONFIRMATION`, `ENABLE_NEWS_GATE`, `ENABLE_REGIME_OVERLAY` |
| Data fetching convention | 19 of the ~35 frontend panel components use `axios.get()` inside `useEffect`/`useState` (mirroring `RedFlagsPanel.jsx`); `swr` is installed but used by zero components — axios+useEffect is the real convention to follow, not swr |
| Charting | `recharts@3.6.0` is already an installed frontend dependency — no new JS dependency is needed for the two quadrant scatter plots |

**D. Two naming collisions the brief did not anticipate — must be avoided:**
- `RedFlagsPanel.jsx` **already exists**, calling a **real, different** endpoint `GET /stock/{symbol}/red-flags`. That system aggregates *qualitative* red flags — Screener.in "cons" text, SEBI/court keyword hits, promoter-pledge mentions — via scraping/NLP, not the 16-point quantitative forensic engine this brief specifies. **Do not reuse this route or component name.** The new engine's red-flag output lives inside the new `/stock/{symbol}/fundamentals` payload under a `forensics.redFlags` key, and its UI panel must be labeled distinctly (e.g. "Forensic Accounting Red Flags") so a user — or a future maintainer — never conflates the two systems.
- `RatioAnalysisPanel.jsx` **already exists**, implementing a PDF-upload-then-AI-extraction ratio flow with its own `localStorage` cache key (`ratioAnalysis_${symbol}`). Unrelated mechanism. Do not reuse this component name either.
- Separately, `ai_service.py`'s existing "AI Verdict" feature already has a virtual desk literally called **"Fundamental & Legal Desk"** (Gemini-powered qualitative synthesis of concalls/auditor notes/NCLT filings). This is a different, complementary, already-shipped feature — not a conflict, but worth knowing so nobody merges the two or gets confused reading the codebase.
→ **Resolution:** the new module is `fundamental_service.py`, the new endpoint is `/stock/{symbol}/fundamentals`, the new component is `FundamentalDeck.jsx` (the brief's own suggested name — confirmed to collide with nothing that exists today).

**E. One honest limitation of this planning session:** yfinance's own data endpoints (query1/query2.finance.yahoo.com) are not reachable from the sandbox this plan was written in, so exact live DataFrame index strings for a current NSE ticker could not be executed and diffed line-by-line here. The alias lists in Section 2 combine (a) field names **confirmed real** by reading `stock_service.get_financials()`'s working implementation (`"Total Revenue"`, `"Operating Income"`, `"Net Income"`, `"EBITDA"`, `"Gross Profit"`, `"Total Assets"`, `"Total Debt"`, `"Stockholders Equity"` / `"Total Stockholder Equity"` as a proven OR-fallback pair, `"Cash And Cash Equivalents"`, `"Operating Cash Flow"`, `"Free Cash Flow"`, `"Capital Expenditure"`), and (b) well-established yfinance/yahooquery naming conventions for everything else. Task 1 in Section 6 is a mandatory live-schema reconnaissance pass against real tickers across sectors (bank, manufacturer, IT, real estate) before the alias lists are treated as final — this is standard practice for any project ingesting a third-party data schema that drifts, and it is cheap insurance against the whole pillar-calculation layer being built on a guessed field name.

---

### 1.1 System Design

```
yfinance (.balance_sheet / .financials / .cashflow / .info / .fast_info)
        │
        ▼
fundamental_service._annual_frames(symbol)          [NEW — disk-cached, 7-day TTL, mirrors sector_map.py's cache style exactly]
        │
        ▼
fundamental_service._val(df, aliases, year_idx)     [NEW — generic case-insensitive alias-resolving accessor]
        │
        ▼
Gate detectors (all NEW, run first, deterministic):
   • Holding Company gate            • BFSI gate            • Ind AS 116 transition-year detector
   • Capital-raise-year detector     • sectorBucket classifier (Section 4.1)
        │
        ▼
10 Pillar calculators (all NEW, pure functions over the cached frames + .info + gate flags)
        │
        ▼
Forensic layer: Piotroski F-Score · Beneish M-Score (audit-corrected) · Altman Z (sector-routed) ·
                Sloan Accrual (growth-adjusted) · 16-point Red Flag Engine · Phase-2 stubs
        │
        ▼
analyze_fundamentals(symbol, include_peers=True)    [NEW public API — orchestrator]
        │
        ├─── (include_peers=True only) extra_service.get_peers(symbol) → sort by marketCap desc → top 4
        │        → analyze_fundamentals(peer, include_peers=False) per peer  [recursion-guarded, see 1.3]
        │        → Pillar 10 comparison matrix + CCC-vs-ROCE quadrant
        │
        ▼
server.py:  GET /api/stock/{symbol}/fundamentals   [NEW route — mirrors the existing /technicals and /financials routes exactly]
        │
        ▼
frontend:  axios.get(`${API}/stock/${symbol}/fundamentals`) → FundamentalDeck.jsx  [NEW component, built on Panel/KV]
        │
        ▼
Wired into StockDetails.jsx alongside the existing panel grid, gated by ENABLE_FUNDAMENTAL_DECK
```

### 1.2 Complete Output Dictionary Schema

Presented as a typed outline, not as implementation. Every branch that can be structurally absent carries an `available` boolean and a `reason` string (see 1.3) — that contract is omitted below for brevity but applies to every non-leaf node marked "(suppressible)".

```
meta:
  symbol (string, e.g. "RELIANCE.NS")
  companyName (string)
  yahooSector (string — raw .info["sector"])
  sectorBucket (string — the NEW bespoke bucket from Section 4.1, e.g. "EPC_CAPITAL_GOODS")
  fiscalYearEnds (array of date strings, newest first, up to 5)
  currencyUnit ("INR Crores")
  dataAsOf (ISO datetime)
  cacheAgeDays (number)
  isPeerCall (boolean — true when this object was generated as part of another symbol's peer loop)

gates:
  isHoldingCompany (boolean) + otherIncomeToTotalIncomePct, investmentsToAssetsPct (the two gate inputs, always shown even when gate is false)
  isBFSI (boolean) + matchedIndustryTag
  capitalRaiseYears (array of fiscal-year labels where shares outstanding rose >5% YoY)
  indAS116TransitionInRange (boolean), indAS116TransitionYear (fiscal-year label or null)

incomeStatement: (suppressible only if <2 fiscal years of data)
  revenue: { values[5], yoyGrowthPct[4], cagr3y, cagr5y, qualityFlag }
  costStructure: { cogsPctOfRevenue[5], grossProfit[5], grossMarginPct[5], marginTrendFlag, employeeSgaPctOfRevenue[5], ebit[5], operatingMarginPct[5], ebitda[5], ebitdaMarginPct[5], indAS116ComparabilityFlag, operatingLeverageFlag }
  profitabilityCascade: { grossMarginPct[5], operatingMarginPct[5], pretaxMarginPct[5], netMarginPct[5], compressionPointFlag }
  interestExpensePctOfEbit: { reported, exLease }
  effectiveTaxRate: { threeYearAvg, yoySwingPp, sectorGated (boolean), classification ("informational" | "warning" | "none") }
  otherIncomePctOfPbt: { value, flagged (boolean, >15%) }
  eps: { basic[5], cagr3y, cagr5y, epsVsRevenueCagrDivergenceFlag }

balanceSheet: (suppressible only if <2 fiscal years of data)
  assets: { totalAssets[5], currentPct[5], nonCurrentPct[5], cash[5], cashPctOfAssets[5], receivables[5], receivablesPctOfRevenue[5], dso[5], inventory[5], inventoryPctOfRevenue[5], dio[5], netPPE[5], ppePctOfAssets[5], fixedAssetTurnover[5], intangiblesGoodwill[5], intangiblesPctOfAssets[5] (flag >25%), cwip[5], cwipPctOfAssets[5], stalledProjectFlag }
  liabilities:
    financialDebt[5]   (NEW split — short + long term borrowings, excludes leases)
    leaseLiabilities[5] (NEW split — Ind AS 116 RoU lease liability, current+non-current)
    totalDebtReference[5] (financialDebt + leaseLiabilities, labeled "reference only")
    debtToEquity: { financialPrimary[5], totalSecondary[5] }
    netDebtEbitda: { reported[5], exLease[5] }
    tradePayables[5], dpo[5]
    contingentLiabilities: { available: false, reason: "Annual Report notes disclosure — not in yfinance statement DataFrames. Phase 2 data source." }
  workingCapital: { nwc[5], nwcPctOfRevenue[5], ccc[5] (sector-gated, see Section 4), indAS116ComparabilityFlag }
  bookValue: { bvps[5], tbvps[5], retainedEarningsGrowthPct[5] }

cashFlow: (suppressible only if <2 fiscal years of data)
  ocfQuality: { ocf[5], ocfToNi[5] (Golden Ratio classification per value), ocfToEbitda[5], fcf[5], fcfMarginPct[5], cumulative5yOcfVsNiFlag }
  capex: { capex[5], capexPctOfRevenue[5], capexToDepreciation[5], growthCapexProxy[5], deferredTaxPnlImpact[5] }
  financing: { netBorrowingTrend[5], netDilutionOrBuybackTrend[5], dividendPayoutRatio[5], fcfDividendCoverage[5], totalShareholderYieldPct[5], capitalRaiseYearFlags[5] }
  cashSelfSufficiencyTest: boolean per year[5]

profitability: (suppressible — Holding Company gate; see 1.5)
  available (boolean), reason (string if false)
  returns: { roe[5], roa[5], roce[5], roic[5] }
  dupont3Factor: { netMargin[5], assetTurnover[5], equityMultiplier[5], roeCheck[5] }
  dupont5Factor: { taxBurden[5], interestBurdenExLease[5], ebitMargin[5], assetTurnover[5], equityMultiplier[5], roeCheck[5] }
  incremental: { incrementalRoe[4], incrementalRoic[4] }
  capitalAllocationQuadrant: { reinvestmentRate[4], incrementalRoic[4], currentQuadrant (one of 4 labels), verdictSentence }

solvency: (partially suppressible — Real Estate suppresses Current Ratio/CCC as *primary* flags, see Section 4)
  liquidity: { currentRatio[5] (primaryFlagSuppressed boolean), quickRatio[5], cashRatio[5], sixMonthSurvivalTest[5] }
  longTermSolvency: { netDebtEbitdaExLease[5] (PRIMARY covenant ratio), netDebtEbitdaReported[5] (secondary), interestCoverageExLease[5], dscr[5], fixedChargeCoverage[5] }
  capitalStructure: { equityPct[5], financialDebtPct[5], wacc[5], costOfEquity[5], costOfDebtPreTax[5] }

efficiency: (suppressible — Holding Company gate)
  available (boolean), reason (string if false)
  totalAssetTurnover[5], fixedAssetTurnover[5], workingCapitalTurnover[5]
  inventoryTurnover[5], receivablesTurnover[5], payablesTurnover[5]
  ccc[5] (cross-ref balanceSheet.workingCapital.ccc), cccYoyExpansionFlag, negativeCccPositiveSignalFlag

forensics:
  piotroski: { availableTests (0-9 with individual pass/fail + plain-English line), score (0-9), verdict ("Strong"|"Moderate"|"Weak/Distressed") }
  beneish: { dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata, mScore, riskBand ("High"|"Moderate"|"Low/Clean"), depiCwipCrossCheckApplied (boolean), sgaiLvgiSuppressedThisYear (boolean, capital-raise gate), corroboratingFlagCount (int), escalatedToRed (boolean — requires corroboratingFlagCount >= 2) }
  altmanZ: { available (boolean), model ("Z_1968"|"Z_PRIME_1983"|"Z_DOUBLE_PRIME_EM_1995"|null), score, zone ("Safe"|"Grey"|"Distress"), selectionReason }
  sloanAccrual: { rawSloan[5], deferredTaxAdjustedSloan[5] (PRIMARY), revenue3yCagrBand ("<10%"|"10-20%"|">20%"), moderateThresholdPct, severeThresholdPct, flagged (boolean, level) }
  redFlags: array of { id (1-16), name, severity ("INFO"|"WARNING"|"RED"|"CRITICAL"), triggered (boolean), sectorOverrideApplied (boolean), alertString (plain English, values interpolated) }
  phase2Stubs: { rpt, promoterPledge, auditorChange, contingentLiabilities, navDiscount (holdco only), fiiDiiQuarterlyTrend } — each `{ available: false, reason: "..." }`

valuation:
  trailingPE, forwardPE, pb, priceToTangibleBook, ps, evToEbitda, evToEbit, evToRevenue
  peg, fcfYieldPct, earningsYieldVsRfPp, dividendYieldPct
  grahamNumber, epv, marginOfSafetyPct (classification per value)
  ownHistory: { peVs5yMedian, pbVs5yMedian, evEbitdaVs5yMedian }
  sectorNote (string — e.g. suppress-high-multiple-as-flag note for FMCG)

growth:
  revenue: { cagr1y, cagr3y, cagr5y }
  ebitda: { cagr1y, cagr3y, cagr5y }
  netIncome: { cagr1y, cagr3y, cagr5y }
  eps: { cagr1y, cagr3y, cagr5y }
  bvps: { cagr3y, cagr5y }
  ocf: { cagr1y, cagr3y, cagr5y }
  fcf: { cagr1y, cagr3y }
  qualityFlags: { profitVsRevenueCagrDivergence, revenueVsAssetCagrDivergence }
  sgr, reinvestmentRate (cross-ref), growthConsistencyScore (0-5)

peerBenchmark: (only computed when include_peers=True; empty/available:false on peer sub-calls)
  peers: array of { symbol, name, marketCap, peerSource } (top 4, sorted marketCap desc, from extra_service.get_peers)
  matrix: 18 metrics × (target + up to 4 peers), each cell { value, rankAmongSet }
  cccRoceQuadrant: array of { symbol, ccc, roce, quadrantLabel }
  relativeStrengths: array of plain-English bullets, one per metric, e.g. "Rank 2 of 5 on ROIC"

overallGrade:
  letter ("A+".."F")
  score (0-100)
  weightingBreakdown: array of { pillar, weight, subScore, renormalized (boolean) }
  verdictSentence (string, template selected by lowest-scoring active pillar)
  redFlagCount, suppressedFlagCount
  specialStructureBadge (null | "Investment Holding Structure" | "BFSI — Phase 2 Module Required")
```

### 1.3 Graceful Partial Degradation Rules

1. **Universal contract:** every suppressible branch carries `available: bool` and, when false, `reason: str` — this exact shape is already proven in the codebase (`stock_service.compute_technicals`'s `news_gate`/`market_regime` blocks use `{"available": False, "reason": "..."}` today). New code follows the same shape, not a new one.
2. **IPOs / short history:** fewer than 2 fiscal years available → CAGR/trend fields return `null` with the metric-level reason `"insufficient history (Nx FY only)"`. Never crash; never fabricate a CAGR from 1 data point.
3. **Holding Company gate (1.5):** suppresses Pillars 4, 5 (partially — capital structure sub-block only, liquidity stays), 6 entirely, plus Piotroski/Beneish/Sloan classification (raw numbers may still be shown as "Not Applicable — Investment Holding Structure" rather than hidden).
4. **BFSI gate:** suppresses essentially the entire standard 10-pillar output. Returns a top-level `available: false` with `reason: "Banks/NBFC require NIM, GNPA/NNPA, PCR, CASA, Cost-to-Income, Credit Cost, CRAR — a separate BFSI schema. Recommended as a Phase 2 module, not force-fit into this engine."` — this mirrors the brief's own recommendation and is treated as a hard architectural boundary, not a soft suppression.
5. **Missing lease-liability line specifically:** treated as `0`, not `null` — absence of a lease-liability row is economically meaningful (the company has no Ind AS 116 lease liabilities, common pre-FY19-20 or for asset-light non-lessee businesses), unlike a missing core P&L/BS line, which is a genuine data gap and must be `available:false` at the metric level, never silently zeroed.
6. **Capital-raise years:** only SGAI/LVGI *interpretation* is suppressed (the raw index values still compute and display, flagged `"suppressed — capital raise event distorts leverage/SG&A indices this year"`); the rest of Beneish, and every other pillar, computes normally.
7. **Per-pillar isolation:** each of the 10 pillar calculators, each forensic sub-computation, and each peer's `analyze_fundamentals` call is individually wrapped so one failure never blanks the rest of the payload — this mirrors the existing try/except-per-feature pattern already in `stock_service.compute_technicals` around its Kotak/bhavcopy/factor calls (each wrapped independently, each logging and degrading on its own).
8. **Peer recursion guard:** `analyze_fundamentals(symbol, include_peers=True)` — the peer loop always calls `analyze_fundamentals(peer_symbol, include_peers=False)`. This is a new, explicit design resolution the original brief did not specify: without it, analyzing Peer A would try to fetch Peer A's peers (which might include the original symbol or Peer B), each of which would try to fetch further peers — unbounded fan-out. `include_peers=False` short-circuits Pillar 10 for every peer sub-call, returning `peerBenchmark.available:false, reason:"peer sub-call"` for that nested object.

### 1.4 Overall Fundamental Grade Weighting Algorithm

**Design principle, stated explicitly because it is a modeling choice, not a given:** valuation is deliberately **excluded** from the Grade. A grade meant to answer "is this business's accounting and operating quality sound" should not be conflated with "is this stock cheap" — a wonderful business can be expensive, and blending the two is a well-known modeling mistake that would make the Grade unusable as a pure quality signal. Valuation is shown as its own Pillar 8 output, never folded into `overallGrade`.

**Weights (sum to 100, active pillars only):**
| Pillar | Weight | Sub-score basis |
|---|---|---|
| Forensics / Red Flag Engine | 30 | 100 − (10 × WARNING count) − (20 × RED/CRITICAL count), floored at 0; Piotroski F≥7 adds back 10, F≤3 subtracts 10 (capped 0–100) |
| Cash Flow Quality | 20 | Blend of OCF/NI bucket score, OCF/EBITDA bucket score, count of FCF-positive years (out of 5) |
| Profitability & Returns | 20 | Blend of ROIC-vs-WACC spread (positive/sustained scores highest), ROE level and trend, DuPont quality (margin-driven > leverage-driven) |
| Solvency | 15 | Net Debt/EBITDA (ex-lease) bucket, Interest Coverage (ex-lease) bucket, DSCR bucket |
| Growth Quality | 10 | Growth Consistency Score (0-5) rescaled, penalized by profit-vs-revenue and revenue-vs-asset CAGR divergence flags |
| Efficiency | 5 | CCC trend direction, turnover trend direction |

**Suppressed-pillar handling (important correctness rule):** if Efficiency or Profitability is suppressed by the Holding Company gate, its weight is **not** counted as zero — that would unfairly penalize a structurally-gated entity for a gate that reflects business-model reality, not a quality defect. Instead, remaining active pillars' weights are **renormalized proportionally to sum to 100**. Example: Holding Company suppresses Profitability (20) and Efficiency (5) → the remaining 75 points of weight (Forensics 30, Cash Flow 20, Solvency 15, Growth 10) are scaled up by ×(100/75) to again sum to 100.

**Letter mapping:** ≥90 → A+, 80–89 → A, 70–79 → B+, 60–69 → B, 50–59 → C, 35–49 → D, <35 → F.

**Verdict sentence selection:** rather than one fixed sentence per letter band (which would read as robotic and identical across unrelated companies), the template is selected by **which active pillar scored lowest**, keyed off band × weakest-pillar, e.g.:
- A+/A band, weakest pillar = Efficiency → *"A wealth-compounding franchise with pristine accounting; efficiency metrics lag peers but are not a quality concern at this grade."*
- D/F band, weakest pillar = Forensics → *"Severe earnings-quality and red-flag concentration — treat reported numbers with active skepticism until the flagged items are independently resolved."*
- D/F band, weakest pillar = Solvency → *"Capital destruction and covenant-level solvency stress dominate the picture; the accounting itself may be clean, but the balance sheet is not."*
Each band × weakest-pillar combination gets 2–3 phrasing variants so the same company re-scored a quarter later doesn't read identically if nothing material changed — cosmetic, but avoids the deck feeling templated across a large coverage universe.

### 1.5 Holding Company Gate Logic

**Trigger (exact, per Audit Finding 8):** `(otherIncome / totalIncome) > 0.70` **AND** `(investments / totalAssets) > 0.50`.

**Implementation notes (new resolution — the brief did not specify how "Total Income" is derived, since it is not a standard yfinance row):**
- `otherIncome` — aliases `"Other Income Expense"`, `"Other Non Operating Income Expenses"`, `"Total Other Income Expense Net"`.
- `totalIncome` is **computed**, not looked up: `totalIncome = totalRevenue + otherIncome` (where `totalRevenue` uses the standard revenue aliases from Section 2). It must never be pulled from a row literally named "Total Income" — no such row reliably exists across yfinance's statement schema.
- `investments` — aliases `"Long Term Investments"`, `"Investments And Advances"`, `"Investmentin Financial Assets"`.
- **Defensive rule:** if the `otherIncome` row is genuinely absent (`None`, not zero), the gate **cannot** fire — default to `isHoldingCompany: false` rather than risk a false positive built on a missing numerator. A company should never be silently reclassified as a holding structure because a field failed to resolve.

**On trigger:** suppress Pillars 4, 6 entirely and the capital-structure sub-block of Pillar 5; mark Piotroski/Beneish/Sloan `"Not Applicable — Investment Holding Structure"`; populate `phase2Stubs.navDiscount` (`available:false`, Phase 2) and compute `dividendIncomeStability` (5-year coefficient of variation of dividend income — this one **is** computable from `.cashflow`'s dividend-received-adjacent lines plus `.info`, unlike NAV) as the two Missing-Metric-#... replacements the brief specifies.

### 1.6 Altman Z Sector Router — Implementation Approach

Router keyed off `sectorBucket` (Section 4.1), evaluated as a priority-ordered decision list, **not** a flat lookup, because more than one condition can be true simultaneously and order resolves the conflict:

1. `sectorBucket` ∈ {Banks/NBFC, Telecom, Airlines} **or** book equity ≤ 0 → **suppressed**. Display: *"Not meaningful for this sector — see Net Debt/EBITDA trend instead."*
2. `sectorBucket` ∈ {IT/Software/Services, FMCG/Consumer Staples, Services} → **Z″ EM (1995)**, X5 (asset turnover) term dropped.
3. `sectorBucket` == Pharma/API/CDMO/Chemicals → **new resolved ambiguity:** the brief lists Pharma under both the Z″EM row and (via Audit Finding 12) treats API/CDMO as asset-heavier and structurally distinct from branded/formulations pharma, without giving a splitting rule. Resolution: route to **Z″ EM** by default; if `netPPE / totalAssets > 0.40` (the asset-heavy bulk-drug/API manufacturing signature), fall through to **Z′ revised (1983)** instead. This is now a fully deterministic rule, not left to the coder's judgment.
4. Market cap < ₹5,000 Cr **or** `.info["marketCap"]` timestamp stale >30 days (thin/illiquid small-cap definition, newly specified — the brief did not define the threshold) → **Z′ revised (1983)**.
5. `sectorBucket` ∈ {Auto/Manufacturing, Commodities/Metals/O&G/Mining, EPC/Capital Goods/Defense/Infra} and not caught by rule 4 → **Z original (1968)**.
6. Anything unmatched by rules 1–5 → default fallback to **Z′ revised (1983)** (the most broadly robust variant, since it does not assume public-market book values the way the 1968 original does), tagged `altmanModelSelectionReason: "default fallback — sector bucket unmapped"` so the gap is visible rather than silently guessed.

Output always includes `"altmanModel"` (e.g. `"Z_DOUBLE_PRIME_EM_1995"`) and `"altmanModelSelectionReason"` so every score is traceable to the rule that produced it.

---

## SECTION 2: EXHAUSTIVE MATHEMATICAL & ALIAS MAPPING TABLE

All ₹-denominated absolute figures are divided by 10^7 (yfinance reports paise-free rupees; ÷10^7 → ₹ Crores) at the point of extraction inside `_val()`'s caller, never inside `_val()` itself (which stays a pure lookup). Every alias list is intentionally redundant — this is the entire point of an alias-resolving accessor: yfinance's underlying schema varies by ticker and by library version, and the six names confirmed real in Section 1.0(C) (`"Total Revenue"`, `"Operating Income"`, `"Net Income"`, `"EBITDA"`, `"Gross Profit"`, `"Total Assets"`, `"Total Debt"`, `"Stockholders Equity"` / `"Total Stockholder Equity"` as a proven OR-fallback pair, `"Cash And Cash Equivalents"`, `"Operating Cash Flow"`, `"Free Cash Flow"`, `"Capital Expenditure"`) anchor each list; the rest extend from established yfinance/yahooquery convention and must be confirmed by Task 1 (live schema reconnaissance) before being treated as final.

### 2.1 Pillar 1 — Income Statement (18 rows)

| Metric | Formula | yfinance Aliases | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| Total Revenue | direct | `"Total Revenue"`, `"Operating Revenue"`, `"Total Revenues"` | Trend only, no threshold | 1 | — |
| Revenue YoY Growth % | (Revₜ/Revₜ₋₁)−1 | (derived) | Context metric | 1 | — |
| Revenue 3Y CAGR | (Rev₀/Rev₋₃)^(1/3)−1 | (derived) | Context metric | 1 | — |
| Revenue 5Y CAGR | (Rev₀/Rev₋₄)^(1/4)−1 | (derived) | Context metric | 1 | — |
| Revenue Quality Flag | Rev CAGR vs Asset Turnover trend | (derived, cross-pillar) | Diverging = flag "growth may be acquisition/price-led" | 1 | — |
| COGS % of Revenue | COGS/Revenue | `"Cost Of Revenue"`, `"Reconciled Cost Of Revenue"` | Trend | 1 | — |
| Gross Profit / Margin % | Rev−COGS | `"Gross Profit"` | Expansion ✅ / contraction ⚠️ | 1 | — |
| Employee Cost + SG&A % Rev | SGA/Revenue | `"Selling General And Administration"`, `"SGA Expense"` | Trend | 1 | — |
| EBIT / Operating Margin % | direct | `"EBIT"`, `"Operating Income"` | Trend | 1 | — |
| EBITDA / Margin % | EBIT + D&A | `"EBITDA"`, `"Normalized EBITDA"` | Ind AS 116 comparability flag if FY19-20 in range | 1 | **Finding 1** |
| Operating Leverage | %ΔRev vs %ΔEBIT | (derived) | Rev%>EBIT% growth in tandem = positive leverage | 1 | — |
| Margin Cascade | Gross→Op→PBT→Net | (derived) | Identify compression layer | 1 | — |
| Interest Exp % of EBIT (reported) | InterestExp/EBIT | `"Interest Expense"`, `"Interest Expense Non Operating"` | Includes lease interest | 1 | **Finding 1** |
| Interest Burden Ex-Lease | FinancialInterest/EBIT | Financial interest = reported − lease interest (see 2.2 lease split) | >40% flag applies ONLY here, not to reported | 1 | **Finding 1, 10** |
| Effective Tax Rate (3Y avg) | TaxProvision/PretaxIncome, 3Y avg | `"Tax Provision"`, `"Pretax Income"` | See Section 3 Flag #11 for full gating | 1 | **Finding 3** |
| Other Income % of PBT | OtherIncome/PBT | `"Other Income Expense"`, `"Total Other Income Expense Net"` | >15% flag | 1 | — |
| Basic EPS + CAGR | direct + CAGR | `"Basic EPS"`, `"Diluted EPS"` (fallback) | Trend | 1 | — |
| EPS vs Revenue CAGR Divergence | EPS CAGR / Rev CAGR | (derived) | >2× ratio → flag | 1 | — |

### 2.2 Pillar 2 — Balance Sheet (23 rows)

| Metric | Formula | yfinance Aliases | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| Total Assets | direct | `"Total Assets"` | Trend | 2 | — |
| Current / Non-Current split | direct/TA | `"Current Assets"`, `"Total Non Current Assets"` | % of total, trend | 2 | — |
| Cash & Equivalents | direct | `"Cash And Cash Equivalents"`, `"Cash Cash Equivalents And Short Term Investments"` | Abs + %TA | 2 | — |
| Receivables / DSO | direct, ×365/Rev | `"Receivables"`, `"Accounts Receivable"`, `"Gross Accounts Receivable"` | DSO trend | 2 | **Finding 5 (EPC gate)** |
| Inventory / DIO | direct, ×365/COGS | `"Inventory"` | DIO trend | 2 | **Finding 12 (Pharma gate)** |
| Net PPE / Fixed Asset Turnover | direct, Rev/PPE | `"Net PPE"`, `"Gross PPE"` | Trend | 2 | — |
| Intangibles & Goodwill | direct, %TA | `"Goodwill And Other Intangible Assets"`, `"Goodwill"` | >25% flag | 2 | — |
| CWIP | direct, %TA | `"Construction In Progress"`, `"CWIP"` | Stalled-project flag if CWIP static across 2+ years while %TA elevated | 2 | — |
| **financialDebt (NEW split)** | ShortTermBorrow + LongTermBorrow | `"Short Long Term Debt"`, `"Long Term Debt"`, `"Other Long Term Borrowings"`, `"Current Debt"` — **excludes** lease lines | Excludes Ind AS 116 leases entirely | 2 | **Finding 1** |
| **leaseLiabilities (NEW split)** | current + non-current lease liability | `"Lease Liability"`, `"Current Lease Obligation"`, `"Finance Lease Payable"`, `"Long Term Lease Liability"` | Reported separately, never merged into financialDebt | 2 | **Finding 1** |
| Total Debt (reference only) | financialDebt + leaseLiabilities | `"Total Debt"` (cross-check only) | Labeled "reference," never the primary covenant figure | 2 | **Finding 1** |
| Debt-to-Equity (primary) | financialDebt/Equity | (derived) | Primary leverage read | 2 | **Finding 1** |
| Debt-to-Equity (secondary, total) | totalDebtReference/Equity | (derived) | Secondary, for completeness | 2 | **Finding 1** |
| Net Debt/EBITDA (reported) | (TotalDebt−Cash)/EBITDA | (derived) | Secondary | 2 | **Finding 1** |
| Net Debt/EBITDA (ex-lease) | (financialDebt−Cash)/EBITDA | (derived) | **PRIMARY** distress signal; >3.5 = 🔴 | 2 | **Finding 1** |
| Trade Payables / DPO | direct, ×365/COGS | `"Accounts Payable"`, `"Payables"` | Trend | 2 | — |
| Contingent Liabilities | n/a | n/a | `available:false, reason:"AR notes disclosure — not in yfinance. Phase 2."` | 2 | **Finding 13** |
| Net Working Capital | CA−CL | (derived) | Trend | 2 | — |
| WC % of Revenue | NWC/Rev | (derived) | Trend | 2 | — |
| CCC | DSO+DIO−DPO | (derived) | Suppressed as primary flag for Real Estate; 2.5-3.0× persistence gate for EPC | 2 | **Finding 5, 6** |
| BVPS | Equity/SharesOut | `"Common Stock Equity"`, `"Stockholders Equity"` | Trend | 2 | — |
| TBVPS | (Equity−Intangibles−Goodwill)/Shares | (derived) | Trend | 2 | — |
| Retained Earnings growth | direct YoY | `"Retained Earnings"`, `"Retained Earnings Accumulated Deficit"` | Trend; feeds Altman RE/TA term | 2 | **Finding 9** |

### 2.3 Pillar 3 — Cash Flow (17 rows)

| Metric | Formula | yfinance Aliases | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| OCF | direct | `"Operating Cash Flow"`, `"Cash Flow From Continuing Operating Activities"` | Trend | 3 | — |
| OCF/NI (Golden Ratio) | OCF/NetIncome | (derived) | >1.0 ✅, 0.5–1.0 🟡, <0.5 🔴, <0 while NI>0 🔴🔴 | 3 | — |
| OCF/EBITDA | OCF/EBITDA | (derived) | >70% ✅, <50% ⚠️ | 3 | — |
| FCF | OCF−CapEx | `"Free Cash Flow"` (cross-check) | Trend | 3 | — |
| FCF Margin | FCF/Revenue | (derived) | Trend | 3 | — |
| Cumulative 5Y OCF vs NI | Σ5y OCF vs Σ5y NI | (derived) | OCF materially < NI cumulatively = red flag | 3 | — |
| CapEx | direct | `"Capital Expenditure"`, `"Purchase Of PPE"` | Trend | 3 | — |
| CapEx/Revenue | CapEx/Rev | (derived) | Capital intensity | 3 | — |
| CapEx/Depreciation | CapEx/D&A | `"Depreciation And Amortization"`, `"Depreciation Amortization Depletion"` | >1.5 growing, 0.8–1.5 steady, <0.5 milking | 3 | — |
| Growth CapEx proxy | CapEx−Depreciation | (derived) | Positive = expansionary | 3 | — |
| Deferred Tax P&L Impact | direct | `"Deferred Income Tax"`, `"Deferred Tax"`, `"Change In Deferred Tax"` | Feeds adjusted Sloan | 3 | **Finding 2** |
| Net borrowing trend | ΔDebt | (derived from financialDebt) | Trend | 3 | — |
| Net dilution / buyback trend | direct | `"Issuance Of Capital Stock"`, `"Repurchase Of Capital Stock"` | Trend; feeds capital-raise detector | 3 | **Finding 11** |
| Dividend Payout Ratio + FCF coverage | DivPaid/NI, DivPaid/FCF | `"Cash Dividends Paid"`, `"Common Stock Dividend Paid"` | Payout > FCF = unsustainable | 3 | — |
| Total Shareholder Yield | (Div+Buyback)/MarketCap | (derived) | Trend | 3 | — |
| Capital-raise event detector | SharesOut YoY >5% | `"Ordinary Shares Number"`, `"Share Issued"` | Marks year for SGAI/LVGI suppression | 3 | **Finding 11** |
| Cash Self-Sufficiency Test | OCF ≥ CapEx+Div+DebtRepay ? | (derived, boolean) | Can the business fund itself without new borrowing | 3 | — |

### 2.4 Pillar 4 — Profitability & Returns (13 rows)

| Metric | Formula | yfinance Aliases / Source | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| ROE | NI/AvgEquity | (derived) | Trend | 4 | — |
| ROA | NI/AvgAssets | (derived) | Trend | 4 | — |
| ROCE | EBIT/(TA−CL) | (derived) | Trend | 4 | — |
| ROIC | NOPAT/InvestedCapital | NOPAT = EBIT×(1−taxRate); InvestedCapital = financialDebt+Equity−Cash | vs WACC (Pillar 5) | 4 | — |
| DuPont 3-Factor | Margin×Turnover×Leverage | (derived) | Identify which driver moves ROE | 4 | — |
| DuPont 5-Factor | TaxBurden×InterestBurdenExLease×EBITMargin×Turnover×Leverage | Interest Burden uses ex-lease figure | Identify driver, ex-lease-corrected | 4 | **Finding 1** |
| Incremental ROE | ΔNI/ΔEquity | (derived) | Marginal capital efficiency | 4 | — |
| Incremental ROIC | ΔNOPAT/ΔInvestedCapital | (derived) | Marginal capital efficiency | 4 | — |
| Reinvestment Rate | (NetCapEx+ΔWC)/NOPAT | (derived) | X-axis of quadrant | 4 | — |
| Capital Allocation Quadrant | Reinvestment Rate × Incremental ROIC | (derived) | 4-way classification, see 1.2 schema | 4 | New Institutional Metric #2 |
| WACC | We×Ke+Wd×Kd×(1−t) | Ke=7%+β×6%; Kd=FinancialInterest/financialDebt; β from `.info["beta"]` | Feeds ROIC-vs-WACC and EPV | 4/5/8 | — |
| Cost of Equity (Ke) | CAPM | rf=7.0%, ERP=6.0%, β from `.info` | — | 4/5 | — |
| Cost of Debt pre-tax (Kd) | FinancialInterest/financialDebt | (derived, ex-lease) | — | 4/5 | **Finding 1** |

### 2.5 Pillar 5 — Liquidity & Solvency (14 rows)

| Metric | Formula | yfinance Aliases | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| Current Ratio | CA/CL | `"Current Assets"`, `"Current Liabilities"` | Suppressed as primary flag for Real Estate | 5 | **Finding 6** |
| Quick Ratio | (CA−Inventory)/CL | (derived) | Trend | 5 | — |
| Cash Ratio | Cash/CL | (derived) | Trend | 5 | — |
| 6-Month Survival Test | Cash/(MonthlyOpex) | Opex ≈ (COGS+SGA)/12 | Months of runway | 5 | — |
| Net Debt/EBITDA Ex-Lease | see 2.2 | — | Primary covenant, >3.5 🔴 | 5 | **Finding 1** |
| Interest Coverage Ex-Lease | EBIT/FinancialInterest | (derived) | <2.0 🔴 | 5 | **Finding 1, 10** |
| DSCR | OCF/(FinancialInterest+PrincipalRepay) | `"Repayment Of Debt"` for principal proxy | <1.0 🔴 | 5 | — |
| Fixed Charge Coverage | (EBIT+LeasePayment)/(FinancialInterest+LeasePayment) | Lease payment from `"Operating Lease Payments"` or leaseLiabilities amortization proxy | Airlines/retail-relevant | 5 | **Finding 1, 7** |
| Equity % vs financialDebt % | Equity/(Equity+financialDebt) | (derived) | Capital structure mix, ex-lease | 5 | **Finding 1** |
| WACC (cross-ref) | see 2.4 | — | — | 5 | — |
| EBITDAR Coverage (Airlines only) | (EBIT+AircraftRent)/(Interest+AircraftRent) | `"Operating Lease Payments"` as aircraft-rent proxy | Replaces plain Interest Coverage for Airlines bucket | 5 | **Finding 7** |
| Net Debt/EBITDA 5Y trend (Telecom/Airlines) | rolling series | (derived) | Replaces suppressed Altman Z | 5 | **Finding 7** |
| FCF trend (Telecom/Airlines) | rolling series | (derived) | Replaces suppressed Altman Z | 5 | **Finding 7** |
| Thresholds summary | — | — | NetDebt/EBITDA(ExLease)>3.5🔴; IntCov(ExLease)<2.0🔴; DSCR<1.0🔴 | 5 | **Finding 1** |

### 2.6 Pillar 6 — Efficiency & Activity (8 rows)

| Metric | Formula | yfinance Aliases | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| Total Asset Turnover | Rev/AvgTA | (derived) | Interpret within-sector for IT, not vs. manufacturing | 6 | Sector override table |
| Fixed Asset Turnover | Rev/AvgNetPPE | (derived) | De-emphasized (not removed) for IT | 6 | Sector override table |
| Working Capital Turnover | Rev/AvgNWC | (derived) | Trend | 6 | — |
| Inventory Turnover | COGS/AvgInventory | (derived) | Trend | 6 | **Finding 12** |
| Receivables Turnover | Rev/AvgReceivables | (derived) | Trend | 6 | **Finding 5** |
| Payables Turnover | COGS/AvgPayables | (derived) | Trend | 6 | — |
| CCC trend/flag | see 2.2 | — | >20% YoY expansion flag; suppressed for Real Estate/EPC | 6 | **Finding 5, 6** |
| Negative CCC signal | CCC<0 | — | ✅✅ for FMCG/retail (collect before paying suppliers) | 6 | — |

### 2.7 Pillar 7 — Forensic Scorecards (24 rows)

| Metric | Formula | yfinance Aliases / Source | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| Piotroski F-Score (9 tests) | binary sum | ROA>0; CFO>0; ΔROA>0; CFO>NI; ΔLTDebtRatio<0; ΔCurrentRatio>0; noNewShares; ΔGrossMargin>0; ΔAssetTurnover>0 | ≥7 Strong, 4–6 Moderate, ≤3 Weak | 7 | — |
| Beneish DSRI | (Rec/Rev)ₜ / (Rec/Rev)ₜ₋₁ | Receivables, Revenue aliases | Component of M-Score | 7 | — |
| Beneish GMI | GrossMarginₜ₋₁/GrossMarginₜ | Gross Profit, Revenue aliases | Component | 7 | — |
| Beneish AQI | 1−[(CA+NetPPE)/TA]ₜ vs ₜ₋₁ | (derived) | Component | 7 | — |
| Beneish SGI | Revₜ/Revₜ₋₁ | (derived) | Component; suppressed in capital-raise years | 7 | **Finding 11** |
| Beneish DEPI | DepRateₜ₋₁/DepRateₜ | Depreciation, Gross PPE aliases | **Cross-check vs CWIP→Gross Block transition before red escalation** | 7 | **Finding 2** |
| Beneish SGAI | (SGA/Rev)ₜ / (SGA/Rev)ₜ₋₁ | SGA, Revenue aliases | **Suppressed in capital-raise year + following year** | 7 | **Finding 11** |
| Beneish LVGI | Leverageₜ/Leverageₜ₋₁ | financialDebt, TA aliases | **Suppressed in capital-raise year + following year** | 7 | **Finding 11** |
| Beneish TATA | (NI−CFO)/TA | (derived) | Component | 7 | — |
| Beneish M-Score | 8-variable weighted sum | (derived) | >−1.78 High, −2.22 to −1.78 Moderate, <−2.22 Clean; **standalone escalation to red requires ≥2 corroborating custom red flags** | 7 | **Finding 11** |
| Altman Z original (1968) | 1.2(WC/TA)+1.4(RE/TA)+3.3(EBIT/TA)+0.6(MCap/TL)+1.0(Rev/TA) | see 2.2/2.4 aliases | Safe>2.99, Grey 1.81–2.99, Distress<1.81 | 7 | **Finding 9** |
| Altman Z′ revised (1983) | 0.717(WC/TA)+0.847(RE/TA)+3.107(EBIT/TA)+0.420(BookEq/TL)+0.998(Rev/TA) | same | Safe>2.9, Grey 1.23–2.9, Distress<1.23 | 7 | **Finding 9** |
| Altman Z″ EM (1995) | 6.56(WC/TA)+3.26(RE/TA)+6.72(EBIT/TA)+1.05(BookEq/TL) | same, X5 dropped | Safe>2.6, Grey 1.1–2.6, Distress<1.1 (raw thresholds as specified — note some published Z″EM variants add a +3.25 constant for bond-rating equivalence; this brief specifies the unconstant form) | 7 | **Finding 9** |
| Altman Z model selector | sectorBucket + marketCap-staleness + book-equity sign | — | See 1.6 for full router logic | 7 | **Finding 9** |
| Sloan raw accrual | (NI−OCF−ICF)/AvgTA | (derived) | Secondary figure | 7 | **Finding 14** |
| Sloan deferred-tax-adjusted | (NI−DeferredTaxPnL−OCF−ICF)/AvgTA | (derived) | **PRIMARY** figure | 7 | **Finding 2, 14** |
| Sloan threshold (mature, <10% CAGR) | — | — | Moderate>10%, Severe>25% | 7 | **Finding 14** |
| Sloan threshold (moderate, 10-20% CAGR) | — | — | Moderate>12%, Severe>27% | 7 | **Finding 14** |
| Sloan threshold (high growth, >20% CAGR) | — | — | Moderate>15%, Severe>30% | 7 | **Finding 14** |
| Promoter Shareholding YoY | `.info["heldPercentInsiders"]` delta | direct from `.info` | >3pp decline = warning | 7 | New Institutional Metric #1 |
| RPT stub | n/a | n/a | `available:false, reason:"Requires SEBI LODR BSE/NSE filing scrape — Phase 2"` | 7 | **Finding 4** |
| Promoter Pledge stub | n/a | n/a | `available:false, reason:"Requires BSE/NSE shareholding XBRL — Phase 2"` | 7 | New Institutional Metric #1 |
| Auditor Change stub | n/a | n/a | `available:false, reason:"Requires BSE corporate announcements + AR text-mining — Phase 2. Historically high-signal (Satyam, DHFL, IL&FS)."` | 7 | New Institutional Metric #3 |
| Contingent Liabilities stub | n/a | n/a | `available:false, reason:"AR notes disclosure — Phase 2"` | 7 | **Finding 13** |

### 2.8 Pillar 8 — Valuation (16 rows)

| Metric | Formula | yfinance Aliases | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| Trailing P/E | direct | `.info["trailingPE"]` | Context | 8 | — |
| Forward P/E | direct | `.info["forwardPE"]` | Context | 8 | — |
| P/B | direct | `.info["priceToBook"]` | Suppress as auto-flag for FMCG | 8 | Sector override table |
| Price-to-Tangible-Book | Price/TBVPS | (derived, uses 2.2 TBVPS) | Context | 8 | — |
| P/S | MCap/Revenue | (derived) | Context | 8 | — |
| EV/EBITDA | EV/EBITDA | `.info["enterpriseValue"]` | **Primary valuation metric for Commodities/Metals/O&G** | 8 | Sector override table |
| EV/EBIT | EV/EBIT | (derived) | Context | 8 | — |
| EV/Revenue | EV/Revenue | (derived) | Context | 8 | — |
| PEG | PE/(3Y EPS CAGR) | (derived) | <1 potentially undervalued | 8 | — |
| FCF Yield | FCF/MarketCap | (derived) | "Real" earnings yield | 8 | — |
| Earnings Yield vs rf | (1/PE) vs 7% G-Sec | (derived) | Spread context | 8 | — |
| Dividend Yield | direct | `.info["dividendYield"]` | Trailing | 8 | — |
| Graham Number | √(22.5×EPS×BVPS) | (derived) | Deterministic intrinsic estimate | 8 | — |
| EPV | NormalizedEBIT×(1−t)/WACC | uses 2.4 WACC | Deterministic intrinsic estimate | 8 | — |
| Margin of Safety | (EPV−Price)/EPV | (derived) | >30% ✅, 0-30% 🟡, <0 🔴 | 8 | — |
| Own-history P/E, P/B, EV/EBITDA vs 5Y median | rolling | (derived) | Never auto-flag high multiple for FMCG; flag only >50% premium to own history | 8 | Sector override table |

### 2.9 Pillar 9 — Growth (13 rows)

| Metric | Formula | yfinance Aliases | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|---|
| Revenue CAGR (1/3/5Y) | see 2.1 | — | — | 9 | — |
| EBITDA CAGR (1/3/5Y) | see 2.1 | — | — | 9 | — |
| Net Income CAGR (1/3/5Y) | (derived) | `"Net Income"` | — | 9 | — |
| EPS CAGR (1/3/5Y) | see 2.1 | — | — | 9 | — |
| BVPS CAGR (3/5Y) | see 2.2 | — | — | 9 | — |
| OCF CAGR (1/3/5Y) | see 2.3 | — | — | 9 | — |
| FCF CAGR (1/3Y) | see 2.3 | — | — | 9 | — |
| Profit vs Revenue CAGR divergence | ratio | (derived) | Large gap = quality flag | 9 | — |
| Revenue vs Asset CAGR divergence | ratio | (derived) | Large gap = quality flag | 9 | — |
| SGR | ROE×(1−PayoutRatio) | (derived) | Sustainable growth ceiling | 9 | — |
| Reinvestment Rate (cross-ref) | see 2.4 | — | — | 9 | — |
| Growth Consistency Score | count of positive-growth years / 5 | (derived) | 0–5 scale | 9 | — |
| Real Estate 3Y rolling override | rolling avg replaces YoY | — | Applies to all Pillar 9 metrics for Real Estate bucket | 9 | **Finding 6** |

### 2.10 Pillar 10 — Peer Benchmarking (19 rows — reuses formulas defined above; new items only)

| Metric | Formula / Source | Threshold / Interpretation | Pillar | Audit Correction |
|---|---|---|---|---|
| Peer discovery | **reuse** `extra_service.get_peers(symbol)` (4-tier engine, confirmed real) — do not build a new peer-discovery function | Top 4 by `marketCap`, sorted desc | 10 | — |
| Metrics 1-17 | Revenue Growth 1Y/3Y, Gross/Op/Net Margin, ROE, ROIC, D/E (financial, ex-lease), Net Debt/EBITDA (ex-lease), Interest Coverage (ex-lease), Current Ratio, P/E, EV/EBITDA, P/B, FCF Yield, Piotroski, Altman Z (+model) | all cross-referenced from Sections 2.1–2.8 | Sortable, rank shown per metric | 10 | **Finding 1** (ex-lease everywhere) |
| Metric 18: FII/DII Holding % | `.info["heldPercentInstitutions"]` | Cross-sectional snapshot rank; quarterly trend is Phase 2 | 10 | New Institutional Metric #5 |
| CCC vs ROCE Quadrant | X=CCC, Y=ROCE per peer | Low CCC+High ROCE="Quality Compounder"; Low CCC+Low ROCE="Efficient but Marginal"; High CCC+High ROCE="Capital-Intensive Winner"; High CCC+Low ROCE="Value Trap/Avoid" | 10 | New Institutional Metric #4 |
| Relative Strengths bullets | rank vs sector median per metric | Plain-English, e.g. "Rank 2 of 5 on ROIC" | 10 | — |

---

## SECTION 3: COMPLETE RED FLAG ENGINE SPECIFICATION

**Severity taxonomy (new — formalizes the brief's mixed emoji/word usage into four consistent, code-branchable levels):**
- `INFO` — contextual only, no negative connotation (e.g. sector-holiday ETR note, Ind AS 116 comparability note, suppressed-flag disclosures)
- `WARNING` (amber) — worth investigating, not inherently a fraud/distress signal
- `RED` — significant, meaningfully elevates risk
- `CRITICAL` (red, bold, pulsing per the existing `animate-pulse` convention) — severe, fraud-adjacent or imminent-distress

**Resolved ambiguity:** Audit Finding 11 says Beneish escalation requires corroboration from "≥2 of the 15 custom red flags" — written before Flag #16 (Promoter Shareholding) was added elsewhere in the same brief. There is no principled reason to exclude Flag #16 from corroboration, so this plan reads the rule as **≥2 of the 16 custom red flags**, and treats the "15" in the original text as a numbering artifact of the brief's own drafting order, not a deliberate exclusion.

| # | Red Flag Name | Standard Trigger | Sector Override | Alert String Template | Severity | Audit Finding |
|---|---|---|---|---|---|---|
| 1 | Revenue vs Receivables Divergence | Receivables growth > 1.5× Revenue growth (YoY) | EPC/Capital Goods/Defense/Infra: >2.5× **and** persists 2+ consecutive years | *"⚠️ Sales grew {rev_growth}% but uncollected bills surged {rec_growth}%. Possible channel stuffing, round-tripping, or aggressive revenue recognition."* | WARNING | **5** |
| 2 | Profit vs Cash Flow Divergence | NI>0 **and** OCF<0 | — | *"Company reports ₹{ni} Cr profit but burned ₹{abs(ocf)} Cr cash. Reported profit is being driven by accruals, not real cash."* | CRITICAL | — |
| 3 | Rising Inventory Without Revenue Growth | Inventory growth > 2× Revenue growth | Pharma/API/CDMO/Chemicals: >3.0–3.5× **and** co-occurring gross margin compression required to escalate | *"⚠️ Inventory piling up {inv_growth}% while sales grew only {rev_growth}%. Possible obsolescence risk or demand slowdown — check if gross margin is also compressing; if not, may reflect strategic supply-chain buffering, not a demand problem."* | WARNING | **12** |
| 4 | Other Income Dependence | Other Income > 20% of Pretax Income | — | *"⚠️ Core business profitability is weak. {pct}% of pre-tax profit comes from non-operational sources."* | WARNING | — |
| 5 | Debt Spiral Detection | financialDebt grew >15% YoY for 3 consecutive years **and** OCF flat/declining | Uses financialDebt (ex-lease), not total debt | *"Financial borrowings compounded at {debt_cagr}% annually for 3 years while OCF stagnated."* | RED | **1** |
| 6 | Equity Dilution | Share count increased >2% YoY | — | *"⚠️ Shareholder dilution: {dilution}% new shares issued. If this coincides with a QIP/rights issue, Beneish SGAI/LVGI are suppressed for this year."* | WARNING | **11** |
| 7 | Goodwill / Intangible Bloat | (Intangibles+Goodwill) > 30% of Total Assets | — | *"⚠️ {pct}% of the balance sheet is intangible. High impairment risk."* | WARNING | — |
| 8 | CapEx Collapse (Asset Milking) | CapEx/Depreciation < 0.5 for 2+ consecutive years | — | *"⚠️ CapEx is only {ratio}× depreciation for {n} years. Assets are being milked without reinvestment."* | WARNING | — |
| 9 | Unsustainable Dividend | Dividends Paid > Free Cash Flow (absolute) | — | *"Unsustainable dividend: ₹{div} Cr paid but only ₹{fcf} Cr FCF generated. Funded from debt or reserves."* | RED | — |
| 10 | Interest Coverage Crunch | EBIT / InterestBurdenExLease < 1.5 | Uses ex-lease financial interest only | *"Financial interest barely covered ({ratio}× ex-lease). One bad quarter from technical default risk."* | RED | **1, 10** |
| 11 | Tax Rate Anomaly | (A) 3Y avg ETR > 40%; (B) single-yr or 3Y-avg ETR < 10%; (C) YoY swing > 10pp | IT/SEZ/Renewable/Infra-80-IA: persistent low ETR → INFO, not a flag | (A) *"Effective tax rate averaged {etr}% over 3 years — unusually high; investigate one-time items."* (B, non-holiday sectors) *"🟡 ETR of {etr}% is unusually low for this sector — investigate."* (B, holiday sectors) *"ℹ️ ETR averaged {etr}% over 3 years — consistent with known statutory tax holiday exposure. Not flagged as anomalous."* (C) *"⚠️ ETR moved abruptly from {prev_etr}% to {curr_etr}%. Investigate deferred tax reversal, tax holiday expiry, MAT credit utilization, or one-time assessment."* | (A) RED · (B non-holiday) WARNING · (B holiday) INFO · (C) WARNING | **3** |
| 12 | Leverage-Price Divergence | financialDebt/Equity increased >20% YoY while stock price fell >20% | — | *"⚠️ Leverage increasing during price decline — potential promoter margin-call or forced-selling risk."* | WARNING | **1** |
| 13 | CCC Deterioration | CCC expanded >20% YoY | Suppressed for Real Estate and EPC | *"⚠️ CCC expanded from {ccc_prev} to {ccc_curr} days ({pct}% deterioration)."* | WARNING | **5, 6** |
| 14 | Aggressive Depreciation Policy (DEPI) | DEPI > 1.3 **and** no significant CWIP→Gross Block transition in the same year | — | *"⚠️ Depreciation rates slowing (DEPI: {depi}) without a proportional asset-commissioning event. May be artificially inflating current-year profits."* | WARNING | **2** |
| 15 | Persistent Capital Destruction | ROIC < WACC for 3+ consecutive years | — | *"Persistent capital destruction for {n} years. ROIC ({roic}%) < WACC ({wacc}%) — systematically destroying shareholder wealth."* | RED | — |
| 16 | Promoter Shareholding Decline | Promoter/insider holding declined >3pp YoY | — | *"⚠️ Promoter/insider shareholding fell {pp}pp YoY ({prev}%→{curr}%). Cross-check against pledge disclosures and open-market sale filings."* | WARNING | New Metric #1 |
| 17 | Altman Z Distress Signal | Z-score (sector-routed model) in Distress zone | Suppressed entirely for Banks/NBFC/Telecom/Airlines/negative net worth | *"Altman Z ({model}) of {score} places the company in the Distress zone for its sector-appropriate model."* | RED (Distress) / WARNING (Grey) | **9** |
| 18 | Sloan Accrual Breach | \|deferredTaxAdjustedSloan\| exceeds growth-adjusted threshold (Section 2.7) | Threshold band selected by 3Y revenue CAGR | *"Accrual ratio of {sloan}% exceeds the {band}-growth threshold of {threshold}% — a large share of reported earnings is not yet cash."* | WARNING (moderate) / RED (severe) | **2, 14** |

---

## SECTION 4: SECTOR-SPECIFIC OVERRIDE SPECIFICATION

### 4.1 sectorBucket Classifier (NEW — resolves the gap identified in 1.0.B)

This did not exist anywhere in the codebase and is new required infrastructure. Evaluated as a **priority-ordered** decision list against `.info["sector"]` and `.info["industry"]` (raw Yahoo/GICS-style strings, confirmed as the only sector data actually available via `sector_map.get_sector_map()`), plus the ratio-based gates from 1.5, in this exact order (gates before sector buckets, because a company can satisfy a sector-substring match and a ratio-gate simultaneously, and the ratio-gate should win):

1. **Holding Company gate (1.5) evaluated first, independent of sector.** If triggered → `sectorBucket = "HOLDING_COMPANY"`, regardless of what `.info["sector"]` says (a Bajaj-Holdings-style entity may carry `sector="Financial Services"` and must not be routed to the BFSI bucket).
2. **BFSI gate:** `sector == "Financial Services"` **and** `industry` contains any of `"Bank"`, `"Insurance"`, `"Asset Management"`, `"Financial - Credit Services"`, `"Financial - Capital Markets"`, `"Shadow Banks"` → `"BFSI"`.
3. `industry` contains `"Telecom"` → `"TELECOM"`.
4. `industry` contains `"Airlines"` → `"AIRLINES"` (kept distinct from Telecom despite sharing the Altman-suppression treatment, because EBITDAR coverage logic is airline-specific).
5. `sector == "Real Estate"` → `"REAL_ESTATE_CONSTRUCTION"`.
6. `industry` contains `"Engineering & Construction"`, `"Aerospace & Defense"`, `"Specialty Industrial Machinery"`, or `"Conglomerates"` (the last for L&T-style diversified EPC majors) → `"EPC_CAPITAL_GOODS_DEFENSE_INFRA"`.
7. `industry` contains `"Drug Manufacturers"`, `"Pharmaceutical"`, `"Biotechnology"`, or `"Chemicals"` → `"PHARMA_API_CDMO_CHEMICALS"` (sub-routed further for Altman purposes per 1.6 rule 3).
8. `sector == "Technology"` or `industry` contains `"Information Technology Services"` or `"Software"` → `"IT_SOFTWARE_SERVICES"`.
9. `sector == "Consumer Defensive"` → `"FMCG_CONSUMER_STAPLES"`.
10. `sector == "Energy"`, `sector == "Basic Materials"`, or `industry` contains `"Metals"`, `"Mining"`, `"Steel"` → `"COMMODITIES_METALS_OG_MINING"`.
11. `sector == "Consumer Cyclical"` **and** `industry` contains `"Auto"` → `"AUTO_MANUFACTURING"`.
12. `industry` contains `"Renewable"` or `"Utilities—Renewable"` → `"RENEWABLE_POWER_INFRA_80IA"` (flagged `confidence: "heuristic — 80-IA tax-holiday status cannot be confirmed from yfinance alone; treat as provisional until cross-checked").
13. No match → `"GENERAL_OTHER"` (standard treatment, no overrides applied).

### 4.2 Per-Bucket Override Table (implementation-ready)

| sectorBucket | Suppress | Add / Replace | Threshold Overrides | Implementation Note |
|---|---|---|---|---|
| `EPC_CAPITAL_GOODS_DEFENSE_INFRA` | Generic DSO flag (1.5×) as primary | Book-to-Bill (OrderBook/Revenue — Phase 2, order book not in yfinance), Working Capital % of Order Book (same caveat) | DSO multiplier → 2.5–3.0×, require 2-yr persistence | Government receivables + 5-10% retention money are structural; gate lives in Flag #1's evaluation branch |
| `REAL_ESTATE_CONSTRUCTION` | Current Ratio, CCC as primary flags | Customer Advances/Inventory, Unsold Inventory (months of trailing sales), Net Debt/Pre-sales (Phase 2 — pre-sales not in yfinance, stub), CWIP stalled-project flag (kept) | 3Y rolling averages for ALL Pillar 9 growth metrics | Ind AS 115 POCM makes YoY unreliable; applies to Pillars 2, 5, 6, 9 simultaneously |
| `PHARMA_API_CDMO_CHEMICALS` | — | R&D/Revenue, Export Revenue % (both from `.info` where populated), Gross Margin stability band | Inventory flag → 3.0–3.5×, requires co-occurring margin compression | DIO 120+ days is baseline; strategic stockpiling ≠ demand problem |
| `TELECOM` | Altman Z (any model), generic D/E distress flag | Net Debt/EBITDA 5Y trend, FCF trend | — | AGR dues / spectrum liabilities structural, not distress |
| `AIRLINES` | Altman Z (any model) | EBITDAR coverage (replaces plain Interest Coverage) | — | Aircraft RoU leases structural |
| `BFSI` | ALL standard ratios (inventory, gross margin, asset turnover, standard D/E, Beneish, Altman, Piotroski) | NIM, GNPA/NNPA, PCR, CASA, Cost-to-Income, Credit Cost, CRAR — **Phase 2 module, separate schema** | — | Top-level `available:false` for the whole standard engine, not a partial suppression |
| `HOLDING_COMPANY` | Pillars 4, 6 entirely; Piotroski/Beneish/Sloan classification | Discount-to-NAV % (Phase 2 stub), Dividend Income Stability (5Y CV — computable now) | Gate: OtherIncome/TotalIncome>70% AND Investments/TotalAssets>50% | See 1.5 for exact field derivation |
| `IT_SOFTWARE_SERVICES` | Inventory ratios; Fixed Asset Turnover de-emphasized (not removed) | Revenue/Employee (if `.info["fullTimeEmployees"]` populated), USD/INR sensitivity note | Compare Asset Turnover within-sector only | Altman routes to Z″EM (drops X5) |
| `FMCG_CONSUMER_STAPLES` | High P/E, high P/B as automatic red flags | Negative CCC reinforced as ✅ | Flag only >50% premium to own 5Y median, not absolute level | Brand premium justifies structurally higher multiples |
| `COMMODITIES_METALS_OG_MINING` | P/E as primary valuation | EV/EBITDA as primary; EBITDA margin volatility (stddev) | High D/E may be structural — compare within sector, not vs. market | P/E paradoxically inverted across the cycle |
| `AUTO_MANUFACTURING` | — | Order Book/Revenue where disclosed, CapEx cycle analysis | Normalize margins across 3-4 yr capex cycle before flagging compression | — |
| `RENEWABLE_POWER_INFRA_80IA` | Tax Rate Anomaly as red flag | Project-level capacity utilization if disclosable | ETR flag → INFO only | 80-IA statutory sub-15% ETR is structural; classifier confidence is heuristic (4.1 rule 12) |
| `GENERAL_OTHER` | none | none | none | Standard 10-pillar treatment, no gates beyond Holding/BFSI |

---

## SECTION 5: FRONTEND COMPONENT HIERARCHY & COLOR LOGIC

### 5.0 Grounding for this section (confirmed real, per 1.0.C)
`Panel` and `KV` are real, exported from `frontend/src/components/Panel.jsx`: `Panel` renders a `bg-[#0c0c0e]` container with a `border-zinc-800` border and a `text-[10px] tracking-[0.2em] uppercase text-zinc-400` title bar; `KV` renders a label/value row with `font-mono tabular-nums` values. Nineteen of roughly thirty-five existing panel components fetch data via `axios.get(...)` inside a `useEffect` keyed on `[symbol]`, matching `RedFlagsPanel.jsx`'s exact pattern (including its `const API = `${process.env.REACT_APP_BACKEND_URL}/api`;` constant) — `FundamentalDeck.jsx` must follow this convention, not `swr` (installed but unused anywhere in the codebase). `recharts@3.6.0` is already an installed dependency, so both quadrant visualizations use Recharts' `ScatterChart`, not a new library. `lucide-react@0.516.0` is installed; use existing icon names already proven elsewhere (`AlertTriangle`, `ShieldAlert`, plus new but standard ones: `TrendingUp`, `TrendingDown`, `Building2`, `Landmark`, `ScanSearch`, `Info`, `ChevronDown`).

### 5.1 Component Tree
```
FundamentalDeck (symbol)                                    — top-level, built on Panel/KV, gated by ENABLE_FUNDAMENTAL_DECK
 ├─ ExecutiveVerdictBanner                                   — full-width, uses overallGrade
 │   ├─ GradeBadge (A+..F)
 │   ├─ VerdictSentence
 │   ├─ RedFlagCountBadge (click → scrolls to ForensicRedFlagPanel)
 │   └─ SpecialStructureBadge (conditional: Holding Company / BFSI)
 ├─ Phase2GapPanel (collapsible)                             — lists every `available:false` stub with its reason
 ├─ ForensicRedFlagPanel (collapsible, auto-expanded if any RED/CRITICAL flag present)
 │   └─ RedFlagListItem × N (severity-colored, distinctly labeled "Forensic Accounting Red Flags" — never "Red Flags" alone, to avoid the RedFlagsPanel.jsx collision)
 ├─ PillarCardGrid (2-column responsive)
 │   ├─ IncomeStatementCard
 │   ├─ BalanceSheetCard (shows financialDebt vs leaseLiabilities split explicitly)
 │   ├─ CashFlowCard
 │   ├─ ProfitabilityCard
 │   │   ├─ DuPont3FactorVisual
 │   │   ├─ DuPont5FactorVisual
 │   │   └─ CapitalAllocationQuadrant (Recharts ScatterChart)
 │   ├─ SolvencyCard
 │   ├─ EfficiencyCard
 │   ├─ ValuationCard
 │   └─ GrowthCard
 ├─ IndAS116NotePanel (conditional — only rendered if meta.indAS116TransitionInRange)
 ├─ PeerComparisonSection
 │   ├─ PeerMatrixTable (18 metrics × up to 5 columns, sortable, rank-colored)
 │   └─ CccRoceQuadrant (Recharts ScatterChart)
 └─ RawStatementTabs (collapsible, 3 tabs: Balance Sheet | Income Statement | Cash Flow)
```

### 5.2 Props Flow
`FundamentalDeck` receives only `symbol` from `StockDetails.jsx` (mirroring every other panel's prop contract). It owns the single `axios.get` call and the `data`/`loading`/`error` state; every child below it receives its slice of `data` as a plain prop (e.g. `<ProfitabilityCard data={data.profitability} />`) — no child performs its own fetch. This matches the existing convention where `RedFlagsPanel.jsx` and siblings are self-contained fetchers but do not further delegate fetching to grandchildren.

### 5.3 Conditional Rendering / Gates
- `gates.isHoldingCompany` → render `SpecialStructureBadge` with amber styling and text *"Investment Holding Structure — standard ratios suppressed. See Phase 2 for NAV analysis."*; `ProfitabilityCard` and `EfficiencyCard` render a single amber-badged line — *"Not applicable — Investment Holding Structure"* — instead of their normal KV grid.
- `gates.isBFSI` → the entire `PillarCardGrid` is replaced by one full-width notice: *"Banks/NBFC require a dedicated BFSI schema (NIM, GNPA/NNPA, CRAR) — not force-fit into this deck. Planned as a separate module."*
- `meta.indAS116TransitionInRange` → `IndAS116NotePanel` renders; otherwise the component returns `null` (not rendered empty).
- `forensics.redFlags` with zero triggered items → `ForensicRedFlagPanel` shows the same reassuring-but-precise pattern already used by `RedFlagsPanel.jsx` (a calm one-line confirmation), adapted to this engine's own scope: *"No forensic accounting red flags triggered across the 16-point engine, Beneish, or Altman Z for this sector's model."*
- `capitalRaiseYears` non-empty → each affected year in `IncomeStatementCard`/`ForensicRedFlagPanel` gets an inline ℹ️ badge referencing the suppressed SGAI/LVGI interpretation for that year.
- Peer sub-calls (`isPeerCall: true`) never render their own `FundamentalDeck` — they exist only as data inputs to `PeerComparisonSection` on the parent symbol's render.

### 5.4 Color Thresholds (reusing the confirmed-real convention exactly — no new color system)
- `text-emerald-400` — good / above-median / Safe zone / passed test
- `text-amber-400` — caution / Grey zone / WARNING severity
- `text-red-400` — danger / Distress zone / RED severity
- `font-bold animate-pulse` (layered on `text-red-400`) — CRITICAL severity only, reserved for Flag #2 (Profit vs Cash Flow Divergence) and any flag explicitly marked CRITICAL in Section 3 — used sparingly so it retains visual weight

### 5.5 Responsive Behavior
`PillarCardGrid` collapses from 2 columns to 1 below the existing app's standard mobile breakpoint (matching the breakpoint already used by `StockDetails.jsx`'s own grid — inspect and reuse that exact Tailwind breakpoint token rather than introducing a new one). `PeerMatrixTable` becomes horizontally scrollable (`overflow-auto`) rather than reflowing on narrow viewports, consistent with how `RedFlagsPanel.jsx` already handles its own overflow (`max-h-80 overflow-auto`).

---

## SECTION 6: SEQUENTIAL STEP-BY-STEP TASK LIST FOR THE CODING AGENT

Tasks are numbered in strict dependency order. Each includes Target File, Exact Scope, Dependencies, Verification Command, and Expected Output. No task requires a design decision not already resolved in Sections 1–5.

**1. Live Schema Reconnaissance**
- Target File: none (throwaway script, not committed)
- Exact Scope: run yfinance against one ticker per sectorBucket (a bank for the BFSI-exclusion check, an EPC major, a pharma/API name, a real-estate developer, an IT services major, an FMCG name, a holding company) and dump `.balance_sheet.index.tolist()`, `.financials.index.tolist()`, `.cashflow.index.tolist()` for each. Diff against every alias list in Section 2; extend any list with real names found that aren't already covered.
- Dependencies: none
- Verification Command: `python -c "import yfinance as yf; t=yf.Ticker('RELIANCE.NS'); print(t.balance_sheet.index.tolist())"` (repeat per sample ticker)
- Expected Output: a short reconciliation note (can live in a code comment at the top of `fundamental_constants.py`, Task 2) listing any alias added or corrected versus Section 2's starting lists.

**2. `backend/fundamental_constants.py` (NEW)**
- Target File: `backend/fundamental_constants.py`
- Exact Scope: house every alias list from Section 2, every threshold from Sections 2–4, the severity enum (`INFO`/`WARNING`/`RED`/`CRITICAL`), the pillar-weight table from 1.4, and the sectorBucket priority list from 4.1 — as plain data structures (dicts/tuples/lists), no logic.
- Dependencies: Task 1
- Verification Command: `python -c "import fundamental_constants as fc; print(len(fc.ALTMAN_THRESHOLDS), len(fc.SECTOR_BUCKET_RULES))"`
- Expected Output: imports cleanly, no syntax errors, non-empty structures.

**3. `backend/fundamental_service.py` — skeleton, `_annual_frames()`, disk cache**
- Target File: `backend/fundamental_service.py`
- Exact Scope: mirror `sector_map.py`'s exact caching style — `_CACHE_PATH` (env `FUNDAMENTAL_CACHE_PATH`, default `fundamental_cache.json` in `backend/`), `_TTL_DAYS` (env `FUNDAMENTAL_TTL_DAYS`, default `"7"`), `_load_cache()`/`_save_cache()`, and `_annual_frames(symbol)` that fetches `.balance_sheet`, `.financials`, `.cashflow`, `.info` once per symbol, serializes to JSON, and returns from cache on subsequent calls within TTL. Include a `if __name__ == "__main__":` smoke block matching `sector_map.py`'s own convention.
- Dependencies: Task 2
- Verification Command: `python backend/fundamental_service.py` (should print a sample frame summary for a hardcoded test symbol with zero network calls on the second run)
- Expected Output: `fundamental_cache.json` created in `backend/`, second invocation noticeably faster (cache hit).

**4. `_val()` generic alias resolver + unit helpers**
- Target File: `backend/fundamental_service.py` (append)
- Exact Scope: `_val(df, aliases, year_idx)` — case-insensitive row lookup returning `float` or `None`, trying each alias in order until one resolves. Add `_to_crores(raw)` (÷10^7) and `_safe_divide(a, b)` (returns `None` on zero/`None` denominator, never raises `ZeroDivisionError`).
- Dependencies: Task 3
- Verification Command: `python -c "import fundamental_service as fs; df=fs._annual_frames('RELIANCE.NS')['balance_sheet']; print(fs._val(df, ['Total Assets'], 0))"`
- Expected Output: a non-`None` float for a live symbol.

**5. `get_sector_bucket(symbol)` classifier**
- Target File: `backend/fundamental_service.py` (append)
- Exact Scope: implement the priority-ordered rules from Section 4.1, calling `sector_map.get_sector_map([symbol])` for the raw Yahoo sector (batch API, single-element list) plus `.info["industry"]` for substring matching. Returns the bucket string plus a `confidence` field (`"heuristic"` for the Renewable/80-IA case).
- Dependencies: Task 4
- Verification Command: `python -c "import fundamental_service as fs; print(fs.get_sector_bucket('IRFC.NS'))"` (expect `HOLDING_COMPANY` or `BFSI`-adjacent depending on live gate values — record whichever it returns as the reconciliation baseline)
- Expected Output: one of the thirteen bucket strings from 4.1, never a crash on an unmapped sector (falls to `GENERAL_OTHER`).

**6. Holding Company gate + BFSI gate detectors**
- Target File: `backend/fundamental_service.py` (append)
- Exact Scope: `_is_holding_company(info, financials, balance_sheet)` implementing the exact trigger and defensive rule from Section 1.5; `_is_bfsi(sector_bucket)` as a simple bucket-membership check.
- Dependencies: Task 5
- Verification Command: `python -c "import fundamental_service as fs; print(fs._is_holding_company.__doc__)"` plus a manual run against a known holding company (e.g. a BSML/Bajaj-Holdings-style symbol) and a known operating company, confirming opposite booleans.
- Expected Output: correct boolean split between the two test symbols.

**7. Capital-raise-year + Ind AS 116 transition-year detectors**
- Target File: `backend/fundamental_service.py` (append)
- Exact Scope: `_capital_raise_years(shares_outstanding_series)` (>5% YoY jump); `_ind_as_116_transition_in_range(fiscal_year_ends)` (True if any FY end falls in FY19-20 window, i.e., year ends between Apr 2019 and Mar 2021 inclusive of transition reporting).
- Dependencies: Task 6
- Verification Command: unit-test both against synthetic Python lists (no network needed) inline in the module's `__main__` block.
- Expected Output: correct booleans/lists on synthetic inputs.

**8. Pillar 1 calculator — Income Statement**
- Target File: `backend/fundamental_service.py` (append, function `_pillar_income_statement(frames, sector_bucket)`)
- Exact Scope: every row of Section 2.1, using `_val()` + the Section 2.1 alias lists.
- Dependencies: Task 7
- Verification Command: `python -c "import fundamental_service as fs; print(fs._pillar_income_statement(fs._annual_frames('TCS.NS'), 'IT_SOFTWARE_SERVICES'))"`
- Expected Output: populated dict matching the `incomeStatement` schema branch in 1.2, no unhandled exception.

**9. Pillar 2 calculator — Balance Sheet (with lease split)**
- Target File: `backend/fundamental_service.py` (append, function `_pillar_balance_sheet(frames, sector_bucket)`)
- Exact Scope: every row of Section 2.2, **critically** implementing the `financialDebt` / `leaseLiabilities` split as two independent lookups (never derive one from the other), plus the CCC sector-suppression flag for Real Estate/EPC.
- Dependencies: Task 8
- Verification Command: run against a lessee-heavy retail/hospitality symbol; confirm `leaseLiabilities` is non-zero and `financialDebt` excludes it (`financialDebt + leaseLiabilities ≈ totalDebtReference`, within rounding).
- Expected Output: the additive check above holds within 1% tolerance.

**10. Pillar 3 calculator — Cash Flow**
- Target File: `backend/fundamental_service.py` (append, function `_pillar_cash_flow(frames)`)
- Exact Scope: every row of Section 2.3, including the deferred-tax-P&L extraction that Pillar 7's Sloan adjustment depends on, and the capital-raise-year flagging from Task 7.
- Dependencies: Task 9
- Verification Command: `python -c "import fundamental_service as fs; d=fs._pillar_cash_flow(fs._annual_frames('RELIANCE.NS')); print(d['ocfQuality']['ocfToNi'])"`
- Expected Output: a 5-element (or fewer, degraded gracefully) list of OCF/NI ratios.

**11. WACC helper + Pillar 4 calculator — Profitability**
- Target File: `backend/fundamental_service.py` (append, functions `_wacc(info, frames)`, `_pillar_profitability(frames, info, sector_bucket, is_holding_company)`)
- Exact Scope: CAPM Ke (rf=7.0%, ERP=6.0%, β from `.info["beta"]`, default β=1.0 if missing), Kd from ex-lease financial interest; full DuPont 3/5-factor; Capital Allocation Quadrant classification per the 4-way rule in 1.2. Returns `available:false` immediately if `is_holding_company`.
- Dependencies: Task 10
- Verification Command: confirm quadrant classification against a known high-reinvestment/high-ROIC compounder and a known mature low-reinvestment cash cow, expecting the two different labels.
- Expected Output: correct differential classification.

**12. Pillar 5 calculator — Solvency**
- Target File: `backend/fundamental_service.py` (append, function `_pillar_solvency(frames, info, sector_bucket)`)
- Exact Scope: every row of Section 2.5, including the Airlines EBITDAR-coverage substitution and the Real-Estate Current-Ratio suppression flag (flag only, still compute the number — suppression is a UI/scoring instruction, not a data-omission instruction).
- Dependencies: Task 11 (shares the WACC helper)
- Verification Command: confirm `netDebtEbitdaExLease` differs from `netDebtEbitdaReported` for a lessee-heavy symbol (should differ meaningfully; identical values on a company with real leases indicates the split from Task 9 isn't wired through).
- Expected Output: the two figures differ for a real lessee; the flag renders "primary flag suppressed" for a Real Estate bucket symbol.

**13. Pillar 6 calculator — Efficiency**
- Target File: `backend/fundamental_service.py` (append, function `_pillar_efficiency(frames, sector_bucket, is_holding_company)`)
- Exact Scope: every row of Section 2.6. Returns `available:false` if `is_holding_company`.
- Dependencies: Task 12
- Verification Command: confirm `available:false` fires for a confirmed holding company from Task 6's test symbol.
- Expected Output: correct suppression.

**14. Piotroski F-Score**
- Target File: `backend/fundamental_service.py` (append, function `_piotroski_f_score(frames)`)
- Exact Scope: all 9 binary tests from Section 2.7, each returned with its own pass/fail boolean and a one-line plain-English explanation, plus the aggregate score and verdict band.
- Dependencies: Task 13
- Verification Command: manually verify against a company known to be improving fundamentally (expect F≥7) and one known to be deteriorating (expect F≤3).
- Expected Output: scores land in the expected bands for both sanity-check symbols.

**15. Beneish M-Score (audit-corrected)**
- Target File: `backend/fundamental_service.py` (append, function `_beneish_m_score(frames, capital_raise_years)`)
- Exact Scope: all 8 indices from Section 2.7; the DEPI-vs-CWIP cross-check from Finding 2 before allowing red escalation; SGAI/LVGI suppression in capital-raise years + the following year from Finding 11; the `corroboratingFlagCount` field left as a placeholder int here (populated later by Task 18, which has visibility into all 16 custom flags) — do not attempt corroboration logic inside this function, since it does not yet have the full red-flag list available.
- Dependencies: Task 14
- Verification Command: run against a symbol with a known recent QIP/rights issue; confirm `sgaiLvgiSuppressedThisYear: true` for that fiscal year and the one after.
- Expected Output: suppression flag fires exactly on the two expected years, not before or after.

**16. Altman Z sector router**
- Target File: `backend/fundamental_service.py` (append, function `_altman_z(frames, info, sector_bucket)`)
- Exact Scope: implement the full priority-ordered router from Section 1.6 exactly, including the Pharma PP&E/TA>0.40 sub-split and the ₹5,000 Cr / 30-day-staleness thin-illiquid rule. Always populate `altmanModel` and `altmanModelSelectionReason`.
- Dependencies: Task 15
- Verification Command: run against one symbol from each of: a bank (expect suppressed), an IT major (expect `Z_DOUBLE_PRIME_EM_1995`), a small-cap manufacturer (expect `Z_PRIME_1983` via the thin-illiquid rule), a large-cap auto major (expect `Z_1968`).
- Expected Output: four different models selected correctly across the four test symbols.

**17. Sloan Accrual (growth-adjusted)**
- Target File: `backend/fundamental_service.py` (append, function `_sloan_accrual(frames, deferred_tax_series, revenue_3y_cagr)`)
- Exact Scope: raw and deferred-tax-adjusted versions from Section 2.7; threshold band selection by revenue 3Y CAGR from the growth-adjusted table.
- Dependencies: Task 16
- Verification Command: confirm a high-growth (>20% CAGR) company is evaluated against the 15%/30% band, not the mature 10%/25% band, on a synthetic or real high-growth symbol.
- Expected Output: correct band selected and reported in the output (`revenue3yCagrBand` field populated correctly).

**18. 16-point Red Flag Engine + Phase-2 stubs + Beneish corroboration wiring**
- Target File: `backend/fundamental_service.py` (append, function `_red_flag_engine(pillars_dict, sector_bucket, beneish, altman_result, sloan_result)`)
- Exact Scope: all 16 flags from Section 3 with sector overrides applied per Section 4.2, output shape matching the `redFlags` array in 1.2, severities per the Section 3 taxonomy. After building the 16-flag list, feed the triggered count back into `beneish["corroboratingFlagCount"]` and set `beneish["escalatedToRed"] = corroboratingFlagCount >= 2` (closing the loop left open in Task 15). Populate the four Phase-2 stub objects verbatim from Section 2.7.
- Dependencies: Task 17
- Verification Command: run against a symbol known to have multiple simultaneous issues (e.g. a stressed company with both rising receivables and weak OCF) and confirm both Flag #1 and Flag #2 trigger with correctly interpolated values in the alert strings.
- Expected Output: alert strings render with real numbers substituted, not template placeholders; `escalatedToRed` correctly reflects the ≥2 corroboration rule.

**19. Pillar 8 calculator — Valuation**
- Target File: `backend/fundamental_service.py` (append, function `_pillar_valuation(info, frames, sector_bucket)`)
- Exact Scope: every row of Section 2.8, including the Graham Number and EPV deterministic estimates (EPV reuses the Task 11 WACC helper) and the FMCG high-multiple-suppression note.
- Dependencies: Task 18
- Verification Command: `python -c "..."` confirming `grahamNumber` and `epv` are both positive floats for a profitable, non-holding-company symbol.
- Expected Output: no `NaN`/`None` on a clean profitable symbol.

**20. Pillar 9 calculator — Growth**
- Target File: `backend/fundamental_service.py` (append, function `_pillar_growth(frames, sector_bucket)`)
- Exact Scope: every row of Section 2.9, including the 3-year-rolling-average override for the Real Estate bucket (this pillar's YoY figures are replaced by rolling averages specifically for that bucket, per Finding 6).
- Dependencies: Task 19
- Verification Command: confirm a Real Estate bucket symbol's growth figures visibly differ from the same calculation done on raw YoY (i.e., the rolling-average branch actually executes, not silently falls through to the default path).
- Expected Output: rolling-average path confirmed distinct from YoY path in output.

**21. Overall Grade weighting function**
- Target File: `backend/fundamental_service.py` (append, function `_overall_grade(pillars_dict, forensics_dict, active_pillar_weights)`)
- Exact Scope: implement 1.4 exactly — sub-scores, renormalization when pillars are suppressed, letter mapping, and the band×weakest-pillar verdict-sentence selector.
- Dependencies: Task 20
- Verification Command: force a synthetic all-suppressed-Profitability-and-Efficiency case and confirm the four remaining pillar weights sum to exactly 100 after renormalization (30/75×100, 20/75×100, 15/75×100, 10/75×100 — i.e. 40, 26.67, 20, 13.33).
- Expected Output: renormalized weights sum to 100.000 within floating-point tolerance.

**22. `analyze_fundamentals()` orchestrator**
- Target File: `backend/fundamental_service.py` (append, public function `analyze_fundamentals(symbol, include_peers=True)`)
- Exact Scope: call Tasks 3-21 in sequence, each wrapped in its own try/except (per the isolation rule in 1.3.7), assemble the full schema from 1.2, and implement the `include_peers` recursion guard from 1.3.8.
- Dependencies: Task 21
- Verification Command: `python -c "import fundamental_service as fs, json; print(json.dumps(fs.analyze_fundamentals('RELIANCE.NS', include_peers=False), default=str)[:500])"`
- Expected Output: valid JSON-serializable dict, no unhandled exception, completes in under ~15 seconds for a single symbol with a warm cache.

**23. Pillar 10 — Peer Benchmarking**
- Target File: `backend/fundamental_service.py` (append, function `_pillar_peer_benchmark(symbol, own_result)`)
- Exact Scope: call `extra_service.get_peers(symbol)` (reuse — do not reimplement peer discovery), sort by `marketCap` descending, take top 4, call `analyze_fundamentals(peer_symbol, include_peers=False)` for each (sequential, relying on the Task 3 disk cache to keep repeat cross-user peer lookups cheap), assemble the 18-metric matrix and CCC-vs-ROCE quadrant from Section 2.10. Wire this into `analyze_fundamentals` only when `include_peers=True`.
- Dependencies: Task 22
- Verification Command: `python -c "import fundamental_service as fs; r=fs.analyze_fundamentals('INFY.NS'); print(len(r['peerBenchmark']['peers']))"`
- Expected Output: between 1 and 4 peers returned (0 only if `extra_service.get_peers` itself returns empty, which should propagate as `available:false` with a clear reason, not a crash).

**24. `server.py` wiring**
- Target File: `backend/server.py`
- Exact Scope: add `@api_router.get("/stock/{symbol}/fundamentals")` immediately after the existing `/stock/{symbol}/financials` route, mirroring its exact structure: cache key `f"fund:{symbol}"`, `data = await asyncio.to_thread(fsvc.analyze_fundamentals, symbol)` (local `import fundamental_service as fsvc` inside the handler, matching the lazy-import convention already used for `factor_service`/`bhavcopy_service`, not a new top-level import), `_cache_set(key, data, custom_ttl=3600)` (matching the existing `factors/ic` precedent for a long-lived expensive computation), and add `"fund"` to the disk-cache-eligible key-prefix tuple inside `_cache_get` so it survives server restarts like `ai_ratios`/`ai_verdict` already do. Gate the entire handler body behind `ENABLE_FUNDAMENTAL_DECK` (new flag, default `"true"`, same pattern as the three existing `ENABLE_*` flags).
- Dependencies: Task 23
- Verification Command: `curl -s http://localhost:8000/api/stock/RELIANCE.NS/fundamentals | python -m json.tool | head -40`
- Expected Output: valid JSON response with top-level `meta`, `gates`, `overallGrade` keys visible in the first 40 lines.

**25. `backend/test_fundamental_service.py`**
- Target File: `backend/test_fundamental_service.py`
- Exact Scope: `unittest.TestCase`-based (matching `test_institutional_flow.py`'s exact style — mock frames, `test_01_...`/`test_02_...` naming with descriptive docstrings), covering at minimum: the financialDebt/leaseLiabilities additive check (Task 9), the Holding Company gate boolean split (Task 6), the Altman router's four-model selection (Task 16), the Sloan growth-band selection (Task 17), and the Beneish corroboration escalation rule (Task 18).
- Dependencies: Task 24
- Verification Command: `python -m unittest backend/test_fundamental_service.py -v`
- Expected Output: all tests pass; any failure names the exact assertion that broke.

**26. `FundamentalDeck.jsx` — shell + data fetching**
- Target File: `frontend/src/components/FundamentalDeck.jsx`
- Exact Scope: import `{ Panel, KV }` from `./Panel`; implement the `axios.get` + `useEffect`/`useState` fetch exactly matching `RedFlagsPanel.jsx`'s pattern (including the loading spinner convention using `Loader2` from lucide-react); render nothing beyond a loading state and an empty shell at this stage — no pillar content yet.
- Dependencies: Task 24 (needs the live endpoint to fetch against)
- Verification Command: manually mount the component in a dev build pointed at a running backend; confirm the network tab shows one call to `/api/stock/{symbol}/fundamentals` per symbol change, not per re-render.
- Expected Output: single fetch per symbol change, loading state visible then clears.

**27. `FundamentalDeck.jsx` — Executive Banner, Phase 2 Gap Panel, Forensic Red Flag Panel**
- Target File: `frontend/src/components/FundamentalDeck.jsx` (extend)
- Exact Scope: build the three sections per Section 5.1/5.3, using the confirmed color convention (5.4) and explicitly labeling the red-flag section "Forensic Accounting Red Flags" (never bare "Red Flags," per the Section 1.0.D collision warning).
- Dependencies: Task 26
- Verification Command: manually verify against a symbol with `overallGrade.letter` in different bands (A+ and D, if two suitable test symbols are available) and confirm the banner styling and verdict sentence both change appropriately.
- Expected Output: visually distinct banner styling and correct verdict text per grade band.

**28. `FundamentalDeck.jsx` — Pillar Cards + DuPont + Capital Allocation Quadrant**
- Target File: `frontend/src/components/FundamentalDeck.jsx` (extend)
- Exact Scope: the 8 pillar cards from 5.1, the 3-factor and 5-factor DuPont visuals (KV-based, color-coded by YoY direction using the 5.4 palette), and the Capital Allocation Quadrant as a Recharts `ScatterChart` (already-installed dependency) with the 4 quadrant labels rendered as background zone annotations.
- Dependencies: Task 27
- Verification Command: manually confirm the Capital Allocation Quadrant correctly plots a known high-reinvestment/high-ROIC symbol in the "Compounder" zone.
- Expected Output: correct visual quadrant placement matching the backend classification from Task 11.

**29. `FundamentalDeck.jsx` — Peer Table, CCC/ROCE Quadrant, Ind AS 116 Note, Raw Data Tabs**
- Target File: `frontend/src/components/FundamentalDeck.jsx` (extend)
- Exact Scope: the sortable 18-metric `PeerMatrixTable` (rank-colored cells per 5.4), the `CccRoceQuadrant` (second Recharts `ScatterChart`), the conditional `IndAS116NotePanel` (5.3), and the collapsible 3-tab raw statement viewer (₹ Cr, 5 fiscal-year columns).
- Dependencies: Task 28
- Verification Command: manually confirm the peer table renders 1-4 peer columns without layout breakage when fewer than 4 peers are returned (the degraded case from Task 23's verification).
- Expected Output: table layout holds correctly at 1, 2, 3, and 4 peer counts.

**30. Wire into `StockDetails.jsx` + final end-to-end smoke test**
- Target File: `frontend/src/components/StockDetails.jsx`
- Exact Scope: import and render `<FundamentalDeck symbol={symbol} />` alongside the existing panel grid (position per the user's visual preference — suggest immediately after the existing `RatioAnalysisPanel`/`RedFlagsPanel` pairing, since they are topically adjacent but must remain visually distinct per Section 1.0.D).
- Dependencies: Task 29
- Verification Command: full end-to-end — start backend (`uvicorn server:app`), start frontend (`npm start`), load a stock detail page in the browser, confirm `FundamentalDeck` renders below/alongside the existing panels with no console errors, then repeat for a second, sector-different symbol (e.g. a bank, to confirm the BFSI suppression notice renders instead of a crash).
- Expected Output: clean render for both a standard-bucket symbol and a BFSI-bucket symbol; zero browser console errors; zero backend 500s in the server log.

---

### Closing note

Sections 2–6 above assume the corrected picture from Section 1.0, not the brief's original assumption. If any part of Section 1.0's audit turns out to be wrong for a branch of this codebase not inspected here (a second repo, a stale local clone, an in-progress uncommitted branch), that is the one thing worth re-verifying before Task 1 begins — everything else in this document follows deterministically from it.
