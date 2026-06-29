import os
import logging
from twikit import Client
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

_vader = SentimentIntensityAnalyzer()

async def get_twitter_sentiment(symbol: str) -> dict:
    auth_token = os.getenv("TWITTER_AUTH_TOKEN")
    ct0 = os.getenv("TWITTER_CT0")
    clean_sym = symbol.replace('.NS', '').replace('.BO', '')
    query = f"${clean_sym}"
    results = []

    if auth_token and ct0:
        try:
            import asyncio
            import json
            process = await asyncio.create_subprocess_exec(
                "node", "twitter_node.mjs", query,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(__file__)
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                output = stdout.decode().strip()
                json_str = output.split('\n')[-1]
                data = json.loads(json_str)
                tweets = data.get("tweets", [])
                for t in tweets:
                    text = t.get('text', '')
                    if not text or "telegram" in text.lower() or "whatsapp" in text.lower():
                        continue
                    score = _vader.polarity_scores(text)["compound"]
                    user = t.get('user', {})
                    results.append({
                        "author": user.get('name', 'Unknown'),
                        "handle": user.get('screen_name', 'unknown'),
                        "text": text,
                        "createdAt": t.get('created_at', ''),
                        "sentimentScore": round(score, 3),
                        "sentimentLabel": "Bullish" if score > 0.15 else "Bearish" if score < -0.15 else "Neutral"
                    })
                if results:
                    return {"query": query, "tweets": results}
        except Exception as e:
            logger.warning(f"Twitter node scraper failed, using public fallback: {e}")

    # Zero-auth: indexed tweets via DuckDuckGo (X de-indexes heavily — best-effort, RSS below covers gaps)
    try:
        import asyncio, re
        from social_service import _ddg_search
        ddg = await asyncio.to_thread(_ddg_search, f'(site:twitter.com OR site:x.com) "{clean_sym}" stock')
        for r in ddg:
            text = r["title"] + (". " + r["snippet"] if r.get("snippet") else "")
            low = text.lower()
            if not text or any(s in low for s in ("telegram", "whatsapp", "sure shot", "paid tip")):
                continue
            score = _vader.polarity_scores(text)["compound"]
            m = re.search(r"(?:twitter|x)\.com/([^/?#]+)", r["url"])
            handle = m.group(1) if m else "unknown"
            results.append({
                "author": handle,
                "handle": handle,
                "text": text[:280],
                "createdAt": "Recent",
                "sentimentScore": round(score, 3),
                "sentimentLabel": "Bullish" if score > 0.15 else "Bearish" if score < -0.15 else "Neutral",
            })
        if results:
            return {"query": query, "tweets": results}
    except Exception as e:
        logger.warning(f"ddg twitter search failed: {e}")

    # Secondary fallback: live public sentiment via Google News RSS search
    try:
        import asyncio
        import requests
        import xml.etree.ElementTree as ET
        import urllib.parse

        def fetch_public_sentiment():
            q = urllib.parse.quote(f"{clean_sym} share price targets OR breakout OR sentiment OR twitter OR x.com India")
            url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            items = []
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                for idx, item in enumerate(root.findall(".//item")[:50]):
                    title = item.find("title").text if item.find("title") is not None else ""
                    pubDate = item.find("pubDate").text if item.find("pubDate") is not None else "Recent"
                    if title:
                        author = "Dalal Street Analyst"
                        handle = "dalal_street_live"
                        if "-" in title:
                            parts = title.rsplit("-", 1)
                            title = parts[0].strip()
                            author = parts[1].strip()
                            handle = author.lower().replace(" ", "_").replace(".", "")[:15]
                        score = _vader.polarity_scores(title)["compound"]
                        items.append({
                            "author": author[:25],
                            "handle": handle,
                            "text": f"[$ {clean_sym}] {title}",
                            "createdAt": pubDate[:16],
                            "sentimentScore": round(score, 3),
                            "sentimentLabel": "Bullish" if score > 0.15 else "Bearish" if score < -0.15 else "Neutral"
                        })
            return items

        results = await asyncio.to_thread(fetch_public_sentiment)
    except Exception as e:
        logger.error(f"Public sentiment fallback error: {e}")

    return {"query": query, "tweets": results}
