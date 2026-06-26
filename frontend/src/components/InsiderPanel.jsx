import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import axios from "axios";
import { fmtNum, fmtBigNum } from "../lib/format";
import SourceQA from "./SourceQA";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function InsiderPanel({ symbol }) {
  const [items, setItems] = useState(null);
  const [extData, setExtData] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setItems(null);
    setExtData(null);
    axios.get(`${API}/stock/${symbol}/insider`).then((r) => setItems(r.data.items || [])).catch(() => setItems([]));
    axios.get(`${API}/stock/${symbol}/external-scrape`).then((r) => setExtData(r.data)).catch(() => setExtData({}));
  }, [symbol]);

  const tt = extData?.tickertape || {};
  const promoter = tt?.promoter || {};
  const recentDeals = tt?.recentDeals || [];
  
  const hasItems = items && items.length > 0;
  const hasDeals = recentDeals && recentDeals.length > 0;

  return (
    <Panel title="Insider & Promoter Pledging" testId="insider-panel">
      {items === null && <p className="text-xs text-zinc-500">Loading…</p>}
      
      {promoter.totalPercentage !== undefined && promoter.totalPercentage !== null && (
        <div className="mb-4 flex items-center justify-between p-3 border border-zinc-800/60 bg-zinc-900/30">
          <div>
            <div className="text-[10px] tracking-widest uppercase text-zinc-500 mb-0.5">Promoter Holding</div>
            <div className="text-sm font-medium text-zinc-200">{promoter.totalPercentage.toFixed(2)}%</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] tracking-widest uppercase text-zinc-500 mb-0.5">Shares Pledged</div>
            <div className={`text-sm font-medium ${promoter.pledgedPercentage > 5 ? 'text-red-400' : promoter.pledgedPercentage > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {promoter.pledgedPercentage.toFixed(2)}%
            </div>
          </div>
        </div>
      )}

      {items !== null && !hasItems && !hasDeals && <p className="text-xs text-zinc-600">No insider data on record</p>}
      
      {hasItems && (
        <div className="max-h-72 overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[9px] tracking-widest uppercase text-zinc-500">
                <th className="text-left pb-1">Insider</th>
                <th className="text-left pb-1">Action</th>
                <th className="text-right pb-1">Shares</th>
                <th className="text-right pb-1">Value</th>
                <th className="text-right pb-1">Date</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, i) => {
                const isBuy = (it.transaction || "").toLowerCase().includes("buy") || (it.transaction || "").toLowerCase().includes("purchase");
                return (
                  <tr key={i} className="border-t border-zinc-800/30">
                    <td className="py-1 text-zinc-300 max-w-[140px] truncate">{it.insider}</td>
                    <td className={`py-1 ${isBuy ? "text-emerald-400" : "text-red-400"}`}>{it.transaction}</td>
                    <td className="py-1 font-mono tabular-nums text-right">{fmtNum(it.shares, 0)}</td>
                    <td className="py-1 font-mono tabular-nums text-right">{fmtBigNum(it.value)}</td>
                    <td className="py-1 font-mono text-right text-zinc-500 text-[10px]">{it.date}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!hasItems && hasDeals && (
        <div className="max-h-72 overflow-auto mt-2">
          <div className="text-[10px] uppercase text-zinc-500 mb-2">Recent Deals (Tickertape)</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[9px] tracking-widest uppercase text-zinc-500">
                <th className="text-left pb-1">Party</th>
                <th className="text-left pb-1">Action</th>
                <th className="text-right pb-1">Price</th>
                <th className="text-right pb-1">Date</th>
              </tr>
            </thead>
            <tbody>
              {recentDeals.map((it, i) => {
                const isBuy = (it.type || "").toLowerCase() === "buy";
                return (
                  <tr key={i} className="border-t border-zinc-800/30">
                    <td className="py-1 text-zinc-300 max-w-[140px] truncate">{it.party}</td>
                    <td className={`py-1 ${isBuy ? "text-emerald-400" : "text-red-400"}`}>{it.type}</td>
                    <td className="py-1 font-mono tabular-nums text-right">{fmtNum(it.price)}</td>
                    <td className="py-1 font-mono text-right text-zinc-500 text-[10px]">{new Date(it.date).toLocaleDateString()}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <SourceQA symbol={symbol} sourceName="Insider & Promoter Pledging" data={{ insiderTransactions: items, externalData: extData }} />
    </Panel>
  );
}
