import React, { useState } from "react";
import { Table, FileText, AlertCircle, ChevronDown, ChevronUp, Layers, DollarSign } from "lucide-react";
import { fmtNum, fmtPct, fmtBig } from "./fundamentalUtils";

export default function FundamentalRawData({ incomeStatement, balanceSheet, cashFlow, meta }) {
  const [activeTab, setActiveTab] = useState("income"); // "income" | "balance" | "cashflow"
  const [isCollapsed, setIsCollapsed] = useState(false);

  const fyEnds = meta?.fiscalYearEnds || ["FY1", "FY2", "FY3", "FY4", "FY5"];
  const isIndAS116 = incomeStatement?.indAS116ComparabilityFlag || balanceSheet?.workingCapital?.indAS116ComparabilityFlag;

  const renderRow = (label, arr, isPct = false, isScalar = false) => {
    if (!arr || !Array.isArray(arr)) {
      return (
        <tr className="hover:bg-zinc-900/40 transition-colors border-b border-zinc-800/40">
          <td className="py-2.5 px-3 font-medium text-zinc-300 font-sans">{label}</td>
          {fyEnds.map((_, i) => (
            <td key={i} className="py-2.5 px-3 text-right font-mono text-zinc-600">—</td>
          ))}
        </tr>
      );
    }

    return (
      <tr className="hover:bg-zinc-900/40 transition-colors border-b border-zinc-800/40">
        <td className="py-2.5 px-3 font-medium text-zinc-300 font-sans">{label}</td>
        {fyEnds.map((_, i) => {
          const val = arr[i];
          const formatted = val !== null && val !== undefined ? (isPct ? fmtPct(val, 1) : isScalar ? `₹${fmtNum(val, 2)}` : fmtNum(val, 1)) : "—";
          return (
            <td key={i} className={`py-2.5 px-3 text-right font-mono tabular-nums ${val !== null ? "text-zinc-200" : "text-zinc-600"}`}>
              {formatted}
            </td>
          );
        })}
      </tr>
    );
  };

  return (
    <div className="space-y-6">
      {/* Ind AS 116 Lease Accounting Comparability Note */}
      {isIndAS116 && (
        <div className="bg-amber-950/30 border border-amber-600/40 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-amber-200/90 leading-relaxed">
            <strong className="text-amber-300 uppercase font-semibold block mb-0.5">
              Ind AS 116 Lease Accounting Standard Notice
            </strong>
            This company's historical comparability across FY19–FY21 is affected by the implementation of Ind AS 116 (Leases). Under Ind AS 116, operating lease expenses are reclassified into depreciation (on Right-of-Use assets) and finance costs (on lease liabilities), which artificially increases reported EBITDA and Operating Cash Flow compared to pre-implementation years.
          </div>
        </div>
      )}

      {/* Collapsible 3-Tab Raw Statement Viewer */}
      <div className="bg-[#0c0c0e] border border-zinc-800/80 rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-zinc-800/80">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100 uppercase tracking-wider flex items-center gap-2">
              <FileText className="w-4 h-4 text-emerald-400" />
              Raw Financial Statement Data
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Historical statement items and primary ratios across 5 fiscal years (Unit: {meta?.currencyUnit || "₹ Crores"}).
            </p>
          </div>

          <div className="flex items-center gap-2 self-start">
            <div className="flex items-center bg-zinc-900/90 p-1 rounded-md border border-zinc-800">
              <button
                onClick={() => { setActiveTab("income"); setIsCollapsed(false); }}
                className={`px-3 py-1 text-xs rounded transition-all ${activeTab === "income" && !isCollapsed ? "bg-zinc-800 text-zinc-100 font-medium shadow-sm" : "text-zinc-400 hover:text-zinc-200"}`}
              >
                Income Statement
              </button>
              <button
                onClick={() => { setActiveTab("balance"); setIsCollapsed(false); }}
                className={`px-3 py-1 text-xs rounded transition-all ${activeTab === "balance" && !isCollapsed ? "bg-zinc-800 text-zinc-100 font-medium shadow-sm" : "text-zinc-400 hover:text-zinc-200"}`}
              >
                Balance Sheet
              </button>
              <button
                onClick={() => { setActiveTab("cashflow"); setIsCollapsed(false); }}
                className={`px-3 py-1 text-xs rounded transition-all ${activeTab === "cashflow" && !isCollapsed ? "bg-zinc-800 text-zinc-100 font-medium shadow-sm" : "text-zinc-400 hover:text-zinc-200"}`}
              >
                Cash Flow
              </button>
            </div>

            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="p-1.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 rounded border border-zinc-800 transition-colors"
              title={isCollapsed ? "Expand Table" : "Collapse Table"}
            >
              {isCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {!isCollapsed && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-[10px] tracking-wider uppercase text-zinc-400 bg-zinc-900/60 font-mono">
                  <th className="py-2.5 px-3 font-semibold">Line Item / Metric</th>
                  {fyEnds.map((date, idx) => (
                    <th key={idx} className="py-2.5 px-3 text-right font-semibold">
                      <div className="text-zinc-200">{date ? `FY${date.slice(2, 4)}` : `Year ${idx + 1}`}</div>
                      <div className="text-[9px] text-zinc-500 font-normal">{date || "—"}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {activeTab === "income" && (
                  <>
                    <tr className="bg-zinc-950/60 text-zinc-500 font-mono text-[10px] uppercase tracking-wider">
                      <td colSpan={fyEnds.length + 1} className="py-1.5 px-3 font-bold">Absolute Financials (₹ Crores)</td>
                    </tr>
                    {renderRow("Total Revenue (Operating)", incomeStatement?.totalRevenue)}
                    {renderRow("Gross Profit", incomeStatement?.grossProfit)}
                    {renderRow("EBITDA", incomeStatement?.ebitda)}
                    {renderRow("EBIT (Operating Profit)", incomeStatement?.ebit)}
                    {renderRow("Basic EPS", incomeStatement?.basicEps, false, true)}

                    <tr className="bg-zinc-950/60 text-zinc-500 font-mono text-[10px] uppercase tracking-wider">
                      <td colSpan={fyEnds.length + 1} className="py-1.5 px-3 font-bold">Operating Ratios & Growth (%)</td>
                    </tr>
                    {renderRow("Revenue YoY Growth", incomeStatement?.revenueYoyGrowthPct, true)}
                    {renderRow("Gross Profit Margin", incomeStatement?.grossMarginPct, true)}
                    {renderRow("EBITDA Margin", incomeStatement?.ebitdaMarginPct, true)}
                    {renderRow("Operating Margin (EBIT)", incomeStatement?.operatingMarginPct, true)}
                    {renderRow("Interest Exp % of EBIT", incomeStatement?.interestExpPctOfEbitReported, true)}
                  </>
                )}

                {activeTab === "balance" && (
                  <>
                    <tr className="bg-zinc-950/60 text-zinc-500 font-mono text-[10px] uppercase tracking-wider">
                      <td colSpan={fyEnds.length + 1} className="py-1.5 px-3 font-bold">Assets & Working Capital (₹ Crores)</td>
                    </tr>
                    {renderRow("Total Assets", balanceSheet?.assets?.totalAssets)}
                    {renderRow("Cash & Bank Balances", balanceSheet?.assets?.cash)}
                    {renderRow("Trade Receivables", balanceSheet?.assets?.receivables)}
                    {renderRow("Inventories", balanceSheet?.assets?.inventory)}
                    {renderRow("Net PPE (Property & Plant)", balanceSheet?.assets?.netPPE)}
                    {renderRow("Net Working Capital (NWC)", balanceSheet?.workingCapital?.nwc)}

                    <tr className="bg-zinc-950/60 text-zinc-500 font-mono text-[10px] uppercase tracking-wider">
                      <td colSpan={fyEnds.length + 1} className="py-1.5 px-3 font-bold">Capital Structure & Book Value</td>
                    </tr>
                    {renderRow("Financial Debt", balanceSheet?.liabilities?.financialDebt)}
                    {renderRow("Lease Liabilities (Ind AS 116)", balanceSheet?.liabilities?.leaseLiabilities)}
                    {renderRow("Total Debt Reference", balanceSheet?.liabilities?.totalDebtReference)}
                    {renderRow("Book Value Per Share (BVPS)", balanceSheet?.bookValue?.bvps, false, true)}
                  </>
                )}

                {activeTab === "cashflow" && (
                  <>
                    <tr className="bg-zinc-950/60 text-zinc-500 font-mono text-[10px] uppercase tracking-wider">
                      <td colSpan={fyEnds.length + 1} className="py-1.5 px-3 font-bold">Cash Flow Generation (₹ Crores)</td>
                    </tr>
                    {renderRow("Operating Cash Flow (OCF)", cashFlow?.ocfQuality?.ocf)}
                    {renderRow("Free Cash Flow (FCF)", cashFlow?.ocfQuality?.fcf)}
                    {renderRow("Capital Expenditures (CapEx)", cashFlow?.capex?.capexAbsolute || cashFlow?.capex?.capex)}
                    {renderRow("FCF to Equity (FCFE)", cashFlow?.financing?.freeCashFlowToEquity)}
                  </>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
