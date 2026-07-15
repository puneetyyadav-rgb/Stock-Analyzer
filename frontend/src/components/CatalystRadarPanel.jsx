/**
 * CatalystRadarPanel.jsx — Phase 4: Catalyst Radar Dashboard Panel
 * Displays upcoming deterministically extracted events from official NSE/BSE filings.
 * Grouped by time horizon: This Week / Next 2 Weeks / 15-30 Days.
 * Strictly NO probability scores, NO outcome predictions, NO buy/sell badges.
 */
import React, { useState, useEffect, useCallback } from "react";
import { getCatalystsUpcoming } from "../lib/api";

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

export default function CatalystRadarPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [days, setDays] = useState(30);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getCatalystsUpcoming(days);
      setData(result);
    } catch (err) {
      setError(err.message || "Failed to load catalyst radar");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#f8fafc", display: "flex", alignItems: "center", gap: 8 }}>
            🛰️ Catalyst Radar
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "#64748b" }}>
            Upcoming events from official NSE/BSE filings · No predictions · No probabilities
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>
          <div style={{ fontSize: 28, marginBottom: 12, animation: "pulse 1.5s infinite" }}>🛰️</div>
          <p>Scanning official NSE/BSE filings for upcoming events...</p>
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
      {!loading && !error && data && (
        <>
          <TimeSection
            title="This Week"
            icon="🔴"
            color="#ef4444"
            events={data.this_week}
          />
          <TimeSection
            title="Next 2 Weeks"
            icon="🟡"
            color="#f59e0b"
            events={data.next_two_weeks}
          />
          <TimeSection
            title="15–30 Days"
            icon="🔵"
            color="#3b82f6"
            events={data.later}
          />

          {data.total === 0 && (
            <div style={{
              textAlign: "center",
              padding: 40,
              color: "#475569",
              fontSize: 14,
            }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>📡</div>
              <p>No upcoming catalyst events found in the next {days} days.</p>
              <p style={{ fontSize: 12, marginTop: 4 }}>Run archive backfill to populate historical filings.</p>
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
      )}
    </div>
  );
}
