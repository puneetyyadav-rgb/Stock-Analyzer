import React from "react";
import { Info } from "lucide-react";

// Shared row for a metric key/value pair.
export function Row({ label, value, valueClass = "text-zinc-200" }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-zinc-800/50 text-xs font-mono">
      <span className="text-zinc-400">{label}</span>
      <strong className={valueClass}>{value ?? "—"}</strong>
    </div>
  );
}

// Shared panel wrapper.
export function Panel({ title, icon: Icon, color = "text-emerald-400", note, children }) {
  return (
    <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-lg p-4">
      <div className="flex items-center gap-1.5 mb-3 pb-2 border-b border-zinc-800/60">
        {Icon && <Icon className={`w-4 h-4 ${color}`} />}
        <span className="text-xs font-bold uppercase tracking-wider text-zinc-200">{title}</span>
      </div>
      {children}
      {note && <p className="mt-3 text-[10px] font-mono text-zinc-500 leading-relaxed">{note}</p>}
    </div>
  );
}

// Amber Phase-2 stub list.
export function Phase2List({ stubs }) {
  const entries = Object.entries(stubs || {});
  if (!entries.length) return null;
  return (
    <div className="mt-3 border border-amber-800/50 bg-amber-950/20 rounded-lg p-3">
      <div className="flex items-center gap-1.5 mb-2 text-[10px] font-bold uppercase text-amber-300">
        <Info className="w-3 h-3" /> Requires Phase-2 Data Source
      </div>
      <div className="space-y-1">
        {entries.map(([k, v]) => (
          <div key={k} className="text-[11px] font-mono flex justify-between gap-3">
            <span className="text-amber-300/90">{k}</span>
            <span className="text-zinc-500 text-right">{v?.reason || "Phase 2"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
