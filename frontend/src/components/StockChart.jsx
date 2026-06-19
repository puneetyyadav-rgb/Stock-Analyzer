import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart } from "recharts";
import { getChart } from "../lib/api";
import { Loader2 } from "lucide-react";

const PERIODS = [
  { key: "1d", label: "1D" },
  { key: "5d", label: "5D" },
  { key: "1mo", label: "1M" },
  { key: "6mo", label: "6M" },
  { key: "1y", label: "1Y" },
  { key: "5y", label: "5Y" },
];

export default function StockChart({ symbol }) {
  const [period, setPeriod] = useState("1y");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    getChart(symbol, period)
      .then((d) => setData(d.data || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [symbol, period]);

  const positive = data.length > 1 && data[data.length - 1].close >= data[0].close;
  const color = positive ? "#34C759" : "#FF3B30";

  return (
    <div className="w-full h-full flex flex-col" data-testid="stock-chart">
      <div className="flex items-center justify-end gap-1 mb-2">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => setPeriod(p.key)}
            data-testid={`chart-period-${p.key}`}
            className={`px-2 py-1 text-[10px] tracking-widest uppercase font-medium transition-colors ${
              period === p.key
                ? "bg-zinc-100 text-zinc-950"
                : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 border border-zinc-800"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="flex-1 min-h-[280px] relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-[#0c0c0e]/60">
            <Loader2 size={20} className="animate-spin text-zinc-500" />
          </div>
        )}
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
                return d.toLocaleDateString("en-IN", { month: "short", day: "2-digit" });
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
      </div>
    </div>
  );
}
