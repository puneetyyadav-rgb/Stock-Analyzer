# Forensic Accounting Scorecard + ROIC vs WACC — detailed build doc

## Context
The platform's factor/quant stack scores purely on **price, volume, delivery, and options positioning**. It
cannot see earnings manipulation or value-destroying capital allocation — a manipulated-earnings name
scores fine right up until the restatement/fraud gap-down. This module adds the missing **fundamental
integrity layer**, using only deterministic formulas on **filed annual financial statements** (zero
hallucination, no LLM math, no new scraping infra).

Chosen over the other 4 candidate modules because it needs **no new data infrastructure**: the raw
material (annual balance sheet / income statement / cashflow) already comes back from yfinance for NSE
names, confirmed in-session. Modules #2 (shareholding/pledge) and #4 (insider/bulk-block deals) require
new scrapers with weaker NSE coverage; #3 (peer benchmarking) is the natural *next* step after this and
reuses the same fetch.

Two user decisions locked in:
- **Data gaps → graceful partial.** Piotroski + ROIC/WACC compute from the latest year (+ a few ratios).
  Beneish needs 2 consecutive years (it is a YoY *index* model); if <2 usable years come back, only the
  Beneish sub-block is marked `available: False` with a reason — the rest of the module still returns.
- **WACC → constants + beta (CAPM).** `rf=7.0%` (10y G-Sec, env-tunable), `ERP=6.0%`, `cost_of_equity =
  rf + beta·ERP`, after-tax `cost_of_debt` from Interest Expense ÷ Total Debt (fallback 8%). All constants
  env-tunable. No live G-Sec scrape (marginal precision, new failure mode).

Grounding facts verified this session:
- `yf.Ticker("RELIANCE.NS").balance_sheet` → **77 rows / 5 fiscal years**, includes `Invested Capital`,
  `Working Capital`, `Total Debt`, `Net Debt`, `Stockholders Equity`.
- `.cashflow` → **47 rows**, includes `Free Cash Flow`, `Capital Expenditure`, `Cash Dividends Paid`,
  `Repayment Of Debt`, `Issuance Of Debt`.
- `.financials` (income statement) is returned alongside the other two and carries `Net Income`,
  `Total Revenue`, `Gross Profit`, `Operating Income`, `Interest Expense`, `Depreciation And Amortization`.
- Existing wiring pattern (Feature 6, just shipped): an env-flag gated, best-effort try/except block in
  `stock_service.compute_technicals()` builds the payload → passes it as a new trailing kwarg into
  `quant_service.compute_complete_quant_deck()` → deck returns it as a new field → `StockDetails.jsx`
  renders a `KV` row → `ai_service.TECHNICAL_SYSTEM_PROMPT` gets a rule + a citation tag. This module
  follows that exact path.
- Cache pattern precedent: `sector_map.py` writes a JSON + `updatedAt` and treats it fresh for a TTL;
  `crash_regime_service.py` does the same with pickle for a non-JSON-serializable object. Our payload is
  plain numbers/strings → **JSON cache**, mirroring `sector_map_cache.json`.

---

## What we are NOT doing (scope guard)
- No quarterly/TTM statements. Annual only — matches Beneish/Piotroski's published construction and keeps
  the fetch to 3 yfinance attributes.
