import sys
import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Body
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()  # also check root .env as fallback

from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent

import stock_service as ss
import ai_service as ai
import extra_service as ex
import concall_service as cs
import concall_longitudinal_service as cls
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
import validation_service as vs
import pairs_service as prs
import portfolio_service as ports
from institutional_flow_service import institutional_flow_service as ifs
import macro_service as ms
import qlib_service as qs
from pydantic import BaseModel

mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=2000)
db = client[os.environ.get("DB_NAME", "stock_sentinel")]

app = FastAPI(title="StockSentinel India")
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Simple in-memory + persistent disk cache to ensure analyses never disappear across refreshes
_CACHE: dict = {}
_CACHE_TTL = 60  # seconds
_DISK_CACHE_FILE = None

def _disk_cache_path():
    global _DISK_CACHE_FILE
    if _DISK_CACHE_FILE is None:
        import os
        base = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(base, exist_ok=True)
        _DISK_CACHE_FILE = os.path.join(base, "server_analysis_cache.json")
    return _DISK_CACHE_FILE

def _cache_get(key: str, custom_ttl: float = None):
    item = _CACHE.get(key)
    now = datetime.now(timezone.utc)
    # If in memory check first
    if item:
        ts, val = item
        ttl = custom_ttl if custom_ttl is not None else _CACHE_TTL
        if (now - ts).total_seconds() <= ttl:
            return val

    # If key is an AI analysis or expensive query, check persistent disk cache (default 24h TTL)
    if any(key.startswith(k) for k in ("ai_ratios", "ai_verdict", "ai_technical", "ai_news", "options_analysis", "concall_summary", "verdict", "guidance_extract")):
        import json, os, time
        try:
            path = _disk_cache_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    store = json.load(f)
                entry = store.get(key)
                if entry:
                    ts_disk = entry.get("ts", 0)
                    disk_ttl = custom_ttl if custom_ttl is not None else 86400  # 24 hours default for AI
                    if time.time() - ts_disk <= disk_ttl:
                        val = entry.get("val")
                        _CACHE[key] = (now, val)
                        return val
        except Exception:
            pass
    return None


