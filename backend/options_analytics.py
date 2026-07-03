"""
options_analytics.py — dealer-positioning engine over an NSE option chain. Pure math (numpy + math,
no scipy). Fed the rows kotak_service.get_option_chain already returns.

Computes: Max Pain and OI walls (OI-only → always valid), and — when option premiums are live —
Black-Scholes implied vol per strike, the Gamma Exposure (GEX) profile with its zero-gamma flip
level and regime, ATM IV, and put/call skew. Degrades to OI-only if premiums look stale/zero.
"""
import math
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_SQRT2 = math.sqrt(2.0)
_SQRT2PI = math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT2PI


def _d1(S, K, T, r, sig):
    return (math.log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))


def _bs_price(S, K, T, r, sig, is_call) -> float:
    if T <= 0 or sig <= 0:
        return max(0.0, (S - K) if is_call else (K - S))
    d1 = _d1(S, K, T, r, sig)
    d2 = d1 - sig * math.sqrt(T)
    if is_call:
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _bs_gamma(S, K, T, r, sig) -> float:
    if T <= 0 or sig <= 0 or S <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sig)
    return _norm_pdf(d1) / (S * sig * math.sqrt(T))


def _implied_vol(price, S, K, T, r, is_call) -> Optional[float]:
    """Bisection on σ (BS price is monotonic in σ). None if price is below intrinsic or degenerate."""
    if not price or price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None
    intrinsic = max(0.0, (S - K) if is_call else (K - S)) * math.exp(-r * T)
    if price < intrinsic - 1e-6:
        return None
    lo, hi = 1e-4, 5.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        p = _bs_price(S, K, T, r, mid, is_call)
        if abs(p - price) < 1e-5:
            return mid
        if p > price:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _f(row, *keys):
    for k in keys:
        v = row.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 0.0


