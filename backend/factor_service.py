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
from quant_service import _rank_corr, walk_forward_validate

logger = logging.getLogger(__name__)

# Composite weights (renormalized over whatever factors have enough history).
_WEIGHTS = {
    "mom_120": 0.22, "mom_60": 0.18, "reversal_5": 0.10,
    "deliv_trend": 0.16, "liquidity": 0.10, "low_vol": 0.10, "turnover_shock": 0.14,
}
_MIN_DAYS = 30          # below this, no factor model
_IC_MIN_NAMES = 5       # min overlapping names to compute a cross-sectional IC point
_DEFAULT_MIN_ADV_TURNOVER_CR = float(os.environ.get("FACTOR_MIN_ADV_TURNOVER_CR", "5.0"))
_SECTOR_TILT_K = float(os.environ.get("FACTOR_SECTOR_TILT_K", "0.025"))
_SECTOR_MAP_REFRESH_LIMIT = int(os.environ.get("FACTOR_SECTOR_MAP_REFRESH_LIMIT", "40"))
_SECTOR_TILT_ENABLED = os.environ.get("FACTOR_SECTOR_TILT_ENABLED", "true").lower() != "false"


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


def _clean_symbol(symbol: str) -> str:
    return str(symbol or "").replace(".NS", "").replace(".BO", "").upper().strip()


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


