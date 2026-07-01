"""Indian stock data service using yfinance + web scraping (Moneycontrol/Screener)."""
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import re
import logging
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from dateutil import parser as date_parser
from defusedxml import ElementTree as ET
from quant_service import compute_complete_quant_deck, cross_sectional_rank

logger = logging.getLogger(__name__)

_vader = SentimentIntensityAnalyzer()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def normalize_symbol(query: str) -> str:
    """Normalize Indian stock symbol to yfinance format (.NS)."""
    q = query.strip().upper().replace(" ", "")
    if q.endswith(".NS") or q.endswith(".BO"):
        return q
    return f"{q}.NS"


def _safe_float(v):
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        f = float(v)
        if f != f or f == float("inf") or f == float("-inf"):
            return None
        return f
    except Exception:
        return None


def search_stocks(query: str) -> list:
    """Search NSE listed stocks via yfinance lookup."""
    try:
        results = yf.Search(query, max_results=8).quotes
        out = []
        for r in results:
            sym = r.get("symbol", "")
            if sym.endswith(".NS") or sym.endswith(".BO") or r.get("exchange") in ("NSI", "BSE"):
                out.append({
                    "symbol": sym,
                    "name": r.get("longname") or r.get("shortname") or sym,
                    "exchange": r.get("exchange", ""),
                    "type": r.get("quoteType", ""),
                })
        return out[:8]
    except Exception as e:
        logger.error(f"search error: {e}")
        return []


