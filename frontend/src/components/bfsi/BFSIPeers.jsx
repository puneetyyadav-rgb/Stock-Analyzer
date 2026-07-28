import React from "react";
import { Users } from "lucide-react";
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from "recharts";
import { fmtNum, rankColor } from "../fundamental/fundamentalUtils";
import { Panel } from "./_bfsiShared";

const fmtCell = (key, v) => {
  if (v == null) return "—";
  if (key === "bvps_inr") return fmtNum(v, 1);
  if (key === "pbRatio" || key === "peRatio" || key === "spreadRatio") return fmtNum(v, 2);
  return fmtNum(v, 1);
};

const QUAD_COLORS = ["#34d399", "#22d3ee", "#fbbf24", "#f87171", "#a78bfa", "#94a3b8"];

export default function BFSIPeers({ data }) {
  if (!data) return null;
  if (!data.available) {
    return <Panel title="Peer Benchmarking" icon={Users} color="text-cyan-400"><p className="text-xs font-mono text-zinc-500">{data.reason || "Peer data unavailable."}</p></Panel>;
  }
  const rows = data.rows || [];
  const cols = data.columns || [];
  const quad = data.nimRoaQuadrant || [];

  // Quadrant medians for reference lines.
  const nims = quad.map((q) => q.nim).filter((x) => x != null);
  const roas = quad.map((q) => q.roa).filter((x) => x != null);
  const medNim = nims.length ? nims.slice().sort((a, b) => a - b)[Math.floor(nims.length / 2)] : 0;
  const medRoa = roas.length ? roas.slice().sort((a, b) => a - b)[Math.floor(roas.length / 2)] : 0;

  return (
    <div className="space-y-4">
      <Panel title={`Peer Benchmarking — ${String(data.subSector || "").replace(/_/g, " ")}`} icon={Users} color="text-cyan-400" note={data.note}>
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] font-mono border-collapse">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left py-2 pr-3 text-zinc-400 font-semibold sticky left-0 bg-zinc-900/60">Metric</th>
                {rows.map((r) => (
                  <th key={r.symbol} className="text-right py-2 px-2 text-zinc-300 font-semibold whitespace-nowrap">{r.name || r.symbol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cols.map((c) => (
                <tr key={c.key} className="border-b border-zinc-800/50">
                  <td className="py-1.5 pr-3 text-zinc-400 sticky left-0 bg-zinc-900/60 whitespace-nowrap">{c.label}</td>
                  {rows.map((r, ri) => {
                    const rank = c.ranks ? c.ranks[ri] : null;
                    const cls = rank ? rankColor(rank, rows.length) : "text-zinc-300";
                    return (
                      <td key={r.symbol} className={`py-1.5 px-2 text-right whitespace-nowrap ${cls}`}>
                        {fmtCell(c.key, r[c.key])}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {quad.length > 1 && (
        <Panel title="NIM vs RoA Quadrant" icon={Users} color="text-cyan-400" note="High NIM + High RoA = Quality Franchise. High NIM + Low RoA = operationally inefficient. Low NIM + High RoA = fee/trading dependent. Low + Low = structurally disadvantaged.">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 30, bottom: 25, left: 10 }}>
                <XAxis type="number" dataKey="nim" name="NIM %" stroke="#71717a" tick={{ fill: "#a1a1aa", fontSize: 11 }} label={{ value: "NIM proxy %", position: "insideBottom", offset: -15, fill: "#a1a1aa", fontSize: 11 }} />
                <YAxis type="number" dataKey="roa" name="RoA %" stroke="#71717a" tick={{ fill: "#a1a1aa", fontSize: 11 }} label={{ value: "RoA %", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 11 }} />
                <ReferenceLine x={medNim} stroke="#52525b" strokeDasharray="4 4" />
                <ReferenceLine y={medRoa} stroke="#52525b" strokeDasharray="4 4" />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 11 }} formatter={(v, n) => [fmtNum(v, 2), n]} labelFormatter={(_, p) => (p && p[0] && p[0].payload ? p[0].payload.name : "")} />
                <Scatter data={quad}>
                  {quad.map((q, i) => (
                    <Cell key={q.symbol} fill={QUAD_COLORS[i % QUAD_COLORS.length]} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-3 mt-2">
            {quad.map((q, i) => (
              <span key={q.symbol} className="text-[10px] font-mono text-zinc-400 flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: QUAD_COLORS[i % QUAD_COLORS.length] }}></span>
                {q.name}
              </span>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
