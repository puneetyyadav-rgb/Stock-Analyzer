import React, { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { getChart } from "../lib/api";
import { Loader2, CandlestickChart as CandleIcon, TrendingUp } from "lucide-react";

const PERIODS = [
  { key: "1d", label: "1D (Live)" },
  { key: "5d", label: "5D" },
  { key: "1mo", label: "1M" },
  { key: "6mo", label: "6M" },
  { key: "1y", label: "1Y" },
  { key: "5y", label: "5Y" },
];

export default function StockChart({ symbol }) {
  const [period, setPeriod] = useState("1d");
  const [chartType, setChartType] = useState("candle");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hovered, setHovered] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setHovered(null);
    getChart(symbol, period)
      .then((d) => setData(d.data || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [symbol, period]);

  const positive = data.length > 1 && data[data.length - 1].close >= data[0].close;
  const color = positive ? "#34C759" : "#FF3B30";

  // Calculate domain bounds for custom candlestick renderer
  const minP = data.length ? Math.min(...data.map(d => Math.min(d.low ?? d.close, d.open ?? d.close))) : 0;
  const maxP = data.length ? Math.max(...data.map(d => Math.max(d.high ?? d.close, d.open ?? d.close))) : 100;
  const pad = (maxP - minP) * 0.05 || 1;
  const domainMin = minP - pad;
  const domainMax = maxP + pad;
  const range = domainMax - domainMin || 1;

  return (
    <div className="w-full h-full flex flex-col select-none" data-testid="stock-chart">
      {/* Chart Header Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2 pb-1 border-b border-zinc-800/60">
        <div className="flex items-center gap-1 bg-zinc-900/80 p-0.5 rounded border border-zinc-800">
          <button
            onClick={() => setChartType("candle")}
            className={`flex items-center gap-1 px-2 py-0.5 text-[10px] uppercase tracking-widest font-bold rounded transition-colors ${
              chartType === "candle" ? "bg-fuchsia-700 text-white" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <CandleIcon size={12} /> Candles
          </button>
          <button
            onClick={() => setChartType("area")}
            className={`flex items-center gap-1 px-2 py-0.5 text-[10px] uppercase tracking-widest font-bold rounded transition-colors ${
              chartType === "area" ? "bg-fuchsia-700 text-white" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <TrendingUp size={12} /> Area
          </button>
        </div>

        <div className="flex items-center gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              data-testid={`chart-period-${p.key}`}
              className={`px-2 py-0.5 text-[10px] tracking-widest uppercase font-bold rounded transition-colors ${
                period === p.key
                  ? "bg-zinc-100 text-zinc-950 shadow-sm"
                  : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 border border-zinc-800"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Candlestick OHL CV Live Status Bar */}
      {chartType === "candle" && (
        <div className="h-6 flex items-center gap-3 text-xs font-mono px-2 bg-zinc-950/80 border border-zinc-800/80 rounded mb-1 text-zinc-300 overflow-x-auto">
          {hovered ? (
            <>
              <span className="text-zinc-500 font-bold">{new Date(hovered.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })}</span>
              <span>O: <strong className={hovered.close >= hovered.open ? "text-emerald-400" : "text-red-400"}>₹{Number(hovered.open || 0).toFixed(2)}</strong></span>
              <span>H: <strong>₹{Number(hovered.high || 0).toFixed(2)}</strong></span>
              <span>L: <strong>₹{Number(hovered.low || 0).toFixed(2)}</strong></span>
              <span>C: <strong className={hovered.close >= hovered.open ? "text-emerald-400" : "text-red-400"}>₹{Number(hovered.close || 0).toFixed(2)}</strong></span>
              <span>Vol: <strong className="text-fuchsia-300">{Number(hovered.volume || 0).toLocaleString()}</strong></span>
            </>
          ) : data.length > 0 ? (
            <>
              <span className="text-emerald-500 font-bold flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"/> LIVE INTRADAY</span>
              <span>O: <strong>₹{Number(data[data.length-1].open || 0).toFixed(2)}</strong></span>
              <span>H: <strong>₹{Number(data[data.length-1].high || 0).toFixed(2)}</strong></span>
              <span>L: <strong>₹{Number(data[data.length-1].low || 0).toFixed(2)}</strong></span>
              <span>C: <strong className={color}>₹{Number(data[data.length-1].close || 0).toFixed(2)}</strong></span>
              <span>Vol: <strong className="text-fuchsia-300">{Number(data[data.length-1].volume || 0).toLocaleString()}</strong></span>
            </>
          ) : (
            <span className="text-zinc-500 text-[10px]">Hover over candles to view institutional price action</span>
          )}
        </div>
      )}

      {/* Main Chart Body */}
      <div className="flex-1 min-h-[280px] relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-[#0c0c0e]/80 backdrop-blur-sm">
            <Loader2 size={24} className="animate-spin text-fuchsia-500" />
          </div>
        )}

        {chartType === "candle" ? (
          data.length > 0 ? (
            <div className="w-full h-full relative" onMouseLeave={() => setHovered(null)}>
              <svg className="w-full h-full absolute inset-0" viewBox="0 0 1000 360" preserveAspectRatio="none">
                {/* Horizontal price grid lines */}
                {[0.1, 0.3, 0.5, 0.7, 0.9].map((pct, i) => {
                  const y = 360 * (1 - pct);
                  const val = domainMin + range * pct;
                  return (
                    <g key={i}>
                      <line x1="0" y1={y} x2="1000" y2={y} stroke="#27272a" strokeDasharray="3 3" strokeWidth="1" />
                      <text x="940" y={y - 4} fill="#71717a" fontSize="10" fontFamily="monospace">₹{val.toFixed(1)}</text>
                    </g>
                  );
                })}

                {/* Candlestick Rendering */}
                {data.map((d, i) => {
                  const n = data.length;
                  const slotW = 1000 / n;
                  const candleW = Math.max(1.5, slotW * 0.65);
                  const x = (i + 0.5) * slotW;

                  const open = d.open ?? d.close;
                  const close = d.close;
                  const high = d.high ?? Math.max(open, close);
                  const low = d.low ?? Math.min(open, close);

                  const isGreen = close >= open;
                  const cColor = isGreen ? "#34C759" : "#FF3B30";

                  const yHigh = 360 * (1 - (high - domainMin) / range);
                  const yLow = 360 * (1 - (low - domainMin) / range);
                  const yOpen = 360 * (1 - (open - domainMin) / range);
                  const yClose = 360 * (1 - (close - domainMin) / range);

                  const rectY = Math.min(yOpen, yClose);
                  const rectH = Math.max(1.5, Math.abs(yOpen - yClose));

                  return (
                    <g key={i} className="cursor-crosshair" onMouseEnter={() => setHovered(d)}>
                      {/* High-Low Wick */}
                      <line x1={x} y1={yHigh} x2={x} y2={yLow} stroke={cColor} strokeWidth={n > 80 ? "1" : "1.5"} />
                      {/* Open-Close Body */}
                      <rect x={x - candleW / 2} y={rectY} width={candleW} height={rectH} fill={cColor} stroke={cColor} />
                      {/* Transparent hit area for hover */}
                      <rect x={x - slotW / 2} y="0" width={slotW} height="360" fill="transparent" />
                    </g>
                  );
                })}
              </svg>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-zinc-500 text-xs">No chart data available for this timeframe</div>
          )
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tick={{ fill: "#71717a", fontSize: 10, fontFamily: "JetBrains Mono" }}
                tickFormatter={(v) => {
                  const d = new Date(v);
                  if (isNaN(d.getTime())) return v;
                  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
                }}
                minTickGap={40}
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
                formatter={(v) => [`₹${Number(v).toFixed(2)}`, "Close"]}
              />
              <Area
                type="linear"
                dataKey="close"
                stroke={color}
                strokeWidth={1.5}
                fill="url(#colorPrice)"
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
