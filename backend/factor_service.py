"""
factor_service.py — cross-sectional multi-factor equity model over the accumulated NSE bhavcopy.

Once enough daily bhavcopy CSVs accrue (see bhavcopy_service), they form a whole-market panel.
This turns that panel into an institutional factor model: per-name factor exposures, winsorized
cross-sectional z-scores, a composite alpha, universe ranking, and walk-forward IC validation.

Every factor is oriented so HIGHER = more bullish/quality. History grows automatically
(compute_technicals downloads today's bhavcopy); use backfill_bhavcopy.py to seed the past.
"""
import os
import logging
from functools import lru_cache
from typing import Dict, Any

import numpy as np
import pandas as pd

import bhavcopy_service as bhav
from quant_service import _rank_corr

logger = logging.getLogger(__name__)

# Composite weights (renormalized over whatever factors have enough history).
_WEIGHTS = {
    "mom_120": 0.22, "mom_60": 0.18, "reversal_5": 0.10,
    "deliv_trend": 0.16, "liquidity": 0.10, "low_vol": 0.10, "turnover_shock": 0.14,
}
_MIN_DAYS = 30          # below this, no factor model
_IC_MIN_NAMES = 5       # min overlapping names to compute a cross-sectional IC point


def _list_files():
    """(path, date) for every bhavcopy CSV across both dirs, de-duped by date, sorted ascending."""
    seen = {}
    for folder in (bhav._DIR, bhav._ALT_DIR):
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if f.startswith("sec_bhavdata_full_") and f.endswith("bhav.csv"):
                d = bhav._date_from_fname(f)
                if d:
                    seen.setdefault(d, os.path.join(folder, f))
    return sorted(((seen[d], d) for d in seen), key=lambda x: x[1])


def _signature():
    return tuple((p, os.path.getmtime(p)) for p, _ in _list_files())


@lru_cache(maxsize=2)
def _load_cached(_sig):
    frames = []
    for path, d in _list_files():
        try:
            df = pd.read_csv(path, skipinitialspace=True)
            df.columns = df.columns.str.strip()
            if "SYMBOL" not in df.columns or "CLOSE_PRICE" not in df.columns:
                continue                     # not a real bhavcopy (e.g. HTML error page) → skip
            df = df[df["SERIES"].astype(str).str.strip() == "EQ"]
            frames.append(pd.DataFrame({
                "symbol": df["SYMBOL"].astype(str).str.strip(),
                "date": pd.Timestamp(d),
                "close": pd.to_numeric(df["CLOSE_PRICE"], errors="coerce"),
                "volume": pd.to_numeric(df["TTL_TRD_QNTY"], errors="coerce"),
                "delivPct": pd.to_numeric(df["DELIV_PER"], errors="coerce"),
                "turnover": pd.to_numeric(df["TURNOVER_LACS"], errors="coerce"),
            }))
        except Exception as e:
            logger.warning(f"panel skip {path}: {e}")
    if not frames:
        return pd.DataFrame(columns=["symbol", "date", "close", "volume", "delivPct", "turnover"])
    return pd.concat(frames, ignore_index=True)


def load_panel() -> pd.DataFrame:
    """Long panel [symbol, date, close, volume, delivPct, turnover] from all accumulated bhavcopy CSVs."""
    return _load_cached(_signature())


def _wide(panel: pd.DataFrame, col: str) -> pd.DataFrame:
    return panel.pivot_table(index="date", columns="symbol", values=col).sort_index()


def _winsor_z(s: pd.Series) -> pd.Series:
    """Winsorize to 1/99 pctile then standardize. Robust to the bhavcopy's penny-stock outliers."""
    s = s.astype(float)
    lo, hi = s.quantile(0.01), s.quantile(0.99)
    s = s.clip(lo, hi)
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and sd > 0 else s * 0.0


