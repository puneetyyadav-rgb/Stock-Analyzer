import React from "react";
import { TrendingUp } from "lucide-react";
import { fmtNum, fmtBig } from "../fundamental/fundamentalUtils";
import { Row, Panel, Phase2List } from "./_bfsiShared";

const gClass = (g) => (g == null ? "text-zinc-400" : g >= 8 && g <= 25 ? "text-emerald-400" : g > 35 ? "text-amber-400" : g < 0 ? "text-red-400" : "text-cyan-400");

export default function BFSIGrowth({ data }) {
  if (!data) return null;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel title="Loan Book Expansion" icon={TrendingUp} color="text-amber-400" note="8-25% YoY is healthy; runaway growth (>35%) can precede future NPAs. A slowdown often precedes NPA recognition by 1-2 years.">
          <Row label="Loan Book Growth (1Y)" value={fmtNum(data.loanBookGrowth1Y_pct, 1) + "%"} valueClass={gClass(data.loanBookGrowth1Y_pct)} />
          <Row label="Loan Book CAGR (3Y)" value={fmtNum(data.loanBookCAGR3Y_pct, 1) + "%"} valueClass={gClass(data.loanBookCAGR3Y_pct)} />
          <Row label="Earning Assets / Total" value={fmtNum(data.earningAssetsToTotal_pct, 1) + "%"} />
          {data.segmentSplit && <Row label="Segment Split" value={data.segmentSplit} valueClass="text-zinc-300 text-xs text-right max-w-[200px]" />}
          {data.geographicConcentration && <Row label="Geographic Conc." value={data.geographicConcentration} valueClass="text-zinc-300 text-xs text-right max-w-[200px]" />}
        </Panel>
        <Panel title="Loan Book Trend (₹ Cr)" icon={TrendingUp} color="text-amber-400" note={data.note}>
          {(data.loanBookSeries_cr || []).map((l, i) => (
            <Row key={i} label={`FY-${i}`} value={fmtBig(l)} />
          ))}
        </Panel>
      </div>
      <Phase2List stubs={data.phase2Stubs} />
    </div>
  );
}
