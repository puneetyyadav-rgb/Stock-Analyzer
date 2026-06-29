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
      title="AI Institutional Quant & Technical Deck"
      right={
        <button
          onClick={run}
          disabled={loading}
          className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] tracking-widest uppercase font-medium bg-fuchsia-700 text-white hover:bg-fuchsia-600 disabled:opacity-50 transition-colors"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <LineChart size={12} />}
          {loading ? "Running Quant Engine…" : tech ? "Re-Analyze Deck" : "Generate Quant Deck"}
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
          {tech.quantScore !== undefined && (
            <div className="flex items-center justify-between p-3 bg-gradient-to-r from-fuchsia-950/40 to-purple-950/40 border border-fuchsia-800/60 rounded">
              <div>
                <span className="text-[10px] uppercase tracking-widest text-fuchsia-400 font-bold block">Institutional Quant Score</span>
                <span className="text-xs text-zinc-400">Pure Math Confidence Rating</span>
              </div>
              <div className="text-2xl font-mono font-black text-fuchsia-300">{tech.quantScore} <span className="text-sm text-zinc-500">/ 100</span></div>
            </div>
          )}

          {tech.regimeClassification && (
            <div className="p-3 bg-purple-950/20 border border-purple-900/50 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-purple-400 mb-1.5 font-bold">Signal Processing & Regime Detection (Hurst & Kalman)</h4>
              <p className="text-sm text-zinc-200 leading-relaxed">{tech.regimeClassification}</p>
            </div>
          )}

          {tech.riskEngineering && (
            <div className="p-3 bg-red-950/20 border border-red-900/50 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-red-400 mb-1.5 font-bold">Risk Engineering (Fat-Tail Bootstrap Monte Carlo VaR)</h4>
              <p className="text-sm text-zinc-200 leading-relaxed">{tech.riskEngineering}</p>
            </div>
          )}

          {tech.microstructureFlow && (
            <div className="p-3 bg-amber-950/20 border border-amber-900/50 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-amber-400 mb-1.5 font-bold">Microstructure & Order Flow (Level-2 OBI & RVOL)</h4>
              <p className="text-sm text-zinc-200 leading-relaxed">{tech.microstructureFlow}</p>
            </div>
          )}

          {tech.keyLevelsMatrix && (
            <div className="p-3 bg-emerald-950/20 border border-emerald-900/50 rounded grid grid-cols-2 sm:grid-cols-4 gap-2 text-center font-mono">
              <div className="bg-black/40 p-2 rounded border border-emerald-900/30">
                <span className="text-[9px] text-zinc-400 uppercase block">Entry Zone</span>
                <span className="text-xs text-emerald-400 font-bold">{tech.keyLevelsMatrix.entryZone || "-"}</span>
              </div>
              <div className="bg-black/40 p-2 rounded border border-emerald-900/30">
                <span className="text-[9px] text-zinc-400 uppercase block">Target ($R1/R2$)</span>
                <span className="text-xs text-emerald-300 font-bold">₹{tech.keyLevelsMatrix.target || "-"}</span>
              </div>
              <div className="bg-black/40 p-2 rounded border border-red-900/30">
                <span className="text-[9px] text-zinc-400 uppercase block">Stop Loss ($S1$)</span>
                <span className="text-xs text-red-400 font-bold">₹{tech.keyLevelsMatrix.stopLoss || "-"}</span>
              </div>
              <div className="bg-black/40 p-2 rounded border border-fuchsia-900/30">
                <span className="text-[9px] text-zinc-400 uppercase block">Risk : Reward</span>
                <span className="text-xs text-fuchsia-300 font-bold">{tech.keyLevelsMatrix.riskRewardRatio || "-"}</span>
              </div>
            </div>
          )}

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
