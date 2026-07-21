import React, { useState, useEffect, useRef } from 'react';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw,
  AlertTriangle, Globe, Sun, Info, Activity,
  ChevronDown, ChevronUp, Zap, Shield, DollarSign,
  BarChart2, Clock
} from 'lucide-react';
import { getOvernightBriefing } from '../lib/api';

// ─── Helpers ─────────────────────────────────────────────────────────────────

const getTodayISTKey = () => {
  const now = new Date();
  // IST = UTC+5:30
  const ist = new Date(now.getTime() + (5.5 * 60 * 60 * 1000));
  return `overnight_session_${ist.toISOString().slice(0, 10)}`;
};

const saveToCacheLS = (data) => {
  try {
    localStorage.setItem(getTodayISTKey(), JSON.stringify(data));
  } catch (e) { /* storage full or private mode */ }
};

const loadFromCacheLS = () => {
  try {
    const raw = localStorage.getItem(getTodayISTKey());
    return raw ? JSON.parse(raw) : null;
  } catch (e) { return null; }
};

const PctBadge = ({ val, className = '' }) => {
  if (val == null) return <span className={`text-slate-500 font-mono text-xs ${className}`}>—</span>;
  const color = val > 0 ? 'text-emerald-400' : val < 0 ? 'text-rose-400' : 'text-slate-400';
  const icon = val > 0 ? '▲' : val < 0 ? '▼' : '—';
  return (
    <span className={`font-mono text-xs font-semibold ${color} ${className}`}>
      {icon} {Math.abs(val).toFixed(2)}%
    </span>
  );
};

const AssetRow = ({ item }) => (
  <div className="flex items-center justify-between py-1.5 px-2 hover:bg-white/5 rounded-md transition-colors group">
    <span className="text-xs text-slate-300 font-medium truncate max-w-[120px] group-hover:text-white transition-colors">
      {item.name}
    </span>
    <div className="flex items-center gap-3 shrink-0">
      <span className="text-xs font-mono text-slate-400">
        {item.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
      </span>
      <div className="w-20 text-right">
        <PctBadge val={item.change_pct} />
      </div>
    </div>
  </div>
);

const CategoryBlock = ({ title, items, icon: Icon, accentColor }) => {
  if (!items || items.length === 0) return null;
  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
      <div className={`flex items-center gap-1.5 mb-2 pb-2 border-b border-slate-800`}>
        {Icon && <Icon className={`w-3.5 h-3.5 ${accentColor}`} />}
        <h5 className={`text-[10px] font-bold uppercase tracking-widest ${accentColor}`}>{title}</h5>
      </div>
      <div className="space-y-0.5">
        {items.map((item, i) => <AssetRow key={i} item={item} />)}
      </div>
    </div>
  );
};

// ─── Main Panel ───────────────────────────────────────────────────────────────

