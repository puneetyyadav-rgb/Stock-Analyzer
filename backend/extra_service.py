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


def fetch_pdf_text(url: str, max_chars: int = 10000000) -> str:
    """Download a PDF and extract text. Returns empty if PDF unreachable (geo-block)."""
    try:
        from pypdf import PdfReader
        # Try with curl_cffi for better TLS fingerprint, fallback to requests
        try:
            import curl_cffi.requests as creq
            r = creq.get(url, impersonate="chrome120",
                         headers={"Referer": "https://www.bseindia.com/", "Accept": "*/*"},
                         timeout=30, allow_redirects=True)
            content = r.content
            ctype = r.headers.get("content-type", "")
        except Exception:
            r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
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



# ─── Peer Cache (disk-backed, 7-day TTL for AI-generated peer symbols) ────────
_PEER_CACHE_FILE = None

def _peer_cache_path():
    global _PEER_CACHE_FILE
    if _PEER_CACHE_FILE is None:
        import os
        base = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(base, exist_ok=True)
        _PEER_CACHE_FILE = os.path.join(base, "peer_cache.json")
    return _PEER_CACHE_FILE

def _peer_cache_get(key: str):
    import json, os, time
    try:
        path = _peer_cache_path()
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            store = json.load(f)
        entry = store.get(key)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) > 7 * 86400:  # 7-day TTL
            return None
        return entry.get("symbols")
    except Exception:
        return None

def _peer_cache_set(key: str, symbols: list):
    import json, os, time
    try:
        path = _peer_cache_path()
        store = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    store = json.load(f)
            except Exception:
                store = {}
        store[key] = {"symbols": symbols, "ts": time.time()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store, f)
    except Exception:
        pass


def _hydrate_peers(symbols: list, source: str) -> list:
    """Fetch real-time yfinance metrics for a list of bare NSE symbols. Never crashes."""
    out = []
    for p in symbols[:8]:
        try:
            sym_ns = p if p.endswith(".NS") or p.endswith(".BO") else f"{p}.NS"
            pt = yf.Ticker(sym_ns)
            info = pt.info or {}
            fast = dict(pt.fast_info or {})
            price = info.get("currentPrice") or fast.get("lastPrice")
            prev = info.get("previousClose") or fast.get("previousClose") or fast.get("regularMarketPreviousClose")
            chg_pct = ((price - prev) / prev * 100) if price and prev else None
            # Approximate P/E from price/eps when trailingPE is missing
            trailing_pe = info.get("trailingPE")
            if trailing_pe is None:
                eps = _safe_float(info.get("trailingEps"))
                if eps and eps > 0 and price:
                    trailing_pe = price / eps
            out.append({
                "symbol": sym_ns,
                "name": info.get("shortName") or info.get("longName") or p,
                "price": _safe_float(price),
                "changePercent": chg_pct,
                "marketCap": _safe_float(info.get("marketCap") or fast.get("marketCap")),
                "peRatio": _safe_float(trailing_pe),
                "pbRatio": _safe_float(info.get("priceToBook")),
                "roe": _safe_float(info.get("returnOnEquity")),
                "profitMargin": _safe_float(info.get("profitMargins")),
                "revenueGrowth": _safe_float(info.get("revenueGrowth")),
                "dividendYield": _safe_float(info.get("dividendYield")),
                "peerSource": source,
            })
        except Exception:
            continue
    return out


