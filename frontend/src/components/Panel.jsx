import React from "react";

export const Panel = ({ title, right, children, className = "", testId }) => (
  <div className={`bg-[#0c0c0e] border border-zinc-800 flex flex-col ${className}`} data-testid={testId}>
    {(title || right) && (
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <h3 className="text-[10px] tracking-[0.2em] uppercase text-zinc-400 font-medium">{title}</h3>
        {right}
      </div>
    )}
    <div className="flex-1 p-3">{children}</div>
  </div>
);

export const KV = ({ label, value, valueClass = "" }) => (
  <div className="flex items-center justify-between py-1.5 border-b border-zinc-800/40 last:border-0">
    <span className="text-[10px] tracking-widest uppercase text-zinc-500">{label}</span>
    <span className={`text-sm font-mono tabular-nums ${valueClass}`}>{value}</span>
  </div>
);
