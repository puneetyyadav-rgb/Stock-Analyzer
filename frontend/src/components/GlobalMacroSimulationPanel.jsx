import React, { useState, useEffect, useRef } from "react";
import { getGlobalMacroMonteCarlo, getBetaCoupledSimulation } from "../lib/api";
import { fmtNum, fmtPct, colorClass } from "../lib/format";
import { 
  Activity, Loader2, AlertCircle, TrendingUp, TrendingDown, 
  ShieldAlert, Sliders, Play, RefreshCw, BarChart2, Layers, AlertTriangle 
} from "lucide-react";

export default function GlobalMacroSimulationPanel({ symbol: parentSymbol = "", sector: parentSector = "Conglomerate" }) {
  // Tier 1: Global Macro Simulation state
  const [horizonDays, setHorizonDays] = useState(20);
  const [paths, setPaths] = useState(10000);
  const [lookback, setLookback] = useState(252);
  const [seed, setSeed] = useState(12345);
  const [volScale, setVolScale] = useState(1.0);
  const [regimeOverride, setRegimeOverride] = useState("normal");
  
  const [macroLoading, setMacroLoading] = useState(false);
  const [macroError, setMacroError] = useState(null);
  const [macroData, setMacroData] = useState(null);

  // Tier 2: Beta-coupled Stock Simulation state
  const [stockSymbol, setStockSymbol] = useState(parentSymbol || "RELIANCE");
  const [stockSector, setStockSector] = useState(parentSector || "Conglomerate");
  const [stockLoading, setStockLoading] = useState(false);
  const [stockError, setStockError] = useState(null);
  const [stockData, setStockData] = useState(null);

  const abortControllerRef = useRef(null);

  // Sync parent symbol changes
  useEffect(() => {
    if (parentSymbol && parentSymbol !== stockSymbol) {
      setStockSymbol(parentSymbol);
    }
    if (parentSector && parentSector !== stockSector) {
      setStockSector(parentSector);
    }
  }, [parentSymbol, parentSector]);

  // Run or Refresh Global Macro Simulation
  const runMacroSimulation = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setMacroLoading(true);
    setMacroError(null);
    try {
      const res = await getGlobalMacroMonteCarlo(
        { horizon_days: horizonDays, paths, lookback, seed, vol_scale: volScale, regime_override: regimeOverride },
        { signal: abortControllerRef.current.signal }
      );
      if (res.status === "error") {
        setMacroError(res.message || "Failed to execute Monte Carlo engine.");
      } else if (res.status !== "canceled") {
        setMacroData(res);
      }
    } catch (err) {
      setMacroError("Network error while calling simulation deck.");
    } finally {
      setMacroLoading(false);
    }
  };

  // Run Beta-Coupled Stock Simulation
  const runStockSimulation = async () => {
    if (!stockSymbol) return;
    setStockLoading(true);
    setStockError(null);
    try {
      const res = await getBetaCoupledSimulation(
        stockSymbol,
        { sector: stockSector, horizon_days: horizonDays, paths, lookback, seed, vol_scale: volScale, regime_override: regimeOverride }
      );
      if (res.status === "error") {
        setStockError(res.message || "Stock coupled simulation failed.");
      } else {
        setStockData(res);
      }
    } catch (err) {
      setStockError("Network error calling stock coupled simulation.");
    } finally {
      setStockLoading(false);
    }
  };

  // Run macro simulation on mount or whenever lookback window changes
  useEffect(() => {
    runMacroSimulation();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [lookback]);

  // When macro data arrives or stockSymbol changes, trigger stock coupling
  useEffect(() => {
    if (macroData && stockSymbol) {
      runStockSimulation();
    }
  }, [macroData, stockSymbol, stockSector]);

  // Helper for driver color badges
  const getDriverColor = (driver) => {
    switch (driver) {
      case "CRUDE": return "bg-amber-950/60 text-amber-400 border-amber-800/80";
      case "USDINR": return "bg-cyan-950/60 text-cyan-400 border-cyan-800/80";
      case "INDIA_VIX": return "bg-red-950/60 text-red-400 border-red-800/80";
      case "GOLD": return "bg-yellow-950/60 text-yellow-400 border-yellow-800/80";
      case "US10Y": return "bg-purple-950/60 text-purple-400 border-purple-800/80";
      default: return "bg-blue-950/60 text-blue-400 border-blue-800/80";
    }
  };

  return (
    <div className="space-y-6 text-zinc-100 font-sans" data-testid="global-macro-simulation-panel">
      {/* Top Banner / Controls Strip */}
      <div className="border border-zinc-800 bg-[#0e0e12] rounded-xl p-5 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-600/5 rounded-full blur-3xl -z-10 pointer-events-none" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-zinc-800/80">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-indigo-600/20 border border-indigo-500/30 text-indigo-400">
              <Activity size={22} className="animate-pulse" />
            </div>
            <div>
              <h3 className="text-lg font-bold tracking-tight font-mono text-white flex items-center gap-2">
                INSTITUTIONAL GLOBAL MACRO & BETA-COUPLED SIMULATION DECK
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                  Cholesky EWMA + Shrinkage
                </span>
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Simulates 10,000+ correlated multi-asset trajectories across Nifty 50, USD/INR, Brent Crude, Gold, VIX, & US 10Y Treasury.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={runMacroSimulation}
              disabled={macroLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold font-mono tracking-wider transition-all disabled:opacity-50 shadow-lg shadow-indigo-900/30"
              data-testid="run-macro-sim-btn"
            >
              {macroLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              {macroLoading ? "SIMULATING PATHS..." : "RE-RUN 10K DECK"}
            </button>
          </div>
        </div>

        {/* Configuration Parameters Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 bg-zinc-900/50 p-3.5 rounded-lg border border-zinc-800/60">
          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-1">
              Forecast Horizon: <span className="text-indigo-400 font-bold">{horizonDays} Days</span>
            </label>
            <input
              type="range"
              min={5}
              max={60}
              step={5}
              value={horizonDays}
              onChange={(e) => setHorizonDays(Number(e.target.value))}
              className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              data-testid="horizon-slider"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-1">
              Paths Volume
            </label>
            <select
              value={paths}
              onChange={(e) => setPaths(Number(e.target.value))}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-xs font-mono text-zinc-200 focus:outline-none focus:border-indigo-500"
              data-testid="paths-select"
            >
              <option value={5000}>5,000 Paths (Fast)</option>
              <option value={10000}>10,000 Paths (Standard)</option>
              <option value={20000}>20,000 Paths (Deep)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-1">
              EWMA Lookback
            </label>
            <select
              value={lookback}
              onChange={(e) => setLookback(Number(e.target.value))}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-xs font-mono text-zinc-200 focus:outline-none focus:border-indigo-500"
            >
              <option value={126}>126 Days (6 Months)</option>
              <option value={252}>252 Days (1 Year)</option>
              <option value={504}>504 Days (2 Years)</option>
              <option value={756}>756 Days (3 Years)</option>
              <option value={1260}>1,260 Days (5 Years)</option>
              <option value={4400}>Since 2009 (17.5+ Yrs Max)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-1">
              Monte Carlo Seed
            </label>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-xs font-mono text-zinc-200 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {/* Phase 7: Option-Implied & Regime Stress Overrides */}
        <div className="mt-3 pt-3 border-t border-zinc-800/80 grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">
                Option-Implied Vol Multiplier: <span className="text-amber-400 font-bold">{volScale.toFixed(1)}x</span>
              </label>
              <span className="text-[10px] text-zinc-500 font-mono">Stress-test Cholesky covariance</span>
            </div>
            <input
              type="range"
              min={1.0}
              max={2.5}
              step={0.1}
              value={volScale}
              onChange={(e) => setVolScale(Number(e.target.value))}
              className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
              data-testid="vol-scale-slider"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-1.5">
              Macro Stress Regime Override
            </label>
            <div className="flex flex-wrap gap-1.5" data-testid="regime-buttons">
              {[
                { id: "normal", label: "🟢 Normal", title: "Historical EWMA baseline drift" },
                { id: "bull", label: "📈 Bullish (+20% Nifty)", title: "Economic expansion regime" },
                { id: "crisis", label: "🔴 Global Crisis (-37% Nifty, +VIX)", title: "Tail event market crash stress" },
                { id: "oil_shock", label: "🛢️ Oil Shock (+75% Crude)", title: "Geopolitical commodity inflation spike" }
              ].map((r) => (
                <button
                  key={r.id}
                  onClick={() => setRegimeOverride(r.id)}
                  title={r.title}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono font-bold border transition-all ${
                    regimeOverride === r.id
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/80 shadow"
                      : "bg-zinc-900/80 text-zinc-400 border-zinc-800 hover:text-zinc-200"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {macroError && (
        <div className="flex items-center gap-3 p-4 bg-red-950/40 border border-red-900/80 rounded-xl text-red-300">
          <AlertCircle size={18} className="shrink-0" />
          <span className="text-xs font-mono">{macroError}</span>
        </div>
      )}

      {macroLoading && !macroData && (
        <div className="flex flex-col items-center justify-center py-24 border border-zinc-800 bg-[#0c0c0e] rounded-xl gap-4 text-zinc-400">
          <Loader2 className="animate-spin text-indigo-500" size={36} />
          <div className="text-center">
            <div className="text-sm font-mono tracking-widest text-zinc-200 font-bold uppercase">
              Computing Cholesky Decomposition & EWMA Covariance Matrix...
            </div>
            <div className="text-xs font-mono text-zinc-500 mt-1">
              Simulating {paths.toLocaleString()} cross-asset paths over {horizonDays} trading days
            </div>
          </div>
        </div>
      )}

      {/* Tier 1 Results Area */}
      {macroData && (
        <div className="space-y-6">
          {/* Key Macro Risk Metrics KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="border border-zinc-800 bg-[#0c0c0e] p-4 rounded-xl relative overflow-hidden">
              <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 mb-1">
                Nifty Expected {horizonDays}-Day Return
              </div>
              <div className={`text-2xl font-bold font-mono tabular-nums ${colorClass(macroData.expected_return)}`}>
                {fmtPct(macroData.expected_return)}
              </div>
              <div className="text-[10px] text-zinc-500 font-mono mt-1">
                Mean log return across {paths.toLocaleString()} paths
              </div>
            </div>

            <div className="border border-zinc-800 bg-[#0c0c0e] p-4 rounded-xl relative overflow-hidden">
              <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 mb-1">
                Nifty Value at Risk (VaR 95%)
              </div>
              <div className="text-2xl font-bold font-mono tabular-nums text-red-400">
                {fmtPct(macroData.var_95)}
              </div>
              <div className="text-[10px] text-zinc-500 font-mono mt-1">
                Worst 5% loss horizon threshold
              </div>
            </div>

            <div className="border border-zinc-800 bg-[#0c0c0e] p-4 rounded-xl relative overflow-hidden">
              <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 mb-1">
                Dominant Macro Risk Driver
              </div>
              <div className="mt-1 flex items-center gap-2">
                <span className={`px-2.5 py-1 text-xs font-bold font-mono rounded border ${getDriverColor(macroData.dominant_risk_driver)}`}>
                  {macroData.dominant_risk_driver || "N/A"}
                </span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono mt-1">
                Highest absolute covariance with Nifty
              </div>
            </div>

            <div className="border border-zinc-800 bg-[#0c0c0e] p-4 rounded-xl relative overflow-hidden">
              <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 mb-1">
                Ledoit-Wolf Shrinkage Intensity
              </div>
              <div className="text-2xl font-bold font-mono tabular-nums text-zinc-200">
                {typeof macroData.shrinkage_intensity === "number" ? macroData.shrinkage_intensity.toFixed(4) : "0.0100"}
              </div>
              <div className="text-[10px] text-zinc-500 font-mono mt-1">
                Diagonal stabilization parameter
              </div>
            </div>
          </div>

          {/* Cross-Asset Forecast Percentile Matrix */}
          <div className="border border-zinc-800 bg-[#0c0c0e] rounded-xl p-5 shadow-lg">
            <h4 className="text-sm font-bold font-mono uppercase tracking-wider text-zinc-300 mb-4 flex items-center gap-2">
              <BarChart2 size={16} className="text-indigo-400" />
              Cross-Asset Forecast Percentiles (End of {horizonDays}-Day Horizon)
            </h4>

            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-zinc-800 text-[11px] tracking-wider uppercase text-zinc-500 bg-zinc-900/40">
                    <th className="py-2.5 px-3 font-semibold">Asset Class</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Latest Base Price</th>
                    <th className="py-2.5 px-3 font-semibold text-right text-red-400">10th Percentile (Bear)</th>
                    <th className="py-2.5 px-3 font-semibold text-right text-zinc-200">50th Percentile (Median)</th>
                    <th className="py-2.5 px-3 font-semibold text-right text-emerald-400">90th Percentile (Bull)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {Object.entries(macroData.asset_path_percentiles || macroData.path_percentiles || {}).map(([asset, p]) => (
                    <tr key={asset} className="hover:bg-zinc-900/30 transition-colors">
                      <td className="py-2.5 px-3 font-bold text-zinc-200 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-indigo-500" />
                        {asset}
                      </td>
                      <td className="py-2.5 px-3 text-right text-zinc-400 tabular-nums">
                        {fmtNum(p.base_price)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-semibold text-red-400 tabular-nums">
                        {fmtNum(p.p10)} <span className="text-[10px] font-normal opacity-80">({fmtPct(p.return_10)})</span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-semibold text-zinc-200 tabular-nums">
                        {fmtNum(p.p50)} <span className="text-[10px] font-normal opacity-80">({fmtPct(p.return_50)})</span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-semibold text-emerald-400 tabular-nums">
                        {fmtNum(p.p90)} <span className="text-[10px] font-normal opacity-80">({fmtPct(p.return_90)})</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tier 2: Asymmetric Beta-Coupled Stock Simulation Section */}
      <div className="border border-zinc-800 bg-[#0e0e12] rounded-xl p-5 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-800/80">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-emerald-600/20 border border-emerald-500/30 text-emerald-400">
              <Layers size={22} />
            </div>
            <div>
              <h4 className="text-base font-bold tracking-tight font-mono text-white flex items-center gap-2">
                TIER 2: ASYMMETRIC BETA STOCK COUPLING ENGINE
              </h4>
              <p className="text-xs text-zinc-400 mt-0.5">
                Evaluates asymmetric tail vulnerability by coupling <span className="text-white font-mono">{stockSymbol}</span> to the {horizonDays}-day simulated Nifty & macro paths.
              </p>
            </div>
          </div>

          {/* Quick Override Stock Selector */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={stockSymbol}
              onChange={(e) => setStockSymbol(e.target.value.toUpperCase())}
              placeholder="e.g. TCS or RELIANCE"
              className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-mono text-zinc-100 uppercase focus:outline-none focus:border-emerald-500 w-32"
            />
            <button
              onClick={runStockSimulation}
              disabled={stockLoading || !macroData}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold font-mono transition-all disabled:opacity-50"
            >
              {stockLoading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
              COUPLE
            </button>
          </div>
        </div>

        {stockLoading && (
          <div className="flex items-center justify-center py-16 gap-3 text-zinc-400">
            <Loader2 className="animate-spin text-emerald-500" size={24} />
            <span className="text-xs font-mono uppercase tracking-widest">Running asymmetric regression & stock path coupling...</span>
          </div>
        )}

        {stockError && !stockLoading && (
          <div className="mt-4 p-4 rounded-lg bg-red-950/30 border border-red-900/60 text-red-300 text-xs font-mono flex items-center gap-2">
            <AlertTriangle size={16} />
            <span>{stockError}</span>
          </div>
        )}

        {stockData && !stockLoading && (
          <div className="mt-5 space-y-6">
            {/* Asymmetric Beta & Tail Risk Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="border border-zinc-800/80 bg-zinc-900/40 p-4 rounded-xl">
                <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 mb-1">
                  Upside vs Downside Beta
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-bold font-mono text-emerald-400" title="Beta when market goes UP">
                    β+ {(stockData.upside_beta ?? 1.0).toFixed(2)}
                  </span>
                  <span className="text-zinc-600 font-mono">/</span>
                  <span className="text-xl font-bold font-mono text-red-400" title="Beta when market drops">
                    β- {(stockData.downside_beta ?? 1.0).toFixed(2)}
                  </span>
                </div>
                <div className="text-[10px] text-zinc-500 font-mono mt-1">
                  {stockData.downside_beta > stockData.upside_beta ? "⚠️ High asymmetry: drops faster than it climbs" : "Balanced market responsiveness"}
                </div>
              </div>

              <div className="border border-zinc-800/80 bg-zinc-900/40 p-4 rounded-xl">
                <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 mb-1">
                  Expected Stock Move ({horizonDays}d)
                </div>
                <div className={`text-2xl font-bold font-mono tabular-nums ${colorClass(stockData.expected_stock_move)}`}>
                  {fmtPct(stockData.expected_stock_move)}
                </div>
                <div className="text-[10px] text-zinc-500 font-mono mt-1">
                  Macro-conditioned return forecast
                </div>
              </div>

              <div className="border border-zinc-800/80 bg-zinc-900/40 p-4 rounded-xl">
                <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 mb-1">
                  Downside VaR / CVaR (95%)
                </div>
                <div className="text-lg font-bold font-mono tabular-nums text-red-400">
                  {fmtPct(stockData.downside_var?.var95 || 0)} <span className="text-xs text-red-300/80">({fmtPct(stockData.downside_cvar || 0)})</span>
                </div>
                <div className="text-[10px] text-zinc-500 font-mono mt-1">
                  Expected shortfall beyond 95% threshold
                </div>
              </div>

              <div className="border border-zinc-800/80 bg-zinc-900/40 p-4 rounded-xl">
                <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 mb-1">
                  Severe Drawdown Probability (&gt;5%)
                </div>
                <div className="text-2xl font-bold font-mono tabular-nums text-amber-400">
                  {typeof stockData.probability_of_large_drawdown === "number" ? `${stockData.probability_of_large_drawdown.toFixed(1)}%` : "0.0%"}
                </div>
                <div className="text-[10px] text-zinc-500 font-mono mt-1">
                  Likelihood of &gt;5% drop across paths
                </div>
              </div>
            </div>

            {/* Macro Factor Variance Contributions Breakdown */}
            {stockData.macro_factor_contribution && Object.keys(stockData.macro_factor_contribution).length > 0 && (
              <div className="border border-zinc-800/60 bg-zinc-900/30 p-4 rounded-xl">
                <h5 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-400 mb-3">
                  Variance Contribution by Macro Driver (R² / Covariance Weight)
                </h5>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                  {Object.entries(stockData.macro_factor_contribution).map(([factor, weight]) => (
                    <div key={factor} className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800/80 flex items-center justify-between">
                      <span className="text-[11px] font-mono font-bold text-zinc-300">{factor}</span>
                      <span className="text-xs font-mono font-semibold text-indigo-400 tabular-nums">
                        {typeof weight === "number" ? `${(weight * 100).toFixed(1)}%` : weight}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
