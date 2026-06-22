import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { ExternalLink, Loader2 } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { key: "company", label: "Company" },
  { key: "sector_news", label: "Sector" },
  { key: "market", label: "Market / Misc" },
];

const sentimentColor = (label) => {
  if (label === "Positive") return "text-emerald-400";
  if (label === "Negative") return "text-red-400";
  return "text-zinc-400";
};

export default function NewsSplitPanel({ symbol }) {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("company");

  useEffect(() => {
    if (!symbol) return;
    setData(null);
    setTab("company");
    axios.get(`${API}/stock/${symbol}/news-split`).then((r) => setData(r.data)).catch(() => setData({ company: [], sector_news: [], market: [], counts: {} }));
  }, [symbol]);

  const items = data?.[tab] || [];

  return (
    <Panel
      title="Latest News (Split by Relevance)"
      testId="news-split-panel"
      right={
        data && (
          <div className="flex items-center gap-1" data-testid="news-tabs">
            {TABS.map((t) => {
              const count = data.counts?.[t.key === "sector_news" ? "sector" : t.key] ?? (data[t.key] || []).length;
              const active = tab === t.key;
              return (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  data-testid={`news-tab-${t.key}`}
                  className={`px-2 py-0.5 text-[10px] tracking-widest uppercase font-medium border ${
                    active
                      ? "bg-zinc-100 text-zinc-950 border-zinc-100"
                      : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:border-zinc-600"
                  }`}
                >
                  {t.label} <span className="ml-1 font-mono">{count}</span>
                </button>
              );
            })}
          </div>
        )
      }
    >
      {!data && <div className="flex items-center gap-2 text-zinc-500 text-xs"><Loader2 size={12} className="animate-spin" /> Loading…</div>}
      {data && items.length === 0 && (
        <p className="text-xs text-zinc-600">No {TABS.find((t) => t.key === tab)?.label.toLowerCase()} news at the moment.</p>
      )}
      {data && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-[420px] overflow-auto pr-1">
          {items.map((n, i) => (
            <a
              key={`${tab}-${i}`}
              href={n.url}
              target="_blank"
              rel="noreferrer"
              data-testid={`split-news-${tab}-${i}`}
              className="border border-zinc-800/60 p-2.5 hover:border-zinc-600 transition-colors block group"
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <span className="text-[9px] tracking-widest uppercase text-blue-400">{n.source}</span>
                <ExternalLink size={10} className="text-zinc-600 group-hover:text-zinc-300 mt-0.5 shrink-0" />
              </div>
              <h4 className="text-xs text-zinc-200 font-medium leading-snug mb-1 group-hover:text-blue-300">{n.title}</h4>
              {n.summary && <p className="text-[11px] text-zinc-500 line-clamp-2 leading-snug">{n.summary}</p>}
              <div className="flex items-center justify-between mt-1">
                <span className={`text-[9px] tracking-widest uppercase ${sentimentColor(n.sentimentLabel)}`}>{n.sentimentLabel || "—"}</span>
                {n.publishedAt && <span className="text-[9px] text-zinc-600 font-mono">{n.publishedAt}</span>}
              </div>
            </a>
          ))}
        </div>
      )}
    </Panel>
  );
}
