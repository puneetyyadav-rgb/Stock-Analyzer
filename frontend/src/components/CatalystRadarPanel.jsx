/**
 * CatalystRadarPanel.jsx — Phase 4: Catalyst Radar Dashboard Panel
 * Displays upcoming deterministically extracted events from official NSE/BSE filings.
 * Grouped by time horizon: This Week / Next 2 Weeks / 15-30 Days.
 * Strictly NO probability scores, NO outcome predictions, NO buy/sell badges.
 */
import React, { useState, useEffect, useCallback } from "react";
import { getCatalystsUpcoming, runBatchArchive, getScanProgress, getResultsDue } from "../lib/api";

const CATEGORY_STYLES = {
  "Legal/Regulatory":   { bg: "rgba(239,68,68,0.15)",  border: "#ef4444", icon: "⚖️",  color: "#fca5a5" },
  "Corporate Action":   { bg: "rgba(168,85,247,0.15)", border: "#a855f7", icon: "🏢",  color: "#c4b5fd" },
  "Board/Governance":   { bg: "rgba(59,130,246,0.15)", border: "#3b82f6", icon: "👔",  color: "#93c5fd" },
  "Debt/Refinancing":   { bg: "rgba(245,158,11,0.15)", border: "#f59e0b", icon: "💳",  color: "#fcd34d" },
  "Regulatory Approval":{ bg: "rgba(16,185,129,0.15)", border: "#10b981", icon: "✅",  color: "#6ee7b7" },
  "Dividend":           { bg: "rgba(34,197,94,0.15)",  border: "#22c55e", icon: "💰",  color: "#86efac" },
  "AGM/EGM":            { bg: "rgba(6,182,212,0.15)",  border: "#06b6d4", icon: "🏛️", color: "#67e8f9" },
  "Other":              { bg: "rgba(148,163,184,0.15)", border: "#94a3b8", icon: "📋",  color: "#cbd5e1" },
};

const CONFIDENCE_STYLES = {
  "High":   { bg: "rgba(34,197,94,0.2)", color: "#22c55e", label: "High · Official Filing" },
  "Medium": { bg: "rgba(245,158,11,0.2)", color: "#f59e0b", label: "Medium · Concall Transcript" },
};

const panelStyle = {
  background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)",
  borderRadius: 16,
  border: "1px solid rgba(99,102,241,0.25)",
  padding: "28px 24px",
  color: "#e2e8f0",
  fontFamily: "'Inter', 'Segoe UI', sans-serif",
  minHeight: 400,
};

const sectionHeaderStyle = (color) => ({
  display: "flex",
  alignItems: "center",
  gap: 10,
  marginBottom: 14,
  paddingBottom: 8,
  borderBottom: `1px solid ${color}33`,
});

const cardStyle = (catStyle) => ({
  background: catStyle.bg,
  border: `1px solid ${catStyle.border}44`,
  borderRadius: 12,
  padding: "16px 18px",
  marginBottom: 10,
  transition: "all 0.2s ease",
  cursor: "default",
});

const badgeStyle = (bg, color) => ({
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  padding: "3px 10px",
  borderRadius: 20,
  fontSize: 11,
  fontWeight: 600,
  background: bg,
  color: color,
  letterSpacing: 0.3,
});

const daysCounterStyle = (days) => ({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minWidth: 44,
  padding: "4px 10px",
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 700,
  background: days <= 3 ? "rgba(239,68,68,0.25)" : days <= 7 ? "rgba(245,158,11,0.2)" : "rgba(59,130,246,0.15)",
  color: days <= 3 ? "#fca5a5" : days <= 7 ? "#fcd34d" : "#93c5fd",
  border: `1px solid ${days <= 3 ? "#ef444466" : days <= 7 ? "#f59e0b44" : "#3b82f644"}`,
});

