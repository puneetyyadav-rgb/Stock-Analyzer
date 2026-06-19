import React, { useEffect, useState } from "react";
import { Panel, KV } from "./Panel";
import { getFinancials, getCorporate, getHolders, getNews, getScreener, getTechnicals } from "../lib/api";
import { fmtNum, fmtPct, fmtBigNum, colorClass } from "../lib/format";
import { ExternalLink, TrendingUp, TrendingDown } from "lucide-react";

const Section = ({ children, hidden }) => hidden ? null : children;

export default function StockDetails({ symbol, overview }) {
  const [financials, setFinancials] = useState(null);
  const [corporate, setCorporate] = useState(null);
  const [holders, setHolders] = useState(null);
  const [news, setNews] = useState(null);
  const [screener, setScreener] = useState(null);
  const [technicals, setTechnicals] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setFinancials(null); setCorporate(null); setHolders(null); setNews(null); setScreener(null); setTechnicals(null);
    getFinancials(symbol).then(setFinancials).catch(() => {});
    getCorporate(symbol).then(setCorporate).catch(() => {});
    getHolders(symbol).then(setHolders).catch(() => {});
    getNews(symbol).then((d) => setNews(d.items)).catch(() => {});
    getScreener(symbol).then(setScreener).catch(() => {});
    getTechnicals(symbol).then(setTechnicals).catch(() => {});
  }, [symbol]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-3" data-testid="stock-details">
      {/* Fundamentals */}
      <div className="lg:col-span-4 space-y-3">
        <Panel title="Valuation & Ratios" testId="valuation-panel">
          <KV label="Market Cap" value={fmtBigNum(overview?.marketCap)} />
          <KV label="P/E (TTM)" value={fmtNum(overview?.peRatio)} />
          <KV label="Forward P/E" value={fmtNum(overview?.forwardPE)} />
          <KV label="P/B Ratio" value={fmtNum(overview?.pbRatio)} />
          <KV label="EPS (TTM)" value={fmtNum(overview?.eps)} />
          <KV label="Book Value" value={fmtNum(overview?.bookValue)} />
          <KV label="Div Yield" value={overview?.dividendYield ? fmtPct(overview.dividendYield) : "—"} />
          <KV label="Beta" value={fmtNum(overview?.beta)} />
        </Panel>
        <Panel title="Profitability & Health" testId="health-panel">
          <KV label="ROE" value={overview?.roe ? fmtPct(overview.roe * 100) : "—"} valueClass={colorClass(overview?.roe)} />
          <KV label="ROA" value={overview?.roa ? fmtPct(overview.roa * 100) : "—"} valueClass={colorClass(overview?.roa)} />
          <KV label="Profit Margin" value={overview?.profitMargin ? fmtPct(overview.profitMargin * 100) : "—"} valueClass={colorClass(overview?.profitMargin)} />
          <KV label="Operating Margin" value={overview?.operatingMargin ? fmtPct(overview.operatingMargin * 100) : "—"} valueClass={colorClass(overview?.operatingMargin)} />
          <KV label="Revenue Growth" value={overview?.revenueGrowth ? fmtPct(overview.revenueGrowth * 100) : "—"} valueClass={colorClass(overview?.revenueGrowth)} />
          <KV label="Earnings Growth" value={overview?.earningsGrowth ? fmtPct(overview.earningsGrowth * 100) : "—"} valueClass={colorClass(overview?.earningsGrowth)} />
          <KV label="Debt/Equity" value={fmtNum(overview?.debtToEquity)} />
        </Panel>
        <Panel title="Analyst View" testId="analyst-panel">
          <KV label="Recommendation" value={(overview?.recommendation || "—").toUpperCase()} valueClass="text-blue-400" />
          <KV label="Target Mean" value={overview?.targetMeanPrice ? `₹${fmtNum(overview.targetMeanPrice)}` : "—"} />
          <KV label="Target High" value={overview?.targetHighPrice ? `₹${fmtNum(overview.targetHighPrice)}` : "—"} valueClass="text-emerald-400" />
          <KV label="Target Low" value={overview?.targetLowPrice ? `₹${fmtNum(overview.targetLowPrice)}` : "—"} valueClass="text-red-400" />
          <KV label="# Analysts" value={overview?.numAnalysts || "—"} />
        </Panel>
      </div>

      {/* Technicals + Pros/Cons */}
      <div className="lg:col-span-4 space-y-3">
        <Panel title="Technical Indicators" testId="technicals-panel">
          <KV label="RSI (14)" value={fmtNum(technicals?.rsi)} valueClass={
            technicals?.rsi > 70 ? "text-red-400" : technicals?.rsi < 30 ? "text-emerald-400" : "text-zinc-200"
          } />
          <KV label="RSI Signal" value={technicals?.rsiSignal || "—"} />
          <KV label="MACD" value={fmtNum(technicals?.macd, 3)} valueClass={colorClass(technicals?.macdHistogram)} />
          <KV label="Signal Line" value={fmtNum(technicals?.macdSignal, 3)} />
          <KV label="SMA 50" value={technicals?.sma50 ? `₹${fmtNum(technicals.sma50)}` : "—"} />
          <KV label="SMA 200" value={technicals?.sma200 ? `₹${fmtNum(technicals.sma200)}` : "—"} />
          <KV label="Support (6M)" value={technicals?.support ? `₹${fmtNum(technicals.support)}` : "—"} valueClass="text-emerald-400" />
          <KV label="Resistance (6M)" value={technicals?.resistance ? `₹${fmtNum(technicals.resistance)}` : "—"} valueClass="text-red-400" />
          <KV label="Trend" value={technicals?.trend || "—"} valueClass={technicals?.trend === "Uptrend" ? "text-emerald-400" : "text-red-400"} />
        </Panel>
        <Section hidden={!screener?.pros?.length && !screener?.cons?.length}>
          <Panel title="Pros & Cons (Screener.in)" testId="pros-cons-panel">
            {screener?.pros?.length > 0 && (
              <>
                <h4 className="text-[10px] tracking-widest uppercase text-emerald-400 mb-1.5 flex items-center gap-1"><TrendingUp size={11} />Pros</h4>
                <ul className="space-y-1 mb-3">
                  {screener.pros.slice(0, 5).map((p, i) => (
                    <li key={i} className="text-xs text-zinc-300 leading-snug pl-2 border-l border-emerald-700/40">{p}</li>
                  ))}
                </ul>
              </>
            )}
            {screener?.cons?.length > 0 && (
              <>
                <h4 className="text-[10px] tracking-widest uppercase text-red-400 mb-1.5 flex items-center gap-1"><TrendingDown size={11} />Cons</h4>
                <ul className="space-y-1">
                  {screener.cons.slice(0, 5).map((p, i) => (
                    <li key={i} className="text-xs text-zinc-300 leading-snug pl-2 border-l border-red-700/40">{p}</li>
                  ))}
                </ul>
              </>
            )}
          </Panel>
        </Section>
      </div>

      {/* Quarterly + Corporate */}
      <div className="lg:col-span-4 space-y-3">
        <Panel title="Quarterly Results" testId="quarterly-panel">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[9px] tracking-widest uppercase text-zinc-500">
                <th className="text-left pb-1.5">Quarter</th>
                <th className="text-right pb-1.5">Revenue</th>
                <th className="text-right pb-1.5">Net Profit</th>
              </tr>
            </thead>
            <tbody>
              {(financials?.quarterly || []).slice(0, 5).map((q) => (
                <tr key={q.period} className="border-t border-zinc-800/40">
                  <td className="py-1 font-mono text-zinc-300">{q.period}</td>
                  <td className="py-1 font-mono tabular-nums text-right text-zinc-200">{fmtBigNum(q.revenue)}</td>
                  <td className={`py-1 font-mono tabular-nums text-right ${colorClass(q.netIncome)}`}>{fmtBigNum(q.netIncome)}</td>
                </tr>
              ))}
              {!financials?.quarterly?.length && <tr><td colSpan="3" className="text-zinc-600 py-2">No data</td></tr>}
            </tbody>
          </table>
        </Panel>
        <Panel title="Corporate Actions" testId="corporate-panel">
          <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-1">Recent Dividends</h4>
          {corporate?.dividends?.length ? (
            <ul className="text-xs space-y-0.5 mb-2">
              {corporate.dividends.slice(0, 5).map((d, i) => (
                <li key={i} className="flex justify-between border-b border-zinc-800/30 py-1">
                  <span className="font-mono text-zinc-400">{d.date}</span>
                  <span className="font-mono tabular-nums text-emerald-400">₹{fmtNum(d.amount)}</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-xs text-zinc-600 mb-2">No recent dividends</p>}
          <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-1 mt-2">Stock Splits</h4>
          {corporate?.splits?.length ? (
            <ul className="text-xs space-y-0.5">
              {corporate.splits.slice(0, 3).map((s, i) => (
                <li key={i} className="flex justify-between border-b border-zinc-800/30 py-1">
                  <span className="font-mono text-zinc-400">{s.date}</span>
                  <span className="font-mono tabular-nums text-blue-400">{fmtNum(s.ratio)}:1</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-xs text-zinc-600">No splits on record</p>}
        </Panel>
        <Panel title="Shareholding Pattern" testId="holders-panel">
          {holders?.majorHoldersBreakdown && Object.keys(holders.majorHoldersBreakdown).length > 0 ? (
            <ul className="text-xs space-y-1">
              {Object.entries(holders.majorHoldersBreakdown).map(([k, v]) => {
                const label = k.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase()).trim();
                return (
                  <li key={k} className="flex justify-between border-b border-zinc-800/30 py-1">
                    <span className="text-zinc-400">{label}</span>
                    <span className="font-mono tabular-nums text-zinc-200">{v}</span>
                  </li>
                );
              })}
            </ul>
          ) : <p className="text-xs text-zinc-600">Data unavailable</p>}
        </Panel>
      </div>

      {/* News full width */}
      <div className="lg:col-span-12">
        <Panel title="Latest News & Sentiment" testId="news-panel">
          {news === null && <p className="text-xs text-zinc-500">Loading news…</p>}
          {news && news.length === 0 && <p className="text-xs text-zinc-600">No recent news.</p>}
          {news && news.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-96 overflow-auto pr-1">
              {news.map((n, i) => (
                <a
                  key={i}
                  href={n.url}
                  target="_blank"
                  rel="noreferrer"
                  className="border border-zinc-800/60 p-2.5 hover:border-zinc-600 transition-colors block group"
                  data-testid={`news-item-${i}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="text-[9px] tracking-widest uppercase text-blue-400">{n.source}</span>
                    <ExternalLink size={10} className="text-zinc-600 group-hover:text-zinc-300 mt-0.5 shrink-0" />
                  </div>
                  <h4 className="text-xs text-zinc-200 font-medium leading-snug mb-1 group-hover:text-blue-300">{n.title}</h4>
                  {n.summary && <p className="text-[11px] text-zinc-500 line-clamp-2 leading-snug">{n.summary}</p>}
                  {n.publishedAt && <p className="text-[9px] text-zinc-600 mt-1 font-mono">{n.publishedAt}</p>}
                </a>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {/* About & Screener Ratios */}
      <div className="lg:col-span-12 grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Panel title="About Company" testId="about-panel">
          <p className="text-xs text-zinc-300 leading-relaxed whitespace-pre-line">
            {overview?.longBusinessSummary || screener?.about || "No description available."}
          </p>
          <div className="grid grid-cols-2 gap-x-3 mt-3">
            <KV label="Sector" value={overview?.sector || "—"} />
            <KV label="Industry" value={overview?.industry || "—"} />
            <KV label="Employees" value={overview?.employees ? fmtNum(overview.employees, 0) : "—"} />
            <KV label="Exchange" value={overview?.exchange || "—"} />
          </div>
        </Panel>
        <Panel title="Screener.in Key Ratios" testId="screener-ratios-panel">
          {screener?.ratios && Object.keys(screener.ratios).length > 0 ? (
            <div className="grid grid-cols-2 gap-x-3">
              {Object.entries(screener.ratios).slice(0, 14).map(([k, v]) => (
                <KV key={k} label={k} value={v} />
              ))}
            </div>
          ) : <p className="text-xs text-zinc-600">Screener data unavailable.</p>}
        </Panel>
      </div>
    </div>
  );
}
