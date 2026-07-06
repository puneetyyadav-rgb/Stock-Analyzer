# StockSentinel India (v2) — New Features Guide
**Written for Non-Tech & Finance Professionals | Plain English & Simple Real-World Examples**

Over the past few days, your StockSentinel terminal has evolved from a basic stock charting tool into an **Institutional-Grade Quantitative Trading Dashboard**. We have integrated the exact risk controls and algorithmic strategies used by top hedge funds (like AQR, Citadel, and Indian prop desks like AlphaGrep)—but designed them to be completely transparent and easy to understand.

Here is a complete, plain-English breakdown of all **7 major features** added to your system and how they protect your money.

---

## 1. 🏛️ Institutional Portfolio Builder (Hierarchical Risk Parity - HRP)
* **What it is:** A smart portfolio allocator that replaces old-school "put equal money in every stock" rules. It groups stocks by how they move together and puts more money into steadier, safer companies while putting less money into volatile, wild companies.
* **The Simple Example:** Imagine you own an **Umbrella shop** and an **Ice Cream shop**. When it rains, umbrellas sell; when it’s sunny, ice cream sells. If you put 100% of your savings into two umbrella shops, a sunny month will bankrupt you! 
* **How it helps you:** Our algorithm automatically scans how Nifty stocks correlate. If you select Reliance and ONGC, it realizes ONGC is a bumpy ride and Reliance is much smoother. It allocates **57% of your money to Reliance** and **43% to ONGC**, ensuring one bad day in oil doesn't crash your entire wealth.

---

## 2. 🛡️ Kelly Position Sizing (Your Smart Financial Advisor)
* **What it is:** A mathematical formula (Fractional Kelly) that calculates **exactly how much cash you should invest** in a trade based on your winning odds and current market risk.
* **The Simple Example:** Imagine a professional poker player. When they hold a pair of Aces (great odds), they bet bigger. When the cards are unpredictable and the table is wild, they bet small or fold.
* **How it helps you:** When Indian market volatility (VIX) spikes or a stock's profit trend weakens, our engine slams the brakes. For example, on ₹10 Lakhs capital, instead of telling you to go all-in, it might say: **"Only deploy 15% (₹1,50,000) into stocks today and keep ₹8,50,000 safely in 7% Liquid FDs until the storm passes!"**

---

## 3. ⚡ Statistical Arbitrage & Pairs Trading (The Rubber Band Strategy)
* **What it is:** A scanner that finds two competitor stocks in the same industry (like HDFC Bank vs. ICICI Bank, or TCS vs. Infosys) whose share prices usually walk hand-in-hand. When one suddenly jumps ahead and the other lags behind, it triggers a signal to buy the cheap one and sell the expensive one.
* **The Simple Example:** Imagine two dogs walking side-by-side on a shared leash. If Dog A suddenly sprints 10 feet ahead after a squirrel, you know the leash (market forces) will eventually snap Dog A back and pull Dog B forward until they are walking together again.
* **How it helps you:** We make money when that price gap snaps back to normal. The best part? **You don't care if the Nifty crashes or booms!** Because you bought one stock and sold another, market-wide crashes don't hurt you.

---

## 4. 💧 Liquidity & Turnover Filter (The Exit Door Safety Check)
* **What it is:** An automated safety rule that blocks stocks with less than **₹5 Crores of daily trading volume** from entering your top quant rankings.
* **The Simple Example:** Buying an illiquid penny stock is like walking into a crowded movie theater that only has a **tiny, locked exit door**. It is super easy to walk in, but if someone yells "FIRE!" and everyone tries to leave at once, you get crushed!
* **How it helps you:** A backtest showing +20% returns on a penny stock is a lie because when you try to sell your shares, there are no buyers! Our filter guarantees you only trade stocks with **massive, wide-open exit doors** (like Reliance, Zomato, HAL, or Tata Motors) where you can enter and exit multi-lakh positions instantly without price slippage.

---

## 5. 📰 48-Hour News & Event Gate (The Cool-Off Period)
* **What it is:** An AI news scanner that automatically blocks buy signals on any stock for **48 hours (2 days)** if a major negative news headline, regulatory investigation, or bad earnings report just came out.
* **The Simple Example:** If a popular restaurant gets shut down by health inspectors today, you don't rush to buy its shares tomorrow morning just because the price dropped 10%! You wait 48 hours for the dust to settle to make sure there aren't more skeletons in the closet.
* **How it helps you:** In your dashboard, if a stock has fresh bad news, the UI displays a red badge: **"Wait 2 days | [Exact Negative Headline]"** and pauses trading, preventing you from catching "falling knives."

---

## 6. ⏱️ Multi-Timeframe Trend Confirmation (15m, 60m, & Daily Alignment)
* **What it is:** A verification engine that checks intraday chart trends (15-minute and 1-hour candles) before approving a daily breakout trade.
* **The Simple Example:** Before setting sail across the ocean, a ship captain doesn't just look at yesterday's weather report—they look out the window at the **current hourly wind and ocean waves**. 
* **How it helps you:** Often, a stock looks great on a daily chart, but big institutions are quietly dumping shares every 15 minutes today! By checking alignment across 15m, 60m, and daily charts, our system generates a **Timeframe Confirmation Score (/100)**, saving you from buying right before an intraday sell-off.

---

## 7. 🔍 Universal Indian Market Search & Sector Overlays
* **What it is:** You can now search and add **ANY stock listed on the NSE/BSE** into your portfolio builder or pairs scanner, complete with real-time sector momentum multipliers.
* **The Simple Example:** In a horse race, it is easier to win if you bet on horses running with the wind at their back rather than running against a hurricane.
* **How it helps you:** If the IT sector is booming (+5% vs Nifty) and Banking is sluggish (-2%), our **Sector Overlay** automatically boosts the Quant Score of IT stocks and reduces the score of Banking stocks. This ensures you are always investing your money in market-leading sectors!

---

## 📋 Summary: Why This System is Different
Old retail stock apps simply show you indicators like RSI or Moving Averages and leave you to guess. 

**StockSentinel India (v2)** acts like an institutional risk manager sitting next to you. Before it lets you invest a single Rupee, it checks:
1. *Is the exit door wide open?* (Liquidity Filter ✓)
2. *Is there any fresh bad news?* (48-Hour News Gate ✓)
3. *Are intraday charts agreeing with daily charts?* (Multi-Timeframe Confirm ✓)
4. *How much cash should we keep safe in FDs?* (Kelly Sizing ✓)
5. *How do we balance risk across stocks?* (HRP Correlation Clustering ✓)
