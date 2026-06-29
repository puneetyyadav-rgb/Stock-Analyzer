import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Newspaper, Loader2, AlertCircle, ExternalLink } from "lucide-react";
import { getAINews, getSocial } from "../lib/api";
import axios from "axios";
import { DisclaimerNote } from "./Disclaimer";
import SourceQA from "./SourceQA";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const sentimentColor = (label) => {
  if (label === "Positive") return "text-emerald-400";
  if (label === "Negative") return "text-red-400";
  return "text-zinc-400";
};

export default function AINewsAnalysis({ symbol }) {
  const [tab, setTab] = useState("ai_summary");
  
  // AI State
  const [newsAI, setNewsAI] = useState(null);
  const [socialData, setSocialData] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiErr, setAiErr] = useState(null);

  // Split News State
  const [splitData, setSplitData] = useState(null);
  const [splitLoading, setSplitLoading] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setNewsAI(null);
    setSocialData(null);
    setAiErr(null);
    setSplitData(null);
    
    // Fetch split news
    setSplitLoading(true);
    axios.get(`${API}/stock/${symbol}/news-split`)
      .then((r) => setSplitData(r.data))
      .catch(() => setSplitData({ company: [], sector_news: [], market: [], counts: {} }))
      .finally(() => setSplitLoading(false));
  }, [symbol]);

  const runAI = async () => {
    setAiLoading(true);
    setAiErr(null);
    try {
      const [aiRes, socialRes] = await Promise.all([
        getAINews(symbol),
        getSocial(symbol)
      ]);
      
      if (aiRes.error) setAiErr(aiRes.error);
      else setNewsAI(aiRes);
      
      if (socialRes && socialRes.twitter_x && socialRes.twitter_x.tweets) {
        setSocialData(socialRes.twitter_x.tweets);
      }
    } catch (e) {
      setAiErr(e.message || "Failed to load News Analysis");
    } finally {
      setAiLoading(false);
    }
  };

  const TABS = [
    { key: "ai_summary", label: "AI Summary", count: null },
    { key: "twitter_x", label: "🐦 FinTwit Feed", count: socialData?.length || null },
    { key: "company", label: "Company", count: splitData?.counts?.company },
    { key: "sector_news", label: "Sector", count: splitData?.counts?.sector },
    { key: "market", label: "Market / Misc", count: splitData?.counts?.market },
  ];

  const renderSplitNews = (items) => {
    if (!items || items.length === 0) {
      return <p className="text-xs text-zinc-600 py-4">No news found for this category at the moment.</p>;
    }
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-[420px] overflow-auto pr-1">
        {items.map((n, i) => (
          <a
            key={i}
            href={n.url}
            target="_blank"
            rel="noreferrer"
            className="border border-zinc-800/60 p-2.5 hover:border-zinc-600 transition-colors block group"
          >
            <div className="flex items-start justify-between gap-2 mb-1">
              <span className="text-[9px] tracking-widest uppercase text-blue-400">{n.source}</span>
              <ExternalLink size={10} className="text-zinc-600 group-hover:text-zinc-300 mt-0.5 shrink-0" />
            </div>
            <h4 className="text-xs text-zinc-200 font-medium leading-snug mb-1 group-hover:text-blue-300">{n.title}</h4>
            {n.summary && <p className="text-[11px] text-zinc-500 line-clamp-2 leading-snug">{n.summary}</p>}
            <div className="flex items-center justify-between mt-1">
              <span className={`text-[9px] tracking-widest uppercase ${sentimentColor(n.sentimentLabel)}`}>{n.sentimentLabel || "—"}</span>
              {n.publishedAt && <span className="text-[9px] text-zinc-600 font-mono">{n.publishedAt}</span>}
            </div>
          </a>
        ))}
      </div>
    );
  };

  return (
    <Panel
      title="News Desk & AI Analyst"
      right={
        <div className="flex items-center gap-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-2 py-0.5 text-[10px] tracking-widest uppercase font-medium border ${
                tab === t.key
                  ? "bg-zinc-100 text-zinc-950 border-zinc-100"
                  : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:border-zinc-600"
              }`}
            >
              {t.label} {t.count !== null && t.count !== undefined && <span className="ml-1 font-mono">{t.count}</span>}
            </button>
          ))}
        </div>
      }
    >
      {tab === "ai_summary" && (
        <div className="pt-2">
          {!newsAI && !aiLoading && !aiErr && (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <Newspaper size={28} className="text-amber-500 mb-3" />
              <p className="text-sm text-zinc-400 max-w-md mb-4">
                Have the AI synthesize all recent headlines into a crux, key pointers, and price-impact scenarios.
              </p>
              <button
                onClick={runAI}
                className="flex items-center gap-1.5 px-4 py-2 text-xs tracking-widest uppercase font-medium bg-amber-700 text-amber-50 hover:bg-amber-600 transition-colors rounded-sm"
              >
                <Newspaper size={14} /> Generate News Analysis
              </button>
            </div>
          )}
          {aiLoading && (
            <div className="flex items-center justify-center py-10 gap-2 text-zinc-400">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-xs tracking-widest uppercase">Synthesizing news catalysts…</span>
            </div>
          )}
          {aiErr && (
            <div className="flex items-start gap-2 p-3 bg-red-950/40 border border-red-900/60 text-red-300 text-xs">
              <AlertCircle size={14} /> <span>{aiErr}</span>
            </div>
          )}
          {newsAI && !newsAI.error && (
            <div className="space-y-4">
              {!newsAI.dataSufficient ? (
                <div className="p-4 bg-zinc-900/50 border border-zinc-800 rounded text-center">
                  <AlertCircle size={24} className="text-amber-500 mx-auto mb-2" />
                  <h4 className="text-sm font-semibold text-zinc-200 mb-1">Low News Volume</h4>
                  <p className="text-xs text-zinc-400">
                    There are not enough substantive recent headlines or corporate announcements to draw a confident conclusion.
                  </p>
                </div>
              ) : (
                <>
                  <div className="p-3 bg-amber-950/10 border border-amber-900/30 rounded">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-[10px] tracking-widest uppercase text-amber-500">The Crux</h4>
                      {newsAI.headlinesAnalyzed && (
                        <span className="text-[9px] tracking-widest uppercase text-zinc-500">
                          Analyzed {newsAI.headlinesAnalyzed} updates
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-semibold text-zinc-200">{newsAI.crux}</p>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <h4 className="text-[10px] tracking-widest uppercase text-zinc-400">Summary</h4>
                      <p className="text-xs text-zinc-300 leading-relaxed">{newsAI.summary}</p>
                    </div>
                    
                    <div className="space-y-2">
                      <h4 className="text-[10px] tracking-widest uppercase text-blue-400">Main Pointers</h4>
                      <ul className="space-y-2">
                        {(newsAI.mainPointers || []).map((ptr, i) => (
                          <li key={i} className="text-xs text-zinc-300 flex items-start gap-2">
                            <span className="text-blue-500 mt-0.5">•</span>
                            <div className="flex flex-col">
                              <span>{ptr.point}</span>
                              {ptr.sourceDate && <span className="text-[9px] text-zinc-500 mt-0.5">{ptr.sourceDate}</span>}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded">
                      <h4 className="text-[10px] tracking-widest uppercase text-emerald-400 mb-2">Directional Bias</h4>
                      {newsAI.directionalBias ? (
                        <div className="space-y-2 text-xs">
                          <div className="flex items-center gap-2">
                            <span className="text-zinc-400">Bias:</span>
                            <span className={`font-semibold ${newsAI.directionalBias.bias === 'Bullish' ? 'text-emerald-400' : newsAI.directionalBias.bias === 'Bearish' ? 'text-red-400' : 'text-zinc-300'}`}>
                              {newsAI.directionalBias.bias}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-zinc-400">Magnitude:</span>
                            <span className="text-zinc-200">{newsAI.directionalBias.magnitude}</span>
                          </div>
                          <div className="mt-2 text-zinc-300">{newsAI.directionalBias.basis}</div>
                        </div>
                      ) : (
                        <p className="text-xs text-zinc-400">No bias data</p>
                      )}
                    </div>
                    
                    <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded">
                      <h4 className="text-[10px] tracking-widest uppercase text-purple-400 mb-2">"What If" Scenarios</h4>
                      <ul className="space-y-3">
                        {(newsAI.scenarios || []).map((sc, i) => (
                          <li key={i} className="flex flex-col gap-1 text-xs pb-2 border-b border-zinc-800/50 last:border-0 last:pb-0">
                            <div className="flex justify-between items-start">
                              <span className="text-zinc-400 font-semibold uppercase tracking-wider text-[9px]">If this happens:</span>
                              {sc.probability && (
                                <span className="text-[8px] tracking-widest uppercase px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded">
                                  {sc.probability}
                                </span>
                              )}
                            </div>
                            <span className="text-zinc-200">{sc.trigger}</span>
                            <span className="text-purple-400 font-semibold uppercase tracking-wider text-[9px] mt-1">Then expect:</span>
                            <span className="text-zinc-300">{sc.expectedImpact}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  
                  {socialData && socialData.length > 0 && (
                    <div className="p-3 bg-blue-950/20 border border-blue-900/50 rounded mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-[10px] tracking-widest uppercase text-blue-400 font-bold">Live FinTwit Highlights</h4>
                        <button onClick={() => setTab("twitter_x")} className="text-[10px] text-blue-300 hover:underline">View All {socialData.length} Tweets &rarr;</button>
                      </div>
                      <div className="space-y-3">
                        {socialData.slice(0, 4).map((t, i) => (
                          <div key={i} className="pb-2 border-b border-zinc-800/50 last:border-0 last:pb-0">
                            <div className="flex justify-between items-start mb-1">
                              <span className="text-xs font-semibold text-zinc-300">{t.author} <span className="text-zinc-500 font-normal">@{t.handle}</span></span>
                              <span className={`text-[8px] tracking-widest uppercase px-1.5 py-0.5 rounded ${
                                    t.sentimentLabel === 'Bullish' ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-900' :
                                    t.sentimentLabel === 'Bearish' ? 'bg-red-950/50 text-red-400 border border-red-900' :
                                    'bg-zinc-800 text-zinc-300 border border-zinc-700'
                                  }`}>
                                {t.sentimentLabel}
                              </span>
                            </div>
                            <p className="text-xs text-zinc-400 whitespace-pre-wrap">{t.text}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
              <DisclaimerNote className="bg-transparent border-0 pt-2" />
            </div>
          )}
        </div>
      )}
      
      {tab === "twitter_x" && (
        <div className="pt-2">
          {!socialData || socialData.length === 0 ? (
            <p className="text-xs text-zinc-600 py-4">No FinTwit chatter found for this ticker.</p>
          ) : (
            <div>
              <div className="p-3 bg-blue-950/30 border border-blue-800/60 rounded mb-3 flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-blue-300 uppercase tracking-wider">Quant FinTwit Consensus</h4>
                  <p className="text-[11px] text-zinc-400">Sample Depth: {socialData.length} analyzed discussions</p>
                </div>
                {(() => {
                  const avg = socialData.reduce((acc, t) => acc + (t.sentimentScore || 0), 0) / socialData.length;
                  const lbl = avg > 0.15 ? "BULLISH" : avg < -0.15 ? "BEARISH" : "NEUTRAL";
                  const col = lbl === "BULLISH" ? "bg-emerald-500/20 text-emerald-400 border-emerald-500" : lbl === "BEARISH" ? "bg-red-500/20 text-red-400 border-red-500" : "bg-zinc-800 text-zinc-300 border-zinc-600";
                  return <span className={`text-xs font-bold px-3 py-1 rounded border ${col}`}>{lbl} ({avg.toFixed(2)})</span>;
                })()}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[480px] overflow-auto pr-1">
                {socialData.map((t, i) => (
                  <div key={i} className="border border-zinc-800/60 p-2.5 bg-zinc-900/30 rounded">
                    <div className="flex justify-between items-start mb-1 gap-2">
                      <span className="text-xs font-semibold text-zinc-200 truncate">{t.author} <span className="text-zinc-500 font-normal">@{t.handle}</span></span>
                      <span className={`text-[8px] tracking-widest uppercase px-1.5 py-0.5 rounded shrink-0 font-mono ${
                            t.sentimentLabel === 'Bullish' ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800' :
                            t.sentimentLabel === 'Bearish' ? 'bg-red-950/60 text-red-400 border border-red-800' :
                            'bg-zinc-800 text-zinc-400 border border-zinc-700'
                          }`}>
                        {t.sentimentLabel} ({t.sentimentScore})
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-300 leading-relaxed">{t.text}</p>
                    <div className="mt-1.5 text-right">
                      <span className="text-[9px] text-zinc-600 font-mono">{t.createdAt}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab !== "ai_summary" && tab !== "twitter_x" && (
        <div className="pt-2">
          {splitLoading ? (
            <div className="flex items-center gap-2 text-zinc-500 text-xs"><Loader2 size={12} className="animate-spin" /> Loading…</div>
          ) : (
            renderSplitNews(splitData?.[tab])
          )}
        </div>
      )}
      <SourceQA symbol={symbol} sourceName="News Desk & Corporate Filings" data={newsAI} />
    </Panel>
  );
}