function CatalystCard({ event }) {
  const cat = event.category || "Other";
  const style = CATEGORY_STYLES[cat] || CATEGORY_STYLES["Other"];
  const conf = CONFIDENCE_STYLES[event.date_confidence] || CONFIDENCE_STYLES["High"];
  const days = event.days_remaining ?? 999;

  return (
    <div style={cardStyle(style)} onMouseEnter={(e) => {
      e.currentTarget.style.transform = "translateY(-1px)";
      e.currentTarget.style.boxShadow = `0 4px 20px ${style.border}22`;
    }} onMouseLeave={(e) => {
      e.currentTarget.style.transform = "none";
      e.currentTarget.style.boxShadow = "none";
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: "#f8fafc" }}>{event.symbol?.replace(".NS","")}</span>
          <span style={badgeStyle(style.bg, style.color)}>{style.icon} {cat}</span>
          <span style={badgeStyle(conf.bg, conf.color)}>🔒 {conf.label}</span>
        </div>
        <div style={daysCounterStyle(days)}>
          {days === 0 ? "Today" : days === 1 ? "Tomorrow" : `${days}d`}
        </div>
      </div>
      <p style={{ margin: "6px 0 8px", fontSize: 13.5, lineHeight: 1.55, color: "#cbd5e1" }}>
        {event.summary || event.raw_snippet?.substring(0, 150)}
      </p>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>
          📅 {event.extracted_date} · Source: {event.source_type === "NSE_ANNOUNCEMENT" ? "NSE Filing" : "Concall Transcript"}
        </span>
      </div>
    </div>
  );
}

function TimeSection({ title, icon, color, events }) {
  if (!events || events.length === 0) return null;
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={sectionHeaderStyle(color)}>
        <span style={{ fontSize: 20 }}>{icon}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color }}>{title}</span>
        <span style={{
          marginLeft: "auto",
          fontSize: 12,
          background: `${color}22`,
          color,
          padding: "2px 10px",
          borderRadius: 12,
          fontWeight: 600,
        }}>{events.length} event{events.length !== 1 ? "s" : ""}</span>
      </div>
      {events.map((ev, i) => <CatalystCard key={`${ev.symbol}-${ev.extracted_date}-${i}`} event={ev} />)}
    </div>
  );
}

