# INDEPENDENT PROMPT REVIEWER & RED-TEAM AUDIT PROMPT
# (INDIAN CORPORATE LAW, IND AS, AND SECTOR-SPECIFIC STRESS TEST)

> **Copy everything below this line and feed it to an independent AI model (Claude Opus, GPT-4o, o3-mini, or Gemini 1.5 Pro) along with our `fundamental_deck_prompt.md`.**

---

# MISSION BRIEF FOR THE INDEPENDENT REVIEWER

You are acting as an independent panel of three expert reviewers:
1. **A Senior Partner & Forensic Audit Head at a Big 4 Accounting Firm in India** (deep expert in Ind AS, Companies Act 2013, Income Tax Act 1961, and SEBI LODR regulations).
2. **A Principal Buy-Side Equity Research Analyst covering Indian Equities** (veteran of NSE/BSE sector dynamics, business models, and valuation nuances across 15+ sectors).
3. **A Chief Risk Officer (CRO) & Quantitative Strategist** specializing in eliminating false positives/negatives in algorithmic credit and equity scoring models.

### YOUR TASK
I am going to provide you with a comprehensive architectural prompt (`fundamental_deck_prompt.md`) designed to build an institutional-grade **Fundamental & Forensic Equity Research Deck** for Indian equities (NSE/BSE).

Your job is to **rigorously audit, red-team, and critique this prompt** before we give it to our software architects to implement. We want this system to be **100% BULLET-PROOF**. One flawed assumption in an automated algorithmic system can cause catastrophic misclassifications—such as flagging a legitimate EPC contractor for "channel stuffing" due to normal retention money, or triggering a depreciation fraud alert on a company simply following Companies Act vs. Income Tax depreciation differences.

---

## CORE AUDIT AREAS REQUIRED IN YOUR REVIEW

You must independently evaluate our prompt across the following 5 critical dimensions and deliver an actionable, bullet-proof upgrade list:

### 1. INDIAN STATUTORY & ACCOUNTING STANDARDS (Ind AS vs. US GAAP / IFRS)
Most standard forensic models (Beneish M-Score, Altman Z, Piotroski) were designed in the US under US GAAP in the 1990s/2000s. You must audit our prompt for **Indian regulatory reality**:
- **Ind AS 116 (Leases):** Under Ind AS 116, operating leases are capitalized as Right-of-Use (RoU) Assets and Lease Liabilities. This artificially inflates Total Debt, Debt/Equity, and EBITDA, while depressing Net Income in early lease years. Does our prompt account for Ind AS 116 distortions in Debt/EBITDA and Interest Coverage covenants?
- **Depreciation Dual-Policy (Companies Act vs. Income Tax Act):** Companies Act 2013 (Schedule II) mandates useful lives and depreciation methods (SLM vs WDV), whereas Income Tax Act 1961 (Section 32) mandates block of assets and different WDV rates. This difference creates massive Deferred Tax Assets (DTA) or Deferred Tax Liabilities (DTL). Will our Beneish DEPI (Depreciation Index) or Sloan Accrual ratio trigger false alarms due to legitimate statutory DTA/DTL accounting? How should the prompt be adjusted?
- **Tax Rates & MAT (Minimum Alternate Tax):** While standard corporate tax under Section 115BAA is 25.17%, Indian companies under tax holidays (80-IA, 80-IE, SEZ units) or paying MAT under Section 115JB have effective tax rates of 15% or 17.5%. How do we prevent our "Tax Rate Anomaly" red flag (<10% or >40%) from misclassifying clean SEZ exporters, renewable energy generators, or IT firms?
- **Related Party Transactions (RPTs) & LODR:** In Indian family-owned conglomerates, promoter group cross-holdings and RPTs are the primary vector for value leakage. Are we missing a specific check for RPT receivables / loans & advances under SEBI LODR disclosures?

---