def _cache_set(key: str, val):
    _CACHE[key] = (datetime.now(timezone.utc), val)
    # If key is an AI analysis or expensive query, persist to disk cache
    if any(key.startswith(k) for k in ("ai_ratios", "ai_verdict", "ai_technical", "ai_news", "options_analysis", "concall_summary", "verdict", "guidance_extract")):
        import json, os, time
        try:
            path = _disk_cache_path()
            store = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        store = json.load(f)
                except Exception:
                    store = {}
            store[key] = {"val": val, "ts": time.time()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(store, f)
        except Exception:
            pass



def _items_list(value):
    """Normalize legacy/list and AI-wrapped item payloads to a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "tagged_announcements", "announcements", "data"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


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


# --- Cross-sectional factor model (literal routes declared before /factors/{symbol}) ---
@api_router.get("/factors/leaders")
async def factor_leaders(n: int = 15, min_adv_turnover_cr: float = 5.0):
    key = f"factor_leaders:{n}:{min_adv_turnover_cr}"
    cached = _cache_get(key)
    if cached:
        return cached
    import factor_service as fsvc
    data = await asyncio.to_thread(fsvc.get_factor_leaders, n, min_adv_turnover_cr)
    _cache_set(key, data)
    return data


@api_router.get("/factors/ic")
async def factor_ic_endpoint():
    cached = _cache_get("factor_ic")
    if cached:
        return cached
    import factor_service as fsvc
    data = await asyncio.to_thread(fsvc.factor_ic)
    _cache_set("factor_ic", data)
    return data


@api_router.get("/factors/param-validation")
async def factor_param_validation(symbol: str = None, max_symbols: int = 20, train: int = 252,
                                  test: int = 42, step: int = 42, fwd_days: int = 5,
                                  min_adv_turnover_cr: float = 5.0):
    key = f"factor_param_validation:{symbol}:{max_symbols}:{train}:{test}:{step}:{fwd_days}:{min_adv_turnover_cr}"
    cached = _cache_get(key, custom_ttl=3600)
    if cached:
        return cached
    import factor_service as fsvc
    data = await asyncio.to_thread(
        fsvc.param_validation,
        symbol,
        max_symbols,
        train,
        test,
        step,
        fwd_days,
        min_adv_turnover_cr,
    )
    _cache_set(key, data)
    return data


@api_router.get("/factors/{symbol}")
async def factor_profile(symbol: str, min_adv_turnover_cr: float = 5.0):
    key = f"factors:{symbol}:{min_adv_turnover_cr}"
    cached = _cache_get(key)
    if cached:
        return cached
    import factor_service as fsvc
    data = await asyncio.to_thread(fsvc.get_factor_profile, symbol, min_adv_turnover_cr)
    _cache_set(key, data)
    return data


@api_router.get("/concall-synthesis/{symbol}")
async def concall_synthesis(symbol: str, force_refresh: bool = False, auto_load: bool = False):
    """Returns the 8-quarter longitudinal narrative synthesis."""
    import concall_longitudinal_service as cls
    key = f"concall-synthesis:{symbol}:False"  # Always use the same key for the actual data cache
    
    cached = _cache_get(key)
    if cached and not force_refresh:
        return cached
        
    # If the frontend is just polling on page load, do NOT run the 120s generation.
    if auto_load:
        return {"not_generated_yet": True}
        
    data = await cls.generate_longitudinal_synthesis(symbol, force_refresh=True)
    if "error" not in data:
        _cache_set(key, data)
    return data

@api_router.post("/concall-synthesis/{symbol}/download-transcripts")
async def download_transcripts(symbol: str):
    """Downloads missing 8-quarter transcripts to disk without running the AI analysis."""
    import concall_longitudinal_service as cls
    return await cls.sync_transcripts(symbol)

@api_router.post("/backtest")
async def backtest(config: dict):
    """Decile long/short + long-only backtest net of Indian STT & market impact. Heavy; cached 1h by config."""
    import json, hashlib
    key = "backtest:" + hashlib.md5(json.dumps(config or {}, sort_keys=True).encode()).hexdigest()[:12]
    cached = _cache_get(key, custom_ttl=3600)
    if cached:
        return cached
    import backtest_engine as bt
    data = await asyncio.to_thread(bt.run_backtest, config or {})
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

        # ── T4 PDF SOURCE-LOCK OVERRIDE ───────────────────────────────────────
        # If the uploaded PDF already contains an extracted competitor comparison
        # grid (set by extract_ratios_from_source), replace the generic Yahoo peers
        # completely so the AI is benchmarked ONLY against the document's own peers
        # (e.g. Apex Frozen Foods / Waterbase from an Avanti Feeds analyst report),
        # not against HUL / Nestle from the broad sector bucket.
        pdf_competitors = (pdf_data.get("competitor_comparison") or {}).get("companies") or []
        if pdf_competitors:
            payload["peers"] = {
                "source": "T4_PDF_EXTRACTED",
                "notice": (
                    "STRICT SOURCE-LOCK: This peer comparison was extracted directly from the "
                    "uploaded analyst/annual report PDF. You MUST evaluate valuation, margins, "
                    "and growth EXCLUSIVELY against these document-sourced peers. "
                    "Ignore any generic sector benchmarks you may infer from company names."
                ),
                "companies": pdf_competitors,
            }


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
    
    # ── Phase 1: Data Sanitization & Divergence Detection ──
    overview = stock_data.get("overview", {})
    sanitized_ov, outlier_flags = vs.sanitize_overview(overview)
    stock_data["overview"] = sanitized_ov
    divergences = vs.detect_divergences(sanitized_ov, ext_data)
    stock_data["_divergences"] = divergences
    stock_data["_outlier_flags"] = outlier_flags
    divergence_note = vs.build_divergence_note(divergences)
    if divergence_note:
        macro["_divergence_note"] = divergence_note
    
    verdict = await ai.generate_verdict(stock_data, macro)
    
    # Attach divergence info to response so frontend can display it
    if divergences:
        verdict["divergences"] = divergences
    if outlier_flags:
        verdict["outlier_flags"] = outlier_flags
    
    _cache_set(cache_key, verdict)
    # ── Phase 2: Structured verdict ledger ──
    try:
        price_at_verdict = sanitized_ov.get("price")
        thesis = verdict.get("thesis", {})
        await db.verdict_history.insert_one({
            "symbol": symbol,
            "bias": thesis.get("bias", "Neutral"),
            "conviction": thesis.get("conviction", "Low"),
            "price_at_verdict": price_at_verdict,
            "target_horizon_days": 30,
            "verdict_summary": thesis.get("coreArgument", "")[:500],
            "createdAt": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.error(f"verdict_history insert error: {e}")
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
    if isinstance(verdict, dict):
        q_deck = technicals_data.get("quantDeck", {})
        verdict["signalBacktest"] = q_deck.get("signalBacktest")
        verdict["quantScore"] = q_deck.get("quantScore", verdict.get("quantScore"))
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
        
    announcements = _items_list(legal_data.get("items", []))
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
    # Update institutional flow logbook and attach Alpha 24 positioning diagnostics
    alpha24_metrics = await asyncio.to_thread(ifs.fetch_and_update_flows, ex)
    if isinstance(data, dict):
        data["alpha24_metrics"] = alpha24_metrics
    _cache_set(key, data)
    return data


@api_router.get("/quant/self-learning/institutional-flow")
async def get_institutional_flow_metrics():
    """Phase C / Alpha 24: Returns active FII/DII whale flow imbalance and conviction multipliers."""
    try:
        metrics = await asyncio.to_thread(ifs.fetch_and_update_flows, ex)
        return {"status": "success", "metrics": metrics}
    except Exception as e:
        return {"status": "error", "error": str(e), "metrics": ifs.compute_institutional_flow_metrics()}


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
        try:
            import catalyst_archive_service as cas
            from extra_service import _strip_symbol
            from datetime import datetime
            with cas.get_db_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO concalls_archive (symbol, quarter_label, full_text, date_published, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (_strip_symbol(symbol), date_str or "Latest", text, datetime.now().strftime("%Y-%m-%d"), datetime.now().isoformat())
                )
        except Exception as arc_err:
            logger.debug(f"Failed to archive concall text: {arc_err}")
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
    classified = _items_list(await ls.classify_legal_announcements(relevant))
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


@api_router.get("/catalysts/upcoming")
async def catalysts_upcoming(days: int = 30, force_refresh: bool = False):
    """Phase 4: Catalyst Radar endpoint — returns upcoming deterministically extracted
    events from official NSE/BSE filings, classified by category. No predictions, no probabilities."""
    key = f"catalysts:upcoming:{days}"
    if not force_refresh:
        cached = _cache_get(key)
        if cached:
            return cached
    else:
        logger.info(f"Forced exchange sync triggered for /catalysts/upcoming (days={days})")

    raw_events = await asyncio.to_thread(ev_mod.get_extracted_catalyst_events, None, days)

    if raw_events:
        classified = await ev_mod.classify_catalyst_events(raw_events)
    else:
        classified = []

    # Group by time horizon
    from datetime import datetime as _dt, timedelta as _td
    today = _dt.now().date()
    this_week = []
    next_two_weeks = []
    later = []

    for ev in classified:
        try:
            ev_date = _dt.fromisoformat(ev.get("extracted_date", "9999-12-31")).date()
        except (ValueError, TypeError):
            ev_date = today + _td(days=999)

        days_away = (ev_date - today).days
        ev["days_remaining"] = days_away

        if days_away <= 7:
            this_week.append(ev)
        elif days_away <= 21:
            next_two_weeks.append(ev)
        else:
            later.append(ev)

    result = {
        "this_week": this_week,
        "next_two_weeks": next_two_weeks,
        "later": later,
        "total": len(classified),
        "note": "All events sourced from official NSE/BSE filings. No outcome predictions or probabilities."
    }
    _cache_set(key, result)
    return result


@api_router.post("/catalysts/run-batch-archive")
async def run_batch_archive(max_stocks: int = 500, download_pdfs: bool = False, universe_filter: str = "all"):
    """Triggers batch archiving across the full Indian stock universe (up to 2,000+ stocks or micro-caps specifically).
    Runs asynchronously in background thread pool."""
    import catalyst_archive_service as cas
    asyncio.create_task(
        asyncio.to_thread(
            cas.archive_nse_universe_batch,
            symbols=None,
            months_back=3,
            download_pdfs=download_pdfs,
            max_items_per_stock=10,
            max_stocks=max_stocks,
            delay_sec=0.2,
            universe_filter=universe_filter
        )
    )
    return {
        "status": "started",
        "message": f"Background scan started across up to {max_stocks} NSE symbols ({universe_filter}). Micro-cap and upcoming catalysts will appear automatically as extraction progresses!"
    }


@api_router.get("/catalysts/scan-progress")
async def get_scan_progress():
    """Returns real-time progress of market-wide background announcement archiving."""
    import catalyst_archive_service as cas
    return cas.CURRENT_SCAN_PROGRESS


@api_router.get("/catalysts/results-due")
async def get_results_due_route(days: int = 30, force_refresh: bool = False):
    """Returns forthcoming board meetings & corporate actions from structured NSE event-calendar
    enriched with yfinance consensus EPS/revenue estimates and 9-factor profiles.
    """
    key = f"results_due:{days}"
    if not force_refresh:
        cached = _cache_get(key)
        if cached:
            return cached
    else:
        logger.info(f"Forced exchange sync triggered for /catalysts/results-due (days={days})")
    import events_service as es
    result = await asyncio.to_thread(es.get_results_due, days, force_refresh)
    try:
        _cache_set(key, result)
    except TypeError:
        pass
    return result


@api_router.get("/catalysts/results-due/{symbol}/guidance")
async def get_management_guidance(symbol: str, force_refresh: bool = False):
    """Phase 5: strictly-gated dual-source (concall transcript + Investor
    Presentation/Press Release) extraction of explicit management guidance.
    Deliberately NOT bundled into /catalysts/results-due — that would mean one
    Gemini call per visible card on every 10-minute cache refresh. This is
    lazy-loaded per card instead."""
    key = f"guidance_extract:{symbol.upper()}"
    if not force_refresh:
        cached = _cache_get(key, custom_ttl=86400)  # guidance is stable until the next concall
        if cached and "error" not in cached:
            return cached
    import events_service as es
    result = await es.extract_management_guidance(symbol, force_refresh)
    if "error" not in result:
        _cache_set(key, result)
    return result



@api_router.get("/stock/{symbol}/red-flags")
async def red_flags(symbol: str):
    key = f"redflags:{symbol}"
    cached = _cache_get(key)
    if cached:
        return cached
    screener = await asyncio.to_thread(ss.get_screener_data, symbol)
    news_items = await asyncio.to_thread(ss.get_news, symbol)
    legal_data = await legal(symbol)
    classified = _items_list(legal_data.get("items", []))
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
    cached = _cache_get(key, custom_ttl=3600)
    if cached:
        return cached
    aftermarkets_task = scr.scrape_aftermarkets(symbol)
    tickertape_task = scr.scrape_tickertape(symbol)
    trendlyne_task = scr.scrape_trendlyne(symbol)
    delivery_task = scr.scrape_delivery_volume(symbol)
    
    results = await asyncio.gather(
        aftermarkets_task, tickertape_task, trendlyne_task, delivery_task, return_exceptions=True
    )
    aftermarkets = results[0] if isinstance(results[0], dict) else {"available": False, "error": str(results[0])}
    tickertape = results[1] if isinstance(results[1], dict) else {"available": False, "error": str(results[1])}
    trendlyne = results[2] if isinstance(results[2], dict) else {"available": False, "error": str(results[2])}
    delivery = results[3] if isinstance(results[3], dict) else {"available": False, "error": str(results[3])}
    
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


@api_router.post("/stock/{symbol}/ask-source")
async def ask_source(symbol: str, payload: dict):
    source_name = payload.get("sourceName", "Unknown")
    source_data = payload.get("sourceData", {})
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    result = await ai.ask_source_qa(source_name, source_data, question)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result



@api_router.get("/stock/{symbol}/verdict-history")
async def verdict_history(symbol: str):
    """Return past AI verdicts for this symbol with accuracy calibration."""
    try:
        cursor = db.verdict_history.find(
            {"symbol": symbol},
            {"_id": 0}
        ).sort("createdAt", -1).limit(50)
        records = await cursor.to_list(length=50)
    except Exception as e:
        logger.error(f"verdict_history read error: {e}")
        records = []

    if not records:
        return {"history": [], "accuracy": None, "total": 0}

    # ── Accuracy calibration: compare past bias vs realized price move ──
    scored = 0
    correct = 0
    for rec in records:
        price_then = rec.get("price_at_verdict")
        if not price_then:
            continue
        try:
            current_price = (await asyncio.to_thread(ss.get_overview, symbol)).get("price")
        except Exception:
            current_price = None
        if not current_price:
            continue
        move_pct = ((current_price - price_then) / price_then) * 100
        bias = rec.get("bias", "Neutral")
        scored += 1
        if bias == "Bullish" and move_pct > 0:
            correct += 1
        elif bias == "Bearish" and move_pct < 0:
            correct += 1
        elif bias == "Neutral" and abs(move_pct) < 5:
            correct += 1
        rec["realized_move_pct"] = round(move_pct, 2)
        rec["was_correct"] = (
            (bias == "Bullish" and move_pct > 0) or
            (bias == "Bearish" and move_pct < 0) or
            (bias == "Neutral" and abs(move_pct) < 5)
        )
        # Serialize datetime for JSON
        if rec.get("createdAt"):
            rec["createdAt"] = rec["createdAt"].isoformat() if hasattr(rec["createdAt"], "isoformat") else str(rec["createdAt"])

    accuracy_pct = round((correct / scored) * 100, 1) if scored > 0 else None

    return {
        "history": records,
        "accuracy": accuracy_pct,
        "scored": scored,
        "correct": correct,
        "total": len(records),
    }


class PortfolioReq(BaseModel):
    symbols: list[str]
    capital: float = 1000000.0


@api_router.get("/quant/pairs")
async def get_stat_arb_pairs():
    data = await asyncio.to_thread(prs.scan_market_pairs)
    return {"pairs": data, "count": len(data)}


@api_router.get("/quant/pairs/custom")
async def get_custom_pair(symA: str, symB: str):
    data = await asyncio.to_thread(prs.scan_custom_pair, symA, symB)
    return data


@api_router.post("/quant/portfolio")
async def build_hrp_portfolio(req: PortfolioReq):
    data = await asyncio.to_thread(ports.calculate_portfolio_metrics, req.symbols, req.capital)
    return data


@api_router.get("/macro/global-monte-carlo")
async def get_global_macro_monte_carlo_endpoint(
    horizon_days: int = 20,
    paths: int = 10000,
    lookback: int = 252,
    seed: int = 12345,
    vol_scale: float = 1.0,
    regime_override: str = "normal"
):
    data = await asyncio.to_thread(ms.get_global_macro_monte_carlo, horizon_days, paths, lookback, seed, vol_scale, regime_override)
    return data


@api_router.get("/stock/{symbol}/beta-coupled-simulation")
async def get_beta_coupled_simulation_endpoint(
    symbol: str,
    sector: str = "Conglomerate",
    horizon_days: int = 20,
    paths: int = 10000,
    lookback: int = 252,
    seed: int = 12345,
    vol_scale: float = 1.0,
    regime_override: str = "normal"
):
    data = await asyncio.to_thread(
        ms.get_beta_coupled_simulation,
        symbol,
        sector,
        horizon_days,
        paths,
        lookback,
        seed,
        vol_scale,
        regime_override
    )
    return data


@api_router.get("/stock/{symbol}/outlier-investigation")
async def get_outlier_investigation_endpoint(
    symbol: str,
    date: str,
    nifty_ret: float = 0.0,
    stock_ret: float = 0.0,
    deviation: float = 0.0
):
    data = await asyncio.to_thread(ms.get_outlier_investigation, symbol, date, nifty_ret, stock_ret, deviation)
    return data


@api_router.get("/qlib/predict/{symbol}")
async def get_qlib_prediction_endpoint(
    symbol: str,
    lookback_days: int = 500
):
    data = await asyncio.to_thread(qs.get_qlib_alpha_prediction, symbol, lookback_days)
    return data


@api_router.get("/qlib/rankings")
async def get_qlib_rankings_endpoint():
    cache_file = os.path.join(ROOT_DIR, "data", "latest_nse_rankings.json")
    if os.path.exists(cache_file):
        try:
            import json
            with open(cache_file, "r") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e), "top_buys": [], "bottom_avoids": []}
    return {"status": "not_trained", "message": "Run train_nse_qlib.py to generate live rankings.", "top_buys": [], "bottom_avoids": []}


@api_router.get("/qlib/diagnostics")
async def get_qlib_diagnostics_endpoint():
    """Returns the latest Closed-Loop Prediction Error Log, SHAP Attributions, and Adaptive Factor Weights."""
    error_log_path = os.path.join(ROOT_DIR, "data", "prediction_error_log.json")
    if os.path.exists(error_log_path):
        try:
            import json, math
            with open(error_log_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Replace NaN/Infinity literals that Python json.dump may have written
            content = content.replace(": NaN", ": null").replace(":NaN", ":null")
            content = content.replace(": Infinity", ": null").replace(": -Infinity", ": null")
            return json.loads(content)
        except Exception as e:
            pass
    # If not run yet, trigger a fresh check
    try:
        import self_learning_service as sls
        return await asyncio.to_thread(sls.run_daily_error_attribution_and_factor_decay)
    except Exception as e:
        return {"error": str(e), "status": "failed_diagnostics"}


@api_router.get("/quant/ledger")
async def get_quant_ledger_endpoint():
    """Returns aggregated summary metrics and recent error misses of the Phase A1 Prediction Ledger."""
    try:
        import prediction_ledger_service as pls
        summary = await asyncio.to_thread(pls.get_ledger_summary)
        recent_misses = await asyncio.to_thread(pls.get_recent_error_misses, 15)
        return {"status": "success", "summary": summary, "recent_misses": recent_misses}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@api_router.get("/quant/rank-ic")
async def get_quant_rank_ic_endpoint():
    """Returns rolling Spearman Rank IC health, ICIR, and Pruning/Promotion status across all factors (`Phase A2`)."""
    try:
        import self_learning_service as sls
        data = await asyncio.to_thread(sls.get_factor_rank_ic_report)
        return data
    except Exception as e:
        return {"status": "error", "error": str(e)}


@api_router.get("/quant/shap-memory")
async def get_quant_shap_memory_endpoint():
    """Returns the cached ternary failure vectors from Phase A3 SHAP memory."""
    try:
        import shap_memory_service as sms
        if os.path.exists(sms.CACHE_PATH):
            with open(sms.CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return await asyncio.to_thread(sms.build_shap_failure_memory_cache)
    except Exception as e:
        return {"status": "error", "error": str(e)}


@api_router.post("/quant/shap-memory/rebuild")
async def rebuild_quant_shap_memory_endpoint():
    """Rebuilds the SHAP failure memory cache from latest SETTLED MODEL_MISS ledger entries."""
    try:
        import shap_memory_service as sms
        res = await asyncio.to_thread(sms.build_shap_failure_memory_cache)
        return res
    except Exception as e:
        return {"status": "error", "error": str(e)}


@api_router.get("/quant/calibration")
async def get_quant_calibration_endpoint(score: float = 75.0):
    """Returns Phase B Isotonic calibration status for a given candidate alpha score."""
    try:
        import isotonic_calibrator_service as ics
        res = await asyncio.to_thread(ics.calibrate_alpha_score, score)
        return res
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _auto_log_daily_rankings_to_ledger():
    import prediction_ledger_service as pls
    import json
    rank_path = os.path.join(ROOT_DIR, "data", "latest_nse_rankings.json")
    if os.path.exists(rank_path):
        try:
            with open(rank_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            top_buys = data.get("top_buys", [])[:15]
            for pick in top_buys:
                sym = pick.get("symbol")
                pred = float(pick.get("pred_return_10d_pct", 0.0))
                score = pred * 10.0 + 50.0
                feats = {"roc_20": pick.get("momentum_20d_pct", 0.0), "zscore_20": pick.get("zscore", 0.0), "v_surge": pick.get("volume_surge", 1.0)}
                if sym:
                    pls.log_prediction(
                        symbol=sym,
                        target_horizon_days=10,
                        predicted_return_pct=pred,
                        raw_alpha_score=score,
                        features=feats,
                        model_version=data.get("model_used", "LightGBM_Alpha158_v2.1")
                    )
            logger.info(f"Auto-logged {len(top_buys)} daily top picks from latest rankings into prediction ledger as PENDING.")
        except Exception as e:
            logger.warning(f"Error auto-logging daily rankings: {e}")


@api_router.post("/quant/self-learning/run-cycle")
async def run_quant_reality_check_cycle_endpoint():
    """Triggers immediate manual execution of Phase A1 -> A2 -> A3 reality check loop with fresh closing prices."""
    try:
        import prediction_ledger_service as pls
        import self_learning_service as sls
        import shap_memory_service as sms
        import train_nse_qlib as tnq
        logger.info("Downloading fresh closing prices for all stocks and updating rankings...")
        await asyncio.to_thread(tnq.run_daily_universe_refresh)
        await asyncio.to_thread(_auto_log_daily_rankings_to_ledger)
        await asyncio.to_thread(pls.evaluate_pending_predictions)
        await asyncio.to_thread(sls.run_daily_error_attribution_and_factor_decay)
        await asyncio.to_thread(sms.build_shap_failure_memory_cache)
        return {"status": "success", "message": "Quant Reality Check Cycle executed across Phase A1, A2, and A3 with fresh daily data."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@api_router.get("/quant/self-learning/audit")
async def get_quant_governance_audit_logbook():
    """Returns the immutable compliance and governance audit logbook for the closed-loop engine without mutating weights."""
    import hashlib
    import prediction_ledger_service as pls
    import isotonic_calibrator_service as ics
    
    model_path = os.path.join(ROOT_DIR, "data", "models", "nse_lightgbm_alpha.pkl")
    model_hash = "no_model_file"
    model_trained_at = "unknown"
    if os.path.exists(model_path):
        try:
            with open(model_path, "rb") as f:
                raw_bytes = f.read()
                model_hash = hashlib.sha256(raw_bytes).hexdigest()
            import pickle
            with open(model_path, "rb") as f:
                saved = pickle.load(f)
                if isinstance(saved, dict) and "trained_at" in saved:
                    model_trained_at = str(saved["trained_at"])
        except Exception as ex:
            model_hash = f"error_reading_hash: {ex}"

    error_log_path = os.path.join(ROOT_DIR, "data", "prediction_error_log.json")
    error_log = {}
    if os.path.exists(error_log_path):
        try:
            with open(error_log_path, "r", encoding="utf-8") as f:
                error_log = json.load(f)
        except Exception:
            pass

    weights_path = os.path.join(ROOT_DIR, "data", "meta_factor_weights.json")
    meta_weights = {}
    if os.path.exists(weights_path):
        try:
            with open(weights_path, "r", encoding="utf-8") as f:
                meta_weights = json.load(f)
        except Exception:
            pass

    ledger_stats = pls.get_ledger_summary()
    calib_status = ics.calibrate_alpha_score(75.0)
    flow_status = ifs.compute_institutional_flow_metrics()

    # Determine T-1 Completed-Bar Guard enforcement status
    now = datetime.now()
    target_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    guard_status = {
        "enforcement_rule": "Strict T-1 completed bar cutoff or post-15:30 IST closing verification",
        "excluded_current_session": now < target_close,
        "current_server_time": now.isoformat(),
        "market_close_cutoff": "15:30:00 IST"
    }

    return {
        "status": "success",
        "governance_metadata": {
            "model_version": meta_weights.get("active_model_version", "LightGBM_Alpha158_v2.1"),
            "model_hash_sha256": model_hash,
            "model_trained_at": model_trained_at,
            "factor_schema_version": "Qlib_Alpha158_Bhavcopy_v2.1",
            "data_cutoff_timestamp": guard_status["current_server_time"] if not guard_status["excluded_current_session"] else (now - timedelta(days=1)).strftime("%Y-%m-%d 15:30:00"),
            "completed_bar_guard_status": guard_status,
            "audited_at": datetime.now().isoformat()
        },
        "prediction_ledger_stats": ledger_stats,
        "isotonic_calibration_status": calib_status,
        "factor_health_summary": meta_weights,
        "institutional_flow_status": flow_status,
        "historical_diagnostics_audit": error_log
    }


import overnight_service as osrv

@api_router.get("/overnight/raw-data")
async def get_overnight_raw_data():
    """Returns the overnight global market indices and commodities (raw data only)."""
    key = "overnight:raw"
    cached = _cache_get(key, custom_ttl=900)  # 15 minutes cache
    if cached:
        return cached
    try:
        result = await asyncio.to_thread(osrv.fetch_overnight_data)
        _cache_set(key, result)
        return result
    except Exception as e:
        logger.error(f"Error fetching overnight raw data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/overnight/briefing")
async def get_overnight_briefing(force_refresh: bool = False):
    """Returns the overnight market raw data AND the AI-synthesized morning briefing bias.
    Feeds REAL FII/DII net flow data into the AI prompt instead of letting the model guess."""
    key = "overnight:briefing"
    if not force_refresh:
        cached = _cache_get(key, custom_ttl=7200)  # 2 hours cache
        if cached:
            return cached

    # Fetch real FII data to pass into AI prompt (not for AI to guess from DXY)
    fii_data = None
    try:
        fii_data = ifs.compute_institutional_flow_metrics()
    except Exception as e:
        logger.warning(f"Could not fetch FII data for overnight briefing: {e}")

    try:
        result = await osrv.generate_morning_briefing(force_refresh, fii_data=fii_data)

        # Only cache if AI layer succeeded — don't freeze a null AI for 2 hours
        if result.get("ai") is not None:
            _cache_set(key, result)

        return result
    except Exception as e:
        logger.error(f"Error generating overnight briefing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _daily_quant_reality_check_loop():
    """Background task locked specifically to 3:45 PM IST daily after Indian market close."""
    import prediction_ledger_service as pls
    import self_learning_service as sls
    import shap_memory_service as sms
    import train_nse_qlib as tnq
    from datetime import datetime, timedelta

    logger.info("Starting Daily Quant Reality Check background scheduler loop...")
    # Perform initial warm check on boot — if data is stale (>18h), do a FULL universe refresh + retrain
    try:
        weights_path = os.path.join(ROOT_DIR, "data", "meta_factor_weights.json")
        is_stale = True
        if os.path.exists(weights_path):
            try:
                with open(weights_path, "r", encoding="utf-8") as f:
                    mw = json.load(f)
                last_upd = mw.get("updated_at")
                if last_upd:
                    age_hours = (datetime.now() - datetime.fromisoformat(last_upd)).total_seconds() / 3600
                    is_stale = age_hours > 18
                    logger.info(f"Meta-learning data age: {age_hours:.1f}h — {'STALE, triggering full refresh' if is_stale else 'FRESH, warm check only'}.")
            except Exception:
                pass

        if is_stale:
            logger.info("Data is stale (>18h). Running full universe refresh + self-learning cycle on startup...")
            await asyncio.to_thread(tnq.run_daily_universe_refresh)

        await asyncio.to_thread(_auto_log_daily_rankings_to_ledger)
        await asyncio.to_thread(pls.evaluate_pending_predictions)
        await asyncio.to_thread(sls.run_daily_error_attribution_and_factor_decay)
        await asyncio.to_thread(sms.build_shap_failure_memory_cache)
        logger.info("Startup warm check completed successfully.")
    except Exception as e:
        logger.error(f"Error during initial startup check: {e}")

    while True:
        try:
            now = datetime.now()
            target_today = now.replace(hour=15, minute=45, second=0, microsecond=0)
            if now >= target_today:
                target_next = target_today + timedelta(days=1)
            else:
                target_next = target_today

            wait_seconds = (target_next - now).total_seconds()
            logger.info(f"Locked schedule: Next Quant Reality Check at 3:45 PM IST ({target_next.strftime('%Y-%m-%d %H:%M:%S')}, sleeping {int(wait_seconds)}s)...")
            await asyncio.sleep(wait_seconds)

            logger.info("Step 1: Downloading locked 3:45 PM IST fresh today's closing prices for all NSE universe stocks...")
            await asyncio.to_thread(tnq.run_daily_universe_refresh)
            logger.info("Step 2: Executing automated Quant Reality Check (Phase A1 -> A2 -> A3)...")
            await asyncio.to_thread(_auto_log_daily_rankings_to_ledger)
            await asyncio.to_thread(pls.evaluate_pending_predictions)
            await asyncio.to_thread(sls.run_daily_error_attribution_and_factor_decay)
            await asyncio.to_thread(sms.build_shap_failure_memory_cache)
            logger.info("Step 3: Automatically syncing forthcoming exchange board meetings & indexing latest corporate filings...")
            import events_service as es
            import catalyst_archive_service as cas
            try:
                res_due = await asyncio.to_thread(es.get_results_due, 30)
                _cache_set("results_due:30", res_due)
                logger.info(f"Daily automated sync complete: cached {res_due.get('total', 0)} upcoming structured board meetings.")
            except Exception as ev_err:
                logger.warning(f"Daily board meeting sync warning: {ev_err}")
            try:
                # Automatically scan and backfill top 100 most liquid/active stocks for new disclosures daily
                await asyncio.to_thread(cas.run_batch_archive, max_stocks=100, download_pdfs=False, universe_filter="all")
                logger.info("Daily automated corporate announcement archiving loop triggered successfully.")
            except Exception as cas_err:
                logger.warning(f"Daily filings archive warning: {cas_err}")
            logger.info("Completed locked 3:45 PM IST automated Quant Reality Check & Catalyst Scan successfully.")
        except Exception as e:
            logger.error(f"Error in daily 3:45 PM quant reality check loop: {e}")
            await asyncio.sleep(3600)  # Retry in 1 hour on error


@app.on_event("startup")
async def startup_quant_scheduler():
    asyncio.create_task(_daily_quant_reality_check_loop())


@app.on_event("shutdown")
async def shutdown_db_client():
    await scr.shutdown()
    client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, loop="asyncio")
