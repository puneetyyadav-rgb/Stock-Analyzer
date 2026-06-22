from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
load_dotenv()

from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
import asyncio

ROOT_DIR = Path(__file__).parent

import stock_service as ss
import ai_service as ai
import extra_service as ex
import concall_service as cs
import kotak_service as ks
import social_service as sc
import legal_service as ls
import events_service as ev_mod
import ml_service as mls
import regime_service as rs
import pattern_service as ps


mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=2000)
db = client[os.environ.get("DB_NAME", "stock_sentinel")]

app = FastAPI(title="StockSentinel India")
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


# Simple in-memory cache to avoid hammering data sources
_CACHE: dict = {}
_CACHE_TTL = 60  # seconds


def _cache_get(key: str):
    item = _CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if (datetime.now(timezone.utc) - ts).total_seconds() > _CACHE_TTL:
        return None
    return val


def _cache_set(key: str, val):
    _CACHE[key] = (datetime.now(timezone.utc), val)


@api_router.get("/")
async def root():
    return {"app": "StockSentinel India", "status": "ok"}


@api_router.get("/search")
async def search(q: str):
    if not q or len(q) < 1:
        return {"results": []}
    results = await asyncio.to_thread(ss.search_stocks, q)
    return {"results": results}


@api_router.get("/stock/{symbol}/overview")
async def overview(symbol: str):
    key = f"ov:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_overview, symbol)
    if not data.get("price"):
        raise HTTPException(status_code=404, detail="Stock not found or no data")
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/depth")
async def depth(symbol: str):
    # Live data, DO NOT cache
    data = await ks.get_market_depth(symbol)
    if data and "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@api_router.get("/stock/{symbol}/chart")
async def chart(symbol: str, period: str = "1y"):
    key = f"ch:{symbol}:{period}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_chart, symbol, period)
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/technicals")
async def technicals(symbol: str):
    key = f"tech:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.compute_technicals, symbol)
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/financials")
async def financials(symbol: str):
    key = f"fin:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_financials, symbol)
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/corporate")
async def corporate(symbol: str):
    key = f"corp:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_corporate_actions, symbol)
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/holders")
async def holders(symbol: str):
    key = f"hold:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_holders, symbol)
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/news")
async def news(symbol: str):
    key = f"news:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = {"items": await asyncio.to_thread(ss.get_news, symbol)}
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/screener")
async def screener(symbol: str):
    key = f"scr:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_screener_data, symbol)
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/full")
async def full(symbol: str):
    key = f"full:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_full_analysis, symbol)
    _cache_set(key, data)
    return data


@api_router.post("/stock/{symbol}/ai-verdict")
async def ai_verdict(symbol: str):
    cache_key = f"ai:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    (
        stock_data,
        social_data,
        legal_data,
        events_data,
        red_flags_data,
        macro,
        ml_forecast,
        regime,
        patterns
    ) = await asyncio.gather(
        asyncio.to_thread(ss.get_full_analysis, symbol),
        social(symbol),
        legal(symbol),
        events(symbol),
        red_flags(symbol),
        asyncio.to_thread(ss.get_macro_snapshot),
        asyncio.to_thread(mls.generate_ml_prediction, symbol),
        asyncio.to_thread(rs.classify_regime, symbol),
        asyncio.to_thread(ps.get_candlestick_patterns, symbol)
    )
    
    stock_data["social"] = social_data
    stock_data["legal"] = legal_data
    stock_data["events"] = events_data
    stock_data["red_flags"] = red_flags_data
    stock_data["ml_forecast"] = ml_forecast
    stock_data["regime"] = regime
    stock_data["patterns"] = patterns
    
    verdict = await ai.generate_verdict(stock_data, macro)
    _cache_set(cache_key, verdict)
    # store in mongo for history
    try:
        await db.ai_verdicts.insert_one({
            "symbol": symbol,
            "verdict": verdict,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"mongo insert error: {e}")
    return verdict


@api_router.post("/stock/{symbol}/ai-technical")
async def ai_technical(symbol: str):
    cache_key = f"ai_tech:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    (
        stock_data,
        ml_forecast,
        regime,
        patterns
    ) = await asyncio.gather(
        asyncio.to_thread(ss.get_full_analysis, symbol),
        asyncio.to_thread(mls.generate_ml_prediction, symbol),
        asyncio.to_thread(rs.classify_regime, symbol),
        asyncio.to_thread(ps.get_candlestick_patterns, symbol)
    )
    
    tech_data = {
        "technicals": stock_data.get("technicals", {}),
        "ml_forecast": ml_forecast,
        "regime": regime,
        "patterns": patterns,
    }
    
    verdict = await ai.generate_technical_analysis(tech_data)
    _cache_set(cache_key, verdict)
    return verdict


