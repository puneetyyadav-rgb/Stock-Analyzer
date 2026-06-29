import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { MessageSquare, ExternalLink, AlertCircle, Loader2 } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const sentimentColor = (label) => {
  if (label === "Bullish") return "bg-emerald-700 text-emerald-50";
  if (label === "Bearish") return "bg-red-700 text-red-50";
  return "bg-zinc-700 text-zinc-100";
};

export default function SocialPanel({ symbol }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setData(null);
    axios.get(`${API}/stock/${symbol}/social`).then((r) => setData(r.data)).catch(() => setData({ error: true }));
  }, [symbol]);

  return (
    <Panel title="Social Sentiment · Reddit + StockTwits" testId="social-panel">
      {!data && <div className="flex items-center gap-2 text-zinc-500 text-xs"><Loader2 size={12} className="animate-spin" /> Loading…</div>}
      {data && (
        <div className="space-y-3">
          {/* Reddit */}
          <div className="border border-zinc-800/60 p-2.5" data-testid="reddit-block">
            <div className="flex items-center justify-between mb-1.5">
              <h4 className="text-[10px] tracking-widest uppercase text-orange-400 flex items-center gap-1">
                <MessageSquare size={11} /> Reddit
              </h4>
              {data.reddit?.available ? (
                <span className={`px-1.5 py-0.5 text-[9px] tracking-widest uppercase ${sentimentColor(data.reddit.sentiment)}`}>
                  {data.reddit.sentiment || "—"}
                </span>
              ) : (
                <span className="text-[9px] tracking-widest uppercase text-zinc-500">Unavailable</span>
              )}
            </div>
            {data.reddit?.available && data.reddit?.mention_count > 0 && (
              <>
                <div className="flex gap-4 text-[10px] mb-2">
                  <span className="text-zinc-400">Mentions: <span className="text-zinc-200 font-mono">{data.reddit.mention_count}</span></span>
                  <span className="text-zinc-400">Score: <span className="text-zinc-200 font-mono">{data.reddit.avg_sentiment_score}</span></span>
                </div>
                <ul className="space-y-1">
                  {(data.reddit.top_posts || []).map((p, i) => (
                    <li key={i} className="text-[11px] text-zinc-300 leading-snug flex items-start gap-1.5">
                      <span className="text-orange-500 shrink-0 mt-0.5">▲ {p.score}</span>
                      <a href={p.url} target="_blank" rel="noreferrer" className="hover:text-blue-300 truncate flex items-center gap-1 group">
                        <span className="truncate">{p.title}</span>
                        <ExternalLink size={10} className="shrink-0 opacity-50 group-hover:opacity-100" />
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {data.reddit?.available && data.reddit?.mention_count === 0 && (
              <p className="text-xs text-zinc-600">No mentions in the last month across IndianStreetBets / IndiaInvestments / DalalStreetTalks.</p>
            )}
            {!data.reddit?.available && (
              <div className="flex items-start gap-1.5 text-[11px] text-zinc-500 leading-snug">
                <AlertCircle size={11} className="text-amber-400 shrink-0 mt-0.5" />
                <span>{data.reddit?.reason || data.reddit?.error || "Reddit API not configured"}</span>
              </div>
            )}
          </div>

          {/* StockTwits */}
          <div className="border border-zinc-800/60 p-2.5" data-testid="stocktwits-block">
            <div className="flex items-center justify-between mb-1.5">
              <h4 className="text-[10px] tracking-widest uppercase text-emerald-400">StockTwits</h4>
              {data.stocktwits?.available ? (
                <span className="text-[10px] text-zinc-400">{data.stocktwits.message_count} msgs</span>
              ) : (
                <span className="text-[9px] tracking-widest uppercase text-zinc-500">Unavailable</span>
              )}
            </div>
            {data.stocktwits?.available && data.stocktwits?.bullish_pct !== null && (
              <div className="space-y-1">
                <div className="flex h-2 bg-zinc-900 overflow-hidden">
                  <div className="bg-emerald-600 h-full" style={{ width: `${data.stocktwits.bullish_pct}%` }} />
                  <div className="bg-red-600 h-full" style={{ width: `${data.stocktwits.bearish_pct}%` }} />
                </div>
                <div className="flex justify-between text-[10px] font-mono">
                  <span className="text-emerald-400">{data.stocktwits.bullish_pct}% Bullish</span>
                  <span className="text-red-400">{data.stocktwits.bearish_pct}% Bearish</span>
                </div>
              </div>
            )}
            {data.stocktwits?.available && data.stocktwits?.bullish_pct === null && (
              <p className="text-xs text-zinc-600">No tagged sentiment in recent messages.</p>
            )}
            {!data.stocktwits?.available && (
              <p className="text-[11px] text-zinc-500 leading-snug">{data.stocktwits?.reason || "No India coverage for this ticker."}</p>
            )}
          </div>

          {/* Twitter / X */}
          <div className="border border-zinc-800/60 p-2.5" data-testid="twitter-block">
            {(() => {
              const tweets = data.twitter_x?.tweets || [];
              const twCount = tweets.length;
              const twAvg = twCount > 0 ? tweets.reduce((acc, t) => acc + (t.sentimentScore || 0), 0) / twCount : 0;
              const twLabel = twAvg > 0.15 ? "BULLISH" : twAvg < -0.15 ? "BEARISH" : "NEUTRAL";
              const labelColor = twLabel === "BULLISH" ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" : twLabel === "BEARISH" ? "bg-red-500/20 text-red-400 border-red-500/30" : "bg-zinc-500/20 text-zinc-300 border-zinc-500/30";

              return (
                <>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <h4 className="text-[10px] tracking-widest uppercase text-blue-400 font-semibold">X / Twitter</h4>
                      {twCount > 0 && (
                        <span className={`text-[9px] font-bold tracking-widest uppercase px-1.5 py-0.5 rounded border ${labelColor}`}>
                          {twLabel}
                        </span>
                      )}
                    </div>
                    {twCount > 0 ? (
                      <span className="text-[10px] text-zinc-400">{twCount} analyzed</span>
                    ) : (
                      <span className="text-[9px] tracking-widest uppercase text-zinc-500">Unavailable</span>
                    )}
                  </div>

                  {data.twitter_x?.error && (
                     <p className="text-[11px] text-zinc-500 leading-snug mb-2">{data.twitter_x.error}</p>
                  )}
                  {twCount === 0 && (
                     <p className="text-[11px] text-zinc-500 leading-snug">No recent tweets found for this ticker.</p>
                  )}
                  {twCount > 0 && (
                    <div className="space-y-2.5 mt-2">
                      {tweets.slice(0, 4).map((t, idx) => (
                        <div key={idx} className="pb-2 border-b border-zinc-800/60 last:border-0 last:pb-0">
                          <div className="flex items-center justify-between text-[11px] mb-0.5">
                            <span className="font-medium text-zinc-200 truncate max-w-[180px]">{t.author}</span>
                            <span className={`text-[8px] tracking-wider uppercase px-1 py-0.2 rounded font-mono ${
                              t.sentimentLabel === 'Bullish' ? 'text-emerald-400 bg-emerald-950/40' :
                              t.sentimentLabel === 'Bearish' ? 'text-red-400 bg-red-950/40' : 'text-zinc-400 bg-zinc-800'
                            }`}>
                              {t.sentimentLabel} ({t.sentimentScore})
                            </span>
                          </div>
                          <p className="text-[11px] text-zinc-400 leading-relaxed line-clamp-2">{t.text}</p>
                        </div>
                      ))}
                      <div className="pt-1 text-center">
                        <span className="text-[10px] text-blue-400 font-medium">View all {twCount} analyzed tweets in News Desk tab &rarr;</span>
                      </div>
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        </div>
      )}
    </Panel>
  );
}
