import os
import logging
import pyotp
import asyncio
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional, Dict, Any, List

try:
    from neo_api_client import NeoAPI
except ImportError:
    try:
        import subprocess
        import sys
        logging.info("Installing neo_api_client with --no-deps to bypass certifi conflict...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-deps", "git+https://github.com/Kotak-Neo/Kotak-neo-api-v2.git"])
        from neo_api_client import NeoAPI
    except Exception as e:
        logging.error(f"Failed to auto-install neo_api_client: {e}")
        NeoAPI = None

logger = logging.getLogger(__name__)

# Load credentials from environment
KOTAK_CONSUMER_KEY = os.environ.get("KOTAK_CONSUMER_KEY")
KOTAK_UCC = os.environ.get("KOTAK_UCC")
KOTAK_MOBILE_NUM = os.environ.get("KOTAK_MOBILE_NUM")
KOTAK_MPIN = os.environ.get("KOTAK_MPIN")
KOTAK_TOTP_SECRET = os.environ.get("KOTAK_TOTP_SECRET")

_client_instance = None
_last_login_date = None

def get_client() -> NeoAPI:
    """Singleton to get and auto-login the Kotak Neo client daily."""
    global _client_instance, _last_login_date
    if not NeoAPI:
        logger.error("NeoAPI client library is not installed.")
        return None
        
    if not all([KOTAK_CONSUMER_KEY, KOTAK_UCC, KOTAK_MOBILE_NUM, KOTAK_MPIN, KOTAK_TOTP_SECRET]):
        logger.warning("Kotak Neo credentials missing in .env")
        return None

    today = datetime.now(timezone.utc).date()
    
    if _client_instance is None or _last_login_date != today:
        logger.info("Initializing Kotak Neo Client and logging in...")
        try:
            client = NeoAPI(
                environment='prod',
                consumer_key=KOTAK_CONSUMER_KEY
            )
            
            totp_obj = pyotp.TOTP(KOTAK_TOTP_SECRET)
            current_totp = totp_obj.now()
            
            mobile = KOTAK_MOBILE_NUM
            if not mobile.startswith("+91"):
                mobile = "+91" + mobile
                
            res_login = client.totp_login(
                mobile_number=mobile,
                ucc=KOTAK_UCC,
                totp=current_totp
            )
            
            if isinstance(res_login, dict) and "error" in res_login:
                logger.error(f"Error in totp_login: {res_login}")
                
            res_val = client.totp_validate(mpin=KOTAK_MPIN)
            if isinstance(res_val, dict) and "error" in res_val:
                logger.error(f"Error in totp_validate: {res_val}")
                
        except Exception as e:
            logger.error(f"Error during Kotak V2 auth: {e}")
            return None

        _client_instance = client
        _last_login_date = today

    return _client_instance


def normalize_symbol_for_kotak(symbol: str) -> str:
    """Convert yfinance symbol (RELIANCE.NS) to Kotak format (e.g. RELIANCE-EQ or token extraction)"""
    sym = symbol.replace(".NS", "").replace(".BO", "")
    return sym + "-EQ"

_token_cache: Dict[str, str] = {}


def _yf_ltp(symbol: str) -> Optional[float]:
    """Last price from yfinance — for the LTP display field ONLY (never to fabricate a book)."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        fi = getattr(t, "fast_info", None)
        lp = getattr(fi, "last_price", None) if fi else None
        if lp:
            return float(lp)
        hist = t.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def _num(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _resolve_token(client, symbol: str) -> Optional[str]:
    """Map a yfinance symbol (RELIANCE.NS) to its NSE cash instrument token via search_scrip."""
    clean = symbol.replace(".NS", "").replace(".BO", "").upper()
    if clean in _token_cache:
        return _token_cache[clean]
    try:
        res = client.search_scrip(exchange_segment="nse_cm", symbol=clean)
    except Exception as e:
        logger.error(f"search_scrip(nse_cm) failed for {clean}: {e}")
        return None
    if not isinstance(res, list):
        return None
    want = f"{clean}-EQ"
    fallback = None
    for it in res:
        if not isinstance(it, dict):
            continue
        tok = it.get("pSymbol") or it.get("instrument_token") or it.get("pSymbolToken")
        if not tok:
            continue
        tsym = str(it.get("pTrdSymbol") or it.get("pSymbolName") or "").upper()
        itype = str(it.get("pInstType") or it.get("pInstName") or "").upper()
        if tsym == want:                       # exact RELIANCE-EQ match wins
            _token_cache[clean] = str(tok)
            return str(tok)
        if fallback is None and itype in ("EQ", "STK"):
            fallback = str(tok)
    if fallback:
        _token_cache[clean] = fallback
    return fallback


def _coerce_levels(book) -> List[Dict[str, Any]]:
    """Normalize a list of order-book levels regardless of Kotak's field naming."""
    out = []
    if not isinstance(book, list):
        return out
    for lv in book:
        if not isinstance(lv, dict):
            continue
        price = _num(lv.get("price") or lv.get("buy_price") or lv.get("sell_price") or lv.get("bp") or lv.get("sp"))
        qty = _num(lv.get("quantity") or lv.get("buy_quantity") or lv.get("sell_quantity") or lv.get("bq") or lv.get("sq"))
        orders = _num(lv.get("orders") or lv.get("no_of_orders") or lv.get("bno") or lv.get("sno")) or 0
        if price is None and qty is None:
            continue
        out.append({"price": round(price, 2) if price else None, "quantity": int(qty or 0), "orders": int(orders)})
    return out


