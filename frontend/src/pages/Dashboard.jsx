import React, { useEffect, useState } from "react";
import StockSearch from "../components/StockSearch";
import StockChart from "../components/StockChart";
import MacroPanel from "../components/MacroPanel";
import MarketDepthPanel from "../components/MarketDepthPanel";
import AIVerdict from "../components/AIVerdict";
import AITechnicalAnalysis from "../components/AITechnicalAnalysis";
import AINewsAnalysis from "../components/AINewsAnalysis";
import StockDetails from "../components/StockDetails";
import { Panel } from "../components/Panel";
import FiiDiiPanel from "../components/FiiDiiPanel";
import ConcallsPanel from "../components/ConcallsPanel";
import PeersPanel from "../components/PeersPanel";
import OptionsPanel from "../components/OptionsPanel";
import BacktestPanel from "../components/BacktestPanel";
import InsiderPanel from "../components/InsiderPanel";
import SocialPanel from "../components/SocialPanel";
import LegalPanel from "../components/LegalPanel";
import EventsPanel from "../components/EventsPanel";
import RedFlagsPanel from "../components/RedFlagsPanel";
import { DisclaimerNote } from "../components/Disclaimer";
import WatchlistPanel from "../components/WatchlistPanel";
import PdfExportButton from "../components/PdfExportButton";
import MLPredictor from "../components/MLPredictor";
import PatternsPanel from "../components/PatternsPanel";
import SectorAnalysisPanel from "../components/SectorAnalysisPanel";
import RatioAnalysisPanel from "../components/RatioAnalysisPanel";
import AIRatioAnalysisPanel from "../components/AIRatioAnalysisPanel";
import PairsTradingPanel from "../components/PairsTradingPanel";
import PortfolioAllocPanel from "../components/PortfolioAllocPanel";
import GlobalMacroSimulationPanel from "../components/GlobalMacroSimulationPanel";
import StockMacroCouplingWidget from "../components/StockMacroCouplingWidget";
import QlibAlphaLeaderboardPanel from "../components/QlibAlphaLeaderboardPanel";
import CatalystRadarPanel from "../components/CatalystRadarPanel";
import OvernightSightPanel from "../components/OvernightSightPanel";
import FundamentalDeck from "../components/FundamentalDeck";
import { getOverview, getRegime } from "../lib/api";
import { fmtNum, fmtPct, fmtBigNum, colorClass } from "../lib/format";
import { Activity, Loader2, AlertCircle, Star, StarOff, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { addToWatchlist, removeFromWatchlist, isInWatchlist } from "../lib/watchlist";
import { toast } from "sonner";

const POPULAR = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC", "BHARTIARTL", "LT", "WIPRO"];

export default function Dashboard() {
  const [symbol, setSymbol] = useState("");
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [starred, setStarred] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [regime, setRegime] = useState(null);
  const [pdfData, setPdfData] = useState(null);
  const [activeTab, setActiveTab] = useState("stock");

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setErr(null);
    setOverview(null);
    setRegime(null);
    setPdfData(null);
    getOverview(symbol)
      .then((d) => {
        setOverview(d);
        setStarred(isInWatchlist(symbol));
      })
      .catch((e) => setErr(e.response?.data?.detail || "Failed to load stock data"))
      .finally(() => setLoading(false));
      
    getRegime(symbol).then(setRegime).catch(() => {});
  }, [symbol]);

  const toggleStar = () => {
    if (!symbol) return;
    if (starred) {
      removeFromWatchlist(symbol);
      setStarred(false);
      toast(`${symbol} removed from watchlist`);
    } else {
      addToWatchlist(symbol);
      setStarred(true);
      toast.success(`${symbol} added to watchlist`);
    }
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-[#0c0c0e] sticky top-0 z-40 backdrop-blur" data-testid="app-header">
        <div className="max-w-[1700px] mx-auto px-4 py-3 flex items-center gap-4">
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="text-zinc-400 hover:text-zinc-100"
            data-testid="toggle-sidebar"
            title="Toggle sidebar"
          >
            {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
          </button>
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
          {symbol && (
            <PdfExportButton targetId="dashboard-main" filename={`${symbol}-report.pdf`} />
          )}
          <div className="hidden md:flex items-center gap-2 text-[10px] tracking-widest uppercase text-zinc-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 blink" />
            <span>LIVE · IST</span>
          </div>
        </div>
      </header>

      <div className="max-w-[1700px] mx-auto flex">
        {/* Sidebar */}
        {sidebarOpen && (
          <aside className="w-64 shrink-0 p-3 border-r border-zinc-800 sticky top-[60px] h-[calc(100vh-60px)] overflow-y-auto" data-testid="sidebar">
            <WatchlistPanel onSelect={setSymbol} currentSymbol={symbol} />
          </aside>
        )}

        {/* Main */}
        <main className="flex-1 min-w-0 p-3 lg:p-4 space-y-3" id="dashboard-main" data-testid="dashboard-main">
          <div className="flex items-center gap-2 pb-3 border-b border-zinc-800">
            <button
              onClick={() => setActiveTab("stock")}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                activeTab === "stock"
                  ? "bg-blue-600 text-white shadow-md shadow-blue-900/30"
                  : "bg-zinc-900 text-zinc-400 hover:text-white"
              }`}
            >
              📊 Stock Terminal
            </button>
            <button
              onClick={() => setActiveTab("pairs")}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                activeTab === "pairs"
                  ? "bg-purple-600 text-white shadow-md shadow-purple-900/30"
                  : "bg-zinc-900 text-zinc-400 hover:text-white"
              }`}
            >
              ⚡ Stat-Arb Pairs Scanner
            </button>
            <button
              onClick={() => setActiveTab("hrp")}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                activeTab === "hrp"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-900/30"
                  : "bg-zinc-900 text-zinc-400 hover:text-white"
              }`}
            >
              🏛️ Institutional HRP Allocator
            </button>
            <button
              onClick={() => setActiveTab("backtest")}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                activeTab === "backtest"
                  ? "bg-fuchsia-600 text-white shadow-md shadow-fuchsia-900/30"
                  : "bg-zinc-900 text-zinc-400 hover:text-white"
              }`}
            >
              🧪 Decile Backtest
            </button>
            <button
              onClick={() => setActiveTab("macro-sim")}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                activeTab === "macro-sim"
                  ? "bg-emerald-600 text-white shadow-md shadow-emerald-900/30"
                  : "bg-zinc-900 text-zinc-400 hover:text-white"
              }`}
              data-testid="macro-sim-tab-btn"
            >
              🌐 Global Macro Simulation Deck
            </button>
            <button
              onClick={() => setActiveTab("qlib")}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                activeTab === "qlib"
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md shadow-emerald-900/40 border border-emerald-400/30 animate-pulse"
                  : "bg-zinc-900 text-emerald-400 hover:text-white border border-emerald-900/40"
              }`}
              data-testid="qlib-alpha-tab-btn"
            >
              🔥 Quant AI Alpha (Qlib & SHAP)
            </button>
            <button
              onClick={() => setActiveTab("catalyst-radar")}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                activeTab === "catalyst-radar"
                  ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-900/40 border border-indigo-400/30"
                  : "bg-zinc-900 text-indigo-400 hover:text-white border border-indigo-900/40"
              }`}
              data-testid="catalyst-radar-tab-btn"
            >
              🛰️ Catalyst Radar
            </button>
            <button
              onClick={() => setActiveTab("fundamentals")}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                activeTab === "fundamentals"
                  ? "bg-gradient-to-r from-amber-600 to-orange-600 text-white shadow-md shadow-amber-900/40 border border-amber-400/30 animate-pulse"
                  : "bg-zinc-900 text-amber-400 hover:text-white border border-amber-900/40"
              }`}
              data-testid="fundamental-analysis-tab-btn"
            >
              💎 10-Pillar Fundamental Scorecard
            </button>
          </div>

          {activeTab === "pairs" && <PairsTradingPanel />}
          {activeTab === "hrp" && <PortfolioAllocPanel />}
          {activeTab === "backtest" && <BacktestPanel />}
          {activeTab === "macro-sim" && <GlobalMacroSimulationPanel symbol={symbol || "RELIANCE"} sector={overview?.sector || "Conglomerate"} />}
          {activeTab === "qlib" && <QlibAlphaLeaderboardPanel onSelectStock={(sym) => { setSymbol(sym); setActiveTab("stock"); }} />}
          <div style={{ display: activeTab === "catalyst-radar" ? "block" : "none" }}>
            <CatalystRadarPanel />
          </div>
          {activeTab === "fundamentals" && (
            <div className="space-y-4">
              <div className="bg-[#0c0c0e] border border-zinc-800 rounded-xl p-6 shadow-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl pointer-events-none"></div>
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6 pb-4 border-b border-zinc-800 relative z-10">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-2xl shadow-inner">
                      💎
                    </div>
                    <div>
                      <h2 className="text-xl sm:text-2xl font-black text-zinc-100 tracking-tight flex items-center gap-2">
                        Institutional 10-Pillar Fundamental Scorecard
                      </h2>
                      <p className="text-xs sm:text-sm text-zinc-400 mt-1">
                        Deep quantitative forensic accounting, DuPont return decomposition, Altman/Beneish/Sloan distress models, and peer benchmarking.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setActiveTab("stock")}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-bold rounded-lg transition-all border border-zinc-700 flex items-center gap-2 shadow-sm"
                  >
                    <span>← Back to Stock Terminal</span>
                  </button>
                </div>

                {/* Quick Stock Switcher for Fundamental Scorecard */}
                <div className="mb-6 p-4 bg-zinc-900/60 border border-zinc-800/80 rounded-lg relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="w-full md:w-80 flex-shrink-0">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 block mb-1">🔍 Search Ticker to Score:</span>
                    <StockSearch onSelect={setSymbol} initial={symbol} />
                  </div>
                  <div className="flex-1">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 block mb-1">⚡ Quick Institutional Targets:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {POPULAR.map((s) => (
                        <button
                          key={s}
                          onClick={() => setSymbol(s)}
                          className={`px-2.5 py-1 text-xs font-mono tracking-wider rounded border transition-all ${
                            (symbol || "RELIANCE").toUpperCase().includes(s)
                              ? "bg-amber-600/20 text-amber-300 border-amber-500/50 font-bold shadow-sm"
                              : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:border-zinc-600 hover:text-zinc-200"
                          }`}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="relative z-10">
                  <FundamentalDeck symbol={symbol || "RELIANCE.NS"} />
                </div>
              </div>
            </div>
          )}

          {activeTab === "stock" && (
            <>
              {!symbol && !loading && (
                <>
                  <OvernightSightPanel />
                  <EmptyState onPick={setSymbol} />
                </>
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
                    {regime && (
                      <span className={`px-1.5 py-0.5 text-[10px] tracking-widest uppercase border ${
                        regime.trend.includes("Uptrend") && regime.volatility_state !== "Expanding" ? "bg-emerald-950/40 text-emerald-400 border-emerald-900/50" :
                        regime.trend.includes("Downtrend") && regime.volatility_state === "Expanding" ? "bg-red-950/40 text-red-400 border-red-900/50" :
                        regime.trend.includes("Unknown") ? "bg-zinc-900 text-zinc-400 border-zinc-800" :
                        "bg-amber-950/30 text-amber-400 border-amber-900/50"
                      }`} title={regime.note}>
                        {regime.regime_label}
                      </span>
                    )}
                    <button
                      onClick={toggleStar}
                      data-testid="watchlist-star-btn"
                      className={`flex items-center gap-1 px-2 py-0.5 text-[10px] tracking-widest uppercase border ${
                        starred ? "bg-amber-500/20 text-amber-300 border-amber-700" : "bg-zinc-900 text-zinc-400 border-zinc-700 hover:text-zinc-100"
                      } transition-colors`}
                    >
                      {starred ? <Star size={11} className="fill-amber-300" /> : <StarOff size={11} />}
                      {starred ? "Watching" : "Watchlist"}
                    </button>
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
              {/* Chart + Depth + Macro + Patterns */}

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 mb-3">
                <div className="lg:col-span-8 flex flex-col gap-3">
                  <Panel title={`Price Chart · ${overview.symbol}`} testId="chart-panel" className="h-full min-h-[320px]">
                    <StockChart symbol={overview.symbol} />
                  </Panel>
                </div>
                <div className="lg:col-span-4 flex flex-col gap-3">
                  <MarketDepthPanel symbol={overview.symbol} />
                  <PatternsPanel symbol={overview.symbol} />
                  <MacroPanel />
                </div>
              </div>

              {/* Phase 6: Asymmetric Beta & Macro Tail Risk Coupling Widget */}
              <StockMacroCouplingWidget
                symbol={overview.symbol}
                sector={overview.sector || "Conglomerate"}
                onSwitchToMacro={() => setActiveTab("macro-sim")}
              />

              {/* Mathematical Predictor */}
              <MLPredictor symbol={overview.symbol} />

              {/* AI Analysis Suite */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
                <AIVerdict symbol={overview.symbol} />
                <AIRatioAnalysisPanel symbol={overview.symbol} pdfData={pdfData} />
                <AITechnicalAnalysis symbol={overview.symbol} />
                <AINewsAnalysis symbol={overview.symbol} />
              </div>

              {/* Dedicated Sectoral Analysis & News */}
              <div className="mb-3">
                <SectorAnalysisPanel symbol={overview.symbol} />
              </div>

              {/* Custom Ratio Analysis from Source */}
              <div className="mb-3">
                <RatioAnalysisPanel symbol={overview.symbol} onAnalyzed={setPdfData} />
              </div>

              {/* Dedicated Institutional 10-Pillar Fundamental Scorecard Card Section */}
              <div className="mb-4 bg-gradient-to-br from-[#0c0c0e] via-zinc-900/90 to-[#0c0c0e] border-2 border-emerald-500/30 rounded-xl p-4 sm:p-6 shadow-2xl relative overflow-hidden group hover:border-emerald-500/50 transition-all">
                <div className="absolute -top-24 -right-24 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-zinc-800/80 relative z-10">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-xl shadow-inner">
                      💎
                    </div>
                    <div>
                      <h3 className="text-base sm:text-lg font-bold text-zinc-100 tracking-tight flex flex-wrap items-center gap-2">
                        <span>Institutional 10-Pillar Fundamental Scorecard</span>
                        <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-emerald-950/90 text-emerald-300 border border-emerald-800 rounded-full shadow-sm">
                          FORENSIC AUDIT
                        </span>
                      </h3>
                      <p className="text-xs text-zinc-400 mt-0.5">
                        Deep quantitative forensic accounting, Beneish M-Score, Altman Z-Score, Sloan Accrual, and DuPont return decomposition.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setActiveTab("fundamentals")}
                    className="self-start sm:self-auto px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-all shadow-lg shadow-emerald-900/30 flex items-center gap-1.5 whitespace-nowrap border border-emerald-400/30 group-hover:scale-105"
                  >
                    <span>Full Scorecard View</span>
                    <span>→</span>
                  </button>
                </div>
                <div className="relative z-10">
                  <FundamentalDeck symbol={overview.symbol} />
                </div>
              </div>

              {/* FII/DII + Concalls */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
                <div className="lg:col-span-5">
                  <FiiDiiPanel />
                </div>
                <div className="lg:col-span-7">
                  <ConcallsPanel symbol={overview.symbol} />
                </div>
              </div>

              {/* Peer Comparison */}
              <PeersPanel symbol={overview.symbol} onSelect={setSymbol} />

              {/* Red Flags + Events */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
                <div className="lg:col-span-7">
                  <RedFlagsPanel symbol={overview.symbol} />
                </div>
                <div className="lg:col-span-5">
                  <EventsPanel symbol={overview.symbol} />
                </div>
              </div>

              {/* Social + Legal */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
                <div className="lg:col-span-6">
                  <SocialPanel symbol={overview.symbol} />
                </div>
                <div className="lg:col-span-6">
                  <LegalPanel symbol={overview.symbol} />
                </div>
              </div>



              {/* Options + Insider */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
                <div className="lg:col-span-7">
                  <OptionsPanel symbol={overview.symbol} />
                </div>
                <div className="lg:col-span-5">
                  <InsiderPanel symbol={overview.symbol} />
                </div>
              </div>

              {/* All other details */}
              <StockDetails symbol={overview.symbol} overview={overview} />
            </>
          )}

              {!symbol && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 mt-4">
                  <div className="lg:col-span-7 grid grid-cols-1 md:grid-cols-2 gap-3">
                    <MacroPanel />
                  </div>
                  <div className="lg:col-span-5">
                    <FiiDiiPanel />
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      <footer className="border-t border-zinc-800 mt-10 py-4 px-4">
        <div className="max-w-3xl mx-auto text-center space-y-2">
          <DisclaimerNote />
          <p className="text-[10px] tracking-widest uppercase text-zinc-600">
            Stock Sentinel IN · Data: NSE/BSE · Yahoo · Screener.in · Moneycontrol · Reddit · AI: Gemini 1.5 Flash
          </p>
        </div>
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
      macro context, news, FII/DII flows, concalls, options chain, peers, and an AI verdict from <span className="text-blue-400">Gemini 1.5 Flash</span>.
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
