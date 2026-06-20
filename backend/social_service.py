"""Social sentiment: Reddit (free, non-commercial) + StockTwits (free, limited India coverage)."""
import os
import logging
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from extra_service import HEADERS, _strip_symbol

logger = logging.getLogger(__name__)

REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = "StockSentinelIN/1.0 (personal, non-commercial use)"

_analyzer = SentimentIntensityAnalyzer()


def get_reddit_sentiment(company_name: str) -> dict:
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return {
            "available": False,
            "reason": "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not configured. Create a free Reddit script app at reddit.com/prefs/apps and set both env vars in /app/backend/.env to enable.",
        }
    try:
        import praw
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        posts = []
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
        if not posts:
            return {"available": True, "mention_count": 0, "sentiment": "No mentions found"}
        scores = [_analyzer.polarity_scores(p["title"])["compound"] for p in posts]
        avg = sum(scores) / len(scores)
        label = "Bullish" if avg > 0.15 else "Bearish" if avg < -0.15 else "Mixed/Neutral"
        return {
            "available": True,
            "mention_count": len(posts),
            "avg_sentiment_score": round(avg, 3),
            "sentiment": label,
            "top_posts": sorted(posts, key=lambda p: p["score"], reverse=True)[:5],
        }
    except Exception as e:
        logger.error(f"reddit error: {e}")
        return {"available": False, "error": str(e)}


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
