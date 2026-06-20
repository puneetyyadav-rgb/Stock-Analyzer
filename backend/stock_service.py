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


def compute_technicals(symbol: str) -> dict:
    sym = normalize_symbol(symbol)
    try:
        df = yf.Ticker(sym).history(period="6mo", interval="1d", auto_adjust=True)
        if df.empty or len(df) < 30:
            return {}
        close = df["Close"]
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
        # Support/resistance approximations (recent 6m)
        support = float(close.tail(60).min())
        resistance = float(close.tail(60).max())
        cur = float(close.iloc[-1])
        rsi_val = _safe_float(rsi.iloc[-1])
        signal_text = "Neutral"
        if rsi_val and rsi_val > 70:
            signal_text = "Overbought"
        elif rsi_val and rsi_val < 30:
            signal_text = "Oversold"

        return {
            "currentPrice": _safe_float(cur),
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


def get_news(symbol: str) -> list:
    """Scrape news from Yahoo Finance + Moneycontrol search."""
    sym = normalize_symbol(symbol)
    news_items = []

    # Yahoo Finance news via yfinance
    try:
        t = yf.Ticker(sym)
        for n in (t.news or [])[:15]:
            content = n.get("content", n)
            title = content.get("title") or n.get("title")
            if not title:
                continue
            link = (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else content.get("clickThroughUrl", {}).get("url") if isinstance(content.get("clickThroughUrl"), dict) else n.get("link")
            provider = content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else n.get("publisher", "")
            pub_date = content.get("pubDate") or n.get("providerPublishTime")
            if isinstance(pub_date, int):
                pub_date = datetime.fromtimestamp(pub_date, tz=timezone.utc).isoformat()
            news_items.append({
                "title": title,
                "url": link or "",
                "source": provider or "Yahoo Finance",
                "publishedAt": str(pub_date) if pub_date else "",
                "summary": content.get("summary", "")[:300],
            })
    except Exception as e:
        logger.error(f"yahoo news error: {e}")

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

    return _score_news(news_items[:25])


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
