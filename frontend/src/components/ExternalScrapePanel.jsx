import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { ExternalLink, Loader2, Sparkles, ShieldCheck, ShieldAlert } from "lucide-react";
import axios from "axios";
import { fmtNum, fmtPct, colorClass } from "../lib/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const scoreColor = (s) => {
  if (s >= 75) return "bg-emerald-700 text-emerald-50";
  if (s >= 60) return "bg-emerald-900/60 text-emerald-300";
  if (s >= 45) return "bg-amber-700/70 text-amber-100";
  return "bg-red-700/70 text-red-100";
};

const ratingColor = (r) => {
  const rating = (r || "").toUpperCase();
  if (rating === "CHEAP" || rating === "STRONG") return "text-emerald-400";
  if (rating === "STABLE" || rating === "MODERATE") return "text-amber-400";
  if (rating === "WEAK" || rating === "EXPENSIVE") return "text-red-400";
  return "text-zinc-300";
};

const safetyBadge = (val) => {
  const v = (val || "").toLowerCase();
  if (v === "none" || v === "low" || v === "not tracked") return "bg-emerald-900/60 text-emerald-200 border-emerald-700/60";
  if (v.includes("high") || v.includes("yes") || v.includes("flagged")) return "bg-red-700 text-red-50 border-red-500";
  return "bg-zinc-800 text-zinc-200 border-zinc-700";
};

export default function ExternalScrapePanel({ symbol }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setData(null);
    axios.get(`${API}/stock/${symbol}/external-scrape`, { timeout: 60000 })
      .then((r) => setData(r.data))
      .catch(() => setData({ error: true }));
  }, [symbol]);

  return (
    <Panel
      title={<><Sparkles size={11} className="inline mr-1 text-purple-400" /> External Intelligence (Aftermarkets · Trendlyne · StockEdge)</>}
      testId="external-scrape-panel"
    >
      {!data && (
        <div className="flex items-center gap-2 text-zinc-500 text-xs">
          <Loader2 size={12} className="animate-spin" /> Running headless browser scrape (15-25s first time, cached for 30 min)…
        </div>
      )}
      {data && (
        <div className="space-y-3">
          {/* Aftermarkets — primary, real data */}
          <div className="border border-purple-900/40 p-3 bg-purple-950/10" data-testid="aftermarkets-card">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[10px] tracking-widest uppercase text-purple-400 font-semibold">Aftermarkets.in</h4>
              {data.aftermarkets?.url && (
                <a href={data.aftermarkets.url} target="_blank" rel="noreferrer" className="text-[10px] text-purple-300 hover:text-purple-100 flex items-center gap-1">
                  Open <ExternalLink size={10} />
                </a>
              )}
            </div>
            {data.aftermarkets?.available ? (
              <>
                {data.aftermarkets.editorialQuote && (
                  <p className="text-sm text-zinc-300 italic leading-snug mb-2 px-2 border-l-2 border-purple-600/60">
                    "{data.aftermarkets.editorialQuote}"
                  </p>
                )}
                {/* Market view + business score row */}
                <div className="flex items-center gap-3 flex-wrap mb-3">
                  {data.aftermarkets.marketView && (
                    <div>
                      <div className="text-[9px] tracking-widest uppercase text-zinc-500">Market View</div>
                      <div className="text-sm font-medium text-zinc-200">{data.aftermarkets.marketView}</div>
                    </div>
                  )}
                  {data.aftermarkets.businessScore !== null && data.aftermarkets.businessScore !== undefined && (
                    <div className="flex items-center gap-2">
                      <div>
                        <div className="text-[9px] tracking-widest uppercase text-zinc-500">Business Score</div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 text-sm font-mono font-semibold ${scoreColor(data.aftermarkets.businessScore)}`}>
                            {data.aftermarkets.businessScore}/100
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                  {data.aftermarkets.livePrice && (
                    <div>
                      <div className="text-[9px] tracking-widest uppercase text-zinc-500">Live (AM)</div>
                      <div className="text-sm font-mono tabular-nums">₹{fmtNum(data.aftermarkets.livePrice.price)} <span className={colorClass(data.aftermarkets.livePrice.changePercent)}>{fmtPct(data.aftermarkets.livePrice.changePercent)}</span></div>
                    </div>
                  )}
                </div>

                {/* Sub-scores */}
                {data.aftermarkets.subScores && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
                    {Object.entries(data.aftermarkets.subScores).map(([k, v]) => (
                      <div key={k} className="border border-zinc-800/60 p-2 bg-zinc-900/40" data-testid={`am-subscore-${k}`}>
                        <div className="text-[9px] tracking-widest uppercase text-zinc-500 mb-1">{k.replace(/([A-Z])/g, ' $1').trim()}</div>
                        <div className="flex items-baseline gap-2">
                          <span className={`text-xs font-semibold ${ratingColor(v.rating)}`}>{v.rating}</span>
                          <span className="text-lg font-mono tabular-nums text-zinc-200">{v.score}</span>
                        </div>
                        <div className="text-[10px] text-zinc-500 leading-snug mt-1 line-clamp-2">{v.description}</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Safety checks */}
                {data.aftermarkets.safetyChecks && (
                  <div className="border-t border-zinc-800/40 pt-2">
                    <h5 className="text-[9px] tracking-widest uppercase text-zinc-400 mb-1 flex items-center gap-1">
                      <ShieldCheck size={10} /> Safety Checks
                    </h5>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(data.aftermarkets.safetyChecks).map(([k, v]) => (
                        <span key={k} className={`px-1.5 py-0.5 text-[10px] border ${safetyBadge(v)}`} data-testid={`am-safety-${k}`}>
                          {k}: <span className="font-mono">{v}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-start gap-2 text-xs text-zinc-500">
                <ShieldAlert size={12} className="text-amber-400 shrink-0 mt-0.5" />
                <span>{data.aftermarkets?.error || "Aftermarkets unreachable from server. Open link in your browser."}</span>
              </div>
            )}
          </div>

          {/* Trendlyne + StockEdge — blocked, honest UI */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <BlockedSourceCard name="Trendlyne" data={data.trendlyne} testId="trendlyne-card" />
            <BlockedSourceCard name="StockEdge" data={data.stockedge} testId="stockedge-card" />
          </div>
        </div>
      )}
    </Panel>
  );
}

const BlockedSourceCard = ({ name, data, testId }) => (
  <div className="border border-zinc-800/60 p-2.5 bg-zinc-900/30" data-testid={testId}>
    <div className="flex items-center justify-between mb-1">
      <h5 className="text-[10px] tracking-widest uppercase text-zinc-400">{name}</h5>
      <span className="text-[9px] tracking-widest uppercase text-amber-400">Anti-bot blocked</span>
    </div>
    <p className="text-[11px] text-zinc-500 leading-snug mb-2">{data?.reason}</p>
    {data?.url && (
      <a
        href={data.url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 text-[10px] text-blue-400 hover:underline"
      >
        Open {name} in browser <ExternalLink size={10} />
      </a>
    )}
  </div>
);
