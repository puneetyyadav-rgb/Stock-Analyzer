import React, { useState } from "react";
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea, ReferenceLine, Cell } from "recharts";
import { Users, Award, TrendingUp, HelpCircle, ArrowUpDown, ShieldCheck } from "lucide-react";
import { fmtNum, fmtPct, rankColor } from "./fundamentalUtils";

const METRIC_LABELS = [
  { key: "revenueGrowth1y", label: "Revenue Growth YoY", isPct: true },
  { key: "revenueGrowth3y", label: "Revenue 3Y CAGR", isPct: true },
  { key: "grossMarginPct", label: "Gross Profit Margin", isPct: true },
  { key: "operatingMarginPct", label: "Operating Margin (EBIT)", isPct: true },
  { key: "netMarginPct", label: "Net Profit Margin", isPct: true },
  { key: "roe", label: "Return on Equity (ROE)", isPct: true },
  { key: "roic", label: "Return on Invested Capital (ROIC)", isPct: true },
  { key: "debtToEquityExLease", label: "Debt / Equity (ex-Lease)", isPct: false },
  { key: "netDebtEbitdaExLease", label: "Net Debt / EBITDA", isPct: false },
  { key: "interestCoverageExLease", label: "Interest Coverage Ratio", isPct: false },
  { key: "currentRatio", label: "Current Ratio", isPct: false },
  { key: "pe", label: "P/E Ratio (TTM)", isPct: false },
  { key: "evToEbitda", label: "EV / EBITDA", isPct: false },
  { key: "pb", label: "Price / Book (P/B)", isPct: false },
  { key: "fcfYieldPct", label: "Free Cash Flow Yield", isPct: true },
  { key: "piotroskiScore", label: "Piotroski F-Score (0-9)", isPct: false },
  { key: "altmanZScore", label: "Altman Z-Score", isPct: false },
  { key: "fiiDiiHoldingPct", label: "FII + DII Institutional Share", isPct: true },
];

