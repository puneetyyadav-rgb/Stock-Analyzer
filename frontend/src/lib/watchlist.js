/* Watchlist & alerts — pure localStorage; no auth required */

const WL_KEY = "ssin_watchlist";
const AL_KEY = "ssin_alerts";

export const getWatchlist = () => {
  try {
    return JSON.parse(localStorage.getItem(WL_KEY) || "[]");
  } catch {
    return [];
  }
};

export const addToWatchlist = (symbol) => {
  const list = getWatchlist();
  const norm = symbol.toUpperCase().replace(".NS", "");
  if (!list.find((s) => s === norm)) {
    list.unshift(norm);
    localStorage.setItem(WL_KEY, JSON.stringify(list.slice(0, 30)));
  }
  window.dispatchEvent(new Event("watchlist-changed"));
  return getWatchlist();
};

export const removeFromWatchlist = (symbol) => {
  const list = getWatchlist().filter((s) => s !== symbol.toUpperCase().replace(".NS", ""));
  localStorage.setItem(WL_KEY, JSON.stringify(list));
  window.dispatchEvent(new Event("watchlist-changed"));
  return list;
};

export const isInWatchlist = (symbol) => {
  return getWatchlist().includes(symbol.toUpperCase().replace(".NS", ""));
};

export const getAlerts = () => {
  try {
    return JSON.parse(localStorage.getItem(AL_KEY) || "[]");
  } catch {
    return [];
  }
};

export const addAlert = (alert) => {
  const list = getAlerts();
  const newAlert = {
    id: Date.now().toString(),
    symbol: alert.symbol.toUpperCase().replace(".NS", ""),
    condition: alert.condition, // "above" | "below"
    price: Number(alert.price),
    note: alert.note || "",
    createdAt: new Date().toISOString(),
    triggered: false,
  };
  list.unshift(newAlert);
  localStorage.setItem(AL_KEY, JSON.stringify(list.slice(0, 50)));
  window.dispatchEvent(new Event("alerts-changed"));
  return getAlerts();
};

export const removeAlert = (id) => {
  const list = getAlerts().filter((a) => a.id !== id);
  localStorage.setItem(AL_KEY, JSON.stringify(list));
  window.dispatchEvent(new Event("alerts-changed"));
  return list;
};

export const markAlertTriggered = (id) => {
  const list = getAlerts().map((a) => a.id === id ? { ...a, triggered: true, triggeredAt: new Date().toISOString() } : a);
  localStorage.setItem(AL_KEY, JSON.stringify(list));
  return list;
};

export const clearTriggered = () => {
  const list = getAlerts().filter((a) => !a.triggered);
  localStorage.setItem(AL_KEY, JSON.stringify(list));
  return list;
};
