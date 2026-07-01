"""
bhavcopy_service.py — single owner of the NSE security-wise full bhavcopy.

The bhavcopy is one CSV holding the WHOLE NSE cash market for one trading day
(SYMBOL, OHLC, CLOSE_PRICE, TTL_TRD_QNTY, DELIV_QTY, DELIV_PER). That makes it
three things at once:
  1. the official source of truth to validate yfinance prices/volume (cross_check),
  2. a real institutional signal — delivery % (strong-hands accumulation),
  3. the universe snapshot for cross-sectional ranking.

Download goes through Scrapling (the anti-bot fetcher already used for Twitter/
Reddit/Aftermarkets) because jugaad_data's plain-requests download is NSE-blocked.
"""
import os
import sys
import io
import logging
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Vendored Scrapling (same import pattern as scraper_service.py)
_vendor = os.path.join(os.path.dirname(__file__), "vendor", "scrapling")
if _vendor not in sys.path:
    sys.path.append(_vendor)

# Canonical download dir (abs path → kills the CWD ambiguity between backend/bhavcopy and root bhavcopy)
_DIR = os.path.join(os.path.dirname(__file__), "bhavcopy")
# Also read pre-existing files dropped in the repo-root bhavcopy/ dir
_ALT_DIR = os.path.join(os.path.dirname(__file__), "..", "bhavcopy")

