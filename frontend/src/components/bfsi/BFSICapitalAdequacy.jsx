import React from "react";
import { ShieldCheck, Activity } from "lucide-react";
import { fmtNum } from "../fundamental/fundamentalUtils";
import { Row, Panel, Phase2List } from "./_bfsiShared";

const eqClass = (e) => (e == null ? "text-zinc-400" : e >= 7 ? "text-emerald-400" : e >= 5 ? "text-cyan-400" : "text-red-400");
const ldrClass = (l) => (l == null ? "text-zinc-400" : l > 90 ? "text-red-400" : l >= 75 ? "text-cyan-400" : "text-emerald-400");

export default function BFSICapitalAdequacy({ capital, liquidity }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel title="Capital Adequacy" icon={ShieldCheck} color="text-indigo-400" note={capital?.note}>
          {capital?.crar_pct != null && <Row label="Reported CRAR (Basel III)" value={fmtNum(capital?.crar_pct, 1) + "%"} valueClass={capital?.crar_pct >= 15 ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"} />}
          {capital?.Tier1Capital_pct != null && <Row label="Tier 1 Capital" value={fmtNum(capital?.Tier1Capital_pct, 1) + "%"} valueClass="text-emerald-400" />}
          {capital?.CET1_pct != null && <Row label="CET 1 Ratio" value={fmtNum(capital?.CET1_pct, 1) + "%"} valueClass="text-emerald-400" />}
          {capital?.leverageRatio_pct != null && <Row label="Leverage Ratio" value={fmtNum(capital?.leverageRatio_pct, 1) + "%"} />}
          <Row label="Equity / Total Assets (leverage proxy)" value={fmtNum(capital?.equityToTotalAssets_pct, 1) + "%"} valueClass={eqClass(capital?.equityToTotalAssets_pct)} />
          <Row label="BVPS (₹)" value={fmtNum(capital?.bvps_inr, 2)} />
          <Row label="Tangible BVPS (₹)" value={fmtNum(capital?.tbvps_inr, 2)} />
          <Row label="BVPS Growth (1Y)" value={fmtNum(capital?.bvpsGrowth1Y_pct, 1) + "%"} valueClass={capital?.bvpsGrowth1Y_pct < 0 ? "text-red-400" : "text-emerald-400"} />
        </Panel>
        <Panel title="Liquidity Management" icon={Activity} color="text-teal-400" note={liquidity?.note}>
          {liquidity?.LCR_pct != null && <Row label="Liquidity Coverage Ratio (LCR)" value={fmtNum(liquidity?.LCR_pct, 1) + "%"} valueClass="text-emerald-400 font-bold" />}
          {liquidity?.NSFR_pct != null && <Row label="Net Stable Funding (NSFR)" value={fmtNum(liquidity?.NSFR_pct, 1) + "%"} valueClass="text-emerald-400 font-bold" />}
          {liquidity?.ALM_mismatch != null && <Row label="ALM Mismatch" value={liquidity?.ALM_mismatch} />}
          <Row label="Cash / Total Assets" value={fmtNum(liquidity?.cashToTotalAssets_pct, 1) + "%"} />
          <Row label="Investments / Total Assets" value={fmtNum(liquidity?.investmentsToTotalAssets_pct, 1) + "%"} />
          <Row label="Loan-to-Deposit Ratio" value={fmtNum(liquidity?.loanToDepositRatio_pct, 0) + "%"} valueClass={ldrClass(liquidity?.loanToDepositRatio_pct)} />
        </Panel>
      </div>
      <Phase2List stubs={{ ...(capital?.phase2Stubs || {}), ...(liquidity?.phase2Stubs || {}) }} />
    </div>
  );
}
