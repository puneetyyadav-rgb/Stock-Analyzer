import React, { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PairsTradingPanel() {
  const [pairs, setPairs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/quant/pairs`)
      .then((r) => {
        setPairs(r.data?.pairs || []);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide">
              Statistical Arbitrage Cointegration Scanner
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Engle-Granger ADF cointegration test & Ornstein-Uhlenbeck AR(1) half-life mean-reversion scanner across NSE sector peers.
            </p>
          </div>
          <span className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold rounded-full animate-pulse">
            LIVE ENGINE
          </span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-zinc-500 text-sm animate-pulse">
            Scanning NSE peer clusters for cointegrated pairs...
          </div>
        ) : pairs.length === 0 ? (
          <div className="py-12 text-center text-zinc-500 text-sm">
            No cointegrated pairs found right now.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
            {pairs.map((p, idx) => {
              const isSignal = p.signal !== "NEUTRAL" && p.signal !== "CONVERGED_CLOSE";
              return (
                <div
                  key={idx}
                  className={`p-5 rounded-xl border transition-all duration-200 ${
                    p.cointegrated
                      ? "bg-zinc-900/90 border-purple-500/40 shadow-lg shadow-purple-950/20"
                      : "bg-zinc-950/60 border-zinc-800/80 opacity-75"
                  }`}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <span className="text-xs font-semibold tracking-wider text-purple-400 uppercase">
                        {p.sector}
                      </span>
                      <h3 className="text-base font-bold text-white mt-0.5">
                        {p.pair}
                      </h3>
                    </div>
                    {p.cointegrated ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 border border-purple-500/40 text-purple-300">
                        p={p.pValue}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-zinc-800 text-zinc-400">
                        No Cointegration
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2 my-4 text-xs bg-black/40 p-3 rounded-lg border border-zinc-800/60">
                    <div>
                      <span className="text-zinc-500 block">Hedge Ratio (β)</span>
                      <span className="text-zinc-200 font-mono font-bold">{p.beta}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block">ADF t-Stat</span>
                      <span className="text-zinc-200 font-mono">{p.tStat}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block">Half-Life</span>
                      <span className="text-zinc-200 font-mono font-bold">
                        {p.halfLifeDays < 900 ? `${p.halfLifeDays}d` : "N/A"}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block">Spread Z-Score</span>
                      <span
                        className={`font-mono font-bold ${
                          p.currentSpreadZ <= -2.0
                            ? "text-emerald-400"
                            : p.currentSpreadZ >= 2.0
                            ? "text-rose-400"
                            : "text-zinc-300"
                        }`}
                      >
                        {p.currentSpreadZ > 0 ? `+${p.currentSpreadZ}` : p.currentSpreadZ}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-zinc-800/80 flex items-center justify-between">
                    <div className="text-[11px] text-zinc-400">
                      <span>{p.symbolA.replace(".NS", "")}: ₹{p.lastPriceA}</span>
                      <span className="mx-1.5 text-zinc-600">|</span>
                      <span>{p.symbolB.replace(".NS", "")}: ₹{p.lastPriceB}</span>
                    </div>
                    {isSignal ? (
                      <span
                        className={`px-2.5 py-1 rounded text-xs font-bold border animate-pulse ${
                          p.signal === "BUY_A_SELL_B"
                            ? "bg-emerald-500/20 border-emerald-500 text-emerald-300"
                            : "bg-rose-500/20 border-rose-500 text-rose-300"
                        }`}
                      >
                        {p.signal === "BUY_A_SELL_B" ? "BUY A / SELL B" : "SELL A / BUY B"}
                      </span>
                    ) : (
                      <span className="text-[11px] font-medium text-zinc-500">
                        {p.signal === "CONVERGED_CLOSE" ? "Converged" : "Neutral Spread"}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
