"""Cached NSE symbol -> Yahoo sector map for sector-rotation overlays."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE_PATH = os.environ.get(
    "SECTOR_MAP_CACHE_PATH",
    os.path.join(os.path.dirname(__file__), "sector_map_cache.json"),
)
_TTL_DAYS = int(os.environ.get("SECTOR_MAP_TTL_DAYS", "7"))
_MAX_REFRESH = int(os.environ.get("SECTOR_MAP_MAX_REFRESH", "40"))


def _clean_symbol(symbol: str) -> str:
    return str(symbol or "").replace(".NS", "").replace(".BO", "").upper().strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(updated_at: Optional[str]) -> bool:
    if not updated_at:
        return False
    try:
        dt = datetime.fromisoformat(updated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return _now() - dt <= timedelta(days=_TTL_DAYS)
    except Exception:
        return False


def _load_cache() -> Dict[str, dict]:
    try:
        if not os.path.exists(_CACHE_PATH):
            return {}
        with open(_CACHE_PATH, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return raw.get("symbols", {}) if isinstance(raw, dict) else {}
    except Exception as exc:
        logger.warning("sector map cache read failed: %s", exc)
        return {}


def _save_cache(symbols: Dict[str, dict]) -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"updatedAt": _now().isoformat(), "symbols": symbols}, fh, indent=2, sort_keys=True)
    except Exception as exc:
        logger.warning("sector map cache write failed: %s", exc)


def _fetch_sector(clean: str) -> Optional[str]:
    for suffix in (".NS", ".BO"):
        try:
            info = yf.Ticker(f"{clean}{suffix}").info or {}
            sector = info.get("sector")
            if sector:
                return str(sector)
        except Exception as exc:
            logger.info("sector lookup failed for %s%s: %s", clean, suffix, exc)
    return None


def get_sector_map(symbols: Iterable[str], max_refresh: Optional[int] = None,
                   force_refresh: bool = False) -> Dict[str, str]:
    """
    Return cached sectors and refresh a bounded number of stale/missing symbols.
    The bounded refresh amortizes the slow yfinance .info calls across requests.
    """
    clean_symbols = []
    seen = set()
    for symbol in symbols:
        clean = _clean_symbol(symbol)
        if clean and clean not in seen:
            clean_symbols.append(clean)
            seen.add(clean)

    cache = _load_cache()
    out: Dict[str, str] = {}
    stale = []
    for clean in clean_symbols:
        rec = cache.get(clean) or {}
        sector = rec.get("sector")
        fresh = (not force_refresh) and _is_fresh(rec.get("updatedAt"))
        if fresh:
            if sector:
                out[clean] = sector
        else:
            if sector:
                out[clean] = sector
            stale.append(clean)

    refresh_budget = _MAX_REFRESH if max_refresh is None else max(0, int(max_refresh))
    changed = False
    for clean in stale[:refresh_budget]:
        sector = _fetch_sector(clean)
        cache[clean] = {"sector": sector, "updatedAt": _now().isoformat()}
        changed = True
        if sector:
            out[clean] = sector

    if changed:
        _save_cache(cache)
    return out


if __name__ == "__main__":
    sample = get_sector_map(["RELIANCE", "TCS"], max_refresh=2)
    print(json.dumps(sample, indent=2, sort_keys=True))
