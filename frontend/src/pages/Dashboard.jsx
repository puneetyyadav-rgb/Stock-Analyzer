import React, { useEffect, useState } from "react";
import StockSearch from "../components/StockSearch";
import StockChart from "../components/StockChart";
import MacroPanel from "../components/MacroPanel";
import AIVerdict from "../components/AIVerdict";
import StockDetails from "../components/StockDetails";
import { Panel } from "../components/Panel";
import { getOverview } from "../lib/api";
import { fmtNum, fmtPct, fmtBigNum, colorClass } from "../lib/format";
import { Activity, Loader2, AlertCircle } from "lucide-react";

const POPULAR = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC", "BHARTIARTL", "LT", "WIPRO"];

export default function Dashboard() {
  const [symbol, setSymbol] = useState("");
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setErr(null);
    setOverview(null);
    getOverview(symbol)
      .then(setOverview)
      .catch((e) => setErr(e.response?.data?.detail || "Failed to load stock data"))
      .finally(() => setLoading(false));
  }, [symbol]);

  const positive = (overview?.changePercent ?? 0) >= 0;

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-[#0c0c0e] sticky top-0 z-40 backdrop-blur" data-testid="app-header">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center gap-4">
          <div className="flex items-center gap-2 shrink-0">
            <div className="w-7 h-7 bg-blue-600 flex items-center justify-center">
              <Activity size={16} className="text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold tracking-tight" data-testid="app-title">STOCK SENTINEL <span className="text-blue-400">·IN</span></h1>
              <p className="text-[9px] tracking-widest uppercase text-zinc-500">NSE/BSE Terminal · 9-Factor AI Analysis</p>
            </div>
          </div>
          <div className="flex-1 max-w-2xl">
            <StockSearch onSelect={setSymbol} initial={symbol} />
          </div>
          <div className="hidden md:flex items-center gap-2 text-[10px] tracking-widest uppercase text-zinc-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 blink" />
            <span>LIVE · IST</span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto p-3 lg:p-4 space-y-3" data-testid="dashboard-main">
        {!symbol && !loading && (
          <EmptyState onPick={setSymbol} />
        )}

        {symbol && loading && (
          <div className="flex items-center justify-center py-20 gap-3 text-zinc-400">
            <Loader2 className="animate-spin" size={22} />
            <span className="tracking-widest uppercase text-xs">Fetching {symbol}…</span>
          </div>
        )}

        {symbol && err && !loading && (
          <div className="flex items-center gap-2 p-4 bg-red-950/30 border border-red-900/60 text-red-300" data-testid="error-banner">
            <AlertCircle size={16} /> <span className="text-sm">{err}</span>
          </div>
        )}

        {overview && !loading && (
          <>
            {/* Stock header strip */}
            <div className="border border-zinc-800 bg-[#0c0c0e] p-4 flex flex-wrap items-end justify-between gap-4" data-testid="stock-header">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h2 className="text-2xl font-semibold tracking-tight font-mono" data-testid="stock-symbol">{overview.symbol}</h2>
                  <span className="px-1.5 py-0.5 text-[10px] tracking-widest uppercase bg-zinc-800 text-zinc-300 border border-zinc-700">{overview.exchange}</span>
                </div>
                <p className="text-sm text-zinc-400" data-testid="stock-name">{overview.name}</p>
                <p className="text-[10px] tracking-widest uppercase text-zinc-600 mt-1">{overview.sector} · {overview.industry}</p>
              </div>
              <div className="text-right">
                <div className="text-3xl font-mono tabular-nums font-semibold" data-testid="stock-price">₹{fmtNum(overview.price)}</div>
                <div className={`text-sm font-mono tabular-nums ${colorClass(overview.change)}`} data-testid="stock-change">
                  {overview.change >= 0 ? "+" : ""}{fmtNum(overview.change)} ({fmtPct(overview.changePercent)})
                </div>
              </div>
              <div className="flex gap-6 text-[10px] tracking-widest uppercase text-zinc-500">
                <div>
                  <div>Day Range</div>
                  <div className="text-xs font-mono text-zinc-300 mt-0.5">₹{fmtNum(overview.dayLow)} – ₹{fmtNum(overview.dayHigh)}</div>
                </div>
                <div>
                  <div>52W Range</div>
                  <div className="text-xs font-mono text-zinc-300 mt-0.5">₹{fmtNum(overview.yearLow)} – ₹{fmtNum(overview.yearHigh)}</div>
                </div>
                <div>
                  <div>Volume</div>
                  <div className="text-xs font-mono text-zinc-300 mt-0.5">{fmtBigNum(overview.volume)}</div>
                </div>
                <div>
                  <div>Market Cap</div>
                  <div className="text-xs font-mono text-zinc-300 mt-0.5">{fmtBigNum(overview.marketCap)}</div>
                </div>
              </div>
            </div>

            {/* Chart + Macro */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
              <div className="lg:col-span-8">
                <Panel title={`Price Chart · ${overview.symbol}`} testId="chart-panel" className="h-full">
                  <StockChart symbol={overview.symbol} />
                </Panel>
              </div>
              <div className="lg:col-span-4 space-y-3">
                <MacroPanel />
              </div>
            </div>

            {/* AI Verdict */}
            <AIVerdict symbol={overview.symbol} />

            {/* All details */}
            <StockDetails symbol={overview.symbol} overview={overview} />
          </>
        )}

        {!symbol && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 mt-4">
            <div className="lg:col-span-12 grid grid-cols-1 md:grid-cols-2 gap-3">
              <MacroPanel />
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-zinc-800 mt-10 py-4 px-4">
        <p className="text-[10px] tracking-widest uppercase text-zinc-600 text-center">
          Stock Sentinel IN · Data: NSE/BSE via Yahoo · Screener.in · Moneycontrol · AI: Gemini 3 Flash · Not investment advice
        </p>
      </footer>
    </div>
  );
}

const EmptyState = ({ onPick }) => (
  <div className="flex flex-col items-center justify-center py-16 text-center" data-testid="empty-state">
    <div
      className="absolute inset-0 -z-10 opacity-20 pointer-events-none"
      style={{
        backgroundImage: `url(https://images.pexels.com/photos/10628030/pexels-photo-10628030.png?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)`,
        backgroundSize: "cover",
        backgroundPosition: "center",
        maskImage: "linear-gradient(to bottom, black, transparent)",
      }}
    />
    <h2 className="text-3xl tracking-tight font-semibold mb-2">Indian Stock Analyzer</h2>
    <p className="text-sm text-zinc-400 max-w-xl">
      Search any NSE/BSE listed stock to get a full 9-factor terminal analysis — fundamentals, technicals,
      macro context, news, corporate actions, and an AI verdict from <span className="text-blue-400">Gemini 3 Flash</span>.
    </p>
    <div className="mt-6">
      <p className="text-[10px] tracking-widest uppercase text-zinc-500 mb-2">Try a Nifty 50 stock</p>
      <div className="flex flex-wrap justify-center gap-1.5">
        {POPULAR.map((s) => (
          <button
            key={s}
            data-testid={`popular-${s}`}
            onClick={() => onPick(s)}
            className="px-2.5 py-1 text-xs font-mono tracking-wider bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-600 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  </div>
);
