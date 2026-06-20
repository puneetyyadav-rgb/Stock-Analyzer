import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Sparkles, Loader2, AlertCircle } from "lucide-react";
import { getAIVerdict } from "../lib/api";
import { DisclaimerNote } from "./Disclaimer";

const verdictColors = {
  "STRONG BUY": "bg-emerald-500 text-emerald-950",
  "BUY": "bg-emerald-700 text-emerald-50",
  "HOLD": "bg-amber-600 text-amber-50",
  "SELL": "bg-red-700 text-red-50",
  "STRONG SELL": "bg-red-500 text-red-950",
};

export default function AIVerdict({ symbol }) {
  const [verdict, setVerdict] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setVerdict(null);
    setErr(null);
  }, [symbol]);

  const run = async () => {
    setLoading(true);
    setErr(null);
    try {
      const r = await getAIVerdict(symbol);
      if (r.error) setErr(r.error);
      else setVerdict(r);
    } catch (e) {
      setErr(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel
      title="AI Verdict (Gemini 3 Flash)"
      testId="ai-verdict-panel"
      right={
        <button
          onClick={run}
          disabled={loading}
          data-testid="generate-verdict-btn"
          className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] tracking-widest uppercase font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
          {loading ? "Analyzing 9 Factors…" : verdict ? "Re-Analyze" : "Generate Verdict"}
        </button>
      }
    >
      {!verdict && !loading && !err && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <Sparkles size={28} className="text-blue-500 mb-3" />
          <p className="text-sm text-zinc-400 max-w-md">
            Click <span className="font-mono text-zinc-200">Generate Verdict</span> to run AI analysis across all 9 factors:
            macro, sector, fundamentals, technicals, news, sentiment, regulatory & management commentary.
          </p>
        </div>
      )}
      {loading && (
        <div className="flex items-center justify-center py-10 gap-2 text-zinc-400">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-xs tracking-widest uppercase">Synthesizing across data points…</span>
        </div>
      )}
      {err && (
        <div className="flex items-start gap-2 p-3 bg-red-950/40 border border-red-900/60 text-red-300 text-xs">
          <AlertCircle size={14} /> <span>{err}</span>
        </div>
      )}
      {verdict && !verdict.error && (
        <div className="space-y-3" data-testid="ai-verdict-content">
          <div className="flex flex-wrap items-center gap-3 pb-3 border-b border-zinc-800">
            <div className={`px-3 py-1 text-xs font-bold tracking-widest uppercase ${verdictColors[verdict.verdict] || "bg-zinc-700 text-zinc-100"}`}>
              {verdict.verdict}
            </div>
            <div className="text-[10px] tracking-widest uppercase text-zinc-500">
              Confidence: <span className="text-zinc-200 font-mono">{verdict.confidence}%</span>
            </div>
            <div className="text-[10px] tracking-widest uppercase text-zinc-500">
              Horizon: <span className="text-zinc-200">{verdict.timeHorizon}</span>
            </div>
            {verdict.analysisAsOf && (
              <div className="text-[10px] tracking-widest uppercase text-zinc-500">
                Analysis as of: <span className="text-blue-300 font-mono">{verdict.analysisAsOf}</span>
              </div>
            )}
            {verdict.targetPrice && (
              <div className="text-[10px] tracking-widest uppercase text-zinc-500">
                Target: <span className="text-emerald-400 font-mono">₹{Number(verdict.targetPrice).toFixed(2)}</span>
              </div>
            )}
            {verdict.sectorBucket && verdict.sectorBucket !== "Other" && (
              <div className="text-[10px] tracking-widest uppercase text-zinc-500">
                Sector lens: <span className="text-blue-400">{verdict.sectorBucket}</span>
              </div>
            )}
          </div>

          <DisclaimerNote className="bg-amber-950/30 border border-amber-900/40 px-2 py-1" />

          <p className="text-sm text-zinc-300 leading-relaxed">{verdict.summary}</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <h4 className="text-[10px] tracking-widest uppercase text-emerald-400 mb-1.5">Bull Case</h4>
              <ul className="space-y-1">
                {(verdict.bullCase || []).map((b, i) => (
                  <li key={i} className="text-xs text-zinc-300 flex gap-2"><span className="text-emerald-500">▲</span>{b}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-[10px] tracking-widest uppercase text-red-400 mb-1.5">Bear Case</h4>
              <ul className="space-y-1">
                {(verdict.bearCase || []).map((b, i) => (
                  <li key={i} className="text-xs text-zinc-300 flex gap-2"><span className="text-red-500">▼</span>{b}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-[10px] tracking-widest uppercase text-amber-400 mb-1.5">Key Risks</h4>
              <ul className="space-y-1">
                {(verdict.keyRisks || []).map((b, i) => (
                  <li key={i} className="text-xs text-zinc-300 flex gap-2"><span className="text-amber-500">⚠</span>{b}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-[10px] tracking-widest uppercase text-blue-400 mb-1.5">Catalysts</h4>
              <ul className="space-y-1">
                {(verdict.catalysts || []).map((b, i) => (
                  <li key={i} className="text-xs text-zinc-300 flex gap-2"><span className="text-blue-500">●</span>{b}</li>
                ))}
              </ul>
            </div>
          </div>

          {verdict.factorAnalysis && (
            <div className="border-t border-zinc-800 pt-3">
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-2">9-Factor Breakdown</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {Object.entries(verdict.factorAnalysis).map(([k, v]) => (
                  <div key={k} className="border border-zinc-800/50 p-2 bg-zinc-900/30">
                    <div className="text-[10px] tracking-widest uppercase text-zinc-500 mb-1">{k}</div>
                    <div className="text-xs text-zinc-300 leading-snug">{v}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {verdict.sectorSpecific && verdict.sectorSpecific.length > 0 && (
            <div className="border-t border-zinc-800 pt-3" data-testid="sector-specific-section">
              <h4 className="text-[10px] tracking-widest uppercase text-blue-400 mb-2">
                Sector-Specific Factors ({verdict.sectorBucket})
              </h4>
              <ul className="space-y-1.5">
                {verdict.sectorSpecific.map((s, i) => (
                  <li key={i} className={`border-l-2 ${s.dataAvailable ? "border-blue-700/60" : "border-zinc-700"} pl-2 py-1 bg-zinc-900/30`}>
                    <div className="text-[11px] font-medium text-zinc-200">{s.factor}</div>
                    <div className="text-[11px] text-zinc-400 leading-snug">{s.assessment}</div>
                    {!s.dataAvailable && (
                      <span className="text-[9px] tracking-widest uppercase text-amber-400">No data available</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