def compute_positioning(rows: List[Dict[str, Any]], spot: float, expiry_ts: Optional[float],
                        now_ts: float, r: float = 0.065, lot: float = 1.0) -> Dict[str, Any]:
    """
    Dealer positioning from the option chain. `expiry_ts`/`now_ts` are epoch seconds.
    Max-pain + OI walls always computed; GEX/IV only when premiums are live (else dataQuality='oi-only').
    """
    try:
        strikes = sorted({_f(x, "strike") for x in rows if _f(x, "strike") > 0})
        if not strikes or not spot or spot <= 0:
            return {"available": False, "reason": "no strikes / spot"}

        ce_oi = {_f(x, "strike"): _f(x, "ceOI") for x in rows}
        pe_oi = {_f(x, "strike"): _f(x, "peOI") for x in rows}
        ce_ltp = {_f(x, "strike"): _f(x, "ceLTP") for x in rows}
        pe_ltp = {_f(x, "strike"): _f(x, "peLTP") for x in rows}

        # --- Max pain: expiry price minimizing total intrinsic paid to holders (OI-only, always valid)
        def payout(P):
            return sum(ce_oi.get(k, 0) * max(0.0, P - k) + pe_oi.get(k, 0) * max(0.0, k - P) for k in strikes)
        max_pain = min(strikes, key=payout)

        # --- OI walls
        oi_resistance = max(strikes, key=lambda k: ce_oi.get(k, 0))
        oi_support = max(strikes, key=lambda k: pe_oi.get(k, 0))
        tot_ce, tot_pe = sum(ce_oi.values()), sum(pe_oi.values())
        pcr_oi = round(tot_pe / tot_ce, 3) if tot_ce else None

        out = {
            "available": True,
            "spot": round(spot, 2),
            "maxPain": round(max_pain, 2),
            "oiSupport": round(oi_support, 2),
            "oiResistance": round(oi_resistance, 2),
            "pcrOI": pcr_oi,
            "dataQuality": "oi-only",
        }

        # --- GEX / IV need live premiums + positive time to expiry
        T = 0.0
        if expiry_ts and expiry_ts > now_ts:
            T = (expiry_ts - now_ts) / (365.0 * 86400.0)
            T = max(T, 1.0 / 365.0) if T <= 2.0 else 0.0   # implausible T → wrong units → OI-only
        iv_ce, iv_pe = {}, {}
        if T > 0:
            for k in strikes:
                iv_ce[k] = _implied_vol(ce_ltp.get(k), spot, k, T, r, True)
                iv_pe[k] = _implied_vol(pe_ltp.get(k), spot, k, T, r, False)
        n_iv = sum(1 for k in strikes if iv_ce.get(k) or iv_pe.get(k))

        if T > 0 and n_iv >= max(3, len(strikes) // 2):   # enough live premiums → full analytics
            def gex_at(P):
                g = 0.0
                for k in strikes:
                    if iv_ce.get(k):
                        g += _bs_gamma(P, k, T, r, iv_ce[k]) * ce_oi.get(k, 0)
                    if iv_pe.get(k):
                        g -= _bs_gamma(P, k, T, r, iv_pe[k]) * pe_oi.get(k, 0)   # dealers short put gamma
                return g * P * P * 0.01 * lot

            net = gex_at(spot)
            # zero-gamma flip: scan spot levels across the strike range for a sign change
            lo, hi = strikes[0], strikes[-1]
            prev_p, prev_g, flip = lo, gex_at(lo), None
            steps = 60
            for s in range(1, steps + 1):
                P = lo + (hi - lo) * s / steps
                g = gex_at(P)
                if prev_g == 0 or (g < 0) != (prev_g < 0):
                    flip = round(prev_p + (P - prev_p) * 0.5, 2)
                    break
                prev_p, prev_g = P, g

            atm = min(strikes, key=lambda k: abs(k - spot))
            atm_iv = next((v for v in (iv_ce.get(atm), iv_pe.get(atm)) if v), None)
            # skew: OTM put IV (~-5%) minus OTM call IV (~+5%) → crash-fear premium
            put_k = min(strikes, key=lambda k: abs(k - spot * 0.95))
            call_k = min(strikes, key=lambda k: abs(k - spot * 1.05))
            skew = None
            if iv_pe.get(put_k) and iv_ce.get(call_k):
                skew = round((iv_pe[put_k] - iv_ce[call_k]) * 100.0, 2)

            out.update({
                "dataQuality": "full",
                "gex": {
                    "net": round(net, 2),
                    "regime": ("Positive — dealers dampen/pin (mean-revert)" if net > 0
                               else "Negative — dealers amplify moves (trend)"),
                    "flipStrike": flip,
                },
                "iv": {
                    "atmPct": round(atm_iv * 100.0, 2) if atm_iv else None,
                    "skewPct": skew,   # >0 = puts richer = downside fear
                },
            })
        return out
    except Exception as e:
        logger.error(f"options positioning error: {e}")
        return {"available": False, "reason": str(e)[:120]}


if __name__ == "__main__":  # offline self-check (no network)
    # 1) BS implied-vol round-trip
    _p = _bs_price(100, 100, 0.25, 0.065, 0.20, True)
    _iv = _implied_vol(_p, 100, 100, 0.25, 0.065, True)
    assert abs(_iv - 0.20) < 1e-3, _iv
    # gamma is positive and peaks near ATM
    assert _bs_gamma(100, 100, 0.25, 0.065, 0.2) > _bs_gamma(100, 130, 0.25, 0.065, 0.2) > 0

    # 2) Build a synthetic chain around spot=100, T≈36d. Symmetric OI peak at 100 → max pain 100.
    _spot, _T_days = 100.0, 36.0
    _now = 1_700_000_000.0
    _exp = _now + _T_days * 86400.0
    _rows = []
    for k in range(80, 121, 5):
        oi_c = 10000 - abs(k - 100) * 300        # OI peaks at ATM
        oi_p = 10000 - abs(k - 100) * 300
        # price options at a vol with a put-skew (OTM puts get higher vol)
        ivc = 0.20 + max(0, k - 100) * 0.0
        ivp = 0.20 + max(0, 100 - k) * 0.004      # lower strikes → higher put IV
        _rows.append({
            "strike": k, "ceOI": oi_c, "peOI": oi_p,
            "ceLTP": _bs_price(_spot, k, _T_days / 365, 0.065, ivc, True),
            "peLTP": _bs_price(_spot, k, _T_days / 365, 0.065, ivp, False),
        })
    _pos = compute_positioning(_rows, _spot, _exp, _now)
    assert _pos["available"] and _pos["dataQuality"] == "full", _pos
    assert _pos["maxPain"] == 100.0, _pos                     # symmetric OI → pin at ATM
    assert _pos["iv"]["skewPct"] > 0, ("put skew should be positive", _pos)   # OTM puts richer
    assert _pos["iv"]["atmPct"] and abs(_pos["iv"]["atmPct"] - 20.0) < 3, _pos

    # 3) OI-only fallback when premiums are zero/missing
    _rows2 = [{"strike": k, "ceOI": 100, "peOI": 500 if k <= 100 else 100, "ceLTP": 0, "peLTP": 0}
              for k in range(80, 121, 5)]
    _pos2 = compute_positioning(_rows2, 100.0, None, _now)
    assert _pos2["available"] and _pos2["dataQuality"] == "oi-only", _pos2
    assert _pos2["oiSupport"] <= 100 and "gex" not in _pos2, _pos2
    print("ok options_analytics  maxPain=%.0f  atmIV=%.1f%%  skew=%.2f%%  gexRegime=%s  flip=%s" % (
        _pos["maxPain"], _pos["iv"]["atmPct"], _pos["iv"]["skewPct"],
        _pos["gex"]["regime"].split(" —")[0], _pos["gex"]["flipStrike"]))
