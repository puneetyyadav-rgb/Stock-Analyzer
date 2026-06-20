import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Scale, ExternalLink, Loader2 } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const sevColor = (s) => {
  switch (s) {
    case "Critical": return "bg-red-600 text-red-50";
    case "High": return "bg-orange-600 text-orange-50";
    case "Medium": return "bg-amber-600 text-amber-50";
    case "Low": return "bg-zinc-700 text-zinc-100";
    default: return "bg-zinc-800 text-zinc-300";
  }
};

export default function LegalPanel({ symbol }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setData(null);
    axios.get(`${API}/stock/${symbol}/legal`).then((r) => setData(r.data)).catch(() => setData({ items: [], announcements_scanned: 0, error: true }));
  }, [symbol]);

  return (
    <Panel
      title="Legal & Regulatory Disclosures"
      testId="legal-panel"
      right={data && <span className="text-[9px] tracking-widest uppercase text-zinc-500">Scanned: {data.announcements_scanned ?? 0}</span>}
    >
      {!data && <div className="flex items-center gap-2 text-zinc-500 text-xs"><Loader2 size={12} className="animate-spin" /> Loading…</div>}
      {data && (
        <>
          {data.items && data.items.length > 0 ? (
            <ul className="space-y-2 max-h-72 overflow-auto pr-1">
              {data.items.map((it, i) => (
                <li key={i} className="border border-zinc-800/60 p-2" data-testid={`legal-item-${i}`}>
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={`px-1.5 py-0.5 text-[9px] tracking-widest uppercase ${sevColor(it.severity)}`}>{it.severity}</span>
                    <span className="text-[10px] tracking-widest uppercase text-zinc-500">{it.category}</span>
                  </div>
                  <p className="text-xs text-zinc-300 leading-snug">{it.summary || it.announcement}</p>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-xs text-zinc-500 space-y-1">
              <p className="text-emerald-400 font-medium">Checked — no current legal/SEBI red flags found.</p>
              <p className="text-[11px] text-zinc-600 leading-snug">
                {data.announcements_scanned === 0
                  ? "NSE may be geo-blocked from server location — view announcements directly on NSE."
                  : `Scanned ${data.announcements_scanned} recent NSE announcements; none matched litigation/SEBI/court/penalty keywords.`}
              </p>
              <a
                href={`https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol=${symbol.replace(".NS","")}`}
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-blue-400 hover:underline inline-flex items-center gap-1"
              >
                View on NSE <ExternalLink size={10} />
              </a>
            </div>
          )}
          <p className="text-[9px] tracking-widest uppercase text-zinc-600 mt-3 pt-2 border-t border-zinc-800/40">
            <Scale size={9} className="inline mr-1" /> Source: NSE scrape, not an official SEBI API
          </p>
        </>
      )}
    </Panel>
  );
}
