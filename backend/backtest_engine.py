"""
backtest_engine.py — the truth oracle. Replays the factor model over history, forms weekly decile
portfolios, and subtracts exact Indian frictions (execution_costs) to report REALIZED net-of-cost
performance. IC says "the signal correlates with returns"; this says "the signal makes money after STT
and slippage" — the only claim that matters.

Two strategies (India reality: no overnight retail equity short):
  • long_only  — long the top decile, benchmarked to Nifty (fully executable in cash).
  • long_short — long top / short bottom, the short leg priced with stock-FUTURES costs.

Survivorship-bias-free: the bhavcopy panel only contains names that actually traded each day.
No look-ahead: scores at date i use data ≤ i; P&L uses i → i+holding.
"""
import logging
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

import factor_service as fs
from execution_costs import roundtrip_cost_frac, market_impact_frac, gamma_for_liquidity

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "mode": "both",             # both | long_only | long_short
    "rebalance_days": 5,        # weekly
    "holding": 5,
    "deciles": 10,
    "aum": 1.0e7,               # ₹1 cr
    "min_adv_turnover_cr": 5.0, # liquidity filter
    "weighting": "equal",
    "participation_cap": 0.10,  # can't be >10% of ADV in one name → size-capped (slippage gate)
    "rf": 0.07,
    "corp_action_clip": 0.35,   # winsorize daily returns (unadjusted bhavcopy → split/bonus guard)
    "benchmark": True,
    "costs": True,
    "impact": True,
}


def _metrics(rets: np.ndarray, exit_dates: List[str], ppy: float, rf: float) -> Dict[str, Any]:
    rets = np.asarray(rets, dtype=float)
    if len(rets) == 0:
        return {"available": False}
    eq = np.cumprod(1.0 + rets)
    yrs = len(rets) / ppy
    cagr = eq[-1] ** (1.0 / yrs) - 1.0 if yrs > 0 and eq[-1] > 0 else float("nan")
    vol = float(rets.std(ddof=1)) * np.sqrt(ppy) if len(rets) > 1 else 0.0
    sharpe = (float(rets.mean()) * ppy - rf) / vol if vol > 0 else 0.0
    downside = rets[rets < 0]
    dstd = float(downside.std(ddof=1)) * np.sqrt(ppy) if len(downside) > 1 else 0.0
    sortino = (float(rets.mean()) * ppy - rf) / dstd if dstd > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    maxdd = float(((eq - peak) / peak).min())
    calmar = cagr / abs(maxdd) if maxdd < 0 and np.isfinite(cagr) else float("nan")
    return {
        "available": True,
        "cagrPct": round(cagr * 100, 2), "volPct": round(vol * 100, 2),
        "sharpe": round(sharpe, 2), "sortino": round(sortino, 2),
        "maxDDPct": round(maxdd * 100, 2), "calmar": round(calmar, 2) if np.isfinite(calmar) else None,
        "hitRate": round(float((rets > 0).mean()), 3), "periods": len(rets),
        "curve": [{"date": d, "value": round(float(v), 4)} for d, v in zip(exit_dates, eq)],
    }


def _leg(names, prices, fwd_ret, adv_sh, dvol, turn_rank, w, aum, instrument, cap, apply_impact):
    """Weighted leg return under three cost regimes: (gross, after_txn, after_all, capped_count)."""
    gross = txn = allc = 0.0
    capped = 0
    sign = 1.0 if instrument == "delivery" else -1.0     # long vs short
    for nm in names:
        px, ar = prices.get(nm, np.nan), fwd_ret.get(nm, np.nan)
        adv = adv_sh.get(nm, 0.0)
        if not (np.isfinite(px) and px > 0 and np.isfinite(ar)):
            continue
        order_sh = w * aum / px
        part = order_sh / adv if adv > 0 else np.inf
        eff_w = w
        if part > cap:                                   # slippage gate → size-cap, cash fills the rest
            eff_w = (cap * adv * px) / aum if adv > 0 else 0.0
            capped += 1
        if eff_w <= 0:
            continue
        g = sign * ar
        txn_c = roundtrip_cost_frac(eff_w * aum, instrument) if instrument else 0.0
        imp = (2.0 * market_impact_frac(eff_w * aum / px, adv, dvol.get(nm, 0.0),
                                        gamma_for_liquidity(int(turn_rank.get(nm, 9999))))) if apply_impact else 0.0
        gross += eff_w * g
        txn += eff_w * (g - txn_c)
        allc += eff_w * (g - txn_c - imp)
    return gross, txn, allc, capped


