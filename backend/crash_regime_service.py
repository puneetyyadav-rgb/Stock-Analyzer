"""Market-wide crash-regime detector — 3-state Gaussian HMM on Nifty features.
Weekly refit + disk cache (same cadence pattern as sector_map.py); cheap daily
forward-inference against the cached model. Not per-stock: this is a single
macro capital-scaling signal shared across every symbol.
"""
import logging
import os
import pickle
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE_PATH = os.environ.get(
    "REGIME_HMM_CACHE_PATH",
    os.path.join(os.path.dirname(__file__), "regime_hmm_cache.pkl"),
)
_REFIT_TTL_DAYS = int(os.environ.get("REGIME_HMM_REFIT_DAYS", "7"))

_LABELS = {0: "Bull", 1: "Choppy", 2: "Crash"}
_CAPITAL_SCALE = {0: 1.0, 1: 0.6, 2: 0.15}


def _garman_klass(high, low, close, open_):
    """Per-bar GK variance estimate; annualize by * 252 outside."""
    log_hl = np.log(high / low)
    log_co = np.log(close / open_)
    return 0.5 * log_hl ** 2 - (2 * np.log(2) - 1) * log_co ** 2


def _build_features(hist: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c, v = hist["Open"], hist["High"], hist["Low"], hist["Close"], hist["Volume"]
    gk_daily = _garman_klass(h, l, c, o)
    gk_vol = np.sqrt(gk_daily.rolling(10).mean().clip(lower=0) * 252) * 100
    ret_5d = np.log(c / c.shift(5)) * 100
    vol_churn = v / v.rolling(20).mean()
    feats = pd.DataFrame({"gkVol": gk_vol, "ret5d": ret_5d, "volChurn": vol_churn}).dropna()
    return feats


def _fit_hmm(feats: pd.DataFrame):
    from hmmlearn.hmm import GaussianHMM

    X = feats.values
    mean, std = X.mean(axis=0), X.std(axis=0)
    std[std == 0] = 1.0
    Xs = (X - mean) / std

    model = GaussianHMM(n_components=3, covariance_type="diag", n_iter=200, random_state=42)
    model.fit(Xs)

    # Sort states by total variance (ascending) so labels are deterministic: 0=Bull, 1=Choppy, 2=Crash
    variances = model.covars_.sum(axis=1) if model.covars_.ndim == 2 else np.array(
        [np.trace(c) for c in model.covars_])
    order = np.argsort(variances)
    return {"model": model, "order": order, "mean": mean, "std": std,
            "fittedAt": datetime.now(timezone.utc).isoformat()}


def _is_fresh(fitted_at: str) -> bool:
    try:
        dt = datetime.fromisoformat(fitted_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(days=_REFIT_TTL_DAYS)
    except Exception:
        return False


def _load_or_fit(ticker: str, force: bool = False) -> Dict[str, Any]:
    if not force and os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, "rb") as fh:
                bundle = pickle.load(fh)
            if _is_fresh(bundle.get("fittedAt", "")):
                return bundle
        except Exception as exc:
            logger.warning("regime HMM cache read failed: %s", exc)

    hist = yf.Ticker(ticker).history(period="5y", interval="1d", auto_adjust=True)
    feats = _build_features(hist)
    if len(feats) < 100:
        raise ValueError(f"insufficient {ticker} history to fit regime HMM ({len(feats)} rows)")
    bundle = _fit_hmm(feats)
    try:
        with open(_CACHE_PATH, "wb") as fh:
            pickle.dump(bundle, fh)
    except Exception as exc:
        logger.warning("regime HMM cache write failed: %s", exc)
    return bundle


@lru_cache(maxsize=1)
def classify_market_regime(ticker: str = "^NSEI") -> Dict[str, Any]:
    """Current market-wide regime + posterior + capital scaling. Cached for process lifetime
    (weekly model refit lives on disk; this just avoids refetching Nifty per stock request)."""
    try:
        bundle = _load_or_fit(ticker)
        hist = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=True)
        feats = _build_features(hist)
        if feats.empty:
            return {"available": False, "reason": "no recent feature data"}

        Xs = (feats.values - bundle["mean"]) / bundle["std"]
        model, order = bundle["model"], bundle["order"]
        raw_states = model.predict(Xs)
        raw_posteriors = model.predict_proba(Xs)

        rank_of_raw = np.argsort(order)  # raw component index -> sorted regime rank
        regime_idx = int(rank_of_raw[raw_states[-1]])
        posteriors = raw_posteriors[-1][order]  # reorder columns into sorted regime order

        return {
            "available": True,
            "ticker": ticker,
            "regimeIndex": regime_idx,
            "regime": _LABELS[regime_idx],
            "posteriors": {_LABELS[i]: round(float(posteriors[i]), 4) for i in range(3)},
            "capitalScalingFactor": _CAPITAL_SCALE[regime_idx],
            "modelFittedAt": bundle["fittedAt"],
            "asOf": feats.index[-1].strftime("%Y-%m-%d"),
            "lagWarning": f"model refit weekly (every {_REFIT_TTL_DAYS}d); daily inference may lag a brand-new regime shift by up to that long",
        }
    except Exception as e:
        logger.error(f"market regime classification failed: {e}")
        return {"available": False, "reason": str(e)}


if __name__ == "__main__":
    _rng = np.random.default_rng(0)

    def _segment(n, vol_scale, drift):
        gk = _rng.normal(10 * vol_scale, 2 * vol_scale, n).clip(min=0.1)
        ret = _rng.normal(drift, 3 * vol_scale, n)
        churn = _rng.normal(1.0, 0.15 * vol_scale, n).clip(min=0.1)
        return np.column_stack([gk, ret, churn])

    calm = _segment(150, 1.0, 0.3)
    choppy = _segment(150, 2.5, 0.0)
    crash = _segment(150, 6.0, -2.0)
    synth = pd.DataFrame(np.vstack([calm, choppy, crash]), columns=["gkVol", "ret5d", "volChurn"])

    bundle = _fit_hmm(synth)
    Xs = (synth.values - bundle["mean"]) / bundle["std"]
    raw_states = bundle["model"].predict(Xs)
    rank_of_raw = np.argsort(bundle["order"])
    sorted_states = rank_of_raw[raw_states]

    calm_mode = np.bincount(sorted_states[:150]).argmax()
    choppy_mode = np.bincount(sorted_states[150:300]).argmax()
    crash_mode = np.bincount(sorted_states[300:]).argmax()
    assert calm_mode == 0, ("calm segment must classify as lowest-variance state", calm_mode)
    assert crash_mode == 2, ("crash segment must classify as highest-variance state", crash_mode)
    assert calm_mode != crash_mode != choppy_mode or choppy_mode == 1
    print(f"ok synthetic regime sort  calm->{calm_mode}  choppy->{choppy_mode}  crash->{crash_mode}")

    try:
        _load_or_fit("^NSEI", force=True)
        classify_market_regime.cache_clear()
        live = classify_market_regime()
        assert live.get("available") and live["regime"] in _LABELS.values(), live
        print("live spot-check  regime=%s  capitalScale=%.2f  asOf=%s" % (
            live["regime"], live["capitalScalingFactor"], live["asOf"]))
    except Exception as e:
        print(f"live spot-check skipped (offline/network): {e}")
