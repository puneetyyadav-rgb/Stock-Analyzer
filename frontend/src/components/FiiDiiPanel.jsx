import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Bar, BarChart, ReferenceLine } from "recharts";
import { fmtNum, fmtPct, colorClass } from "../lib/format";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function FiiDiiPanel() {
  const [rows, setRows] = useState(null);

  useEffect(() => {
    axios.get(`${API}/fii-dii`).then((r) => setRows(r.data.rows || [])).catch(() => setRows([]));
  }, []);

  const chart = (rows || []).slice(0, 10).reverse().map((r) => ({
    date: r.date?.slice(5) || "",
    FII: r.fiiCash,
    DII: r.diiCash,
  }));

  return (
    <Panel title="FII / DII Cash Flows (₹ Cr) · Moneycontrol" testId="fii-dii-panel">
      {!rows && <p className="text-xs text-zinc-500">Loading…</p>}
      {rows && rows.length === 0 && <p className="text-xs text-zinc-600">Data unavailable</p>}
      {rows && rows.length > 0 && (
        <>
          <div className="h-32 mb-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart}>
                <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 9, fontFamily: "JetBrains Mono" }} stroke="#27272a" />
                <YAxis tick={{ fill: "#71717a", fontSize: 9, fontFamily: "JetBrains Mono" }} stroke="#27272a" width={45} />
                <ReferenceLine y={0} stroke="#3f3f46" />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0c0c0e", border: "1px solid #27272a", fontSize: 11, fontFamily: "JetBrains Mono" }}
                  formatter={(v) => Number(v).toFixed(0)}
                />
                <Bar dataKey="FII" fill="#3b82f6" />
                <Bar dataKey="DII" fill="#a855f7" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-3 mb-2 text-[10px] tracking-widest uppercase">
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-blue-500" />FII</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-purple-500" />DII</span>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[9px] tracking-widest uppercase text-zinc-500">
                <th className="text-left pb-1">Date</th>
                <th className="text-right pb-1">FII</th>
                <th className="text-right pb-1">DII</th>
                <th className="text-right pb-1">Nifty %</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 7).map((r) => (
                <tr key={r.date} className="border-t border-zinc-800/40">
                  <td className="py-1 font-mono text-zinc-300">{r.date?.slice(5) || ""}</td>
                  <td className={`py-1 font-mono tabular-nums text-right ${colorClass(r.fiiCash)}`}>{fmtNum(r.fiiCash, 0)}</td>
                  <td className={`py-1 font-mono tabular-nums text-right ${colorClass(r.diiCash)}`}>{fmtNum(r.diiCash, 0)}</td>
                  <td className={`py-1 font-mono tabular-nums text-right ${colorClass(r.niftyChangePct)}`}>{fmtPct(r.niftyChangePct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Panel>
  );
}
