import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import axios from "axios";
import { fmtNum, fmtBigNum } from "../lib/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OptionsPanel({ symbol }) {
  const [data, setData] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setData(null);
    setAnalysis(null);
    axios.get(`${API}/stock/${symbol}/options`).then((r) => setData(r.data)).catch(() => setData({ available: false }));
  }, [symbol]);

  const handleAnalyze = async () => {
    if (!data || !data.rows) return;
    setAnalyzing(true);
    setAnalysis(null);
    try {
      const res = await axios.post(`${API}/stock/${symbol}/analyze-options`, data);
      setAnalysis(res.data);
    } catch (e) {
      setAnalysis({ error: "Analysis failed" });
    }
    setAnalyzing(false);
  };

  if (!data) return <Panel title="Options Chain & PCR (NSE)" testId="options-panel"><p className="text-xs text-zinc-500">Loading…</p></Panel>;

  if (!data.available) {
    const isNotFO = data.error === "Not F&O" || (data.reason && data.reason.includes("not available"));
    return (
      <Panel title="Options Chain & PCR (NSE)" testId="options-panel">
        <div className="text-xs text-zinc-500 space-y-1">
          {isNotFO ? (
            <p className="text-zinc-400 font-medium">{symbol} does not trade in the F&O segment.</p>
          ) : (
            <>
              <p className="text-amber-400 font-medium">Options chain temporarily unavailable</p>
              <p className="text-zinc-600 leading-snug">{data.reason || data.error}</p>
            </>
          )}
        </div>
      </Panel>
    );
  }

  return (
    <Panel title={`Options Chain · ${data.expiry || ""}`} testId="options-panel">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-4">
        <div className="flex gap-4 flex-wrap">
          <div>
            <div className="text-[9px] tracking-widest uppercase text-zinc-500">Underlying</div>
            <div className="text-sm font-mono tabular-nums">₹{fmtNum(data.underlying)}</div>
          </div>
          <div>
            <div className="text-[9px] tracking-widest uppercase text-zinc-500">PCR</div>
            <div className={`text-sm font-mono tabular-nums ${data.pcr > 1 ? "text-emerald-400" : "text-red-400"}`}>{fmtNum(data.pcr, 2)}</div>
          </div>
          <div>
            <div className="text-[9px] tracking-widest uppercase text-zinc-500">CE Tot OI</div>
            <div className="text-sm font-mono tabular-nums">{fmtBigNum(data.ceTotalOI)}</div>
          </div>
          <div>
            <div className="text-[9px] tracking-widest uppercase text-zinc-500">PE Tot OI</div>
            <div className="text-sm font-mono tabular-nums">{fmtBigNum(data.peTotalOI)}</div>
          </div>
        </div>
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="px-3 py-1.5 bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded text-xs font-medium hover:bg-blue-600/30 transition-colors disabled:opacity-50"
        >
          {analyzing ? "Analyzing..." : "Analyze Options"}
        </button>
      </div>

      {data.positioning?.available && (
        <div className="mb-4 p-2.5 rounded bg-indigo-950/20 border border-indigo-900/40">
          <div className="text-[10px] uppercase tracking-widest text-indigo-400 font-bold mb-1.5">Dealer Positioning</div>
          <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs">
            <div><span className="text-zinc-500">Max Pain </span><span className="font-mono text-amber-300">₹{fmtNum(data.positioning.maxPain)}</span></div>
            <div><span className="text-zinc-500">OI Supp </span><span className="font-mono text-emerald-400">₹{fmtNum(data.positioning.oiSupport)}</span></div>
            <div><span className="text-zinc-500">OI Resist </span><span className="font-mono text-red-400">₹{fmtNum(data.positioning.oiResistance)}</span></div>
            {data.positioning.dataQuality === "full" && data.positioning.gex && (
              <>
                <div className="col-span-3 leading-snug">
                  <span className="text-zinc-500">Gamma </span>
                  <span className={data.positioning.gex.net >= 0 ? "text-emerald-400" : "text-red-400"}>{data.positioning.gex.regime}</span>
                  {data.positioning.gex.flipStrike ? <span className="text-zinc-500"> · flip ₹{fmtNum(data.positioning.gex.flipStrike)}</span> : null}
                </div>
                {data.positioning.iv?.atmPct != null && (
                  <div><span className="text-zinc-500">ATM IV </span><span className="font-mono text-fuchsia-300">{fmtNum(data.positioning.iv.atmPct)}%</span></div>
                )}
                {data.positioning.iv?.skewPct != null && (
                  <div><span className="text-zinc-500">Skew </span><span className={`font-mono ${data.positioning.iv.skewPct > 0 ? "text-red-400" : "text-emerald-400"}`}>{fmtNum(data.positioning.iv.skewPct)}%</span></div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {analysis && (
        <div className="mb-4 p-3 rounded bg-zinc-800/40 border border-zinc-700/50">
          {analysis.error ? (
            <p className="text-xs text-red-400">{analysis.error}</p>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-4">
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                  analysis.trend === "Bullish" ? "bg-emerald-500/20 text-emerald-400" :
                  analysis.trend === "Bearish" ? "bg-red-500/20 text-red-400" :
                  "bg-amber-500/20 text-amber-400"
                }`}>
                  {analysis.trend}
                </span>
                <div className="text-xs text-zinc-300">
                  <span className="text-zinc-500">Support:</span> <span className="font-mono">₹{fmtNum(analysis.support)}</span>
                </div>
                <div className="text-xs text-zinc-300">
                  <span className="text-zinc-500">Resistance:</span> <span className="font-mono">₹{fmtNum(analysis.resistance)}</span>
                </div>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">
                {analysis.conclusion}
              </p>
            </div>
          )}
        </div>
      )}

      <table className="w-full text-xs">
        <thead>
          <tr className="text-[9px] tracking-widest uppercase text-zinc-500">
            <th className="text-right py-1 text-emerald-400">CE OI</th>
            <th className="text-right py-1 text-emerald-400">CE LTP</th>
            <th className="text-center py-1">Strike</th>
            <th className="text-right py-1 text-red-400">PE LTP</th>
            <th className="text-right py-1 text-red-400">PE OI</th>
          </tr>
        </thead>
        <tbody>
          {(data.rows || []).map((r) => {
            const isATM = data.underlying && Math.abs(r.strike - data.underlying) === Math.min(...data.rows.map(x => Math.abs(x.strike - data.underlying)));
            return (
              <tr key={r.strike} className={`border-t border-zinc-800/30 ${isATM ? "bg-blue-900/20" : ""}`}>
                <td className="py-1 font-mono tabular-nums text-right">{fmtBigNum(r.ceOI)}</td>
                <td className="py-1 font-mono tabular-nums text-right">{fmtNum(r.ceLTP)}</td>
                <td className="py-1 font-mono tabular-nums text-center font-medium">{fmtNum(r.strike, 0)}</td>
                <td className="py-1 font-mono tabular-nums text-right">{fmtNum(r.peLTP)}</td>
                <td className="py-1 font-mono tabular-nums text-right">{fmtBigNum(r.peOI)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
