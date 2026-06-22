import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Sparkles, Loader2, AlertCircle } from "lucide-react";
import { getAIVerdict } from "../lib/api";
import { DisclaimerNote } from "./Disclaimer";

const verdictColors = {
  "Bullish": "bg-emerald-600 text-emerald-50",
  "Bearish": "bg-red-600 text-red-50",
  "Neutral": "bg-zinc-600 text-zinc-50",
};

const factorTitles = {
  macroeconomic: "Macroeconomic",
  industryAndSector: "Industry & Sector",
  companyFinancials: "Company Financials",
  technicalAndMarket: "Technical & Market",
  newsAndSentiment: "News & Sentiment",
  globalShocks: "Global Shocks",
  regulatoryPolicy: "Regulatory Policy",
  demandSupplyTrade: "Demand-Supply & Trade",
  managementAndCorporate: "Management & Corporate"
};

export default function AIVerdict({ symbol }) {
  const [verdict, setVerdict] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setVerdict(null);
    setErr(null);
  }, [symbol]);

  const run = async () => {
    setLoading(true);
    setErr(null);
    try {
      const r = await getAIVerdict(symbol);
      if (r.error) setErr(r.error);
      else setVerdict(r);
    } catch (e) {
      setErr(e.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel
      title="AI Verdict (Gemini 3 Flash)"
      testId="ai-verdict-panel"
      right={
        <button
          onClick={run}
          disabled={loading}
          data-testid="generate-verdict-btn"
          className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] tracking-widest uppercase font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
          {loading ? "Analyzing 9 Factors…" : verdict ? "Re-Analyze" : "Generate Verdict"}
        </button>
      }
    >
      {!verdict && !loading && !err && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <Sparkles size={28} className="text-blue-500 mb-3" />
          <p className="text-sm text-zinc-400 max-w-md">
            Click <span className="font-mono text-zinc-200">Generate Verdict</span> to run AI analysis across all 9 factors:
            macro, sector, fundamentals, technicals, news, sentiment, regulatory & management commentary.
          </p>
        </div>
      )}
      {loading && (
        <div className="flex items-center justify-center py-10 gap-2 text-zinc-400">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-xs tracking-widest uppercase">Synthesizing across data points…</span>
        </div>
      )}
      {err && (
        <div className="flex items-start gap-2 p-3 bg-red-950/40 border border-red-900/60 text-red-300 text-xs">
          <AlertCircle size={14} /> <span>{err}</span>
        </div>
      )}
      {verdict && !verdict.error && (
        <div className="space-y-4" data-testid="ai-verdict-content">
          <div className="flex flex-wrap items-center gap-3 pb-3 border-b border-zinc-800">
            <div className={`px-3 py-1 text-xs font-bold tracking-widest uppercase ${verdictColors[verdict.thesis?.bias] || "bg-zinc-700 text-zinc-100"}`}>
              {verdict.thesis?.bias || "ANALYSIS"}
            </div>
            <div className="text-[10px] tracking-widest uppercase text-zinc-500">
              Conviction: <span className="text-zinc-200 font-mono">{verdict.thesis?.conviction}</span>
            </div>
            <div className="text-[10px] tracking-widest uppercase text-zinc-500">
              Pricing Status: <span className={`font-mono ${verdict.pricedInAssessment?.status === 'Not Yet Priced In' ? 'text-emerald-400' : 'text-amber-400'}`}>{verdict.pricedInAssessment?.status}</span>
            </div>
            {verdict.analysisAsOf && (
              <div className="text-[10px] tracking-widest uppercase text-zinc-500">
                As of: <span className="text-blue-300 font-mono">{verdict.analysisAsOf}</span>
              </div>
            )}
          </div>
          
          <DisclaimerNote className="bg-amber-950/30 border border-amber-900/40 px-2 py-1" />

          {/* Thesis Section */}
          <div className="p-4 bg-blue-950/20 border border-blue-900/50 rounded-lg">
            <h4 className="text-[10px] tracking-widest uppercase text-blue-400 mb-2">Master Synthesis Thesis</h4>
            <p className="text-sm text-zinc-200 leading-relaxed font-medium mb-3">{verdict.thesis?.coreArgument}</p>
            <div className="pt-3 border-t border-blue-900/30">
              <h5 className="text-[9px] tracking-widest uppercase text-zinc-500 mb-1">What would change this view:</h5>
              <p className="text-xs text-zinc-400">{verdict.thesis?.whatWouldChangeThisView}</p>
            </div>
          </div>

          {/* Priced In Assessment & Catalyst Chain */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-purple-400 mb-2">Priced-In Assessment</h4>
              <p className="text-xs text-zinc-300 leading-relaxed">{verdict.pricedInAssessment?.reasoning}</p>
            </div>
            <div className="p-3 bg-zinc-900/50 border border-zinc-800 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-emerald-400 mb-2">Catalyst Chain</h4>
              <p className="text-xs text-zinc-300 leading-relaxed">{verdict.catalystChain}</p>
            </div>
          </div>

          {/* Comprehensive 9-Factor Breakdown */}
          {verdict.nineFactorAssessment && (
            <div className="pt-2">
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-2">Comprehensive 9-Factor Breakdown</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {Object.entries(verdict.nineFactorAssessment).map(([key, data]) => {
                  const isMissing = data.text?.includes("No data available");
                  return (
                    <div key={key} className={`border border-zinc-800/50 p-3 rounded ${isMissing ? 'bg-zinc-900/20' : 'bg-zinc-900/40'}`}>
                      <div className="flex justify-between items-center mb-1.5">
                        <div className="text-[9px] font-bold tracking-widest uppercase text-zinc-300">
                          {factorTitles[key] || key}
                        </div>
                        {!isMissing && (
                          <span className={`text-[8px] tracking-widest uppercase px-1.5 py-0.5 rounded ${
                            data.bias === 'Bullish' ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-900' :
                            data.bias === 'Bearish' ? 'bg-red-950/50 text-red-400 border border-red-900' :
                            'bg-zinc-800 text-zinc-300 border border-zinc-700'
                          }`}>
                            {data.bias}
                          </span>
                        )}
                      </div>
                      <div className={`text-xs leading-snug ${isMissing ? 'text-zinc-600 italic' : 'text-zinc-400'}`}>
                        {data.text}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Four Desks Scorecard */}
          <div className="pt-2">
            <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-2">The Four Desks</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(verdict.deskSignals || {}).map(([desk, data]) => (
                <div key={desk} className="border border-zinc-800/50 p-3 bg-zinc-900/30 rounded">
                  <div className="flex justify-between items-center mb-2">
                    <div className="text-[10px] font-bold tracking-widest uppercase text-zinc-300">{desk}</div>
                    {data.dataSufficient ? (
                      <span className={`text-[9px] tracking-widest uppercase px-1.5 py-0.5 rounded ${
                        data.bias === 'Bullish' ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-900' :
                        data.bias === 'Bearish' ? 'bg-red-950/50 text-red-400 border border-red-900' :
                        'bg-zinc-800 text-zinc-300 border border-zinc-700'
                      }`}>
                        {data.bias}
                      </span>
                    ) : (
                      <span className="text-[9px] tracking-widest uppercase text-amber-500">Insufficient Data</span>
                    )}
                  </div>
                  <div className="text-xs text-zinc-400 leading-snug">
                    <span className="text-zinc-500 font-medium">Key Fact: </span>
                    {data.keyFact}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Unexplained Tensions */}
          {verdict.unexplainedTensions && verdict.unexplainedTensions.length > 0 && (
            <div className="mt-4 p-3 bg-red-950/20 border border-red-900/40 rounded">
              <h4 className="text-[10px] tracking-widest uppercase text-red-400 mb-2 flex items-center gap-1.5">
                <AlertCircle size={12} />
                Unexplained Tensions
              </h4>
              <ul className="space-y-2">
                {verdict.unexplainedTensions.map((tension, i) => (
                  <li key={i} className="text-xs text-zinc-300">
                    <span className="text-red-400 font-medium mr-2">[{tension.desks?.join(" vs ")}]</span>
                    {tension.description}
                  </li>
                ))}
              </ul>
            </div>
          )}

        </div>
      )}
    </Panel>
  );
}
