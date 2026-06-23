"""Extended data services: FII/DII, concalls, peers, options, insider trading."""
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import json
import re
import io
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _strip_symbol(symbol: str) -> str:
    return symbol.upper().replace(".NS", "").replace(".BO", "").strip()


def get_fii_dii() -> dict:
    """Scrape Moneycontrol FII/DII daily activity from Next.js page data."""
    try:
        import curl_cffi.requests as creq
        r = creq.get("https://www.moneycontrol.com/markets/fii-dii-data/",
                         headers={"Referer": "https://www.moneycontrol.com/", "Accept": "text/html"}, impersonate="chrome120", timeout=12, allow_redirects=True)
        if r.status_code != 200:
            return {"rows": [], "error": f"HTTP {r.status_code}"}
        m = re.search(r'__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
        if not m:
            return {"rows": []}
        data = json.loads(m.group(1))
        fdata = data.get("props", {}).get("pageProps", {}).get("FiiDiiData", {}).get("fiiDiiData", [])
        rows = []
        for d in fdata[:15]:
            rows.append({
                "date": d.get("date"),
                "displayDate": d.get("fDate"),
                "fiiCash": _to_num(d.get("fiiCM")),
                "diiCash": _to_num(d.get("diiCM")),
                "fiiIdxFut": _to_num(d.get("fiiIdxFut")),
                "fiiIdxOpt": _to_num(d.get("fiiIdxOpt")),
                "fiiStkFut": _to_num(d.get("fiiStkFut")),
                "fiiStkOpt": _to_num(d.get("fiiStkOpt")),
                "niftyClose": _to_num(d.get("niftyClose")),
                "niftyChangePct": _to_num(d.get("niftyChangePer")),
                "sensexClose": _to_num(d.get("sensexClose")),
                "sensexChangePct": _to_num(d.get("sensexChangePer")),
            })
        return {"rows": rows, "updatedAt": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"fii-dii error: {e}")
        return {"rows": [], "error": str(e)}


def _to_num(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None


def get_concalls(symbol: str) -> list:
    """Scrape concall transcripts/PPT links from Screener.in."""
    clean = _strip_symbol(symbol)
    for path in ("consolidated/", ""):
        url = f"https://www.screener.in/company/{clean}/{path}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for sec in soup.find_all(["div", "section"]):
                txt = sec.get_text(" ", strip=True)
                if "Concall" not in txt or len(txt) > 6000:
                    continue
                lis = sec.find_all("li")
                if not lis or len(lis) > 80:
                    continue
                out = []
                for li in lis[:24]:
                    line = li.get_text(" ", strip=True)
                    if not line or "Concall" in line:
                        continue
                    date_match = re.match(r"^([A-Z][a-z]+\s+\d{4})", line)
                    if not date_match:
                        continue
                    date_str = date_match.group(1)
                    item = {"date": date_str, "transcript": None, "ppt": None, "recording": None, "aiSummary": None}
                    for a in li.find_all("a"):
                        label = a.get_text(strip=True).lower()
                        href = a.get("href", "")
                        if not href:
                            continue
                        if "transcript" in label:
                            item["transcript"] = href
                        elif label == "ppt" or "presentation" in label:
                            item["ppt"] = href
                        elif "rec" in label or "youtube" in href or "youtu.be" in href:
                            item["recording"] = href
                        elif "ai" in label or "summary" in label:
                            item["aiSummary"] = href
                    if item["transcript"] or item["ppt"] or item["recording"]:
                        out.append(item)
                if out:
                    return out
        except Exception as e:
            logger.error(f"concalls scrape error: {e}")
    return []


def fetch_pdf_text(url: str, max_chars: int = 30000) -> str:
    """Download a PDF and extract text. Returns empty if PDF unreachable (geo-block)."""
    try:
        from pypdf import PdfReader
        # Try with curl_cffi for better TLS fingerprint, fallback to requests
        try:
            import curl_cffi.requests as creq
            r = creq.get(url, impersonate="chrome120",
                         headers={"Referer": "https://www.bseindia.com/", "Accept": "*/*"},
                         timeout=20, allow_redirects=True)
            content = r.content
            ctype = r.headers.get("content-type", "")
        except Exception:
            r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
            content = r.content
            ctype = r.headers.get("content-type", "")
        # Detect geo-block: BSE returns HTML instead of PDF
        if not content or len(content) < 1000:
            return ""
        if content[:4] != b"%PDF" and "html" in ctype.lower():
            return ""
        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        total = 0
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            text_parts.append(t)
            total += len(t)
            if total >= max_chars:
                break
        return "\n".join(text_parts)[:max_chars]
    except Exception as e:
        logger.error(f"pdf extract error: {e}")
        return ""


def get_peers(symbol: str) -> list:
    """Get sector peers of a stock using yfinance recommendations + manual mapping."""
    sym = symbol if symbol.endswith(".NS") or symbol.endswith(".BO") else f"{symbol}.NS"
    t = yf.Ticker(sym)
    sector = None
    try:
        sector = (t.info or {}).get("sector")
    except Exception:
        pass

    SECTOR_PEERS = {
        "Energy": ["RELIANCE", "ONGC", "IOC", "BPCL", "GAIL", "HINDPETRO", "OIL", "PETRONET"],
        "Financial Services": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BAJFINANCE", "BAJAJFINSV"],
        "Technology": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS", "PERSISTENT"],
        "Consumer Defensive": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "TATACONSUM", "COLPAL"],
        "Basic Materials": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL", "SAIL", "NMDC"],
        "Industrials": ["LT", "BHEL", "SIEMENS", "ABB", "BEL", "HAL", "CUMMINSIND"],
        "Communication Services": ["BHARTIARTL", "RELIANCE", "IDEA", "BHARTIHEXA"],
        "Healthcare": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "BIOCON", "LUPIN", "AUROPHARMA", "TORNTPHARM"],
        "Consumer Cyclical": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "TVSMOTOR", "EICHERMOT"],
        "Utilities": ["NTPC", "POWERGRID", "ADANIPOWER", "TATAPOWER", "JSWENERGY", "NHPC"],
        "Real Estate": ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE", "PHOENIXLTD"],
    }
    peer_list = SECTOR_PEERS.get(sector or "", [])
    me = _strip_symbol(symbol)
    peer_list = [p for p in peer_list if p != me][:8]

    out = []
    for p in peer_list:
        try:
            pt = yf.Ticker(f"{p}.NS")
            info = pt.info or {}
            fast = dict(pt.fast_info or {})
            price = info.get("currentPrice") or fast.get("lastPrice")
            prev = info.get("previousClose") or fast.get("previousClose") or fast.get("regularMarketPreviousClose")
            chg_pct = ((price - prev) / prev * 100) if price and prev else None
            out.append({
                "symbol": f"{p}.NS",
                "name": info.get("shortName") or info.get("longName") or p,
                "price": _safe_float(price),
                "changePercent": chg_pct,
                "marketCap": _safe_float(info.get("marketCap") or fast.get("marketCap")),
                "peRatio": _safe_float(info.get("trailingPE")),
                "pbRatio": _safe_float(info.get("priceToBook")),
                "roe": _safe_float(info.get("returnOnEquity")),
                "profitMargin": _safe_float(info.get("profitMargins")),
                "revenueGrowth": _safe_float(info.get("revenueGrowth")),
                "dividendYield": _safe_float(info.get("dividendYield")),
            })
        except Exception:
            continue
    return out