def _factors_at(wc: pd.DataFrame, wd: pd.DataFrame, wt: pd.DataFrame, i: int) -> pd.DataFrame:
    """Raw factor values per symbol at date-row i (higher = more bullish). Factors drop out if short on history."""
    F = {}

    def ret(a, b):                       # close[i-a] / close[i-b] - 1
        return (wc.iloc[i - a] / wc.iloc[i - b] - 1.0) if i - b >= 0 else None

    m120 = ret(5, 125)                   # 12-1 style: 120d return skipping the last 5d
    if m120 is not None:
        F["mom_120"] = m120
    m60 = ret(5, 65)
    if m60 is not None:
        F["mom_60"] = m60
    if i - 5 >= 0:
        F["reversal_5"] = -(wc.iloc[i] / wc.iloc[i - 5] - 1.0)         # short-term reversal (sign-flipped)
    if i - 20 >= 0:
        F["deliv_trend"] = wd.iloc[i - 19:i + 1].mean()               # accumulation quality
        F["liquidity"] = np.log1p(wt.iloc[i - 19:i + 1].mean())       # institutional tradability
        F["turnover_shock"] = wt.iloc[i] / wt.iloc[i - 19:i + 1].mean()
    if i - 60 >= 0:
        F["low_vol"] = -wc.iloc[i - 60:i + 1].pct_change().std()      # low-vol anomaly
    return pd.DataFrame(F)


def _score_frame(fdf: pd.DataFrame) -> pd.DataFrame:
    """Z-score each factor cross-sectionally and build the weighted composite."""
    z = pd.DataFrame({c: _winsor_z(fdf[c]) for c in fdf.columns})
    w = {c: _WEIGHTS[c] for c in z.columns if c in _WEIGHTS}
    wsum = sum(w.values()) or 1.0
    z["composite"] = sum(z[c] * w[c] for c in w) / wsum
    return z


def _latest_scores():
    """(z-score DataFrame at the latest date, asOf date, historyDays) or (None, ...) if too short."""
    panel = load_panel()
    if panel.empty:
        return None, None, 0
    wc, wd, wt = _wide(panel, "close"), _wide(panel, "delivPct"), _wide(panel, "turnover")
    n = len(wc)
    if n < _MIN_DAYS:
        return None, (wc.index[-1].date() if n else None), n
    z = _score_frame(_factors_at(wc, wd, wt, n - 1))
    return z, wc.index[-1].date(), n


