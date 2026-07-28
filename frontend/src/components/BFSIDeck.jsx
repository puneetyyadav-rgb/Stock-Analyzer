import React, { useEffect, useState } from "react";
import axios from "axios";
import {
  ShieldAlert,
  TrendingUp,
  Landmark,
  Coins,
  PiggyBank,
  ShieldCheck,
  Activity,
  Users,
  AlertOctagon,
  Loader2,
  AlertTriangle,
  BarChart3,
  Info,
} from "lucide-react";
import { fmtNum, gradeStyle, pillarColor } from "./fundamental/fundamentalUtils";
import BFSIAssetQuality from "./bfsi/BFSIAssetQuality";
import BFSIProfitability from "./bfsi/BFSIProfitability";
import BFSIDepositFranchise from "./bfsi/BFSIDepositFranchise";
import BFSICapitalAdequacy from "./bfsi/BFSICapitalAdequacy";
import BFSIGrowth from "./bfsi/BFSIGrowth";
import BFSIPeers from "./bfsi/BFSIPeers";
import BFSIRedFlags from "./bfsi/BFSIRedFlags";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "overview", label: "BFSI Overview", icon: BarChart3 },
  { id: "asset", label: "Asset Quality", icon: ShieldAlert },
  { id: "nim", label: "NIM & Profitability", icon: Coins },
  { id: "deposit", label: "Deposit & Funding", icon: PiggyBank },
  { id: "capital", label: "Capital & Liquidity", icon: ShieldCheck },
  { id: "growth", label: "Growth & Peers", icon: TrendingUp },
  { id: "flags", label: "Banking Red Flags", icon: AlertOctagon },
];

const SUB_LABEL = {
  PSU_BANK: "PSU BANK",
  PRIVATE_BANK: "PRIVATE BANK",
  SFB: "SMALL FINANCE BANK",
  NBFC_HOUSING: "NBFC · HOUSING",
  NBFC_GOLD: "NBFC · GOLD LOAN",
  NBFC_MFI: "NBFC · MFI",
  NBFC_VEHICLE: "NBFC · VEHICLE/DIVERSE",
  INSURANCE_LIFE: "LIFE INSURANCE",
  INSURANCE_GENERAL: "GENERAL INSURANCE",
  FINTECH: "FINTECH",
};

