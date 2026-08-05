import React, { useState } from "react";
import { ShieldAlert, AlertTriangle, CheckCircle2, Info, HelpCircle, AlertOctagon, ChevronDown, ChevronUp } from "lucide-react";
import { fmtNum, fmtPct, getVal0, zoneStyle } from "./fundamentalUtils";

// ─── helpers ────────────────────────────────────────────────────────────────
const cr = (v) => (v == null ? "—" : `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`);
const idx = (v) => (v == null ? "—" : Number(v).toFixed(4));
const pct = (v) => (v == null ? "—" : `${(Number(v) * 100).toFixed(2)}%`);
const num4 = (v) => (v == null ? "—" : Number(v).toFixed(4));

// colour an index value: >1.05 amber, >1.30 red, else green
function idxColor(v, invert = false) {
  if (v == null) return "text-zinc-400";
  const hi = invert ? v < 0.95 : v > 1.30;
  const mid = invert ? v < 1.00 : v > 1.05;
  if (hi) return "text-red-400";
  if (mid) return "text-amber-400";
  return "text-emerald-400";
}

// ─── Expandable toggle button ────────────────────────────────────────────────
function CalcToggle({ open, onClick }) {
  return (
    <button
      onClick={onClick}
      className="mt-3 flex items-center gap-1.5 text-[11px] text-indigo-400 hover:text-indigo-300 transition-colors font-mono tracking-wide"
    >
      {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      {open ? "Hide Calculation" : "Show Calculation"}
    </button>
  );
}

// ─── BENEISH expanded panel ──────────────────────────────────────────────────
function BeneishCalcPanel({ calc }) {
  if (!calc) return <p className="text-xs text-zinc-500 italic mt-3">Calculation data not available.</p>;

  const { fiscalYear, priorFiscalYear, inputs: inp, indices, weights, formula, finalScore, corroborated, sgaiLvgiSuppressed } = calc;

  const indexRows = [
    { key: "DSRI",  label: "Days Sales Receivable Index",      desc: "Rising receivables vs revenue → possible fake sales" },
    { key: "GMI",   label: "Gross Margin Index",               desc: "Prior gross margin ÷ current — deterioration precedes manipulation" },
    { key: "AQI",   label: "Asset Quality Index",              desc: "Soft/non-productive asset buildup" },
    { key: "SGI",   label: "Sales Growth Index",               desc: "Revenue growth — aggressive growth often precedes manipulation" },
    { key: "DEPI",  label: "Depreciation Index",               desc: "Slowing depreciation rate → extending asset life on paper" },
    { key: "SGAI",  label: "SG&A Index",                       desc: "Rising overhead vs revenue signals inefficiency", suppressed: sgaiLvgiSuppressed },
    { key: "TATA",  label: "Total Accruals to Total Assets",   desc: "Core manipulation indicator — accruals not backed by cash", invertColor: false },
    { key: "LVGI",  label: "Leverage Index",                   desc: "Rapidly rising debt relative to assets", suppressed: sgaiLvgiSuppressed },
  ];

  // Reconstruct weighted formula line
  const W = weights || {};
  const I = indices || {};
  const terms = [
    { w: W.DSRI,  v: I.DSRI,  label: "DSRI" },
    { w: W.GMI,   v: I.GMI,   label: "GMI" },
    { w: W.AQI,   v: I.AQI,   label: "AQI" },
    { w: W.SGI,   v: I.SGI,   label: "SGI" },
    { w: W.DEPI,  v: I.DEPI,  label: "DEPI" },
    { w: W.SGAI,  v: I.SGAI,  label: "SGAI" },
    { w: W.TATA,  v: I.TATA,  label: "TATA" },
    { w: W.LVGI,  v: I.LVGI,  label: "LVGI" },
  ];

  return (
    <div className="mt-4 border-t border-zinc-800/80 pt-4 space-y-4 text-[11px]">
      <p className="text-zinc-500 font-mono">FY {fiscalYear?.slice(0, 7) || "—"} vs {priorFiscalYear?.slice(0, 7) || "—"} · Source: yfinance annual statements</p>

      {/* Raw Inputs */}
      <div>
        <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-2 text-[10px]">Raw Inputs (₹ Crores)</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono">
          {[
            ["Revenue (t)",         inp?.revenue_t],
            ["Revenue (t-1)",       inp?.revenue_t1],
            ["Receivables (t)",     inp?.receivables_t],
            ["Receivables (t-1)",   inp?.receivables_t1],
            ["Gross Profit (t)",    inp?.grossProfit_t],
            ["Gross Profit (t-1)",  inp?.grossProfit_t1],
            ["Net Income (t)",      inp?.netIncome_t],
            ["Op. Cash Flow (t)",   inp?.ocf_t],
            ["Total Assets (t)",    inp?.totalAssets_t],
            ["Total Assets (t-1)",  inp?.totalAssets_t1],
            ["Current Assets (t)",  inp?.currentAssets_t],
            ["Net PP&E (t)",        inp?.netPPE_t],
            ["SG&A (t)",            inp?.sga_t],
            ["Depreciation (t)",    inp?.depreciation_t],
            ["Total Debt (t)",      inp?.totalDebt_t],
            ["Total Debt (t-1)",    inp?.totalDebt_t1],
          ].map(([label, val]) => (
            <div key={label} className="flex justify-between items-center py-0.5 border-b border-zinc-800/40">
              <span className="text-zinc-500">{label}</span>
              <span className="text-zinc-200">{cr(val)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 8 Indices */}
      <div>
        <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-2 text-[10px]">8 Beneish Index Values</p>
        <div className="space-y-1.5">
          {indexRows.map(({ key, label, desc, suppressed }) => {
            const val = I[key];
            const w = W[key];
            return (
              <div key={key} className={`rounded border border-zinc-800/60 p-2 bg-zinc-900/40 ${suppressed ? "opacity-50" : ""}`}>
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-zinc-200">{key}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-zinc-500">weight: <span className="text-zinc-300">{w}</span></span>
                    <span className={`font-mono font-bold text-sm ${idxColor(val)}`}>{idx(val)}</span>
                  </div>
                </div>
                <p className="text-zinc-500 mt-0.5">{label} — {desc}</p>
                {suppressed && <p className="text-amber-500/80 mt-0.5 italic">⚠ Suppressed: capital raise detected in this window</p>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Final Formula */}
      <div className="bg-zinc-900/60 border border-indigo-900/40 rounded p-3">
        <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-2 text-[10px]">Final M-Score Calculation</p>
        <p className="text-zinc-500 font-mono mb-2 text-[10px]">{formula}</p>
        <div className="flex flex-wrap gap-x-2 gap-y-1 font-mono text-[10px] text-zinc-400 mb-2">
          <span className="text-zinc-500">{W.intercept}</span>
          {terms.map(({ w, v, label }) => (
            <span key={label}>
              {w >= 0 ? "+" : ""}{w} × <span className="text-zinc-200">{v != null ? Number(v).toFixed(4) : "—"}</span>
              <span className="text-zinc-600">({label})</span>
            </span>
          ))}
        </div>
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
          <span className="text-zinc-400">Final M-Score</span>
          <span className="text-lg font-mono font-bold text-zinc-100">{finalScore != null ? Number(finalScore).toFixed(2) : "—"}</span>
        </div>
        {corroborated && (
          <p className="text-red-400 mt-2 text-[10px]">⚠ Corroboration Triggered: High M-Score + TATA &gt; 0.10 + OCF/NI &lt; 0.80</p>
        )}
      </div>
    </div>
  );
}

// ─── ALTMAN expanded panel ───────────────────────────────────────────────────
function AltmanCalcPanel({ calc }) {
  if (!calc) return <p className="text-xs text-zinc-500 italic mt-3">Calculation data not available.</p>;

  const { fiscalYear, model, formula, selectionReason, weights: W, thresholds, inputs: inp, variables, finalScore, zone } = calc;
  const varKeys = ["X1", "X2", "X3", "X4", "X5"].filter(k => variables?.[k]?.value != null);

  const zoneColor = zone === "Safe" ? "text-emerald-400" : zone === "Grey" ? "text-amber-400" : "text-red-400";

  return (
    <div className="mt-4 border-t border-zinc-800/80 pt-4 space-y-4 text-[11px]">
      <div className="flex items-center justify-between">
        <p className="text-zinc-500 font-mono">FY {fiscalYear?.slice(0, 7) || "—"} · Model: <span className="text-indigo-300">{thresholds?.label || model}</span></p>
      </div>
      <p className="text-zinc-500 text-[10px] italic">{selectionReason}</p>

      {/* Raw Inputs */}
      <div>
        <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-2 text-[10px]">Raw Inputs (₹ Crores)</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono">
          {[
            ["Current Assets",       inp?.currentAssets],
            ["Current Liabilities",  inp?.currentLiabilities],
            ["Working Capital",      inp?.workingCapital],
            ["Retained Earnings",    inp?.retainedEarnings],
            ["EBIT",                 inp?.ebit],
            ["Revenue",              inp?.revenue],
            ["Total Assets",         inp?.totalAssets],
            ["Total Liabilities",    inp?.totalLiabilities],
            ["Book Equity",          inp?.bookEquity],
            ["Market Cap",           inp?.marketCap],
          ].map(([label, val]) => (
            <div key={label} className="flex justify-between items-center py-0.5 border-b border-zinc-800/40">
              <span className="text-zinc-500">{label}</span>
              <span className="text-zinc-200">{cr(val)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* X1–X5 Variables */}
      <div>
        <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-2 text-[10px]">Variable Breakdown</p>
        <div className="space-y-1.5">
          {varKeys.map((k) => {
            const v = variables[k];
            const w = W?.[k];
            const contribution = w != null && v?.value != null ? w * v.value : null;
            return (
              <div key={k} className="rounded border border-zinc-800/60 p-2 bg-zinc-900/40">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-mono font-bold text-indigo-300">{k}</span>
                  <div className="flex items-center gap-3 font-mono text-xs">
                    {w != null && <span className="text-zinc-500">w={w} × <span className="text-zinc-200">{num4(v.value)}</span> = <span className="text-amber-300">{contribution != null ? contribution.toFixed(4) : "—"}</span></span>}
                  </div>
                </div>
                <p className="text-zinc-500">{v.formula}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Score reconstruction */}
      <div className="bg-zinc-900/60 border border-amber-900/30 rounded p-3">
        <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-2 text-[10px]">Final Z-Score</p>
        <p className="text-zinc-500 font-mono text-[10px] mb-2">{formula}</p>
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
          <span className="text-zinc-400">Z-Score</span>
          <span className="text-lg font-mono font-bold text-zinc-100">{finalScore != null ? Number(finalScore).toFixed(2) : "—"}</span>
        </div>
        <div className="flex items-center justify-between mt-1 text-[10px] font-mono">
          <span className="text-zinc-500">Zone: <span className={`font-bold ${zoneColor}`}>{zone}</span></span>
          <span className="text-zinc-500">Safe &gt; {thresholds?.safe} | Grey &gt; {thresholds?.grey_low}</span>
        </div>
      </div>
    </div>
  );
}

// ─── SLOAN expanded panel ────────────────────────────────────────────────────
function SloanCalcPanel({ calc }) {
  if (!calc) return <p className="text-xs text-zinc-500 italic mt-3">Calculation data not available.</p>;

  const { fiscalYear, priorFiscalYear, inputs: inp, variants, growthContext: gc } = calc;

  const variantRows = [
    { key: "standard",           label: "Standard Accrual",          color: "text-zinc-200" },
    { key: "rawSloan",           label: "Raw Sloan (incl. ICF)",      color: "text-amber-300" },
    { key: "deferredTaxAdjusted",label: "Deferred-Tax Adjusted",     color: "text-orange-300" },
  ];

  return (
    <div className="mt-4 border-t border-zinc-800/80 pt-4 space-y-4 text-[11px]">
      <p className="text-zinc-500 font-mono">FY {fiscalYear?.slice(0, 7) || "—"} vs {priorFiscalYear?.slice(0, 7) || "—"} · Source: yfinance</p>

      {/* Raw Inputs */}
      <div>
        <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-2 text-[10px]">Raw Inputs (₹ Crores)</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono">
          {[
            ["Net Income",            inp?.netIncome],
            ["Operating Cash Flow",   inp?.operatingCashFlow],
            ["Investing Cash Flow",   inp?.investingCashFlow],
            ["Deferred Tax",          inp?.deferredTax],
            ["Total Assets (t)",      inp?.totalAssets_t],
            ["Total Assets (t-1)",    inp?.totalAssets_t1],
            ["Avg Total Assets",      inp?.avgTotalAssets],
          ].map(([label, val]) => (
            <div key={label} className="flex justify-between items-center py-0.5 border-b border-zinc-800/40">
              <span className="text-zinc-500">{label}</span>
              <span className="text-zinc-200">{cr(val)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 3 Variants */}
      <div>
        <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-2 text-[10px]">Three Accrual Variants</p>
        <div className="space-y-2">
          {variantRows.map(({ key, label, color }) => {
            const v = variants?.[key];
            if (!v) return null;
            return (
              <div key={key} className="rounded border border-zinc-800/60 p-2.5 bg-zinc-900/40">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-semibold text-zinc-200">{label}</span>
                  <span className={`font-mono font-bold text-sm ${color}`}>
                    {v.valuePct != null ? `${v.valuePct.toFixed(2)}%` : "—"}
                  </span>
                </div>
                <p className="text-zinc-500 font-mono text-[10px]">{v.formula}</p>
                <p className="text-zinc-600 mt-0.5">{v.description}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Growth Band Context */}
      {gc && (
        <div className="bg-zinc-900/60 border border-cyan-900/30 rounded p-3">
          <p className="text-zinc-400 font-semibold uppercase tracking-wider mb-1.5 text-[10px]">Growth-Adjusted Threshold</p>
          <div className="flex gap-4 font-mono text-[10px] mb-2">
            <span className="text-zinc-500">3Y Revenue CAGR: <span className="text-cyan-300">{gc.revenue3yCagr != null ? `${Number(gc.revenue3yCagr).toFixed(1)}%` : "—"}</span></span>
            <span className="text-zinc-500">Band: <span className="text-cyan-300">{gc.cagrBand}</span></span>
          </div>
          <div className="flex gap-4 font-mono text-[10px] mb-2">
            <span className="text-zinc-500">Moderate Threshold: <span className="text-amber-300">{gc.moderateThreshold}%</span></span>
            <span className="text-zinc-500">Severe Threshold: <span className="text-red-400">{gc.severeThreshold}%</span></span>
          </div>
          <p className="text-zinc-600 text-[10px]">{gc.note}</p>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────
export default function FundamentalForensics({ forensics, sectorBucket, gates }) {
  const [filter, setFilter] = useState("all"); // "all" | "triggered"
  const [expandedCalc, setExpandedCalc] = useState(null); // "beneish" | "altman" | "sloan" | null
  const [expandedFlag, setExpandedFlag] = useState(null); // flag id number | null

  if (!forensics) return null;

  const redFlags = forensics.redFlags || [];
  const phase2StubsRaw = forensics.phase2Stubs || {};
  const phase2Stubs = Array.isArray(phase2StubsRaw)
    ? phase2StubsRaw
    : Object.entries(phase2StubsRaw).map(([key, val]) => ({
        name: key === "rpt" ? "Related Party Transactions (RPT)" : key === "promoterPledge" ? "Promoter Pledge %" : key === "auditorChange" ? "Auditor Integrity / Switch" : key === "contingentLiabilities" ? "Contingent Liabilities" : key === "navDiscount" ? "NAV Discount %" : key,
        ...(typeof val === "object" && val !== null ? val : { reason: String(val) })
      }));
  const beneish = forensics.beneish || {};
  const altman = forensics.altmanZ || {};
  const sloan = forensics.sloanAccrual || {};

  const triggeredFlags = redFlags.filter((f) => f.triggered);
  const displayedFlags = filter === "triggered" ? triggeredFlags : redFlags;

  const beneishScore = getVal0(beneish.mScore);
  const beneishBand = getVal0(beneish.riskBand) || "Low/Clean";
  const altmanScore = getVal0(altman.score);
  const altmanZone = getVal0(altman.zone) || (altman.available ? "Safe" : "N/A");
  const sloanVal = getVal0(sloan.accrualRatio);
  const sloanBand = sloan.revenue3yCagrBand || "<10%";
  const sloanLevel = getVal0(sloan.flagLevel) || "Normal";

  const toggle = (key) => setExpandedCalc(prev => prev === key ? null : key);

  return (
    <div className="space-y-6">
      {/* Three Quantitative Forensic Models Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

        {/* 1. Beneish M-Score Card */}
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-4 flex flex-col hover:border-zinc-700/80 transition-all">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold tracking-wider text-zinc-300 uppercase flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-indigo-400" /> Beneish M-Score
              </span>
              <span className={`px-2 py-0.5 text-[10px] font-medium rounded uppercase ${zoneStyle(beneish.escalatedToRed ? "Red" : beneishBand)}`}>
                {beneish.escalatedToRed ? "ESCALATED TO RED" : beneishBand}
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-zinc-100 my-1">
              {beneish.available ? fmtNum(beneishScore, 2) : "Suppressed"}
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed mt-2">
              {beneish.available
                ? `Measures earnings manipulation risk. Thresholds: > -1.78 is High Risk, -2.22 to -1.78 is Moderate.`
                : beneish.reason || "Not applicable for financial/holding structures."}
            </p>
          </div>
          {beneish.available && (
            <div className="mt-3 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-400">
              <span>Corroborating Flags: <strong className="text-zinc-200">{beneish.corroboratingFlagCount || 0}</strong></span>
              {beneish.escalatedToRed && (
                <span className="text-red-400 font-medium flex items-center gap-1">
                  <AlertOctagon className="w-3 h-3" /> Rule Triggered
                </span>
              )}
            </div>
          )}
          {beneish.available && (
            <>
              <CalcToggle open={expandedCalc === "beneish"} onClick={() => toggle("beneish")} />
              {expandedCalc === "beneish" && <BeneishCalcPanel calc={beneish.calculation} />}
            </>
          )}
        </div>

        {/* 2. Altman Z-Score Card */}
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-4 flex flex-col hover:border-zinc-700/80 transition-all">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold tracking-wider text-zinc-300 uppercase flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Altman Z-Score
              </span>
              <span className={`px-2 py-0.5 text-[10px] font-medium rounded uppercase ${zoneStyle(altmanZone)}`}>
                {altmanZone}
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-zinc-100 my-1">
              {altman.available ? (altmanScore !== null ? fmtNum(altmanScore, 2) : "Safe") : "Suppressed"}
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed mt-2">
              {altman.selectionReason || altman.reason || `Model selected by sector router: ${altman.modelUsed || "Standard"}.`}
            </p>
          </div>
          <div className="mt-3 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[10px] text-zinc-500 font-mono">
            <span>MODEL: {altman.modelUsed || altman.model || "N/A"}</span>
            <span>SECTOR: {sectorBucket}</span>
          </div>
          {altman.available && altman.calculation && (
            <>
              <CalcToggle open={expandedCalc === "altman"} onClick={() => toggle("altman")} />
              {expandedCalc === "altman" && <AltmanCalcPanel calc={altman.calculation} />}
            </>
          )}
        </div>

        {/* 3. Sloan Accrual Ratio Card */}
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-4 flex flex-col hover:border-zinc-700/80 transition-all">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold tracking-wider text-zinc-300 uppercase flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-cyan-400" /> Sloan Accrual Ratio
              </span>
              <span className={`px-2 py-0.5 text-[10px] font-medium rounded uppercase ${zoneStyle(sloanLevel)}`}>
                {sloanLevel}
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-zinc-100 my-1">
              {sloan.available ? (sloanVal !== null ? fmtPct(sloanVal * 100, 1) : "0.0%") : "Suppressed"}
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed mt-2">
              {sloan.available
                ? `Evaluates earnings quality vs cash. Growth band (${sloanBand}) threshold: ${sloan.moderateThresholdPct || 10}%.`
                : sloan.reason || "Suppressed for BFSI."}
            </p>
          </div>
          {sloan.available && (
            <div className="mt-3 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-400">
              <span>Growth Adjusted: <strong className="text-zinc-200">{sloan.growthAdjustedThresholdApplied ? "Yes" : "No"}</strong></span>
              <span>Severe Thresh: <strong className="text-zinc-200">{sloan.severeThresholdPct || 25}%</strong></span>
            </div>
          )}
          {sloan.available && (
            <>
              <CalcToggle open={expandedCalc === "sloan"} onClick={() => toggle("sloan")} />
              {expandedCalc === "sloan" && <SloanCalcPanel calc={sloan.calculation} />}
            </>
          )}
        </div>
      </div>

      {/* Forensic Accounting Red Flags Table / List */}
      <div className="bg-[#0c0c0e] border border-zinc-800/80 rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-zinc-800/80">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100 uppercase tracking-wider flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-orange-400" />
              Forensic Accounting Red Flags
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              16-point quantitative audit checking balance sheet integrity, revenue recognition, and capital allocation.
            </p>
          </div>
          <div className="flex items-center gap-1 bg-zinc-900/80 p-1 rounded-md border border-zinc-800 self-start">
            <button
              onClick={() => setFilter("all")}
              className={`px-2.5 py-1 text-xs rounded transition-all ${filter === "all" ? "bg-zinc-800 text-zinc-100 font-medium" : "text-zinc-400 hover:text-zinc-200"}`}
            >
              All Flags ({redFlags.length})
            </button>
            <button
              onClick={() => setFilter("triggered")}
              className={`px-2.5 py-1 text-xs rounded transition-all flex items-center gap-1 ${filter === "triggered" ? "bg-red-950/80 text-red-300 font-medium border border-red-800/60" : "text-zinc-400 hover:text-zinc-200"}`}
            >
              Triggered Only ({triggeredFlags.length})
            </button>
          </div>
        </div>

        {displayedFlags.length === 0 ? (
          <div className="text-center py-8 bg-zinc-900/20 rounded border border-dashed border-zinc-800">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2 opacity-80" />
            <p className="text-sm font-medium text-zinc-300">Clean Forensic Profile</p>
            <p className="text-xs text-zinc-500 mt-1">No quantitative forensic red flags were triggered in this category.</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/60">
            {displayedFlags.map((flag) => {
              const isTrig = flag.triggered;
              const sev = flag.severity || "INFO";
              const badgeClass = isTrig
                ? (sev === "RED" || sev === "CRITICAL" ? "bg-red-950/80 text-red-300 border-red-700/80" : "bg-amber-950/80 text-amber-300 border-amber-700/80")
                : "bg-zinc-900/80 text-zinc-400 border-zinc-800";
              const isExpanded = expandedFlag === flag.id;
              const calc = flag.calculation;

              return (
                <div key={flag.id} className={`py-3.5 transition-colors ${isTrig ? "bg-red-950/5 -mx-2 px-2 rounded" : ""}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      <div className="mt-0.5">
                        {isTrig ? (
                          <AlertTriangle className={`w-4 h-4 ${sev === "RED" || sev === "CRITICAL" ? "text-red-400 animate-pulse" : "text-amber-400"}`} />
                        ) : (
                          <CheckCircle2 className="w-4 h-4 text-emerald-500/70" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-zinc-500">#{flag.id}</span>
                          <h4 className={`text-xs font-semibold ${isTrig ? "text-zinc-100" : "text-zinc-300"}`}>
                            {flag.name}
                          </h4>
                          {flag.sectorOverrideApplied && (
                            <span className="px-1.5 py-0.2 text-[9px] bg-indigo-950/60 text-indigo-300 border border-indigo-800/60 rounded">
                              Sector Override
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
                          {flag.alertString || "No anomaly detected."}
                        </p>

                        {/* Per-flag expandable calculation */}
                        {calc && (
                          <>
                            <button
                              onClick={() => setExpandedFlag(isExpanded ? null : flag.id)}
                              className="mt-2 flex items-center gap-1 text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors font-mono"
                            >
                              {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                              {isExpanded ? "Hide Calculation" : "Show Calculation"}
                            </button>
                            {isExpanded && (
                              <div className="mt-3 bg-zinc-900/60 border border-zinc-800/50 rounded p-3 text-[11px] space-y-2">
                                {/* Formula */}
                                <div>
                                  <span className="text-zinc-500 text-[10px] uppercase tracking-wider font-semibold">Formula</span>
                                  <p className="font-mono text-zinc-300 mt-0.5">{calc.formula}</p>
                                  {calc.formulaSubstituted && (
                                    <p className="font-mono text-indigo-300/80 mt-1.5 text-[10px] bg-indigo-950/20 p-1.5 rounded border border-indigo-900/30">
                                      {calc.formulaSubstituted}
                                    </p>
                                  )}
                                </div>
                                {/* Variables */}
                                {calc.variables && Object.keys(calc.variables).length > 0 && (
                                  <div>
                                    <span className="text-zinc-500 text-[10px] uppercase tracking-wider font-semibold">Computed Values</span>
                                    <div className="grid grid-cols-2 gap-x-4 mt-1 font-mono">
                                      {Object.entries(calc.variables).map(([k, v]) => (
                                        <div key={k} className="flex justify-between py-0.5 border-b border-zinc-800/40">
                                          <span className="text-zinc-500">{k}</span>
                                          <span className="text-zinc-200">{v == null ? "—" : typeof v === "number" ? v.toFixed(typeof v === "number" && Math.abs(v) < 10 ? 4 : 2) : String(v)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {/* Raw values */}
                                {calc.rawValues && Object.keys(calc.rawValues).length > 0 && (
                                  <div>
                                    <span className="text-zinc-500 text-[10px] uppercase tracking-wider font-semibold">Raw Inputs (₹ Cr)</span>
                                    <div className="grid grid-cols-2 gap-x-4 mt-1 font-mono">
                                      {Object.entries(calc.rawValues).map(([k, v]) => (
                                        <div key={k} className="flex justify-between py-0.5 border-b border-zinc-800/40">
                                          <span className="text-zinc-500">{k}</span>
                                          <span className="text-zinc-200">{v == null ? "—" : `₹${Number(v).toLocaleString("en-IN", {maximumFractionDigits: 0})} Cr`}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {/* Threshold & Result */}
                                <div className="pt-1 border-t border-zinc-800/60 space-y-1">
                                  <div className="flex gap-2">
                                    <span className="text-zinc-500 text-[10px] w-16 flex-shrink-0">Threshold</span>
                                    <span className="text-amber-300/80 font-mono text-[10px]">{calc.threshold}</span>
                                  </div>
                                  <div className="flex gap-2">
                                    <span className="text-zinc-500 text-[10px] w-16 flex-shrink-0">Result</span>
                                    <span className={`font-mono font-semibold text-[10px] ${isTrig ? "text-red-300" : "text-emerald-400"}`}>{calc.result} → {isTrig ? "TRIGGERED" : "PASS"}</span>
                                  </div>
                                </div>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex-shrink-0">
                      <span className={`px-2 py-0.5 text-[10px] font-mono font-medium rounded border uppercase ${badgeClass}`}>
                        {isTrig ? sev : "PASS"}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Phase 2 Gap Panel */}
      <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-zinc-400" />
            Phase-2 Qualitative Disclosures & Audit Stubs
          </h4>
          <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
            Annual Report Notes Scope
          </span>
        </div>
        <p className="text-xs text-zinc-400 mb-3">
          The following qualitative audit items require Annual Report footnotes parsing and are excluded from the current quantitative score:
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {phase2Stubs.map((stub, idx) => (
            <div key={idx} className="bg-[#0c0c0e] p-2.5 rounded border border-zinc-800/80 flex flex-col justify-between">
              <span className="text-xs font-medium text-zinc-300">{stub.name}</span>
              <span className="text-[10px] text-zinc-500 mt-2 font-mono">{stub.reason}</span>
            </div>
          ))}
          {phase2Stubs.length === 0 && (
            <div className="col-span-full text-xs text-zinc-500 italic">No Phase-2 stubs registered.</div>
          )}
        </div>
      </div>
    </div>
  );
}
