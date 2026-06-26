import sys
import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Body
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
import twitter_service as ts
import sector_service as sec
import scraper_service as scr


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

@api_router.post("/stock/{symbol}/ai-ratios")
async def ai_ratios(symbol: str, force: bool = False, pdf_data: dict = Body(None)):
    cache_key = f"ai_ratios:{symbol}"
    # If pdf_data is provided, don't use the simple cache key because the input is unique
    if pdf_data:
        cache_key = f"ai_ratios_custom:{symbol}:{hash(str(pdf_data))}"
        
    if not force:
        cached = _cache_get(cache_key)
        if cached:
            return cached

    (
        screener_data,
        peers_data,
        overview_data
    ) = await asyncio.gather(
        screener(symbol),
        peers(symbol),
        asyncio.to_thread(ss.get_overview, symbol)
    )

    payload = {
        "overview": overview_data,
        "screener": screener_data,
        "peers": peers_data
    }
    
    if pdf_data:
        payload["pdf_extracted_data"] = pdf_data
    
    import ai_service as ais
    data = await ais.generate_ratio_analysis(payload)
    if data and "error" not in data:
        _cache_set(cache_key, data)
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
        patterns,
        ext_data
    ) = await asyncio.gather(
        asyncio.to_thread(ss.get_full_analysis, symbol),
        social(symbol),
        legal(symbol),
        events(symbol),
        red_flags(symbol),
        asyncio.to_thread(ss.get_macro_snapshot),
        asyncio.to_thread(mls.generate_ml_prediction, symbol),
        asyncio.to_thread(rs.classify_regime, symbol),
        asyncio.to_thread(ps.get_candlestick_patterns, symbol),
        external_scrape(symbol)
    )
    
    stock_data["social"] = social_data
    stock_data["legal"] = legal_data
    stock_data["events"] = events_data
    stock_data["red_flags"] = red_flags_data
    stock_data["ml_forecast"] = ml_forecast
    stock_data["regime"] = regime
    stock_data["patterns"] = patterns
    stock_data["external_scrape"] = ext_data
    
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
        technicals_data,
        ml_forecast,
        regime,
        patterns,
        ext_data
    ) = await asyncio.gather(
        asyncio.to_thread(ss.compute_technicals, symbol),
        asyncio.to_thread(mls.generate_ml_prediction, symbol),
        asyncio.to_thread(rs.classify_regime, symbol),
        asyncio.to_thread(ps.get_candlestick_patterns, symbol),
        external_scrape(symbol)
    )
    
    tech_data = {
        "technicals": technicals_data,
        "ml_forecast": ml_forecast,
        "regime": regime,
        "patterns": patterns,
        "delivery": ext_data.get("delivery")
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
    twitter_data = await ts.get_twitter_sentiment(symbol)
    
    result = {
        "reddit": reddit_data,
        "stocktwits": stocktwits_data,
        "twitter_x": twitter_data,
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


@api_router.get("/stock/{symbol}/news-split")
async def news_split(symbol: str):
    """Return news bucketed by company / sector / market relevance."""
    key = f"news_split:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    ov = await asyncio.to_thread(ss.get_overview, symbol)
    items = await asyncio.to_thread(ss.get_news, symbol)
    buckets = sec.categorize_news(items, ov.get("name") or symbol, ov.get("sector") or "")
    # add a few extra real sector-only headlines from Moneycontrol sector landing
    extra_sector = await asyncio.to_thread(sec.get_sector_news, ov.get("sector") or "")
    # Score sentiment on extras using the same VADER helper
    extra_sector = await asyncio.to_thread(ss._score_news, extra_sector)
    if extra_sector:
        existing_titles = {n.get("title") for n in buckets["sector"]}
        for n in extra_sector:
            if n.get("title") not in existing_titles:
                buckets["sector"].append(n)
        
        # Re-sort using the smart date parser so new items integrate seamlessly
        for n in buckets["sector"]:
            pub = ss._parse_news_datetime(n.get("publishedAt"))
            n["_ts"] = pub.timestamp() if pub else 0
        buckets["sector"].sort(key=lambda x: x.get("_ts", 0), reverse=True)
        for n in buckets["sector"]:
            n.pop("_ts", None)
    result = {
        "sector": ov.get("sector"),
        "company": buckets["company"],
        "sector_news": buckets["sector"],
        "market": buckets["market"],
        "counts": {
            "company": len(buckets["company"]),
            "sector": len(buckets["sector"]),
            "market": len(buckets["market"]),
        },
    }
    _cache_set(key, result)
    return result


@api_router.get("/stock/{symbol}/sector-analysis")
async def sector_analysis(symbol: str):
    key = f"sector_an:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    ov = await asyncio.to_thread(ss.get_overview, symbol)
    data = await asyncio.to_thread(sec.get_sector_analysis, symbol, ov.get("sector"))
    # Also compute peers' aggregate metrics (avg PE, ROE, profit margin) for sector comparison
    peers = await asyncio.to_thread(ex.get_peers, symbol)
    def _avg(lst):
        vals = [x for x in lst if x is not None]
        return sum(vals) / len(vals) if vals else None
    if peers:
        data["peer_aggregates"] = {
            "count": len(peers),
            "avg_pe": _avg([p.get("peRatio") for p in peers]),
            "avg_pb": _avg([p.get("pbRatio") for p in peers]),
            "avg_roe": _avg([p.get("roe") for p in peers]),
            "avg_profit_margin": _avg([p.get("profitMargin") for p in peers]),
            "avg_revenue_growth": _avg([p.get("revenueGrowth") for p in peers]),
            "top_gainer": max(peers, key=lambda p: p.get("changePercent") or -999, default=None),
            "top_loser": min(peers, key=lambda p: p.get("changePercent") or 999, default=None),
        }
        # Stock vs peer percentile rough position
        my_pe = ov.get("peRatio")
        if my_pe and data["peer_aggregates"]["avg_pe"]:
            data["stock_vs_peers"] = {
                "pe_vs_peer_avg": "Cheaper" if my_pe < data["peer_aggregates"]["avg_pe"] else "Pricier",
                "pe_diff_pct": ((my_pe - data["peer_aggregates"]["avg_pe"]) / data["peer_aggregates"]["avg_pe"]) * 100,
            }
    _cache_set(key, data)
    return data


@api_router.get("/stock/{symbol}/external-scrape")
async def external_scrape(symbol: str):
    """Aggregated headless-browser scrape of Trendlyne, Aftermarkets, and Tickertape."""
    key = f"external_scrape_v3:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    aftermarkets_task = scr.scrape_aftermarkets(symbol)
    tickertape_task = scr.scrape_tickertape(symbol)
    trendlyne_task = scr.scrape_trendlyne(symbol)
    delivery_task = scr.scrape_delivery_volume(symbol)
    
    aftermarkets, tickertape, trendlyne, delivery = await asyncio.gather(
        aftermarkets_task, tickertape_task, trendlyne_task, delivery_task, return_exceptions=False
    )
    
    result = {
        "aftermarkets": aftermarkets,
        "tickertape": tickertape,
        "trendlyne": trendlyne,
        "delivery": delivery,
    }
    _cache_set(key, result)
    return result



@api_router.post("/stock/{symbol}/upload-source")
async def upload_source(symbol: str, file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        from pypdf import PdfReader
        import io
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            text_parts.append(t)
        full_text = "\n".join(text_parts)
        
        # Call AI service
        import ai_service as ais
        data = await ais.extract_ratios_from_source(full_text)
        
        if "error" in data:
            raise HTTPException(status_code=500, detail=data["error"])
            
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Source upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    await scr.shutdown()
    client.close()