def _apply_sector_overlay(z: pd.DataFrame, adv_turnover_lakh: pd.Series) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Attach sector-adjusted composite using cached symbol sectors and sector-index momentum."""
    z = z.copy()
    z["sectorAdjustedComposite"] = z["composite"]
    z["sectorMultiplier"] = 1.0
    if not _SECTOR_TILT_ENABLED or z.empty:
        return z, {"available": False, "reason": "disabled or empty universe"}
    try:
        import sector_map
        import sector_service as sec

        symbols = z["composite"].dropna().index.tolist()
        symbols = sorted(symbols, key=lambda s: float(adv_turnover_lakh.get(s) or 0.0), reverse=True)
        sector_by_symbol = sector_map.get_sector_map(symbols, max_refresh=_SECTOR_MAP_REFRESH_LIMIT)
        momentum = sec.sector_momentum()
        sector_mom = momentum.get("sectors", {}) if momentum.get("available") else {}
        tilted = 0
        for sym in z.index:
            sector = sector_by_symbol.get(sym)
            excess = (sector_mom.get(sector) or {}).get("excess_1m") if sector else None
            if excess is None or pd.isna(excess):
                continue
            mult = float(np.clip(1.0 + _SECTOR_TILT_K * float(excess), 0.5, 1.5))
            z.loc[sym, "sector"] = sector
            z.loc[sym, "sectorExcess1m"] = float(excess)
            z.loc[sym, "sectorMultiplier"] = mult
            z.loc[sym, "sectorAdjustedComposite"] = float(z.loc[sym, "composite"]) * mult
            if abs(mult - 1.0) > 1e-9:
                tilted += 1
        return z, {
            "available": bool(sector_mom),
            "mappedSymbols": int(len(sector_by_symbol)),
            "tiltedSymbols": int(tilted),
            "k": _SECTOR_TILT_K,
            "refreshLimit": _SECTOR_MAP_REFRESH_LIMIT,
            "benchmark": momentum.get("benchmark"),
        }
    except Exception as exc:
        logger.warning("sector overlay skipped: %s", exc)
        return z, {"available": False, "reason": str(exc)}


def _latest_scores(min_adv_turnover_cr: float = _DEFAULT_MIN_ADV_TURNOVER_CR):
    """Latest factor scores after the live tradability filter."""
    panel = load_panel()
    if panel.empty:
        return None, None, 0, {}
    wc, wd, wt = _wide(panel, "close"), _wide(panel, "delivPct"), _wide(panel, "turnover")
    n = len(wc)
    if n < _MIN_DAYS:
        return None, (wc.index[-1].date() if n else None), n, {}
    z_all = _score_frame(_factors_at(wc, wd, wt, n - 1))
    adv_turn = wt.iloc[max(0, n - 20):n].mean()
    min_turn_lakh = max(0.0, float(min_adv_turnover_cr or 0.0)) * 100.0
    if min_turn_lakh > 0:
        eligible = adv_turn[adv_turn >= min_turn_lakh].dropna().index
        z = z_all.loc[z_all.index.intersection(eligible)].copy()
    else:
        z = z_all.copy()
    z, sector_overlay = _apply_sector_overlay(z, adv_turn)
    meta = {
        "totalUniverse": int(len(z_all["composite"].dropna())) if "composite" in z_all else 0,
        "tradableUniverse": int(len(z["composite"].dropna())) if "composite" in z else 0,
        "liquidityFilter": {
            "minAdvTurnoverCr": round(float(min_adv_turnover_cr or 0.0), 2),
            "minAdvTurnoverLakh": round(min_turn_lakh, 2),
        },
        "advTurnoverLakh": adv_turn,
        "sectorOverlay": sector_overlay,
    }
    return z, wc.index[-1].date(), n, meta


def _ranking_col(z: pd.DataFrame) -> str:
    return "sectorAdjustedComposite" if "sectorAdjustedComposite" in z.columns else "composite"


def _adv_cr(meta: Dict[str, Any], symbol: str):
    adv = (meta.get("advTurnoverLakh") if meta else None)
    try:
        val = adv.get(symbol) if adv is not None else None
        return round(float(val) / 100.0, 2) if val is not None and pd.notna(val) else None
    except Exception:
        return None


def _sector_payload(z: pd.DataFrame, symbol: str) -> Dict[str, Any]:
    if symbol not in z.index:
        return {}
    out = {
        "sectorMultiplier": round(float(z.loc[symbol].get("sectorMultiplier", 1.0)), 3),
    }
    sector = z.loc[symbol].get("sector")
    excess = z.loc[symbol].get("sectorExcess1m")
    if isinstance(sector, str) and sector:
        out["sector"] = sector
    if excess is not None and pd.notna(excess):
        out["sectorExcess1m"] = round(float(excess), 2)
    return out


def get_factor_profile(symbol: str, min_adv_turnover_cr: float = _DEFAULT_MIN_ADV_TURNOVER_CR) -> Dict[str, Any]:
    """Per-name factor exposures, composite, and universe percentile/decile at the latest date."""
    clean = _clean_symbol(symbol)
    z, as_of, n, meta = _latest_scores(min_adv_turnover_cr)
    if z is None:
        return {"available": False, "reason": f"insufficient bhavcopy history ({n} days; need {_MIN_DAYS})"}
    adv_cr = _adv_cr(meta, clean)
    min_cr = (meta.get("liquidityFilter") or {}).get("minAdvTurnoverCr", min_adv_turnover_cr)
    if adv_cr is not None and adv_cr < float(min_cr or 0.0):
        return {
            "available": False,
            "reason": f"below liquidity filter ({adv_cr} Cr ADV < {min_cr} Cr)",
            "asOf": str(as_of),
            "advTurnoverCr": adv_cr,
            "liquidityFilter": meta.get("liquidityFilter"),
            "totalUniverse": meta.get("totalUniverse"),
            "tradableUniverse": meta.get("tradableUniverse"),
        }
    rank_col = _ranking_col(z)
    if clean not in z.index or pd.isna(z.loc[clean, rank_col]):
        return {"available": False, "reason": "symbol not in universe / factors unavailable"}
    comp = z[rank_col].dropna()
    pctile = round(float((comp < comp[clean]).mean()) * 100.0, 1)
    return {
        "available": True,
        "asOf": str(as_of),
        "universeSize": int(len(comp)),
        "tradableUniverse": meta.get("tradableUniverse"),
        "totalUniverse": meta.get("totalUniverse"),
        "liquidityFilter": meta.get("liquidityFilter"),
        "advTurnoverCr": adv_cr,
        "composite": round(float(comp[clean]), 3),
        "rawComposite": round(float(z.loc[clean, "composite"]), 3),
        "sectorAdjustedComposite": round(float(z.loc[clean, rank_col]), 3),
        "percentile": pctile,
        "decile": int(min(9, int(pctile // 10)) + 1),
        "factors": {c: round(float(z.loc[clean, c]), 3) for c in z.columns
                    if c in _WEIGHTS and pd.notna(z.loc[clean, c])},
        "sectorOverlay": {**(meta.get("sectorOverlay") or {}), **_sector_payload(z, clean)},
        "historyDays": int(n),
    }


def get_factor_leaders(n: int = 15, min_adv_turnover_cr: float = _DEFAULT_MIN_ADV_TURNOVER_CR) -> Dict[str, Any]:
    """Top/bottom composite-alpha names across the whole universe."""
    z, as_of, days, meta = _latest_scores(min_adv_turnover_cr)
    if z is None:
        return {"available": False, "reason": f"insufficient bhavcopy history ({days} days)"}
    rank_col = _ranking_col(z)
    comp = z[rank_col].dropna().sort_values(ascending=False)

    def fmt(s):
        rows = []
        for k, v in s.items():
            row = {
                "symbol": k,
                "composite": round(float(v), 3),
                "rawComposite": round(float(z.loc[k, "composite"]), 3),
                "advTurnoverCr": _adv_cr(meta, k),
            }
            sector_info = _sector_payload(z, k)
            if sector_info:
                row.update(sector_info)
            rows.append(row)
        return rows

    return {
        "available": True,
        "asOf": str(as_of),
        "universeSize": int(len(comp)),
        "tradableUniverse": meta.get("tradableUniverse"),
        "totalUniverse": meta.get("totalUniverse"),
        "liquidityFilter": meta.get("liquidityFilter"),
        "sectorOverlay": meta.get("sectorOverlay"),
        "top": fmt(comp.head(n)),
        "bottom": fmt(comp.tail(n)[::-1]),
    }


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


def param_validation(symbol: str | None = None, max_symbols: int = 20, train: int = 252,
                     test: int = 42, step: int = 42, fwd_days: int = 5,
                     min_adv_turnover_cr: float = _DEFAULT_MIN_ADV_TURNOVER_CR) -> Dict[str, Any]:
    """Out-of-sample validation of quant-deck score params on bhavcopy close history."""
    panel = load_panel()
    if panel.empty:
        return {"available": False, "reason": "no bhavcopy history"}
    wc = _wide(panel, "close")
    wv = _wide(panel, "volume")
    wt = _wide(panel, "turnover")
    min_turn_lakh = max(0.0, float(min_adv_turnover_cr or 0.0)) * 100.0
    if symbol:
        symbols = [_clean_symbol(symbol)]
    else:
        adv_turn = wt.iloc[max(0, len(wt) - 20):].mean().dropna()
        symbols = adv_turn[adv_turn >= min_turn_lakh].sort_values(ascending=False).head(max_symbols).index.tolist()
    results = []
    for clean in symbols:
        if clean not in wc.columns:
            continue
        data = pd.DataFrame({"close": wc[clean], "volume": wv[clean] if clean in wv.columns else np.nan}).dropna(subset=["close"])
        if len(data) < train + test + fwd_days:
            continue
        res = walk_forward_validate(
            data["close"].tolist(),
            data["volume"].tolist() if data["volume"].notna().any() else None,
            train=train,
            test=test,
            step=step,
            fwd_days=fwd_days,
        )
        if res.get("available"):
            results.append({
                "symbol": clean,
                "meanIS_IC": res.get("meanIS_IC"),
                "meanOOS_IC": res.get("meanOOS_IC"),
                "meanOOSHitRate": res.get("meanOOSHitRate"),
                "isMinusOosDecay": res.get("isMinusOosDecay"),
                "overfitWarning": res.get("overfitWarning"),
                "samples": res.get("samples"),
                "windows": res.get("windows", [])[-6:],
            })

    if not results:
        return {"available": False, "reason": "insufficient history for selected universe"}
    oos = [r["meanOOS_IC"] for r in results if r.get("meanOOS_IC") is not None]
    ins = [r["meanIS_IC"] for r in results if r.get("meanIS_IC") is not None]
    hit = [r["meanOOSHitRate"] for r in results if r.get("meanOOSHitRate") is not None]
    decay = [r["isMinusOosDecay"] for r in results if r.get("isMinusOosDecay") is not None]
    return {
        "available": True,
        "asOf": str(wc.index[-1].date()) if len(wc) else None,
        "symbolsValidated": len(results),
        "requestedSymbol": _clean_symbol(symbol) if symbol else None,
        "liquidityFilter": {
            "minAdvTurnoverCr": round(float(min_adv_turnover_cr or 0.0), 2),
            "minAdvTurnoverLakh": round(min_turn_lakh, 2),
        },
        "trainBars": int(train),
        "testBars": int(test),
        "stepBars": int(step),
        "fwdDays": int(fwd_days),
        "meanIS_IC": round(float(np.mean(ins)), 4) if ins else None,
        "meanOOS_IC": round(float(np.mean(oos)), 4) if oos else None,
        "meanOOSHitRate": round(float(np.mean(hit)), 3) if hit else None,
        "isMinusOosDecay": round(float(np.mean(decay)), 4) if decay else None,
        "overfitWarnings": int(sum(1 for r in results if r.get("overfitWarning"))),
        "results": results,
    }


if __name__ == "__main__":  # synthetic-panel self-check (no files/network)
    _rng = np.random.default_rng(0)
    _dates = pd.date_range("2026-01-01", periods=150, freq="B")
    _syms = ["TREND", "FALL", "FLAT", "A", "B", "C", "D", "LIQ", "ILLIQ"]
    _rows = []
    for s in _syms:
        drift = 0.004 if s == "TREND" else -0.004 if s == "FALL" else 0.0
        px = 100 * np.exp(np.cumsum(_rng.normal(drift, 0.01, 150)))
        vol = (_rng.random(150) * 1e6 + 1e6) if s != "ILLIQ" else (_rng.random(150) * 1000 + 1000)
        deliv = np.clip(_rng.normal(50, 10, 150), 5, 95)
        turn = px * vol / 1e5 * (10 if s == "LIQ" else 1)
        for i, dt in enumerate(_dates):
            _rows.append((s, dt, px[i], vol[i], deliv[i], turn[i]))
    _panel = pd.DataFrame(_rows, columns=["symbol", "date", "close", "volume", "delivPct", "turnover"])
    globals()["load_panel"] = lambda: _panel     # monkeypatch loader → offline

    def _no_sector_overlay(z, _adv):
        z = z.copy()
        z["sectorAdjustedComposite"] = z["composite"]
        z["sectorMultiplier"] = 1.0
        return z, {"available": False, "reason": "self-check"}

    globals()["_apply_sector_overlay"] = _no_sector_overlay

    _prof = get_factor_profile("TREND")
    assert _prof["available"], _prof
    assert _prof["factors"].get("mom_60", 0) > 0.5, ("uptrend → high momentum z", _prof)
    assert _prof["decile"] >= 7, ("strong trender should rank top", _prof)
    _fall = get_factor_profile("FALL")
    assert _fall["factors"].get("mom_60", 0) < -0.5, ("downtrend → negative momentum z", _fall)
    _lead = get_factor_leaders(3)
    assert _lead["tradableUniverse"] < _lead["totalUniverse"], _lead
    assert not get_factor_profile("ILLIQ")["available"], "illiquid name should fail the live liquidity filter"
    assert all((row.get("advTurnoverCr") or 0) >= 5.0 for row in _lead["top"]), _lead
    assert _lead["top"][0]["symbol"] == "TREND", _lead                 # strong uptrend tops the alpha
    assert _fall["percentile"] < 50, ("downtrend should rank below median", _fall)
    _ic = factor_ic()
    assert _ic["available"] and np.isfinite(_ic["meanIC"]), _ic
    print("ok factor_service  TREND decile=%d  mom_60z=%.2f  |  leaders top=%s  |  meanIC=%.4f (n=%d)" % (
        _prof["decile"], _prof["factors"]["mom_60"], _lead["top"][0]["symbol"], _ic["meanIC"], _ic["samples"]))
