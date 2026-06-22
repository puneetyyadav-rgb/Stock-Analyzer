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
            <div className="flex items-center justify-between mb-1.5">
              <h4 className="text-[10px] tracking-widest uppercase text-blue-400">X / Twitter</h4>
              {data.twitter_x?.tweets ? (
                <span className="text-[10px] text-zinc-400">{data.twitter_x.tweets.length} tweets analyzed</span>
              ) : (
                <span className="text-[9px] tracking-widest uppercase text-zinc-500">Unavailable</span>
              )}
            </div>
            {data.twitter_x?.error && (
               <p className="text-[11px] text-zinc-500 leading-snug">{data.twitter_x.error}</p>
            )}
            {data.twitter_x?.tweets && data.twitter_x.tweets.length === 0 && (
               <p className="text-[11px] text-zinc-500 leading-snug">No recent tweets found for this ticker.</p>
            )}
            {data.twitter_x?.tweets && data.twitter_x.tweets.length > 0 && (
               <p className="text-[11px] text-zinc-300 leading-snug">
                 Live FinTwit chatter is active. View the full feed in the <span className="font-semibold text-zinc-200">News Desk</span> tab.
               </p>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
