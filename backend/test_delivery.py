import asyncio, re
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://trendlyne.com/equity/volume-analysis/RELI/reliance-industries-ltd/', timeout=20000)
        await page.wait_for_timeout(3000)
        text = await page.evaluate('document.body.innerText')
        m = re.search(r'Delivery\s*Volume\s*[\d\.,MKB]+\s*\(([\d\.]+)\s*%\)', text, re.I)
        if m:
            print("Regex matched:", m.group(1))
        else:
            print("No match")
            print(text[:1000])
        await browser.close()

asyncio.run(test())
