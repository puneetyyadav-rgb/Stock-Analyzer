"""Sector-level data: categorized news + sector analysis with deep-links to Trendlyne / StockEdge / Aftermarkets."""
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re
import logging
from extra_service import HEADERS, _strip_symbol, _safe_float

logger = logging.getLogger(__name__)


# Yahoo sector → Moneycontrol tag URL (uses /news/tags/SLUG.html, which renders server-side)
SECTOR_NEWS_SLUGS = {
    "Energy": ("oil-and-gas", "Oil & Gas"),
    "Financial Services": ("banking", "Banking & Finance"),
    "Technology": ("it-sector", "IT / Technology"),
    "Healthcare": ("pharma", "Pharma & Healthcare"),
    "Consumer Cyclical": ("automobile", "Auto & Auto Ancillaries"),
    "Consumer Defensive": ("fmcg", "FMCG"),
    "Basic Materials": ("metals", "Metals & Mining"),
    "Industrials": ("capital-goods", "Capital Goods"),
    "Communication Services": ("telecom", "Telecom"),
    "Utilities": ("power", "Power"),
    "Real Estate": ("real-estate", "Real Estate"),
}


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def categorize_news(news_items: list, company_name: str, sector: str) -> dict:
    """Split a news list into company / sector / market buckets using name & sector keywords."""
    if not company_name:
        company_name = ""

    # Build company keyword set
    base = company_name.lower()
    base = re.sub(r"\b(limited|ltd|corporation|corp|inc|company|industries|industries\.?)\b", "", base).strip()
    company_keywords = [kw for kw in re.split(r"[\s,&-]+", base) if len(kw) > 2]
    sector_label = (sector or "").lower()

    sector_keyword_map = {
        "energy": ["oil", "gas", "crude", "petrol", "refinery", "lng", "petroleum"],
        "financial services": ["bank", "nbfc", "rbi", "loan", "deposit", "casa", "fintech", "insurance"],
        "technology": ["it ", "software", "tech", "cloud", "saas", "infosys", "wipro", "tcs"],
        "healthcare": ["pharma", "drug", "medical", "hospital", "diagnostic", "vaccine"],
        "consumer cyclical": ["auto", "automobile", "ev ", "passenger vehicle"],
        "consumer defensive": ["fmcg", "consumer", "groceries", "retail"],
        "basic materials": ["steel", "metal", "aluminium", "copper", "iron ore", "cement"],
        "industrials": ["capital goods", "engineering", "construction", "defence"],
        "communication services": ["telecom", "5g", "spectrum", "airtel", "jio"],
        "utilities": ["power", "electricity", "energy grid"],
        "real estate": ["realty", "real estate", "housing", "property"],
    }
    sector_keywords = sector_keyword_map.get(sector_label, [])

    company = []
    sector_news = []
    market = []

    for n in news_items:
        title = (n.get("title") or "").lower()
        summary = (n.get("summary") or "").lower()
        blob = f"{title} {summary}"

        if any(kw and kw in blob for kw in company_keywords):
            company.append(n)
        elif sector_keywords and any(kw in blob for kw in sector_keywords):
            sector_news.append(n)
        else:
            market.append(n)

    return {
        "company": company,
        "sector": sector_news,
        "market": market,
        "_meta": {
            "company_keywords": company_keywords,
            "sector_label": sector_label,
            "sector_keywords": sector_keywords,
        },
    }


