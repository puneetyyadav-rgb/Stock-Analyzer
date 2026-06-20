import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Calendar, Loader2 } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const typeColor = (t) => {
  switch (t) {
    case "Earnings": return "text-blue-400 border-blue-700/60";
    case "Dividend": return "text-emerald-400 border-emerald-700/60";
    case "Board Meeting": return "text-amber-400 border-amber-700/60";
    default: return "text-zinc-400 border-zinc-700/60";
  }
};

export default function EventsPanel({ symbol }) {
  const [items, setItems] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setItems(null);
    axios.get(`${API}/stock/${symbol}/events`).then((r) => setItems(r.data.items || [])).catch(() => setItems([]));
  }, [symbol]);

  return (
    <Panel title="Events Calendar" testId="events-panel">
      {items === null && <div className="flex items-center gap-2 text-zinc-500 text-xs"><Loader2 size={12} className="animate-spin" /> Loading…</div>}
      {items && items.length === 0 && (
        <p className="text-xs text-zinc-600">No upcoming events on record. Check NSE corporate-actions for full calendar.</p>
      )}
      {items && items.length > 0 && (
        <ul className="space-y-1.5 max-h-64 overflow-auto pr-1">
          {items.map((e, i) => (
            <li key={i} className={`flex items-center justify-between gap-2 px-2 py-1.5 border-l-2 ${typeColor(e.type)} bg-zinc-900/30`} data-testid={`event-${i}`}>
              <div className="flex items-center gap-2 min-w-0">
                <Calendar size={11} className="shrink-0 text-zinc-500" />
                <span className="text-xs text-zinc-200 truncate">{e.event}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] tracking-widest uppercase text-zinc-500">{e.type}</span>
                <span className="text-xs font-mono text-zinc-300">{e.date}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
