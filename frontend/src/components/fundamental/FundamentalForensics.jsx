import React, { useState } from "react";
import { ShieldAlert, AlertTriangle, CheckCircle2, Info, HelpCircle, AlertOctagon } from "lucide-react";
import { fmtNum, fmtPct, getVal0, zoneStyle } from "./fundamentalUtils";

export default function FundamentalForensics({ forensics, sectorBucket, gates }) {
  const [filter, setFilter] = useState("all"); // "all" | "triggered"

  if (!forensics) return null;

  const redFlags = forensics.redFlags || [];
  const phase2Stubs = forensics.phase2Stubs || [];
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

  return (
    <div className="space-y-6">
      {/* Three Quantitative Forensic Models Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 1. Beneish M-Score Card */}
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between hover:border-zinc-700/80 transition-all">
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
            <div className="mt-4 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-400">
              <span>Corroborating Flags: <strong className="text-zinc-200">{beneish.corroboratingFlagCount || 0}</strong></span>
              {beneish.escalatedToRed && (
                <span className="text-red-400 font-medium flex items-center gap-1">
                  <AlertOctagon className="w-3 h-3" /> Rule Triggered
                </span>
              )}
            </div>
          )}
        </div>

        {/* 2. Altman Z-Score Card */}
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between hover:border-zinc-700/80 transition-all">
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
          <div className="mt-4 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[10px] text-zinc-500 font-mono">
            <span>MODEL: {altman.modelUsed || altman.model || "N/A"}</span>
            <span>SECTOR: {sectorBucket}</span>
          </div>
        </div>

        {/* 3. Sloan Accrual Ratio Card */}
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-4 flex flex-col justify-between hover:border-zinc-700/80 transition-all">
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
            <div className="mt-4 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-400">
              <span>Growth Adjusted: <strong className="text-zinc-200">{sloan.growthAdjustedThresholdApplied ? "Yes" : "No"}</strong></span>
              <span>Severe Thresh: <strong className="text-zinc-200">{sloan.severeThresholdPct || 25}%</strong></span>
            </div>
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
                ? (sev === "RED" ? "bg-red-950/80 text-red-300 border-red-700/80" : "bg-amber-950/80 text-amber-300 border-amber-700/80")
                : "bg-zinc-900/80 text-zinc-400 border-zinc-800";

              return (
                <div key={flag.id} className={`py-3.5 flex items-start justify-between gap-4 transition-colors ${isTrig ? "bg-red-950/5 -mx-2 px-2 rounded" : ""}`}>
                  <div className="flex items-start gap-3 flex-1">
                    <div className="mt-0.5">
                      {isTrig ? (
                        <AlertTriangle className={`w-4 h-4 ${sev === "RED" ? "text-red-400 animate-pulse" : "text-amber-400"}`} />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500/70" />
                      )}
                    </div>
                    <div>
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
                    </div>
                  </div>
                  <div className="flex-shrink-0">
                    <span className={`px-2 py-0.5 text-[10px] font-mono font-medium rounded border uppercase ${badgeClass}`}>
                      {isTrig ? sev : "PASS"}
                    </span>
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
