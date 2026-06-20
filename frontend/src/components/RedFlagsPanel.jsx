import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { AlertTriangle, ExternalLink, Loader2, ShieldAlert } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const sevColor = (s) => {
  switch (s) {
    case "Critical": return "bg-red-600 text-red-50 border-red-500";
    case "High": return "bg-orange-600 text-orange-50 border-orange-500";
    case "Medium": return "bg-amber-700 text-amber-50 border-amber-600";
    case "Low": return "bg-zinc-700 text-zinc-100 border-zinc-600";
    default: return "bg-zinc-800 text-zinc-300 border-zinc-700";
  }
};

export default function RedFlagsPanel({ symbol }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setData(null);
    axios.get(`${API}/stock/${symbol}/red-flags`).then((r) => setData(r.data)).catch(() => setData({ items: [] }));
  }, [symbol]);

  const hasCritical = (data?.items || []).some((f) => f.severity === "Critical" || f.severity === "High");

  return (
    <Panel
      title={<><ShieldAlert size={11} className="inline mr-1" /> Red Flags</>}
      testId="redflags-panel"
      className={hasCritical ? "border-red-700" : ""}
    >
      {!data && <div className="flex items-center gap-2 text-zinc-500 text-xs"><Loader2 size={12} className="animate-spin" /> Aggregating…</div>}
      {data && (
        <>
          {(data.items || []).length === 0 && (
            <p className="text-xs text-emerald-400">No red flags detected — Screener cons clean, no SEBI/court keywords, no promoter pledge data.</p>
          )}
          {(data.items || []).length > 0 && (
            <ul className="space-y-2 max-h-80 overflow-auto pr-1">
              {data.items.map((f, i) => (
                <li key={i} className={`border-l-2 p-2 bg-zinc-900/30 ${sevColor(f.severity).split(" ").pop()}`} data-testid={`flag-${i}`}>
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={`px-1.5 py-0.5 text-[9px] tracking-widest uppercase ${sevColor(f.severity)}`}>{f.severity}</span>
                    <span className="text-[10px] tracking-widest uppercase text-zinc-500">{f.category}</span>
                    <span className="text-[9px] text-zinc-600">· {f.source}</span>
                  </div>
                  <p className="text-xs text-zinc-300 leading-snug flex items-start gap-1.5">
                    <AlertTriangle size={11} className="text-amber-400 mt-0.5 shrink-0" />
                    <span>{f.summary}</span>
                    {f.url && (
                      <a href={f.url} target="_blank" rel="noreferrer" className="text-blue-400">
                        <ExternalLink size={10} />
                      </a>
                    )}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {data.promoterPledge !== null && data.promoterPledge !== undefined && (
            <div className="mt-3 pt-3 border-t border-zinc-800/40 flex items-center justify-between">
              <span className="text-[10px] tracking-widest uppercase text-zinc-500">Promoter Pledge</span>
              <span className={`text-sm font-mono ${data.promoterPledge >= 25 ? "text-red-400" : data.promoterPledge >= 10 ? "text-amber-400" : "text-emerald-400"}`}>{data.promoterPledge}%</span>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
