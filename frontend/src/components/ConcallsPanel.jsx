import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Sparkles, Loader2, FileText, Presentation, Youtube } from "lucide-react";
import axios from "axios";
import SourceQA from "./SourceQA";
import ConcallSynthesisPanel from "./ConcallSynthesisPanel";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ConcallsPanel({ symbol }) {
  const [items, setItems] = useState(null);
  const [summaries, setSummaries] = useState({}); // {url: summary}
  const [loadingFor, setLoadingFor] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    setItems(null);
    const cachedSums = localStorage.getItem(`concallSummaries_${symbol}`);
    if (cachedSums) {
      try {
        setSummaries(JSON.parse(cachedSums));
      } catch (e) {
        setSummaries({});
      }
    } else {
      setSummaries({});
    }
    axios.get(`${API}/stock/${symbol}/concalls`)
      .then((r) => setItems(r.data.items || []))
      .catch(() => setItems([]));
  }, [symbol]);

  const summarize = async (item) => {
    if (!item.transcript) return;
    setLoadingFor(item.transcript);
    try {
      const r = await axios.post(`${API}/stock/${symbol}/concall-summary`, {
        transcriptUrl: item.transcript,
        date: item.date,
      }, { timeout: 90000 });
      setSummaries((s) => {
        const next = { ...s, [item.transcript]: r.data };
        try {
          localStorage.setItem(`concallSummaries_${symbol}`, JSON.stringify(next));
        } catch (e) {}
        return next;
      });
    } catch (e) {
      setSummaries((s) => ({ ...s, [item.transcript]: { error: e.response?.data?.detail || e.message || "Failed" } }));
    } finally {
      setLoadingFor(null);
    }
  };

  return (
    <Panel title="Concalls & Management Commentary (Screener)" testId="concalls-panel">
      {/* 2-Year Longitudinal Synthesis — always shown first */}
      <div className="mb-4">
        <ConcallSynthesisPanel symbol={symbol} />
      </div>

      {/* Per-Quarter AI Summaries */}
      <p className="text-[9px] tracking-widest uppercase text-zinc-500 mb-2">Quarter-by-Quarter Summaries</p>
      {items === null && <p className="text-xs text-zinc-500">Loading concalls…</p>}
      {items && items.length === 0 && <p className="text-xs text-zinc-600">No concall data found</p>}
      {items && items.length > 0 && (
        <div className="space-y-2 max-h-[480px] overflow-auto pr-1">
          {items.map((item, i) => {
            const summary = summaries[item.transcript];
            return (
              <div key={i} className="border border-zinc-800/60 p-2.5 bg-zinc-900/20" data-testid={`concall-${i}`}>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono font-medium text-zinc-200">{item.date}</span>
                    <div className="flex items-center gap-2">
                      {item.transcript && (
                        <a href={item.transcript} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[10px] text-blue-400 hover:underline" data-testid={`concall-transcript-${i}`}>
                          <FileText size={11} /> Transcript
                        </a>
                      )}
                      {item.ppt && (
                        <a href={item.ppt} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[10px] text-zinc-400 hover:underline">
                          <Presentation size={11} /> PPT
                        </a>
                      )}
                      {item.recording && (
                        <a href={item.recording} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[10px] text-red-400 hover:underline">
                          <Youtube size={11} /> Recording
                        </a>
                      )}
                    </div>
                  </div>
                  {item.transcript && (
                    <button
                      onClick={() => summarize(item)}
                      disabled={loadingFor === item.transcript}
                      data-testid={`summarize-concall-${i}`}
                      className="flex items-center gap-1 px-2 py-0.5 text-[10px] tracking-widest uppercase font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
                    >
                      {loadingFor === item.transcript ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
                      {summary ? "Re-Summarize" : "AI Summary"}
                    </button>
                  )}
                </div>
                {summary && !summary.error && (
                  <div className="mt-2 pt-2 border-t border-zinc-800 space-y-2" data-testid={`concall-summary-${i}`}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`px-1.5 py-0.5 text-[9px] tracking-widest uppercase ${
                        summary.sentimentScore >= 5 ? "bg-emerald-700 text-emerald-50" :
                        summary.sentimentScore >= 0 ? "bg-emerald-900/60 text-emerald-200" :
                        summary.sentimentScore >= -3 ? "bg-amber-700 text-amber-50" :
                        "bg-red-700 text-red-50"
                      }`}>
                        {summary.sentimentLabel}
                      </span>
                      <span className="text-[10px] text-zinc-400">Score: <span className="font-mono">{summary.sentimentScore}/10</span></span>
                      {summary.source === "alternative" && (
                        <span className="px-1.5 py-0.5 text-[9px] tracking-widest uppercase bg-amber-900/60 text-amber-200 border border-amber-700">
                          Indirect (news+screener)
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-200 italic leading-snug">{summary.verdict}</p>
                    {summary.highlights?.length > 0 && (
                      <SummarySection title="Highlights" items={summary.highlights} color="text-zinc-300" />
                    )}
                    {summary.managementGuidance?.length > 0 && (
                      <SummarySection title="Management Guidance" items={summary.managementGuidance} color="text-emerald-300" />
                    )}
                    {summary.capexPlans?.length > 0 && (
                      <SummarySection title="Capex & Expansion" items={summary.capexPlans} color="text-indigo-300" />
                    )}
                    {summary.newOrders?.length > 0 && (
                      <SummarySection title="New Orders / Wins" items={summary.newOrders} color="text-blue-300" />
                    )}
                    {summary.concerns?.length > 0 && (
                      <SummarySection title="Concerns" items={summary.concerns} color="text-amber-300" />
                    )}
                    {summary.qaInsights?.length > 0 && (
                      <SummarySection title="Q&A Insights" items={summary.qaInsights} color="text-zinc-300" />
                    )}
                    {summary.managementTone && (
                      <p className="text-[10px] text-zinc-500 leading-snug pt-1 border-t border-zinc-800/50">
                        <span className="uppercase tracking-widest">Tone:</span> {summary.managementTone}
                      </p>
                    )}
                    {summary.futureConclusion && (
                      <div className="mt-2.5 p-2.5 bg-emerald-950/20 border border-emerald-800/40 rounded-sm">
                        <h5 className="text-[9px] tracking-widest uppercase text-emerald-400 mb-1 font-semibold">Future Outlook Conclusion</h5>
                        <p className="text-[11px] leading-snug text-zinc-200">{summary.futureConclusion}</p>
                      </div>
                    )}
                  </div>
                )}
                {summary?.error && (
                  <p className="text-xs text-red-400 mt-2">{summary.error}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
      <SourceQA symbol={symbol} sourceName="Concalls & Management Commentary" data={summaries} />
    </Panel>
  );
}

const SummarySection = ({ title, items, color }) => (
  <div>
    <h5 className="text-[9px] tracking-widest uppercase text-zinc-500 mb-0.5">{title}</h5>
    <ul className="space-y-0.5">
      {items.map((it, i) => (
        <li key={i} className={`text-[11px] leading-snug ${color}`}>• {it}</li>
      ))}
    </ul>
  </div>
);
