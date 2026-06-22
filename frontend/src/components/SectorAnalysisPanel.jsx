import React, { useEffect, useState } from "react";
import { Panel, KV } from "./Panel";
import { ExternalLink, Loader2, TrendingUp, TrendingDown } from "lucide-react";
import axios from "axios";
import { fmtNum, fmtPct, colorClass } from "../lib/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DEEP_LINKS_META = [
  { key: "trendlyne", label: "Trendlyne", color: "bg-orange-700 hover:bg-orange-600" },
  { key: "stockedge", label: "StockEdge", color: "bg-blue-700 hover:bg-blue-600" },
  { key: "aftermarkets", label: "Aftermarkets", color: "bg-purple-700 hover:bg-purple-600" },
  { key: "moneycontrol_sector", label: "MC Sector News", color: "bg-amber-700 hover:bg-amber-600" },
  { key: "nse_indices", label: "NSE Indices", color: "bg-zinc-700 hover:bg-zinc-600" },
];

export default function SectorAnalysisPanel({ symbol }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setData(null);
    axios.get(`${API}/stock/${symbol}/sector-analysis`).then((r) => setData(r.data)).catch(() => setData({ error: true }));
  }, [symbol]);

  return (
    <Panel title="Sectoral Analysis" testId="sector-analysis-panel">
      {!data && <div className="flex items-center gap-2 text-zinc-500 text-xs"><Loader2 size={12} className="animate-spin" /> Loading…</div>}
      {data && !data.error && (
        <div className="space-y-3">
          {/* Sector vs Benchmark */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div className="border border-zinc-800/60 p-2.5" data-testid="sector-index-card">
              <div className="text-[10px] tracking-widest uppercase text-zinc-500 mb-1">{data.sector_index?.label}</div>
              <div className="text-lg font-mono tabular-nums">{fmtNum(data.sector_index?.price)}</div>
              <div className={`text-xs font-mono tabular-nums ${colorClass(data.sector_index?.changePercent)}`}>
                Today: {fmtPct(data.sector_index?.changePercent)}
              </div>
              <div className="flex gap-3 text-[10px] mt-2">
                <span className={colorClass(data.sector_index?.perf_1m)}>1M: {fmtPct(data.sector_index?.perf_1m)}</span>
                <span className={colorClass(data.sector_index?.perf_3m)}>3M: {fmtPct(data.sector_index?.perf_3m)}</span>
              </div>
            </div>
            <div className="border border-zinc-800/60 p-2.5" data-testid="benchmark-card">
              <div className="text-[10px] tracking-widest uppercase text-zinc-500 mb-1">{data.benchmark?.label}</div>
              <div className="text-lg font-mono tabular-nums">{fmtNum(data.benchmark?.price)}</div>
              <div className={`text-xs font-mono tabular-nums ${colorClass(data.benchmark?.changePercent)}`}>
                Today: {fmtPct(data.benchmark?.changePercent)}
              </div>
              <div className="flex gap-3 text-[10px] mt-2">
                <span className={colorClass(data.benchmark?.perf_1m)}>1M: {fmtPct(data.benchmark?.perf_1m)}</span>
                <span className={colorClass(data.benchmark?.perf_3m)}>3M: {fmtPct(data.benchmark?.perf_3m)}</span>
              </div>
            </div>
          </div>

          {/* Verdict */}
          <div className={`px-3 py-2 border-l-2 ${
            (data.relative_perf_1m || 0) > 1 ? "border-emerald-500 bg-emerald-950/30" :
            (data.relative_perf_1m || 0) < -1 ? "border-red-500 bg-red-950/30" :
            "border-zinc-600 bg-zinc-900/30"
          }`} data-testid="sector-verdict">
            <div className="flex items-center justify-between">
              <span className="text-xs tracking-widest uppercase text-zinc-300 flex items-center gap-1">
                {(data.relative_perf_1m || 0) > 1 ? <TrendingUp size={12} className="text-emerald-400" /> :
                 (data.relative_perf_1m || 0) < -1 ? <TrendingDown size={12} className="text-red-400" /> : null}
                {data.verdict}
              </span>
              <span className={`text-sm font-mono tabular-nums ${colorClass(data.relative_perf_1m)}`}>
                Rel 1M: {fmtPct(data.relative_perf_1m)}
              </span>
            </div>
          </div>

          {/* Peer Aggregates */}
          {data.peer_aggregates && (
            <div className="border-t border-zinc-800/40 pt-3">
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-2">Sector Peer Aggregates ({data.peer_aggregates.count} peers)</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-x-3">
                <KV label="Avg P/E" value={fmtNum(data.peer_aggregates.avg_pe)} />
                <KV label="Avg P/B" value={fmtNum(data.peer_aggregates.avg_pb)} />
                <KV label="Avg ROE" value={data.peer_aggregates.avg_roe ? fmtPct(data.peer_aggregates.avg_roe * 100) : "—"} />
                <KV label="Avg Margin" value={data.peer_aggregates.avg_profit_margin ? fmtPct(data.peer_aggregates.avg_profit_margin * 100) : "—"} />
                <KV label="Avg Rev Growth" value={data.peer_aggregates.avg_revenue_growth ? fmtPct(data.peer_aggregates.avg_revenue_growth * 100) : "—"} />
              </div>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {data.peer_aggregates.top_gainer && (
                  <div className="border-l-2 border-emerald-700/60 pl-2 py-1">
                    <div className="text-[10px] tracking-widest uppercase text-emerald-400">Top Gainer</div>
                    <div className="text-xs font-mono text-zinc-200">{data.peer_aggregates.top_gainer.symbol?.replace(".NS", "")}</div>
                    <div className="text-xs font-mono text-emerald-400">{fmtPct(data.peer_aggregates.top_gainer.changePercent)}</div>
                  </div>
                )}
                {data.peer_aggregates.top_loser && (
                  <div className="border-l-2 border-red-700/60 pl-2 py-1">
                    <div className="text-[10px] tracking-widest uppercase text-red-400">Top Loser</div>
                    <div className="text-xs font-mono text-zinc-200">{data.peer_aggregates.top_loser.symbol?.replace(".NS", "")}</div>
                    <div className="text-xs font-mono text-red-400">{fmtPct(data.peer_aggregates.top_loser.changePercent)}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Stock vs peers */}
          {data.stock_vs_peers && (
            <div className="border-t border-zinc-800/40 pt-3">
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-2">Stock vs Sector Peers</h4>
              <div className="text-xs text-zinc-300">
                Valued <span className={data.stock_vs_peers.pe_vs_peer_avg === "Cheaper" ? "text-emerald-400" : "text-amber-400"}>
                  {data.stock_vs_peers.pe_vs_peer_avg}
                </span> than peer avg by <span className="font-mono">{fmtPct(data.stock_vs_peers.pe_diff_pct)}</span> on P/E
              </div>
            </div>
          )}

          {/* Deep Links to external sources */}
          <div className="border-t border-zinc-800/40 pt-3">
            <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-2">Deep Dive on External Sources</h4>
            <div className="flex flex-wrap gap-1.5">
              {DEEP_LINKS_META.map((dl) => {
                const url = data.deep_links?.[dl.key];
                if (!url) return null;
                return (
                  <a
                    key={dl.key}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={`deeplink-${dl.key}`}
                    className={`flex items-center gap-1 px-2 py-1 text-[10px] tracking-widest uppercase font-medium text-white transition-colors ${dl.color}`}
                  >
                    {dl.label}
                    <ExternalLink size={9} />
                  </a>
                );
              })}
            </div>
            <p className="text-[9px] text-zinc-600 mt-2 leading-snug">
              Trendlyne, StockEdge, and Aftermarkets are protected by anti-bot/SPA rendering that prevents server-side scraping —
              these deep links open the relevant pages directly in your browser where they render normally.
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}
