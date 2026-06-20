import React, { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Line } from "recharts";
import { getMLPredict } from "../lib/api";
import { Loader2, AlertTriangle, Calculator, ActivitySquare } from "lucide-react";
import { Panel } from "./Panel";
import { DisclaimerNote } from "./Disclaimer";

export default function MLPredictor({ symbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showZeroDrift, setShowZeroDrift] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    getMLPredict(symbol)
      .then((res) => {
        if (res.error) throw new Error(res.error);
        setData(res);
      })
      .catch((e) => setError(e.message || "Failed to load ML forecast"))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <Panel className="flex items-center justify-center py-12 text-zinc-500 mb-3">
        <Loader2 size={24} className="animate-spin" />
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel className="py-6 border-red-900/40 bg-red-950/10 mb-3">
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle size={16} />
          <span className="text-sm">ML Forecast Error: {error}</span>
        </div>
      </Panel>
    );
  }

  if (!data) return null;

  const chartData = [
    ...data.historical.map((d) => ({
      date: d.date,
      close: d.close,
    })),
    ...data.forecast.map((d) => ({
      date: d.date,
      forecast: d.forecast,
      forecastZeroDrift: d.forecastZeroDrift,
      lowerBound: d.lowerBound,
      upperBound: d.upperBound,
      range: [d.lowerBound, d.upperBound],
      path1: d.path1,
      path2: d.path2,
      path3: d.path3,
      path4: d.path4,
      path5: d.path5,
    })),
  ];

  const trendColor =
    data.trendSignal === "BULLISH BREAKOUT"
      ? "text-emerald-400"
      : data.trendSignal === "BEARISH DRIFT"
      ? "text-red-400"
      : "text-zinc-300";

  return (
    <div className="border border-purple-900/50 bg-[#0c0c0e] rounded shadow-sm overflow-hidden mb-3">
      {/* Experimental Header */}
      <div className="bg-purple-900/20 px-4 py-2 border-b border-purple-900/50 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Calculator size={14} className="text-purple-400" />
          <h3 className="text-xs font-semibold tracking-wider uppercase text-purple-300">
            Monte Carlo Simulation (1,000 Paths)
          </h3>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowZeroDrift(!showZeroDrift)}
            className={`text-[9px] tracking-widest uppercase flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
              showZeroDrift 
                ? "bg-amber-900/40 text-amber-400 border border-amber-900/50" 
                : "bg-zinc-900 text-zinc-500 border border-zinc-800 hover:text-zinc-300"
            }`}
            title="Toggle zero drift (no momentum) vs historical drift"
          >
            <ActivitySquare size={12} />
            Compare Zero Drift
          </button>
          <span className="text-[9px] text-purple-400/70 tracking-widest uppercase hidden sm:block">
            Statistical Projection
          </span>
        </div>
      </div>

      <div className="p-4 grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Left Side: Stats */}
        <div className="lg:col-span-1 flex flex-col justify-center space-y-4">
          <div>
            <p className="text-[10px] tracking-widest uppercase text-zinc-500 mb-1">
              30-Day Trend
            </p>
            <p className={`text-base font-semibold font-mono tracking-tight ${trendColor}`}>
              {data.trendSignal}
            </p>
          </div>

          <div className="bg-[#121215] p-3 rounded border border-zinc-800/60">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] tracking-widest uppercase text-zinc-400">Backtest (10 Windows)</p>
            </div>
            
            <div className="grid grid-cols-2 gap-4 mb-2">
              <div>
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider mb-0.5">Median Error</p>
                <div className="flex items-baseline gap-1">
                  <span className={`text-lg font-mono ${data.mape <= 5 ? "text-emerald-400" : data.mape <= 10 ? "text-amber-400" : "text-red-400"}`}>
                    {data.mape}%
                  </span>
                </div>
              </div>
              <div>
                <p className="text-[9px] text-zinc-500 uppercase tracking-wider mb-0.5" title="How often the actual price stayed inside the 80% band">Band Reliability</p>
                <div className="flex items-baseline gap-1">
                  <span className={`text-lg font-mono ${data.bandCoverage >= 75 ? "text-emerald-400" : data.bandCoverage >= 50 ? "text-amber-400" : "text-red-400"}`}>
                    {data.bandCoverage}%
                  </span>
                </div>
              </div>
            </div>
            
            <p className="text-[9px] text-zinc-500 leading-tight border-t border-zinc-800/60 pt-2">
              Tested over 10 separate historical periods to verify if the 80% cone actually captures reality.
            </p>
          </div>
        </div>

        {/* Right Side: Chart */}
        <div className="lg:col-span-3 min-h-[260px] relative">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorForecast" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#a855f7" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#a855f7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tick={{ fill: "#71717a", fontSize: 10, fontFamily: "JetBrains Mono" }}
                tickFormatter={(v) => {
                  const d = new Date(v);
                  if (isNaN(d.getTime())) return v;
                  return d.toLocaleDateString("en-IN", { month: "short", day: "2-digit" });
                }}
                minTickGap={30}
                stroke="#27272a"
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fill: "#71717a", fontSize: 10, fontFamily: "JetBrains Mono" }}
                orientation="right"
                stroke="#27272a"
                width={50}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0c0c0e",
                  border: "1px solid #27272a",
                  borderRadius: 2,
                  fontSize: 12,
                  fontFamily: "JetBrains Mono",
                }}
                labelStyle={{ color: "#a1a1aa", fontSize: 10 }}
                formatter={(val, name) => {
                  if (name === "range") return [`₹${val[0]} - ₹${val[1]}`, "80% Confidence Bound"];
                  if (name === "close") return [`₹${val}`, "Actual Price"];
                  if (name === "forecast") return [`₹${val}`, "Median Forecast (Drift)"];
                  if (name === "forecastZeroDrift") return [`₹${val}`, "Zero Drift Baseline"];
                  if (name.startsWith("path")) return [`₹${val}`, "Sample Path"];
                  return [val, name];
                }}
              />
              {/* Confidence Interval Cone */}
              <Area
                type="monotone"
                dataKey="range"
                stroke="none"
                fill="url(#colorForecast)"
                isAnimationActive={false}
              />
              
              {/* Sample Texture Paths (Faint) */}
              <Line type="monotone" dataKey="path1" stroke="#52525b" strokeWidth={1} dot={false} isAnimationActive={false} opacity={0.3} />
              <Line type="monotone" dataKey="path2" stroke="#52525b" strokeWidth={1} dot={false} isAnimationActive={false} opacity={0.3} />
              <Line type="monotone" dataKey="path3" stroke="#52525b" strokeWidth={1} dot={false} isAnimationActive={false} opacity={0.3} />
              <Line type="monotone" dataKey="path4" stroke="#52525b" strokeWidth={1} dot={false} isAnimationActive={false} opacity={0.3} />
              <Line type="monotone" dataKey="path5" stroke="#52525b" strokeWidth={1} dot={false} isAnimationActive={false} opacity={0.3} />

              {/* Zero Drift Line (Optional) */}
              {showZeroDrift && (
                <Line
                  type="linear"
                  dataKey="forecastZeroDrift"
                  stroke="#fbbf24"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                  isAnimationActive={false}
                />
              )}

              {/* Main Median Forecast Line */}
              <Line
                type="linear"
                dataKey="forecast"
                stroke="#a855f7"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                isAnimationActive={false}
              />
              
              {/* Actual Historical Line */}
              <Line type="linear" dataKey="close" stroke="#3b82f6" strokeWidth={1.5} dot={false} isAnimationActive={false} />

              {/* Divider between past and future */}
              <ReferenceLine x={data.historical[data.historical.length - 1].date} stroke="#3f3f46" strokeDasharray="3 3" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      {/* Disclaimer Section */}
      <div className="px-4 py-3 bg-[#09090b] border-t border-purple-900/30">
        <DisclaimerNote />
      </div>
    </div>
  );
}
