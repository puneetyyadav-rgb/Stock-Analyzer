import React, { useEffect, useState, useRef } from "react";
import { Panel } from "./Panel";
import { getMarketDepth } from "../lib/api";
import { Loader2, AlertCircle, Activity } from "lucide-react";

export default function MarketDepthPanel({ symbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  
  // Use a ref to store the interval so we can clear it
  const intervalRef = useRef(null);

  const fetchDepth = async () => {
    try {
      const res = await getMarketDepth(symbol);
      setData(res);
      setErr(null);
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || "Failed to fetch market depth");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    fetchDepth();

    // Poll every 5 seconds for "live" feel
    intervalRef.current = setInterval(fetchDepth, 5000);

    return () => clearInterval(intervalRef.current);
  }, [symbol]);

  return (
    <Panel title="Market Depth (Level 2)" testId="market-depth-panel" className="h-full">
      {loading && !data && (
        <div className="flex justify-center py-10">
          <Loader2 className="animate-spin text-zinc-500" size={24} />
        </div>
      )}

      {err && (
        <div className="flex items-start gap-2 p-3 bg-red-950/40 border border-red-900/60 text-red-300 text-xs">
          <AlertCircle size={14} className="shrink-0 mt-0.5" /> <span>{err}</span>
        </div>
      )}

      {data && !err && (
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] tracking-widest uppercase text-emerald-500 font-bold">Live</span>
            </div>
            <div className="text-right">
              <div className="text-[10px] tracking-widest uppercase text-zinc-500">LTP</div>
              <div className="text-lg font-mono font-medium text-zinc-100">₹{data.ltp !== undefined && data.ltp !== null ? Number(data.ltp).toFixed(2) : "—"}</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            {/* Bids (Buyers) */}
            <div>
              <div className="grid grid-cols-3 gap-1 mb-2 text-[10px] tracking-widest uppercase text-zinc-500 border-b border-zinc-800 pb-1">
                <div className="text-right">Qty</div>
                <div className="text-right">Orders</div>
                <div className="text-right text-emerald-400">Bid</div>
              </div>
              <div className="space-y-1">
                {data.bids?.map((b, i) => (
                  <div key={i} className="grid grid-cols-3 gap-1 hover:bg-zinc-800/50 cursor-default">
                    <div className="text-right text-zinc-300">{b.quantity}</div>
                    <div className="text-right text-zinc-500">{b.orders}</div>
                    <div className="text-right text-emerald-400 font-medium">₹{b.price !== undefined && b.price !== null ? Number(b.price).toFixed(2) : "-"}</div>
                  </div>
                ))}
                {(!data.bids || data.bids.length === 0) && (
                  <div className="col-span-3 text-center text-zinc-600 py-2">No Bids</div>
                )}
              </div>
            </div>

            {/* Asks (Sellers) */}
            <div>
              <div className="grid grid-cols-3 gap-1 mb-2 text-[10px] tracking-widest uppercase text-zinc-500 border-b border-zinc-800 pb-1">
                <div className="text-left text-red-400">Ask</div>
                <div className="text-left">Orders</div>
                <div className="text-left">Qty</div>
              </div>
              <div className="space-y-1">
                {data.asks?.map((a, i) => (
                  <div key={i} className="grid grid-cols-3 gap-1 hover:bg-zinc-800/50 cursor-default">
                    <div className="text-left text-red-400 font-medium">₹{a.price !== undefined && a.price !== null ? Number(a.price).toFixed(2) : "-"}</div>
                    <div className="text-left text-zinc-500">{a.orders}</div>
                    <div className="text-left text-zinc-300">{a.quantity}</div>
                  </div>
                ))}
                {(!data.asks || data.asks.length === 0) && (
                  <div className="col-span-3 text-center text-zinc-600 py-2">No Asks</div>
                )}
              </div>
            </div>
          </div>
          
          <div className="text-[9px] text-zinc-600 tracking-widest uppercase text-center mt-2 flex items-center justify-center gap-1">
            <Activity size={10} /> Data via Kotak Neo API
          </div>
        </div>
      )}
    </Panel>
  );
}
