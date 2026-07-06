import React, { useState } from "react";
import axios from "axios";
import StockSearch from "./StockSearch";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STOCK_CATEGORIES = {
  "Banking & NBFC": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "BAJFINANCE", "CHOLAFIN", "IDFCFIRSTB", "AUBANK"],
  "IT & Tech": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "PERSISTENT", "COFORGE", "ZOMATO"],
  "Energy & Power": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "TATAPOWER", "COALINDIA", "BPCL", "IOC"],
  "Auto & EV": ["TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "EICHERMOT", "TVSMOTOR", "HEROMOTOCO", "BOSCHLTD"],
  "Pharma & Healthcare": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN", "AUROPHARMA", "APOLLOHOSP", "MAXHEALTH"],
  "Metals, Cement & Infra": ["LT", "TATASTEEL", "JSWSTEEL", "HINDALCO", "ULTRACEMCO", "GRASIM", "HAL", "BEL", "ABB"]
};

export default function PortfolioAllocPanel() {
  const [selected, setSelected] = useState(["RELIANCE", "TCS", "HDFCBANK", "TATAMOTORS"]);
  const [activeCategory, setActiveCategory] = useState("Banking & NBFC");
  const [capital, setCapital] = useState(1000000);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const toggleTicker = (t) => {
    if (selected.includes(t)) {
      setSelected(selected.filter((s) => s !== t));
    } else {
      setSelected([...selected, t]);
    }
  };

  const addCustomTicker = (sym) => {
    const clean = sym.replace(".NS", "").replace(".BO", "").toUpperCase();
    if (clean && !selected.includes(clean)) {
      setSelected([...selected, clean]);
    }
  };

  const removeTicker = (t) => {
    setSelected(selected.filter((s) => s !== t));
  };

  const handleBuild = async () => {
    if (selected.length < 2) {
      setErr("Please select at least 2 tickers to construct a portfolio.");
      return;
    }
    setErr("");
    setLoading(true);
    try {
      const res = await axios.post(`${API}/quant/portfolio`, {
        symbols: selected,
        capital: Number(capital) || 1000000,
      });
      if (res.data?.error) {
        setErr(res.data.error);
      } else {
        setResult(res.data);
      }
    } catch (e) {
      setErr("Failed to calculate HRP portfolio.");
    }
    setLoading(false);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide">
              Hierarchical Risk Parity (HRP) & Kelly Allocator
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Marcos López de Prado's correlation distance tree clustering & recursive inverse-variance position sizing.
            </p>
          </div>
          <span className="px-3 py-1 bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs font-semibold rounded-full">
            INSTITUTIONAL HRP
          </span>
        </div>

        <div className="mt-6 p-4 bg-black/40 rounded-xl border border-zinc-800/80 space-y-4">
          <div>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
              <label className="text-xs font-semibold text-zinc-300">
                1. Add ANY Indian Stock to Watchlist:
              </label>
              <div className="w-full md:w-72">
                <StockSearch onSelect={addCustomTicker} />
              </div>
            </div>

            <div className="mb-4 p-3 bg-zinc-950/60 rounded-lg border border-zinc-800">
              <span className="text-xs font-semibold text-purple-300 block mb-2">
                Currently Selected Universe ({selected.length} stocks):
              </span>
              <div className="flex flex-wrap gap-2">
                {selected.length === 0 && <span className="text-xs text-zinc-500 italic">No stocks selected yet.</span>}
                {selected.map((t) => (
                  <span key={t} className="inline-flex items-center gap-1.5 px-3 py-1 bg-purple-900/40 border border-purple-500/50 text-purple-200 text-xs font-bold rounded-lg shadow-sm">
                    {t}
                    <button onClick={() => removeTicker(t)} className="text-purple-400 hover:text-white font-black ml-1">
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <label className="text-xs font-semibold text-zinc-300 block mb-2">
              2. Or Quick-Select from Major Indian Market Sectors:
            </label>
            <div className="flex flex-wrap gap-1.5 mb-3 border-b border-zinc-800 pb-3">
              {Object.keys(STOCK_CATEGORIES).map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                    activeCategory === cat
                      ? "bg-zinc-800 text-white border border-zinc-600"
                      : "bg-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              {STOCK_CATEGORIES[activeCategory].map((t) => {
                const active = selected.includes(t);
                return (
                  <button
                    key={t}
                    onClick={() => toggleTicker(t)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
                      active
                        ? "bg-purple-600/30 border-purple-500 text-purple-200 shadow-md shadow-purple-950/40"
                        : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700"
                    }`}
                  >
                    {active ? "✓ " : "+ "}{t}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pt-2 border-t border-zinc-800/60">
            <div className="flex items-center gap-3">
              <label className="text-xs font-semibold text-zinc-300">
                Total Portfolio Capital (₹):
              </label>
              <input
                type="number"
                step="50000"
                value={capital}
                onChange={(e) => setCapital(e.target.value)}
                className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm font-mono text-white focus:outline-none focus:border-purple-500 w-40"
              />
            </div>
            <button
              onClick={handleBuild}
              disabled={loading || selected.length < 2}
              className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold px-6 py-2 rounded-lg shadow-lg transition-all disabled:opacity-50"
            >
              {loading ? "Calculating Clusters..." : "Generate HRP Allocation"}
            </button>
          </div>
          {err && <p className="text-xs text-rose-400 font-medium">{err}</p>}
        </div>

        {result && (
          <div className="mt-8 space-y-6 animate-fadeIn">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-zinc-950/80 p-4 rounded-xl border border-zinc-800">
                <span className="text-xs text-zinc-400 block">HRP Annual Volatility</span>
                <span className="text-2xl font-bold font-mono text-emerald-400">
                  {result.hrpMetrics.volatilityPct}%
                </span>
                <span className="text-[11px] text-zinc-500 block mt-1">
                  vs {result.eqMetrics.volatilityPct}% Equal-Weight ({result.volReductionPct}% Reduction)
                </span>
              </div>

              <div className="bg-zinc-950/80 p-4 rounded-xl border border-zinc-800">
                <span className="text-xs text-zinc-400 block">HRP Sharpe Ratio</span>
                <span className="text-2xl font-bold font-mono text-purple-300">
                  {result.hrpMetrics.sharpeRatio}
                </span>
                <span className="text-[11px] text-zinc-500 block mt-1">
                  Expected Return: {result.hrpMetrics.expectedReturnPct}% / yr
                </span>
              </div>

              <div className="bg-zinc-950/80 p-4 rounded-xl border border-zinc-800">
                <span className="text-xs text-zinc-400 block">Fractional Kelly Recommended Sizing</span>
                <span className="text-2xl font-bold font-mono text-indigo-300">
                  ₹{(result.recommendedCapital / 100000).toFixed(2)} Lakhs
                </span>
                <span className="text-[11px] text-zinc-500 block mt-1">
                  ({result.fractionalKellyPct}% of Total Capital Allocation)
                </span>
              </div>
            </div>

            <div className="bg-black/50 border border-zinc-800/80 rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b border-zinc-800 bg-zinc-900/50">
                <h3 className="text-sm font-bold text-white">
                  Hierarchical Cluster Optimal Share Allocations
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-400 bg-zinc-950">
                      <th className="py-3 px-4 font-semibold">Ticker</th>
                      <th className="py-3 px-4 font-semibold">HRP Weight</th>
                      <th className="py-3 px-4 font-semibold">Equal Weight</th>
                      <th className="py-3 px-4 font-semibold">Latest Price</th>
                      <th className="py-3 px-4 font-semibold">Recommended Shares</th>
                      <th className="py-3 px-4 font-semibold">Allocated Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60 font-mono">
                    {result.allocations.map((a, i) => (
                      <tr key={i} className="hover:bg-zinc-900/40">
                        <td className="py-3 px-4 font-bold text-white font-sans">{a.symbol}</td>
                        <td className="py-3 px-4 text-purple-400 font-bold">{a.weightPercent}%</td>
                        <td className="py-3 px-4 text-zinc-500">{a.eqWeightPercent}%</td>
                        <td className="py-3 px-4 text-zinc-300">₹{a.latestPrice}</td>
                        <td className="py-3 px-4 text-emerald-400 font-bold">{a.recommendedShares} shares</td>
                        <td className="py-3 px-4 text-zinc-200">₹{a.allocatedRupees.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
