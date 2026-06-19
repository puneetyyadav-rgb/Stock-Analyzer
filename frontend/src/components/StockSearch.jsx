import React, { useEffect, useRef, useState } from "react";
import { Search, X, Loader2 } from "lucide-react";
import { searchStocks } from "../lib/api";

export default function StockSearch({ onSelect, initial = "" }) {
  const [q, setQ] = useState(initial);
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (!q || q.length < 1) {
      setResults([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await searchStocks(q);
        setResults(data.results || []);
        setOpen(true);
      } catch (e) {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [q]);

  const choose = (r) => {
    setQ(r.symbol);
    setOpen(false);
    onSelect(r.symbol);
  };

  const submitDirect = (e) => {
    e.preventDefault();
    if (q.trim()) {
      setOpen(false);
      onSelect(q.trim().toUpperCase());
    }
  };

  return (
    <div className="relative w-full">
      <form onSubmit={submitDirect} className="flex items-center gap-2 border border-zinc-800 bg-zinc-950 px-3 py-2.5 focus-within:border-blue-500 transition-colors">
        <Search size={16} className="text-zinc-500" />
        <input
          data-testid="stock-search-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Search NSE stocks (e.g. RELIANCE, TCS, INFY, HDFCBANK)…"
          className="flex-1 bg-transparent outline-none text-sm placeholder:text-zinc-600 font-mono uppercase tracking-wide"
        />
        {loading && <Loader2 size={14} className="animate-spin text-zinc-500" />}
        {q && !loading && (
          <button type="button" onClick={() => { setQ(""); setResults([]); }} className="text-zinc-500 hover:text-zinc-300" data-testid="search-clear">
            <X size={14} />
          </button>
        )}
      </form>
      {open && results.length > 0 && (
        <div data-testid="search-dropdown" className="absolute top-full left-0 right-0 mt-1 bg-zinc-950 border border-zinc-800 z-50 max-h-80 overflow-auto">
          {results.map((r) => (
            <button
              key={r.symbol}
              data-testid={`search-result-${r.symbol}`}
              onClick={() => choose(r)}
              className="w-full text-left px-3 py-2 hover:bg-zinc-900 border-b border-zinc-800/50 last:border-0 flex items-center justify-between"
            >
              <div>
                <div className="text-sm font-mono font-medium text-zinc-100">{r.symbol}</div>
                <div className="text-xs text-zinc-500 truncate max-w-md">{r.name}</div>
              </div>
              <span className="text-[10px] uppercase tracking-widest text-zinc-600">{r.exchange}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
