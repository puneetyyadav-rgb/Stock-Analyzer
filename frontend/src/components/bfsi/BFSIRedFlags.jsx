import React, { useState } from "react";
import { AlertOctagon, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { Panel } from "./_bfsiShared";

const SEV = {
  SEVERE: { icon: AlertOctagon, cls: "text-red-400", badge: "bg-red-950/60 text-red-300 border-red-800/60" },
  WARNING: { icon: AlertTriangle, cls: "text-amber-400", badge: "bg-amber-950/60 text-amber-300 border-amber-800/60" },
  INFO: { icon: Info, cls: "text-cyan-400", badge: "bg-cyan-950/60 text-cyan-300 border-cyan-800/60" },
};

export default function BFSIRedFlags({ data }) {
  const [showAll, setShowAll] = useState(false);
  if (!data) return null;
  const flags = data.flags || [];
  const visible = showAll ? flags : flags.filter((f) => f.triggered);

  return (
    <Panel
      title="Banking-Specific Forensic & Credit Risk Indicators"
      icon={AlertOctagon}
      color="text-red-400"
      note="16 banking-specific triggers on asset quality, margin, funding, capital and valuation. Distinct from industrial forensic red flags."
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-zinc-400">
          Triggered: <strong className={data.triggeredCount > 0 ? "text-red-400" : "text-emerald-400"}>{data.triggeredCount || 0}</strong>
          {"  "}· Severe: <strong className={data.severeCount > 0 ? "text-red-400" : "text-emerald-400"}>{data.severeCount || 0}</strong>
        </span>
        <button
          onClick={() => setShowAll((s) => !s)}
          className="text-[10px] font-mono px-2.5 py-1 rounded border border-zinc-700 text-zinc-300 hover:border-emerald-600 hover:text-emerald-300 transition-all"
        >
          {showAll ? "Show Triggered Only" : "Show All 16"}
        </button>
      </div>

      {visible.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-emerald-300 py-4">
          <CheckCircle2 className="w-4 h-4" /> No banking red flags triggered on the available data.
        </div>
      )}

      <div className="space-y-2">
        {visible.map((f) => {
          const sev = SEV[f.severity] || SEV.INFO;
          const Icon = sev.icon;
          return (
            <div key={f.id} className={`border rounded-lg p-3 ${f.triggered ? "border-zinc-700 bg-zinc-900/40" : "border-zinc-800/60 bg-zinc-950/40 opacity-70"}`}>
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-semibold text-zinc-200 flex items-center gap-2">
                  <Icon className={`w-3.5 h-3.5 ${f.triggered ? sev.cls : "text-zinc-600"}`} /> {f.name}
                </span>
                <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded border ${f.triggered ? sev.badge : "bg-zinc-800 text-zinc-400 border-zinc-700"}`}>
                  {f.triggered ? f.severity : f.available === false ? "N/A" : "Clear"}
                </span>
              </div>
              {f.triggered && f.alert && <p className="mt-2 text-[11px] font-mono text-zinc-300 leading-relaxed">{f.alert}</p>}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