def run_backtest(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = {**_DEFAULTS, **(config or {})}
    panel = fs.load_panel()
    if panel.empty:
        return {"available": False, "reason": "no bhavcopy history — run backfill_bhavcopy.py"}

    wc = fs._wide(panel, "close")
    wt = fs._wide(panel, "turnover")            # ₹ lakhs
    wv = fs._wide(panel, "volume")              # shares
    wd = fs._wide(panel, "delivPct")
    n = len(wc)
    warnings = []
    if n < 150:
        warnings.append(f"short history ({n} days) — results are noisy; backfill more for a robust Sharpe")

    rets = wc.pct_change()
    clip = cfg["corp_action_clip"]
    corp_flagged = int((rets.abs() > clip).sum().sum())
    rets_w = rets.clip(-clip, clip)
    wr = 1.0 + rets_w                           # winsorized growth factors

    h, step, aum = cfg["holding"], cfg["rebalance_days"], cfg["aum"]
    min_turn_lakh = cfg["min_adv_turnover_cr"] * 100.0   # ₹cr → lakhs
    cap, nd = cfg["participation_cap"], cfg["deciles"]
    do_costs, do_impact = cfg["costs"], cfg["impact"]

    start = 125                                 # need momentum lookback
    idxs = list(range(start, n - h, step))
    if len(idxs) < 5:
        return {"available": False, "reason": f"insufficient history for backtest ({len(idxs)} rebalances)"}

    lo_g, lo_t, lo_a = [], [], []               # long-only gross / after-txn / after-all
    ls_a = []                                   # long/short net
    nifty_rets, exit_dates = [], []
    decile_fwd = {d: [] for d in range(1, nd + 1)}
    prev_top = None
    turnover_track, capped_total = [], 0

    for i in idxs:
        comp = fs._score_frame(fs._factors_at(wc, wd, wt, i)).get("composite")
        if comp is None:
            continue
        adv_turn = wt.iloc[i - 19:i + 1].mean()          # ₹ lakhs, per symbol
        tradable = comp.dropna().index.intersection(adv_turn[adv_turn >= min_turn_lakh].index)
        if len(tradable) < nd * 2:
            continue
        comp = comp[tradable].sort_values()
        m = len(comp)
        dsz = m // nd
        prices = wc.iloc[i].to_dict()
        adv_sh = wv.iloc[i - 19:i + 1].mean().to_dict()
        dvol = rets_w.iloc[i - 20:i].std().to_dict()
        turn_rank = adv_turn.rank(ascending=False).to_dict()
        fwd = (wr.iloc[i + 1:i + 1 + h].prod() - 1.0).to_dict()   # winsorized holding return

        # decile-spread diagnostic (gross)
        for d in range(nd):
            seg = comp.index[d * dsz:(d + 1) * dsz] if d < nd - 1 else comp.index[d * dsz:]
            vals = [fwd.get(s) for s in seg if np.isfinite(fwd.get(s, np.nan))]
            if vals:
                decile_fwd[d + 1].append(float(np.mean(vals)))

        bottom = comp.index[:dsz]
        top = comp.index[-dsz:]
        w = 1.0 / dsz

        g, t, a, cap_l = _leg(top, prices, fwd, adv_sh, dvol, turn_rank, w, aum, "delivery",
                              cap, do_impact)
        lo_g.append(g); lo_t.append(t if do_costs else g); lo_a.append(a if do_costs else g)
        capped_total += cap_l

        if cfg["mode"] in ("both", "long_short"):
            _, _, sa, cap_s = _leg(bottom, prices, fwd, adv_sh, dvol, turn_rank, w, aum, "futures",
                                   cap, do_impact)
            ls_a.append((a if do_costs else g) + sa)     # long net + short net
            capped_total += cap_s

        # turnover = fraction of top-decile names replaced since last rebalance
        if prev_top is not None:
            turnover_track.append(1.0 - len(set(top) & set(prev_top)) / max(1, len(top)))
        prev_top = list(top)
        exit_dates.append(str(wc.index[i + h].date()))

    ppy = 252.0 / step
    out: Dict[str, Any] = {
        "available": True,
        "config": {k: cfg[k] for k in ("mode", "rebalance_days", "holding", "deciles", "aum",
                                       "min_adv_turnover_cr", "participation_cap", "costs", "impact")},
        "dateRange": {"start": str(wc.index[0].date()), "end": str(wc.index[-1].date()),
                      "tradingDays": n, "rebalances": len(exit_dates)},
        "warnings": warnings,
        "corpActionFlagged": corp_flagged,
        "droppedIlliquid": capped_total,
        "avgTurnover": round(float(np.mean(turnover_track)), 3) if turnover_track else None,
        "decileSpread": [{"decile": d, "meanFwdRetPct": round(float(np.mean(v)) * 100, 3)}
                         for d, v in decile_fwd.items() if v],
        "costWaterfall": {
            "grossCagrPct": _metrics(lo_g, exit_dates, ppy, cfg["rf"]).get("cagrPct"),
            "afterTxnCagrPct": _metrics(lo_t, exit_dates, ppy, cfg["rf"]).get("cagrPct"),
            "afterImpactCagrPct": _metrics(lo_a, exit_dates, ppy, cfg["rf"]).get("cagrPct"),
        },
    }
    if cfg["mode"] in ("both", "long_only"):
        out["longOnly"] = _metrics(lo_a, exit_dates, ppy, cfg["rf"])
    if cfg["mode"] in ("both", "long_short"):
        out["longShort"] = _metrics(ls_a, exit_dates, ppy, cfg["rf"])

    # Nifty benchmark (best-effort; skipped offline/in self-check)
    if cfg["benchmark"]:
        try:
            import yfinance as yf
            ndf = yf.Ticker("^NSEI").history(start=str(wc.index[0].date()), interval="1d", auto_adjust=True)
            nclose = ndf["Close"]
            nclose.index = nclose.index.tz_localize(None) if nclose.index.tz else nclose.index
            aligned = nclose.reindex(wc.index, method="ffill")
            for i in idxs:
                if i + h < len(aligned):
                    nifty_rets.append(float(aligned.iloc[i + h] / aligned.iloc[i] - 1.0))
            if len(nifty_rets) == len(exit_dates) and nifty_rets:
                out["nifty"] = _metrics(nifty_rets, exit_dates, ppy, cfg["rf"])
                if out.get("longOnly", {}).get("available"):
                    lo = np.array(lo_a); nf = np.array(nifty_rets)
                    beta = float(np.cov(lo, nf)[0, 1] / np.var(nf)) if np.var(nf) > 0 else None
                    out["longOnly"]["vsNifty"] = {
                        "excessCagrPct": round((out["longOnly"]["cagrPct"] or 0) - (out["nifty"]["cagrPct"] or 0), 2),
                        "beta": round(beta, 2) if beta is not None else None}
        except Exception as e:
            logger.info(f"nifty benchmark skipped: {e}")

    return out


if __name__ == "__main__":  # synthetic self-check with a KNOWN embedded alpha (no network)
    _rng = np.random.default_rng(7)
    _dates = pd.date_range("2025-01-01", periods=320, freq="B")
    _rows = []
    _N = 40
    for s in range(_N):
        drift = (s - _N / 2) / (_N / 2) * 0.0025          # symbol index → linear drift (the hidden alpha)
        px = 100 * np.exp(np.cumsum(_rng.normal(drift, 0.012, len(_dates))))
        vol_sh = 50_000 + s * 2_000                        # low float → slippage gate will bite at ₹1cr AUM
        turn = px * vol_sh / 1e5                            # ₹ lakhs (all above ₹5cr filter here)
        for j, dt in enumerate(_dates):
            _rows.append((f"S{s:02d}", dt, px[j], vol_sh, np.clip(_rng.normal(55, 8), 5, 95), turn[j]))
    _panel = pd.DataFrame(_rows, columns=["symbol", "date", "close", "volume", "delivPct", "turnover"])
    fs.load_panel = lambda: _panel                         # monkeypatch → offline

    r = run_backtest({"mode": "both", "benchmark": False, "min_adv_turnover_cr": 0.5})
    assert r["available"], r
    ds = {d["decile"]: d["meanFwdRetPct"] for d in r["decileSpread"]}
    assert ds[max(ds)] > ds[min(ds)], ("top decile must beat bottom (alpha is real)", ds)
    cw = r["costWaterfall"]
    assert cw["grossCagrPct"] > cw["afterImpactCagrPct"], ("costs must reduce return", cw)
    assert r["droppedIlliquid"] > 0, "slippage gate should cap illiquid names at ₹1cr AUM"
    assert r["longOnly"]["available"] and r["longShort"]["available"]
    r2 = run_backtest({"mode": "both", "benchmark": False, "min_adv_turnover_cr": 0.5})
    assert r2["longOnly"]["sharpe"] == r["longOnly"]["sharpe"], "must be deterministic"
    print("ok backtest_engine  rebalances=%d  LO net Sharpe=%.2f  L/S net Sharpe=%.2f" % (
        r["dateRange"]["rebalances"], r["longOnly"]["sharpe"], r["longShort"]["sharpe"]))
    print("   decile spread D1..D10 (%%): ", [ds[k] for k in sorted(ds)])
    print("   cost waterfall gross->net CAGR: %.1f%% -> %.1f%% -> %.1f%%  | dropped=%d corp=%d" % (
        cw["grossCagrPct"], cw["afterTxnCagrPct"], cw["afterImpactCagrPct"],
        r["droppedIlliquid"], r["corpActionFlagged"]))
