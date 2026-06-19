import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { getMacro, getSectors } from "../lib/api";
import { fmtNum, fmtPct, colorClass } from "../lib/format";

export default function MacroPanel() {
  const [macro, setMacro] = useState(null);
  const [sectors, setSectors] = useState(null);

  useEffect(() => {
    getMacro().then(setMacro).catch(() => {});
    getSectors().then((d) => setSectors(d.sectors)).catch(() => {});
  }, []);

  return (
    <>
      <Panel title="Macro Snapshot" testId="macro-panel">
        <div className="grid grid-cols-2 gap-x-3">
          {(macro?.indicators || []).map((ind) => (
            <div key={ind.symbol} className="flex items-center justify-between py-1 border-b border-zinc-800/40">
              <span className="text-[10px] tracking-widest uppercase text-zinc-500">{ind.name}</span>
              <div className="text-right">
                <div className="text-xs font-mono tabular-nums">{fmtNum(ind.price)}</div>
                <div className={`text-[10px] font-mono tabular-nums ${colorClass(ind.changePercent)}`}>
                  {fmtPct(ind.changePercent)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Sector Heatmap (NSE)" testId="sector-panel">
        <div className="grid grid-cols-2 gap-1">
          {(sectors || []).map((s) => {
            const pct = s.changePercent || 0;
            const bg =
              pct > 2 ? "bg-emerald-900/60" :
              pct > 0 ? "bg-emerald-900/30" :
              pct < -2 ? "bg-red-900/60" :
              pct < 0 ? "bg-red-900/30" : "bg-zinc-900/40";
            return (
              <div key={s.symbol} className={`flex justify-between items-center px-2 py-1.5 border border-zinc-800/40 ${bg}`}>
                <span className="text-[11px] font-medium text-zinc-200">{s.name}</span>
                <span className={`text-[11px] font-mono tabular-nums ${colorClass(pct)}`}>{fmtPct(pct)}</span>
              </div>
            );
          })}
        </div>
      </Panel>
    </>
  );
}