def _shape(raw) -> str:
    """Compact description of an unrecognized response — logged so parsing can be tightened against live data."""
    if isinstance(raw, dict):
        return "dict:" + ",".join(list(raw.keys())[:12])
    if isinstance(raw, list):
        return f"list[{len(raw)}]:" + (",".join(list(raw[0].keys())[:12]) if raw and isinstance(raw[0], dict) else "")
    return type(raw).__name__


def _parse_depth(raw) -> Optional[Dict[str, Any]]:
    """
    Defensive parser for the Kotak REST quotes(depth) payload. The SDK returns the server
    JSON verbatim and its shape is undocumented/versioned, so we unwrap common envelopes and
    accept multiple field names. Returns None (→ 'no data') rather than guessing on garbage.
    """
    items = raw
    if isinstance(raw, dict):
        for k in ("data", "Data", "result", "quotes", "response"):
            v = raw.get(k)
            if isinstance(v, list):
                items = v
                break
            if isinstance(v, dict):
                items = [v]
                break
        else:
            items = [raw]
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return None

    q = items[0]
    depth = q.get("depth") if isinstance(q.get("depth"), dict) else q
    bids = _coerce_levels(depth.get("buy") or depth.get("bids") or q.get("bids"))
    asks = _coerce_levels(depth.get("sell") or depth.get("asks") or q.get("asks"))

    # Prefer the exchange's total pending buy/sell quantity (full book) over the 5 visible levels.
    tbq = _num(q.get("total_buy_quantity") or q.get("totBuyQty") or q.get("tbq") or depth.get("total_buy_quantity"))
    tsq = _num(q.get("total_sell_quantity") or q.get("totSellQty") or q.get("tsq") or depth.get("total_sell_quantity"))
    if tbq is None:
        tbq = sum(b["quantity"] for b in bids) or None
    if tsq is None:
        tsq = sum(a["quantity"] for a in asks) or None

    ltp = _num(q.get("ltp") or q.get("last_price") or q.get("lastPrice") or q.get("lp") or q.get("ltpc"))

    if not bids and not asks and not (tbq or tsq):
        return None
    return {
        "bids": bids[:5],
        "asks": asks[:5],
        "ltp": ltp,
        "totalBidQty": int(tbq) if tbq else 0,
        "totalAskQty": int(tsq) if tsq else 0,
    }


def _fetch_depth_sync(symbol: str) -> Dict[str, Any]:
    """
    Real Level-2 order book from Kotak Neo (blocking SDK call — run via asyncio.to_thread).
    On any failure returns available=False with empty bids/asks and a yfinance LTP for display.
    It NEVER fabricates a book.
    """
    ltp_fallback = _yf_ltp(symbol)
    base = {"available": False, "source": "none", "bids": [], "asks": [],
            "ltp": round(ltp_fallback, 2) if ltp_fallback else None, "totalBidQty": 0, "totalAskQty": 0}

    client = get_client()
    if client is None:
        base["reason"] = "Kotak client unavailable (check .env credentials / TOTP)"
        return base

    token = _resolve_token(client, symbol)
    if not token:
        base["reason"] = "Instrument token not found via search_scrip"
        return base

    try:
        raw = client.quotes(
            instrument_tokens=[{"instrument_token": str(token), "exchange_segment": "nse_cm"}],
            quote_type="depth",
        )
    except Exception as e:
        logger.error(f"Kotak quotes(depth) failed for {symbol}: {repr(e)}")
        base["reason"] = f"quotes error: {repr(e)[:120]}"
        return base

    parsed = _parse_depth(raw)
    if parsed is None:
        logger.warning(f"Kotak depth unparseable for {symbol}; shape={_shape(raw)}")
        base["reason"] = "depth response unrecognized"
        base["rawShape"] = _shape(raw)
        return base

    parsed["available"] = True
    parsed["source"] = "Kotak-Level2"
    if not parsed.get("ltp"):
        parsed["ltp"] = ltp_fallback
    parsed["ltp"] = round(parsed["ltp"], 2) if parsed.get("ltp") else None
    return parsed


async def get_market_depth(symbol: str) -> dict:
    """Live Level-2 market depth from Kotak Neo (real data; available=False if the feed is down)."""
    return await asyncio.to_thread(_fetch_depth_sync, symbol)