- No LLM involvement in any number. Formulas only; the AI layer only *reads* the precomputed flags.
- No peer benchmarking yet (that's module #3; this builds the per-stock engine it would compare across).
- No new Python dependencies (yfinance + pandas already present; JSON cache = stdlib).

---

## Data mapping — each formula's yfinance field (verified names)
Annual statements: `bs = t.balance_sheet`, `inc = t.financials`, `cf = t.cashflow` (each a DataFrame,
rows=line items, cols=fiscal years, newest col first). Helper `_val(df, [aliases], year_idx)` does a
case-insensitive alias lookup and returns `float` or `None` — this is the single chokepoint for the
"yfinance field naming varies" risk.

**Piotroski F-Score (9 binary tests, 1 pt each)** — needs current (t) + prior (t-1) year:
| # | Test | Fields |
|---|------|--------|
| 1 | ROA > 0 | `Net Income` ÷ `Total Assets` |
| 2 | Operating Cash Flow > 0 | `Operating Cash Flow` (cf) |
| 3 | ΔROA > 0 | ROA(t) > ROA(t-1) |
| 4 | Accruals: OCF > Net Income | quality of earnings |
| 5 | ΔLeverage < 0 | `Long Term Debt`÷`Total Assets` falling |
| 6 | ΔCurrent Ratio > 0 | `Current Assets`÷`Current Liabilities` rising |
| 7 | No new shares | `Ordinary Shares Number`/`Share Issued` not increased |
| 8 | ΔGross Margin > 0 | `Gross Profit`÷`Total Revenue` rising |
| 9 | ΔAsset Turnover > 0 | `Total Revenue`÷`Total Assets` rising |

**Beneish M-Score (8 indices, needs t-1 and t)** — classic weights, threshold −2.22 (8-var model):
`DSRI` (receivables index), `GMI` (gross margin index), `AQI` (asset quality index), `SGI` (sales growth),
`DEPI` (depreciation index), `SGAI` (SG&A index), `LVGI` (leverage index), `TATA` (accruals/total assets).
`M = −4.84 + 0.92·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI − 0.172·SGAI + 4.679·TATA − 0.327·LVGI`.
Fields: `Receivables`, `Total Revenue`, `Gross Profit`, `Total Assets`, `Current Assets`, `Net PPE`/`Plant
Property Equipment`, `Depreciation And Amortization`, `Selling General And Administration`, `Total Debt`,
`Current Liabilities`, `Total Assets`, `Income Before Tax`, `Operating Cash Flow` (for TATA), `Depreciation`.

**ROIC vs WACC**:
- `ROIC = NOPAT ÷ Invested Capital`; `NOPAT = Operating Income × (1 − tax_rate)`; `tax_rate` from
  `Tax Provision ÷ Pretax Income` (fallback 25.17% India corporate). `Invested Capital` directly on the
  balance sheet (confirmed present).
- `WACC` per the locked CAPM decision above; weights from `marketCap` (E, already in `get_overview`) and
  `Total Debt` (D). Verdict bands: `ROIC > WACC + 2%` → **Wealth Compounder**; `ROIC < WACC` → **Capital
  Destroyer**; within ±2% → **Marginal**.

If any required field for a sub-score is missing → that sub-score returns `available: False, reason:` and
the others still compute (the locked "graceful partial" decision).

---

## Files & changes

### 1. NEW `backend/forensic_service.py` (the engine — all formulas + cache)
- `_annual_frames(symbol)` → fetch `bs/inc/cf` once; **JSON cache to `backend/forensic_cache.json`**
  keyed by symbol with `updatedAt` ISO; fresh for `FORENSIC_TTL_DAYS` (default 7). Mirrors `sector_map`
  cache. On cache miss/stale → yfinance fetch, persist best-effort.
- `_val(df, aliases, year_idx)` → case-insensitive alias lookup (the field-name-variance chokepoint).
- `piotroski_f_score(frames)` → `{available, score 0-9, tests: {f1..f9: 0/1}, verdict}`.
- `beneish_m_score(frames)` → `{available, mScore, indices: {dsri..tata}, manipulatorRisk: bool, verdict}`;
  `available: False` if <2 years (locked decision).
- `roic_vs_wacc(frames, beta, market_cap)` → `{available, roic, wacc, spread, category}`.
- `analyze_forensics(symbol, beta=None, market_cap=None)` → **public API**; orchestrates the three
  sub-scores + `forensicAlert` string (e.g. *"⚠️ Net profit grew but Operating Cash Flow is negative and
  receivables jumped — high earnings-manipulation risk"* when F≤3 or M>−1.78 or TATA high). Always returns
  a dict; never raises (caller wraps in try/except anyway).
- `__main__` self-check (no network):
  - synthetic clean statements → F ≥ 7, M < −2.22, ROIC > WACC.
  - synthetic manipulated statements (inflate `Receivables` + `Total Revenue`, hold OCF flat) → M > −1.78,
    F drops, alert fires.
  - single-year frame → Beneish `available: False`, Piotroski/ROIC still compute (asserts the locked
    graceful-partial behavior).
  - live spot-check `analyze_forensics("RELIANCE")` wrapped in try/except with graceful offline skip.

### 2. `backend/stock_service.py` — wire into `compute_technicals()`
- After the existing `market_regime` block, add an env-flag gated best-effort block:
  ```python
  forensics = {"available": False, "reason": "disabled"}
  if os.environ.get("ENABLE_FORENSICS", "true").lower() != "false":
      try:
          import forensic_service as fsvc
          forensics = fsvc.analyze_forensics(sym, beta=<overview beta if handy>, market_cap=<if handy>)
      except Exception as e:
          logger.info(f"forensics skipped for {sym}: {e}")
          forensics = {"available": False, "reason": str(e)}
  ```
  (beta/marketCap are optional enrichers — ROIC falls back to constants if absent.)
- Add `forensics=forensics` to the `compute_complete_quant_deck(...)` call.

### 3. `backend/quant_service.py` — extend `compute_complete_quant_deck()`
- Signature: add trailing `forensics: Optional[Dict[str, Any]] = None`.
- Return dict: add `"forensics": forensics` alongside the existing pass-through fields (`marketRegime`,
  `signalBacktest`, etc.). No multiplication into `quantScore` (same convention as `marketRegime` — it's a
  *gate/overlay*, not a momentum factor).

### 4. `frontend/src/components/StockDetails.jsx` — render
Three `KV` rows after the existing `Market Regime (Nifty)` row (line ~93), each guarded by its
`?.available` and color-coded like the neighbors:
- **Forensic F-Score** → `{score}/9` (emerald ≥7, amber 4-6, red ≤3).
- **Earnings Manipulation (M)** → `{mScore}` + `Manipulator Risk` when `manipulatorRisk` (red bold when
  flagged, else emerald). Renders only when Beneish `available`.
- **ROIC vs WACC** → `{roic}% vs {wacc}% | {category}` (emerald Compounder, red Capital Destroyer, amber
  Marginal).
- Optional alert line: if `forensicAlert` present, a red `⚠` row.

### 5. `backend/ai_service.py` — prompt rules (read-only consumption)
- Extend `TECHNICAL_SYSTEM_PROMPT` `SIGNAL-QUALITY RULE` (line ~282): *"Treat forensics.mScore > −1.78 or
  forensics.fScore ≤ 3 as an earnings-integrity red flag independent of price/quant setup; treat
  forensics.category = 'Capital Destroyer' (ROIC < WACC) as structurally value-destructive."*
- Add `[Forensics]` to the `SOURCE CITATION RULE` tag list (line ~284).

### 6. `.gitignore`
- Add `backend/forensic_cache.json` next to `backend/sector_map_cache.json`.

**No change to `requirements.txt`** — no new deps.

---

## Task list (for the coder)
1. **`forensic_service.py`** — engine: `_annual_frames`+JSON cache, `_val` alias lookup, `piotroski_f_score`,
   `beneish_m_score`, `roic_vs_wacc`, `analyze_forensics`, `__main__` self-check. Run
   `python forensic_service.py` → all three synthetic assertions pass + live RELIANCE spot-check prints.
2. **Wire `stock_service.compute_technicals()`** — env-flag block + pass into deck.
3. **Extend `quant_service.compute_complete_quant_deck()`** — signature + return field.
   Re-run `python quant_service.py` self-check → unchanged output (new field is pass-through).
4. **`StockDetails.jsx`** — 3 KV rows (+ optional alert row).
5. **`ai_service.py`** — SIGNAL-QUALITY RULE + `[Forensics]` citation tag.
6. **`.gitignore`** — `backend/forensic_cache.json`.
7. **Verify end-to-end** — `python -c "import stock_service as ss; d=ss.compute_technicals('RELIANCE');
   print(d['quantDeck']['forensics'])"` → populated; `python -c "import server"` → imports clean.

## Coding process — exact step-by-step (do these in order)
Each task below is one focused edit + one runnable check. Don't move to the next until the check passes.
Run all commands from the `backend/` directory unless noted.

**Task 1 — build the engine (`forensic_service.py`)**
1. Create `backend/forensic_service.py` with the pieces listed in "Files & changes → 1".
2. Start from the *helper layer first* and test each piece before the next:
   - `_annual_frames(symbol)` + JSON cache → quick `python -c` to confirm it returns 3 DataFrames and writes `forensic_cache.json`.
   - `_val(df, aliases, year_idx)` → assert it finds `Net Income`, `Total Revenue`, `Total Assets`, `Receivables`, `Operating Cash Flow`, `Invested Capital` on a real frame.
3. Implement `piotroski_f_score` → `beneish_m_score` → `roic_vs_wacc` → `analyze_forensics` (each is pure math on the frames).
4. Write the `__main__` self-check (the 4 cases in "Files & changes → 1").
5. **Check:** `python forensic_service.py` → all synthetic assertions pass AND live spot-check prints (or offline-skips). Stop here if any assert fails — fix the formula, not the test.

**Task 2 — extend the deck (`quant_service.py`)**
1. Add `forensics: Optional[Dict[str, Any]] = None` to the `compute_complete_quant_deck` signature (trailing param).
2. Add `"forensics": forensics` to the return dict (next to `marketRegime`).
3. **Check:** `python quant_service.py` → existing self-check output is byte-identical to before (new field is pass-through, default `None`).

**Task 3 — wire the caller (`stock_service.py`)**
1. In `compute_technicals()`, right after the `market_regime` block, paste the env-flag gated `forensics` block from "Files & changes → 2".
2. Add `forensics=forensics` to the `compute_complete_quant_deck(...)` call.
3. **Check:** `python -c "import stock_service as ss; d=ss.compute_technicals('RELIANCE'); import json; print(json.dumps(d['quantDeck']['forensics'], indent=2))"` → populated dict with fScore/mScore/roic present.

**Task 4 — AI prompt (`ai_service.py`)**
1. Extend `SIGNAL-QUALITY RULE` (line ~282) with the forensics red-flag sentence.
2. Add `[Forensics]` to the `SOURCE CITATION RULE` tag list (line ~284).
3. **Check:** `python -c "import ai_service"` → imports clean (prompt is just a string; no runtime check needed beyond import).

**Task 5 — frontend (`frontend/src/components/StockDetails.jsx`)**
1. After the `Market Regime (Nifty)` KV row (~line 93), add the 3 new KV rows (+ optional `forensicAlert` row) from "Files & changes → 4", each guarded by `?.available`.
2. **Check:** with backend running, load a stock page → the three rows render with sane values/colors; a thin name shows only F-Score + ROIC rows (Beneish hidden when unavailable).

**Task 6 — gitignore**
1. Add `backend/forensic_cache.json` to `.gitignore` beside `backend/sector_map_cache.json`.
2. **Check:** `git status --short` → `forensic_cache.json` no longer appears as untracked.

**Task 7 — full end-to-end verification** (the checklist in "Verification" below): run each command, confirm each expected result, then confirm `python -c "import server"` imports clean.

**Dependency order:** Task 1 must finish (engine works standalone) before 2-3 (they only pass it through). 2 and 3 are independent of each other but both depend on 1. 4, 5, 6 are independent of each other and of 2-3 but all depend on 1's output shape. 7 is last.

**No git commit** unless you explicitly ask for one.

## Verification (end-to-end)
- `python backend/forensic_service.py` — synthetic clean / manipulated / single-year assertions all pass;
  live RELIANCE spot-check prints F, M, ROIC/WACC (or graceful offline skip).
- `python backend/quant_service.py` — prior self-check output unchanged.
- Live deck spot-check on RELIANCE **and a thin/recently-listed name** → thin name shows
  `beneish.available: False` but Piotroski/ROIC present (proves graceful partial, not all-or-nothing).
- `python -c "import server"` — clean import.
- Frontend: load a stock page → the three new KV rows render with sane values and correct color states.

## Risks & ceilings
- **yfinance field naming varies by ticker/version** → mitigated by the `_val` alias list at one chokepoint;
  a missing field degrades that sub-score to `available: False` rather than crashing (matches regime service).
- **Beneish/Piotroski are annual & lagging** — they reflect the last filed fiscal year, not real-time. This
  is inherent to forensic accounting; the cache TTL (7d) matches how slowly statements change.
- **Banks/NBFCs**: Beneish's AQI/current-ratio logic mis-fits lenders (different balance-sheet structure).
  Ceiling noted in output via a `note` when `sector == "Financial Services"` (sector already in
  `get_overview`) — scores still computed but flagged as lower-confidence. Not special-cased further.
- **WACC uses constant rf/ERP** (locked decision) — documented as an estimate, not a live curve.