def get_sector_news(sector: str) -> list:
    """Fetch sector-tagged news from Moneycontrol tag pages (server-rendered)."""
    slug, _ = SECTOR_NEWS_SLUGS.get(sector or "", ("market", ""))
    url = f"https://www.moneycontrol.com/news/tags/{slug}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for li in soup.select("ul#cagetory li.clearfix")[:25]:
            a = li.select_one("h2 a") or li.select_one("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            desc = li.select_one("p")
            desc_text = desc.get_text(strip=True) if desc else ""
            date_span = li.select_one("span")
            pub = date_span.get_text(strip=True) if date_span else ""
            if title and href and len(title) > 15:
                out.append({
                    "title": title,
                    "url": href,
                    "source": "Moneycontrol · Sector",
                    "publishedAt": pub,
                    "summary": desc_text[:300],
                })
        return out
    except Exception as e:
        logger.error(f"sector news error: {e}")
        return []


# Sector → NSE sector index ticker (already exists in stock_service but mapped by Yahoo sector here)
YAHOO_TO_NSE_INDEX = {
    "Energy": ("^CNXENERGY", "NIFTY ENERGY"),
    "Financial Services": ("^NSEBANK", "NIFTY BANK"),
    "Technology": ("^CNXIT", "NIFTY IT"),
    "Healthcare": ("^CNXPHARMA", "NIFTY PHARMA"),
    "Consumer Cyclical": ("^CNXAUTO", "NIFTY AUTO"),
    "Consumer Defensive": ("^CNXFMCG", "NIFTY FMCG"),
    "Basic Materials": ("^CNXMETAL", "NIFTY METAL"),
    "Communication Services": ("^CNXMEDIA", "NIFTY MEDIA"),
    "Real Estate": ("^CNXREALTY", "NIFTY REALTY"),
    "Industrials": ("^NSEI", "NIFTY 50"),
    "Utilities": ("^NSEI", "NIFTY 50"),
}


def _index_snapshot(ticker: str, period: str = "1mo") -> dict:
    try:
        t = yf.Ticker(ticker)
        fast = dict(t.fast_info or {})
        last = _safe_float(fast.get("lastPrice") or fast.get("last_price"))
        prev = _safe_float(fast.get("previousClose") or fast.get("previous_close") or fast.get("regularMarketPreviousClose"))
        chg_pct = ((last - prev) / prev * 100) if last and prev else None
        # 1-month and YTD-ish performance
        hist = t.history(period="3mo", interval="1d", auto_adjust=True)
        perf_1m = None
        perf_3m = None
        if not hist.empty:
            closes = hist["Close"]
            if len(closes) > 20:
                perf_1m = float((closes.iloc[-1] / closes.iloc[-20] - 1) * 100)
            if len(closes) > 1:
                perf_3m = float((closes.iloc[-1] / closes.iloc[0] - 1) * 100)
        return {"price": last, "changePercent": chg_pct, "perf_1m": perf_1m, "perf_3m": perf_3m}
    except Exception as e:
        logger.error(f"index snapshot error: {e}")
        return {"price": None, "changePercent": None, "perf_1m": None, "perf_3m": None}


def get_sector_analysis(symbol: str, sector: str | None = None) -> dict:
    """Aggregate sector index performance, position vs peers, deep-links."""
    sym = symbol if symbol.endswith(".NS") or symbol.endswith(".BO") else f"{symbol}.NS"
    if not sector:
        try:
            sector = (yf.Ticker(sym).info or {}).get("sector") or ""
        except Exception:
            sector = ""

    nse_ticker, nse_label = YAHOO_TO_NSE_INDEX.get(sector or "", ("^NSEI", "NIFTY 50"))
    sector_perf = _index_snapshot(nse_ticker)
    nifty_perf = _index_snapshot("^NSEI")

    # Sector-relative outperformance (1-month)
    rel_1m = None
    if sector_perf.get("perf_1m") is not None and nifty_perf.get("perf_1m") is not None:
        rel_1m = sector_perf["perf_1m"] - nifty_perf["perf_1m"]

    clean = _strip_symbol(symbol)
    deep_links = {
        "trendlyne": f"https://trendlyne.com/equity/search/?q={clean}",
        "stockedge": f"https://web.stockedge.com/share/{clean.lower()}",
        "aftermarkets": f"https://aftermarkets.in/stock/{clean}",
        "moneycontrol_sector": f"https://www.moneycontrol.com/news/business/{SECTOR_NEWS_SLUGS.get(sector or '', ('market',''))[0]}/",
        "nse_indices": "https://www.nseindia.com/market-data/live-market-indices",
    }

    return {
        "sector": sector,
        "sector_index": {"ticker": nse_ticker, "label": nse_label, **sector_perf},
        "benchmark": {"ticker": "^NSEI", "label": "NIFTY 50", **nifty_perf},
        "relative_perf_1m": rel_1m,
        "verdict": (
            "Sector outperforming Nifty 50" if (rel_1m or 0) > 1
            else "Sector underperforming Nifty 50" if (rel_1m or 0) < -1
            else "Sector tracking Nifty 50"
        ),
        "deep_links": deep_links,
    }