function ResultsDueView({ days }) {
  const [data, setData] = useState(() => {
    try {
      const cached = localStorage.getItem(`results_due_cache_${days}`);
      return cached ? JSON.parse(cached) : null;
    } catch { return null; }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const fetchResults = useCallback(async () => {
    if (!data) setLoading(true);
    setError(null);
    try {
      const res = await getResultsDue(days);
      setData(res);
      try { localStorage.setItem(`results_due_cache_${days}`, JSON.stringify(res)); } catch {}
    } catch (err) {
      setError(err.message || "Failed to load forthcoming board meetings & corporate actions");
    } finally {
      setLoading(false);
    }
  }, [days, data]);

  useEffect(() => { fetchResults(); }, [fetchResults]);

  if (loading && !data) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>
        <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
        Syncing forthcoming structured board meetings from NSE...
      </div>
    );
  }

  if (error && !data) {
    return <div style={{ padding: 20, color: "#fca5a5", background: "rgba(239,68,68,0.1)", borderRadius: 10 }}>⚠️ {error}</div>;
  }

  const list = data?.results_due || [];
  const filtered = list.filter(c => {
    if (filter === "RESULTS" && !c.event_type.includes("Financial Results")) return false;
    if (filter === "DIVIDEND" && !c.event_type.includes("Dividend")) return false;
    if (filter === "ACTIONS" && !c.event_type.includes("Corporate Action")) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      const symMatch = (c.symbol || "").toLowerCase().includes(q);
      const compMatch = (c.company || "").toLowerCase().includes(q);
      const purpMatch = (c.purpose || "").toLowerCase().includes(q);
      if (!symMatch && !compMatch && !purpMatch) return false;
    }
    return true;
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {[
            { id: "ALL", label: `🏢 All Events (${list.length})` },
            { id: "RESULTS", label: `📊 Financial Results (${list.filter(c => c.event_type.includes("Financial Results")).length})` },
            { id: "DIVIDEND", label: `💰 Dividends (${list.filter(c => c.event_type.includes("Dividend")).length})` },
            { id: "ACTIONS", label: `🎁 Bonus/Rights/Splits (${list.filter(c => c.event_type.includes("Corporate Action")).length})` },
          ].map(btn => (
            <button
              key={btn.id}
              onClick={() => setFilter(btn.id)}
              style={{
                padding: "6px 12px",
                borderRadius: 8,
                border: filter === btn.id ? "1px solid #38bdf8" : "1px solid #334155",
                background: filter === btn.id ? "rgba(56,189,248,0.15)" : "rgba(15,23,42,0.6)",
                color: filter === btn.id ? "#7dd3fc" : "#94a3b8",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>

        {/* Search Bar & Manual Sync Button */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", flex: "1 1 320px", justifyContent: "flex-end" }}>
          <div style={{ position: "relative", minWidth: 220, flex: "1 1 auto", maxWidth: 350 }}>
            <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", fontSize: 13, color: "#64748b" }}>🔍</span>
            <input
              type="text"
              placeholder="Filter by Symbol or Company (e.g. TCS)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: "100%",
                padding: "6px 28px 6px 30px",
                borderRadius: 8,
                border: searchQuery ? "1px solid #38bdf8" : "1px solid #334155",
                background: "rgba(15, 23, 42, 0.85)",
                color: "#f8fafc",
                fontSize: 12.5,
                outline: "none",
                transition: "all 0.15s ease",
                boxSizing: "border-box"
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 13 }}
              >✕</button>
            )}
          </div>

          <button
            onClick={fetchResults}
            disabled={loading}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid #6366f1",
              background: loading ? "rgba(99,102,241,0.1)" : "rgba(99,102,241,0.2)",
              color: "#a5b4fc",
              fontSize: 12,
              fontWeight: 700,
              cursor: loading ? "wait" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              transition: "all 0.15s ease",
              whiteSpace: "nowrap"
            }}
          >
            {loading ? "⏳ Syncing..." : "⚡ Sync Exchange Feed"}
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: "#64748b", background: "rgba(15,23,42,0.4)", borderRadius: 12, border: "1px solid #1e293b" }}>
          No upcoming board meetings found for {searchQuery ? `"${searchQuery}"` : filter === "ALL" ? "any category" : filter} inside the next {days} days horizon.
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
          {filtered.map((card, idx) => {
            const badgeBg = card.badge_color === "red" ? "rgba(239,68,68,0.15)" :
                            card.badge_color === "green" ? "rgba(34,197,94,0.15)" :
                            card.badge_color === "purple" ? "rgba(168,85,247,0.15)" : "rgba(59,130,246,0.15)";
            const badgeBorder = card.badge_color === "red" ? "#ef4444" :
                                card.badge_color === "green" ? "#22c55e" :
                                card.badge_color === "purple" ? "#a855f7" : "#3b82f6";
            const badgeColor = card.badge_color === "red" ? "#fca5a5" :
                               card.badge_color === "green" ? "#86efac" :
                               card.badge_color === "purple" ? "#d8b4fe" : "#93c5fd";

            return (
              <div
                key={`${card.symbol}-${card.meeting_date}-${idx}`}
                style={{
                  background: "rgba(15, 23, 42, 0.75)",
                  border: "1px solid rgba(51, 65, 85, 0.6)",
                  borderRadius: 12,
                  padding: 16,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
                  transition: "border-color 0.2s ease",
                }}
              >
                <div>
                  {/* Top bar */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                    <div>
                      <span style={{ fontSize: 16, fontWeight: 800, color: "#f8fafc", letterSpacing: 0.5 }}>{card.symbol}</span>
                      <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2, maxWidth: 210, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {card.company}
                      </div>
                    </div>
                    <span style={{
                      padding: "3px 8px",
                      borderRadius: 6,
                      background: badgeBg,
                      border: `1px solid ${badgeBorder}55`,
                      color: badgeColor,
                      fontSize: 10.5,
                      fontWeight: 700,
                      textTransform: "uppercase"
                    }}>
                      {card.event_type}
                    </span>
                  </div>

                  {/* Date & Countdown */}
                  <div style={{ display: "flex", alignItems: "center", gap: 10, background: "rgba(30,41,59,0.5)", padding: "8px 12px", borderRadius: 8, marginBottom: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0" }}>
                      🗓️ {card.meeting_date}
                    </div>
                    <span style={{ fontSize: 11, color: card.countdown_days <= 3 ? "#f87171" : "#38bdf8", fontWeight: 600 }}>
                      ⏱️ {card.countdown_days === 0 ? "Today!" : `${card.countdown_days} day${card.countdown_days === 1 ? "" : "s"} away`}
                    </span>
                  </div>

                  {/* Purpose */}
                  <p style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.4, margin: "0 0 12px" }}>
                    {card.purpose}
                  </p>

                  {/* Consensus Estimates */}
                  {card.consensus && (card.consensus.eps_avg || card.consensus.rev_avg_cr) ? (
                    <div style={{
                      background: "rgba(16, 185, 129, 0.08)",
                      border: "1px solid rgba(16, 185, 129, 0.25)",
                      borderRadius: 8,
                      padding: "8px 10px",
                      marginBottom: 10,
                      fontSize: 11.5,
                      color: "#6ee7b7",
                    }}>
                      <div style={{ fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 4 }}>
                        📈 yfinance Consensus Estimates
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 6, color: "#a7f3d0" }}>
                        {card.consensus.eps_avg && (
                          <span>EPS Avg: <strong>₹{card.consensus.eps_avg}</strong></span>
                        )}
                        {card.consensus.eps_high && (
                          <span style={{ fontSize: 10.5, color: "#6ee7b7" }}>(High ₹{card.consensus.eps_high} / Low ₹{card.consensus.eps_low})</span>
                        )}
                        {card.consensus.rev_avg_cr && (
                          <span>Est. Revenue: <strong>₹{card.consensus.rev_avg_cr.toLocaleString()} Cr</strong></span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: 10.5, color: "#475569", marginBottom: 10 }}>
                      📊 Consensus EPS estimate: N/A
                    </div>
                  )}

                  {/* Factor Snapshot */}
                  {card.factor_snapshot ? (
                    <div style={{
                      background: "rgba(99, 102, 241, 0.08)",
                      border: "1px solid rgba(99, 102, 241, 0.25)",
                      borderRadius: 8,
                      padding: "8px 10px",
                      fontSize: 11,
                      color: "#a5b4fc",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                        <span style={{ fontWeight: 700, color: "#c4b5fd" }}>🏛️ Factor Profile (Latest)</span>
                        {card.factor_snapshot.decile && (
                          <span style={{ background: "rgba(168,85,247,0.2)", padding: "2px 6px", borderRadius: 4, fontSize: 10, fontWeight: 700, color: "#e9d5ff" }}>
                            Decile D{card.factor_snapshot.decile} · Top {card.factor_snapshot.percentile}%
                          </span>
                        )}
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6, fontSize: 10.5 }}>
                        <div>
                          <div style={{ color: "#64748b" }}>Delivery %</div>
                          <div style={{ fontWeight: 700, color: "#e2e8f0" }}>
                            {card.factor_snapshot.deliv_pct !== null ? `${card.factor_snapshot.deliv_pct}%` : "—"}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: "#64748b" }}>Vol Trend</div>
                          <div style={{ fontWeight: 700, color: "#e2e8f0" }}>
                            {card.factor_snapshot.vol_trend !== null ? `${card.factor_snapshot.vol_trend}×` : "—"}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: "#64748b" }}>20d Mom</div>
                          <div style={{ fontWeight: 700, color: card.factor_snapshot.mom_20d >= 0 ? "#4ade80" : "#f87171" }}>
                            {card.factor_snapshot.mom_20d !== null ? `${card.factor_snapshot.mom_20d > 0 ? "+" : ""}${card.factor_snapshot.mom_20d}%` : "—"}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: 10.5, color: "#475569" }}>
                      🏛️ Factor profile unavailable
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function CatalystRadarPanel() {
  const [radarTab, setRadarTab] = useState("results-due");
  const [days, setDays] = useState(30);
  const [data, setData] = useState(() => {
    try {
      const cached = localStorage.getItem(`catalyst_radar_cache_30`);
      return cached ? JSON.parse(cached) : null;
    } catch { return null; }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState("");
  const [scanProgress, setScanProgress] = useState(null);
  const [nlpQuery, setNlpQuery] = useState("");

  const fetchData = useCallback(async () => {
    // Stale-while-revalidate: only show loading spinner if we have no cached data at all
    if (!data) setLoading(true);
    setError(null);
    try {
      const result = await getCatalystsUpcoming(days);
      setData(result);
      try {
        localStorage.setItem(`catalyst_radar_cache_${days}`, JSON.stringify(result));
      } catch (e) {}
    } catch (err) {
      setError(err.message || "Failed to load catalyst radar");
    } finally {
      setLoading(false);
    }
  }, [days, data]);

  useEffect(() => { fetchData(); }, [fetchData]);


  useEffect(() => {
    const pollProgress = async () => {
      try {
        const prog = await getScanProgress();
        if (prog) {
          setScanProgress(prog);
          if (prog.is_scanning) setScanning(true);
          else if (scanning && !prog.is_scanning) {
            setScanning(false);
            fetchData(); // Auto refresh when scan finishes
          }
        }
      } catch (err) {
        // silently ignore progress poll errors
      }
    };
    pollProgress();
    const timer = setInterval(pollProgress, 1500);
    return () => clearInterval(timer);
  }, [scanning, fetchData]);

  const handleScanAll = async () => {
    setScanning(true);
    setScanMsg("Starting background scan of all 2,000+ NSE stocks...");
    try {
      const res = await runBatchArchive(2029, false, "all");
      setScanMsg(res.message || "Background scan running across all 2,000+ NSE symbols!");
    } catch (err) {
      setScanMsg("Failed to start scan: " + (err.message || "Network error"));
    }
  };

  const handleScanMicro = async () => {
    setScanning(true);
    setScanMsg("Targeting 1,879 small/micro-cap stocks outside Nifty 200...");
    try {
      const res = await runBatchArchive(1879, false, "micro_only");
      setScanMsg(res.message || "Background scan running across 1,879 micro-cap stocks!");
    } catch (err) {
      setScanMsg("Failed to start micro-cap scan: " + (err.message || "Network error"));
    }
  };

  return (
    <div style={panelStyle}>
      {/* Header & Mode Tabs */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#f8fafc", display: "flex", alignItems: "center", gap: 8 }}>
            🛰️ Catalyst Radar
          </h2>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button
              onClick={() => setRadarTab("results-due")}
              style={{
                padding: "6px 14px",
                borderRadius: 8,
                border: radarTab === "results-due" ? "1px solid #10b981" : "1px solid #334155",
                background: radarTab === "results-due" ? "rgba(16,185,129,0.2)" : "rgba(15,23,42,0.6)",
                color: radarTab === "results-due" ? "#6ee7b7" : "#94a3b8",
                fontSize: 12.5,
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              📅 Results Due & Actions (Structured Calendar)
            </button>
            <button
              onClick={() => setRadarTab("nlp-filings")}
              style={{
                padding: "6px 14px",
                borderRadius: 8,
                border: radarTab === "nlp-filings" ? "1px solid #6366f1" : "1px solid #334155",
                background: radarTab === "nlp-filings" ? "rgba(99,102,241,0.2)" : "rgba(15,23,42,0.6)",
                color: radarTab === "nlp-filings" ? "#a5b4fc" : "#94a3b8",
                fontSize: 12.5,
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              📑 Free-Text Filings Radar (Phase 3 NLP)
            </button>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <button
            onClick={handleScanAll}
            disabled={scanning}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid #10b981",
              background: scanning ? "rgba(16,185,129,0.1)" : "rgba(16,185,129,0.2)",
              color: "#6ee7b7",
              fontSize: 12,
              fontWeight: 700,
              cursor: scanning ? "wait" : "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {scanning ? "⏳ Initiating..." : "🚀 Scan All 2,000+ Stocks"}
          </button>
          <button
            onClick={handleScanMicro}
            disabled={scanning}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid #a855f7",
              background: scanning ? "rgba(168,85,247,0.1)" : "rgba(168,85,247,0.2)",
              color: "#c4b5fd",
              fontSize: 12,
              fontWeight: 700,
              cursor: scanning ? "wait" : "pointer",
              transition: "all 0.15s ease",
            }}
          >
            🔬 Scan 1,800+ Micro Caps
          </button>
          {[30, 60, 90].map(d => (
            <button key={d} onClick={() => setDays(d)} style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: days === d ? "1px solid #6366f1" : "1px solid #334155",
              background: days === d ? "rgba(99,102,241,0.2)" : "transparent",
              color: days === d ? "#a5b4fc" : "#64748b",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}>
              {d}d
            </button>
          ))}
          <button onClick={fetchData} style={{
            padding: "6px 12px",
            borderRadius: 8,
            border: "1px solid #334155",
            background: "transparent",
            color: "#94a3b8",
            fontSize: 13,
            cursor: "pointer",
          }}>
            ↻
          </button>
        </div>
      </div>

      {/* Live Glassmorphism Progress Bar */}
      {scanProgress && (scanProgress.is_scanning || scanProgress.scanned_count > 0) && (
        <div style={{
          background: "rgba(15, 23, 42, 0.85)",
          border: scanProgress.is_scanning ? "1px solid rgba(99, 102, 241, 0.6)" : "1px solid rgba(51, 65, 85, 0.6)",
          borderRadius: 14,
          padding: "16px 20px",
          marginBottom: 20,
          boxShadow: scanProgress.is_scanning ? "0 0 25px rgba(99, 102, 241, 0.15)" : "0 4px 15px rgba(0,0,0,0.2)",
          backdropFilter: "blur(12px)",
          transition: "all 0.3s ease"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{
                display: "inline-block",
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: scanProgress.is_scanning ? "#10b981" : "#6366f1",
                boxShadow: scanProgress.is_scanning ? "0 0 10px #10b981" : "none"
              }} />
              <span style={{ fontSize: 13.5, fontWeight: 700, color: "#f8fafc", letterSpacing: "0.3px" }}>
                {scanProgress.is_scanning ? `Scanning Market Universe (${scanProgress.filter_type.toUpperCase()})` : "Last Market Scan Summary"}
              </span>
              {scanProgress.current_stock && scanProgress.is_scanning && (
                <span style={{
                  fontSize: 11.5,
                  background: "rgba(99, 102, 241, 0.2)",
                  color: "#c4b5fd",
                  padding: "3px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(99, 102, 241, 0.4)",
                  fontWeight: 700
                }}>
                  Scanning: {scanProgress.current_stock}
                </span>
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 800, color: "#38bdf8" }}>
              {scanProgress.total_stocks > 0 ? `${Math.round((scanProgress.scanned_count / scanProgress.total_stocks) * 100)}% (${scanProgress.scanned_count} / ${scanProgress.total_stocks} Stocks)` : ""}
            </div>
          </div>

          {/* Progress Bar Track */}
          <div style={{ width: "100%", height: 10, background: "rgba(30, 41, 59, 0.9)", borderRadius: 6, overflow: "hidden", border: "1px solid rgba(255,255,255,0.06)", marginBottom: 12 }}>
            <div style={{
              width: `${scanProgress.total_stocks > 0 ? Math.min(100, (scanProgress.scanned_count / scanProgress.total_stocks) * 100) : 0}%`,
              height: "100%",
              background: scanProgress.is_scanning
                ? "linear-gradient(90deg, #6366f1, #38bdf8, #10b981)"
                : "linear-gradient(90deg, #6366f1, #10b981)",
              transition: "width 0.3s ease",
              borderRadius: 6
            }} />
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12.5, color: "#94a3b8", flexWrap: "wrap", gap: 8 }}>
            <span>⚡ {scanProgress.status_msg}</span>
            <div style={{ display: "flex", gap: 16, fontWeight: 700 }}>
              <span style={{ color: "#6ee7b7" }}>📥 Disclosures Found: {scanProgress.disclosures_found || 0}</span>
              {scanProgress.catalysts_extracted > 0 && (
                <span style={{ color: "#fcd34d" }}>🎯 Catalysts Extracted: {scanProgress.catalysts_extracted}</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Scan Banner */}
      {scanMsg && !scanProgress?.is_scanning && (
        <div style={{
          background: "rgba(16,185,129,0.15)",
          border: "1px solid #10b98155",
          borderRadius: 10,
          padding: "10px 14px",
          marginBottom: 16,
          color: "#6ee7b7",
          fontSize: 12.5,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between"
        }}>
          <span>📡 {scanMsg}</span>
          <button onClick={() => setScanMsg("")} style={{ background: "transparent", border: "none", color: "#6ee7b7", cursor: "pointer", fontWeight: 700 }}>✕</button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          background: "rgba(239,68,68,0.1)",
          border: "1px solid #ef444444",
          borderRadius: 10,
          padding: 16,
          color: "#fca5a5",
          fontSize: 13,
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Content */}
      {radarTab === "results-due" ? (
        <ResultsDueView days={days} />
      ) : (
        !loading && !error && data && (() => {
          const filterList = (list = []) => {
            if (!nlpQuery.trim()) return list;
            const q = nlpQuery.trim().toLowerCase();
            return list.filter(ev => 
              (ev.symbol || "").toLowerCase().includes(q) ||
              (ev.company || "").toLowerCase().includes(q) ||
              (ev.raw_snippet || "").toLowerCase().includes(q) ||
              (ev.event_type || "").toLowerCase().includes(q)
            );
          };
          const tw = filterList(data.this_week);
          const n2 = filterList(data.next_two_weeks);
          const lt = filterList(data.later);
          const totalFiltered = tw.length + n2.length + lt.length;

          return (
            <>
              {/* NLP Filings Search & Manual Sync Bar */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#94a3b8" }}>
                  📡 Extracted Free-Text Filings ({totalFiltered}{nlpQuery ? ` matching "${nlpQuery}"` : ""})
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", flex: "1 1 300px", justifyContent: "flex-end" }}>
                  <div style={{ position: "relative", minWidth: 220, flex: "1 1 auto", maxWidth: 350 }}>
                    <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", fontSize: 13, color: "#64748b" }}>🔍</span>
                    <input
                      type="text"
                      placeholder="Filter by Symbol or Company (e.g. RELIANCE)..."
                      value={nlpQuery}
                      onChange={(e) => setNlpQuery(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "6px 28px 6px 30px",
                        borderRadius: 8,
                        border: nlpQuery ? "1px solid #38bdf8" : "1px solid #334155",
                        background: "rgba(15, 23, 42, 0.85)",
                        color: "#f8fafc",
                        fontSize: 12.5,
                        outline: "none",
                        transition: "all 0.15s ease",
                        boxSizing: "border-box"
                      }}
                    />
                    {nlpQuery && (
                      <button
                        onClick={() => setNlpQuery("")}
                        style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 13 }}
                      >✕</button>
                    )}
                  </div>

                  <button
                    onClick={fetchData}
                    disabled={loading}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 8,
                      border: "1px solid #6366f1",
                      background: loading ? "rgba(99,102,241,0.1)" : "rgba(99,102,241,0.2)",
                      color: "#a5b4fc",
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: loading ? "wait" : "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      transition: "all 0.15s ease",
                      whiteSpace: "nowrap"
                    }}
                  >
                    {loading ? "⏳ Syncing..." : "⚡ Sync NLP Filings"}
                  </button>
                </div>
              </div>

              <TimeSection
                title="This Week"
                icon="🔴"
                color="#ef4444"
                events={tw}
              />
              <TimeSection
                title="Next 2 Weeks"
                icon="🟡"
                color="#f59e0b"
                events={n2}
              />
              <TimeSection
                title="15–30 Days"
                icon="🔵"
                color="#3b82f6"
                events={lt}
              />

              {totalFiltered === 0 && (
                <div style={{
                  textAlign: "center",
                  padding: 40,
                  color: "#475569",
                  fontSize: 14,
                }}>
                  <div style={{ fontSize: 32, marginBottom: 12 }}>📡</div>
                  <p>No upcoming catalyst events found {nlpQuery ? `matching "${nlpQuery}"` : `in the next ${days} days`}.</p>
                  <p style={{ fontSize: 12, marginTop: 4 }}>Run archive backfill or clear search query.</p>
                </div>
              )}

              {/* Footer disclaimer */}
              <div style={{
                marginTop: 16,
                padding: "10px 14px",
                background: "rgba(30,41,59,0.6)",
                borderRadius: 8,
                border: "1px solid #1e293b",
                fontSize: 11,
                color: "#475569",
                lineHeight: 1.5,
              }}>
                🔒 <strong>Data Integrity:</strong> {data.note || "All events sourced exclusively from official NSE/BSE exchange filings."}
                {" "}This panel does not predict outcomes, assign probabilities, or issue buy/sell recommendations.
              </div>
            </>
          );
        })()
      )}

    </div>
  );
}
