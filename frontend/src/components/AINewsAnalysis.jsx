import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Newspaper, Loader2, AlertCircle } from "lucide-react";
import { getAINews, getSocial } from "../lib/api";
import { DisclaimerNote } from "./Disclaimer";

export default function AINewsAnalysis({ symbol }) {
  const [newsAI, setNewsAI] = useState(null);
  const [socialData, setSocialData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setNewsAI(null);
    setSocialData(null);
    setErr(null);
  }, [symbol]);

  const run = async () => {
    setLoading(true);
    setErr(null);
    try {
      const [aiRes, socialRes] = await Promise.all([
        getAINews(symbol),
        getSocial(symbol)
      ]);
      
      if (aiRes.error) setErr(aiRes.error);
      else setNewsAI(aiRes);
      
      if (socialRes && socialRes.twitter_x && socialRes.twitter_x.tweets) {
        setSocialData(socialRes.twitter_x.tweets);
      }
    } catch (e) {
      setErr(e.message || "Failed to load News Analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel
      title="AI News Desk Analyst"
      right={
        <button
          onClick={run}
          disabled={loading}
          className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] tracking-widest uppercase font-medium bg-amber-700 text-amber-50 hover:bg-amber-600 disabled:opacity-50 transition-colors"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Newspaper size={12} />}
          {loading ? "Reading Headlines…" : newsAI ? "Re-Analyze" : "Generate News Analysis"}
        </button>
      }
    >
      {!newsAI && !loading && !err && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <Newspaper size={28} className="text-amber-500 mb-3" />
          <p className="text-sm text-zinc-400 max-w-md">
            Click <span className="font-mono text-zinc-200">Generate</span> to have the AI synthesize all recent headlines into a crux, key pointers, and price-impact scenarios.
          </p>
        </div>
      )}
      {loading && (
        <div className="flex items-center justify-center py-10 gap-2 text-zinc-400">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-xs tracking-widest uppercase">Synthesizing news catalysts…</span>
        </div>
      )}
      {err && (
        <div className="flex items-start gap-2 p-3 bg-red-950/40 border border-red-900/60 text-red-300 text-xs">
          <AlertCircle size={14} /> <span>{err}</span>
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
                  <h4 className="text-[10px] tracking-widest uppercase text-blue-400 mb-2">Live FinTwit Chatter</h4>
                  <div className="space-y-3 max-h-64 overflow-y-auto pr-2 custom-scrollbar">
                    {socialData.slice(0, 8).map((t, i) => (
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
    </Panel>
  );
}
