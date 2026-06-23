import React, { useState, useEffect } from "react";
import { Panel } from "./Panel";
import { uploadSourceMaterial } from "../lib/api";
import { UploadCloud, Loader2, CheckCircle2 } from "lucide-react";

export default function RatioAnalysisPanel({ symbol, onAnalyzed }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!symbol) return;
    const cached = localStorage.getItem(`ratioAnalysis_${symbol}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        setData(parsed);
        if (onAnalyzed) onAnalyzed(parsed);
      } catch (e) {
        // invalid cache
      }
    } else {
      setData(null);
      setFile(null);
      if (onAnalyzed) onAnalyzed(null);
    }
  }, [symbol]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const res = await uploadSourceMaterial(symbol, file);
      setData(res);
      localStorage.setItem(`ratioAnalysis_${symbol}`, JSON.stringify(res));
      if (onAnalyzed) onAnalyzed(res);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to upload and parse source material");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel title="Custom Ratio Analysis (Source Material)" testId="ratio-analysis-panel">
      {!data && (
        <div className="border border-dashed border-zinc-700/50 rounded-lg p-6 flex flex-col items-center justify-center bg-zinc-900/20">
          <UploadCloud className="text-zinc-500 mb-3" size={32} />
          <h3 className="text-sm font-medium text-zinc-300 mb-1">Upload PDF Source Report</h3>
          <p className="text-xs text-zinc-500 text-center max-w-xs mb-4">
            Upload an analyst report or financial document (PDF) to extract custom ratios and peer comparisons.
          </p>
          <div className="flex items-center gap-3 w-full max-w-sm">
            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="block w-full text-xs text-zinc-400
                file:mr-3 file:py-1.5 file:px-3
                file:rounded-sm file:border-0
                file:text-[10px] file:font-semibold file:uppercase file:tracking-widest
                file:bg-blue-900/30 file:text-blue-400
                hover:file:bg-blue-900/50 cursor-pointer"
            />
            <button
              onClick={handleUpload}
              disabled={!file || loading}
              className={`px-3 py-1.5 text-xs font-medium rounded-sm flex items-center gap-1.5 transition-colors ${
                !file || loading 
                  ? "bg-zinc-800 text-zinc-600 cursor-not-allowed" 
                  : "bg-blue-600 hover:bg-blue-500 text-white"
              }`}
            >
              {loading && <Loader2 size={12} className="animate-spin" />}
              {loading ? "Analyzing..." : "Analyze"}
            </button>
          </div>
          {error && <p className="text-xs text-red-400 mt-3">{error}</p>}
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} className="text-emerald-400" />
              <span className="text-sm font-medium text-zinc-200">Analysis Complete</span>
            </div>
            <button 
              onClick={() => { 
                setData(null); 
                setFile(null); 
                localStorage.removeItem(`ratioAnalysis_${symbol}`);
                if (onAnalyzed) onAnalyzed(null);
              }}
              className="text-[10px] tracking-widest uppercase text-zinc-500 hover:text-zinc-300"
            >
              Upload Another
            </button>
          </div>

          {data.company_ratios && data.company_ratios.length > 0 && (
            <div>
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-3">{symbol} Extracted Ratios</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {data.company_ratios.map((r, i) => (
                  <div key={i} className="border border-zinc-800/60 p-2.5 bg-zinc-900/30">
                    <div className="text-[10px] text-zinc-500 mb-1">{r.name}</div>
                    <div className="font-mono text-zinc-200">
                      {r.value} <span className="text-zinc-500 text-xs">{r.unit || ""}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.competitor_comparison && data.competitor_comparison.companies && data.competitor_comparison.companies.length > 0 && (
            <div>
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-3">Peer Comparison Ratios</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-zinc-900/50 border-b border-zinc-800">
                    <tr>
                      <th className="py-2 px-3 text-zinc-400 font-medium">Company</th>
                      {(data.competitor_comparison.metrics || []).map((m, i) => (
                        <th key={i} className="py-2 px-3 text-zinc-400 font-medium whitespace-nowrap">{m}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.competitor_comparison.companies.map((c, i) => (
                      <tr key={i} className="border-b border-zinc-800/40 hover:bg-zinc-800/20">
                        <td className="py-2 px-3 font-medium text-zinc-300">{c.name}</td>
                        {(data.competitor_comparison.metrics || []).map((m, j) => {
                           const val = c.ratios[m] || c.ratios[Object.keys(c.ratios).find(k => k.toLowerCase().includes(m.toLowerCase()))] || "—";
                           return <td key={j} className="py-2 px-3 font-mono text-zinc-400">{val}</td>;
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {data.other_fields && Object.keys(data.other_fields).length > 0 && (
            <div>
              <h4 className="text-[10px] tracking-widest uppercase text-zinc-400 mb-3">Other Extracted Insights</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(data.other_fields).map(([k, v], i) => {
                  let parsedValue = v;
                  if (typeof v === "string" && v.trim().startsWith("{")) {
                    try {
                      parsedValue = JSON.parse(v);
                    } catch (e) {
                      parsedValue = v;
                    }
                  }
                  
                  return (
                    <div key={i} className="border border-zinc-800/40 p-3 bg-zinc-900/20">
                      <div className="text-[10px] text-zinc-500 mb-2 uppercase tracking-wider border-b border-zinc-800/50 pb-1">{k.replace(/_/g, " ")}</div>
                      <div className="text-sm text-zinc-300 font-medium">
                        {typeof parsedValue === "object" && parsedValue !== null ? (
                          <div className="flex flex-col gap-1.5 mt-1">
                            {Object.entries(parsedValue).map(([subK, subV], subI) => (
                              <div key={subI} className="flex justify-between items-center text-xs">
                                <span className="text-zinc-500 capitalize">{subK.replace(/_/g, " ")}</span>
                                <span className="font-mono text-zinc-300">{typeof subV === "object" ? JSON.stringify(subV) : String(subV)}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          String(parsedValue)
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