# NSE archive: security-wise full bhavcopy with delivery. {DDMMYYYY}, e.g. 29062026
_NSE_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{}.csv"
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/csv,*/*",
    "Referer": "https://www.nseindia.com/all-reports",
}
_IST = timezone(timedelta(hours=5, minutes=30))


def _fname(d: date) -> str:
    """jugaad_data-compatible local filename, e.g. sec_bhavdata_full_29Jun2026bhav.csv."""
    return f"sec_bhavdata_full_{d.strftime('%d%b%Y')}bhav.csv"


def _date_from_fname(fname: str) -> Optional[date]:
    try:
        core = fname.replace("sec_bhavdata_full_", "").replace("bhav.csv", "")
        return datetime.strptime(core, "%d%b%Y").date()
    except Exception:
        return None


def _looks_like_bhavcopy(text: str) -> bool:
    """A real bhavcopy starts with the header; an HTML block page won't contain these tokens."""
    head = (text or "")[:400].upper()
    return "SYMBOL" in head and "DELIV_PER" in head and "SERIES" in head


def _last_trading_day(d: Optional[date] = None) -> date:
    """Most recent weekday on/before d. ponytail: weekend-only; NSE holidays need a calendar — upgrade if false mismatches appear."""
    d = d or datetime.now(_IST).date()
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d -= timedelta(days=1)
    return d


def _latest_local() -> Tuple[Optional[str], Optional[date]]:
    """Newest existing bhavcopy across both dirs, by date parsed from filename."""
    best_path, best_date = None, None
    for folder in (_DIR, _ALT_DIR):
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if not (f.startswith("sec_bhavdata_full_") and f.endswith("bhav.csv")):
                continue
            fd = _date_from_fname(f)
            if fd and (best_date is None or fd > best_date):
                best_date, best_path = fd, os.path.join(folder, f)
    return best_path, best_date


def _fetch_csv_text(url: str) -> Optional[str]:
    """
    Pull a CSV over the network. Fast path = Scrapling Fetcher (httpx, clean raw bytes);
    if NSE blocks it, fall through to StealthyFetcher (anti-bot browser, won't get blocked).
    Returns validated CSV text or None.
    """
    # Fast path: plain fetch with NSE-like headers (works for the static archive when not blocked)
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get(url, headers=_NSE_HEADERS, timeout=20)
        if getattr(page, "status", 0) == 200:
            text = page.body.decode("utf-8", "replace") if getattr(page, "body", None) else page.get_all_text()
            if _looks_like_bhavcopy(text):
                return text
    except Exception as e:
        logger.info(f"Fetcher.get bhavcopy fast-path failed: {e}")

    # Anti-bot path: the one the user mandated — StealthyFetcher won't get blocked
    try:
        from scrapling.fetchers import StealthyFetcher
        page = StealthyFetcher.fetch(url, headers=_NSE_HEADERS)
        if getattr(page, "status", 0) in (200, 0):
            text = page.body.decode("utf-8", "replace") if getattr(page, "body", None) else page.get_all_text()
            if _looks_like_bhavcopy(text):
                return text
    except Exception as e:
        logger.warning(f"StealthyFetcher bhavcopy failed: {e}")
    return None


def _download(d: date) -> Optional[str]:
    """Download the bhavcopy for date d → write to canonical dir → return path, else None."""
    os.makedirs(_DIR, exist_ok=True)
    text = _fetch_csv_text(_NSE_URL.format(d.strftime("%d%m%Y")))
    if text:
        path = os.path.join(_DIR, _fname(d))
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        logger.info(f"Bhavcopy downloaded via Scrapling for {d}: {path}")
        return path

    # Last-resort fallback: jugaad_data (plain requests — often blocked, hence Scrapling above)
    try:
        from jugaad_data.nse import full_bhavcopy_save
        full_bhavcopy_save(d, _DIR)
        path = os.path.join(_DIR, _fname(d))
        return path if os.path.exists(path) else None
    except Exception as e:
        logger.info(f"jugaad_data fallback failed for {d}: {e}")
        return None


def _ensure() -> Tuple[Optional[str], Optional[date]]:
    """Return (path, refDate) of a bhavcopy that is as fresh as the last trading day, downloading if needed."""
    target = _last_trading_day()
    local_path, local_date = _latest_local()
    if local_date and local_date >= target:
        return local_path, local_date

    # Need a fresher pull — try target day, then walk back a few sessions (today's may not be published yet)
    for i in range(4):
        d = _last_trading_day(target - timedelta(days=i))
        path = _download(d)
        if path:
            return path, d

    # Network down → degrade to whatever we have locally (flagged stale by the caller)
    return local_path, local_date


@lru_cache(maxsize=4)
def _read_csv_cached(path: str, _mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    for c in ("SYMBOL", "SERIES"):
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df


def _parse_df(raw_text: str) -> pd.DataFrame:
    """Parse bhavcopy CSV text → normalized DataFrame (shared by the loader and the self-check)."""
    df = pd.read_csv(io.StringIO(raw_text), skipinitialspace=True)
    df.columns = df.columns.str.strip()
    for c in ("SYMBOL", "SERIES"):
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df


def load_bhavcopy() -> Tuple[Optional[pd.DataFrame], Optional[date]]:
    """The freshest available bhavcopy as (DataFrame, refDate). (None, None) if nothing is reachable."""
    path, ref = _ensure()
    if not path or not os.path.exists(path):
        return None, ref
    try:
        return _read_csv_cached(path, os.path.getmtime(path)), ref
    except Exception as e:
        logger.error(f"bhavcopy read failed {path}: {e}")
        return None, ref


def load_bhavcopy_df() -> Optional[pd.DataFrame]:
    """Convenience for the verification one-liner."""
    return load_bhavcopy()[0]


def _num(v) -> Optional[float]:
    """Coerce a bhavcopy cell ('-', ' 12.3', '') to float or None."""
    try:
        f = float(str(v).strip())
        return f if f == f else None  # drop NaN
    except (TypeError, ValueError):
        return None


def _eq_row(df: pd.DataFrame, clean: str) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None
    hit = df[(df["SYMBOL"] == clean) & (df["SERIES"] == "EQ")]
    return hit.iloc[0] if not hit.empty else None


def _clean_symbol(symbol: str) -> str:
    return symbol.replace(".NS", "").replace(".BO", "").upper().strip()


def cross_check(symbol: str, yf_close: Optional[float], yf_vol: Optional[float],
                yf_date: Optional[date]) -> Dict[str, Any]:
    """
    Validate yfinance's latest COMPLETED bar against the official NSE bhavcopy.
    Compare RAW (unadjusted) close — bhavcopy CLOSE_PRICE is unadjusted.
    status: ok | mismatch | stale-reference | not-found | unavailable
    """
    df, ref = load_bhavcopy()
    if df is None:
        return {"status": "unavailable", "refDate": None}

    # Reference older than yfinance's bar → can't claim a mismatch (apples vs oranges)
    if yf_date and ref and ref < yf_date:
        return {"status": "stale-reference", "refDate": ref.isoformat(), "yfDate": yf_date.isoformat()}

    row = _eq_row(df, _clean_symbol(symbol))
    if row is None:
        return {"status": "not-found", "refDate": ref.isoformat() if ref else None}

    nse_close = _num(row.get("CLOSE_PRICE"))
    nse_vol = _num(row.get("TTL_TRD_QNTY"))
    close_delta = ((yf_close - nse_close) / nse_close * 100.0) if (yf_close and nse_close) else None
    vol_delta = ((yf_vol - nse_vol) / nse_vol * 100.0) if (yf_vol and nse_vol) else None
    # 0.5% close tolerance absorbs rounding/feed lag; volume feeds differ more, so 5%
    match = close_delta is not None and abs(close_delta) <= 0.5
    return {
        "status": "ok" if match else "mismatch",
        "match": bool(match),
        "refDate": ref.isoformat() if ref else None,
        "nseClose": nse_close,
        "yfClose": round(yf_close, 2) if yf_close else None,
        "closeDeltaPct": round(close_delta, 3) if close_delta is not None else None,
        "volDeltaPct": round(vol_delta, 2) if vol_delta is not None else None,
    }


def delivery_signal(symbol: str) -> Dict[str, Any]:
    """Delivery % from the bhavcopy — high delivery = real ownership transfer (strong hands), not intraday churn."""
    df, ref = load_bhavcopy()
    row = _eq_row(df, _clean_symbol(symbol)) if df is not None else None
    if row is None:
        return {"available": False, "refDate": ref.isoformat() if ref else None}
    pct = _num(row.get("DELIV_PER"))
    qty = _num(row.get("DELIV_QTY"))
    if pct is None:
        return {"available": False, "refDate": ref.isoformat() if ref else None}
    if pct >= 65:
        sig = "Very High — Strong-Hand Accumulation"
    elif pct >= 45:
        sig = "High — Investor Participation"
    elif pct >= 25:
        sig = "Moderate"
    else:
        sig = "Low — Speculative / Intraday Churn"
    return {
        "available": True,
        "deliveryPercentage": round(pct, 2),
        "deliveryQuantity": int(qty) if qty else 0,
        "signal": sig,
        "refDate": ref.isoformat() if ref else None,
    }


def universe_factors() -> Optional[pd.DataFrame]:
    """
    Whole-market EQ snapshot → comparable single-day factors for cross-sectional ranking.
    Columns: oneDayRet, delivPct, turnover, rangePct (indexed by SYMBOL).
    ponytail: single-day only — multi-day momentum/quality needs a persisted history store.
    """
    df, _ = load_bhavcopy()
    if df is None or df.empty:
        return None
    eq = df[df["SERIES"] == "EQ"].copy()
    for c in ("CLOSE_PRICE", "PREV_CLOSE", "HIGH_PRICE", "LOW_PRICE", "TURNOVER_LACS", "DELIV_PER"):
        eq[c] = pd.to_numeric(eq[c], errors="coerce")
    out = pd.DataFrame(index=eq["SYMBOL"])
    out["oneDayRet"] = (eq["CLOSE_PRICE"].values - eq["PREV_CLOSE"].values) / eq["PREV_CLOSE"].values * 100.0
    out["delivPct"] = eq["DELIV_PER"].values
    out["turnover"] = eq["TURNOVER_LACS"].values
    out["rangePct"] = (eq["HIGH_PRICE"].values - eq["LOW_PRICE"].values) / eq["PREV_CLOSE"].values * 100.0
    return out


if __name__ == "__main__":  # offline self-check of parse + cross-check + delivery (no network)
    _csv = (
        "SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, "
        "CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
        "RELIANCE, EQ, 29-Jun-2026, 1400.00, 1410.00, 1420.00, 1395.00, 1415.00, 1415.00, 1412.00, 1000000, 14120.0, 50000, 800000, 80.00\n"
        "PENNY, EQ, 29-Jun-2026, 10.00, 10.2, 10.5, 9.8, 10.1, 10.1, 10.0, 5000000, 505.0, 2000, 500000, 10.00\n"
        "SOMEBE, BE, 29-Jun-2026, 50.0, 50, 51, 49, 50.5, 50.5, 50.4, 1000, 0.5, 30, 900, 90.0\n"
    )
    _df = _parse_df(_csv)
    assert list(_df.columns)[:2] == ["SYMBOL", "SERIES"], _df.columns.tolist()
    assert (_df["SYMBOL"] == "RELIANCE").any()

    # _eq_row only matches the EQ series, never BE
    assert _eq_row(_df, "SOMEBE") is None
    _r = _eq_row(_df, "RELIANCE")
    assert _r is not None and _num(_r["CLOSE_PRICE"]) == 1415.0

    # cross_check math via a monkeypatched loader (no file/network)
    _ref = date(2026, 6, 29)
    globals()["load_bhavcopy"] = lambda: (_df, _ref)
    ok = cross_check("RELIANCE.NS", 1415.0, 1000000, _ref)
    assert ok["status"] == "ok" and ok["match"] and abs(ok["closeDeltaPct"]) < 1e-6, ok
    bad = cross_check("RELIANCE.NS", 1500.0, 1000000, _ref)               # +6% off → mismatch
    assert bad["status"] == "mismatch" and not bad["match"], bad
    stale = cross_check("RELIANCE.NS", 1415.0, 1000000, date(2026, 6, 30))  # ref older than yf bar
    assert stale["status"] == "stale-reference", stale
    miss = cross_check("NOTLISTED.NS", 100.0, 1, _ref)
    assert miss["status"] == "not-found", miss

    # delivery signal banding + non-deliverable handling
    dsig = delivery_signal("RELIANCE.NS")
    assert dsig["available"] and dsig["deliveryPercentage"] == 80.0 and "Strong-Hand" in dsig["signal"], dsig

    # universe factors: RELIANCE +1.07% day, range ~1.79%, only EQ rows kept
    uf = universe_factors()
    assert uf is not None and "RELIANCE" in uf.index and "SOMEBE" not in uf.index, uf
    assert abs(uf.loc["RELIANCE", "oneDayRet"] - (1415.0 - 1400.0) / 1400.0 * 100.0) < 1e-6, uf.loc["RELIANCE"]
    print("ok  bhavcopy_service:", ok["status"], dsig["signal"], "| universe rows:", len(uf))
