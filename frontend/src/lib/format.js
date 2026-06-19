export const fmtNum = (n, decimals = 2) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

export const fmtPrice = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return `₹${fmtNum(n)}`;
};

export const fmtPct = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${Number(n).toFixed(2)}%`;
};

export const fmtCr = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const cr = n / 1e7;
  if (Math.abs(cr) >= 1e5) return `₹${(cr / 1e5).toFixed(2)} L Cr`;
  if (Math.abs(cr) >= 1) return `₹${cr.toFixed(2)} Cr`;
  return `₹${fmtNum(n, 0)}`;
};

export const fmtBigNum = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e7) return `${(n / 1e7).toFixed(2)} Cr`;
  if (abs >= 1e5) return `${(n / 1e5).toFixed(2)} L`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(2)} K`;
  return fmtNum(n, 0);
};

export const colorClass = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "text-zinc-400";
  return n >= 0 ? "text-emerald-400" : "text-red-400";
};
