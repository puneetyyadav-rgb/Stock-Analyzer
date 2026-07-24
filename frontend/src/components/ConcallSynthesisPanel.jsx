import React, { useEffect, useState, useCallback } from "react";
import {
  RefreshCw, Loader2, ChevronDown, ChevronUp, Download,
  CheckCircle2, XCircle, Clock, AlertTriangle, MinusCircle,
  MessageSquareWarning, TrendingUp, Target
} from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ── Status badge config ───────────────────────────────────────────────────────
const STATUS_CONFIG = {
  "Delivered In Full":             { color: "bg-emerald-900/60 text-emerald-300 border-emerald-700", Icon: CheckCircle2 },
  "Delivered Late":                { color: "bg-teal-900/60 text-teal-300 border-teal-700",         Icon: Clock },
  "Partially Delivered":           { color: "bg-yellow-900/50 text-yellow-300 border-yellow-700",   Icon: AlertTriangle },
  "Missed - Acknowledged By Management": { color: "bg-orange-900/50 text-orange-300 border-orange-700", Icon: XCircle },
  "Missed - Silently Dropped":     { color: "bg-red-900/60 text-red-300 border-red-700",            Icon: XCircle },
  "Still Pending (Not Yet Due)":   { color: "bg-zinc-800 text-zinc-400 border-zinc-700",            Icon: Clock },
  "Insufficient Evidence To Determine": { color: "bg-zinc-800 text-zinc-500 border-zinc-700",       Icon: MinusCircle },
};

const RESPONSE_CONFIG = {
  "Direct and Substantive Answer": { color: "text-emerald-400", label: "Answered Directly" },
  "Partial Answer With Deflection": { color: "text-yellow-400", label: "Partial Answer" },
  "Full Dodge":                    { color: "text-red-400",     label: "Full Dodge" },
  "Deferred Offline":              { color: "text-orange-400",  label: "Deferred Offline" },
  "Defensive or Evasive Tone":     { color: "text-red-400",     label: "Evasive" },
};

const VISION_CONFIG = {
  "Consistent Vision, Reinforced By Actions":         { color: "text-emerald-400", bar: "bg-emerald-500" },
  "Consistent Vision, Not Yet Backed By Actions":     { color: "text-yellow-400",  bar: "bg-yellow-500" },
  "Vision Has Shifted Opportunistically":             { color: "text-orange-400",  bar: "bg-orange-500" },
  "Vision Is Vague Or Underdeveloped Across All 8 Quarters": { color: "text-red-400", bar: "bg-red-500" },
};

// ── Collapsible item ──────────────────────────────────────────────────────────
function Collapsible({ header, children }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-zinc-800 bg-zinc-900/30">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-zinc-800/40 transition-colors"
      >
        {header}
        {open ? <ChevronUp size={13} className="text-zinc-500 shrink-0" /> : <ChevronDown size={13} className="text-zinc-500 shrink-0" />}
      </button>
      {open && <div className="px-3 pb-3 pt-1 border-t border-zinc-800/60">{children}</div>}
    </div>
  );
}

