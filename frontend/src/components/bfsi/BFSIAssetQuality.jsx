import React from "react";
import { ShieldAlert, AlertTriangle } from "lucide-react";
import { fmtNum, fmtBig } from "../fundamental/fundamentalUtils";
import { Row, Panel, Phase2List } from "./_bfsiShared";

export default function BFSIAssetQuality({ data }) {
  if (!data) return null;
  return (
    <div className="space-y-4">
      {data.assetQualityProxyFlag && (
        <div className="border border-red-800/60 bg-red-950/30 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-200 leading-relaxed">{data.assetQualityProxyFlag}</p>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel title="Balance-Sheet Asset Quality Proxies" icon={ShieldAlert} color="text-orange-400" note={data.note}>
          <Row label="Net Loans / Total Assets" value={fmtNum(data.netLoansToTotalAssets_pct, 1) + "%"} />
          <Row label="Provision Growth (1Y)" value={fmtNum(data.provisionGrowth1Y_pct, 1) + "%"} valueClass={data.provisionGrowth1Y_pct > 30 ? "text-red-400" : "text-zinc-200"} />
        </Panel>
        <Panel title="Provisioning Trend (₹ Cr)" icon={ShieldAlert} color="text-orange-400" note="Rising provisions relative to the loan book signal deteriorating credit quality ahead of reported NPAs.">
          {(data.provisionSeries_cr || []).map((p, i) => (
            <Row key={i} label={`FY-${i}`} value={fmtBig(p)} />
          ))}
        </Panel>
      </div>
      <Phase2List stubs={data.phase2Stubs} />
    </div>
  );
}
