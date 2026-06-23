import React, { useState, useEffect } from "react";
import { Panel } from "./Panel";
import { getAIRatios } from "../lib/api";
import { Loader2, AlertCircle, RefreshCw, Activity, AlertTriangle, Scale, Target } from "lucide-react";

export default function AIRatioAnalysisPanel({ symbol, pdfData }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [started, setStarted] = useState(false);

  const fetchData = async (force = false) => {
    if (!symbol) return;
    setStarted(true);
    setLoading(true);
    setErr(null);
    try {
      const result = await getAIRatios(symbol, force, pdfData);
      if (result && result.error) {
        setErr(result.error);
      } else {
        setData(result);
      }
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Failed to generate AI Ratio Analysis");
    } finally {
      setLoading(false);
    }
  };

  // Removed useEffect auto-fetch to prevent rate limits
  // Analysis only starts when user clicks the button

  const handleRefresh = () => {
    fetchData(true);
  };

  if (!symbol) return null;

  return (
    <Panel 
      title={`AI Fundamental Ratio Synthesis · ${symbol}`} 
      testId="ai-ratio-panel"
      headerRight={
        <button 
          onClick={handleRefresh}
          disabled={loading}
          className="text-zinc-500 hover:text-zinc-300 disabled:opacity-50 transition-colors"
          title="Refresh Analysis"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      }
    >
      {!started && !data && !loading && !err && (
        <div className="flex flex-col items-center justify-center py-12 text-center border border-dashed border-zinc-800 rounded-lg bg-zinc-900/20">
          <Activity className="text-zinc-500 mb-3" size={32} />
          <h3 className="text-sm font-medium text-zinc-300 mb-1">AI Ratio Synthesis</h3>
          <p className="text-xs text-zinc-500 max-w-xs mb-4">
            Generate a comprehensive AI synthesis of fundamental ratios and peer comparisons.
          </p>
          <button
            onClick={() => fetchData(false)}
            className="px-4 py-2 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-sm transition-colors"
          >
            Start Analysis
          </button>
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center justify-center py-10 text-zinc-500 gap-2">
          <Loader2 className="animate-spin" size={16} />
          <span className="text-xs uppercase tracking-widest">Synthesizing Ratios...</span>
        </div>
      )}

      {err && (
        <div className="p-3 bg-red-950/30 border border-red-900/50 text-red-400 text-xs flex items-start gap-2">
          <AlertCircle size={14} className="shrink-0 mt-0.5" />
          <p>{err}</p>
        </div>
      )}

      {data && (
        <div className="space-y-6">
          {/* Top Synthesis */}
          {data.synthesis && (
            <div className={`p-4 border ${
              data.synthesis.view === "Bullish" ? "bg-emerald-950/10 border-emerald-900/30" :
              data.synthesis.view === "Bearish" ? "bg-red-950/10 border-red-900/30" :
              "bg-amber-950/10 border-amber-900/30"
            }`}>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                  <Activity size={16} className={
                    data.synthesis.view === "Bullish" ? "text-emerald-400" :
                    data.synthesis.view === "Bearish" ? "text-red-400" : "text-amber-400"
                  } />
                  Master Synthesis
                </h3>
                <div className="flex gap-2">
                  <span className={`px-2 py-0.5 text-[10px] tracking-widest uppercase border ${
                    data.synthesis.view === "Bullish" ? "bg-emerald-950/40 text-emerald-400 border-emerald-900/50" :
                    data.synthesis.view === "Bearish" ? "bg-red-950/40 text-red-400 border-red-900/50" :
                    "bg-amber-950/30 text-amber-400 border-amber-900/50"
                  }`}>
                    {data.synthesis.view}
                  </span>
                  <span className="px-2 py-0.5 text-[10px] tracking-widest uppercase bg-zinc-900 text-zinc-400 border border-zinc-700">
                    {data.synthesis.conviction} Conviction
                  </span>
                </div>
              </div>
              <p className="text-sm text-zinc-300 leading-relaxed mb-3">
                {data.synthesis.narrative}
              </p>
              {data.synthesis.watchItem && (
                <div className="flex items-start gap-2 pt-3 border-t border-zinc-800/50 text-xs">
                  <Target size={14} className="text-blue-400 shrink-0 mt-0.5" />
                  <p><span className="text-zinc-500 font-medium">Watch Item:</span> <span className="text-zinc-300">{data.synthesis.watchItem}</span></p>
                </div>
              )}
            </div>
          )}

          {/* Category Reads */}
          {data.categoryReads && (
            <div>
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-500 mb-3">Category Verdicts vs Peers</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(data.categoryReads).map(([cat, info]) => {
                  if (!info) return null;
                  let colorClass = "text-zinc-400 border-zinc-800";
                  if (info.verdict === "Cheap" || info.verdict === "Strong" || info.verdict === "Conservative" || info.verdict === "Above peers") {
                    colorClass = "text-emerald-400 border-emerald-900/30 bg-emerald-950/10";
                  } else if (info.verdict === "Expensive" || info.verdict === "Weak" || info.verdict === "Aggressive" || info.verdict === "Below peers") {
                    colorClass = "text-red-400 border-red-900/30 bg-red-950/10";
                  } else if (info.verdict === "Fair" || info.verdict === "Average" || info.verdict === "Moderate" || info.verdict === "In line") {
                    colorClass = "text-amber-400 border-amber-900/30 bg-amber-950/10";
                  }

                  return (
                    <div key={cat} className={`border p-3 ${colorClass.split(" ")[1]} ${colorClass.split(" ")[2] || ""}`}>
                      <div className="flex justify-between items-center mb-1.5">
                        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-300">{cat}</span>
                        <span className={`text-[10px] font-medium uppercase tracking-widest ${colorClass.split(" ")[0]}`}>
                          {info.verdict}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-400">{info.vsSectorReasoning}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Cross Ratio & Red Flags */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {data.crossRatioInsights && data.crossRatioInsights.length > 0 && (
              <div>
                <h4 className="text-[10px] tracking-widest uppercase text-zinc-500 mb-3 flex items-center gap-1.5">
                  <Scale size={12} /> Cross-Ratio Insights
                </h4>
                <div className="space-y-2">
                  {data.crossRatioInsights.map((insight, i) => (
                    <div key={i} className="bg-zinc-900/50 border border-zinc-800/60 p-2.5">
                      <div className="text-[10px] font-mono text-blue-400 mb-1">{insight.pattern}</div>
                      <p className="text-xs text-zinc-300">{insight.interpretation}</p>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {(insight.ratiosInvolved || []).map((r, j) => (
                          <span key={j} className="text-[9px] bg-zinc-800 text-zinc-400 px-1.5 py-0.5">{r}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {data.redFlagCombos && data.redFlagCombos.length > 0 && (
              <div>
                <h4 className="text-[10px] tracking-widest uppercase text-zinc-500 mb-3 flex items-center gap-1.5">
                  <AlertTriangle size={12} className="text-red-400" /> Red Flag Combinations
                </h4>
                <div className="space-y-2">
                  {data.redFlagCombos.map((flag, i) => (
                    <div key={i} className="bg-red-950/10 border border-red-900/30 p-2.5">
                      <div className="flex justify-between items-center mb-1">
                        <div className="text-[10px] font-mono text-red-400 uppercase tracking-wider">Severity: {flag.severity}</div>
                      </div>
                      <p className="text-xs text-zinc-300">{flag.explanation}</p>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {(flag.ratiosInvolved || []).map((r, j) => (
                          <span key={j} className="text-[9px] bg-red-950/50 text-red-300 border border-red-900/50 px-1.5 py-0.5">{r}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Peer Standing */}
          {data.peerStanding && (
            <div className="flex items-center gap-4 border-t border-zinc-800/50 pt-4 mt-2">
              <div className="flex-1">
                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-0.5">Overall Peer Position</div>
                <div className="text-sm font-medium text-zinc-200">{data.peerStanding.position}</div>
              </div>
              <div className="w-px h-8 bg-zinc-800"></div>
              <div className="flex-1">
                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-0.5">Strongest Metric</div>
                <div className="text-sm font-medium text-emerald-400">{data.peerStanding.strongestRelativeMetric}</div>
              </div>
              <div className="w-px h-8 bg-zinc-800"></div>
              <div className="flex-1">
                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-0.5">Weakest Metric</div>
                <div className="text-sm font-medium text-red-400">{data.peerStanding.weakestRelativeMetric}</div>
              </div>
            </div>
          )}

          {data.disclaimer && (
            <div className="mt-4 pt-3 border-t border-zinc-800">
              <p className="text-[10px] text-zinc-600 leading-relaxed italic">{data.disclaimer}</p>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