def get_overview(symbol: str) -> dict:
    sym = normalize_symbol(symbol)
    t = yf.Ticker(sym)
    info = {}
    try:
        info = t.info or {}
    except Exception as e:
        logger.error(f"info error: {e}")

    fast = {}
    try:
        fast = dict(t.fast_info or {})
    except Exception:
        pass

    price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice") or fast.get("lastPrice") or fast.get("last_price"))
    prev = _safe_float(info.get("previousClose") or fast.get("previousClose") or fast.get("previous_close") or fast.get("regularMarketPreviousClose"))
    change = (price - prev) if price is not None and prev is not None else None
    change_pct = (change / prev * 100) if change is not None and prev else None

    return {
        "symbol": sym,
        "name": info.get("longName") or info.get("shortName") or sym,
        "exchange": info.get("exchange", "NSI"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency", "INR"),
        "price": price,
        "previousClose": prev,
        "change": change,
        "changePercent": change_pct,
        "dayHigh": _safe_float(info.get("dayHigh") or fast.get("dayHigh") or fast.get("day_high")),
        "dayLow": _safe_float(info.get("dayLow") or fast.get("dayLow") or fast.get("day_low")),
        "yearHigh": _safe_float(info.get("fiftyTwoWeekHigh") or fast.get("yearHigh")),
        "yearLow": _safe_float(info.get("fiftyTwoWeekLow") or fast.get("yearLow")),
        "volume": _safe_float(info.get("volume") or fast.get("lastVolume") or fast.get("last_volume")),
        "avgVolume": _safe_float(info.get("averageVolume")),
        "marketCap": _safe_float(info.get("marketCap") or fast.get("marketCap") or fast.get("market_cap")),
        "peRatio": _safe_float(info.get("trailingPE")),
        "forwardPE": _safe_float(info.get("forwardPE")),
        "pbRatio": _safe_float(info.get("priceToBook")),
        "eps": _safe_float(info.get("trailingEps")),
        "dividendYield": _safe_float(info.get("dividendYield")),
        "beta": _safe_float(info.get("beta")),
        "bookValue": _safe_float(info.get("bookValue")),
        "debtToEquity": _safe_float(info.get("debtToEquity")),
        "roe": _safe_float(info.get("returnOnEquity")),
        "roa": _safe_float(info.get("returnOnAssets")),
        "profitMargin": _safe_float(info.get("profitMargins")),
        "operatingMargin": _safe_float(info.get("operatingMargins")),
        "revenueGrowth": _safe_float(info.get("revenueGrowth")),
        "earningsGrowth": _safe_float(info.get("earningsGrowth")),
        "longBusinessSummary": info.get("longBusinessSummary"),
        "website": info.get("website"),
        "employees": info.get("fullTimeEmployees"),
        "recommendation": info.get("recommendationKey"),
        "targetMeanPrice": _safe_float(info.get("targetMeanPrice")),
        "targetHighPrice": _safe_float(info.get("targetHighPrice")),
        "targetLowPrice": _safe_float(info.get("targetLowPrice")),
        "numAnalysts": info.get("numberOfAnalystOpinions"),
    }


def get_chart(symbol: str, period: str = "1y") -> dict:
    sym = normalize_symbol(symbol)
    intervals = {"1d": "5m", "5d": "15m", "1mo": "1h", "6mo": "1d", "1y": "1d", "5y": "1wk"}
    interval = intervals.get(period, "1d")
    try:
        df = yf.Ticker(sym).history(period=period, interval=interval, auto_adjust=True)
        if df.empty:
            return {"symbol": sym, "period": period, "data": []}
        df = df.reset_index()
        date_col = "Datetime" if "Datetime" in df.columns else "Date"
        data = []
        for _, row in df.iterrows():
            data.append({
                "date": str(row[date_col]),
                "open": _safe_float(row.get("Open")),
                "high": _safe_float(row.get("High")),
                "low": _safe_float(row.get("Low")),
                "close": _safe_float(row.get("Close")),
                "volume": _safe_float(row.get("Volume")),
            })
        return {"symbol": sym, "period": period, "data": data}
    except Exception as e:
        logger.error(f"chart error: {e}")
        return {"symbol": sym, "period": period, "data": []}


def _is_live_partial_bar(df) -> bool:
    """True if the last daily bar is today's still-forming candle (IST session not yet settled)."""
    try:
        last = df.index[-1]
        last_date = last.date() if hasattr(last, "date") else None
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        return last_date == now_ist.date() and (now_ist.hour * 60 + now_ist.minute) < 940  # before 15:40 IST
    except Exception:
        return False


def compute_technicals(symbol: str) -> dict:
    sym = normalize_symbol(symbol)
    try:
        # auto_adjust=False → raw Close (price levels a trader compares to the broker chart) PLUS
        # Adj Close (total-return series) so split/dividend jumps don't distort return-based stats.
        df = yf.Ticker(sym).history(period="1y", interval="1d", auto_adjust=False)
        if df.empty or len(df) < 30:
            return {}
        df = df.dropna(subset=["Close"])
        current_price_display = float(df["Close"].iloc[-1])   # live price (may be today's partial bar)
        # Analytics run on COMPLETED bars only — strip today's live candle so RVOL/pivots/bands aren't
        # computed off a mid-session bar (RVOL especially reads artificially low intraday otherwise).
        a = df.iloc[:-1] if _is_live_partial_bar(df) else df
        close = a["Adj Close"] if "Adj Close" in a.columns else a["Close"]   # adjusted → indicators
        # RSI 14
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        # SMA
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean() if len(close) >= 200 else None
        # Support/resistance on RAW completed prices (the levels a trader actually sees on the chart)
        raw_close = a["Close"]
        support = float(raw_close.tail(60).min())
        resistance = float(raw_close.tail(60).max())
        cur = float(close.iloc[-1])   # last COMPLETED adjusted close (for trend/RS comparisons)
        rsi_val = _safe_float(rsi.iloc[-1])
        signal_text = "Neutral"
        if rsi_val and rsi_val > 70:
            signal_text = "Overbought"
        elif rsi_val and rsi_val < 30:
            signal_text = "Oversold"

        nifty_df = yf.Ticker("^NSEI").history(period="6mo", interval="1d", auto_adjust=True)
        rs_data = {}
        if not nifty_df.empty and len(nifty_df) >= 60 and len(close) >= 60:
            nifty_close = nifty_df["Close"]
            stock_1m = (cur - float(close.iloc[-21])) / float(close.iloc[-21]) * 100 if len(close) >= 21 else 0
            nifty_1m = (float(nifty_close.iloc[-1]) - float(nifty_close.iloc[-21])) / float(nifty_close.iloc[-21]) * 100 if len(nifty_close) >= 21 else 0
            stock_3m = (cur - float(close.iloc[-60])) / float(close.iloc[-60]) * 100 if len(close) >= 60 else 0
            nifty_3m = (float(nifty_close.iloc[-1]) - float(nifty_close.iloc[-60])) / float(nifty_close.iloc[-60]) * 100 if len(nifty_close) >= 60 else 0
            rs_data = {
                "stock_1m_pct": _safe_float(stock_1m),
                "nifty_1m_pct": _safe_float(nifty_1m),
                "outperformance_1m": _safe_float(stock_1m - nifty_1m),
                "stock_3m_pct": _safe_float(stock_3m),
                "nifty_3m_pct": _safe_float(nifty_3m),
                "outperformance_3m": _safe_float(stock_3m - nifty_3m)
            }

        ohlcv_dict = {
            "open": a["Open"].tolist() if "Open" in a.columns else [],
            "high": a["High"].tolist() if "High" in a.columns else [],
            "low": a["Low"].tolist() if "Low" in a.columns else [],
            "close": a["Close"].tolist() if "Close" in a.columns else [],          # RAW → levels
            "adj_close": a["Adj Close"].tolist() if "Adj Close" in a.columns else a["Close"].tolist(),
            "volume": a["Volume"].tolist() if "Volume" in a.columns else [],
        }

        # Live order-flow (Kotak Level-2) + official NSE bhavcopy context. Best-effort: any failure
        # degrades gracefully (the deck still computes, just without that factor).
        depth = delivery = cross = integrity = None
        try:
            import kotak_service as ks
            depth = ks._fetch_depth_sync(sym)
        except Exception as e:
            logger.info(f"depth fetch skipped for {sym}: {e}")
        try:
            import bhavcopy_service as bhav
            delivery = bhav.delivery_signal(sym)
            cross = cross_sectional_rank(sym, bhav.universe_factors())
            comp_date = a.index[-1].date() if hasattr(a.index[-1], "date") else None
            integrity = bhav.cross_check(
                sym, float(a["Close"].iloc[-1]),
                float(a["Volume"].iloc[-1]) if "Volume" in a.columns else None, comp_date)
        except Exception as e:
            logger.info(f"bhavcopy context skipped for {sym}: {e}")

        quant_deck = compute_complete_quant_deck(sym, ohlcv_dict, kotak_depth=depth,
                                                 delivery=delivery, cross_sectional=cross)
        if isinstance(quant_deck, dict):
            quant_deck["dataIntegrity"] = integrity

        return {
            "currentPrice": _safe_float(current_price_display),
            "rsi": rsi_val,
            "rsiSignal": signal_text,
            "macd": _safe_float(macd.iloc[-1]),
            "macdSignal": _safe_float(signal.iloc[-1]),
            "macdHistogram": _safe_float(macd.iloc[-1] - signal.iloc[-1]),
            "sma50": _safe_float(sma50.iloc[-1]) if sma50 is not None else None,
            "sma200": _safe_float(sma200.iloc[-1]) if sma200 is not None and not sma200.empty else None,
            "support": _safe_float(support),
            "resistance": _safe_float(resistance),
            "trend": "Uptrend" if cur > (_safe_float(sma50.iloc[-1]) or 0) else "Downtrend",
            "relativeStrength": rs_data,
            "quantDeck": quant_deck,
        }
    except Exception as e:
        logger.error(f"technicals error: {e}")
        return {}


def get_financials(symbol: str) -> dict:
    sym = normalize_symbol(symbol)
    t = yf.Ticker(sym)
    out = {"quarterly": [], "annual": [], "balanceSheet": [], "cashFlow": []}
    try:
        q = t.quarterly_financials
        if q is not None and not q.empty:
            for col in q.columns[:6]:
                row = q[col]
                out["quarterly"].append({
                    "period": str(col.date()) if hasattr(col, "date") else str(col),
                    "revenue": _safe_float(row.get("Total Revenue")),
                    "operatingIncome": _safe_float(row.get("Operating Income")),
                    "netIncome": _safe_float(row.get("Net Income")),
                    "ebitda": _safe_float(row.get("EBITDA")),
                    "grossProfit": _safe_float(row.get("Gross Profit")),
                })
    except Exception as e:
        logger.error(f"q fin error: {e}")
    try:
        a = t.financials
        if a is not None and not a.empty:
            for col in a.columns[:4]:
                row = a[col]
                out["annual"].append({
                    "period": str(col.date()) if hasattr(col, "date") else str(col),
                    "revenue": _safe_float(row.get("Total Revenue")),
                    "netIncome": _safe_float(row.get("Net Income")),
                    "ebitda": _safe_float(row.get("EBITDA")),
                })
    except Exception:
        pass
    try:
        bs = t.balance_sheet
        if bs is not None and not bs.empty:
            for col in bs.columns[:4]:
                row = bs[col]
                out["balanceSheet"].append({
                    "period": str(col.date()) if hasattr(col, "date") else str(col),
                    "totalAssets": _safe_float(row.get("Total Assets")),
                    "totalDebt": _safe_float(row.get("Total Debt")),
                    "totalEquity": _safe_float(row.get("Stockholders Equity") or row.get("Total Stockholder Equity")),
                    "cash": _safe_float(row.get("Cash And Cash Equivalents")),
                })
    except Exception:
        pass
    try:
        cf = t.cashflow
        if cf is not None and not cf.empty:
            for col in cf.columns[:4]:
                row = cf[col]
                out["cashFlow"].append({
                    "period": str(col.date()) if hasattr(col, "date") else str(col),
                    "operatingCashFlow": _safe_float(row.get("Operating Cash Flow")),
                    "freeCashFlow": _safe_float(row.get("Free Cash Flow")),
                    "capex": _safe_float(row.get("Capital Expenditure")),
                })
    except Exception:
        pass
    return out


def get_corporate_actions(symbol: str) -> dict:
    sym = normalize_symbol(symbol)
    t = yf.Ticker(sym)
    out = {"dividends": [], "splits": []}
    try:
        d = t.dividends
        if d is not None and not d.empty:
            for date, val in d.tail(10).items():
                out["dividends"].append({"date": str(date.date()), "amount": _safe_float(val)})
            out["dividends"].reverse()
    except Exception:
        pass
    try:
        s = t.splits
        if s is not None and not s.empty:
            for date, val in s.tail(10).items():
                out["splits"].append({"date": str(date.date()), "ratio": _safe_float(val)})
            out["splits"].reverse()
    except Exception:
        pass
    return out


def get_holders(symbol: str) -> dict:
    sym = normalize_symbol(symbol)
    t = yf.Ticker(sym)
    out = {"institutional": [], "majorHoldersBreakdown": {}, "insiderTransactions": []}
    try:
        ih = t.institutional_holders
        if ih is not None and not ih.empty:
            for _, row in ih.head(10).iterrows():
                out["institutional"].append({
                    "holder": str(row.get("Holder", "")),
                    "shares": _safe_float(row.get("Shares")),
                    "percent": _safe_float(row.get("pctHeld")),
                    "value": _safe_float(row.get("Value")),
                })
    except Exception:
        pass
    try:
        mh = t.major_holders
        if mh is not None and not mh.empty:
            # New schema: index = breakdown label, column = "Value"
            for idx, row in mh.iterrows():
                key = str(idx)
                val = row.get("Value")
                if val is None:
                    continue
                # convert decimals to percent for *PercentHeld keys
                if "Percent" in key:
                    out["majorHoldersBreakdown"][key] = f"{float(val) * 100:.2f}%"
                elif "Count" in key:
                    out["majorHoldersBreakdown"][key] = f"{int(float(val))}"
                else:
                    out["majorHoldersBreakdown"][key] = str(val)
    except Exception as e:
        logger.error(f"major_holders parse: {e}")
    try:
        it = t.insider_transactions
        if it is not None and not it.empty:
            for _, row in it.head(10).iterrows():
                out["insiderTransactions"].append({
                    "insider": str(row.get("Insider", "")),
                    "transaction": str(row.get("Transaction", "")),
                    "shares": _safe_float(row.get("Shares")),
                    "value": _safe_float(row.get("Value")),
                    "date": str(row.get("Start Date", "")),
                })
    except Exception:
        pass
    return out


NEWS_PUBLISHER_DOMAINS = (
    "economictimes.indiatimes.com",
    "timesofindia.indiatimes.com",
    "livemint.com",
    "business-standard.com",
    "businesstoday.in",
    "cnbctv18.com",
    "ndtvprofit.com",
    "reuters.com",
)


def _parse_news_datetime(value):
    """Return a timezone-aware publication time, or None for unknown dates."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        try:
            dt = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            try:
                dt = date_parser.parse(text)
            except (TypeError, ValueError, OverflowError):
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_relevant_headline(title: str, terms: list[str]) -> bool:
    lowered = title.lower()
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", lowered)
        for term in terms if term
    )


def _google_news_items(query: str, limit: int = 30, relevance_terms=None) -> list:
    """Fetch Google News RSS results for an India-focused stock query."""
    url = (
        "https://news.google.com/rss/search?q=" + quote_plus(query) +
        "&hl=en-IN&gl=IN&ceid=IN:en"
    )
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = []
        for node in root.findall("./channel/item")[:limit]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            source_node = node.find("source")
            source = (source_node.text or "Google News").strip() if source_node is not None else "Google News"
            if title.endswith(f" - {source}"):
                title = title[:-(len(source) + 3)].strip()
            if not title or not link:
                continue
            if relevance_terms and not _is_relevant_headline(title, relevance_terms):
                continue
            items.append({
                "title": title,
                "url": link,
                "source": source,
                "publishedAt": (node.findtext("pubDate") or "").strip(),
                "summary": "",
            })
        return items
    except Exception as exc:
        logger.warning("Google News RSS error for %r: %s", query, exc)
        return []


def _finalize_news(items: list, limit: int = 60) -> list:
    """Normalize dates, remove duplicate headlines, and sort newest first."""
    unique = []
    seen = set()
    for item in items:
        title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
        if not title:
            continue
        dedupe_key = re.sub(r"[^a-z0-9]+", "", title.lower())
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized = dict(item)
        normalized["title"] = title
        published = _parse_news_datetime(normalized.get("publishedAt"))
        normalized["publishedAt"] = published.isoformat() if published else ""
        normalized["_publishedTs"] = published.timestamp() if published else 0
        unique.append(normalized)
    unique.sort(key=lambda item: item["_publishedTs"], reverse=True)
    for item in unique:
        item.pop("_publishedTs", None)
    return _score_news(unique[:limit])


def get_news(symbol: str) -> list:
    """Aggregate stock news from Yahoo, Moneycontrol, and Indian publishers."""
    sym = normalize_symbol(symbol)
    news_items = []
    clean_symbol = sym.replace(".NS", "").replace(".BO", "")
    company_name = clean_symbol
    industry_name = ""

    # Yahoo Finance news via yfinance
    try:
        t = yf.Ticker(sym)
        try:
            info = t.info or {}
            company_name = info.get("shortName") or company_name
            industry_name = info.get("industry") or info.get("sector") or ""
        except Exception:
            industry_name = ""
            pass
        for n in (t.news or [])[:15]:
            content = n.get("content", n)
            title = content.get("title") or n.get("title")
            if not title:
                continue
            link = (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else content.get("clickThroughUrl", {}).get("url") if isinstance(content.get("clickThroughUrl"), dict) else n.get("link")
            provider = content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else n.get("publisher", "")
            pub_date = content.get("pubDate") or n.get("providerPublishTime")
            news_items.append({
                "title": title,
                "url": link or "",
                "source": provider or "Yahoo Finance",
                "publishedAt": str(pub_date) if pub_date else "",
                "summary": content.get("summary", "")[:300],
            })
    except Exception as e:
        logger.error(f"yahoo news error: {e}")

    # Yahoo's quote search is a reliable fallback when ticker.info has no name.
    if company_name == clean_symbol:
        try:
            quotes = yf.Search(clean_symbol, max_results=8).quotes
            exact = next((q for q in quotes if q.get("symbol") == sym), None)
            match = exact or next((q for q in quotes if q.get("symbol") == clean_symbol), None)
            if match:
                company_name = match.get("longname") or match.get("shortname") or company_name
        except Exception as exc:
            logger.warning("Yahoo company-name lookup error for %s: %s", clean_symbol, exc)

    # Moneycontrol scraping
    try:
        clean_name = sym.replace(".NS", "").replace(".BO", "")
        url = f"https://www.moneycontrol.com/news/tags/{clean_name.lower()}.html"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for li in soup.select("ul#cagetory li.clearfix")[:10]:
                a = li.select_one("h2 a") or li.select_one("a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                href = a.get("href", "")
                desc = li.select_one("p")
                desc_text = desc.get_text(strip=True) if desc else ""
                date_span = li.select_one("span")
                pub = date_span.get_text(strip=True) if date_span else ""
                if title and href:
                    news_items.append({
                        "title": title,
                        "url": href,
                        "source": "Moneycontrol",
                        "publishedAt": pub,
                        "summary": desc_text[:300],
                    })
    except Exception as e:
        logger.error(f"moneycontrol news error: {e}")

    legal_suffixes = {"limited", "ltd", "plc", "inc", "corporation", "corp", "company"}
    company_terms = [
        token for token in re.findall(r"[A-Za-z0-9&]+", company_name)
        if len(token) >= 2 and token.lower() not in legal_suffixes
    ]
    relevance_terms = list(dict.fromkeys([clean_symbol, *company_terms]))
    primary_name = " ".join(company_terms) or company_name
    stock_query = f'("{primary_name}" OR "{clean_symbol}") stock when:30d'
    news_items.extend(_google_news_items(stock_query, 40, relevance_terms))

    publisher_filter = " OR ".join(f"site:{domain}" for domain in NEWS_PUBLISHER_DOMAINS)
    publisher_query = f'("{primary_name}" OR "{clean_symbol}") ({publisher_filter}) when:60d'
    news_items.extend(_google_news_items(publisher_query, 40, relevance_terms))

    if industry_name:
        industry_query = f'"{industry_name}" (industry OR sector OR market OR prices) India when:14d'
        news_items.extend(_google_news_items(industry_query, 10, []))

    return _finalize_news(news_items)


def _score_news(items: list) -> list:
    """Add VADER sentiment to each news item in place."""
    for it in items:
        title = it.get("title", "")
        try:
            score = _vader.polarity_scores(title)["compound"]
        except Exception:
            score = 0.0
        it["sentimentScore"] = round(score, 3)
        it["sentimentLabel"] = "Positive" if score > 0.15 else "Negative" if score < -0.15 else "Neutral"
    return items


def get_screener_data(symbol: str) -> dict:
    """Scrape additional ratios + management commentary from Screener.in."""
    sym = normalize_symbol(symbol)
    clean = sym.replace(".NS", "").replace(".BO", "")
    out = {"ratios": {}, "pros": [], "cons": [], "about": "", "promoterPledge": None}
    try:
        url = f"https://www.screener.in/company/{clean}/consolidated/"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            url = f"https://www.screener.in/company/{clean}/"
            r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            # ratios
            for li in soup.select("#top-ratios li"):
                name_el = li.select_one("span.name")
                val_el = li.select_one("span.value")
                if name_el and val_el:
                    out["ratios"][name_el.get_text(strip=True)] = val_el.get_text(" ", strip=True)
            # pros & cons
            pros_section = soup.select_one(".pros ul")
            if pros_section:
                out["pros"] = [li.get_text(strip=True) for li in pros_section.select("li")]
            cons_section = soup.select_one(".cons ul")
            if cons_section:
                out["cons"] = [li.get_text(strip=True) for li in cons_section.select("li")]
            # about
            about = soup.select_one(".company-profile .about")
            if about:
                out["about"] = about.get_text(" ", strip=True)[:1000]
            # Promoter pledge — look in the shareholding table for "Pledged" row
            txt = soup.get_text(" ", strip=True)
            m = re.search(r"Pledged[^\d%]*([\d.]+)\s*%", txt, re.I)
            if m:
                try:
                    out["promoterPledge"] = float(m.group(1))
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"screener error: {e}")
    return out


SPECIAL_KEYWORDS = {
    "succession": "Succession/Leadership",
    "founder health": "Founder Health",
    "ceo health": "Founder Health",
    "data breach": "Cybersecurity",
    "ransomware": "Cybersecurity",
    "cyberattack": "Cybersecurity",
    "cyber attack": "Cybersecurity",
    "phishing": "Cybersecurity",
}


def get_special_news_tags(news_items: list) -> list:
    """Surface news headlines matching special-event keywords (succession / cybersecurity etc.)."""
    flagged = []
    for n in news_items:
        title = (n.get("title") or "").lower()
        summary = (n.get("summary") or "").lower()
        blob = f"{title} {summary}"
        for kw, tag in SPECIAL_KEYWORDS.items():
            if kw in blob:
                flagged.append({
                    "tag": tag,
                    "keyword": kw,
                    "title": n.get("title"),
                    "url": n.get("url"),
                    "source": n.get("source"),
                })
                break
    return flagged


def get_macro_snapshot() -> dict:
    """Macro indicators relevant to Indian markets."""
    tickers = {
        "NIFTY 50": "^NSEI",
        "SENSEX": "^BSESN",
        "BANK NIFTY": "^NSEBANK",
        "NIFTY IT": "^CNXIT",
        "USD/INR": "INR=X",
        "DXY": "DX-Y.NYB",
        "CRUDE OIL": "CL=F",
        "GOLD": "GC=F",
        "US 10Y YIELD": "^TNX",
        "VIX INDIA": "^INDIAVIX",
        "DOW JONES": "^DJI",
        "NASDAQ": "^IXIC",
    }
    snapshot = []
    for name, sym in tickers.items():
        try:
            t = yf.Ticker(sym)
            fast = dict(t.fast_info or {})
            last = _safe_float(fast.get("lastPrice") or fast.get("last_price"))
            prev = _safe_float(fast.get("previousClose") or fast.get("previous_close") or fast.get("regularMarketPreviousClose"))
            chg_pct = ((last - prev) / prev * 100) if last and prev else None
            snapshot.append({
                "name": name,
                "symbol": sym,
                "price": last,
                "change": (last - prev) if last and prev else None,
                "changePercent": chg_pct,
            })
        except Exception:
            snapshot.append({"name": name, "symbol": sym, "price": None, "change": None, "changePercent": None})
    return {"indicators": snapshot, "updatedAt": datetime.now(timezone.utc).isoformat()}


def get_sector_performance() -> list:
    sectors = {
        "Auto": "^CNXAUTO",
        "Bank": "^NSEBANK",
        "FMCG": "^CNXFMCG",
        "IT": "^CNXIT",
        "Metal": "^CNXMETAL",
        "Pharma": "^CNXPHARMA",
        "Realty": "^CNXREALTY",
        "Energy": "^CNXENERGY",
        "Media": "^CNXMEDIA",
        "PSU Bank": "^CNXPSUBANK",
    }
    out = []
    for name, sym in sectors.items():
        try:
            t = yf.Ticker(sym)
            fast = dict(t.fast_info or {})
            last = _safe_float(fast.get("lastPrice") or fast.get("last_price"))
            prev = _safe_float(fast.get("previousClose") or fast.get("previous_close") or fast.get("regularMarketPreviousClose"))
            chg_pct = ((last - prev) / prev * 100) if last and prev else None
            out.append({"name": name, "symbol": sym, "price": last, "changePercent": chg_pct})
        except Exception:
            out.append({"name": name, "symbol": sym, "price": None, "changePercent": None})
    return out


def get_full_analysis(symbol: str) -> dict:
    """Aggregate everything for a stock."""
    overview = get_overview(symbol)
    technicals = compute_technicals(symbol)
    financials = get_financials(symbol)
    corporate = get_corporate_actions(symbol)
    holders = get_holders(symbol)
    news = get_news(symbol)
    screener = get_screener_data(symbol)
    return {
        "overview": overview,
        "technicals": technicals,
        "financials": financials,
        "corporate": corporate,
        "holders": holders,
        "news": news,
        "screener": screener,
    }
