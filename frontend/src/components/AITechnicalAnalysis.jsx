import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { LineChart, Loader2, AlertCircle } from "lucide-react";
import { getAITechnical } from "../lib/api";
import { DisclaimerNote } from "./Disclaimer";

export default function AITechnicalAnalysis({ symbol }) {
  const [tech, setTech] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setTech(null);
    setErr(null);
  }, [symbol]);

  const run = async () => {
    setLoading(true);
    setErr(null);
    try {
      const r = await getAITechnical(symbol);
      if (r.error) setErr(r.error);
      else setTech(r);
    } catch (e) {
      setErr(e.message || "Failed to load Technical Analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel
      title="AI Technical Analysis (CMT)"
      right={
        <button
          onClick={run}
          disabled={loading}
          className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] tracking-widest uppercase font-medium bg-fuchsia-700 text-white hover:bg-fuchsia-600 disabled:opacity-50 transition-colors"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <LineChart size={12} />}
          {loading ? "Analyzing Charts…" : tech ? "Re-Analyze" : "Generate Technical Analysis"}
        </button>
      }
    >
      {!tech && !loading && !err && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <LineChart size={28} className="text-fuchsia-500 mb-3" />
          <p className="text-sm text-zinc-400 max-w-md">
            Click <span className="font-mono text-zinc-200">Generate</span> to have the AI interpret candlestick patterns, Monte Carlo volatility, and price action like a Chartered Market Technician.
          </p>
        </div>
      )}
      {loading && (
        <div className="flex items-center justify-center py-10 gap-2 text-zinc-400">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-xs tracking-widest uppercase">Reading the charts…</span>
        </div>
      )}
      {err && (
        <div className="flex items-start gap-2 p-3 bg-red-950/40 border border-red-900/60 text-red-300 text-xs">
          <AlertCircle size={14} /> <span>{err}</span>
        </div>
      )}
      {tech && !tech.error && (
        <div className="space-y-4">
          <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded">
            <h4 className="text-[10px] tracking-widest uppercase text-fuchsia-400 mb-2">Trend & Posture</h4>
            <p className="text-sm text-zinc-300 leading-relaxed">{tech.trend_summary}</p>
          </div>
          
          {tech.volume_and_delivery_insight && (
            <div className="p-3 bg-blue-950/20 border border-blue-900/50 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-blue-400 mb-2">Volume & Delivery Insight (Bhavcopy)</h4>
              <p className="text-sm text-zinc-200 leading-relaxed font-medium">{tech.volume_and_delivery_insight}</p>
            </div>
          )}
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-emerald-900/40 bg-emerald-950/10 p-3 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-emerald-500 mb-2">Support Levels</h4>
              <ul className="space-y-3">
                {(tech.support_levels || []).map((s, i) => (
                  <li key={i} className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400 font-mono text-sm">₹{s.price}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded ${s.strength === "Strong" ? "bg-emerald-900 text-emerald-200" : "bg-zinc-800 text-zinc-400"}`}>{s.strength}</span>
                    </div>
                    <span className="text-xs text-zinc-400">{s.rationale}</span>
                  </li>
                ))}
              </ul>
            </div>
            
            <div className="border border-red-900/40 bg-red-950/10 p-3 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-red-500 mb-2">Resistance Levels</h4>
              <ul className="space-y-3">
                {(tech.resistance_levels || []).map((r, i) => (
                  <li key={i} className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <span className="text-red-400 font-mono text-sm">₹{r.price}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded ${r.strength === "Strong" ? "bg-red-900 text-red-200" : "bg-zinc-800 text-zinc-400"}`}>{r.strength}</span>
                    </div>
                    <span className="text-xs text-zinc-400">{r.rationale}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-[#0c0c0e] border border-blue-900/30 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-blue-400 mb-1">Trade Setup</h4>
              <p className="text-sm text-zinc-300">{tech.setup_recommendation}</p>
            </div>
            
            <div className="p-3 bg-[#0c0c0e] border border-purple-900/30 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-purple-400 mb-1">Volatility Insight (Monte Carlo)</h4>
              <p className="text-sm text-zinc-300">{tech.monte_carlo_insight}</p>
            </div>
          </div>
          
          <DisclaimerNote className="bg-transparent border-0 pt-2" />
        </div>
      )}
    </Panel>
  );
}
