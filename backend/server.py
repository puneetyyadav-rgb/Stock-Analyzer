from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import stock_service as ss
import ai_service as ai

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

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