@api_router.post("/stock/{symbol}/ai-news")
async def ai_news(symbol: str):
    cache_key = f"ai_news:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    (
        news_items,
        overview_data,
        legal_data
    ) = await asyncio.gather(
        asyncio.to_thread(ss.get_news, symbol),
        asyncio.to_thread(ss.get_overview, symbol),
        legal(symbol)
    )
    
    formatted_items = []
    for n in (news_items or [])[:15]:
        formatted_items.append({
            "title": n.get("title"),
            "date": n.get("publishedAt") or n.get("date"),
            "sentiment": n.get("sentimentLabel"),
            "source": "news"
        })
        
    announcements = legal_data.get("items", [])
    for l in (announcements or [])[:10]:
        formatted_items.append({
            "title": l.get("summary") or l.get("announcement") or "",
            "date": l.get("date") or l.get("dt"),
            "sentiment": l.get("sentimentLabel") or "Neutral",
            "source": "corporate_announcement"
        })
    
    verdict = await ai.generate_news_analysis(formatted_items, overview_data)
    _cache_set(cache_key, verdict)
    return verdict


@api_router.get("/macro")
async def macro():
    key = "macro"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_macro_snapshot)
    _cache_set(key, data)
    return data


@api_router.get("/sectors")
async def sectors():
    key = "sectors"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ss.get_sector_performance)
    _cache_set(key, {"sectors": data})
    return {"sectors": data}


@api_router.get("/fii-dii")
async def fii_dii():
    key = "fii_dii"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ex.get_fii_dii)
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/concalls")
async def concalls(symbol: str):
    key = f"concalls:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ex.get_concalls, symbol)
    _cache_set(key, {"items": data})
    return {"items": data}


