# ULTIMATE ONE-SHOT PROMPT: Institutional Fundamental & Forensic Equity Research Deck
# (PLAN & TASK LIST ONLY — NO SOURCE CODE)
# VERSION 3.0 — AUDIT-CORRECTED (Big 4 Forensic / Buy-Side / CRO Panel Review Incorporated)

> **Copy everything below this line and paste it into Claude as a single prompt.**

---

# MISSION BRIEF — MASTER ARCHITECTURAL PLAN ONLY

You are simultaneously acting as:
1. **A CFA Level 3 Charterholder & Buy-Side Principal Equity Research Analyst** at a $50B AUM fund
2. **A Forensic Accountant (CFE)** specializing in earnings manipulation detection on Indian listed companies, with deep expertise in Ind AS, Companies Act 2013, Income Tax Act 1961, and SEBI LODR regulations
3. **A Lead Financial Software Architect** designing institutional-grade research systems for NSE/BSE equities

## 🛑 CRITICAL INSTRUCTION — READ THIS FIRST
**You must NOT write any source code in your response.** No Python files (`.py`). No React components (`.jsx`). No code blocks containing implementation. Zero.

Another autonomous coding agent will do 100% of the actual coding, file creation, and test execution. That coding agent is extremely capable but needs an **exhaustive, unambiguous, step-by-step technical blueprint** to follow.

**Your sole deliverable is a Master Technical Architecture Document containing:**
1. Executive Architectural Blueprint (system design, data flow, schema)
2. Exhaustive Mathematical Formula Reference (every formula, every alias, every threshold)
3. Complete Red Flag Engine Specification (every trigger condition, every plain-English output string)
4. Sector-Specific Override Rules (what changes for banks, IT, commodities, pharma, real estate, EPC, telecom, holding companies)
5. Frontend UI/UX Design Specification (layout, color logic, component hierarchy — described in words, not code)
6. Sequential Step-by-Step Task List (exact file targets, exact actions, exact verification commands)

**Think of your output as the "Forensic_Accounting_Scorecard_Plan.md" document that a senior architect hands to a junior developer — every formula spelled out, every edge case documented, every verification step defined. The coder should never need to make a design decision; every decision must already be made in your plan.**

---

## ⚠️ PRE-ARCHITECTURE AUDIT FINDINGS (MANDATORY — Read Before Designing Anything)

This prompt has been independently reviewed by a panel of: a Big 4 Forensic Audit Partner (Ind AS / Companies Act / SEBI LODR), a Principal Buy-Side Analyst (NSE/BSE), and a Chief Risk Officer / Quant Strategist. Their findings revealed **14 critical false-positive traps** that will misclassify entire Indian sectors unless corrected. Your architecture MUST incorporate every correction below — they are non-negotiable design constraints, not optional enhancements.

### AUDIT FINDING 1: Ind AS 116 Lease Capitalization (affects Debt/EBITDA, Interest Coverage, EBITDA Margin)
**Problem:** Since FY19-20, Ind AS 116 requires operating leases to be capitalized as Right-of-Use (RoU) assets and Lease Liabilities. The `_val()` alias "Long Term Debt" can silently absorb these lease liabilities, and "Interest Expense" absorbs lease interest. Retail, hospitality, aviation, and telecom-tower tenants will be falsely flagged as over-leveraged purely from lease accounting. EBITDA becomes non-comparable pre/post FY19-20 (rent moves from opex to D&A + interest, inflating EBITDA with no operational change).

**Mandatory Fix:** Split debt into TWO separate line items in the schema:
- `financialDebt` = Short-term Borrowings + Long-term Borrowings (excludes lease liabilities — use aliases: "Short Long Term Debt", "Long Term Debt", "Other Long Term Borrowings")
- `leaseLiabilities` = Ind AS 116 lease liability line (current + non-current, aliases: "Lease Liability", "Current Lease Obligation", "Finance Lease Payable")
- Report BOTH: `netDebtEbitdaReported` (includes leases) AND `netDebtEbitdaExLease` (financial debt only)
- Report BOTH: `interestExpenseReported` AND `interestBurdenExLease = FinancialInterest / EBIT` (excluding lease interest)
- Append a comparability flag whenever fiscal years span FY19-20: *"EBITDA margin trend spans the Ind AS 116 transition — pre/post periods are not directly comparable due to the rent-to-D&A/interest reclassification."*

### AUDIT FINDING 2: Companies Act vs Income Tax Act Depreciation (affects Beneish DEPI and Sloan Accrual)
**Problem:** Companies Act 2013 (Schedule II) mandates specific useful lives (SLM/WDV). Income Tax Act 1961 (Section 32) mandates WDV block-of-assets at different rates. This creates legitimate, disclosed Deferred Tax Assets (DTA) or Deferred Tax Liabilities (DTL) that flow through the P&L as non-cash accrual items. The Beneish DEPI index and Sloan Accrual Ratio will fire false alarms on capex-heavy, fastest-growing companies in a sector — exactly the ones you DO NOT want to exclude.

**Mandatory Fix:**
- Before firing DEPI flag (>1.3), cross-check: was there significant CWIP→Gross Block transition in the same year (a commissioning year with new assets generates a natural step-change in depreciation rates)?
- Add a supplementary metric alongside raw Sloan: `deferredTaxAdjustedAccrualRatio = (NI − DeferredTaxP&LImpact − OCF − ICF) / AvgTotalAssets`. Use this to DEMOTE (not replace) the raw Sloan figure when deferred tax movements are large. Alias for deferred tax P&L: "Deferred Income Tax", "Deferred Tax", "Change In Deferred Tax".
- Only escalate DEPI to red severity if it co-occurs with: (a) stagnant or declining revenue AND (b) no large CWIP→Gross Block transition in the year.

### AUDIT FINDING 3: Tax Rate Anomaly Misfires on SEZ / Tax Holiday / MAT Companies
**Problem:** Sec 10AA (SEZ), 80-IA / 80-IE (infra/power/industrial area), 80-IE (North-East), MAT credit utilization under Section 115JB, and Sec 115BAB (new manufacturing) routinely produce ETRs of 5-17.5% for years. This is the *normal* statutory state for a large slice of the NSE universe. Single-year ETR < 10% is NOT an anomaly for these entities.

