import React, { useEffect, useState } from "react";
import axios from "axios";
import {
  ShieldAlert,
  TrendingUp,
  Layers,
  Users,
  FileText,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  BarChart3,
  Award,
  DollarSign,
  Activity,
  Briefcase,
  Sliders,
  AlertOctagon
} from "lucide-react";
import { fmtNum, fmtPct, fmtBig, gradeStyle, pillarColor, getVal0 } from "./fundamental/fundamentalUtils";
import BFSIDeck from "./BFSIDeck";
import FundamentalForensics from "./fundamental/FundamentalForensics";
import FundamentalDuPont from "./fundamental/FundamentalDuPont";
import FundamentalPeers from "./fundamental/FundamentalPeers";
import FundamentalRawData from "./fundamental/FundamentalRawData";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "pillars", label: "10-Pillar Synthesis", icon: BarChart3 },
  { id: "forensics", label: "Forensic Accounting & Distress", icon: ShieldAlert },
  { id: "dupont", label: "DuPont & Capital Allocation", icon: Layers },
  { id: "peers", label: "Peer Benchmarking", icon: Users },
  { id: "raw", label: "Raw Financial Statements", icon: FileText },
];

export default function FundamentalDeck({ symbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("pillars");

  useEffect(() => {
    if (!symbol) return;
    let isMounted = true;
    setLoading(true);
    setError(null);

    axios
      .get(`${API}/stock/${symbol}/fundamentals`)
      .then((res) => {
        if (isMounted) {
          setData(res.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err?.response?.data?.detail || "Failed to fetch fundamental synthesis.");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [symbol]);

  if (loading) {
    return (
      <div className="bg-[#0c0c0e] border border-zinc-800 rounded-lg p-12 flex flex-col items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin mb-4" />
        <span className="text-sm font-mono font-semibold text-zinc-100 mb-2">Downloading & Caching 5-Year Financials for {symbol}...</span>
        <span className="text-xs font-mono text-zinc-400">Saving Balance Sheet, P&L, and Cash Flow locally to disk</span>
        <div className="w-48 h-px bg-zinc-800 my-3"></div>
        <span className="text-xs font-mono text-emerald-400/80">Synthesizing 10-Pillar Ratios & 16-Point Red Flags</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[#0c0c0e] border border-red-900/50 rounded-lg p-8 text-center min-h-[300px] flex flex-col items-center justify-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mb-2" />
        <p className="text-sm font-medium text-red-200">Fundamental Synthesis Failed</p>
        <p className="text-xs font-mono text-red-400 mt-1 max-w-md">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const gates = data.gates || {};
  const meta = data.meta || {};
  const overall = data.overallGrade || {};

  // BFSI entities get the banking-native deck instead of the industrial one.
  if (gates.isBFSI) {
    return <BFSIDeck symbol={symbol} />;
  }

  // Holding Company suppression
  if (gates.isHoldingCompany || !overall.available) {
    return (
      <div className="bg-[#0c0c0e] border border-zinc-800 rounded-lg p-8">
        <div className="bg-amber-950/40 border border-amber-600/50 rounded-lg p-6 flex flex-col md:flex-row items-start gap-4">
          <div className="p-3 bg-amber-900/40 rounded-full text-amber-400 flex-shrink-0">
            <AlertOctagon className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-amber-900/80 text-amber-200 border border-amber-700">
                Holding Company Gate
              </span>
              <h3 className="text-base font-bold text-zinc-100">{meta.companyName || symbol}</h3>
            </div>
            <p className="text-sm text-amber-200/90 leading-relaxed mt-2">
              <strong>Fundamental Synthesis Suppressed:</strong> Standard industrial accounting ratios, working capital cycles, and distress models (Altman Z-Score, Beneish M-Score, Sloan Accrual) do not apply to Holding Companies & Conglomerates.
            </p>
            <p className="text-xs text-zinc-400 mt-2">
              Evaluating holding structures via standard manufacturing debt-to-equity and operating cash flow metrics creates distortive false-positive red flags. Please refer to sector-specific valuation panels or quarterly disclosures.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const letter = overall.letterGrade || "C";
  const gStyle = gradeStyle(letter);
  const wBreakdown = overall.weightingBreakdown || [];

  // Map subscore from weighting breakdown
  const getSubScore = (pillarName) => {
    const found = wBreakdown.find((b) => b.pillar === pillarName);
    return found ? found.subScore : null;
  };
  const getWeight = (pillarName) => {
    const found = wBreakdown.find((b) => b.pillar === pillarName);
    return found ? { active: found.activeWeight, raw: found.rawWeight, renorm: found.renormalized } : { active: 0, raw: 0, renorm: false };
  };

  return (
    <div className="bg-[#0c0c0e] border border-zinc-800 rounded-lg shadow-xl overflow-hidden my-4" data-testid="fundamental-deck">
      {/* 1. Executive Banner */}
      <div className={`p-6 border-b ${gStyle.border} ${gStyle.bg} transition-all`}>
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="flex items-start sm:items-center gap-5">
            {/* Letter Grade Pill */}
            <div className={`w-20 h-20 rounded-2xl border flex flex-col items-center justify-center flex-shrink-0 ${gStyle.badge} ${gStyle.glow}`}>
              <span className="text-3xl font-black tracking-tight">{letter}</span>
              <span className="text-[10px] font-mono opacity-80 mt-0.5">GRADE</span>
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="text-[11px] font-mono tracking-widest uppercase text-zinc-400">
                  {meta.sectorBucket || meta.yahooSector || "Industrial"}
                </span>
                <span className="text-zinc-600">•</span>
                <span className="text-xs font-mono font-bold text-zinc-200">
                  Score: {fmtNum(overall.overallGrade, 1)} / 100
                </span>
                {overall.renormalizationApplied && (
                  <span className="px-2 py-0.5 text-[9px] font-semibold uppercase rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                    Weights Renormalized
                  </span>
                )}
              </div>
              <h2 className="text-lg sm:text-xl font-bold text-zinc-100 tracking-tight">
                {meta.companyName || symbol} ({symbol})
              </h2>
              <p className="text-xs sm:text-sm text-zinc-300 leading-relaxed mt-1.5 max-w-3xl">
                {overall.verdictSentence || "A comprehensive 10-pillar accounting and valuation synthesis."}
              </p>
            </div>
          </div>

          {/* Quick Metrics Badges */}
          <div className="flex flex-wrap lg:flex-col items-start lg:items-end gap-2 text-xs font-mono self-stretch lg:self-auto justify-end border-t lg:border-t-0 pt-4 lg:pt-0 border-zinc-800/80">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-900/80 border border-zinc-800 text-zinc-300">
              <ShieldAlert className={`w-3.5 h-3.5 ${overall.redFlagCount > 0 ? "text-red-400 animate-pulse" : "text-emerald-400"}`} />
              <span>Red Flags: <strong className={overall.redFlagCount > 0 ? "text-red-400" : "text-emerald-400"}>{overall.redFlagCount || 0}</strong></span>
            </div>
            {overall.weakestPillar && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-900/80 border border-zinc-800 text-zinc-400">
                <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
                <span>Weakest Pillar: <strong className="text-amber-300 uppercase">{overall.weakestPillar}</strong></span>
              </div>
            )}
            <div className="text-[10px] text-zinc-500">
              Data: {meta.currencyUnit || "₹ Cr"} • Updated {meta.dataAsOf ? meta.dataAsOf.slice(0, 10) : "Today"}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Sleek Institutional Tab Bar */}
      <div className="flex items-center gap-1 px-4 pt-3 bg-zinc-950/80 border-b border-zinc-800/80 overflow-x-auto scrollbar-none">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                active
                  ? "border-emerald-500 text-emerald-400 bg-zinc-900/60"
                  : "border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${active ? "text-emerald-400" : "text-zinc-500"}`} />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* 3. Tab Content Area */}
      <div className="p-6">
        {activeTab === "pillars" && (
          <div className="space-y-6">
            {/* 9 Cards Grid (8 Scored Pillars + 1 Excluded Valuation Card) */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* 1. Forensics Card */}
              <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                      <ShieldAlert className="w-3.5 h-3.5 text-orange-400" /> Forensics & Red Flags
                    </span>
                    <span className={`text-base font-mono font-bold ${pillarColor(getSubScore("forensics"))}`}>
                      {getSubScore("forensics") ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-400">
                    <div className="flex justify-between"><span>Beneish M-Score:</span> <strong className="text-zinc-200">{getVal0(data.forensics?.beneish?.mScore) ? fmtNum(getVal0(data.forensics?.beneish?.mScore), 2) : "Clean"}</strong></div>
                    <div className="flex justify-between"><span>Altman Z-Zone:</span> <strong className="text-zinc-200">{getVal0(data.forensics?.altmanZ?.zone) || "Safe"}</strong></div>
                    <div className="flex justify-between"><span>Sloan Accrual:</span> <strong className="text-zinc-200">{getVal0(data.forensics?.sloanAccrual?.accrualRatio) ? fmtPct(getVal0(data.forensics?.sloanAccrual?.accrualRatio) * 100, 1) : "0%"}</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-zinc-800/60 flex justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Weight: {getWeight("forensics").active}%</span>
                  <span>16-Point Quantitative Engine</span>
                </div>
              </div>

              {/* 2. Cash Flow Card */}
              <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 text-emerald-400" /> Cash Flow Quality
                    </span>
                    <span className={`text-base font-mono font-bold ${pillarColor(getSubScore("cashFlow"))}`}>
                      {getSubScore("cashFlow") ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-400">
                    <div className="flex justify-between"><span>OCF (Latest):</span> <strong className="text-zinc-200">{fmtBig(getVal0(data.cashFlow?.ocfQuality?.ocf))}</strong></div>
                    <div className="flex justify-between"><span>Free Cash Flow:</span> <strong className="text-zinc-200">{fmtBig(getVal0(data.cashFlow?.ocfQuality?.fcf))}</strong></div>
                    <div className="flex justify-between"><span>CapEx / Deprec:</span> <strong className="text-zinc-200">{fmtNum(getVal0(data.cashFlow?.capex?.capexToDepreciation), 1)}×</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-zinc-800/60 flex justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Weight: {getWeight("cashFlow").active}%</span>
                  <span>Self-Sufficiency & OCF/EBITDA</span>
                </div>
              </div>

              {/* 3. Profitability Card */}
              <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                      <TrendingUp className="w-3.5 h-3.5 text-cyan-400" /> Profitability & Returns
                    </span>
                    <span className={`text-base font-mono font-bold ${pillarColor(getSubScore("profitability"))}`}>
                      {getSubScore("profitability") ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-400">
                    <div className="flex justify-between"><span>ROIC vs WACC:</span> <strong className="text-emerald-400">{fmtNum(getVal0(data.profitability?.returns?.roic), 1)}% vs {fmtNum(getVal0(data.profitability?.returns?.wacc), 1)}%</strong></div>
                    <div className="flex justify-between"><span>Return on Equity:</span> <strong className="text-zinc-200">{fmtPct(getVal0(data.profitability?.returns?.roe) * 100, 1)}</strong></div>
                    <div className="flex justify-between"><span>Net Profit Margin:</span> <strong className="text-zinc-200">{fmtPct(getVal0(data.profitability?.dupont3Factor?.netMargin) * 100, 1)}</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-zinc-800/60 flex justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Weight: {getWeight("profitability").active}%</span>
                  <span>DuPont & Capital Allocation</span>
                </div>
              </div>

              {/* 4. Solvency Card */}
              <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                      <Briefcase className="w-3.5 h-3.5 text-indigo-400" /> Liquidity & Solvency
                    </span>
                    <span className={`text-base font-mono font-bold ${pillarColor(getSubScore("solvency"))}`}>
                      {getSubScore("solvency") ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-400">
                    <div className="flex justify-between"><span>Net Debt / EBITDA:</span> <strong className="text-zinc-200">{fmtNum(getVal0(data.solvency?.netDebtToEbitda?.reported), 2)}×</strong></div>
                    <div className="flex justify-between"><span>Interest Coverage:</span> <strong className="text-zinc-200">{fmtNum(getVal0(data.solvency?.interestCoverage?.reported), 1)}×</strong></div>
                    <div className="flex justify-between"><span>Current Ratio:</span> <strong className="text-zinc-200">{fmtNum(getVal0(data.solvency?.currentRatio), 2)}</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-zinc-800/60 flex justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Weight: {getWeight("solvency").active}%</span>
                  <span>Lease & Contingent Ratios</span>
                </div>
              </div>

              {/* 5. Income Statement Card */}
              <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-amber-400" /> Income Statement
                    </span>
                    <span className={`text-base font-mono font-bold ${pillarColor(getSubScore("incomeStatement"))}`}>
                      {getSubScore("incomeStatement") ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-400">
                    <div className="flex justify-between"><span>Revenue (TT/FY1):</span> <strong className="text-zinc-200">{fmtBig(getVal0(data.incomeStatement?.totalRevenue))}</strong></div>
                    <div className="flex justify-between"><span>EBITDA Margin:</span> <strong className="text-zinc-200">{fmtPct(getVal0(data.incomeStatement?.ebitdaMarginPct), 1)}</strong></div>
                    <div className="flex justify-between"><span>3Y EPS CAGR:</span> <strong className="text-zinc-200">{fmtPct(data.incomeStatement?.eps3yCagr, 1)}</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-zinc-800/60 flex justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Weight: {getWeight("incomeStatement").active}%</span>
                  <span>Margin Cascade & Growth</span>
                </div>
              </div>

              {/* 6. Growth Card */}
              <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> Growth & Quality
                    </span>
                    <span className={`text-base font-mono font-bold ${pillarColor(getSubScore("growth"))}`}>
                      {getSubScore("growth") ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-400">
                    <div className="flex justify-between"><span>3Y Revenue CAGR:</span> <strong className="text-zinc-200">{fmtPct(data.incomeStatement?.revenue3yCagr, 1)}</strong></div>
                    <div className="flex justify-between"><span>5Y Revenue CAGR:</span> <strong className="text-zinc-200">{fmtPct(data.incomeStatement?.revenue5yCagr, 1)}</strong></div>
                    <div className="flex justify-between"><span>EPS / Rev Divergence:</span> <strong className="text-zinc-200">{fmtNum(data.incomeStatement?.epsVsRevCagrDivergence, 1)}%</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-zinc-800/60 flex justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Weight: {getWeight("growth").active}%</span>
                  <span>Sustainable Growth Rate</span>
                </div>
              </div>

              {/* 7. Balance Sheet Card */}
              <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                      <Briefcase className="w-3.5 h-3.5 text-cyan-400" /> Balance Sheet Health
                    </span>
                    <span className={`text-base font-mono font-bold ${pillarColor(getSubScore("balanceSheet"))}`}>
                      {getSubScore("balanceSheet") ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-400">
                    <div className="flex justify-between"><span>Total Assets:</span> <strong className="text-zinc-200">{fmtBig(getVal0(data.balanceSheet?.assets?.totalAssets))}</strong></div>
                    <div className="flex justify-between"><span>Cash % of Assets:</span> <strong className="text-zinc-200">{fmtPct(getVal0(data.balanceSheet?.assets?.cashPctOfAssets), 1)}</strong></div>
                    <div className="flex justify-between"><span>Book Value / Share:</span> <strong className="text-zinc-200">₹{fmtNum(getVal0(data.balanceSheet?.bookValue?.bvps), 1)}</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-zinc-800/60 flex justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Weight: {getWeight("balanceSheet").active}%</span>
                  <span>Asset Mix & Working Cap</span>
                </div>
              </div>

              {/* 8. Efficiency Card */}
              <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                    <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                      <Sliders className="w-3.5 h-3.5 text-indigo-400" /> Efficiency & Activity
                    </span>
                    <span className={`text-base font-mono font-bold ${pillarColor(getSubScore("efficiency"))}`}>
                      {getSubScore("efficiency") ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-400">
                    <div className="flex justify-between"><span>Cash Conversion (CCC):</span> <strong className="text-zinc-200">{fmtNum(getVal0(data.balanceSheet?.workingCapital?.ccc), 1)} days</strong></div>
                    <div className="flex justify-between"><span>Days Sales Out (DSO):</span> <strong className="text-zinc-200">{fmtNum(getVal0(data.balanceSheet?.assets?.dso), 1)} days</strong></div>
                    <div className="flex justify-between"><span>Asset Turnover:</span> <strong className="text-zinc-200">{fmtNum(getVal0(data.profitability?.dupont3Factor?.assetTurnover), 2)}×</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-zinc-800/60 flex justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Weight: {getWeight("efficiency").active}%</span>
                  <span>Working Capital Cycles</span>
                </div>
              </div>

              {/* 9. Valuation Card (Deliberately Excluded from Overall Grade) */}
              <div className="bg-gradient-to-br from-zinc-900/80 via-zinc-900/40 to-indigo-950/20 border border-indigo-500/30 rounded-lg p-4 hover:border-indigo-500/50 transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-indigo-900/40">
                    <span className="text-xs font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
                      <DollarSign className="w-3.5 h-3.5 text-indigo-400" /> Valuation & Multiples
                    </span>
                    <span className="px-2 py-0.5 text-[9px] font-semibold bg-indigo-950 text-indigo-300 border border-indigo-800 rounded">
                      EXCLUDED FROM GRADE
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs font-mono text-zinc-300">
                    <div className="flex justify-between"><span>P/E Ratio (TTM):</span> <strong>{fmtNum(getVal0(data.valuation?.peRatio), 2)}×</strong></div>
                    <div className="flex justify-between"><span>EV / EBITDA:</span> <strong>{fmtNum(getVal0(data.valuation?.evToEbitda), 2)}×</strong></div>
                    <div className="flex justify-between"><span>Price / Book (P/B):</span> <strong>{fmtNum(getVal0(data.valuation?.pbRatio), 2)}×</strong></div>
                    <div className="flex justify-between"><span>FCF Yield:</span> <strong className="text-emerald-400">{fmtPct(getVal0(data.valuation?.fcfYieldPct), 1)}</strong></div>
                  </div>
                </div>
                <div className="mt-4 pt-2 border-t border-indigo-900/40 text-[10px] text-indigo-400/80 italic font-sans">
                  * Deliberately excluded from overallGrade to separate fundamental quality from market pricing (Design Principle 4).
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "forensics" && (
          <FundamentalForensics forensics={data.forensics} sectorBucket={meta.sectorBucket} gates={gates} />
        )}

        {activeTab === "dupont" && (
          <FundamentalDuPont profitability={data.profitability} meta={meta} />
        )}

        {activeTab === "peers" && (
          <FundamentalPeers peerBenchmark={data.peerBenchmark} meta={meta} />
        )}

        {activeTab === "raw" && (
          <FundamentalRawData
            incomeStatement={data.incomeStatement}
            balanceSheet={data.balanceSheet}
            cashFlow={data.cashFlow}
            meta={meta}
          />
        )}
      </div>
    </div>
  );
}
