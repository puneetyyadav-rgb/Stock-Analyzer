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


mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(mongo_url)
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
    data = await asyncio.to_thread(ss.get_news, symbol)
    _cache_set(key, data)
    return {"items": data}


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
    stock_data = await asyncio.to_thread(ss.get_full_analysis, symbol)
    macro = await asyncio.to_thread(ss.get_macro_snapshot)
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


@api_router.get("/stock/{symbol}/insider")
async def insider(symbol: str):
    key = f"insider:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    data = await asyncio.to_thread(ex.get_insider_transactions, symbol)
    _cache_set(key, {"items": data})
    return {"items": data}


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
