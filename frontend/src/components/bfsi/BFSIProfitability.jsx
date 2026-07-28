import React from "react";
import { Coins, TrendingUp } from "lucide-react";
import { fmtNum, fmtBig, pillarColor } from "../fundamental/fundamentalUtils";
import { Row, Panel, Phase2List } from "./_bfsiShared";

const roaClass = (r) => (r == null ? "text-zinc-400" : r >= 1.5 ? "text-emerald-400" : r >= 1.0 ? "text-cyan-400" : r >= 0.5 ? "text-amber-400" : "text-red-400");
const roeClass = (r) => (r == null ? "text-zinc-400" : r >= 15 ? "text-emerald-400" : r >= 12 ? "text-cyan-400" : r >= 10 ? "text-amber-400" : "text-red-400");
const cirClass = (c) => (c == null ? "text-zinc-400" : c < 45 ? "text-emerald-400" : c <= 55 ? "text-amber-400" : "text-red-400");

export default function BFSIProfitability({ data }) {
  if (!data) return null;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel title="Net Interest Margin Engine" icon={Coins} color="text-emerald-400" note={data.note}>
          <Row label="Net Interest Income" value={fmtBig(data.nii_cr)} />
          <Row label="NII Growth (1Y)" value={fmtNum(data.niiGrowth1Y_pct, 1) + "%"} valueClass={data.niiGrowth1Y_pct >= 15 ? "text-emerald-400" : "text-zinc-200"} />
          <Row label="NIM (proxy)" value={fmtNum(data.nimProxy_pct, 2) + "%"} valueClass="text-emerald-300" />
          <Row label="Interest Spread Ratio" value={fmtNum(data.spreadRatio, 3)} valueClass={data.spreadRatio < 1.3 ? "text-amber-400" : "text-zinc-200"} />
          <Row label="Fee Income Share" value={fmtNum(data.feeIncomeShare_pct, 1) + "%"} valueClass={data.feeIncomeShare_pct > 40 ? "text-amber-400" : "text-zinc-200"} />
        </Panel>
        <Panel title="Returns & Efficiency" icon={TrendingUp} color="text-emerald-400" note="RoA > 1.5% is best-in-class; Cost-to-Income < 45% is efficient. PPOP strips out provisioning volatility.">
          <Row label="Return on Assets (RoA)" value={fmtNum(data.roa_pct, 2) + "%"} valueClass={roaClass(data.roa_pct)} />
          <Row label="Return on Equity (RoE)" value={fmtNum(data.roe_pct, 1) + "%"} valueClass={roeClass(data.roe_pct)} />
          <Row label="Cost-to-Income" value={fmtNum(data.costToIncome_pct, 1) + "%"} valueClass={cirClass(data.costToIncome_pct)} />
          <Row label="PPOP" value={fmtBig(data.ppop_cr)} />
          <Row label="PPOP Margin" value={fmtNum(data.ppopMargin_pct, 2) + "%"} valueClass={pillarColor(data.ppopMargin_pct >= 2 ? 80 : 40)} />
        </Panel>
      </div>
      <Phase2List stubs={data.phase2Stubs} />
    </div>
  );
}
