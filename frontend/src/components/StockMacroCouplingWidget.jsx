import React, { useState, useEffect } from "react";
import { getBetaCoupledSimulation } from "../lib/api";
import { fmtPct, colorClass } from "../lib/format";
import { Layers, Loader2, AlertTriangle, ArrowRight, BarChart2, TrendingUp, Activity } from "lucide-react";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ReferenceLine,
  BarChart,
  Bar,
  AreaChart,
  Area,
  Cell
} from "recharts";

export default function StockMacroCouplingWidget({ symbol, sector = "Conglomerate", onSwitchToMacro }) {
  const [lookback, setLookback] = useState(252);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState("scatter"); // "scatter" | "distribution" | "factors"

  useEffect(() => {
    if (!symbol) return;
    let isMounted = true;
    setLoading(true);
    setError(null);

    getBetaCoupledSimulation(symbol, { sector, horizon_days: 20, paths: 10000, lookback })
      .then((res) => {
        if (!isMounted) return;
        if (res.status === "error") {
          setError(res.message || "Beta coupling regression unavailable.");
        } else {
          setData(res);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setError("Network error fetching beta simulation.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [symbol, sector, lookback]);

  // Prepare macro factor sensitivities and contributions for BarChart
  const factorBarData = React.useMemo(() => {
    if (!data) return [];
    const sens = data.macro_factor_sensitivities || {};
    const contrib = data.macro_factor_contribution || {};
    const factors = Array.from(new Set([...Object.keys(sens), ...Object.keys(contrib)]));
    return factors.map((fac) => ({
      factor: fac,
      sensitivity: typeof sens[fac] === "number" ? sens[fac] : 0,
      contribution: typeof contrib[fac] === "number" ? contrib[fac] : (parseFloat(contrib[fac]) || 0)
    }));
  }, [data]);

  if (!symbol) return null;

  return (
    <div className="border border-zinc-800 bg-[#0c0c0e] rounded-xl p-4 my-3 shadow-lg font-sans text-zinc-100" data-testid="stock-macro-coupling-widget">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-zinc-800/80">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-emerald-600/20 border border-emerald-500/30 text-emerald-400">
            <Layers size={18} />
          </div>
          <div>
            <h4 className="text-xs font-bold font-mono tracking-wider text-white flex items-center gap-2">
              ASYMMETRIC BETA & TAIL RISK COUPLING ({symbol})
              <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                20-Day Horizon
              </span>
            </h4>
            <p className="text-[11px] text-zinc-400">
              Evaluates stock downside vulnerability against 10,000 global macro simulation trajectories.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-zinc-900/90 rounded-lg p-0.5 border border-zinc-800 text-[10px] font-mono">
            {[
              { label: "1Y (252d)", val: 252 },
              { label: "3Y (756d)", val: 756 },
              { label: "5Y (1260d)", val: 1260 },
              { label: "Since 2009 (Max)", val: 4400 },
            ].map((opt) => (
              <button
                key={opt.val}
                onClick={() => setLookback(opt.val)}
                className={`px-2 py-1 rounded-md font-bold transition-all ${
                  lookback === opt.val
                    ? "bg-emerald-600/30 text-emerald-400 border border-emerald-500/50"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {onSwitchToMacro && (
            <button
              onClick={onSwitchToMacro}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-indigo-400 hover:text-indigo-300 text-xs font-mono font-bold border border-zinc-800 transition-all shrink-0"
              data-testid="switch-to-macro-btn"
            >
              Explore Full 10k Cholesky Deck <ArrowRight size={13} />
            </button>
          )}
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-10 gap-2 text-zinc-400 text-xs font-mono">
          <Loader2 className="animate-spin text-emerald-500" size={18} />
          <span>Regressing {symbol} against Cholesky macro drivers & tail scenarios...</span>
        </div>
      )}

      {error && !loading && (
        <div className="mt-3 p-3 rounded-lg bg-red-950/30 border border-red-900/60 text-red-300 text-xs font-mono flex items-center gap-2">
          <AlertTriangle size={14} />
          <span>{error}</span>
        </div>
      )}

      {data && !loading && (
        <div className="mt-3.5 space-y-4">
          {/* Key Summary Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/80">
              <div className="text-[10px] font-mono tracking-wider uppercase text-zinc-500 mb-0.5">
                Beta Asymmetry (β+ / β-)
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-base font-bold font-mono text-emerald-400" title="Upside Beta">
                  β+ {(data.upside_beta ?? 1.0).toFixed(2)}
                </span>
                <span className="text-zinc-600 font-mono text-xs">/</span>
                <span className="text-base font-bold font-mono text-red-400" title="Downside Beta">
                  β- {(data.downside_beta ?? 1.0).toFixed(2)}
                </span>
              </div>
              <div className="text-[9px] text-zinc-400 font-mono mt-0.5 truncate">
                {data.downside_beta > (data.upside_beta ?? 1.0) * 1.1 ? "⚠️ Crash Sensitive" : "Symmetric Tail Response"}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/80">
              <div className="text-[10px] font-mono tracking-wider uppercase text-zinc-500 mb-0.5">
                Macro Conditioned Return
              </div>
              <div className={`text-lg font-bold font-mono tabular-nums ${colorClass(data.expected_stock_move)}`}>
                {fmtPct(data.expected_stock_move)}
              </div>
              <div className="text-[9px] text-zinc-500 font-mono mt-0.5">
                Expected 20-day mean trajectory
              </div>
            </div>

            <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/80">
              <div className="text-[10px] font-mono tracking-wider uppercase text-zinc-500 mb-0.5">
                Downside VaR / CVaR (95%)
              </div>
              <div className="text-base font-bold font-mono tabular-nums text-red-400">
                {fmtPct(data.downside_var?.var95 || 0)} <span className="text-[10px] text-red-300/80">({fmtPct(data.downside_cvar || 0)})</span>
              </div>
              <div className="text-[9px] text-zinc-500 font-mono mt-0.5">
                Worst 5% tail loss expected shortfall
              </div>
            </div>

            <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800/80">
              <div className="text-[10px] font-mono tracking-wider uppercase text-zinc-500 mb-0.5">
                Drawdown Risk (&gt;5%)
              </div>
              <div className="text-lg font-bold font-mono tabular-nums text-amber-400">
                {typeof data.probability_of_large_drawdown === "number" ? `${data.probability_of_large_drawdown.toFixed(1)}%` : "0.0%"}
              </div>
              <div className="text-[9px] text-zinc-500 font-mono mt-0.5">
                Probability of severe 20d drop
              </div>
            </div>
          </div>

          {/* Interactive Chart Navigation Tabs */}
          <div className="border border-zinc-800/80 bg-zinc-900/30 rounded-xl p-3.5">
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2.5 mb-3">
              <div className="flex items-center gap-1.5 text-xs font-mono">
                <button
                  onClick={() => setActiveTab("scatter")}
                  className={`px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all ${
                    activeTab === "scatter"
                      ? "bg-emerald-600/20 text-emerald-400 border border-emerald-500/40"
                      : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
                  }`}
                >
                  <TrendingUp size={14} /> Nifty vs. {symbol} Beta Scatter
                </button>
                <button
                  onClick={() => setActiveTab("distribution")}
                  className={`px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all ${
                    activeTab === "distribution"
                      ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/40"
                      : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
                  }`}
                >
                  <Activity size={14} /> 20D Return Distribution &amp; Tail VaR
                </button>
                <button
                  onClick={() => setActiveTab("factors")}
                  className={`px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 transition-all ${
                    activeTab === "factors"
                      ? "bg-amber-600/20 text-amber-400 border border-amber-500/40"
                      : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
                  }`}
                >
                  <BarChart2 size={14} /> Macro Factor Sensitivities
                </button>
              </div>
              <div className="hidden md:block text-[10px] font-mono text-zinc-500 uppercase">
                {lookback === 4400 ? "Since 2009 Institutional Window" : `${lookback}-Day Empirical Window`}
              </div>
            </div>

            {/* TAB 1: Asymmetric Beta Scatter Plot */}
            {activeTab === "scatter" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 px-1">
                  <span>Empirical Scatter: Nifty Daily Returns vs. {symbol} Daily Returns</span>
                  <div className="flex items-center gap-3 text-[10px]">
                    <span className="flex items-center gap-1 text-emerald-400"><span className="w-2.5 h-0.5 bg-emerald-400 inline-block" /> Up Slope (β+ {data.upside_beta})</span>
                    <span className="flex items-center gap-1 text-red-400"><span className="w-2.5 h-0.5 bg-red-400 inline-block" /> Down Slope (β- {data.downside_beta})</span>
                  </div>
                </div>
                <div className="h-64 w-full bg-zinc-950/60 border border-zinc-800/60 rounded-lg p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                      <XAxis
                        type="number"
                        dataKey="nifty"
                        name="Nifty Return"
                        unit="%"
                        domain={[-5, 5]}
                        stroke="#71717a"
                        fontSize={10}
                        label={{ value: "Nifty Daily Return (%)", position: "insideBottom", offset: -10, fill: "#71717a", fontSize: 10 }}
                      />
                      <YAxis
                        type="number"
                        dataKey="stock"
                        name={`${symbol} Return`}
                        unit="%"
                        domain={[-8, 8]}
                        stroke="#71717a"
                        fontSize={10}
                        label={{ value: `${symbol} Return (%)`, angle: -90, position: "insideLeft", fill: "#71717a", fontSize: 10 }}
                      />
                      <RechartsTooltip
                        cursor={{ strokeDasharray: "3 3", stroke: "#52525b" }}
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            const d = payload[0].payload;
                            return (
                              <div className="bg-zinc-900 border border-zinc-700 p-2 rounded text-xs font-mono shadow-xl">
                                <div className="text-zinc-400 text-[10px] mb-1">{d.date || "Empirical Day"}</div>
                                <div className="text-indigo-300">Nifty: <span className="font-bold text-white">{d.nifty}%</span></div>
                                <div className="text-emerald-300">{symbol}: <span className="font-bold text-white">{d.stock}%</span></div>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <ReferenceLine x={0} stroke="#3f3f46" strokeDasharray="3 3" />
                      <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="3 3" />
                      
                      {/* Regression Reference Slopes */}
                      <ReferenceLine
                        segment={[{ x: 0, y: (data.alpha || 0) * 100 }, { x: 5, y: ((data.alpha || 0) + (data.upside_beta || 1) * 0.05) * 100 }]}
                        stroke="#10b981"
                        strokeWidth={2}
                      />
                      <ReferenceLine
                        segment={[{ x: -5, y: ((data.alpha || 0) - (data.downside_beta || 1) * 0.05) * 100 }, { x: 0, y: (data.alpha || 0) * 100 }]}
                        stroke="#ef4444"
                        strokeWidth={2}
                      />

                      <Scatter name="Daily Returns" data={data.scatter_data || []}>
                        {(data.scatter_data || []).map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.nifty >= 0 ? "#34d399" : "#f87171"} fillOpacity={0.7} />
                        ))}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* TAB 2: 20-Day Return Probability Distribution */}
            {activeTab === "distribution" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 px-1">
                  <span>10,000-Path Simulated Horizon Return Density Curve ({symbol})</span>
                  <div className="flex items-center gap-3 text-[10px]">
                    <span className="text-red-400 font-bold">VaR 95%: {fmtPct(data.downside_var?.var95 || 0)}</span>
                    <span className="text-sky-400 font-bold">Expected Move: {fmtPct(data.expected_stock_move || 0)}</span>
                  </div>
                </div>
                <div className="h-64 w-full bg-zinc-950/60 border border-zinc-800/60 rounded-lg p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data.return_distribution || []} margin={{ top: 15, right: 20, bottom: 20, left: 0 }}>
                      <XAxis
                        dataKey="ret"
                        unit="%"
                        stroke="#71717a"
                        fontSize={10}
                        label={{ value: "20-Day Simulated Return (%)", position: "insideBottom", offset: -10, fill: "#71717a", fontSize: 10 }}
                      />
                      <YAxis
                        dataKey="density"
                        unit="%"
                        stroke="#71717a"
                        fontSize={10}
                        label={{ value: "Path Density (%)", angle: -90, position: "insideLeft", fill: "#71717a", fontSize: 10 }}
                      />
                      <RechartsTooltip
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            const d = payload[0].payload;
                            return (
                              <div className="bg-zinc-900 border border-zinc-700 p-2 rounded text-xs font-mono shadow-xl">
                                <div className="text-zinc-300 font-bold">Return Bin: {d.ret}%</div>
                                <div className="text-emerald-400">Path Count: <span className="text-white">{d.count} paths</span></div>
                                <div className="text-indigo-400">Density: <span className="text-white">{d.density}%</span></div>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <ReferenceLine
                        x={data.downside_var?.var95 || -5}
                        stroke="#ef4444"
                        strokeWidth={2}
                        strokeDasharray="4 4"
                        label={{ value: `VaR 95% (${fmtPct(data.downside_var?.var95 || 0)})`, fill: "#f87171", fontSize: 10, position: "insideTopLeft" }}
                      />
                      <ReferenceLine
                        x={data.expected_stock_move || 0}
                        stroke="#38bdf8"
                        strokeWidth={2}
                        label={{ value: `Mean (${fmtPct(data.expected_stock_move || 0)})`, fill: "#38bdf8", fontSize: 10, position: "insideTopRight" }}
                      />
                      <Area type="monotone" dataKey="density" stroke="#6366f1" strokeWidth={2} fillOpacity={0.2} fill="#6366f1" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* TAB 3: Macro Factor Sensitivities & Contributions */}
            {activeTab === "factors" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 px-1">
                  <span>Macro Factor Regression Sensitivities (Beta to Driver) &amp; Variance Contribution</span>
                  <span className="text-[10px] text-zinc-500 uppercase">OLS Regression against 6-Asset Cholesky Universe</span>
                </div>
                <div className="h-64 w-full bg-zinc-950/60 border border-zinc-800/60 rounded-lg p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={factorBarData} layout="vertical" margin={{ top: 10, right: 30, bottom: 10, left: 40 }}>
                      <XAxis type="number" stroke="#71717a" fontSize={10} />
                      <YAxis type="category" dataKey="factor" stroke="#e4e4e7" fontSize={11} fontFamily="monospace" fontWeight="bold" />
                      <RechartsTooltip
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            const d = payload[0].payload;
                            return (
                              <div className="bg-zinc-900 border border-zinc-700 p-2 rounded text-xs font-mono shadow-xl">
                                <div className="text-zinc-200 font-bold mb-1">{d.factor} Sensitivity &amp; Impact</div>
                                <div className="text-indigo-300">Beta Sensitivity: <span className="font-bold text-white">{d.sensitivity}</span></div>
                                <div className="text-amber-300">Variance Contribution: <span className="font-bold text-white">{typeof d.contribution === "number" ? `${d.contribution.toFixed(1)}%` : d.contribution}</span></div>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <ReferenceLine x={0} stroke="#52525b" />
                      <Bar dataKey="sensitivity" name="Regression Sensitivity (Beta)" radius={[0, 4, 4, 0]}>
                        {factorBarData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.sensitivity >= 0 ? "#10b981" : "#f87171"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>

          {data.macro_factor_contribution && Object.keys(data.macro_factor_contribution).length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-zinc-800/60 text-xs font-mono">
              <span className="text-[10px] uppercase text-zinc-500 font-bold">Variance Drivers:</span>
              {Object.entries(data.macro_factor_contribution).map(([factor, weight]) => (
                <span key={factor} className="px-2 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-zinc-300 flex items-center gap-1.5">
                  <span>{factor}</span>
                  <span className="text-indigo-400 font-bold">{typeof weight === "number" ? `${(weight * 100).toFixed(0)}%` : weight}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
