import React, { useState } from "react";
import { Panel } from "./Panel";
import axios from "axios";
import { fmtNum } from "../lib/format";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell, Legend,
} from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Stat = ({ label, value, cls }) => (
  <div className="px-2 py-1.5 bg-zinc-900/40 rounded border border-zinc-800/50">
    <div className="text-[9px] uppercase tracking-widest text-zinc-500">{label}</div>
    <div className={`text-sm font-mono font-bold ${cls || "text-zinc-200"}`}>{value}</div>
  </div>
);

const sharpeCls = (s) => (s >= 1 ? "text-emerald-400" : s >= 0.5 ? "text-amber-400" : "text-red-400");

export default function BacktestPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    setData(null);
    try {
      const res = await axios.post(`${API}/backtest`, { mode: "both" });
      setData(res.data);
    } catch (e) {
      setData({ available: false, reason: "Backtest request failed (backend may still be seeding history)." });
    }
    setLoading(false);
  };

  const lo = data?.longOnly, ls = data?.longShort, nf = data?.nifty, cw = data?.costWaterfall;
  const equity = (lo?.curve || []).map((p, i) => ({
    date: p.date, longOnly: p.value,
    longShort: ls?.curve?.[i]?.value, nifty: nf?.curve?.[i]?.value,
  }));
  const waterfall = cw ? [
    { stage: "Gross", cagr: cw.grossCagrPct },
    { stage: "After Fees", cagr: cw.afterTxnCagrPct },
    { stage: "Net (Impact)", cagr: cw.afterImpactCagrPct },
  ] : [];

  return (
    <Panel title="Decile Backtest — Net of Indian STT & Slippage" testId="backtest-panel">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <p className="text-[11px] text-zinc-500 leading-snug max-w-md">
          Replays the factor model weekly over the bhavcopy history, forms long/short deciles, and
          subtracts exact STT, exchange fees & square-root market impact. <span className="text-zinc-400">The truth oracle.</span>
        </p>
        <button onClick={run} disabled={loading}
          className="px-3 py-1.5 bg-fuchsia-600/20 text-fuchsia-300 border border-fuchsia-500/30 rounded text-xs font-medium hover:bg-fuchsia-600/30 transition-colors disabled:opacity-50">
          {loading ? "Running… (may take ~30s)" : "Run Backtest"}
        </button>
      </div>

      {data && !data.available && (
        <p className="text-xs text-amber-400">{data.reason || "Backtest unavailable."}</p>
      )}

      {data?.available && (
        <div className="space-y-4">
          {/* Stat cards */}
          <div>
            <div className="text-[10px] uppercase tracking-widest text-emerald-400 font-bold mb-1">Long-Only vs Nifty (executable cash)</div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
              <Stat label="CAGR" value={`${fmtNum(lo?.cagrPct)}%`} cls={lo?.cagrPct >= 0 ? "text-emerald-400" : "text-red-400"} />
              <Stat label="Sharpe" value={fmtNum(lo?.sharpe)} cls={sharpeCls(lo?.sharpe)} />
              <Stat label="Sortino" value={fmtNum(lo?.sortino)} cls={sharpeCls(lo?.sortino)} />
              <Stat label="Max DD" value={`${fmtNum(lo?.maxDDPct)}%`} cls="text-red-400" />
              <Stat label="Calmar" value={fmtNum(lo?.calmar)} />
              <Stat label="Hit Rate" value={`${fmtNum(lo?.hitRate * 100)}%`} />
            </div>
            {lo?.vsNifty && (
              <div className="text-[10px] text-zinc-500 mt-1">
                Excess CAGR vs Nifty: <span className={lo.vsNifty.excessCagrPct >= 0 ? "text-emerald-400" : "text-red-400"}>{fmtNum(lo.vsNifty.excessCagrPct)}%</span> · β {fmtNum(lo.vsNifty.beta)}
              </div>
            )}
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-widest text-blue-400 font-bold mb-1">Long/Short Decile (short = futures)</div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
              <Stat label="CAGR" value={`${fmtNum(ls?.cagrPct)}%`} cls={ls?.cagrPct >= 0 ? "text-emerald-400" : "text-red-400"} />
              <Stat label="Sharpe" value={fmtNum(ls?.sharpe)} cls={sharpeCls(ls?.sharpe)} />
              <Stat label="Sortino" value={fmtNum(ls?.sortino)} cls={sharpeCls(ls?.sortino)} />
              <Stat label="Max DD" value={`${fmtNum(ls?.maxDDPct)}%`} cls="text-red-400" />
              <Stat label="Calmar" value={fmtNum(ls?.calmar)} />
              <Stat label="Hit Rate" value={`${fmtNum(ls?.hitRate * 100)}%`} />
            </div>
          </div>

          {/* Equity curves */}
          <div className="h-52">
            <div className="text-[10px] uppercase tracking-widest text-zinc-400 font-bold mb-1">Equity Curve (₹1 start)</div>
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={equity} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}>
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#71717a" }} minTickGap={40} />
                <YAxis tick={{ fontSize: 9, fill: "#71717a" }} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <ReferenceLine y={1} stroke="#3f3f46" strokeDasharray="3 3" />
                <Line type="monotone" dataKey="longOnly" name="Long-Only" stroke="#34d399" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="longShort" name="Long/Short" stroke="#60a5fa" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="nifty" name="Nifty" stroke="#a1a1aa" strokeWidth={1} dot={false} isAnimationActive={false} opacity={0.7} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Decile spread */}
            <div className="h-44">
              <div className="text-[10px] uppercase tracking-widest text-zinc-400 font-bold mb-1">Decile Spread (mean fwd ret %)</div>
              <ResponsiveContainer width="100%" height="90%">
                <BarChart data={data.decileSpread} margin={{ top: 5, right: 8, left: -20, bottom: 0 }}>
                  <XAxis dataKey="decile" tick={{ fontSize: 9, fill: "#71717a" }} />
                  <YAxis tick={{ fontSize: 9, fill: "#71717a" }} />
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 11 }} />
                  <ReferenceLine y={0} stroke="#3f3f46" />
                  <Bar dataKey="meanFwdRetPct" isAnimationActive={false}>
                    {data.decileSpread.map((d, i) => (
                      <Cell key={i} fill={d.meanFwdRetPct >= 0 ? "#34d399" : "#f87171"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Cost waterfall */}
            <div className="h-44">
              <div className="text-[10px] uppercase tracking-widest text-zinc-400 font-bold mb-1">Cost Waterfall (CAGR %)</div>
              <ResponsiveContainer width="100%" height="90%">
                <BarChart data={waterfall} margin={{ top: 5, right: 8, left: -20, bottom: 0 }}>
                  <XAxis dataKey="stage" tick={{ fontSize: 9, fill: "#71717a" }} />
                  <YAxis tick={{ fontSize: 9, fill: "#71717a" }} />
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 11 }} />
                  <Bar dataKey="cagr" isAnimationActive={false}>
                    {waterfall.map((_, i) => (
                      <Cell key={i} fill={["#34d399", "#fbbf24", "#f87171"][i]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Honesty footnotes */}
          <div className="text-[10px] text-zinc-500 leading-relaxed border-t border-zinc-800/50 pt-2">
            {data.dateRange?.start} → {data.dateRange?.end} · {data.dateRange?.rebalances} weekly rebalances ·
            avg turnover {fmtNum(data.avgTurnover * 100)}% · <span className="text-amber-500">{data.droppedIlliquid} illiquid positions size-capped</span> ·
            {data.corpActionFlagged} corp-action outliers winsorized.
            {data.warnings?.length > 0 && <span className="text-amber-400"> ⚠ {data.warnings.join("; ")}</span>}
          </div>
        </div>
      )}
    </Panel>
  );
}
