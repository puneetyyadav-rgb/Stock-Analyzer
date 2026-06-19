import React, { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { Star, X, Bell, BellRing, Plus, Trash2, ChevronRight } from "lucide-react";
import { getWatchlist, removeFromWatchlist, getAlerts, addAlert, removeAlert, markAlertTriggered } from "../lib/watchlist";
import axios from "axios";
import { fmtNum, fmtPct, colorClass } from "../lib/format";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function WatchlistPanel({ onSelect, currentSymbol }) {
  const [list, setList] = useState(getWatchlist());
  const [prices, setPrices] = useState({});
  const [alerts, setAlerts] = useState(getAlerts());
  const [showAlertForm, setShowAlertForm] = useState(false);
  const [newAlert, setNewAlert] = useState({ symbol: "", condition: "above", price: "", note: "" });

  // Listen for external changes (starred from Dashboard etc.)
  useEffect(() => {
    const refresh = () => { setList(getWatchlist()); setAlerts(getAlerts()); };
    window.addEventListener("watchlist-changed", refresh);
    window.addEventListener("alerts-changed", refresh);
    return () => {
      window.removeEventListener("watchlist-changed", refresh);
      window.removeEventListener("alerts-changed", refresh);
    };
  }, []);

  // Poll prices for watchlist + alert checking
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const symbols = Array.from(new Set([...list, ...alerts.filter((a) => !a.triggered).map((a) => a.symbol)]));
      const newPrices = { ...prices };
      for (const sym of symbols) {
        try {
          const r = await axios.get(`${API}/stock/${sym}/overview`);
          newPrices[sym] = { price: r.data.price, change: r.data.change, changePercent: r.data.changePercent };
        } catch (_) {
          // ignore
        }
      }
      if (cancelled) return;
      setPrices(newPrices);
      // Check alerts
      const active = getAlerts();
      for (const a of active) {
        if (a.triggered) continue;
        const p = newPrices[a.symbol]?.price;
        if (!p) continue;
        const hit = (a.condition === "above" && p >= a.price) || (a.condition === "below" && p <= a.price);
        if (hit) {
          toast.success(`Alert: ${a.symbol} ${a.condition} ₹${a.price}`, { description: `Current ₹${p.toFixed(2)}. ${a.note}` });
          markAlertTriggered(a.id);
          setAlerts(getAlerts());
          try {
            if (Notification && Notification.permission === "granted") {
              new Notification(`Stock Sentinel Alert`, { body: `${a.symbol} ${a.condition} ₹${a.price} → Now ₹${p.toFixed(2)}` });
            }
          } catch (_) {
            // notifications not supported
          }
        }
      }
    };
    if (list.length || alerts.length) tick();
    const id = setInterval(tick, 60000);
    return () => { cancelled = true; clearInterval(id); };
  }, [list, alerts.length]);

  useEffect(() => {
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      Notification.requestPermission?.();
    }
  }, []);

  const remove = (sym) => {
    setList(removeFromWatchlist(sym));
    toast(`${sym} removed from watchlist`);
  };

  const submitAlert = (e) => {
    e.preventDefault();
    if (!newAlert.symbol || !newAlert.price) return;
    setAlerts(addAlert(newAlert));
    setNewAlert({ symbol: "", condition: "above", price: "", note: "" });
    setShowAlertForm(false);
    toast.success(`Alert added: ${newAlert.symbol.toUpperCase()} ${newAlert.condition} ₹${newAlert.price}`);
  };

  const delAlert = (id) => {
    setAlerts(removeAlert(id));
  };

  return (
    <div className="space-y-3">
      <Panel
        title="My Watchlist"
        testId="watchlist-panel"
        right={<span className="text-[9px] tracking-widest uppercase text-zinc-500">{list.length}/30</span>}
      >
        {list.length === 0 && (
          <p className="text-xs text-zinc-600">Star a stock to add it here. Auto-refreshes every 60s.</p>
        )}
        {list.length > 0 && (
          <div className="space-y-0.5">
            {list.map((sym) => {
              const p = prices[sym];
              const active = currentSymbol === sym;
              return (
                <div
                  key={sym}
                  className={`flex items-center justify-between py-1.5 px-2 border-l-2 cursor-pointer transition-colors ${
                    active ? "border-blue-500 bg-blue-950/30" : "border-transparent hover:bg-zinc-900/40"
                  }`}
                  onClick={() => onSelect(sym)}
                  data-testid={`watchlist-item-${sym}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-medium text-zinc-200">{sym}</span>
                    {p && <span className="text-[10px] font-mono text-zinc-400">₹{fmtNum(p.price)}</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    {p && (
                      <span className={`text-[10px] font-mono tabular-nums ${colorClass(p.changePercent)}`}>{fmtPct(p.changePercent)}</span>
                    )}
                    <button onClick={(e) => { e.stopPropagation(); remove(sym); }} className="text-zinc-600 hover:text-red-400" data-testid={`remove-watchlist-${sym}`}>
                      <X size={11} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>

      <Panel
        title="Price Alerts"
        testId="alerts-panel"
        right={
          <button
            onClick={() => setShowAlertForm((v) => !v)}
            className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] tracking-widest uppercase bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
            data-testid="add-alert-btn"
          >
            <Plus size={10} /> New
          </button>
        }
      >
        {showAlertForm && (
          <form onSubmit={submitAlert} className="space-y-1.5 mb-3 p-2 bg-zinc-900/40 border border-zinc-800/60" data-testid="alert-form">
            <div className="grid grid-cols-3 gap-1.5">
              <input
                placeholder="SYMBOL"
                value={newAlert.symbol}
                onChange={(e) => setNewAlert({ ...newAlert, symbol: e.target.value.toUpperCase() })}
                className="bg-zinc-950 border border-zinc-800 px-2 py-1 text-xs font-mono"
                required
                data-testid="alert-symbol-input"
              />
              <select
                value={newAlert.condition}
                onChange={(e) => setNewAlert({ ...newAlert, condition: e.target.value })}
                className="bg-zinc-950 border border-zinc-800 px-1 py-1 text-xs"
                data-testid="alert-condition-select"
              >
                <option value="above">Above</option>
                <option value="below">Below</option>
              </select>
              <input
                placeholder="₹ price"
                type="number"
                step="0.01"
                value={newAlert.price}
                onChange={(e) => setNewAlert({ ...newAlert, price: e.target.value })}
                className="bg-zinc-950 border border-zinc-800 px-2 py-1 text-xs font-mono"
                required
                data-testid="alert-price-input"
              />
            </div>
            <input
              placeholder="Note (optional)"
              value={newAlert.note}
              onChange={(e) => setNewAlert({ ...newAlert, note: e.target.value })}
              className="w-full bg-zinc-950 border border-zinc-800 px-2 py-1 text-xs"
              data-testid="alert-note-input"
            />
            <button type="submit" className="w-full py-1 text-[10px] tracking-widest uppercase bg-blue-600 hover:bg-blue-500 text-white" data-testid="submit-alert">
              Create Alert
            </button>
          </form>
        )}
        {alerts.length === 0 && !showAlertForm && (
          <p className="text-xs text-zinc-600">No alerts yet. Get notified when a stock hits your price.</p>
        )}
        {alerts.length > 0 && (
          <div className="space-y-1">
            {alerts.map((a) => (
              <div key={a.id} className="flex items-center justify-between py-1 px-1.5 border-l-2 border-amber-500/40 bg-zinc-900/30" data-testid={`alert-${a.id}`}>
                <div className="flex items-center gap-1.5">
                  {a.triggered ? <BellRing size={11} className="text-emerald-400" /> : <Bell size={11} className="text-amber-400" />}
                  <span className="text-[11px] font-mono">{a.symbol}</span>
                  <span className="text-[10px] text-zinc-500">{a.condition}</span>
                  <span className="text-[11px] font-mono">₹{a.price}</span>
                  {a.triggered && <span className="text-[9px] tracking-widest uppercase text-emerald-400">HIT</span>}
                </div>
                <button onClick={() => delAlert(a.id)} className="text-zinc-600 hover:text-red-400" data-testid={`remove-alert-${a.id}`}>
                  <Trash2 size={10} />
                </button>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
