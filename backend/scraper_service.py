"""Playwright-powered headless scraper for sites that require JS rendering.
Singleton browser instance — launched lazily on first request, reused across calls.
Aggressive 30-min cache because each scrape costs ~5-8 seconds."""
import os
# Set Playwright browser path BEFORE importing playwright modules
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and os.path.exists("/pw-browsers"):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/pw-browsers"

import re
import logging
from typing import Optional
from extra_service import _strip_symbol
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
]

def _safe_pct(text: str) -> Optional[float]:
    m = re.search(r"(-?[\d.]+)\s*%", text)
    return float(m.group(1)) if m else None

def _safe_num(text: str) -> Optional[float]:
    text = text.replace(",", "")
    m = re.search(r"(-?[\d.]+)", text)
    return float(m.group(1)) if m else None

def _scrape_aftermarkets_sync(symbol: str) -> dict:
    import sys
    import asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    clean = _strip_symbol(symbol)
    url = f"https://aftermarkets.in/stock/{clean}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=LAUNCH_ARGS)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=6000)
            page.wait_for_timeout(1500)
            sections = page.eval_on_selector_all(
                "section, div",
                """els => els.slice(0, 400).map(e => {
                     const t = (e.innerText || '').replace(/\\s+/g,' ').trim();
                     return (t.length > 40 && t.length < 1200) ? t : null;
                   }).filter(Boolean)"""
            )
            page_text = " ".join(sections)
            result = {"source": "Aftermarkets", "url": url, "available": True}

            m = re.search(r"(?:Market view[^•]*?)(No clear market view|Bullish|Bearish|Mixed|Cautious)", page_text, re.I)
            if m:
                result["marketView"] = m.group(1).strip()
            elif "No clear market view" in page_text:
                result["marketView"] = "No clear market view"

            safety = {}
            for label in ["Promoter pledge", "ASM list", "GSM list", "F&O ban", "Default probability"]:
                m = re.search(rf"{re.escape(label)}\s+([A-Za-z][A-Za-z\s]+?)(?=\s+(?:ASM list|GSM list|F&O ban|Default probability|Promoter pledge|business score|VALUATION|GROWTH|RETURNS|FINANCIAL|Financials|$))", page_text)
                if m:
                    safety[label] = m.group(1).strip()[:30]
            if safety:
                result["safetyChecks"] = safety

            m = re.search(r"(\d{1,3})\s+business score, of 100", page_text)
            if m:
                result["businessScore"] = int(m.group(1))

            scores = {}
            for key, label in [
                ("VALUATION", "valuation"),
                ("GROWTH", "growth"),
                ("RETURNS & MARGINS", "returnsMargins"),
                ("FINANCIAL HEALTH", "financialHealth"),
            ]:
                m = re.search(rf"{key}\s+([A-Z][A-Z\s&-]+?)\s+(\d{{1,3}})\s+([^✦]+?)(?=\s+(?:VALUATION|GROWTH|RETURNS|FINANCIAL|Financials|Concalls|$))", page_text)
                if m:
                    scores[label] = {
                        "rating": m.group(1).strip(),
                        "score": int(m.group(2)),
                        "description": m.group(3).strip()[:140],
                    }
            if scores:
                result["subScores"] = scores

            m = re.search(r"₹([\d,.]+)\s*[▴▾]\s*([+-]?[\d.]+%)\s*([+-]?₹?[\d.]+)\s*today", page_text)
            if m:
                result["livePrice"] = {
                    "price": _safe_num(m.group(1)),
                    "changePercent": _safe_pct(m.group(2)),
                    "change": _safe_num(m.group(3)),
                }

            m = re.search(r"Day low\s*₹([\d,.]+)\s*Day high\s*₹([\d,.]+)", page_text)
            if m:
                result["dayRange"] = {"low": _safe_num(m.group(1)), "high": _safe_num(m.group(2))}

            m = re.search(r"NSE:\s*\w+\s+([^•]+?)\s+₹[\d,]+\s*Cr\s+[“\"]([^”\"]+)[”\"]", page_text)
            if m:
                result["sectorTag"] = m.group(1).strip()[:80]
                result["editorialQuote"] = m.group(2).strip()[:200]

            return result
    except Exception as e:
        logger.error(f"aftermarkets scrape error: {e}")
        return {"available": False, "error": str(e)[:200], "url": url}

import asyncio
async def scrape_aftermarkets(symbol: str) -> dict:
    return await asyncio.to_thread(_scrape_aftermarkets_sync, symbol)


def _scrape_trendlyne_sync(symbol: str) -> dict:
    import sys
    import asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    clean = _strip_symbol(symbol)
    url = f"https://trendlyne.com/equity/{clean}/forecasts/"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=LAUNCH_ARGS)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=6000)
            page.wait_for_timeout(1500)
            
            text = page.evaluate("document.body.innerText")
            
            pe_match = re.search(r"PE TTM[^\d]*([0-9\.]+)", text)
            roe_match = re.search(r"ROE[^\d]*([0-9\.]+)", text)
            roce_match = re.search(r"ROCE[^\d]*([0-9\.]+)", text)
            pb_match = re.search(r"PB TTM[^\d]*([0-9\.]+)", text)
            eps_match = re.search(r"EPS[^\d]*([0-9\.]+)", text)
            
            return {
                "available": True,
                "url": url,
                "fundamentals": {
                    "PE_Ratio": pe_match.group(1) if pe_match else None,
                    "PB_Ratio": pb_match.group(1) if pb_match else None,
                    "ROE": roe_match.group(1) if roe_match else None,
                    "ROCE": roce_match.group(1) if roce_match else None,
                    "EPS": eps_match.group(1) if eps_match else None
                }
            }
    except Exception as e:
        logger.error(f"trendlyne scrape error: {e}")
        return {"available": False, "error": str(e)[:200]}

