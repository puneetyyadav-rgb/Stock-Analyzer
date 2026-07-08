import React, { useState, useEffect } from "react";
import { getBetaCoupledSimulation } from "../lib/api";
import { fmtPct, colorClass } from "../lib/format";
import { Layers, Loader2, AlertTriangle, ArrowRight, ShieldAlert } from "lucide-react";

export default function StockMacroCouplingWidget({ symbol, sector = "Conglomerate", onSwitchToMacro }) {
  const [lookback, setLookback] = useState(252);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

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
        if (isMounted) setError("Network error computing tail risk.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [symbol, sector, lookback]);

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
        <div className="flex items-center justify-center py-8 gap-2 text-zinc-400 text-xs font-mono">
          <Loader2 className="animate-spin text-emerald-500" size={16} />
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
        <div className="mt-3.5 space-y-3">
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