@api_router.post("/stock/{symbol}/concall-summary")
async def concall_summary(symbol: str, payload: dict):
    pdf_url = payload.get("transcriptUrl")
    date_str = payload.get("date", "")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="transcriptUrl required")
    cache_key = f"concall_sum:{pdf_url}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    text = await asyncio.to_thread(ex.fetch_pdf_text, pdf_url, 30000)
    if text and len(text) > 500:
        summary = await cs.summarize_concall(symbol, text, date_str)
    else:
        # Fallback: use available news + screener + about data
        full_data = await asyncio.to_thread(ss.get_full_analysis, symbol)
        context = {
            "about": (full_data.get("overview", {}).get("longBusinessSummary") or "")[:1500],
            "screener_pros": full_data.get("screener", {}).get("pros", [])[:8],
            "screener_cons": full_data.get("screener", {}).get("cons", [])[:8],
            "recent_news": [{"title": n.get("title"), "source": n.get("source"), "summary": n.get("summary", "")[:200]}
                            for n in full_data.get("news", [])[:15]],
            "screener_ratios": full_data.get("screener", {}).get("ratios", {}),
            "recent_quarterly": full_data.get("financials", {}).get("quarterly", [])[:4],
            "note": "Transcript PDF unavailable from server location (BSE geo-block). Synthesizing from public news/Screener data.",
        }
        summary = await cs.summarize_alternative(symbol, date_str, context)
    _cache_set(cache_key, summary)
    try:
        await db.concall_summaries.insert_one({
            "symbol": symbol,
            "date": date_str,
            "transcriptUrl": pdf_url,
            "summary": summary,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"mongo concall insert error: {e}")
    return summary


@api_router.get("/stock/{symbol}/peers")
async def peers(symbol: str):
    key = f"peers:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ex.get_peers, symbol)
    _cache_set(key, {"peers": data})
    return {"peers": data}


@api_router.get("/stock/{symbol}/options")
async def options(symbol: str):
    key = f"options:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await ks.get_option_chain(symbol)
    _cache_set(key, data)
    return data


@api_router.post("/stock/{symbol}/analyze-options")
async def analyze_options(symbol: str, payload: dict):
    if not payload or not payload.get("rows"):
        raise HTTPException(status_code=400, detail="Invalid options data provided")
    
    cache_key = f"ai_options:{symbol}:{payload.get('expiry', '0')}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
        
    analysis = await ai.analyze_options(payload)
    if analysis and "error" not in analysis:
        _cache_set(cache_key, analysis)
        
    return analysis


@api_router.get("/stock/{symbol}/insider")
async def insider(symbol: str):
    key = f"insider:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ex.get_insider_transactions, symbol)
    _cache_set(key, {"items": data})
    return {"items": data}


@api_router.get("/stock/{symbol}/social")
async def social(symbol: str):
    key = f"social:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    ov = await asyncio.to_thread(ss.get_overview, symbol)
    company_name = ov.get("name") or symbol
    reddit_data = await asyncio.to_thread(sc.get_reddit_sentiment, company_name)
    stocktwits_data = await asyncio.to_thread(sc.get_stocktwits_sentiment, symbol)
    result = {
        "reddit": reddit_data,
        "stocktwits": stocktwits_data,
        "twitter_x": {
            "available": False,
            "reason": (
                "X discontinued its free read tier in Feb 2026 (pay-per-use only, ~$0.005/read). "
                "Not integrated — Reddit is the primary retail-sentiment source here."
            ),
        },
    }
    _cache_set(key, result)
    return result


@api_router.get("/stock/{symbol}/legal")
async def legal(symbol: str):
    key = f"legal:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    raw = await asyncio.to_thread(ls.get_nse_announcements, symbol)
    relevant = ls.filter_legal_relevant(raw)
    classified = await ls.classify_legal_announcements(relevant)
    result = {
        "items": classified,
        "source": "NSE corporate-announcements (scraped — not an official SEBI or NSE API)",
        "announcements_scanned": len(raw),
        "note": (
            "Empty results are expected for most stocks most of the time — litigation/SEBI-action "
            "disclosures are rare events, not a constant feed. NSE may also geo-block from server "
            "location; in that case scanned=0."
        ),
    }
    _cache_set(key, result)
    return result


@api_router.get("/stock/{symbol}/events")
async def events(symbol: str):
    key = f"events:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ev_mod.get_events, symbol)
    _cache_set(key, {"items": data})
    return {"items": data}


@api_router.get("/stock/{symbol}/red-flags")
async def red_flags(symbol: str):
    key = f"redflags:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    screener = await asyncio.to_thread(ss.get_screener_data, symbol)
    news_items = await asyncio.to_thread(ss.get_news, symbol)
    legal_data = await legal(symbol)
    classified = legal_data.get("items", [])
    special = ss.get_special_news_tags(news_items)

    flags = []
    for c in screener.get("cons", []) or []:
        flags.append({"category": "Business Concern", "severity": "Medium", "summary": c, "source": "Screener.in cons"})
    pledge = screener.get("promoterPledge")
    if pledge is not None:
        sev = "Critical" if pledge >= 50 else "High" if pledge >= 25 else "Medium" if pledge >= 10 else "Low"
        flags.append({
            "category": "Promoter Pledge",
            "severity": sev,
            "summary": f"Promoter shareholding pledged: {pledge}%",
            "source": "Screener.in shareholding",
        })
    for item in classified or []:
        sev = item.get("severity") or "Medium"
        if sev in ("Critical", "High"):
            flags.append({
                "category": item.get("category", "Regulatory"),
                "severity": sev,
                "summary": item.get("summary") or item.get("announcement") or "",
                "source": "NSE announcement",
            })
    for s in special or []:
        flags.append({
            "category": s.get("tag", "Special Event"),
            "severity": "High",
            "summary": s.get("title") or "",
            "source": s.get("source"),
            "url": s.get("url"),
        })

    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    flags.sort(key=lambda f: sev_order.get(f.get("severity"), 4))

    result = {
        "items": flags,
        "promoterPledge": pledge,
        "specialEvents": special,
    }
    _cache_set(key, result)
    return result


@api_router.get("/stock/{symbol}/ml-predict")
async def ml_predict(symbol: str):
    key = f"ml:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(mls.generate_ml_prediction, symbol)
    if "error" not in data:
        _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/regime")
async def regime(symbol: str):
    key = f"regime:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(rs.classify_regime, symbol)
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/patterns")
async def patterns(symbol: str):
    key = f"patterns:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ps.get_candlestick_patterns, symbol)
    _cache_set(key, data)
    return data


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
