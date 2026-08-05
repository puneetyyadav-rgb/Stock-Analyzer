import React from "react";
import { PiggyBank } from "lucide-react";
import { fmtNum, fmtBig } from "../fundamental/fundamentalUtils";
import { Row, Panel, Phase2List } from "./_bfsiShared";

export default function BFSIDepositFranchise({ data }) {
  if (!data) return null;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel title="Deposit Base" icon={PiggyBank} color="text-cyan-400" note={data.note}>
          {data.casaRatio_pct != null && <Row label="Reported CASA Ratio" value={fmtNum(data.casaRatio_pct, 1) + "%"} valueClass={data.casaRatio_pct >= 40 ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"} />}
          <Row label="Total Deposits" value={fmtBig(data.totalDeposits_cr)} />
          <Row label="Deposit Growth (1Y)" value={fmtNum(data.depositGrowth1Y_pct, 1) + "%"} />
          <Row label="Deposits / Total Liabilities" value={fmtNum(data.depositsToLiabilities_pct, 1) + "%"} valueClass={data.depositsToLiabilities_pct >= 65 ? "text-emerald-400" : "text-amber-400"} />
        </Panel>
        <Panel title="Cost & Stability of Funding" icon={PiggyBank} color="text-cyan-400" note="Low borrowings/deposits + high CASA (Phase-2) = structural funding-cost advantage.">
          <Row label="Cost of Deposits (proxy)" value={fmtNum(data.costOfDepositsProxy_pct, 2) + "%"} />
          <Row label="Borrowings / Deposits" value={fmtNum(data.borrowingsToDeposits_pct, 1) + "%"} valueClass={data.borrowingsToDeposits_pct > 40 ? "text-red-400" : "text-emerald-400"} />
        </Panel>
      </div>
      <Phase2List stubs={data.phase2Stubs} />
    </div>
  );
}