def _t1_screener_peers(clean_symbol: str) -> list:
    """T1: Scrape Screener.in peer comparison table using Scrapling (bypasses Cloudflare).
    Strategy:
      1. Load main company page with Scrapling Fetcher (gets session cookies + data-warehouse-id).
      2. Parse peer links from the peers section directly in the loaded HTML.
      3. If peers section is empty (JS-rendered), call Screener's internal AJAX /api/company/{id}/peers/ with session cookies.
    """
    urls = [
        f"https://www.screener.in/company/{clean_symbol}/consolidated/",
        f"https://www.screener.in/company/{clean_symbol}/",
    ]
    try:
        from scrapling import Fetcher
        fetcher = Fetcher()

        for url in urls:
            try:
                page = fetcher.get(url, timeout=15)
                if page.status != 200:
                    continue

                # Step 1: Extract data-company-id and data-warehouse-id from the page
                company_id = None
                warehouse_id = None
                info_divs = page.find_all("div", id="company-info")
                if info_divs:
                    attribs = info_divs[0].attrib
                    company_id = attribs.get("data-company-id")
                    warehouse_id = attribs.get("data-warehouse-id")

                # Step 2: Parse peer links directly from the HTML (section#peers)
                peers_found = []
                peers_section = page.find("section", id="peers")
                if peers_section:
                    for a in peers_section.find_all("a"):
                        href = a.attrib.get("href", "")
                        parts = [p for p in href.split("/") if p]
                        if len(parts) >= 2 and parts[0] == "company":
                            peer_sym = parts[1].upper()
                            if peer_sym and peer_sym != clean_symbol and peer_sym not in peers_found:
                                # Filter out index/non-equity entries (they have digits or known index names)
                                if not any(c.isdigit() for c in peer_sym) and len(peer_sym) >= 2:
                                    peers_found.append(peer_sym)

                if len(peers_found) >= 2:
                    logger.info(f"T1 Screener (HTML) peers for {clean_symbol}: {peers_found[:8]}")
                    return peers_found[:8]

                # Step 3: Fallback — hit the AJAX peers endpoint using session cookies from the fetcher
                # Screener AJAX uses company-id (not warehouse-id) as the URL key
                if company_id:
                    ajax_url = f"https://www.screener.in/api/company/{company_id}/peers/"
                    # Re-use cookies from the initial page response via Scrapling's internal session
                    ajax_resp = fetcher.get(
                        ajax_url,
                        headers={
                            "Referer": url,
                            "X-Requested-With": "XMLHttpRequest",
                            "Accept": "text/html,*/*",
                        },
                        timeout=12,
                    )
                    if ajax_resp.status == 200:
                        # Parse returned HTML fragment
                        for a in ajax_resp.find_all("a"):
                            href = a.attrib.get("href", "")
                            parts = [p for p in href.split("/") if p]
                            if len(parts) >= 2 and parts[0] == "company":
                                peer_sym = parts[1].upper()
                                if peer_sym and peer_sym != clean_symbol and peer_sym not in peers_found:
                                    if not any(c.isdigit() for c in peer_sym) and len(peer_sym) >= 2:
                                        peers_found.append(peer_sym)

                    if len(peers_found) >= 2:
                        logger.info(f"T1 Screener (AJAX) peers for {clean_symbol}: {peers_found[:8]}")
                        return peers_found[:8]

                # Step 4: Final fallback — scan ALL /company/ links on the full page (belt & suspenders)
                for a in page.find_all("a"):
                    href = a.attrib.get("href", "")
                    parts = [p for p in href.split("/") if p]
                    if len(parts) >= 2 and parts[0] == "company":
                        peer_sym = parts[1].upper()
                        if peer_sym and peer_sym != clean_symbol and peer_sym not in peers_found:
                            name_text = a.text.strip() if hasattr(a, "text") else ""
                            # Skip index/sector entries (e.g. "BSE Fast Moving Consumer Goods", "Nifty Microcap 250")
                            if (not any(c.isdigit() for c in peer_sym)
                                    and len(peer_sym) >= 2
                                    and "BSE" not in name_text.upper()[:3]
                                    and "NIFTY" not in name_text.upper()[:5]):
                                peers_found.append(peer_sym)

                if len(peers_found) >= 2:
                    logger.info(f"T1 Screener (full-page fallback) peers for {clean_symbol}: {peers_found[:8]}")
                    return peers_found[:8]

            except Exception as e:
                logger.warning(f"T1 Scrapling scrape failed ({url}): {e}")

    except ImportError:
        # Scrapling not available — fall back to original requests approach
        logger.warning("T1: Scrapling not installed. Falling back to requests.")
        for url in urls:
            try:
                r = requests.get(url, headers=HEADERS, timeout=12)
                if r.status_code != 200:
                    continue
                from bs4 import BeautifulSoup as _BS
                soup = _BS(r.text, "html.parser")
                peers_found = []
                for a in soup.select("a[href*='/company/']"):
                    href = a.get("href", "")
                    parts = [p for p in href.split("/") if p]
                    if len(parts) >= 2 and parts[0] == "company":
                        peer_sym = parts[1].upper()
                        if peer_sym and peer_sym != clean_symbol and peer_sym not in peers_found:
                            peers_found.append(peer_sym)
                if len(peers_found) >= 2:
                    return peers_found[:8]
            except Exception as e2:
                logger.warning(f"T1 requests fallback failed ({url}): {e2}")
    return []



