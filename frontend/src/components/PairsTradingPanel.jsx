import React, { useEffect, useState } from "react";
import axios from "axios";
import StockSearch from "./StockSearch";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PairsTradingPanel() {
  const [pairs, setPairs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [customA, setCustomA] = useState("ZOMATO");
  const [customB, setCustomB] = useState("PAYTM");
  const [customResult, setCustomResult] = useState(null);
  const [customLoading, setCustomLoading] = useState(false);
  const [customErr, setCustomErr] = useState("");
  const [filterSector, setFilterSector] = useState("All");

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

  const handleScanCustom = async () => {
    if (!customA || !customB) {
      setCustomErr("Please select both Symbol A and Symbol B.");
      return;
    }
    setCustomErr("");
    setCustomLoading(true);
    setCustomResult(null);
    try {
      const res = await axios.get(`${API}/quant/pairs/custom`, {
        params: { symA: customA, symB: customB }
      });
      if (res.data?.error) {
        setCustomErr(res.data.error);
      } else {
        setCustomResult(res.data);
      }
    } catch (e) {
      setCustomErr("Failed to evaluate custom pair cointegration.");
    }
    setCustomLoading(false);
  };

  const uniqueSectors = ["All", ...new Set(pairs.map(p => p.sector))];
  const filteredPairs = filterSector === "All" ? pairs : pairs.filter(p => p.sector === filterSector);

  const renderPairCard = (p, idx, isCustom = false) => {
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
              {p.sector} {isCustom && " (Custom)"}
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
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide">
              Statistical Arbitrage Cointegration Scanner
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Engle-Granger ADF cointegration test & Ornstein-Uhlenbeck AR(1) half-life mean-reversion scanner across ALL Indian market sector peers.
            </p>
          </div>
          <span className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold rounded-full animate-pulse">
            LIVE ENGINE
          </span>
        </div>

        {/* Custom Pair Tester Bar */}
        <div className="mt-6 p-4 bg-black/50 rounded-xl border border-purple-500/30 space-y-3">
          <span className="text-xs font-bold text-purple-300 uppercase tracking-wider block">
            ⚡ Test ANY Custom Indian Market Pair on Demand
          </span>
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
            <div className="md:col-span-4">
              <label className="text-[10px] font-bold text-zinc-400 block mb-1">Symbol A (Long/Short Leg):</label>
              <StockSearch initial={customA} onSelect={(s) => setCustomA(s.replace(".NS", "").replace(".BO", ""))} />
            </div>
            <div className="md:col-span-1 text-center font-black text-zinc-500 text-lg">VS</div>
            <div className="md:col-span-4">
              <label className="text-[10px] font-bold text-zinc-400 block mb-1">Symbol B (Short/Long Leg):</label>
              <StockSearch initial={customB} onSelect={(s) => setCustomB(s.replace(".NS", "").replace(".BO", ""))} />
            </div>
            <div className="md:col-span-3 pt-4 md:pt-5">
              <button
                onClick={handleScanCustom}
                disabled={customLoading}
                className="w-full py-2.5 px-4 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-bold text-xs rounded-lg shadow-lg shadow-purple-950/50 transition-all flex items-center justify-center gap-2"
              >
                {customLoading ? "Scanning..." : "⚡ Scan Custom Pair"}
              </button>
            </div>
          </div>
          {customErr && <div className="text-rose-400 text-xs font-medium p-2 bg-rose-950/30 rounded border border-rose-800">{customErr}</div>}
          {customResult && (
            <div className="mt-4 pt-3 border-t border-zinc-800">
              {renderPairCard(customResult, "custom-0", true)}
            </div>
          )}
        </div>

        {/* Sector Filters */}
        <div className="mt-6 flex flex-wrap gap-1.5 border-b border-zinc-800 pb-3">
          {uniqueSectors.map((sec) => (
            <button
              key={sec}
              onClick={() => setFilterSector(sec)}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                filterSector === sec
                  ? "bg-purple-600/30 text-purple-200 border border-purple-500"
                  : "bg-zinc-950 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
              }`}
            >
              {sec} ({sec === "All" ? pairs.length : pairs.filter(p => p.sector === sec).length})
            </button>
          ))}
        </div>

        {loading ? (
          <div className="py-12 text-center text-zinc-500 text-sm animate-pulse">
            Scanning NSE peer clusters across Indian market for cointegrated pairs...
          </div>
        ) : filteredPairs.length === 0 ? (
          <div className="py-12 text-center text-zinc-500 text-sm">
            No pairs found in this sector category.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
            {filteredPairs.map((p, idx) => renderPairCard(p, idx))}
          </div>
        )}
      </div>
    </div>
  );
}