export default function BFSIDeck({ symbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [showGap, setShowGap] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    let isMounted = true;
    setLoading(true);
    setError(null);
    axios
      .get(`${API}/stock/${symbol}/bfsi-analysis`)
      .then((res) => {
        if (isMounted) {
          setData(res.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err?.response?.data?.detail || "Failed to fetch BFSI analysis.");
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
        <span className="text-sm font-mono font-semibold text-zinc-100 mb-2">Building BFSI Scorecard for {symbol}...</span>
        <span className="text-xs font-mono text-zinc-400">Classifying sub-sector & computing banking-native pillars</span>
        <div className="w-48 h-px bg-zinc-800 my-3"></div>
        <span className="text-xs font-mono text-emerald-400/80">NIM · RoA · Capital · Liquidity · 16 Banking Red Flags</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[#0c0c0e] border border-red-900/50 rounded-lg p-8 text-center min-h-[300px] flex flex-col items-center justify-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mb-2" />
        <p className="text-sm font-medium text-red-200">BFSI Analysis Failed</p>
        <p className="text-xs font-mono text-red-400 mt-1 max-w-md">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const meta = data.meta || {};
  const overall = data.overallGrade || {};
  const phase2 = data.phase2Stubs || {};
  const gapCount = meta.phase2GapCount || Object.keys(phase2).length;

  const letter = overall.letterGrade || "C";
  const gStyle = gradeStyle(letter);
  const wBreakdown = overall.weightingBreakdown || [];
  const getSub = (name) => {
    const f = wBreakdown.find((b) => b.pillar === name);
    return f ? f.subScore : null;
  };
  const subLabel = SUB_LABEL[meta.bfsiSubSector] || meta.bfsiSubSector || "BFSI";

  const overviewCards = [
    { key: "assetQuality", label: "Asset Quality", icon: ShieldAlert, color: "text-orange-400", hint: "GNPA/PCR are Phase-2 regulatory stubs" },
    { key: "nimProfitability", label: "NIM & Profitability", icon: Coins, color: "text-emerald-400", hint: `RoA ${fmtNum(data.nimProfitability?.roa_pct, 2)}% · RoE ${fmtNum(data.nimProfitability?.roe_pct, 1)}%` },
    { key: "depositFranchise", label: "Deposit Franchise", icon: PiggyBank, color: "text-cyan-400", hint: "CASA is a Phase-2 stub" },
    { key: "capitalAdequacy", label: "Capital Adequacy", icon: ShieldCheck, color: "text-indigo-400", hint: `Equity/Assets ${fmtNum(data.capitalAdequacy?.equityToTotalAssets_pct, 1)}%` },
    { key: "liquidityManagement", label: "Liquidity", icon: Activity, color: "text-teal-400", hint: `LDR ${fmtNum(data.liquidityManagement?.loanToDepositRatio_pct, 0)}%` },
    { key: "loanBookGrowth", label: "Loan Book Growth", icon: TrendingUp, color: "text-amber-400", hint: `1Y ${fmtNum(data.loanBookGrowth?.loanBookGrowth1Y_pct, 1)}%` },
  ];

  return (
    <div className="bg-[#0c0c0e] border border-zinc-800 rounded-lg shadow-xl overflow-hidden my-4" data-testid="bfsi-deck">
      {/* Executive Banner */}
      <div className={`p-6 border-b ${gStyle.border} ${gStyle.bg} transition-all`}>
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="flex items-start sm:items-center gap-5">
            <div className={`w-20 h-20 rounded-2xl border flex flex-col items-center justify-center flex-shrink-0 ${gStyle.badge} ${gStyle.glow}`}>
              <span className="text-3xl font-black tracking-tight">{overall.available ? letter : "—"}</span>
              <span className="text-[10px] font-mono opacity-80 mt-0.5">GRADE</span>
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-indigo-950 text-indigo-300 border border-indigo-800 flex items-center gap-1">
                  <Landmark className="w-3 h-3" /> {subLabel}
                </span>
                <span className="text-zinc-600">•</span>
                <span className="text-xs font-mono font-bold text-zinc-200">
                  Score: {overall.available ? `${fmtNum(overall.overallScore, 1)} / 100` : "N/A"}
                </span>
                {overall.coveragePct != null && (
                  <span className="px-2 py-0.5 text-[9px] font-semibold uppercase rounded bg-teal-950 text-teal-300 border border-teal-800">
                    Coverage {fmtNum(overall.coveragePct, 0)}%
                  </span>
                )}
              </div>
              <h2 className="text-lg sm:text-xl font-bold text-zinc-100 tracking-tight">
                {meta.companyName || symbol} ({symbol})
              </h2>
              <p className="text-xs sm:text-sm text-zinc-300 leading-relaxed mt-1.5 max-w-3xl">
                {overall.verdictSentence || "Banking-native fundamental synthesis across asset quality, NIM, capital, liquidity and growth."}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap lg:flex-col items-start lg:items-end gap-2 text-xs font-mono self-stretch lg:self-auto justify-end border-t lg:border-t-0 pt-4 lg:pt-0 border-zinc-800/80">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-900/80 border border-zinc-800 text-zinc-300">
              <ShieldAlert className={`w-3.5 h-3.5 ${overall.redFlagCount > 0 ? "text-red-400 animate-pulse" : "text-emerald-400"}`} />
              <span>Red Flags: <strong className={overall.redFlagCount > 0 ? "text-red-400" : "text-emerald-400"}>{overall.redFlagCount || 0}</strong></span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-950/60 border border-amber-800/60 text-amber-300">
              <Info className="w-3.5 h-3.5" />
              <span>Phase-2 Data Gaps: <strong>{gapCount}</strong></span>
            </div>
            <div className="text-[10px] text-zinc-500">
              Data: {meta.currencyUnit || "₹ Cr"} • Updated {meta.dataAsOf ? meta.dataAsOf.slice(0, 10) : "Today"}
            </div>
          </div>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="flex items-center gap-1 px-4 pt-3 bg-zinc-950/80 border-b border-zinc-800/80 overflow-x-auto scrollbar-none">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                active ? "border-emerald-500 text-emerald-400 bg-zinc-900/60" : "border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${active ? "text-emerald-400" : "text-zinc-500"}`} />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* Phase-2 Data Gap Panel (always visible, collapsible) */}
      <div className="px-6 pt-4">
        <div className="border border-amber-800/50 bg-amber-950/30 rounded-lg">
          <button onClick={() => setShowGap((s) => !s)} className="w-full flex items-center justify-between px-4 py-2.5 text-left">
            <span className="text-xs font-semibold text-amber-300 flex items-center gap-2">
              <Info className="w-3.5 h-3.5" /> Phase-2 Regulatory Data Not in Public Feed ({gapCount} metrics) — GNPA/NNPA/PCR/CRAR/CASA/LCR/VNB/EV require quarterly filings, RBI Pillar 3 & IRDAI disclosures
            </span>
            <span className="text-[10px] font-mono text-amber-400/80">{showGap ? "Hide" : "Show"}</span>
          </button>
          {showGap && (
            <div className="px-4 pb-3 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1">
              {Object.entries(phase2).map(([k, v]) => (
                <div key={k} className="text-[11px] font-mono text-amber-200/80 flex justify-between gap-3 border-b border-amber-900/30 py-1">
                  <span className="text-amber-300/90">{k}</span>
                  <span className="text-zinc-500 text-right">{v?.reason || "Phase 2"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {activeTab === "overview" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {overviewCards.map((c) => {
              const Icon = c.icon;
              const sub = getSub(c.key);
              return (
                <div key={c.key} className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4 hover:border-zinc-700/80 transition-all flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2 pb-2 border-b border-zinc-800/60">
                      <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                        <Icon className={`w-3.5 h-3.5 ${c.color}`} /> {c.label}
                      </span>
                      <span className={`text-base font-mono font-bold ${pillarColor(sub)}`}>
                        {sub ?? "—"} <span className="text-xs text-zinc-500">/100</span>
                      </span>
                    </div>
                    <p className="text-[11px] font-mono text-zinc-400">{c.hint}</p>
                  </div>
                  <div className="mt-4 pt-2 border-t border-zinc-800/60 text-[10px] text-zinc-500 font-mono">
                    {sub == null ? "Not scored from public feed (Phase-2)" : `Weight (renormalized): ${fmtNum((wBreakdown.find(b => b.pillar === c.key)?.normalizedWeight) ?? 0, 0)}%`}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {activeTab === "asset" && <BFSIAssetQuality data={data.assetQuality} />}
        {activeTab === "nim" && <BFSIProfitability data={data.nimProfitability} />}
        {activeTab === "deposit" && <BFSIDepositFranchise data={data.depositFranchise} />}
        {activeTab === "capital" && <BFSICapitalAdequacy capital={data.capitalAdequacy} liquidity={data.liquidityManagement} />}
        {activeTab === "growth" && (
          <div className="space-y-6">
            <BFSIGrowth data={data.loanBookGrowth} />
            <BFSIPeers data={data.bfsiPeerBenchmark} />
          </div>
        )}
        {activeTab === "flags" && <BFSIRedFlags data={data.bfsiRedFlags} />}
      </div>
    </div>
  );
}