def get_factor_profile(symbol: str) -> Dict[str, Any]:
    """Per-name factor exposures, composite, and universe percentile/decile at the latest date."""
    clean = symbol.replace(".NS", "").replace(".BO", "").upper()
    z, as_of, n = _latest_scores()
    if z is None:
        return {"available": False, "reason": f"insufficient bhavcopy history ({n} days; need {_MIN_DAYS})"}
    if clean not in z.index or pd.isna(z.loc[clean, "composite"]):
        return {"available": False, "reason": "symbol not in universe / factors unavailable"}
    comp = z["composite"].dropna()
    pctile = round(float((comp < comp[clean]).mean()) * 100.0, 1)
    return {
        "available": True,
        "asOf": str(as_of),
        "universeSize": int(len(comp)),
        "composite": round(float(comp[clean]), 3),
        "percentile": pctile,
        "decile": int(min(9, int(pctile // 10)) + 1),
        "factors": {c: round(float(z.loc[clean, c]), 3) for c in z.columns
                    if c != "composite" and pd.notna(z.loc[clean, c])},
        "historyDays": int(n),
    }


def get_factor_leaders(n: int = 15) -> Dict[str, Any]:
    """Top/bottom composite-alpha names across the whole universe."""
    z, as_of, days = _latest_scores()
    if z is None:
        return {"available": False, "reason": f"insufficient bhavcopy history ({days} days)"}
    comp = z["composite"].dropna().sort_values(ascending=False)
    fmt = lambda s: [{"symbol": k, "composite": round(float(v), 3)} for k, v in s.items()]
    return {"available": True, "asOf": str(as_of), "universeSize": int(len(comp)),
            "top": fmt(comp.head(n)), "bottom": fmt(comp.tail(n)[::-1])}


def factor_ic(step: int = 5, fwd: int = 5, max_points: int = 40) -> Dict[str, Any]:
    """
    Walk-forward Information Coefficient of the composite: rank-corr(composite_t, fwd-return_t) over
    sampled historical dates. meanIC>0 with hitRate>0.5 = the composite has real cross-sectional edge.
    """
    panel = load_panel()
    if panel.empty:
        return {"available": False, "reason": "no history"}
    wc, wd, wt = _wide(panel, "close"), _wide(panel, "delivPct"), _wide(panel, "turnover")
    n = len(wc)
    idxs = list(range(65, n - fwd, step))[-max_points:]        # need >=65d for mom_60
    ics = []
    for i in idxs:
        fdf = _factors_at(wc, wd, wt, i)
        if fdf.empty:
            continue
        comp = _score_frame(fdf)["composite"]
        fwd_ret = wc.iloc[i + fwd] / wc.iloc[i] - 1.0
        common = comp.dropna().index.intersection(fwd_ret.dropna().index)
        if len(common) < _IC_MIN_NAMES:
            continue
        ics.append(_rank_corr(comp[common].values, fwd_ret[common].values))
    if not ics:
        return {"available": False, "reason": "insufficient history for IC"}
    return {"available": True, "meanIC": round(float(np.mean(ics)), 4),
            "hitRate": round(float(np.mean([1.0 if x > 0 else 0.0 for x in ics])), 3),
            "samples": len(ics), "fwdDays": fwd}


if __name__ == "__main__":  # synthetic-panel self-check (no files/network)
    _rng = np.random.default_rng(0)
    _dates = pd.date_range("2026-01-01", periods=150, freq="B")
    _syms = ["TREND", "FALL", "FLAT", "A", "B", "C", "D", "LIQ"]
    _rows = []
    for s in _syms:
        drift = 0.004 if s == "TREND" else -0.004 if s == "FALL" else 0.0
        px = 100 * np.exp(np.cumsum(_rng.normal(drift, 0.01, 150)))
        vol = _rng.random(150) * 1e6
        deliv = np.clip(_rng.normal(50, 10, 150), 5, 95)
        turn = px * vol / 1e5 * (10 if s == "LIQ" else 1)
        for i, dt in enumerate(_dates):
            _rows.append((s, dt, px[i], vol[i], deliv[i], turn[i]))
    _panel = pd.DataFrame(_rows, columns=["symbol", "date", "close", "volume", "delivPct", "turnover"])
    globals()["load_panel"] = lambda: _panel     # monkeypatch loader → offline

    _prof = get_factor_profile("TREND")
    assert _prof["available"], _prof
    assert _prof["factors"].get("mom_60", 0) > 0.5, ("uptrend → high momentum z", _prof)
    assert _prof["decile"] >= 7, ("strong trender should rank top", _prof)
    _fall = get_factor_profile("FALL")
    assert _fall["factors"].get("mom_60", 0) < -0.5, ("downtrend → negative momentum z", _fall)
    _lead = get_factor_leaders(3)
    assert _lead["top"][0]["symbol"] == "TREND", _lead                 # strong uptrend tops the alpha
    assert _fall["percentile"] < 50, ("downtrend should rank below median", _fall)
    _ic = factor_ic()
    assert _ic["available"] and np.isfinite(_ic["meanIC"]), _ic
    print("ok factor_service  TREND decile=%d  mom_60z=%.2f  |  leaders top=%s  |  meanIC=%.4f (n=%d)" % (
        _prof["decile"], _prof["factors"]["mom_60"], _lead["top"][0]["symbol"], _ic["meanIC"], _ic["samples"]))