// ── Card wrapper ──────────────────────────────────────────────────────────────
function SectionCard({ icon: Icon, title, badge, children }) {
  return (
    <div className="border border-zinc-800 bg-[#0c0c0e]">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-800 bg-zinc-900/40">
        <Icon size={13} className="text-zinc-400" />
        <h4 className="text-[10px] tracking-widest uppercase text-zinc-300 font-semibold">{title}</h4>
        {badge && (
          <span className="ml-auto px-1.5 py-0.5 text-[9px] tracking-widest uppercase border border-zinc-700 text-zinc-400">{badge}</span>
        )}
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

// ── Label pill ────────────────────────────────────────────────────────────────
function StatusPill({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG["Insufficient Evidence To Determine"];
  const { Icon } = cfg;
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] tracking-widest uppercase border ${cfg.color}`}>
      <Icon size={9} /> {status}
    </span>
  );
}

// ── CARD 1: Execution Tracker ─────────────────────────────────────────────────
function ExecutionTrackerCard({ data }) {
  const promises = data?.promises_evaluated || [];
  const verdict  = data?.overall_execution_pattern;

  const counts = promises.reduce((acc, p) => {
    const s = p.status || "";
    if (s === "Delivered In Full" || s === "Delivered Late") acc.good++;
    else if (s.startsWith("Missed")) acc.missed++;
    else acc.other++;
    return acc;
  }, { good: 0, missed: 0, other: 0 });

  return (
    <SectionCard icon={Target} title="Promise vs. Reality" badge={`${promises.length} Commitments Tracked`}>
      {/* Summary bar */}
      <div className="flex gap-3 mb-3 pb-3 border-b border-zinc-800/60">
        <div className="text-center">
          <div className="text-lg font-mono font-bold text-emerald-400">{counts.good}</div>
          <div className="text-[9px] tracking-widest uppercase text-zinc-500">Delivered</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-mono font-bold text-red-400">{counts.missed}</div>
          <div className="text-[9px] tracking-widest uppercase text-zinc-500">Missed</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-mono font-bold text-zinc-400">{counts.other}</div>
          <div className="text-[9px] tracking-widest uppercase text-zinc-500">Pending/Unclear</div>
        </div>
      </div>

      {/* Overall verdict */}
      {verdict && (
        <p className="text-[11px] leading-relaxed text-zinc-300 mb-3 italic border-l-2 border-zinc-600 pl-2">{verdict}</p>
      )}

      {/* Promise list */}
      <div className="space-y-1.5" data-testid="execution-tracker-list">
        {promises.map((p, i) => (
          <Collapsible
            key={i}
            header={
              <div className="flex items-center gap-2 flex-wrap min-w-0">
                <span className="text-[10px] font-mono text-zinc-200 truncate">{p.original_commitment_summary?.slice(0, 60)}…</span>
                <StatusPill status={p.status} />
              </div>
            }
          >
            <div className="space-y-1.5 pt-1">
              <div className="flex gap-2 flex-wrap">
                <span className="text-[9px] uppercase tracking-widest text-zinc-500">First Promised:</span>
                <span className="text-[10px] font-mono text-zinc-300">{p.quarter_first_promised}</span>
                <span className="text-[9px] uppercase tracking-widest text-zinc-500 ml-2">Category:</span>
                <span className="text-[10px] font-mono text-zinc-300">{p.category}</span>
              </div>
              <p className="text-[11px] text-zinc-300 leading-relaxed">{p.original_commitment_summary}</p>
              <div>
                <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-0.5">Evidence Trail</div>
                <p className="text-[11px] text-zinc-400 leading-relaxed">{p.evidence_trail}</p>
              </div>
              <div>
                <span className="text-[9px] uppercase tracking-widest text-zinc-500">Accountability: </span>
                <span className={`text-[10px] font-medium ${
                  p.management_accountability === "Proactively Acknowledged" ? "text-emerald-400" :
                  p.management_accountability === "Never Mentioned Again" ? "text-red-400" : "text-yellow-400"
                }`}>{p.management_accountability}</span>
              </div>
            </div>
          </Collapsible>
        ))}
      </div>
    </SectionCard>
  );
}

// ── CARD 2: Analyst Grill Vault ───────────────────────────────────────────────
function AnalystGrillCard({ data }) {
  const exchanges = data?.sharpest_exchanges || [];
  return (
    <SectionCard icon={MessageSquareWarning} title="Analyst Grill Vault" badge={`${exchanges.length} Key Exchanges`}>
      <div className="space-y-1.5" data-testid="analyst-grill-list">
        {exchanges.map((ex, i) => {
          const respCfg = RESPONSE_CONFIG[ex.management_response_type] || { color: "text-zinc-400", label: ex.management_response_type };
          return (
            <Collapsible
              key={i}
              header={
                <div className="flex items-center gap-2 flex-wrap min-w-0">
                  <span className="text-[10px] font-mono text-zinc-500 shrink-0">{ex.quarter}</span>
                  <span className="text-[10px] text-zinc-200 truncate">{ex.question_summary?.slice(0, 55)}…</span>
                  <span className={`text-[9px] uppercase tracking-widest font-medium shrink-0 ${respCfg.color}`}>{respCfg.label}</span>
                </div>
              }
            >
              <div className="space-y-2 pt-1">
                <div>
                  <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-0.5">Analyst / Firm</div>
                  <span className="text-[10px] font-mono text-blue-400">{ex.analyst_or_firm}</span>
                </div>
                <div>
                  <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-0.5">Question</div>
                  <p className="text-[11px] text-zinc-200 leading-relaxed">{ex.question_summary}</p>
                </div>
                <div>
                  <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-0.5">Why This Was Uncomfortable</div>
                  <p className="text-[11px] text-amber-300/80 leading-relaxed italic">{ex.why_this_was_uncomfortable}</p>
                </div>
                <div>
                  <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-0.5">
                    Management Response —&nbsp;
                    <span className={`font-medium not-italic ${respCfg.color}`}>{respCfg.label}</span>
                  </div>
                  <p className="text-[11px] text-zinc-300 leading-relaxed">{ex.response_summary}</p>
                </div>
              </div>
            </Collapsible>
          );
        })}
        {exchanges.length === 0 && (
          <p className="text-xs text-zinc-600 italic">No sharp analyst exchanges identified across the 8 quarters.</p>
        )}
      </div>
    </SectionCard>
  );
}

// ── CARD 3: 3-Year Strategic Vision ──────────────────────────────────────────
function StrategicVisionCard({ data }) {
  const assessment = data?.vision_consistency_assessment;
  const vCfg = VISION_CONFIG[assessment] || { color: "text-zinc-400", bar: "bg-zinc-500" };
  const timeline = data?.key_evidence_timeline || [];

  return (
    <SectionCard icon={TrendingUp} title="3-Year Strategic Vision" badge="8-Quarter Arc">
      {/* Assessment badge */}
      {assessment && (
        <div className="flex items-center gap-2 mb-3 pb-3 border-b border-zinc-800/60">
          <div className={`w-1.5 h-full min-h-[28px] ${vCfg.bar} shrink-0`} />
          <span className={`text-[11px] font-medium ${vCfg.color}`}>{assessment}</span>
        </div>
      )}

      {/* Narrative evolution */}
      {data?.narrative_evolution_summary && (
        <div className="mb-3">
          <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-1">How Strategy Evolved</div>
          <p className="text-[11px] text-zinc-300 leading-relaxed">{data.narrative_evolution_summary}</p>
        </div>
      )}

      {/* Where they are headed */}
      {data?.inferred_long_term_destination && (
        <div className="mb-3 p-2.5 bg-indigo-950/20 border border-indigo-800/40">
          <div className="text-[9px] uppercase tracking-widest text-indigo-400 mb-1">Where This Company Is Headed</div>
          <p className="text-[11px] text-zinc-200 leading-relaxed">{data.inferred_long_term_destination}</p>
        </div>
      )}

      {/* Evidence timeline */}
      {timeline.length > 0 && (
        <div>
          <div className="text-[9px] uppercase tracking-widest text-zinc-500 mb-2">Quarter-by-Quarter Signals</div>
          <div className="space-y-1.5" data-testid="vision-timeline">
            {timeline.map((t, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-[10px] font-mono text-zinc-500 shrink-0 w-28">{t.quarter}</span>
                <p className="text-[11px] text-zinc-300 leading-relaxed">{t.signal}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  );
}

// ── MAIN EXPORT ───────────────────────────────────────────────────────────────
export default function ConcallSynthesisPanel({ symbol }) {
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [generated, setGenerated] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadMsg, setDownloadMsg] = useState(null);

  const downloadTranscripts = useCallback(async () => {
    if (!symbol) return;
    setDownloading(true);
    setDownloadMsg(null);
    try {
      const r = await axios.post(`${API}/concall-synthesis/${symbol}/download-transcripts`);
      setDownloadMsg(r.data.message || "Download complete.");
    } catch (e) {
      setDownloadMsg(e.response?.data?.detail || e.message || "Failed to download.");
    } finally {
      setDownloading(false);
      setTimeout(() => setDownloadMsg(null), 5000);
    }
  }, [symbol]);

  const fetch = useCallback(async (force = false, autoLoad = false) => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API}/concall-synthesis/${symbol}`, {
        params: { force_refresh: force, auto_load: autoLoad },
        timeout: 300000, // Increased to 5 minutes for heavy PDF scraping & LLM work
      });
      
      if (r.data?.not_generated_yet) {
        // Just means it wasn't in cache, don't show an error, stay on the idle screen
        setData(null);
        setGenerated(false);
      } else if (r.data?.error) {
        setError(r.data.error);
        setData(null);
      } else {
        setData(r.data);
        setGenerated(true);
      }
    } catch (e) {
      // If it's an auto load, we don't care if it fails or times out
      if (!autoLoad) {
        setError(e.response?.data?.detail || e.message || "Failed to fetch synthesis");
      }
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  // Try to load from cache on mount (autoLoad = true)
  useEffect(() => {
    if (symbol) fetch(false, true);
  }, [symbol, fetch]);

  const meta = data?.analysis_metadata;

  return (
    <div className="border border-zinc-800 bg-[#0c0c0e]" data-testid="concall-synthesis-panel">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800 bg-zinc-900/40">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-4 bg-indigo-500" />
          <h3 className="text-[10px] tracking-widest uppercase text-zinc-100 font-semibold">
            2-Year Management Synthesis
          </h3>
          {meta && (
            <span className="text-[9px] text-zinc-500 font-mono">{meta.quarters_analyzed?.length} qtrs · {meta.data_completeness_note?.slice(0, 30)}</span>
          )}
        </div>
        <div className="flex gap-2">
          {downloadMsg && <span className="text-[9px] text-emerald-400 self-center mr-2">{downloadMsg}</span>}
          <button
            onClick={downloadTranscripts}
            disabled={downloading || loading}
            className="flex items-center gap-1.5 px-2 py-1 text-[9px] tracking-widest uppercase border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors disabled:opacity-40"
          >
            {downloading ? <Loader2 size={10} className="animate-spin" /> : <Download size={10} />}
            Sync Transcripts
          </button>
          <button
            onClick={() => fetch(true, false)}
            disabled={loading || downloading}
            data-testid="synthesis-refresh-btn"
            className="flex items-center gap-1.5 px-2 py-1 text-[9px] tracking-widest uppercase border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors disabled:opacity-40"
          >
            {loading
              ? <Loader2 size={10} className="animate-spin" />
              : <RefreshCw size={10} />
            }
            {generated ? "Refresh" : "Generate"} (8 Qtrs)
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="p-3">
        {/* Idle state */}
        {!loading && !data && !error && !generated && (
          <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
            <TrendingUp size={24} className="text-zinc-600" />
            <p className="text-xs text-zinc-500 max-w-xs">
              Generate a forensic 8-quarter analysis of management promises, analyst interrogations, and the 3-year strategic direction.
            </p>
            <div className="flex gap-3 mt-2">
              <button
                onClick={downloadTranscripts}
                disabled={downloading || loading}
                className="px-3 py-1.5 text-[10px] tracking-widest uppercase border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors disabled:opacity-40"
              >
                {downloading ? "Downloading..." : "Download Transcripts"}
              </button>
              <button
                onClick={() => fetch(false, false)}
                disabled={downloading || loading}
                data-testid="synthesis-generate-btn"
                className="px-3 py-1.5 text-[10px] tracking-widest uppercase border border-indigo-700 bg-indigo-900/30 text-indigo-300 hover:bg-indigo-800/40 transition-colors disabled:opacity-40"
              >
                Generate 2-Year Synthesis
              </button>
            </div>
            {downloadMsg && <p className="text-[10px] text-emerald-400 mt-1">{downloadMsg}</p>}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-10 gap-2">
            <Loader2 size={20} className="animate-spin text-indigo-400" />
            <p className="text-xs text-zinc-500">Reading all 8 quarters of earnings calls… (~30–60s)</p>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <p className="text-xs text-red-400 p-2 border border-red-900/50 bg-red-950/20">{error}</p>
        )}

        {/* Main cards */}
        {data && !loading && (
          <div className="space-y-3">
            <ExecutionTrackerCard data={data.execution_tracker} />
            <AnalystGrillCard    data={data.analyst_grill_vault} />
            <StrategicVisionCard data={data.three_year_strategic_vision} />
          </div>
        )}
      </div>
    </div>
  );
}
