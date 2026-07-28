// Helper functions for FundamentalDeck and subcomponents

export const fmtNum = (val, decimals = 2) => {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  return Number(val).toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

export const fmtPct = (val, decimals = 1) => {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  const num = Number(val);
  return `${num > 0 ? "+" : ""}${num.toFixed(decimals)}%`;
};

export const fmtBig = (val) => {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  const num = Number(val);
  if (Math.abs(num) >= 100000) return `₹${(num / 100000).toFixed(2)} L Cr`;
  if (Math.abs(num) >= 1000) return `₹${(num / 1000).toFixed(2)} k Cr`;
  return `₹${num.toFixed(1)} Cr`;
};

export const getVal0 = (obj) => {
  if (Array.isArray(obj)) return obj.length > 0 ? obj[0] : null;
  if (obj !== null && typeof obj === "object") {
    for (const k of ["value", "values", "financialPrimary", "ocf", "fcf", "reported"]) {
      if (Array.isArray(obj[k])) return obj[k].length > 0 ? obj[k][0] : null;
      if (typeof obj[k] === "number") return obj[k];
    }
  }
  return typeof obj === "number" ? obj : null;
};

// Section 5.4 Color Convention for Letter Grades
export const gradeStyle = (letter) => {
  if (!letter) {
    return {
      text: "text-zinc-400",
      bg: "bg-zinc-950/40",
      border: "border-zinc-800",
      badge: "bg-zinc-900/60 text-zinc-300 border-zinc-700",
      glow: "shadow-none",
    };
  }
  const l = letter.toUpperCase();
  if (l.startsWith("A")) {
    return {
      text: "text-emerald-400",
      bg: "bg-emerald-950/30",
      border: "border-emerald-500/40",
      badge: "bg-emerald-900/50 text-emerald-300 border-emerald-700",
      glow: "shadow-[0_0_20px_rgba(16,185,129,0.15)]",
    };
  }
  if (l.startsWith("B")) {
    return {
      text: "text-cyan-400",
      bg: "bg-cyan-950/30",
      border: "border-cyan-500/40",
      badge: "bg-cyan-900/50 text-cyan-300 border-cyan-700",
      glow: "shadow-[0_0_20px_rgba(6,182,212,0.15)]",
    };
  }
  if (l.startsWith("C")) {
    return {
      text: "text-amber-400",
      bg: "bg-amber-950/30",
      border: "border-amber-500/40",
      badge: "bg-amber-900/50 text-amber-300 border-amber-700",
      glow: "shadow-[0_0_20px_rgba(245,158,11,0.15)]",
    };
  }
  return {
    text: "text-red-400",
    bg: "bg-red-950/30",
    border: "border-red-500/40",
    badge: "bg-red-900/50 text-red-300 border-red-700",
    glow: "shadow-[0_0_20px_rgba(239,68,68,0.15)]",
  };
};

// Sub-score color scale
export const pillarColor = (score) => {
  if (score === null || score === undefined) return "text-zinc-500";
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-cyan-400";
  if (score >= 40) return "text-amber-400";
  return "text-red-400";
};

// Peer matrix rank color
export const rankColor = (rank, total) => {
  if (!rank || !total) return "text-zinc-400 bg-transparent";
  if (rank === 1) return "text-emerald-400 bg-emerald-950/40 font-semibold";
  if (rank === 2) return "text-cyan-400 bg-cyan-950/30";
  if (rank === 3 && total >= 4) return "text-amber-400 bg-amber-950/30";
  if (rank === total && total >= 3) return "text-red-400 bg-red-950/30";
  return "text-zinc-300 bg-transparent";
};

// Zone badges for Altman / Beneish / Sloan
export const zoneStyle = (zone) => {
  if (!zone) return "bg-zinc-800 text-zinc-300 border-zinc-700";
  const z = String(zone).toLowerCase();
  if (z.includes("safe") || z.includes("clean") || z.includes("low") || z.includes("compounder")) {
    return "bg-emerald-950/60 text-emerald-300 border border-emerald-800/60";
  }
  if (z.includes("grey") || z.includes("moderate") || z.includes("corroborate") || z.includes("cash cow") || z.includes("10-20%")) {
    return "bg-amber-950/60 text-amber-300 border border-amber-800/60";
  }
  if (z.includes("distress") || z.includes("high") || z.includes("red") || z.includes("destroyer") || z.includes(">20%")) {
    return "bg-red-950/60 text-red-300 border border-red-800/60";
  }
  return "bg-zinc-800 text-zinc-300 border-zinc-700";
};