### 2. SECTORAL BUSINESS MODEL EXCEPTIONS & FALSE-POSITIVE TRAPS
A ratio that signals fraud in one sector is standard operating procedure in another. Audit our Sector-Specific Overrides and identify any missing sectoral traps:
- **EPC / Capital Goods / Defense:** Days Sales Outstanding (DSO) of 150-250 days is standard due to government receivables, milestone billing, and retention money (10% held until warranty ends). Our "Receivables vs. Revenue Divergence" flag (>1.5x) would falsely label every major Indian EPC contractor as a fraud. How must the threshold be parameterized for EPC/Govt contractors?
- **Real Estate (Ind AS 115 - Revenue from Contracts with Customers):** Revenue recognition is percentage-of-completion or completed-contract. Cash collections (Advances from Customers) show up as Current Liabilities while inventory sits on assets. A naïve Current Ratio or CCC computation fails here. What specific overrides must be added?
- **Pharma & Chemical (CDMO / API):** High inventory holding periods (DIO of 120+ days) are mandatory due to strategic raw material buffering (China import dependency) and US FDA batch validation cycles. How should inventory accumulation red flags be adjusted for Pharma/Chemicals?
- **Telecom & Airlines:** Structurally negative net worth or massive debt-to-equity is common due to spectrum liabilities or aircraft RoU leases. How do we prevent Altman Z-Score from giving useless distress signals here?
- **Holding Companies & Conglomerates:** Shares like Bajaj Holdings, Tata Investment, or Grasim trade at massive holding company discounts with zero operating cash flow from core operations (only dividend income). How should holding companies be gated?

---

### 3. ACADEMIC MODEL VALIDITY ON INDIAN EQUITIES
- **Altman Z-Score:** The weights ($1.2, 1.4, 3.3, 0.6, 1.0$) were calibrated on US manufacturing firms in 1968. Is Altman Z-Score appropriate for modern Indian service/tech/consumer equities, or should we instruct the architect to use the **Altman Z'-Score (Revised for Non-Manufacturing / Emerging Markets)**? What exact coefficients should be mandated for India?
- **Beneish M-Score in India:** Are there specific variables in Beneish (like SGAI or LVGI) that produce noise in Indian growth companies undergoing rapid equity dilution (QIPs/Preferential allotments) or aggressive Capex expansion?
- **Sloan Accrual Ratio:** In rapid-growth Indian economies, working capital investments scale fast. What is the institutional threshold for Sloan Accruals in India ($>10\%$ or $>15\%$)?

---

### 4. YFINANCE DATA LAKE & SCHEMA DRIFT REALITIES
- We rely on `yfinance` (`.balance_sheet`, `.financials`, `.cashflow`) for Indian stocks (`.NS` / `.BO`).
- Are there specific Indian line items in Yahoo Finance that get merged or mislabeled? (e.g., "Other Income" vs. "Operating Revenue", "Long Term Debt" vs. "Lease Liabilities", "Share Warrants", "Minority Interest").
- What additional case-insensitive aliases MUST we add to our `_val()` mapping table to ensure Indian annual reports are parsed without silent failures?

---

### 5. MISSING "KILLER" FUNDAMENTAL METRICS FOR INDIA
What 3 to 5 critical metrics or red flags used by elite Indian fund managers (Saurabh Mukherjea, Kenneth Andrade, Prashant Jain, Motilal Oswal QGLP) are currently **missing** from our 10-pillar prompt?
*(Examples to evaluate: Reinvestment Rate vs. ROIC incremental compounding, Capital Allocation Track Record over 10 years, Promoter Share Pledge % proxy, Auditor Resignation / Auditor Fee to Revenue spike proxy, Cash Conversion Cycle vs. ROCE matrix).*

---

## REQUIRED FORMAT FOR YOUR AUDIT REPORT

Please deliver your independent audit report in the following structured format:

### 📌 SECTION 1: CRITICAL FLAWS & FALSE-POSITIVE TRAPS IDENTIFIED
List every rule, threshold, or formula in our prompt that will fail or misclassify Indian companies due to Ind AS, tax law, or sectoral realities. Explain *why* it fails and provide the exact corrected formula or conditional logic.

### 📌 SECTION 2: ACADEMIC MODEL CORRECTIONS (ALTMAN, BENEISH, SLOAN FOR INDIA)
Specify the exact mathematical adjustments and emerging-market coefficients required to make Altman Z, Beneish M-Score, and Sloan Accruals reliable for NSE/BSE listed equities.

### 📌 SECTION 3: MISSING SECTOR OVERRIDES & GATING RULES
Provide an expanded table of sector overrides covering EPC/Defense, Real Estate, CDMO/Pharma, Telecom, and Holding Companies.

### 📌 SECTION 4: THE "MISSING 5" INDIAN INSTITUTIONAL METRICS
Detail the 5 most powerful fundamental checks specific to the Indian market that we must ADD to our prompt before finalizing the architecture.

### 📌 SECTION 5: EXACT TEXT SNIPPETS TO INSERT INTO OUR PROMPT
Provide ready-to-copy markdown blocks containing your corrections, new red flags, and adjusted formulas so we can copy-paste them directly into our master build prompt!

---
*(Attach or paste our `fundamental_deck_prompt.md` below this line when feeding to the reviewer model).*
