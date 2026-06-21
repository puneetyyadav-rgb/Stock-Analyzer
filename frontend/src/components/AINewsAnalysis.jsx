import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Newspaper, Loader2, AlertCircle } from "lucide-react";
import { getAINews } from "../lib/api";
import { DisclaimerNote } from "./Disclaimer";

export default function AINewsAnalysis({ symbol }) {
  const [newsAI, setNewsAI] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setNewsAI(null);
    setErr(null);
  }, [symbol]);

  const run = async () => {
    setLoading(true);
    setErr(null);
    try {
      const r = await getAINews(symbol);
      if (r.error) setErr(r.error);
      else setNewsAI(r);
    } catch (e) {
      setErr(e.message || "Failed to load News Analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel
      title="AI News Desk Analyst"
      right={
        <button
          onClick={run}
          disabled={loading}
          className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] tracking-widest uppercase font-medium bg-amber-700 text-amber-50 hover:bg-amber-600 disabled:opacity-50 transition-colors"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Newspaper size={12} />}
          {loading ? "Reading Headlines…" : newsAI ? "Re-Analyze" : "Generate News Analysis"}
        </button>
      }
    >
      {!newsAI && !loading && !err && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <Newspaper size={28} className="text-amber-500 mb-3" />
          <p className="text-sm text-zinc-400 max-w-md">
            Click <span className="font-mono text-zinc-200">Generate</span> to have the AI synthesize all recent headlines into a crux, key pointers, and price-impact scenarios.
          </p>
        </div>
      )}
      {loading && (
        <div className="flex items-center justify-center py-10 gap-2 text-zinc-400">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-xs tracking-widest uppercase">Synthesizing news catalysts…</span>
        </div>
      )}
      {err && (
        <div className="flex items-start gap-2 p-3 bg-red-950/40 border border-red-900/60 text-red-300 text-xs">
          <AlertCircle size={14} /> <span>{err}</span>
        </div>
      )}
      {newsAI && !newsAI.error && (
        <div className="space-y-4">
          <div className="p-3 bg-amber-950/10 border border-amber-900/30 rounded">
            <h4 className="text-[10px] tracking-widest uppercase text-amber-500 mb-1">The Crux</h4>
            <p className="text-sm font-semibold text-zinc-200">{newsAI.crux}</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-400">Summary</h4>
              <p className="text-xs text-zinc-300 leading-relaxed">{newsAI.summary}</p>
            </div>
            
            <div className="space-y-2">
              <h4 className="text-[10px] tracking-widest uppercase text-blue-400">Main Pointers</h4>
              <ul className="space-y-1">
                {(newsAI.main_pointers || []).map((ptr, i) => (
                  <li key={i} className="text-xs text-zinc-300 flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    <span>{ptr}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-emerald-400 mb-2">Trade Bias & Target Impact</h4>
              <p className="text-sm text-zinc-200">{newsAI.buy_sell_target}</p>
            </div>
            
            <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-purple-400 mb-2">"What If" Scenarios</h4>
              <ul className="space-y-3">
                {(newsAI.scenarios || []).map((sc, i) => (
                  <li key={i} className="flex flex-col gap-1 text-xs">
                    <span className="text-zinc-400 font-semibold uppercase tracking-wider text-[9px]">If this happens:</span>
                    <span className="text-zinc-200">{sc.if_this_happens}</span>
                    <span className="text-purple-400 font-semibold uppercase tracking-wider text-[9px] mt-1">Then expect:</span>
                    <span className="text-zinc-300">{sc.then_expected_impact}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          
          <DisclaimerNote className="bg-transparent border-0 pt-2" />
        </div>
      )}
    </Panel>
  );
}