async def scrape_trendlyne(symbol: str) -> dict:
    return await asyncio.to_thread(_scrape_trendlyne_sync, symbol)

import httpx
async def scrape_tickertape(symbol: str) -> dict:
    """Tickertape provides structured risk, valuation, and fundamental ratios publicly."""
    clean = _strip_symbol(symbol)
    url = f"https://api.tickertape.in/search?text={clean}"
    try:
        async with httpx.AsyncClient() as client:
            search_res = await client.get(url, timeout=10)
            search_data = search_res.json()
            if not search_data.get("data", {}).get("stocks"):
                return {"available": False, "reason": "Not found on Tickertape."}
            
            sid = search_data["data"]["stocks"][0]["sid"]
            info_url = f"https://api.tickertape.in/stocks/info/{sid}"
            info_res = await client.get(info_url, timeout=10)
            info_data = info_res.json().get("data", {})
            
            ratios = info_data.get("ratios", {})
            labels = info_data.get("labels", {})
            
            holdings_url = f"https://api.tickertape.in/stocks/holdings/{sid}"
            holdings_res = await client.get(holdings_url, timeout=10)
            holdings_data = holdings_res.json().get("data", [])
            
            promoter_pledged = None
            promoter_total = None
            if holdings_data and len(holdings_data) > 0:
                latest = holdings_data[-1].get("data", {})
                promoter_pledged = latest.get("pmPctP")
                promoter_total = latest.get("pmPctT")
                
            deals_url = f"https://api.tickertape.in/stocks/deals/{sid}"
            deals_res = await client.get(deals_url, timeout=10)
            recent_deals = []
            if deals_res.status_code == 200:
                deals_data = deals_res.json().get("data", [])
                if deals_data:
                    for d in deals_data[:5]:
                        recent_deals.append({
                            "date": d.get("date"),
                            "type": d.get("action"),
                            "party": d.get("clientName"),
                            "price": d.get("price")
                        })

            return {
                "available": True,
                "url": f"https://www.tickertape.in/stocks/{info_data.get('slug', '').split('/')[-1] or sid}",
                "ratios": {
                    "pe": ratios.get("pe"),
                    "pb": ratios.get("pb"),
                    "roe": ratios.get("roe"),
                    "divYield": ratios.get("divYield")
                },
                "labels": {
                    "marketCap": labels.get("marketCap", {}).get("title"),
                    "risk": labels.get("risk", {}).get("title"),
                    "sector": labels.get("sector", {}).get("title")
                },
                "promoter": {
                    "pledgedPercentage": promoter_pledged,
                    "totalPercentage": promoter_total
                },
                "recentDeals": recent_deals
            }
    except Exception as e:
        logger.error(f"tickertape scrape error: {e}")
        return {"available": False, "error": str(e)[:200]}


async def shutdown():
    pass
async def scrape_delivery_volume(symbol: str) -> dict:
    from datetime import date, timedelta
    from jugaad_data.nse import full_bhavcopy_save
    import pandas as pd
    import os
    
    clean = _strip_symbol(symbol)
    try:
        # Find the last valid trading day
        d = date.today()
        if d.weekday() >= 5: # Saturday or Sunday
            d = d - timedelta(days=d.weekday() - 4)
            
        os.makedirs("bhavcopy", exist_ok=True)
        date_str = d.strftime("%d%b%Y")
        expected_file = f"bhavcopy/sec_bhavdata_full_{date_str}bhav.csv"
        
        # Try finding the latest available if today's isn't published yet
        for i in range(5):
            test_d = d - timedelta(days=i)
            if test_d.weekday() >= 5:
                continue
            test_date_str = test_d.strftime("%d%b%Y")
            test_file = f"bhavcopy/sec_bhavdata_full_{test_date_str}bhav.csv"
            if os.path.exists(test_file):
                expected_file = test_file
                break
        else:
            # If not found locally, download the latest weekday
            try:
                full_bhavcopy_save(d, "bhavcopy")
                expected_file = f"bhavcopy/sec_bhavdata_full_{d.strftime('%d%b%Y')}bhav.csv"
            except Exception:
                # Fallback to yesterday if today's is not ready
                d = d - timedelta(days=1 if d.weekday() != 0 else 3)
                full_bhavcopy_save(d, "bhavcopy")
                expected_file = f"bhavcopy/sec_bhavdata_full_{d.strftime('%d%b%Y')}bhav.csv"
                
        if not os.path.exists(expected_file):
             return {"available": False, "error": "Bhavcopy not found"}
             
        df = await asyncio.to_thread(pd.read_csv, expected_file)
        df.columns = df.columns.str.strip()
        df['SYMBOL'] = df['SYMBOL'].astype(str).str.strip()
        df['SERIES'] = df['SERIES'].astype(str).str.strip()
        
        row = df[(df['SYMBOL'] == clean) & (df['SERIES'] == 'EQ')]
        if row.empty:
            return {"available": False, "error": "Symbol not found in Bhavcopy"}
            
        deliv_per = row['DELIV_PER'].values[0]
        deliv_qty = row['DELIV_QTY'].values[0]
        def safe_float(v):
            try:
                return float(v)
            except:
                return None
        
        return {
            "available": True,
            "deliveryPercentage": safe_float(deliv_per),
            "deliveryQuantity": safe_float(deliv_qty)
        }
    except Exception as e:
        logger.error(f"delivery scrape error: {e}")
        return {"available": False, "error": str(e)[:200]}
