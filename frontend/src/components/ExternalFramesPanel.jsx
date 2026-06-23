import React, { useState } from "react";
import { Panel } from "./Panel";
import { Loader2, ExternalLink } from "lucide-react";

export default function ExternalFramesPanel({ symbol }) {
  const [activeTab, setActiveTab] = useState("trendlyne");
  const [loading, setLoading] = useState(true);

  if (!symbol) return null;

  const TABS = [
    { id: "trendlyne", label: "Trendlyne", url: `https://trendlyne.com/equity/${symbol}/forecasts/` }
  ];

  const currentTab = TABS.find((t) => t.id === activeTab);

  return (
    <Panel
      title="External Analysis View"
      right={
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  setLoading(true);
                  setActiveTab(t.id);
                }}
                className={`px-2 py-0.5 text-[10px] tracking-widest uppercase font-medium border ${
                  activeTab === t.id
                    ? "bg-zinc-100 text-zinc-950 border-zinc-100"
                    : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:border-zinc-600"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <a
            href={currentTab.url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-[10px] tracking-widest uppercase text-blue-400 hover:text-blue-300 ml-2"
          >
            Pop Out <ExternalLink size={10} />
          </a>
        </div>
      }
    >
      <div className="relative w-full h-[800px] border border-zinc-800/60 bg-zinc-950 mt-2 rounded overflow-hidden">
        {loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950/80 z-10 backdrop-blur-sm">
            <Loader2 size={24} className="animate-spin text-amber-500 mb-2" />
            <span className="text-xs text-zinc-400 tracking-widest uppercase">Loading External Page...</span>
          </div>
        )}
        <iframe
          key={currentTab.url}
          src={currentTab.url}
          className="w-full h-full border-0"
          onLoad={() => setLoading(false)}
          title={`External Frame ${currentTab.label}`}
        />
      </div>
    </Panel>
  );
}