async def get_option_chain(symbol: str) -> dict:
    """Fetch true NSE Options Chain and compute PCR using Kotak Neo API."""
    import asyncio
    client = get_client()
    if not client:
        return {"available": False, "error": "Kotak API Client not initialized", "reason": "Kotak authentication failed. Check your TOTP or credentials in .env."}
    
    # Do NOT append -EQ for options search
    clean_sym = symbol.replace(".NS", "").replace(".BO", "")
    
    try:
        res = await asyncio.to_thread(client.search_scrip, exchange_segment="nse_fo", symbol=clean_sym)
        if not res or not isinstance(res, list) or len(res) == 0:
            return {"available": False, "error": "Not F&O", "reason": f"{clean_sym} is not available in the Futures & Options segment."}
            
        options = [x for x in res if x.get("pInstType") == "OPTSTK" or x.get("pInstName") == "OPTSTK"]
        if not options:
            options = [x for x in res if x.get("pInstType") == "OPTIDX" or x.get("pInstName") == "OPTIDX"]
            
        if not options:
            return {"available": False, "error": "No options found", "reason": f"No active options contracts found for {clean_sym}"}
            
        expiries = sorted(list(set(x.get("pExpiryDate") for x in options if x.get("pExpiryDate"))))
        if not expiries:
            return {"available": False, "error": "No expiries found", "reason": "Options missing expiry dates"}
            
        options.sort(key=lambda x: x.get("lExpiryDate", 9999999999))
        near_expiry_timestamp = options[0].get("lExpiryDate")
        near_expiry_str = options[0].get("pExpiryDate")
        
        near_options = [x for x in options if x.get("lExpiryDate") == near_expiry_timestamp]
        
        ce_total_oi = 0
        pe_total_oi = 0
        strikes_map = {} 
        
        for opt in near_options:
            strike = opt.get("dStrikePrice;") or opt.get("dStrikePrice")
            if not strike or strike <= 0:
                continue
                
            opt_type = opt.get("pOptionType") 
            if not opt_type:
                continue
                
            if strike not in strikes_map:
                strikes_map[strike] = {"strike": float(strike), "ceOI": 0, "peOI": 0, "ceLTP": 0, "peLTP": 0}
                
            oi = float(opt.get("dOpenInterest", 0))
            base_price = float(opt.get("pScripBasePrice", 0))
            
            if opt_type == 'CE':
                strikes_map[strike]["ceOI"] = oi
                strikes_map[strike]["ceLTP"] = base_price
                ce_total_oi += oi
            elif opt_type == 'PE':
                strikes_map[strike]["peOI"] = oi
                strikes_map[strike]["peLTP"] = base_price
                pe_total_oi += oi
                
        # Find underlying approximate price from the cash-market LTP
        cash_depth = await get_market_depth(symbol)
        underlying = 0
        if cash_depth and cash_depth.get("ltp"):
            underlying = cash_depth["ltp"]
        elif strikes_map:
            underlying = list(strikes_map.keys())[len(strikes_map)//2]
            
        rows = list(strikes_map.values())
        if underlying > 0:
            rows.sort(key=lambda x: abs(x["strike"] - underlying))
        rows = rows[:14] # Get 14 nearest strikes
        rows.sort(key=lambda x: x["strike"])
        
        pcr = (pe_total_oi / ce_total_oi) if ce_total_oi else None

        # Dealer positioning (max-pain / OI walls always; GEX/IV when premiums are live). Best-effort.
        positioning = None
        try:
            import time as _time
            import options_analytics as oa
            exp_ts = near_expiry_timestamp
            if exp_ts and exp_ts > 1e11:      # normalize ms → s if Kotak returns millis
                exp_ts = exp_ts / 1000.0
            positioning = oa.compute_positioning(rows, underlying, exp_ts, _time.time())
        except Exception as e:
            logger.warning(f"options positioning failed for {symbol}: {e}")

        return {
            "available": True,
            "underlying": underlying,
            "expiry": near_expiry_str,
            "expiries": expiries[:8],
            "ceTotalOI": ce_total_oi,
            "peTotalOI": pe_total_oi,
            "pcr": pcr,
            "rows": rows,
            "positioning": positioning,
        }
    except Exception as e:
        logger.error(f"Kotak options chain error: {e}")
        return {"available": False, "error": str(e), "reason": "Exception during Kotak API call"}


if __name__ == "__main__":  # offline sanity check of the defensive depth parser (no network)
    # Shape A: nested depth.buy/sell with explicit totals (the documented websocket-style mapping)
    a = _parse_depth({"data": [{"ltp": 100.5, "total_buy_quantity": 9000, "total_sell_quantity": 4000,
                                "depth": {"buy": [{"price": 100.4, "quantity": 5000, "orders": 12}],
                                          "sell": [{"price": 100.6, "quantity": 2000, "orders": 7}]}}]})
    assert a and a["totalBidQty"] == 9000 and a["totalAskQty"] == 4000 and a["ltp"] == 100.5, a
    # Shape B: flat bids/asks, no explicit totals → summed from levels; short field names
    b = _parse_depth([{"bids": [{"bp": 50, "bq": 300}], "asks": [{"sp": 51, "sq": 100}], "lp": 50.5}])
    assert b and b["totalBidQty"] == 300 and b["totalAskQty"] == 100, b
    # Garbage / empty → None (must NOT fabricate a book)
    assert _parse_depth({"data": []}) is None
    assert _parse_depth({"junk": 1}) is None
    assert _parse_depth("error string") is None
    print("ok  kotak depth parser:", a, b)
