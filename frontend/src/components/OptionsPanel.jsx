import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import axios from "axios";
import { fmtNum, fmtBigNum } from "../lib/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OptionsPanel({ symbol }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setData(null);
    axios.get(`${API}/stock/${symbol}/options`).then((r) => setData(r.data)).catch(() => setData({ available: false }));
  }, [symbol]);

  if (!data) return <Panel title="Options Chain & PCR (NSE)" testId="options-panel"><p className="text-xs text-zinc-500">Loading…</p></Panel>;

  if (!data.available) {
    return (
      <Panel title="Options Chain & PCR (NSE)" testId="options-panel">
        <div className="text-xs text-zinc-500 space-y-1">
          <p className="text-amber-400 font-medium">Options chain temporarily unavailable</p>
          <p className="text-zinc-600 leading-snug">{data.reason || data.error || "NSE rate limit / geo-block."} Direct options chain access requires India IP. Visit <a href={`https://www.nseindia.com/option-chain?symbol=${symbol.replace(".NS","")}`} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">NSE Option Chain</a> for live data.</p>
        </div>
      </Panel>
    );
  }

  return (
    <Panel title={`Options Chain · ${data.expiry || ""}`} testId="options-panel">
      <div className="flex items-center gap-4 mb-2 flex-wrap">
        <div>
          <div className="text-[9px] tracking-widest uppercase text-zinc-500">Underlying</div>
          <div className="text-sm font-mono tabular-nums">₹{fmtNum(data.underlying)}</div>
        </div>
        <div>
          <div className="text-[9px] tracking-widest uppercase text-zinc-500">PCR</div>
          <div className={`text-sm font-mono tabular-nums ${data.pcr > 1 ? "text-emerald-400" : "text-red-400"}`}>{fmtNum(data.pcr, 2)}</div>
        </div>
        <div>
          <div className="text-[9px] tracking-widest uppercase text-zinc-500">CE Tot OI</div>
          <div className="text-sm font-mono tabular-nums">{fmtBigNum(data.ceTotalOI)}</div>
        </div>
        <div>
          <div className="text-[9px] tracking-widest uppercase text-zinc-500">PE Tot OI</div>
          <div className="text-sm font-mono tabular-nums">{fmtBigNum(data.peTotalOI)}</div>
        </div>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[9px] tracking-widest uppercase text-zinc-500">
            <th className="text-right py-1 text-emerald-400">CE OI</th>
            <th className="text-right py-1 text-emerald-400">CE LTP</th>
            <th className="text-center py-1">Strike</th>
            <th className="text-right py-1 text-red-400">PE LTP</th>
            <th className="text-right py-1 text-red-400">PE OI</th>
          </tr>
        </thead>
        <tbody>
          {(data.rows || []).map((r) => {
            const isATM = data.underlying && Math.abs(r.strike - data.underlying) === Math.min(...data.rows.map(x => Math.abs(x.strike - data.underlying)));
            return (
              <tr key={r.strike} className={`border-t border-zinc-800/30 ${isATM ? "bg-blue-900/20" : ""}`}>
                <td className="py-1 font-mono tabular-nums text-right">{fmtBigNum(r.ceOI)}</td>
                <td className="py-1 font-mono tabular-nums text-right">{fmtNum(r.ceLTP)}</td>
                <td className="py-1 font-mono tabular-nums text-center font-medium">{fmtNum(r.strike, 0)}</td>
                <td className="py-1 font-mono tabular-nums text-right">{fmtNum(r.peLTP)}</td>
                <td className="py-1 font-mono tabular-nums text-right">{fmtBigNum(r.peOI)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
