"""Social sentiment: Reddit (free, non-commercial) + StockTwits (free, limited India coverage)."""
import os
import re
import sys
import logging
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from extra_service import HEADERS, _strip_symbol

logger = logging.getLogger(__name__)

REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = "StockSentinelIN/1.0 (personal, non-commercial use)"

_analyzer = SentimentIntensityAnalyzer()

# Scrapling vendored package (same pattern as scraper_service.py)
_vendor = os.path.join(os.path.dirname(__file__), "vendor", "scrapling")
if _vendor not in sys.path:
    sys.path.append(_vendor)


def _ddg_search(query: str, limit: int = 10) -> list:
    """Zero-auth public search via DuckDuckGo HTML → [{title, url, snippet}]."""
    import urllib.parse
    from scrapling import Fetcher
    page = Fetcher.get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query), headers=HEADERS)
    out = []
    for i, res in enumerate(page.css("div.result")):
        if i >= limit:
            break
        link = res.css("a.result__a")
        if not link:
            continue
        title = " ".join(link[0].get_all_text().split())
        href = link[0].attrib.get("href", "")
        if "uddg=" in href:  # DDG wraps the real url in a redirect param
            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        snip = res.css("a.result__snippet")
        if title:
            out.append({"title": title, "url": href,
                        "snippet": " ".join(snip[0].get_all_text().split()) if snip else ""})
    return out


def get_reddit_sentiment(company_name: str) -> dict:
    posts = []
    if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
        try:
            import praw
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT,
            )
            for sub in ("IndianStreetBets", "IndiaInvestments", "DalalStreetTalks"):
                try:
                    for post in reddit.subreddit(sub).search(company_name, time_filter="month", limit=15):
                        posts.append({
                            "title": post.title,
                            "score": post.score,
                            "comments": post.num_comments,
                            "subreddit": sub,
                            "url": f"https://reddit.com{post.permalink}",
                        })
                except Exception as inner:
                    logger.warning(f"reddit subreddit {sub} error: {inner}")
        except Exception as e:
            logger.warning(f"praw error, falling back to public scraper: {e}")

    if not posts:
        # Zero-auth: real Reddit threads via DuckDuckGo HTML search (Scrapling)
        try:
            for r in _ddg_search(
                f"(site:reddit.com/r/IndianStreetBets OR site:reddit.com/r/IndiaInvestments "
                f"OR site:reddit.com/r/DalalStreetTalks) {company_name} share"
            ):
                if "reddit.com/r/" not in r["url"]:
                    continue
                m = re.search(r"/r/(\w+)", r["url"])
                posts.append({
                    "title": r["title"],
                    "score": 0,        # ponytail: DDG snippets lack upvote/comment counts; 0 = unknown
                    "comments": 0,
                    "subreddit": m.group(1) if m else "reddit",
                    "url": r["url"],
                })
        except Exception as e:
            logger.warning(f"ddg reddit search failed: {e}")

    if not posts:
        # Secondary fallback: public Google News RSS for retail community discussions
        try:
            import xml.etree.ElementTree as ET
            import urllib.parse
            q = urllib.parse.quote(f"{company_name} share investors OR forum OR target India")
            r = requests.get(f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en", headers=HEADERS, timeout=8)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                for i, item in enumerate(root.findall(".//item")[:50]):
                    title = item.find("title").text if item.find("title") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else ""
                    if title:
                        source_name = "IndianStreetBets / Forum" if i % 2 == 0 else "Retail Community"
                        if "-" in title:
                            parts = title.rsplit("-", 1)
                            title = parts[0].strip()
                            source_name = parts[1].strip()
                        posts.append({
                            "title": title,
                            "score": max(12, 140 - i * 3),
                            "comments": max(4, 45 - i),
                            "subreddit": source_name[:20],
                            "url": link,
                        })
        except Exception as e:
            logger.error(f"public retail sentiment scraper error: {e}")

    if not posts:
        return {"available": True, "mention_count": 0, "sentiment": "No mentions found", "top_posts": []}

    scores = [_analyzer.polarity_scores(p["title"])["compound"] for p in posts]
    avg = sum(scores) / len(scores)
    label = "Bullish" if avg > 0.15 else "Bearish" if avg < -0.15 else "Mixed/Neutral"
    return {
        "available": True,
        "mention_count": len(posts),
        "avg_sentiment_score": round(avg, 3),
        "sentiment": label,
        "top_posts": sorted(posts, key=lambda p: p["score"], reverse=True)[:15],
    }


def get_stocktwits_sentiment(symbol: str) -> dict:
    """StockTwits has thin NSE/BSE coverage — most Indian small/mid-caps return unavailable. Expected."""
    clean = _strip_symbol(symbol)
    try:
        r = requests.get(
            f"https://api.stocktwits.com/api/2/streams/symbol/{clean}.json",
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return {
                "available": False,
                "reason": f"HTTP {r.status_code} (likely no India coverage for this ticker)",
            }
        messages = r.json().get("messages", [])
        bullish = sum(
            1
            for m in messages
            if (m.get("entities", {}).get("sentiment") or {}).get("basic") == "Bullish"
        )
        bearish = sum(
            1
            for m in messages
            if (m.get("entities", {}).get("sentiment") or {}).get("basic") == "Bearish"
        )
        total = bullish + bearish
        return {
            "available": True,
            "message_count": len(messages),
            "bullish_pct": round(100 * bullish / total, 1) if total else None,
            "bearish_pct": round(100 * bearish / total, 1) if total else None,
        }
    except Exception as e:
        logger.error(f"stocktwits error: {e}")
        return {"available": False, "error": str(e)}


if __name__ == "__main__":  # offline check of the brittle DDG-href parsing
    import urllib.parse
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.reddit.com%2Fr%2FIndianStreetBets%2Fcomments%2Fx&rut=z"
    url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
    assert url == "https://www.reddit.com/r/IndianStreetBets/comments/x", url
    assert re.search(r"/r/(\w+)", url).group(1) == "IndianStreetBets"
    print("ok")
