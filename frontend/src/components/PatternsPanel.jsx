import React, { useEffect, useState } from "react";
import { getPatterns } from "../lib/api";
import { Loader2 } from "lucide-react";
import { Panel } from "./Panel";

export default function PatternsPanel({ symbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    getPatterns(symbol)
      .then(setData)
      .catch(() => setData({ patterns: [], note: "Failed to load patterns." }))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <Panel title="Candlestick Patterns (10D)" testId="patterns-panel">
        <div className="flex justify-center py-4">
          <Loader2 size={16} className="animate-spin text-zinc-600" />
        </div>
      </Panel>
    );
  }

  if (!data) return null;

  const { patterns, note } = data;

  return (
    <Panel title="Candlestick Patterns (10D)" testId="patterns-panel">
      {patterns.length === 0 ? (
        <p className="text-xs text-zinc-500 py-2">
          No notable candlestick patterns in the last 10 days.
        </p>
      ) : (
        <div className="space-y-1 mt-1">
          {patterns.map((p, i) => (
            <div key={i} className="flex items-center justify-between border-b border-zinc-800/40 py-1.5">
              <span className="font-mono text-xs text-zinc-400">{p.date}</span>
              <span className="text-xs text-zinc-200">{p.pattern}</span>
              <span
                className={`text-[9px] tracking-widest uppercase px-1.5 py-0.5 rounded-sm border ${
                  p.signal === "Bullish"
                    ? "text-emerald-400 border-emerald-900/50 bg-emerald-950/20"
                    : p.signal === "Bearish"
                    ? "text-red-400 border-red-900/50 bg-red-950/20"
                    : "text-zinc-400 border-zinc-800 bg-zinc-900"
                }`}
              >
                {p.signal}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="text-[9px] text-zinc-600 mt-2 leading-snug">{note}</p>
    </Panel>
  );
}