def _t2_ai_peers(clean_symbol: str, company_name: str, sector: str, industry: str) -> list:
    """T2: Ask AI to identify exact NSE/BSE industry peers. Cached 7 days."""
    cache_key = f"ai_peers:{clean_symbol}"
    cached = _peer_cache_get(cache_key)
    if cached:
        logger.info(f"T2 AI peers for {clean_symbol} served from disk cache: {cached}")
        return cached
    try:
        from ai_service import _execute_ai_call_with_fallback
        prompt = (
            f"You are an Indian institutional equity analyst.\n"
            f"Identify the top 5 direct business competitors and closest publicly traded NSE/BSE industry peers for:\n"
            f"Symbol: {clean_symbol}.NS | Company: {company_name} | Sector: {sector} | Sub-Industry: {industry}\n\n"
            f"STRICT RULES:\n"
            f"1. Output ONLY real NSE-listed company stock ticker symbols. Nothing else.\n"
            f"2. NEVER output index names like NIFTY50, NIFTYMICRO250, NFMICRO250, BSE500, NFTYTOTMKT or any variant.\n"
            f"3. NEVER output numeric codes like 1007, 1202, or any number-only strings.\n"
            f"4. NEVER output words like SOURCE, BENCHMARK, INDEX, ETF, or fund names.\n"
            f"5. Symbols must be real listed companies competing in the same sub-industry.\n"
            f"6. Return ONLY a strict JSON array of bare uppercase NSE tickers (no .NS suffix, no explanation).\n"
            f'Example for Aquaculture/Animal Feed company: ["APEX", "WATERBASE", "GODREJAGRO", "VENKEYS", "KSE"]'
        )
        raw = _execute_ai_call_with_fallback(prompt)
        if not raw:
            return []
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
        symbols = json.loads(raw)
        if not isinstance(symbols, list):
            return []
        # Strip any .NS/.BO suffixes the model may have added
        symbols = [_strip_symbol(s) for s in symbols if isinstance(s, str)][:8]
        # Anti-hallucination filter: reject index names, numeric codes, and non-equity strings
        _REJECT_PREFIXES = ("NIFTY", "NFT", "BSE", "NSE", "SENSEX", "INDIA", "BENCHMARK")
        symbols = [
            s for s in symbols
            if s
            and s != clean_symbol
            and not s.upper().startswith(_REJECT_PREFIXES)
            and not s.isdigit()
            and not any(c.isdigit() for c in s[:3])  # reject symbols starting with digits like "1007"
            and len(s) >= 2
        ]
        _peer_cache_set(cache_key, symbols)
        logger.info(f"T2 AI peers for {clean_symbol}: {symbols}")
        return symbols
    except Exception as e:
        logger.warning(f"T2 AI peer synthesis failed for {clean_symbol}: {e}")
        return []


def _t3a_yahoo_industry_peers(clean_symbol: str, t_info: dict, me_sym: str) -> list:
    """T3A: Dynamically bucket peers by Yahoo Finance granular 'industry' field across NSE universe."""
    industry = (t_info.get("industry") or "").strip()
    if not industry:
        return []
    # Sample a broad NSE universe and find stocks sharing the exact same industry tag
    # We use yfinance search to discover similar tickers
    try:
        results = yf.search(industry, max_results=25)
        quotes = results.get("quotes", []) if isinstance(results, dict) else []
        peers_found = []
        for q in quotes:
            sym = q.get("symbol", "")
            if sym.endswith(".NS") or sym.endswith(".BO"):
                bare = _strip_symbol(sym)
                if bare != clean_symbol and bare not in peers_found:
                    # Validate same industry tag
                    try:
                        qt = yf.Ticker(sym)
                        if (qt.info or {}).get("industry", "") == industry:
                            peers_found.append(bare)
                    except Exception:
                        pass
            if len(peers_found) >= 8:
                break
        if peers_found:
            logger.info(f"T3A Yahoo industry '{industry}' peers for {clean_symbol}: {peers_found}")
        return peers_found
    except Exception as e:
        logger.warning(f"T3A Yahoo industry bucketing failed for {clean_symbol}: {e}")
        return []