export default function FundamentalPeers({ peerBenchmark, meta }) {
  const [sortKey, setSortKey] = useState("default"); // "default" | "targetRank"

  if (!peerBenchmark || !peerBenchmark.available) {
    return (
      <div className="p-6 bg-zinc-900/40 border border-zinc-800 rounded-lg text-center">
        <Users className="w-8 h-8 text-zinc-500 mx-auto mb-2" />
        <p className="text-sm font-medium text-zinc-300">Peer Benchmarking Unavailable</p>
        <p className="text-xs text-zinc-500 mt-1">{peerBenchmark?.reason || "Insufficient sector peer data."}</p>
      </div>
    );
  }

  const matrix = peerBenchmark.matrix || {};
  const peersList = peerBenchmark.peers || [];
  const cccRoce = peerBenchmark.cccRoceQuadrant || [];
  const bullets = peerBenchmark.relativeStrengths || [];
  const targetSymbol = meta?.symbol || "Target";

  // Build columns list: target first, then up to 4 peers
  const columns = [
    { symbol: targetSymbol, name: meta?.companyName || targetSymbol, isTarget: true },
    ...peersList.slice(0, 4).map((p) => ({ symbol: p.symbol, name: p.name || p.symbol, isTarget: false })),
  ];
  const totalCount = columns.length;

  // Helper to get value and rank for a cell
  const getCellData = (metricKey, symbol) => {
    const arr = matrix[metricKey];
    if (!arr || !Array.isArray(arr)) return { value: null, rank: null };
    const found = arr.find((item) => item.symbol === symbol);
    return found ? { value: found.value, rank: found.rankAmongSet } : { value: null, rank: null };
  };

  // Sort metrics if requested
  const sortedMetrics = [...METRIC_LABELS].sort((a, b) => {
    if (sortKey === "targetRank") {
      const rankA = getCellData(a.key, targetSymbol).rank || 99;
      const rankB = getCellData(b.key, targetSymbol).rank || 99;
      return rankA - rankB;
    }
    return 0;
  });

  return (
    <div className="space-y-6">
      {/* Relative Strengths Plain-English Bullets */}
      {bullets.length > 0 && (
        <div className="bg-gradient-to-r from-emerald-950/20 via-zinc-900/50 to-cyan-950/20 border border-emerald-500/20 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Award className="w-4 h-4 text-emerald-400" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
              Institutional Relative Strengths vs Sector Peers
            </h4>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {bullets.map((bullet, idx) => (
              <div key={idx} className="flex items-start gap-2 bg-zinc-900/80 p-2.5 rounded border border-zinc-800/80">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0"></span>
                <span className="text-xs text-zinc-300 font-medium">{bullet}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 18-Metric Peer Matrix Table */}
      <div className="bg-[#0c0c0e] border border-zinc-800/80 rounded-lg p-5 overflow-x-auto">
        <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-zinc-800/80">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100 uppercase tracking-wider flex items-center gap-2">
              <Users className="w-4 h-4 text-cyan-400" />
              18-Metric Peer Benchmarking Matrix
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Cells color-coded by intra-group rank (Rank 1: Emerald, Rank 2: Cyan, Lowest: Red).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSortKey(sortKey === "default" ? "targetRank" : "default")}
              className="px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 text-xs font-medium rounded border border-zinc-700 flex items-center gap-1.5 transition-all"
            >
              <ArrowUpDown className="w-3.5 h-3.5 text-zinc-400" />
              {sortKey === "targetRank" ? "Sorted by Target Rank" : "Sort by Target Rank"}
            </button>
          </div>
        </div>

        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-zinc-800 text-[10px] tracking-wider uppercase text-zinc-400 bg-zinc-900/60 font-mono">
              <th className="py-2.5 px-3 font-semibold">Fundamental Metric</th>
              {columns.map((col) => (
                <th key={col.symbol} className={`py-2.5 px-3 text-right font-semibold ${col.isTarget ? "text-emerald-400 bg-emerald-950/20" : ""}`}>
                  <div className="truncate max-w-[120px]" title={col.name}>{col.symbol}</div>
                  <div className="text-[9px] text-zinc-500 font-normal truncate max-w-[120px]">{col.name}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50 text-xs font-mono">
            {sortedMetrics.map((metric) => (
              <tr key={metric.key} className="hover:bg-zinc-900/40 transition-colors">
                <td className="py-2.5 px-3 text-zinc-300 font-sans font-medium">{metric.label}</td>
                {columns.map((col) => {
                  const { value, rank } = getCellData(metric.key, col.symbol);
                  const formatted = value !== null && value !== undefined ? (metric.isPct ? fmtPct(value, 1) : fmtNum(value, 2)) : "—";
                  const colorClass = rankColor(rank, totalCount);

                  return (
                    <td key={col.symbol} className={`py-2.5 px-3 text-right tabular-nums transition-all ${col.isTarget ? "border-l border-r border-emerald-900/30" : ""} ${colorClass}`}>
                      <div className="flex items-center justify-end gap-1.5">
                        <span>{formatted}</span>
                        {rank && (
                          <span className="text-[9px] px-1 py-0.2 rounded-sm bg-black/40 text-zinc-300 font-semibold border border-white/10">
                            #{rank}
                          </span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* CCC vs ROCE Quadrant Recharts Chart */}
      {cccRoce.length > 0 && (
        <div className="bg-[#0c0c0e] border border-zinc-800/80 rounded-lg p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-zinc-800/80">
            <div>
              <h3 className="text-sm font-semibold text-zinc-100 uppercase tracking-wider flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-amber-400" />
                Cash Conversion Cycle (CCC) vs ROCE Quadrant
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Evaluates operating efficiency (CCC in days, X-axis) against capital return (ROCE %, Y-axis) across the peer group.
              </p>
            </div>
            <span className="text-xs font-mono text-zinc-400">Target + {cccRoce.length - 1} Peers</span>
          </div>

          <div className="h-[360px] w-full relative pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 30, bottom: 25, left: 10 }}>
                <XAxis
                  type="number"
                  dataKey="ccc"
                  name="CCC"
                  unit=" days"
                  stroke="#52525b"
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  label={{ value: "Cash Conversion Cycle (Days)", position: "bottom", offset: 10, fill: "#a1a1aa", fontSize: 12 }}
                />
                <YAxis
                  type="number"
                  dataKey="roce"
                  name="ROCE"
                  unit="%"
                  stroke="#52525b"
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  label={{ value: "ROCE (%)", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 12 }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3", stroke: "#71717a" }}
                  content={({ active, payload }) => {
                    if (!active || !payload || !payload.length) return null;
                    const d = payload[0].payload;
                    return (
                      <div className="bg-zinc-900 border border-zinc-700 p-2.5 rounded shadow-lg text-xs font-mono">
                        <div className="font-bold text-zinc-100 mb-1">{d.symbol} — {d.name}</div>
                        <div className="text-emerald-400">ROCE: {fmtNum(d.roce, 1)}%</div>
                        <div className="text-cyan-400">CCC: {fmtNum(d.ccc, 1)} days</div>
                        <div className="text-zinc-400 text-[11px] mt-1 italic">{d.quadrant}</div>
                      </div>
                    );
                  }}
                />

                {/* Quadrant Background Zones */}
                <ReferenceArea x1={-200} x2={90} y1={12} y2={60} fill="#064e3b" fillOpacity={0.12} />
                <ReferenceArea x1={90} x2={600} y1={12} y2={60} fill="#083344" fillOpacity={0.12} />
                <ReferenceArea x1={-200} x2={90} y1={-20} y2={12} fill="#451a03" fillOpacity={0.12} />
                <ReferenceArea x1={90} x2={600} y1={-20} y2={12} fill="#450a0a" fillOpacity={0.12} />

                {/* Threshold Lines */}
                <ReferenceLine x={90} stroke="#52525b" strokeDasharray="3 3" label={{ value: "90 Days CCC", fill: "#71717a", fontSize: 10, position: "top" }} />
                <ReferenceLine y={12} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "12% ROCE Thresh", fill: "#ef4444", fontSize: 10, position: "right" }} />

                {/* Scatter Points */}
                <Scatter name="Peers" data={cccRoce} shape="circle">
                  {cccRoce.map((entry, index) => {
                    const isTarget = entry.symbol === targetSymbol;
                    return (
                      <Cell
                        key={`cell-${index}`}
                        fill={isTarget ? "#10b981" : "#71717a"}
                        stroke={isTarget ? "#fff" : "#27272a"}
                        strokeWidth={isTarget ? 2 : 1}
                        r={isTarget ? 8 : 6}
                      />
                    );
                  })}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>

            {/* Background Quadrant Labels */}
            <div className="absolute top-6 left-16 text-[11px] font-bold tracking-widest uppercase text-emerald-500/40 pointer-events-none">
              High Efficiency Compounder
            </div>
            <div className="absolute top-6 right-10 text-[11px] font-bold tracking-widest uppercase text-cyan-500/40 pointer-events-none">
              Capital Intensive
            </div>
            <div className="absolute bottom-12 left-16 text-[11px] font-bold tracking-widest uppercase text-amber-500/40 pointer-events-none">
              Efficient / Marginal
            </div>
            <div className="absolute bottom-12 right-10 text-[11px] font-bold tracking-widest uppercase text-red-500/40 pointer-events-none">
              Value Trap / Avoid
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