def _safe_float(v):
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # nan
            return None
        return f
    except Exception:
        return None


def _nse_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/option-chain",
    })
    try:
        s.get("https://www.nseindia.com/option-chain", timeout=10)
    except Exception:
        pass
    return s


def get_options_chain(symbol: str) -> dict:
    """Fetch NSE options chain (equity) for the symbol with PCR computation."""
    clean = _strip_symbol(symbol)
    s = _nse_session()
    try:
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={clean}"
        r = s.get(url, timeout=12)
        if r.status_code != 200:
            return {"available": False, "error": f"HTTP {r.status_code}", "reason": "NSE rate limit or geo-block"}
        try:
            data = r.json()
        except Exception:
            return {"available": False, "error": "Non-JSON response", "reason": "NSE blocked the request"}
        if not data or not data.get("records"):
            return {"available": False, "error": "Empty response from NSE", "reason": "NSE blocks foreign IPs / rate limit. Options chain requires direct NSE access."}
        records = data.get("records", {})
        filtered = data.get("filtered", {})
        underlying = records.get("underlyingValue")
        expiry_dates = records.get("expiryDates", [])
        ce_total = filtered.get("CE", {}).get("totOI", 0)
        pe_total = filtered.get("PE", {}).get("totOI", 0)
        pcr = (pe_total / ce_total) if ce_total else None
        rows = []
        for entry in (filtered.get("data") or records.get("data") or [])[:60]:
            strike = entry.get("strikePrice")
            ce = entry.get("CE") or {}
            pe = entry.get("PE") or {}
            rows.append({
                "strike": strike,
                "ceOI": ce.get("openInterest"),
                "ceChangeOI": ce.get("changeinOpenInterest"),
                "ceLTP": ce.get("lastPrice"),
                "ceIV": ce.get("impliedVolatility"),
                "peOI": pe.get("openInterest"),
                "peChangeOI": pe.get("changeinOpenInterest"),
                "peLTP": pe.get("lastPrice"),
                "peIV": pe.get("impliedVolatility"),
            })
        if underlying:
            rows.sort(key=lambda x: abs((x["strike"] or 0) - underlying))
            rows = rows[:14]
            rows.sort(key=lambda x: x["strike"] or 0)
        return {
            "available": True,
            "underlying": underlying,
            "expiry": expiry_dates[0] if expiry_dates else None,
            "expiries": expiry_dates[:8],
            "ceTotalOI": ce_total,
            "peTotalOI": pe_total,
            "pcr": pcr,
            "rows": rows,
        }
    except Exception as e:
        logger.error(f"options chain error: {e}")
        return {"available": False, "error": str(e)}


def get_insider_transactions(symbol: str) -> list:
    """Combine yfinance insider transactions + recent Moneycontrol bulk deals."""
    sym = symbol if symbol.endswith(".NS") or symbol.endswith(".BO") else f"{symbol}.NS"
    out = []
    try:
        t = yf.Ticker(sym)
        it = t.insider_transactions
        if it is not None and not it.empty:
            for _, row in it.head(20).iterrows():
                trans = str(row.get("Transaction", "")).strip()
                if not trans:
                    text = str(row.get("Text", ""))
                    if "ale" in text.lower():
                        trans = "Sale"
                    elif "urchas" in text.lower() or "uy" in text.lower():
                        trans = "Purchase"
                    elif text:
                        trans = text.split(" at ")[0][:30]
                    else:
                        trans = "Other"
                out.append({
                    "insider": str(row.get("Insider", "")),
                    "position": str(row.get("Position", "")),
                    "transaction": trans,
                    "shares": _safe_float(row.get("Shares")),
                    "value": _safe_float(row.get("Value")),
                    "date": str(row.get("Start Date", "")).split(" ")[0],
                    "source": "Yahoo/SEC",
                })
    except Exception as e:
        logger.error(f"insider error: {e}")
    return out