def _t3b_nse_csv_peers(clean_symbol: str, t_info: dict) -> list:
    """T3B: NSE equity master CSV dynamic classification. Weekly-cached to disk."""
    import os, csv, time
    cache_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(cache_dir, exist_ok=True)
    csv_path = os.path.join(cache_dir, "nse_equity_master.csv")

    # Download NSE equity list CSV weekly
    if not os.path.exists(csv_path) or time.time() - os.path.getmtime(csv_path) > 7 * 86400:
        try:
            url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                with open(csv_path, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(r.text)
                logger.info("NSE equity master CSV refreshed.")
            else:
                logger.warning(f"NSE CSV download failed: HTTP {r.status_code}")
                if not os.path.exists(csv_path):
                    return []
        except Exception as e:
            logger.warning(f"NSE CSV fetch error: {e}")
            if not os.path.exists(csv_path):
                return []

    # Determine our stock's industry key from Yahoo (series / sector proxy)
    industry = (t_info.get("industry") or "").strip()
    sector = (t_info.get("sector") or "").strip()
    if not industry and not sector:
        return []

    try:
        # NSE CSV columns: SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE
        # We match peers by NAME pattern (industry keyword matching) since NSE CSV has no sector column
        # Use the company name words as industry proxy for keyword overlap scoring
        our_name = (t_info.get("longName") or t_info.get("shortName") or "").upper()
        name_keywords = set(w for w in re.split(r'\W+', our_name) if len(w) > 3 and w not in {"INDIA", "INDIA", "LIMITED", "LTD", "AND", "THE", "PRIVATE"})

        candidates = []
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = (row.get("SYMBOL") or "").strip().upper()
                name = (row.get("NAME OF COMPANY") or "").upper()
                series = (row.get("SERIES") or "").strip()
                if series not in ("EQ", "BE", "SM", "ST"):
                    continue
                if sym == clean_symbol:
                    continue
                overlap = sum(1 for kw in name_keywords if kw in name)
                if overlap >= 1:
                    candidates.append((overlap, sym))

        candidates.sort(key=lambda x: x[0], reverse=True)
        peers_found = [s for _, s in candidates[:8]]
        if peers_found:
            logger.info(f"T3B NSE CSV peers for {clean_symbol}: {peers_found}")
        return peers_found
    except Exception as e:
        logger.warning(f"T3B NSE CSV classification failed for {clean_symbol}: {e}")
        return []


def get_peers(symbol: str) -> list:
    """4-Tier Dynamic Peer Engine: T1 Screener.in → T2 AI Synthesizer → T3A Yahoo Industry → T3B NSE CSV.
    Zero static hardcoding. Every tier cascades into the next on failure."""
    clean = _strip_symbol(symbol)
    sym_ns = f"{clean}.NS"
    t = yf.Ticker(sym_ns)
    t_info = {}
    try:
        t_info = t.info or {}
    except Exception:
        pass

    sector = (t_info.get("sector") or "").strip()
    industry = (t_info.get("industry") or "").strip()
    company_name = t_info.get("longName") or t_info.get("shortName") or clean

    # ── T1: Screener.in Live Scraper ──────────────────────────────────────────
    peer_syms = _t1_screener_peers(clean)
    source = "T1_SCREENER_INDUSTRY"

    # ── T2: AI Dynamic Synthesizer (fallback) ─────────────────────────────────
    if not peer_syms:
        peer_syms = _t2_ai_peers(clean, company_name, sector, industry)
        source = "T2_AI_DYNAMIC_PEERS"

    # ── T3A: Yahoo Industry Tag Bucketing (fallback) ──────────────────────────
    if not peer_syms:
        peer_syms = _t3a_yahoo_industry_peers(clean, t_info, clean)
        source = "T3A_YAHOO_INDUSTRY"

    # ── T3B: NSE Equity CSV Classification (final fallback) ───────────────────
    if not peer_syms:
        peer_syms = _t3b_nse_csv_peers(clean, t_info)
        source = "T3B_NSE_CSV"

    if not peer_syms:
        logger.warning(f"All peer tiers exhausted for {clean}. Returning empty peer list.")
        return []

    logger.info(f"get_peers({clean}) resolved via {source}: {peer_syms}")
    return _hydrate_peers(peer_syms, source)




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
