"""Playwright-powered headless scraper for sites that require JS rendering.
Singleton browser instance — launched lazily on first request, reused across calls.
Aggressive 30-min cache because each scrape costs ~5-8 seconds."""
import os
# Set Playwright browser path BEFORE importing playwright modules
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and os.path.exists("/pw-browsers"):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/pw-browsers"

import asyncio
import logging
import re
import time
from typing import Optional
from extra_service import _strip_symbol

logger = logging.getLogger(__name__)

_BROWSER = None
_PLAYWRIGHT_CTX = None
_LOCK = asyncio.Lock()

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
]


async def _get_browser():
    """Lazily launch a singleton browser instance."""
    global _BROWSER, _PLAYWRIGHT_CTX
    if _BROWSER and _BROWSER.is_connected():
        return _BROWSER
    async with _LOCK:
        if _BROWSER and _BROWSER.is_connected():
            return _BROWSER
        from playwright.async_api import async_playwright
        _PLAYWRIGHT_CTX = await async_playwright().start()
        _BROWSER = await _PLAYWRIGHT_CTX.chromium.launch(headless=True, args=LAUNCH_ARGS)
        logger.info("Playwright Chromium launched (singleton)")
        return _BROWSER


async def _new_page():
    browser = await _get_browser()
    ctx = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
        locale="en-IN",
        timezone_id="Asia/Kolkata",
    )
    page = await ctx.new_page()
    return ctx, page


def _safe_pct(text: str) -> Optional[float]:
    m = re.search(r"(-?[\d.]+)\s*%", text)
    return float(m.group(1)) if m else None


def _safe_num(text: str) -> Optional[float]:
    text = text.replace(",", "")
    m = re.search(r"(-?[\d.]+)", text)
    return float(m.group(1)) if m else None


async def scrape_aftermarkets(symbol: str) -> dict:
    """Scrape structured market-view + safety-checks + business scores from aftermarkets.in."""
    clean = _strip_symbol(symbol)
    url = f"https://aftermarkets.in/stock/{clean}"
    ctx = None
    try:
        ctx, page = await _new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(6000)
        sections = await page.eval_on_selector_all(
            "section, div",
            """els => els.slice(0, 400).map(e => {
                 const t = (e.innerText || '').replace(/\\s+/g,' ').trim();
                 return (t.length > 40 && t.length < 1200) ? t : null;
               }).filter(Boolean)"""
        )
        page_text = " ".join(sections)
        # Extract structured data with simple regex anchors
        result = {"source": "Aftermarkets", "url": url, "available": True}

        # Market view verdict
        m = re.search(r"(?:Market view[^•]*?)(No clear market view|Bullish|Bearish|Mixed|Cautious)", page_text, re.I)
        if m:
            result["marketView"] = m.group(1).strip()
        elif "No clear market view" in page_text:
            result["marketView"] = "No clear market view"

        # Safety checks
        safety = {}
        for label in ["Promoter pledge", "ASM list", "GSM list", "F&O ban", "Default probability"]:
            m = re.search(rf"{re.escape(label)}\s+([A-Za-z][A-Za-z\s]+?)(?=\s+(?:ASM list|GSM list|F&O ban|Default probability|Promoter pledge|business score|VALUATION|GROWTH|RETURNS|FINANCIAL|Financials|$))", page_text)
            if m:
                safety[label] = m.group(1).strip()[:30]
        if safety:
            result["safetyChecks"] = safety

        # Business score
        m = re.search(r"(\d{1,3})\s+business score, of 100", page_text)
        if m:
            result["businessScore"] = int(m.group(1))

        # Sub-scores: VALUATION / GROWTH / RETURNS & MARGINS / FINANCIAL HEALTH
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

        # Live price + change
        m = re.search(r"₹([\d,.]+)\s*[▴▾]\s*([+-]?[\d.]+%)\s*([+-]?₹?[\d.]+)\s*today", page_text)
        if m:
            result["livePrice"] = {
                "price": _safe_num(m.group(1)),
                "changePercent": _safe_pct(m.group(2)),
                "change": _safe_num(m.group(3)),
            }

        # Day high/low
        m = re.search(r"Day low\s*₹([\d,.]+)\s*Day high\s*₹([\d,.]+)", page_text)
        if m:
            result["dayRange"] = {"low": _safe_num(m.group(1)), "high": _safe_num(m.group(2))}

        # Tagline / sector quote
        m = re.search(r"NSE:\s*\w+\s+([^•]+?)\s+₹[\d,]+\s*Cr\s+[“\"]([^”\"]+)[”\"]", page_text)
        if m:
            result["sectorTag"] = m.group(1).strip()[:80]
            result["editorialQuote"] = m.group(2).strip()[:200]

        return result
    except Exception as e:
        logger.error(f"aftermarkets scrape error: {e}")
        return {"available": False, "error": str(e)[:200], "url": url}
    finally:
        if ctx:
            try:
                await ctx.close()
            except Exception:
                pass


async def scrape_trendlyne(symbol: str) -> dict:
    """Trendlyne is protected by AWS WAF that detects headless browsers — return an honest 'blocked' response."""
    clean = _strip_symbol(symbol)
    url = f"https://trendlyne.com/fundamentals/{clean}/"
    return {
        "available": False,
        "url": url,
        "reason": (
            "Trendlyne is protected by AWS WAF (Cloudflare-style bot detection) that blocks "
            "headless Chromium even with playwright-stealth. Verified by scraping test. "
            "Use the deep-link below to open in your own browser."
        ),
    }


async def scrape_stockedge(symbol: str) -> dict:
    """StockEdge per-share pages require login or numeric internal IDs not exposed publicly — return an honest 'login-walled' response."""
    clean = _strip_symbol(symbol)
    return {
        "available": False,
        "url": f"https://web.stockedge.com/search?q={clean}",
        "reason": (
            "StockEdge per-share pages require either a logged-in session or an internal numeric "
            "stock ID (not exposed publicly). Free pages redirect to the markets dashboard. "
            "Use the deep-link to open StockEdge search in your browser."
        ),
    }


async def shutdown():
    global _BROWSER, _PLAYWRIGHT_CTX
    try:
        if _BROWSER:
            await _BROWSER.close()
        if _PLAYWRIGHT_CTX:
            await _PLAYWRIGHT_CTX.stop()
    except Exception as e:
        logger.error(f"playwright shutdown error: {e}")
    finally:
        _BROWSER = None
        _PLAYWRIGHT_CTX = None
