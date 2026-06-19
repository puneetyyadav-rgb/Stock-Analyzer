import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import axios from "axios";
import { fmtNum, fmtPct, fmtBigNum, colorClass } from "../lib/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PeersPanel({ symbol, onSelect }) {
  const [peers, setPeers] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setPeers(null);
    axios.get(`${API}/stock/${symbol}/peers`)
      .then((r) => setPeers(r.data.peers || []))
      .catch(() => setPeers([]));
  }, [symbol]);

  return (
    <Panel title="Peer Comparison (Sector)" testId="peers-panel">
      {peers === null && <p className="text-xs text-zinc-500">Loading peers…</p>}
      {peers && peers.length === 0 && <p className="text-xs text-zinc-600">No peer data available</p>}
      {peers && peers.length > 0 && (
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[9px] tracking-widest uppercase text-zinc-500">
                <th className="text-left pb-1.5">Symbol</th>
                <th className="text-right pb-1.5">Price</th>
                <th className="text-right pb-1.5">Chg%</th>
                <th className="text-right pb-1.5">Mkt Cap</th>
                <th className="text-right pb-1.5">P/E</th>
                <th className="text-right pb-1.5">P/B</th>
                <th className="text-right pb-1.5">ROE</th>
                <th className="text-right pb-1.5">Margin</th>
              </tr>
            </thead>
            <tbody>
              {peers.map((p) => (
                <tr
                  key={p.symbol}
                  className="border-t border-zinc-800/40 hover:bg-zinc-900/40 cursor-pointer"
                  onClick={() => onSelect(p.symbol.replace(".NS", ""))}
                  data-testid={`peer-${p.symbol}`}
                >
                  <td className="py-1.5 font-mono text-blue-400">{p.symbol.replace(".NS", "")}</td>
                  <td className="py-1.5 font-mono tabular-nums text-right">₹{fmtNum(p.price)}</td>
                  <td className={`py-1.5 font-mono tabular-nums text-right ${colorClass(p.changePercent)}`}>{fmtPct(p.changePercent)}</td>
                  <td className="py-1.5 font-mono tabular-nums text-right text-zinc-400">{fmtBigNum(p.marketCap)}</td>
                  <td className="py-1.5 font-mono tabular-nums text-right">{fmtNum(p.peRatio)}</td>
                  <td className="py-1.5 font-mono tabular-nums text-right">{fmtNum(p.pbRatio)}</td>
                  <td className="py-1.5 font-mono tabular-nums text-right">{p.roe ? fmtPct(p.roe * 100) : "—"}</td>
                  <td className="py-1.5 font-mono tabular-nums text-right">{p.profitMargin ? fmtPct(p.profitMargin * 100) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
