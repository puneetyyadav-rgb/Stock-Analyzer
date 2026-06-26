import React, { useState, useRef, useEffect } from "react";
import { MessageCircleQuestion, Send, Loader2, X, Sparkles } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SUGGESTIONS = {
  "Concalls & Management Commentary": [
    "What revenue guidance did management give?",
    "Are there any capex expansion plans?",
    "What risks did analysts highlight in Q&A?",
  ],
  "News Desk & Corporate Filings": [
    "What is the most important recent headline?",
    "Are there any negative developments?",
    "Summarize the news sentiment",
  ],
  "Sectoral Analysis": [
    "Is the stock outperforming its sector index?",
    "What are the peer aggregate valuations?",
    "How does delivery volume look?",
  ],
  "Insider & Promoter Pledging": [
    "What percentage of promoter shares are pledged?",
    "Are insiders buying or selling recently?",
    "Any bulk or block deals?",
  ],
  "SEBI & Legal Tracker": [
    "Are there any SEBI penalties or warnings?",
    "Any ongoing court cases?",
    "Summarize the legal risk profile",
  ],
  "Red Flags": [
    "What are the main red flags?",
    "Is promoter pledge dangerously high?",
    "Any governance concerns?",
  ],
  "AI Ratio Analysis (PDF)": [
    "What is the debt-to-equity ratio?",
    "How are operating margins trending?",
    "Summarize the key valuation ratios",
  ],
};

const DEFAULT_SUGGESTIONS = [
  "Summarize the key numbers",
  "What are the main risks?",
  "What is the most important takeaway?",
];

export default function SourceQA({ symbol, sourceName, data }) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const bottomRef = useRef(null);

  const suggestions = SUGGESTIONS[sourceName] || DEFAULT_SUGGESTIONS;

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [history]);

  const ask = async (q) => {
    const trimmed = (q || question).trim();
    if (!trimmed || loading) return;

    setHistory((h) => [...h, { role: "user", text: trimmed }]);
    setQuestion("");
    setLoading(true);

    try {
      const r = await axios.post(
        `${API}/stock/${symbol}/ask-source`,
        { sourceName, sourceData: data, question: trimmed },
        { timeout: 60000 }
      );
      setHistory((h) => [...h, { role: "ai", text: r.data.answer }]);
    } catch (e) {
      setHistory((h) => [
        ...h,
        { role: "ai", text: e.response?.data?.detail || e.message || "Failed to get answer", error: true },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  };

  if (!data || (typeof data === "object" && Object.keys(data).length === 0)) return null;

  return (
    <div className="mt-3 border-t border-zinc-800/50 pt-2">
      {/* Toggle Button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] tracking-widest uppercase font-medium
                     bg-gradient-to-r from-violet-900/40 to-indigo-900/40 border border-violet-800/50
                     text-violet-300 hover:text-violet-100 hover:border-violet-600 transition-all duration-200
                     hover:shadow-[0_0_12px_rgba(139,92,246,0.15)] group"
        >
          <MessageCircleQuestion size={12} className="group-hover:scale-110 transition-transform" />
          Ask AI About This Source
        </button>
      )}

      {/* Expanded Chat Drawer */}
      {open && (
        <div className="border border-violet-900/40 bg-gradient-to-b from-violet-950/20 to-zinc-950/50 rounded overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-violet-900/30 bg-violet-950/30">
            <div className="flex items-center gap-1.5">
              <Sparkles size={11} className="text-violet-400" />
              <span className="text-[9px] tracking-widest uppercase text-violet-400 font-medium">
                Source-Only AI Q&A · {sourceName}
              </span>
            </div>
            <button
              onClick={() => { setOpen(false); setHistory([]); }}
              className="text-zinc-500 hover:text-zinc-300 transition-colors p-0.5"
            >
              <X size={12} />
            </button>
          </div>

          {/* Chat History */}
          <div className="max-h-[240px] overflow-auto px-3 py-2 space-y-2">
            {history.length === 0 && !loading && (
              <div className="space-y-2">
                <p className="text-[10px] text-zinc-500 italic">
                  Ask any question — AI will answer using ONLY the data from this section. No external knowledge allowed.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {suggestions.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => ask(s)}
                      className="px-2 py-1 text-[10px] border border-violet-800/40 text-violet-300/80
                                 hover:bg-violet-900/30 hover:text-violet-200 hover:border-violet-600/60
                                 transition-all duration-150 rounded-sm"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {history.map((msg, i) => (
              <div
                key={i}
                className={`text-xs leading-relaxed ${
                  msg.role === "user"
                    ? "text-violet-300 font-medium pl-2 border-l-2 border-violet-600"
                    : msg.error
                    ? "text-red-400 bg-red-950/20 p-2 rounded border border-red-900/30"
                    : "text-zinc-200 bg-zinc-900/40 p-2 rounded border border-zinc-800/40"
                }`}
              >
                {msg.role === "ai" && !msg.error && (
                  <span className="text-[9px] tracking-widest uppercase text-violet-500 block mb-1">AI Answer</span>
                )}
                {msg.text}
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-violet-400 text-xs py-1">
                <Loader2 size={12} className="animate-spin" />
                <span className="tracking-widest uppercase text-[10px]">Reading source data…</span>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input Bar */}
          <div className="flex items-center gap-2 px-3 py-2 border-t border-violet-900/30 bg-zinc-950/60">
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about this data…"
              disabled={loading}
              className="flex-1 bg-zinc-900/60 border border-zinc-700/50 text-xs text-zinc-200 px-2.5 py-1.5
                         placeholder:text-zinc-600 focus:outline-none focus:border-violet-600 disabled:opacity-50
                         rounded-sm transition-colors"
            />
            <button
              onClick={() => ask()}
              disabled={loading || !question.trim()}
              className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] tracking-widest uppercase font-medium
                         bg-violet-700 text-white hover:bg-violet-600 disabled:opacity-40 transition-colors rounded-sm"
            >
              <Send size={10} />
              Ask
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