const OvernightSightPanel = () => {
  const [data, setData]           = useState(() => loadFromCacheLS()); // instant load from localStorage
  const [loading, setLoading]     = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]         = useState(null);
  const [lastFetch, setLastFetch] = useState(null);
  const [collapsed, setCollapsed] = useState(false);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  const fetchData = async (forceRefresh = false) => {
    if (forceRefresh) setRefreshing(true);
    else if (!data) setLoading(true); // only show full loading if no stale data
    // If we already have stale data, keep it visible while fetching

    try {
      const result = await getOvernightBriefing(forceRefresh);
      if (!isMounted.current) return;
      setData(result);
      saveToCacheLS(result);
      setError(null);
      setLastFetch(new Date());
    } catch (err) {
      if (!isMounted.current) return;
      console.error(err);
      if (!data) setError('Failed to fetch morning briefing. Please try again.');
      // If we had stale data, keep it — don't blank the panel on a failed refresh
    } finally {
      if (isMounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  };

  useEffect(() => {
    fetchData(); // on mount, always do a background fetch
    const interval = setInterval(() => fetchData(true), 30 * 60 * 1000); // auto-refresh every 30 min
    return () => clearInterval(interval);
  }, []);

  // ── Loading State (only when no stale data) ──────────────────────────────
  if (loading && !data) {
    return (
      <div className="w-full bg-slate-950 border border-slate-800 rounded-xl flex flex-col items-center justify-center py-16 mb-6 gap-3">
        <Activity className="w-7 h-7 text-blue-500 animate-pulse" />
        <p className="text-slate-400 text-sm font-medium">Fetching overnight global markets…</p>
        <p className="text-slate-600 text-xs">Pulling {32} tickers + FRED yield + GIFT Nifty via NSEIX</p>
      </div>
    );
  }

  // ── Hard Error (no stale data either) ────────────────────────────────────
  if (error && !data) {
    return (
      <div className="w-full bg-slate-950 border border-red-900/40 rounded-xl p-8 mb-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-500 mx-auto mb-3" />
        <p className="text-slate-300 mb-4">{error}</p>
        <button onClick={() => fetchData(true)}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm transition-colors">
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const { raw, ai } = data;
  const allItems = raw?.data || [];

  // Categorize
  const byCategory = allItems.reduce((acc, item) => {
    const cat = item.category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  const yc = raw?.yield_curve || {};

  const biasGrad = ai?.market_bias === 'BULLISH'
    ? 'from-emerald-950/60 to-slate-950 border-emerald-700/40'
    : ai?.market_bias === 'BEARISH'
    ? 'from-rose-950/60 to-slate-950 border-rose-700/40'
    : 'from-slate-900 to-slate-950 border-slate-700/40';

  const biasText = ai?.market_bias === 'BULLISH' ? 'text-emerald-400'
    : ai?.market_bias === 'BEARISH' ? 'text-rose-400' : 'text-slate-300';

  const BiasIcon = ai?.market_bias === 'BULLISH' ? TrendingUp
    : ai?.market_bias === 'BEARISH' ? TrendingDown : Minus;

  return (
    <div className="w-full bg-slate-950 border border-slate-800 rounded-xl overflow-hidden mb-6 shadow-2xl">

      {/* ── Header ── */}
      <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between bg-black/30">
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-amber-500/10 rounded-lg border border-amber-500/20">
            <Sun className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">Overnight Sight</h2>
            <p className="text-[10px] text-slate-500 flex items-center gap-1">
              <Globe className="w-3 h-3" />
              Pre-market Global Briefing · {raw?.data?.length || 0} assets · GIFT Nifty (NSEIX) · FRED 2Y
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {refreshing && (
            <span className="text-[10px] text-blue-400 flex items-center gap-1 animate-pulse">
              <RefreshCw className="w-3 h-3 animate-spin" /> Refreshing…
            </span>
          )}
          {raw?.timestamp && (
            <span className="text-[10px] text-slate-600">
              <Clock className="w-3 h-3 inline mr-1" />
              {new Date(raw.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} IST
            </span>
          )}
          <button onClick={() => fetchData(true)} disabled={refreshing}
            className="p-1.5 hover:bg-slate-800 rounded-md transition-colors text-slate-500 hover:text-white">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-blue-400' : ''}`} />
          </button>
          <button onClick={() => setCollapsed(v => !v)}
            className="p-1.5 hover:bg-slate-800 rounded-md transition-colors text-slate-500 hover:text-white">
            {collapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {collapsed && (
        <div className="px-5 py-2 flex items-center gap-6 bg-black/20">
          {raw?.gift_nifty && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">GIFT Nifty</span>
              <span className="text-white font-bold font-mono text-sm">{raw.gift_nifty.price.toLocaleString()}</span>
              <PctBadge val={raw.gift_nifty.change_pct} />
            </div>
          )}
          {ai?.market_bias && (
            <div className={`flex items-center gap-1.5 ${biasText}`}>
              <BiasIcon className="w-3.5 h-3.5" />
              <span className="text-xs font-bold">{ai.market_bias}</span>
              <span className="text-slate-500 text-[10px]">{ai.bias_confidence}% conf.</span>
            </div>
          )}
          {ai?.nifty_expected_gap && (
            <span className="text-[10px] text-blue-400 flex items-center gap-1">
              <Info className="w-3 h-3" /> Gap: {ai.nifty_expected_gap}
            </span>
          )}
        </div>
      )}

      {!collapsed && (
        <div className="p-4 space-y-4">

          {/* ── Row 1: GIFT Nifty + AI Bias ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

            {/* GIFT Nifty Headline */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-40 h-40 bg-blue-600/5 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none" />
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                GIFT Nifty · NSEIX:NIFTY1!
              </p>
              {raw?.gift_nifty ? (
                <>
                  <div className="flex items-end gap-3 my-2">
                    <span className="text-4xl font-black text-white font-mono tracking-tight">
                      {raw.gift_nifty.price.toLocaleString()}
                    </span>
                    <PctBadge val={raw.gift_nifty.change_pct} className="!text-base mb-1" />
                  </div>
                  {ai?.nifty_expected_gap && (
                    <div className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-medium">
                      <Info className="w-3 h-3" /> AI Expected Gap: {ai.nifty_expected_gap}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-slate-600 italic text-xs mt-2">NSEIX data unavailable (try after 6 AM)</p>
              )}
            </div>

            {/* AI Bias Card */}
            <div className={`lg:col-span-2 bg-gradient-to-br ${biasGrad} border rounded-xl p-4 relative overflow-hidden`}>
              {ai ? (
                <>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <BiasIcon className={`w-6 h-6 ${biasText}`} />
                      <div>
                        <h3 className={`text-xl font-black tracking-tight ${biasText}`}>{ai.market_bias} BIAS</h3>
                        <span className="text-xs text-slate-400">{ai.bias_confidence}% confidence</span>
                      </div>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">Intraday Watch</p>
                      {ai.intraday_watch?.map((w, i) => (
                        <span key={i} className="block text-xs font-semibold text-amber-400">{w}</span>
                      ))}
                    </div>
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed mb-3">{ai.bias_rationale}</p>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="bg-black/20 rounded-lg p-2">
                      <p className="text-slate-500 text-[10px] uppercase tracking-wider mb-1">Global Cues</p>
                      <p className="text-slate-300 leading-relaxed">{ai.global_cues_summary}</p>
                    </div>
                    <div className="bg-black/20 rounded-lg p-2">
                      <p className="text-slate-500 text-[10px] uppercase tracking-wider mb-1">FII Interpretation</p>
                      <p className="text-slate-300 leading-relaxed">{ai.fii_interpretation || '—'}</p>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-2 py-4">
                  <Activity className="w-6 h-6 text-slate-600" />
                  <p className="text-slate-500 text-xs italic">AI synthesis unavailable · Raw data shown</p>
                </div>
              )}
            </div>
          </div>

          {/* ── Row 2: Global Markets Grid ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <CategoryBlock title="US Markets" items={byCategory.us} icon={BarChart2} accentColor="text-blue-400" />
            <CategoryBlock title="Asian Markets" items={byCategory.asia} icon={Globe} accentColor="text-violet-400" />
            <CategoryBlock title="European Markets" items={byCategory.europe} icon={Globe} accentColor="text-sky-400" />
            <CategoryBlock title="Volatility & Crypto" items={[...(byCategory.vol||[]), ...(byCategory.crypto||[])]} icon={Activity} accentColor="text-orange-400" />
          </div>

          {/* ── Row 3: Commodities + FX + Yield Curve ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <CategoryBlock title="Commodities" items={byCategory.commodity} icon={Zap} accentColor="text-amber-400" />
            <CategoryBlock title="FX Pairs" items={byCategory.fx} icon={DollarSign} accentColor="text-green-400" />

            {/* Yield Curve Panel */}
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
              <div className="flex items-center gap-1.5 mb-2 pb-2 border-b border-slate-800">
                <BarChart2 className="w-3.5 h-3.5 text-teal-400" />
                <h5 className="text-[10px] font-bold uppercase tracking-widest text-teal-400">US Yield Curve</h5>
                {yc.inverted && (
                  <span className="ml-auto text-[10px] font-bold text-rose-400 bg-rose-950/50 border border-rose-800/50 px-1.5 py-0.5 rounded">
                    ⚠ INVERTED
                  </span>
                )}
              </div>
              <div className="space-y-1.5">
                {[
                  { label: "2Y (FRED)", val: yc.us_2y_fred },
                  { label: "5Y", val: yc.us_5y },
                  { label: "10Y", val: yc.us_10y },
                  { label: "30Y", val: yc.us_30y },
                ].map(({ label, val }) => val != null && (
                  <div key={label} className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">{label}</span>
                    <span className="text-xs font-mono text-slate-200">{val.toFixed(3)}%</span>
                  </div>
                ))}
                {yc.spread_10y_2y != null && (
                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800">
                    <span className="text-xs text-slate-500">10Y–2Y Spread</span>
                    <span className={`text-xs font-mono font-bold ${yc.inverted ? 'text-rose-400' : 'text-emerald-400'}`}>
                      {yc.spread_10y_2y >= 0 ? '+' : ''}{yc.spread_10y_2y.toFixed(3)}%
                    </span>
                  </div>
                )}
                {ai?.yield_curve_signal && (
                  <p className="text-[10px] text-slate-500 leading-relaxed mt-2 pt-2 border-t border-slate-800">
                    {ai.yield_curve_signal}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* ── Row 4: Tailwinds / Headwinds / Trade Ideas ── */}
          {ai && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">

              {/* Tailwinds */}
              <div className="bg-emerald-950/20 border border-emerald-900/30 rounded-xl p-3">
                <div className="flex items-center gap-1.5 mb-3 pb-2 border-b border-emerald-900/30">
                  <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                  <h5 className="text-[10px] font-bold uppercase tracking-widest text-emerald-500">Sector Tailwinds</h5>
                </div>
                <div className="space-y-3">
                  {ai.sector_tailwinds?.map((item, i) => (
                    <div key={i} className="text-xs">
                      <span className="font-bold text-emerald-300 block mb-0.5">{item.sector}</span>
                      <span className="text-slate-400 leading-relaxed">{item.reason}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Headwinds */}
              <div className="bg-rose-950/20 border border-rose-900/30 rounded-xl p-3">
                <div className="flex items-center gap-1.5 mb-3 pb-2 border-b border-rose-900/30">
                  <TrendingDown className="w-3.5 h-3.5 text-rose-500" />
                  <h5 className="text-[10px] font-bold uppercase tracking-widest text-rose-500">Sector Headwinds</h5>
                </div>
                <div className="space-y-3">
                  {ai.sector_headwinds?.map((item, i) => (
                    <div key={i} className="text-xs">
                      <span className="font-bold text-rose-300 block mb-0.5">{item.sector}</span>
                      <span className="text-slate-400 leading-relaxed">{item.reason}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Trade Ideas */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
                <div className="flex items-center gap-1.5 mb-3 pb-2 border-b border-slate-800">
                  <Zap className="w-3.5 h-3.5 text-amber-400" />
                  <h5 className="text-[10px] font-bold uppercase tracking-widest text-amber-400">Trade Ideas</h5>
                </div>
                <div className="space-y-4">
                  {ai.trade_ideas?.map((trade, i) => (
                    <div key={i} className="text-xs border-b border-slate-800 last:border-0 pb-3 last:pb-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          trade.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' :
                          trade.direction === 'SHORT' ? 'bg-rose-500/20 text-rose-400' : 'bg-slate-500/20 text-slate-400'
                        }`}>{trade.direction}</span>
                        <span className="font-bold text-slate-200">{trade.sector}</span>
                      </div>
                      <p className="text-slate-400 mb-1.5 leading-relaxed">{trade.rationale}</p>
                      <div className="grid grid-cols-3 gap-1 text-[10px]">
                        <div className="bg-slate-800/50 rounded p-1">
                          <p className="text-slate-600 uppercase mb-0.5">Entry</p>
                          <p className="text-slate-300">{trade.entry_trigger || '—'}</p>
                        </div>
                        <div className="bg-rose-950/30 rounded p-1">
                          <p className="text-slate-600 uppercase mb-0.5">Stop</p>
                          <p className="text-rose-300">{trade.stop_concept || '—'}</p>
                        </div>
                        <div className="bg-emerald-950/30 rounded p-1">
                          <p className="text-slate-600 uppercase mb-0.5">Target</p>
                          <p className="text-emerald-300">{trade.target_concept || '—'}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ── Row 5: Key Risks + Commodity Alert ── */}
          {ai && (ai.key_risks?.length || ai.commodity_alert) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {ai.key_risks?.length > 0 && (
                <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-3 flex items-start gap-2">
                  <Shield className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Key Risks</p>
                    <div className="flex flex-wrap gap-2">
                      {ai.key_risks.map((r, i) => (
                        <span key={i} className="text-[10px] px-2 py-0.5 bg-slate-800 text-slate-400 rounded-full border border-slate-700">
                          {r}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              {ai.commodity_alert && (
                <div className="bg-amber-950/20 border border-amber-900/30 rounded-xl p-3 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-[10px] font-bold text-amber-500 uppercase tracking-wider mb-1">Commodity Alert</p>
                    <p className="text-xs text-slate-300 leading-relaxed">{ai.commodity_alert}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Row 6: Indian Domestic Close (Yesterday) ── */}
          {raw?.india_sectoral?.length > 0 && (
            <div className="bg-slate-900/30 border border-slate-800/50 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-4 bg-orange-500/60 rounded-full" />
                <h5 className="text-[10px] font-bold uppercase tracking-widest text-orange-400/80">
                  Indian Domestic Close — Yesterday's Session
                </h5>
                <span className="text-[10px] text-slate-600 ml-1">(Not overnight data — domestic day session)</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
                {raw.india_sectoral.map((item, i) => (
                  <div key={i} className="bg-slate-950 border border-slate-800 rounded-lg p-2 text-center">
                    <p className="text-[10px] text-slate-500 truncate mb-1">{item.name}</p>
                    <p className="text-xs font-mono text-slate-300 font-semibold">
                      {item.price?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </p>
                    <PctBadge val={item.change_pct} className="!text-[10px]" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Disclaimer ── */}
          {ai?.disclaimer && (
            <p className="text-[10px] text-slate-600 leading-relaxed border-t border-slate-800 pt-3">
              {ai.disclaimer}
            </p>
          )}

        </div>
      )}
    </div>
  );
};

export default OvernightSightPanel;