**Mandatory Fix (replaces old Red Flag #11):**
- Use 3-year AVERAGE ETR, not single-year
- Fire red alert ONLY if ETR swings abruptly (>10 percentage points YoY) OR if 3Y average ETR exceeds 40%
- For sectors with known statutory holidays (IT/SEZ, Renewable Power, Infra-80-IA, Manufacturing new regime): downgrade the persistent-low-ETR case to informational severity (not a red flag)
- Generate two distinct alert strings:
  - Persistent low (informational): *"ℹ️ Effective tax rate averaged {etr}% over 3 years — consistent with known statutory tax holiday exposure in this sector. Not flagged as anomalous."*
  - Abrupt swing (warning): *"⚠️ Effective tax rate moved abruptly from {prev_etr}% to {curr_etr}%. Investigate deferred tax reversal, tax holiday expiry, MAT credit utilization, or one-time assessment."*
- Also note: MAT credit entitlement (a balance-sheet asset under Sec 115JB) whose drawdown mechanically reduces ETR — mark as best-effort since full tax reconciliation notes are not machine-parseable from yfinance.

### AUDIT FINDING 4: Related Party Transactions (RPT) — Critical Gap, Must Be Acknowledged
**Problem:** RPTs are THE single highest-signal red flag category for Indian promoter-controlled companies (Satyam, DHFL, Zee-Essel, Yes Bank promoter loans). They are completely absent from the 15-flag engine. yfinance does NOT carry RPT data — it lives only in Annual Report notes and SEBI LODR disclosures.

**Mandatory Fix:** Do NOT silently omit RPT. Add an explicit `rpt` key to the schema with `available: false, reason: "RPT data not available via yfinance — requires SEBI LODR BSE/NSE filing scrape. Planned Phase 2 data source."` This makes the gap visible in the architecture. The deck must never imply RPT risk is covered when it isn't.

### AUDIT FINDING 5: EPC / Capital Goods / Defense / Infrastructure — DSO Flag Will False-Fire
**Problem:** Days Sales Outstanding (DSO) of 150-250 days is the baseline for major Indian EPC contractors (L&T, Kalpataru, KEC) due to government payment cycles, milestone billing, and retention money (5-10% withheld 1-3 years post-completion). Receivables routinely outpace revenue during order-book ramp-up. The 1.5× multiplier trigger will fire on the entire sector.

**Mandatory Fix (EPC/Capital Goods/Defense/Infra sector gate for Red Flag #1):**
- Raise trigger multiplier to **2.5-3.0×** for this sector class
- Also require the divergence to **persist for 2+ consecutive fiscal years** before firing (single-year spikes reflect milestone-billing lumpiness, not fraud)
- Revised alert: *"⚠️ Receivables have outpaced revenue by {ratio}× for {n} consecutive years — beyond what retention-money and government payment cycles typically explain in this sector. Worth cross-checking order-book ramp timing against milestone billing."*

### AUDIT FINDING 6: Real Estate (Ind AS 115) Breaks Current Ratio and CCC
**Problem:** Under Ind AS 115 (Revenue from Contracts with Customers), customer advances sit in Current Liabilities while WIP inventory is often classified as Non-Current. Revenue recognition is percentage-of-completion or project-completion, making YoY comparisons unreliable. A structurally sound developer will chronically show a "weak" current ratio and a meaningless CCC — both are false distress signals.

**Mandatory Fix:** For Real Estate sector:
- SUPPRESS generic Current Ratio / CCC as primary distress flags (they are not meaningful for this sector)
- REPLACE with sector-specific metrics: Customer Advances / Inventory ratio, Unsold Inventory in months of trailing sales, Net Debt / Pre-sales, CWIP stalled-project flag (this one KEEPS from the original)
- Use 3-year rolling averages for all growth metrics due to lumpy POCM revenue recognition

### AUDIT FINDING 7: Telecom and Airlines — Altman Z Auto-Fails the Entire Sector
**Problem:** Two of Altman Z's five terms (Market Cap / Total Liabilities, Retained Earnings / Total Assets) are structurally near-zero or negative for sectors with spectrum liabilities (AGR dues), aircraft RoU leases, and structural accumulated losses. Altman Z will permanently show "Distress Zone" for the entire Telecom and Airlines sector regardless of actual operating improvement — pure noise.

**Mandatory Fix:**
- Explicitly suppress (do not compute) Altman Z for Telecom, Airlines, and any entity with negative net worth
- Replace distress signal with: Net Debt / EBITDA trend (5-year) + FCF trend
- For Airlines specifically: use EBITDAR-based coverage (EBIT + Aircraft Rent / Interest + Aircraft Rent) instead of plain Interest Coverage

### AUDIT FINDING 8: Holding Companies Break Pillars 4-6 Completely
**Problem:** Investment holding companies (Bajaj Holdings, Tata Investment, Grasim-type, BSML type) have near-zero operating revenue — income is dividend + interest. All margin, turnover, ROCE, ROIC, and DuPont computations produce nonsensical or divide-by-zero output. Without a gate, the deck will either crash or output garbage ratios that look plausible.

**Mandatory Fix — Holding Company Detection Gate:**
- Trigger: `(Other Income / Total Income > 70%)` AND `(Investments / Total Assets > 50%)`
- If triggered: Suppress ALL of Pillars 4, 5, 6 (Profitability, Solvency, Efficiency), and mark Piotroski, Beneish, Sloan as "Not Applicable — Investment Holding Structure"
- Replace with: Discount-to-NAV % (non-computable from yfinance — stub as `available: false, reason: "NAV computation requires investee mark-to-market — Phase 2"`), Dividend Income Stability (5Y coefficient of variation of dividend income)
- All suppressed sections must return `available: false, reason: "Investment Holding Structure — standard operating ratios are not meaningful for this entity type"`

### AUDIT FINDING 9: Altman Z Coefficients Are the 1968 US Manufacturing Model — Wrong for Indian Service/Tech/Consumer Stocks
**Problem:** The original Z-score (weights: 1.2, 1.4, 3.3, 0.6, 1.0) penalizes asset-light, high-margin businesses via the X5 term (Revenue / Total Assets) because it rewards asset-heaviness. Applying it uniformly to IT, Consumer, Pharma, and Services names systematically mislabels efficient businesses as risky.

**Mandatory Fix — Altman Z Sector Router (MUST be implemented as a selector, not a single formula):**

| Sector Class | Model | Formula to Use | Zone Thresholds |
|---|---|---|---|
| Auto, Capital Goods, Metals, Manufacturing (public) | Z original (1968) | `1.2(WC/TA) + 1.4(RE/TA) + 3.3(EBIT/TA) + 0.6(MCap/TL) + 1.0(Rev/TA)` | Safe >2.99, Grey 1.81-2.99, Distress <1.81 |
| Thin/illiquid small-caps (any sector, when MCap data is stale) | Z' revised (1983) | `0.717(WC/TA) + 0.847(RE/TA) + 3.107(EBIT/TA) + 0.420(BookEq/TL) + 0.998(Rev/TA)` | Safe >2.9, Grey 1.23-2.9, Distress <1.23 |
| IT, Consumer/FMCG, Pharma (branded/formulations), Services | Z'' EM non-manufacturing (1995) | `6.56(WC/TA) + 3.26(RE/TA) + 6.72(EBIT/TA) + 1.05(BookEq/TL)` — **X5 asset-turnover term is DROPPED** | Safe >2.6, Grey 1.1-2.6, Distress <1.1 |
| Banks, NBFC, Telecom, Airlines, negative net worth entities | Suppressed | Do not compute | Display: "Not meaningful for this sector — see Net Debt/EBITDA trend instead" |

### AUDIT FINDING 10: Lease Interest vs Financial Interest Conflation
**Problem:** Same root cause as Finding 1. Interest Burden ratio (>40% flag) includes Ind AS 116 lease interest, making retail/hospitality/telecom-tower tenants appear debt-burdened even when financial leverage is low.

**Mandatory Fix:** Report both `interestBurdenTotal` (all interest including lease) and `interestBurdenExLease` (financial interest only). Apply the >40% flag ONLY to `interestBurdenExLease`.

### AUDIT FINDING 11: Beneish SGAI and LVGI Produce Noise Around Indian Capital Raise Events
**Problem:** QIPs, preferential allotments, and rights issues are extremely common financing events for fast-growing Indian companies. A capital raise mechanically resets leverage (LVGI) and can distort SG&A-to-sales (SGAI) in the raise year — with zero manipulation involved. The US Beneish calibration sample did not include frequent equity-raise events common in emerging markets.

**Mandatory Fix:**
- Detect capital-raise events: if shares outstanding increased >5% YoY → flag the year as a "capital raise year"
- In the capital raise year AND the subsequent year, suppress interpretation of LVGI and SGAI (mark as "suppressed — capital raise event distorts leverage and SG&A indices")
- Only escalate Beneish to "red" severity if it is corroborated by **≥2 of the 15 custom red flags simultaneously** — multi-signal confirmation is mandatory for Beneish standalone signals

### AUDIT FINDING 12: CDMO/Pharma/API Inventory Flag Ignores Strategic Stockpiling
**Problem:** China+1 de-risking and US FDA batch-validation buffers routinely produce 2-3× inventory builds in Pharma/API/CDMO expansion years with zero demand problem. The 2× revenue growth multiplier in Red Flag #3 fires on legitimate strategic behavior.

**Mandatory Fix (Pharma/API/CDMO/Chemical sector gate for Red Flag #3):**
- Raise trigger to **3.0-3.5× revenue growth**
- ALSO require **co-occurring gross margin compression** before escalating to warning severity (genuine obsolescence or demand weakness manifests in declining margins; strategic stockpiling does not)
- Revised alert: *"⚠️ Inventory has surged {inv_growth}% vs. revenue growth of {rev_growth}% in a sector where strategic stockpiling is common. Check if gross margin is also compressing — if not, this may reflect India+1 supply-chain buffering, not a demand problem."*

### AUDIT FINDING 13: Contingent Liabilities Flag Not Computable — Must Be Stubbed
**Problem:** Contingent liabilities (>20% of Net Worth flag) are an Annual Report notes disclosure. They are NOT present in any yfinance statement. As written, this flag will either never fire (giving false comfort) or crash on a missing field.

**Mandatory Fix:** Mark explicitly as `available: false, reason: "Contingent liabilities are Annual Report notes disclosures — not in yfinance statement DataFrames. Phase 2 data source."` Do not leave it as an implied working flag.

### AUDIT FINDING 14: Sloan Accrual Thresholds Are Too Tight for Indian High-Growth Companies
**Problem:** Indian high-growth companies scale working capital faster than the US calibration sample assumed (Indian GDP-linked growth rates run 2-3× US averages). A static ±10%/±25% band over-flags exactly the fastest-growing, most-interesting names in the coverage universe.

**Mandatory Fix — Growth-Adjusted Sloan Thresholds:**

| Revenue 3Y CAGR | Moderate Warning Threshold | Severe Red Flag Threshold |
|---|---|---|
| < 10% (steady-state / mature) | |Sloan| > 10% | |Sloan| > 25% |
| 10-20% (moderate growth) | |Sloan| > 12% | |Sloan| > 27% |
| > 20% (high growth) | |Sloan| > 15% | |Sloan| > 30% |

---

## EXISTING PLATFORM CONTEXT (Read Every Detail Carefully)

### Tech Stack
- **Backend:** Python 3.11+ / FastAPI (`backend/server.py` is the main controller)
- **Frontend:** React 19 + Tailwind CSS + Radix UI (`frontend/src/components/`)
- **Data Source:** `yfinance` Python library (already installed and working). For any NSE-listed stock (e.g., `RELIANCE.NS`, `TCS.NS`, `SWIGGY.NS`), calling `yf.Ticker(symbol)` gives us:
  - `.balance_sheet` → Annual Balance Sheet DataFrame (77+ rows × 5 fiscal years, newest column first)
  - `.financials` → Annual Income Statement / P&L DataFrame (50+ rows × 5 fiscal years, newest column first)
  - `.cashflow` → Annual Cash Flow Statement DataFrame (47+ rows × 5 fiscal years, newest column first)
  - `.info` → Dictionary with `marketCap`, `beta`, `sector`, `industry`, `trailingPE`, `forwardPE`, `priceToBook`, `enterpriseValue`, `bookValue`, `dividendYield`, `trailingEps`, `forwardEps`, `debtToEquity`, `returnOnEquity`, `returnOnAssets`, `revenueGrowth`, `earningsGrowth`, `grossMargins`, `operatingMargins`, `profitMargins`, `heldPercentInsiders`, `heldPercentInstitutions`, `fullTimeEmployees`, etc.
  - `.fast_info` → Lightweight dict with `lastPrice`, `marketCap`, `shares`

### Existing Local Data Cache (MUST Reuse)
We already have a fully working caching engine in `backend/forensic_service.py` that:
- `_annual_frames(symbol)` → Fetches `.balance_sheet`, `.financials`, and `.cashflow` once, then stores them as structured JSON in `backend/forensic_cache.json`, keyed by symbol with `updatedAt` ISO timestamp. Cache is fresh for `FORENSIC_TTL_DAYS` (default 7 days). On cache hit, returns instantly from disk with 0 network calls.
- `_val(df, aliases, year_idx)` → Case-insensitive alias lookup helper. Takes a DataFrame, a list of possible field name strings, and a year index (0=newest, 1=prior year). Returns `float` or `None`.
- Cache stores the FULL raw financial statements (all 174+ rows across all 3 statements, all 5 fiscal years), not just extracted values.
- **Your plan MUST instruct the coder to reuse `_annual_frames()` and `_val()`. Do NOT design a separate data fetcher.**

### Existing Forensic Engine (Already Built — Call, Don't Duplicate)
`backend/forensic_service.py` already computes:
- **Piotroski F-Score (9 binary tests)**
- **Beneish M-Score (8-variable model)** with -1.78 / -2.22 thresholds
- **ROIC vs WACC** (CAPM-based, rf=7%, ERP=6%, beta from yfinance)
- **`analyze_forensics(symbol, beta, market_cap)`** → Public API

**Your plan must instruct the coder to CALL these existing functions via import — not reimplement them.** The new `fundamental_service.py` imports and invokes `forensic_service.piotroski_f_score()`, `beneish_m_score()`, and `roic_vs_wacc()`.

### Existing Sector & Universe Infrastructure
- `backend/sector_map.py` → `get_sector(symbol)` returns sector string
- `backend/bhavcopy_service.py` → Full NSE universe (~1800 symbols)
- `backend/factor_service.py` → Factor profiles for the NSE universe

### Existing UI Integration Pattern (Follow Exactly)
```
{technicals.quantDeck.forensics?.piotroski?.available && (
  <KV label="..." value="..." valueClass="..." />
)}
```
Color convention: `text-emerald-400` = good, `text-amber-400` = caution, `text-red-400` = danger, `font-bold animate-pulse` = critical.

### Env-Flag Gating Pattern (Follow Exactly)
```
result = {"available": False, "reason": "disabled"}
if os.environ.get("ENABLE_FEATURE", "true").lower() != "false":
    try:
        import service_module as svc
        result = svc.main_function(sym)
    except Exception as e:
        result = {"available": False, "reason": str(e)}
```

---

## THE 10 PILLARS OF EXHAUSTIVE FUNDAMENTAL ANALYSIS

You must design the architecture for ALL of the following. Leave nothing out.

---

### PILLAR 1: INCOME STATEMENT DEEP DIVE (`incomeStatement`)

**Revenue Analysis:**
- Total Revenue (absolute, in ₹ Crores — divide raw yfinance values by 10^7) for latest 5 fiscal years
- Revenue YoY Growth Rate for each year
- Revenue 3-Year CAGR and 5-Year CAGR
- Revenue quality flag: Cross-check against Asset Turnover trends — if revenue grows but asset turnover declines, growth may be acquisition-driven or price-led, not organic volume growth

**Cost Structure & Operating Leverage:**
- COGS as % of Revenue (5-year trend)
- Gross Profit and Gross Margin % (5-year trend with expansion/contraction flag)
- Employee Cost / SG&A as % of Revenue (trend)
- Operating Profit (EBIT) and Operating Margin % (5-year trend)
- EBITDA and EBITDA Margin % (5-year trend) — **with Ind AS 116 comparability flag if transition year is in range**
- Operating Leverage: Revenue growth % vs EBIT growth % (>10% rev = >10% EBIT → positive operating leverage)

**Profitability Cascade (Full P&L Waterfall):**
- 5-year trend: Gross Margin → Operating Margin → Pre-Tax Margin → Net Profit Margin
- Margin expansion/contraction flag at each level (where is compression happening?)
- Interest Expense as % of EBIT (two versions: total including lease interest, and ex-lease per Audit Finding 1)
- **Effective Tax Rate — revised per Audit Finding 3:** 3-year average ETR, with sector-gated anomaly detection (persistent low ≠ anomaly for SEZ/80-IA/Renewable sectors; abrupt swing = warning for all sectors)
- Other Income as % of PBT — flag if >15%

**EPS Analysis:**
- Basic EPS (5-year trend)
- EPS 3Y CAGR and 5Y CAGR
- EPS growth vs Revenue growth divergence check: EPS CAGR > 2× Revenue CAGR → flag

---

### PILLAR 2: BALANCE SHEET DEEP DIVE (`balanceSheet`)

**Asset Composition & Quality:**
- Total Assets (absolute, 5-year trend in ₹ Cr)
- Current vs Non-Current split (% of total, trend)
- Cash & Cash Equivalents (absolute and % of Total Assets)
- Receivables / Debtors (absolute, % of Revenue, DSO trend)
- Inventory (absolute, % of Revenue, DIO trend)
- Net Fixed Assets / PPE (absolute, % of Total Assets, Fixed Asset Turnover)
- Intangibles & Goodwill (absolute, % of Total Assets — flag if >25%)
- CWIP (absolute, % of Total Assets — stalled-project flag)

**Liability Structure — WITH AUDIT FINDING 1 LEASE SPLIT:**
- `financialDebt` = Short-term Borrowings + Long-term Borrowings (excludes lease liabilities)
- `leaseLiabilities` = Ind AS 116 RoU lease liabilities (current + non-current, separate line)
- Total Debt = financialDebt + leaseLiabilities (for reference, clearly labeled)
- Debt-to-Equity Ratio (use financialDebt/Equity as primary; Total/Equity as secondary)
- `netDebtEbitdaReported` = (Total Debt - Cash) / EBITDA
- `netDebtEbitdaExLease` = (financialDebt - Cash) / EBITDA ← PRIMARY DISTRESS SIGNAL
- Trade Payables (DPO)
- Contingent Liabilities: `available: false, reason: "AR notes disclosure — not in yfinance. Phase 2."` — explicit stub, not omitted

**Working Capital Analysis:**
- Net Working Capital = Current Assets - Current Liabilities (5-year trend)
- Working Capital as % of Revenue
- **CCC = DSO + DIO - DPO** — with sector gate (suppress as primary flag for Real Estate, apply cautiously for EPC)
- Ind AS 116 comparability flag if applicable

**Book Value:**
- BVPS (5-year trend)
- TBVPS = (Total Equity - Intangibles - Goodwill) / Shares Outstanding
- Retained Earnings growth rate

---

### PILLAR 3: CASH FLOW STATEMENT DEEP DIVE (`cashFlow`)

**OCF Quality — The Truth Serum:**
- OCF absolute (5-year trend)
- OCF / Net Income (Golden Ratio): >1.0 = ✅ High Quality; 0.5-1.0 = 🟡 Moderate; <0.5 = 🔴 Paper Profits; <0 while NI>0 = 🔴🔴 Severe Red Flag
- OCF / EBITDA (Cash Conversion Efficiency): >70% = ✅; <50% = ⚠️
- FCF = OCF - CapEx (5-year trend)
- FCF Margin = FCF / Revenue
- Cumulative 5Y OCF vs Cumulative 5Y Net Income test

**CapEx Analysis:**
- CapEx absolute (5-year)
- CapEx / Revenue (capital intensity)
- CapEx / Depreciation: >1.5 = growing, 0.8-1.5 = steady, <0.5 = milking assets
- Growth CapEx proxy = CapEx - Depreciation
- **Deferred Tax P&L Impact extraction** (for Audit Finding 2 — adjusted accrual ratio)

**Financing Activities:**
- Net borrowing trend
- Net equity dilution / buyback trend
- Dividend Payout Ratio and FCF coverage
- Total Shareholder Yield
- **Capital-raise event detection:** shares outstanding >5% YoY increase → mark as capital-raise year (feeds into Audit Finding 11 SGAI/LVGI suppression)

**Cash Self-Sufficiency Test:** Boolean — can OCF fund CapEx + Dividends + Debt Repayment without new borrowing?

---

### PILLAR 4: PROFITABILITY & RETURN RATIOS (`profitability`)
*(SUPPRESS ENTIRELY for Holding Companies per Audit Finding 8)*

**Core Return Metrics (5-year trends):**
- ROE = Net Income / Average Shareholders' Equity
- ROA = Net Income / Average Total Assets
- ROCE = EBIT / (Total Assets - Current Liabilities)
- ROIC = NOPAT / Invested Capital (already in forensic_service — reuse)

**3-Factor DuPont Decomposition:**
- ROE = Net Profit Margin × Asset Turnover × Equity Multiplier
- Plain-English verdict for each driver

**5-Factor Extended DuPont:**
- ROE = Tax Burden × Interest Burden × EBIT Margin × Asset Turnover × Equity Multiplier
- Interest Burden MUST use ex-lease figure per Audit Finding 1

**Incremental Returns:**
- Incremental ROE = ΔNet Income / ΔEquity
- Incremental ROIC = ΔNOPAT / ΔInvested Capital

**NEW — Capital Allocation Quadrant (Audit Finding: Missing Institutional Metric #2):**
- X-axis: Reinvestment Rate = (Net CapEx + ΔWorking Capital) / NOPAT
- Y-axis: Incremental ROIC = ΔNOPAT / ΔInvested Capital
- Classify into exactly 4 quadrants:
  - High Reinvestment + High Incremental ROIC → **"✅ Compounder — capital is being deployed at attractive incremental returns"**
  - Low Reinvestment + High ROIC → **"✅ Cash Cow — mature, high-return business with low reinvestment need"**
  - High Reinvestment + Low/Negative Incremental ROIC → **"🔴 Value Destroyer — the worst quadrant: management is reinvesting aggressively but generating poor incremental returns"**
  - Low Reinvestment + Declining ROIC → **"⚠️ Harvest — returns eroding without compensating reinvestment"**

---

### PILLAR 5: LIQUIDITY & SOLVENCY (`solvency`)
*(SUPPRESS generic Current Ratio / CCC for Real Estate per Audit Finding 6)*
*(Apply ex-lease versions of all interest-related ratios per Audit Finding 1 & 10)*

**Short-Term Liquidity:**
- Current Ratio, Quick Ratio, Cash Ratio (5-year trends)
- 6-Month Survival Test = Cash / Monthly Operating Expenses
- **Gate:** Do NOT use Current Ratio as primary distress flag for Real Estate sector

**Long-Term Solvency:**
- `netDebtEbitdaExLease` ← PRIMARY COVENANT RATIO (per Audit Finding 1)
- `netDebtEbitdaReported` ← secondary (include Ind AS 116 leases for completeness)
- Interest Coverage = EBIT / `interestBurdenExLease` (financial interest only)
- DSCR = OCF / (FinancialInterest + Principal Repayments)
- Fixed Charge Coverage = (EBIT + Lease Payments) / (FinancialInterest + Lease Payments)
- Thresholds: Net Debt/EBITDA (Ex-Lease) >3.5 = 🔴; Interest Coverage (Ex-Lease) <2.0 = 🔴; DSCR <1.0 = 🔴

**Capital Structure:**
- Equity % vs financialDebt % (excluding leases)
- WACC = We×Ke + Wd×Kd(1-t), Ke = 7% + beta×6%, Kd = FinancialInterest / financialDebt

---

### PILLAR 6: EFFICIENCY & ACTIVITY RATIOS (`efficiency`)
*(SUPPRESS for Holding Companies per Audit Finding 8)*
*(Interpret Asset Turnover within-sector for IT, not vs. manufacturing per sector override)*

- Total Asset Turnover, Fixed Asset Turnover, Working Capital Turnover
- Inventory Turnover, Receivables Turnover, Payables Turnover (all 5-year trends)
- **CCC = DSO + DIO - DPO** (5-year trend)
  - Flag if CCC expands >20% YoY
  - Negative CCC = ✅✅ (FMCG/retail — collect before paying suppliers)
  - **EPC/Real Estate: suppress as primary distress flag per Audit Findings 5 & 6**

---

### PILLAR 7: FORENSIC ACCOUNTING & RED FLAG ENGINE (`forensics`)

**Academic Scorecards (all with audit corrections applied):**

**Piotroski F-Score — REUSE from forensic_service:**
- All 9 tests with individual pass/fail + plain-English explanation each
- Verdict: ≥7 Strong, 4-6 Moderate, ≤3 Weak/Distressed

**Beneish M-Score — REUSE from forensic_service WITH AUDIT CORRECTIONS:**
- All 8 indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA)
- **Audit Finding 2:** DEPI cross-checked against CWIP→Gross Block transition before red escalation
- **Audit Finding 11:** SGAI and LVGI suppressed in capital-raise year and following year (>5% share count jump)
- **Audit Finding 11:** Beneish alone only escalates to red if ≥2 custom red flags are simultaneously triggered
- Threshold: > -1.78 = High Risk, -2.22 to -1.78 = Moderate, < -2.22 = Low/Clean

**Altman Z-Score — NEW, with Audit Finding 9 Sector Router:**
- Use the sector-router table from Audit Finding 9 — implement as a mandatory IF/ELIF selector
- Z original (manufacturing), Z' (book equity / illiquid), Z'' EM (IT, FMCG, Pharma, Services)
- Suppressed for Banks, NBFC, Telecom, Airlines, negative net worth
- Model selected shown in output: `"altmanModel": "Z_EM_1995"` etc.

**Sloan Accrual Ratio — NEW, with Audit Finding 14 Growth-Adjusted Thresholds:**
- `rawSloan = (Net Income - OCF - Investing CF) / Average Total Assets`
- `deferredTaxAdjustedSloan = (Net Income - DeferredTaxPnLImpact - OCF - ICF) / AvgTotalAssets`
- Apply growth-adjusted threshold table from Audit Finding 14
- Report both values; flag on `deferredTaxAdjustedSloan` as primary, `rawSloan` as secondary

**Phase 2 Data Stubs (NOT computable via yfinance — explicitly stubbed, not omitted):**
- `rpt` → `available: false, reason: "RPT requires SEBI LODR filing scrape — Phase 2"`
- `promoterPledge` → `available: false, reason: "Pledge % requires BSE/NSE shareholding XBRL — Phase 2"`
- `auditorChange` → `available: false, reason: "Auditor data requires AR text-mining / BSE corporate announcements — Phase 2"`
- `contingentLiabilities` → `available: false, reason: "AR notes disclosure — not in yfinance — Phase 2"`

**16-Point Custom Red Flag Engine (1-15 existing + 1 new, ALL with audit corrections applied):**

1. **Revenue vs Receivables Divergence:**
   - **Standard sectors:** Trigger: Receivables growth > 1.5× Revenue growth (YoY)
   - **EPC/Capital Goods/Defense/Infra (Audit Finding 5):** Trigger: >2.5× AND persists 2+ years
   - Alert: *"⚠️ RED FLAG: Sales grew {rev_growth}% but uncollected bills surged {rec_growth}%. Possible channel stuffing, round-tripping, or aggressive revenue recognition."*

2. **Profit vs Cash Flow Divergence:**
   - Trigger: Net Income > 0 AND OCF < 0
   - Alert: *"🔴 SEVERE: Company reports ₹{ni} Cr profit but BURNED ₹{abs(ocf)} Cr cash. Reported profit is fictional — driven by accruals, not real cash."*

3. **Rising Inventory Without Revenue Growth:**
   - **Standard sectors:** Trigger: Inventory growth > 2× Revenue growth
   - **Pharma/API/CDMO/Chemicals (Audit Finding 12):** Trigger: >3.0× AND co-occurring gross margin compression
   - Alert: *"⚠️ Inventory piling up {inv_growth}% while sales grew only {rev_growth}%. Possible obsolescence risk or demand slowdown."*

4. **Other Income Dependence:**
   - Trigger: Other Income > 20% of Pretax Income
   - Alert: *"⚠️ Core business profitability is weak. {pct}% of pre-tax profit comes from non-operational sources."*

5. **Debt Spiral Detection:**
   - Trigger: financialDebt grew >15% YoY for 3 consecutive years AND OCF flat/declining
   - Alert: *"🔴 Debt Spiral: Financial borrowings compounded at {debt_cagr}% annually for 3 years while OCF stagnated."*

6. **Equity Dilution:**
   - Trigger: Share count increased >2% YoY
   - Alert: *"⚠️ Shareholder dilution: {dilution}% new shares issued. Note: If this coincides with a QIP/rights issue, Beneish SGAI/LVGI indices are suppressed for this year."*

7. **Goodwill / Intangible Asset Bloat:**
   - Trigger: (Intangibles + Goodwill) > 30% of Total Assets
   - Alert: *"⚠️ {pct}% of the balance sheet is intangible. High impairment risk."*

8. **CapEx Collapse (Asset Milking):**
   - Trigger: CapEx / Depreciation < 0.5 for 2+ consecutive years
   - Alert: *"⚠️ CapEx is only {ratio}x depreciation for {n} years. Assets are being milked without reinvestment."*

9. **Unsustainable Dividend (Dividend > FCF):**
   - Trigger: Dividends Paid > Free Cash Flow (absolute)
   - Alert: *"🔴 Unsustainable dividend: ₹{div} Cr paid but only ₹{fcf} Cr FCF generated. Funded from debt or reserves."*

10. **Interest Coverage Crunch:**
    - Trigger: EBIT / `interestBurdenExLease` < 1.5 (use financial interest only per Audit Finding 10)
    - Alert: *"🔴 Financial interest barely covered ({ratio}x ex-lease). One bad quarter from technical default risk."*

11. **Tax Rate Anomaly (REVISED per Audit Finding 3):**
    - Trigger A (all sectors): 3Y average ETR > 40% → 🔴 warning
    - Trigger B (non-holiday sectors): single-year ETR < 10% OR 3Y avg < 10% → 🟡 warning
    - Trigger C (all sectors): year-on-year ETR swing > 10 percentage points → ⚠️ investigate
    - For IT/SEZ/Renewable/Infra-80-IA: persistent low ETR → ℹ️ informational only
    - Three distinct alert strings as specified in Audit Finding 3

12. **Leverage-Price Divergence (Margin Call Proxy):**
    - Trigger: financialDebt/Equity increased >20% YoY while stock price declined >20%
    - Alert: *"⚠️ Leverage increasing during price decline — potential promoter margin-call or forced-selling risk."*

13. **CCC Deterioration:**
    - Trigger: CCC expanded >20% YoY — **suppress for Real Estate and EPC sectors**
    - Alert: *"⚠️ CCC expanded from {ccc_prev} to {ccc_curr} days ({pct}% deterioration)."*

14. **Aggressive Depreciation Policy (DEPI — Audit Finding 2 cross-check applied):**
    - Trigger: DEPI > 1.3 AND no significant CWIP→Gross Block transition in the same year
    - Alert: *"⚠️ Depreciation rates slowing (DEPI: {depi}) without a proportional asset commissioning event. May be artificially inflating current-year profits."*

15. **Persistent Capital Destruction:**
    - Trigger: ROIC < WACC for 3+ consecutive years
    - Alert: *"🔴 Persistent capital destruction for {n} years. ROIC ({roic}%) < WACC ({wacc}%) — systematically destroying shareholder wealth."*

16. **NEW — Promoter Shareholding Decline (Audit Finding: Missing Institutional Metric #1):**
    - Computable via `.info["heldPercentInsiders"]`: Trigger: promoter/insider holding declined >3 percentage points YoY
    - Alert: *"⚠️ Promoter/insider shareholding fell {pp}pp YoY ({prev}% → {curr}%). Cross-check against pledge disclosures and open-market sale filings."*
    - Promoter pledge %: `available: false, reason: "Pledge % requires BSE/NSE shareholding XBRL — Phase 2 data source"`

---

### PILLAR 8: VALUATION ANALYSIS (`valuation`)

**Absolute Valuation Metrics:**
- Trailing P/E, Forward P/E, P/B, Price-to-Tangible-Book, P/S, EV/EBITDA, EV/EBIT, EV/Revenue
- PEG Ratio = P/E / (3Y EPS CAGR): < 1 = potentially undervalued
- FCF Yield = FCF / Market Cap (the "real" earnings yield)
- Earnings Yield = 1 / P/E vs. rf rate (7% G-Sec benchmark)
- Dividend Yield (trailing)

**Intrinsic Value Estimates (Deterministic):**
- **Graham Number** = sqrt(22.5 × EPS × BVPS)
- **Earnings Power Value (EPV)** = Normalized EBIT × (1 - tax rate) / WACC
- **Margin of Safety** = (EPV - Price) / EPV: >30% = ✅; 0-30% = 🟡; <0 = 🔴

**Historical Valuation Context:**
- Current P/E vs own 5Y median P/E
- Current P/B vs own 5Y median P/B
- Current EV/EBITDA vs own 5Y median

**Note:** Do NOT flag high multiples as automatic red flags for FMCG/Consumer Staples — high P/E is structurally normal. Generate comparison-within-sector context.

---

### PILLAR 9: GROWTH ANALYSIS (`growth`)

**Historical Growth Rates:**
- Revenue (1Y, 3Y CAGR, 5Y CAGR)
- EBITDA (1Y, 3Y CAGR, 5Y CAGR)
- Net Income (1Y, 3Y CAGR, 5Y CAGR)
- EPS (1Y, 3Y CAGR, 5Y CAGR)
- Book Value Per Share (3Y CAGR, 5Y CAGR)
- OCF (1Y, 3Y CAGR, 5Y CAGR)
- FCF (1Y, 3Y CAGR)

**Growth Quality:**
- Profit CAGR vs Revenue CAGR divergence
- Revenue CAGR vs Asset CAGR divergence
- Sustainable Growth Rate (SGR) = ROE × (1 - Payout Ratio)
- Reinvestment Rate = (Net CapEx + ΔWorking Capital) / NOPAT
- Growth Consistency Score: out of 5 years, how many had positive revenue / profit growth?

---

### PILLAR 10: SECTOR & PEER BENCHMARKING (`peerBenchmark`)

**Peer Selection:**
- Use `sector_map.py` → `get_sector(symbol)` to identify sector/industry
- Select top 4-5 peers by market cap in same industry (expand to sector if <3 peers available)
- Fetch peer financials via same `_annual_frames()` cache

**Comparative Matrix — 18 Metrics (expanded from 16 to include audit additions):**
1. Revenue Growth (1Y) | 2. Revenue Growth (3Y CAGR) | 3. Gross Margin % | 4. Operating Margin % | 5. Net Profit Margin % | 6. ROE % | 7. ROIC % | 8. Debt-to-Equity (financial debt, ex-lease) | 9. Net Debt / EBITDA (Ex-Lease) | 10. Interest Coverage (Ex-Lease) | 11. Current Ratio | 12. P/E (Trailing) | 13. EV/EBITDA | 14. P/B | 15. FCF Yield % | 16. Piotroski F-Score | 17. Altman Z-Score (model applied noted) | 18. FII/DII Holding % (per audit addition)

**NEW — CCC vs ROCE Quadrant (Audit Finding: Missing Institutional Metric #4):**
- Plot each peer on a 2D quadrant: X-axis = CCC (days), Y-axis = ROCE (%)
- Quadrant interpretation:
  - Low CCC + High ROCE → "Quality Compounder" (top-left — ideal)
  - Low CCC + Low ROCE → "Efficient but Marginal"
  - High CCC + High ROCE → "Capital-Intensive Winner"
  - High CCC + Low ROCE → "Value Trap / Avoid"
- This is additive to (not a replacement of) the standard comparison table

**Relative Strengths/Weaknesses (Plain English Bullets):** Automated comparison vs sector median for each metric with ranking (e.g., "Rank 2 of 5").

---

## THE 5 MISSING INDIAN INSTITUTIONAL METRICS (Add to Architecture)

The independent audit panel identified these 5 critical metrics — used by elite Indian fund managers (Saurabh Mukherjea's Marcellus, Kenneth Andrade's Old Bridge, Motilal Oswal QGLP) — that were absent from the original design. All 5 must be added:

### Missing Metric #1: Promoter Shareholding Trend (+ Pledge Stub) [Added as Red Flag #16 above]
- Computable now: `heldPercentInsiders` from `.info`, trend over available data points
- Trigger: >3pp YoY decline → warning alert
- Phase 2 stub: Pledge % of promoter holding (`available: false`)

### Missing Metric #2: Capital Allocation Quadrant [Added to Pillar 4 above]
- Reinvestment Rate × Incremental ROIC matrix
- Compounder / Cash Cow / Value Destroyer / Harvest classification

### Missing Metric #3: Auditor Integrity Stub (Phase 2 — explicit acknowledgment)
- Not computable via yfinance (audit firm, audit fee, non-audit fee ratio require AR note parsing)
- Schema stub: `auditorChange: {available: false, reason: "Requires BSE corporate announcements + AR text-mining — Phase 2. Auditor resignation or Big-4 to smaller-firm switch is a historically high-signal India red flag (Satyam, DHFL, IL&FS)."}`

### Missing Metric #4: CCC vs ROCE Quadrant Peer Plot [Added to Pillar 10 above]
- Distinguishes quality compounders (low CCC + high ROCE) from balance-sheet-timing "good ROCE" companies

### Missing Metric #5: Institutional Shareholding Trend (FII/DII) [Added to Pillar 10 matrix]
- Computable: `heldPercentInstitutions` from `.info` (point-in-time; trend needs quarterly scrape for Phase 2)
- Use available data as a cross-sectional rank within peer group for current snapshot
- Phase 2: quarterly shareholding pattern trend from BSE/NSE

---

## COMPREHENSIVE SECTOR-SPECIFIC OVERRIDE TABLE

| Sector | Metrics to SUPPRESS / REMOVE | Metrics to ADD / REPLACE | Threshold Overrides | Special Notes |
|---|---|---|---|---|
| **EPC / Capital Goods / Defense / Infra** | Generic DSO red flag (1.5×) | Book-to-Bill ratio (Order Book/Revenue), Working Capital as % of Order Book | DSO flag multiplier → 2.5-3.0×, require 2-year persistence | Government receivables and retention money (5-10% of contract withheld 1-3yr) are structural, not fraud |
| **Real Estate / Construction** | Current Ratio as primary flag, CCC as primary flag | Customer Advances / Inventory, Unsold Inventory (months), Net Debt / Pre-sales, CWIP stalled-project flag (keep) | Use 3Y rolling averages for all growth metrics | Ind AS 115 POCM revenue recognition makes YoY comparisons unreliable |
| **Pharma / API / CDMO / Chemicals** | — | R&D / Revenue, Export Revenue %, Gross Margin stability band | Inventory red flag multiplier → 3.0-3.5×, requires co-occurring margin compression | DIO of 120+ days is sector baseline; China+1 strategic buffering is legitimate |
| **Telecom / Airlines** | Altman Z (any model), generic D/E distress flag | Net Debt/EBITDA trend (5Y), FCF trend, EBITDAR coverage for Airlines | — | AGR dues, spectrum liabilities, aircraft RoU leases are structural, not distress signals |
| **Banks / NBFC** | ALL standard ratios (inventory, gross margin, asset turnover, standard D/E, Beneish, Altman) | NIM, GNPA/NNPA, PCR, CASA, Cost-to-Income, Credit Cost, CRAR/CAR | — | **Recommend implementing as a separate BFSI module (Phase 2) — the standard 10-pillar architecture does not map meaningfully to the BFSI balance sheet schema** |
| **Holding Companies** | Pillars 4, 5, 6 entirely; Piotroski, Beneish, Sloan | Discount-to-NAV % (Phase 2 stub), Dividend Income Stability (5Y CV) | Gate: OtherIncome/TotalIncome > 70% AND Investments/TotalAssets > 50% | All suppressed sections: `available: false, reason: "Investment Holding Structure"` |
| **IT / Software / Services** | Inventory ratios, Fixed Asset Turnover (de-emphasize not remove) | Revenue / Employee (if `.info["fullTimeEmployees"]` populated), USD/INR sensitivity note | Compare Asset Turnover only within-sector, not vs. manufacturing | Z'' EM model for Altman (drops asset turnover term) |
| **FMCG / Consumer Staples** | High P/E as automatic red flag, high P/B as automatic red flag | Negative CCC treated as ✅ positive signal (reinforce) | FMCG 5Y median P/E premium is normal — flag only unusual deviation (>50% premium to own history) | Brand premium and customer captivity justify structurally higher multiples |
| **Commodities / Metals / O&G / Mining** | P/E as primary valuation (cyclical earnings distort it) | EV/EBITDA as primary valuation metric, EBITDA margin volatility (stddev) | High D/E may be structural — compare within sector | P/E is paradoxically low at cycle peaks (high earnings) and high at cycle troughs (low earnings) |
| **Auto / Manufacturing** | — | Order Book / Revenue where available, CapEx cycle analysis | Normalize margins across 3-4 year auto/capex cycle before applying compression flags | — |
| **Renewable Power / Infra-80IA** | Tax Rate Anomaly as red flag (persistent low ETR is statutory, not suspicious) | Project-level capacity utilization if disclosable | ETR flag → informational only | 80-IA tax holiday produces structural sub-15% ETR for years |

---

## FRONTEND DESIGN SPECIFICATION

### Component: `FundamentalDeck.jsx`

**Design Aesthetic:** Premium dark-mode institutional research terminal. Think Bloomberg Terminal meets modern SaaS. Dense with data but scannable. Organized into logical collapsible sections.

**Layout Structure:**

1. **Executive Verdict Banner (Full-Width, Top)**
   - Subtle gradient background (dark slate to darker)
   - **Overall Fundamental Grade:** A+ / A / B+ / B / C / D / F (weighted across 10 pillars — specify weighting algorithm in your plan)
   - **One-Line Institutional Verdict:** Dynamically generated (A+: "Wealth-compounding franchise with pristine accounting"; D: "Severe earnings quality and capital destruction concerns")
   - **Red Flag Count Badge:** clicking scrolls to alert panel; includes suppressed-flag count with reason
   - **Holding Company / Special Structure Badge:** if holdco gate is triggered, display a prominent amber banner: "⚠️ Investment Holding Structure — standard ratios suppressed. See Phase 2 for NAV analysis."

2. **Phase 2 Data Gap Panel (Collapsible Info Section)**
   - Explicitly lists ALL Phase 2 stubs with what they are and why they're not yet available: RPT, Pledge %, Auditor changes, Contingent Liabilities, NAV for holdcos, FII trend (quarterly), promoter pledge
   - Design intent: the deck must never silently imply these are covered when they aren't

3. **Red Flag Alert Panel (Collapsible, auto-expanded if flags exist)**
   - `bg-red-950/40` with `border-red-500/30`
   - ALL triggered flags as numbered bullets, severity-colored
   - Suppressed flags (e.g., SGAI/LVGI in capital-raise year) listed as ℹ️ informational context

4. **Pillar Cards (2-column responsive grid)**
   - Each pillar card: header (icon + name + health dot), key metrics KV grid, trend arrows (↑↗→↘↓), collapsible full-details accordion, hover tooltips in plain English
   - Suppressed pillars (holdco): display `"Not applicable — Investment Holding Structure"` with amber badge

5. **DuPont Visual (inside Pillar 4 card)**
   - 3-factor: [Margin] × [Turnover] × [Leverage] = [ROE] — color-coded green/red by YoY direction
   - 5-factor below: [Tax Burden] × [Interest Burden] × [EBIT Margin] × [Turnover] × [Multiplier] = [ROE]
   - Capital Allocation Quadrant: 2×2 grid with the company's current position marked

6. **Peer Comparison Table (Full-width)**
   - 18 metrics (expanded list), target highlighted, color-coded cells (green = above median, red = below)
   - Sortable columns. Rank shown for each metric.
   - CCC vs ROCE Quadrant chart embedded below the table

7. **Ind AS 116 Lease Note Panel**
   - If Ind AS 116 transition year detected in the 5-year window: display a prominent informational note explaining the pre/post comparability issue

8. **3-Statement Raw Data (Collapsible at Bottom)**
   - Three tabs: Balance Sheet | Income Statement | Cash Flow
   - ₹ Cr format, 5 fiscal year columns

---

## REQUIRED FORMAT OF YOUR OUTPUT

Structure your response as a single, exhaustive markdown document with EXACTLY these 6 sections:

### SECTION 1: EXECUTIVE ARCHITECTURAL BLUEPRINT
- System design diagram (text-based: yfinance → cache → fundamental_service → server.py → frontend)
- Complete output dictionary schema (every key, nested key, data type)
- Graceful partial degradation rules (IPOs, holdcos, banks, missing fields, capital-raise years)
- Overall Fundamental Grade weighting algorithm (A+ through F)
- Holding Company gate logic
- Altman Z sector router implementation approach

### SECTION 2: EXHAUSTIVE MATHEMATICAL & ALIAS MAPPING TABLE
100+ row markdown table with columns:
| Metric Name | Formula | yfinance Aliases (for `_val()`) | Threshold / Interpretation | Pillar | Audit Correction Applied |

Include all Ind AS 116 lease-split aliases and deferred tax aliases.

### SECTION 3: COMPLETE RED FLAG ENGINE SPECIFICATION
All 16 custom flags + Altman Z + Sloan Accrual (growth-adjusted):
| # | Red Flag Name | Standard Trigger | Sector Override (if any) | Alert String Template | Severity | Audit Finding Applied |

### SECTION 4: SECTOR-SPECIFIC OVERRIDE SPECIFICATION
Expand the override table above with exact implementation logic (if/elif chain using sector_map.py output).

### SECTION 5: FRONTEND COMPONENT HIERARCHY & COLOR LOGIC
Describe (in words, NOT code): component tree, props flow, conditional rendering for all gates (holdco, lease note, capital-raise, sector suppression), color thresholds, responsive behavior.

### SECTION 6: SEQUENTIAL STEP-BY-STEP TASK LIST FOR THE CODING AGENT
Numbered checklist executed in strict dependency order. For each task:
- **Target File**
- **Exact Scope:** Functions/components to create or modify
- **Dependencies:** Prior tasks that must be complete
- **Verification Command:** Exact terminal command
- **Expected Output:** What success looks like

---

## CRITICAL CONSTRAINTS FOR YOUR PLAN

1. **ZERO CODE IN YOUR OUTPUT.** Not a single line of Python or JSX.
2. **REUSE EXISTING INFRASTRUCTURE.** Import from `forensic_service.py`, `sector_map.py`, `bhavcopy_service.py`.
3. **NO NEW PYTHON DEPENDENCIES.** Only `yfinance`, `pandas`, `numpy`, stdlib.
4. **GRACEFUL PARTIAL DEGRADATION.** Missing data → `available: False` with reason. Never crash another section.
5. **INDIAN MARKET CONTEXT.** ₹ Crores (/ 10^7). Default tax rate 25.17%. rf 7.0%. ERP 6.0%.
6. **PLAIN ENGLISH EVERYWHERE.** Every ratio has a tooltip. Every flag generates a human-readable sentence.
7. **ALL 14 AUDIT FINDINGS ARE MANDATORY.** Every single audit correction listed above must appear in your plan. Do not omit any.
8. **THE CODING AGENT NEVER MAKES A DESIGN DECISION.** Every threshold, color rule, sector gate, edge case, and formula variant is already resolved in this prompt. Your plan makes it unambiguous.

**BEGIN YOUR MASTER ARCHITECTURAL PLAN NOW.**
