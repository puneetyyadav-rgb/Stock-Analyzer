import os
import json
import logging
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "forensic_cache.json")
FORENSIC_TTL_DAYS = int(os.environ.get("FORENSIC_TTL_DAYS", "7"))
RF_RATE = float(os.environ.get("RF_RATE", "7.0"))
ERP_RATE = float(os.environ.get("ERP_RATE", "6.0"))

def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read forensic cache: {e}")
    return {}

def _save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception as e:
        logger.warning(f"Failed to save forensic cache: {e}")

def _df_to_json_dict(df):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {"index": [], "columns": [], "data": []}
    cols = [str(c) for c in df.columns]
    idx = [str(r) for r in df.index]
    data = df.where(pd.notnull(df), None).values.tolist()
    return {"index": idx, "columns": cols, "data": data}

def _json_dict_to_df(d):
    if not d or not d.get("index"):
        return pd.DataFrame()
    df = pd.DataFrame(data=d["data"], index=d["index"], columns=d["columns"])
    return df

def _annual_frames(symbol: str):
    """
    Fetches bs/inc/cf once; JSON cache to backend/forensic_cache.json keyed by symbol
    with updatedAt ISO; fresh for FORENSIC_TTL_DAYS (default 7).
    Returns (bs, inc, cf) DataFrames.
    """
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    
    if symbol in cache:
        entry = cache[symbol]
        updated_at_str = entry.get("updatedAt")
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                if (now - updated_at).total_seconds() <= FORENSIC_TTL_DAYS * 86400:
                    bs = _json_dict_to_df(entry.get("bs"))
                    inc = _json_dict_to_df(entry.get("inc"))
                    cf = _json_dict_to_df(entry.get("cf"))
                    return bs, inc, cf
            except Exception:
                pass
                
    logger.info(f"[{symbol}] Fetching annual statements from yfinance for forensic math...")
    t = yf.Ticker(symbol)
    try:
        bs = t.balance_sheet
    except Exception:
        bs = pd.DataFrame()
    try:
        inc = t.financials
    except Exception:
        inc = pd.DataFrame()
    try:
        cf = t.cashflow
    except Exception:
        cf = pd.DataFrame()
        
    if not isinstance(bs, pd.DataFrame): bs = pd.DataFrame()
    if not isinstance(inc, pd.DataFrame): inc = pd.DataFrame()
    if not isinstance(cf, pd.DataFrame): cf = pd.DataFrame()
    
    cache[symbol] = {
        "updatedAt": now.isoformat(),
        "bs": _df_to_json_dict(bs),
        "inc": _df_to_json_dict(inc),
        "cf": _df_to_json_dict(cf)
    }
    _save_cache(cache)
    
    return bs, inc, cf

def _val(df, aliases, year_idx: int = 0):
    """
    Case-insensitive alias lookup on df for column at year_idx (0=newest year, 1=prior year).
    Returns float or None.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    if year_idx < 0 or year_idx >= len(df.columns):
        return None
        
    col = df.columns[year_idx]
    idx_lower_map = {str(k).strip().lower(): k for k in df.index}
    
    for alias in aliases:
        alias_clean = alias.strip().lower()
        if alias_clean in idx_lower_map:
            orig_row = idx_lower_map[alias_clean]
            try:
                val = df.loc[orig_row, col]
                if pd.notnull(val):
                    return float(val)
            except Exception:
                pass
    return None

def piotroski_f_score(frames):
    """
    Computes Piotroski F-Score (0-9) across Profitability, Leverage/Liquidity, and Efficiency.
    """
    bs, inc, cf = frames
    if bs.empty or inc.empty or cf.empty or len(bs.columns) < 2 or len(inc.columns) < 2:
        # Check if we have at least 1 year for partial computation or if <2 years fail gracefully
        if len(bs.columns) < 1 or len(inc.columns) < 1:
            return {"available": False, "reason": "No financial statements available"}
            
    try:
        # We need year 0 (current) and year 1 (prior)
        if len(bs.columns) < 2 or len(inc.columns) < 2 or len(cf.columns) < 1:
            return {"available": False, "reason": "Requires at least 2 years of history for F-Score YoY comparisons"}
            
        ni_0 = _val(inc, ["Net Income", "net income", "Net Income Common Stockholders", "Net Income Continuous Operations"], 0)
        ta_0 = _val(bs, ["Total Assets", "total assets"], 0)
        ta_1 = _val(bs, ["Total Assets", "total assets"], 1)
        ocf_0 = _val(cf, ["Operating Cash Flow", "operating cash flow", "Cash Flow From Continuing Operating Activities", "Total Cash From Operating Activities"], 0)
        
        if ni_0 is None or ta_0 is None or ta_0 == 0 or ocf_0 is None or ta_1 is None or ta_1 == 0:
            return {"available": False, "reason": "Missing core profitability fields (Net Income / Assets / OCF)"}
            
        roa_0 = ni_0 / ta_0
        ni_1 = _val(inc, ["Net Income", "net income", "Net Income Common Stockholders", "Net Income Continuous Operations"], 1)
        roa_1 = (ni_1 / ta_1) if ni_1 is not None else roa_0
        
        # F1: ROA > 0
        f1 = 1 if roa_0 > 0 else 0
        # F2: OCF > 0
        f2 = 1 if ocf_0 > 0 else 0
        # F3: Delta ROA > 0
        f3 = 1 if roa_0 > roa_1 else 0
        # F4: Accruals (OCF > Net Income)
        f4 = 1 if ocf_0 > ni_0 else 0
        
        # Leverage, Liquidity and Source of Funds
        ltd_0 = _val(bs, ["Long Term Debt", "long term debt", "Long Term Debt And Capital Lease Obligation", "Total Debt", "total debt"], 0) or 0
        ltd_1 = _val(bs, ["Long Term Debt", "long term debt", "Long Term Debt And Capital Lease Obligation", "Total Debt", "total debt"], 1) or 0
        lev_0 = ltd_0 / ta_0
        lev_1 = ltd_1 / ta_1
        # F5: Delta Leverage < 0 (lower is better)
        f5 = 1 if lev_0 < lev_1 else 0
        
        ca_0 = _val(bs, ["Current Assets", "current assets", "Total Current Assets"], 0)
        cl_0 = _val(bs, ["Current Liabilities", "current liabilities", "Total Current Liabilities"], 0)
        ca_1 = _val(bs, ["Current Assets", "current assets", "Total Current Assets"], 1)
        cl_1 = _val(bs, ["Current Liabilities", "current liabilities", "Total Current Liabilities"], 1)
        
        if ca_0 and cl_0 and cl_0 > 0 and ca_1 and cl_1 and cl_1 > 0:
            cr_0 = ca_0 / cl_0
            cr_1 = ca_1 / cl_1
            f6 = 1 if cr_0 > cr_1 else 0
        else:
            f6 = 1  # Give benefit of doubt if current ratio fields are structured differently
            
        shares_0 = _val(bs, ["Ordinary Shares Number", "ordinary shares number", "Share Issued", "share issued", "Common Stock"], 0)
        shares_1 = _val(bs, ["Ordinary Shares Number", "ordinary shares number", "Share Issued", "share issued", "Common Stock"], 1)
        if shares_0 and shares_1:
            f7 = 1 if shares_0 <= shares_1 * 1.01 else 0
        else:
            f7 = 1
            
        # Operating Efficiency
        gp_0 = _val(inc, ["Gross Profit", "gross profit"], 0)
        rev_0 = _val(inc, ["Total Revenue", "total revenue", "Operating Revenue"], 0)
        gp_1 = _val(inc, ["Gross Profit", "gross profit"], 1)
        rev_1 = _val(inc, ["Total Revenue", "total revenue", "Operating Revenue"], 1)
        
        if not gp_0 and rev_0:
            cor_0 = _val(inc, ["Cost Of Revenue", "cost of revenue", "Operating Expense"], 0) or 0
            gp_0 = rev_0 - cor_0
        if not gp_1 and rev_1:
            cor_1 = _val(inc, ["Cost Of Revenue", "cost of revenue", "Operating Expense"], 1) or 0
            gp_1 = rev_1 - cor_1
            
        if gp_0 and rev_0 and rev_0 > 0 and gp_1 and rev_1 and rev_1 > 0:
            gm_0 = gp_0 / rev_0
            gm_1 = gp_1 / rev_1
            f8 = 1 if gm_0 > gm_1 else 0
        else:
            f8 = 1
            
        if rev_0 and ta_0 > 0 and rev_1 and ta_1 > 0:
            at_0 = rev_0 / ta_0
            at_1 = rev_1 / ta_1
            f9 = 1 if at_0 > at_1 else 0
        else:
            f9 = 1
            
        score = f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9
        verdict = "Strong / Financially Sound" if score >= 7 else ("Moderate / Stable" if score >= 4 else "Weak / Distressed")
        
        return {
            "available": True,
            "score": score,
            "tests": {
                "f1_roa_pos": f1,
                "f2_ocf_pos": f2,
                "f3_roa_improving": f3,
                "f4_accruals_quality": f4,
                "f5_leverage_improving": f5,
                "f6_liquidity_improving": f6,
                "f7_no_dilution": f7,
                "f8_margin_improving": f8,
                "f9_turnover_improving": f9
            },
            "verdict": verdict
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}

def beneish_m_score(frames):
    """
    Computes Beneish M-Score (8 indices). Returns available:False if < 2 years.
    Threshold -2.22 (scores > -1.78 indicate high accounting manipulation risk).
    """
    bs, inc, cf = frames
    if bs.empty or inc.empty or len(bs.columns) < 2 or len(inc.columns) < 2:
        return {"available": False, "reason": "Requires 2 consecutive years of balance sheet and income statement data"}
        
    try:
        rev_0 = _val(inc, ["Total Revenue", "total revenue", "Operating Revenue"], 0)
        rev_1 = _val(inc, ["Total Revenue", "total revenue", "Operating Revenue"], 1)
        rec_0 = _val(bs, ["Receivables", "receivables", "Accounts Receivable", "Net Receivables"], 0) or 0
        rec_1 = _val(bs, ["Receivables", "receivables", "Accounts Receivable", "Net Receivables"], 1) or 0
        
        if not rev_0 or not rev_1 or rev_0 == 0 or rev_1 == 0:
            return {"available": False, "reason": "Missing Total Revenue for YoY index computation"}
            
        # DSRI: Days Sales in Receivables Index
        dsri = (rec_0 / rev_0) / (rec_1 / rev_1) if (rec_1 > 0 and rev_1 > 0) else 1.0
        
        # GMI: Gross Margin Index
        gp_0 = _val(inc, ["Gross Profit", "gross profit"], 0) or rev_0 * 0.4
        gp_1 = _val(inc, ["Gross Profit", "gross profit"], 1) or rev_1 * 0.4
        gm_0 = gp_0 / rev_0 if rev_0 > 0 else 0.4
        gm_1 = gp_1 / rev_1 if rev_1 > 0 else 0.4
        gmi = (gm_1 / gm_0) if gm_0 > 0 else 1.0
        
        # AQI: Asset Quality Index
        ta_0 = _val(bs, ["Total Assets", "total assets"], 0)
        ta_1 = _val(bs, ["Total Assets", "total assets"], 1)
        if not ta_0 or not ta_1 or ta_0 == 0 or ta_1 == 0:
            return {"available": False, "reason": "Missing Total Assets"}
            
        ca_0 = _val(bs, ["Current Assets", "current assets", "Total Current Assets"], 0) or (ta_0 * 0.4)
        ca_1 = _val(bs, ["Current Assets", "current assets", "Total Current Assets"], 1) or (ta_1 * 0.4)
        ppe_0 = _val(bs, ["Net PPE", "net ppe", "Plant Property Equipment", "Net Property Plant And Equipment", "Property Plant And Equipment"], 0) or (ta_0 * 0.4)
        ppe_1 = _val(bs, ["Net PPE", "net ppe", "Plant Property Equipment", "Net Property Plant And Equipment", "Property Plant And Equipment"], 1) or (ta_1 * 0.4)
        
        non_curr_qual_0 = max(0.0, 1.0 - ((ca_0 + ppe_0) / ta_0))
        non_curr_qual_1 = max(0.0, 1.0 - ((ca_1 + ppe_1) / ta_1))
        aqi = (non_curr_qual_0 / non_curr_qual_1) if non_curr_qual_1 > 0 else 1.0
        
        # SGI: Sales Growth Index
        sgi = rev_0 / rev_1
        
        # DEPI: Depreciation Index
        dep_0 = _val(inc, ["Depreciation And Amortization", "depreciation and amortization", "Depreciation"], 0) or (ppe_0 * 0.1)
        dep_1 = _val(inc, ["Depreciation And Amortization", "depreciation and amortization", "Depreciation"], 1) or (ppe_1 * 0.1)
        dep_rate_0 = dep_0 / (ppe_0 + dep_0) if (ppe_0 + dep_0) > 0 else 0.1
        dep_rate_1 = dep_1 / (ppe_1 + dep_1) if (ppe_1 + dep_1) > 0 else 0.1
        depi = (dep_rate_1 / dep_rate_0) if dep_rate_0 > 0 else 1.0
        
        # SGAI: SG&A Expense Index
        sga_0 = _val(inc, ["Selling General And Administration", "selling general and administration", "Selling And Marketing Expense"], 0) or (rev_0 * 0.15)
        sga_1 = _val(inc, ["Selling General And Administration", "selling general and administration", "Selling And Marketing Expense"], 1) or (rev_1 * 0.15)
        sgai = (sga_0 / rev_0) / (sga_1 / rev_1) if (sga_1 > 0 and rev_1 > 0) else 1.0
        
        # LVGI: Leverage Index
        ltd_0 = _val(bs, ["Total Debt", "total debt", "Long Term Debt"], 0) or 0
        ltd_1 = _val(bs, ["Total Debt", "total debt", "Long Term Debt"], 1) or 0
        lev_0 = ltd_0 / ta_0
        lev_1 = ltd_1 / ta_1
        lvgi = (lev_0 / lev_1) if lev_1 > 0 else 1.0
        
        # TATA: Total Accruals to Total Assets
        ni_0 = _val(inc, ["Net Income", "net income", "Pretax Income", "Income Before Tax"], 0) or 0
        ocf_0 = _val(cf, ["Operating Cash Flow", "operating cash flow", "Total Cash From Operating Activities"], 0) or (ni_0 * 0.9)
        tata = (ni_0 - ocf_0) / ta_0
        
        # 8-variable Beneish M-Score formula
        m_score = -4.84 + (0.920 * dsri) + (0.528 * gmi) + (0.404 * aqi) + (0.892 * sgi) + (0.115 * depi) - (0.172 * sgai) + (4.679 * tata) - (0.327 * lvgi)
        m_score = round(float(m_score), 2)
        
        manipulator_risk = m_score > -1.78
        verdict = "High Accounting Manipulation Risk" if manipulator_risk else ("Moderate Risk" if m_score > -2.22 else "Low Manipulation Risk / Clean")
        
        return {
            "available": True,
            "mScore": m_score,
            "indices": {
                "dsri": round(dsri, 2),
                "gmi": round(gmi, 2),
                "aqi": round(aqi, 2),
                "sgi": round(sgi, 2),
                "depi": round(depi, 2),
                "sgai": round(sgai, 2),
                "lvgi": round(lvgi, 2),
                "tata": round(tata, 4)
            },
            "manipulatorRisk": manipulator_risk,
            "verdict": verdict
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}

def roic_vs_wacc(frames, beta=None, market_cap=None):
    """
    Computes ROIC vs WACC. Returns available:False if core current year fields missing.
    """
    bs, inc, cf = frames
    if bs.empty or inc.empty or len(bs.columns) < 1 or len(inc.columns) < 1:
        return {"available": False, "reason": "No balance sheet or income statement data available"}
        
    try:
        op_inc = _val(inc, ["Operating Income", "operating income", "EBIT", "ebit", "Operating Profit"], 0)
        if op_inc is None:
            # Try Gross Profit - SG&A / Operating expense
            gp = _val(inc, ["Gross Profit", "gross profit"], 0)
            opex = _val(inc, ["Operating Expense", "operating expense", "Selling General And Administration"], 0)
            if gp is not None and opex is not None:
                op_inc = gp - opex
            else:
                return {"available": False, "reason": "Missing Operating Income (EBIT)"}
                
        # Tax rate
        tax_prov = _val(inc, ["Tax Provision", "tax provision", "Income Tax Expense"], 0)
        pretax = _val(inc, ["Pretax Income", "pretax income", "Income Before Tax"], 0)
        if tax_prov is not None and pretax and pretax > 0:
            tax_rate = max(0.0, min(0.40, tax_prov / pretax))
        else:
            tax_rate = 0.2517  # Fallback India corporate tax rate
            
        nopat = op_inc * (1.0 - tax_rate)
        
        # Invested Capital
        inv_cap = _val(bs, ["Invested Capital", "invested capital"], 0)
        if not inv_cap or inv_cap <= 0:
            # Fallback: Total Debt + Stockholders Equity - Cash
            total_debt = _val(bs, ["Total Debt", "total debt", "Long Term Debt"], 0) or 0
            equity = _val(bs, ["Stockholders Equity", "stockholders equity", "Total Equity Gross Minority Interest", "Total Stockholder Equity"], 0) or 0
            cash = _val(bs, ["Cash And Cash Equivalents", "cash and cash equivalents", "Cash"], 0) or 0
            inv_cap = total_debt + equity - cash
            
        if not inv_cap or inv_cap <= 0:
            return {"available": False, "reason": "Missing or negative Invested Capital"}
            
        roic = (nopat / inv_cap) * 100.0
        
        # WACC computation
        eff_beta = float(beta) if beta and float(beta) > 0 else 1.0
        cost_of_equity = RF_RATE + (eff_beta * ERP_RATE)
        
        total_debt = _val(bs, ["Total Debt", "total debt", "Long Term Debt"], 0) or 0
        int_exp = _val(inc, ["Interest Expense", "interest expense", "Interest Expense Non Operating"], 0)
        
        if int_exp and total_debt and total_debt > 0:
            pretax_cod = min(0.20, abs(int_exp) / total_debt) * 100.0
        else:
            pretax_cod = 8.0  # Fallback 8% interest rate
            
        cost_of_debt = pretax_cod * (1.0 - tax_rate)
        
        # Weights
        mcap = float(market_cap) if market_cap and float(market_cap) > 0 else (inv_cap * 0.7)
        we = mcap / (mcap + total_debt) if (mcap + total_debt) > 0 else 0.7
        wd = 1.0 - we
        
        wacc = (we * cost_of_equity) + (wd * cost_of_debt)
        
        roic_val = round(float(roic), 2)
        wacc_val = round(float(wacc), 2)
        spread = round(roic_val - wacc_val, 2)
        
        if spread > 2.0:
            category = "Wealth Compounder"
        elif spread < 0.0:
            category = "Capital Destroyer"
        else:
            category = "Marginal"
            
        return {
            "available": True,
            "roic": roic_val,
            "wacc": wacc_val,
            "spread": spread,
            "category": category
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}

def analyze_forensics(symbol: str, beta=None, market_cap=None):
    """
    Public API orchestrating Piotroski, Beneish, and ROIC vs WACC.
    Never raises an exception; always returns a structured dictionary.
    """
    try:
        frames = _annual_frames(symbol)
        f_res = piotroski_f_score(frames)
        m_res = beneish_m_score(frames)
        r_res = roic_vs_wacc(frames, beta=beta, market_cap=market_cap)
        
        alert = None
        alerts_list = []
        if m_res.get("available") and m_res.get("manipulatorRisk"):
            alerts_list.append(f"⚠️ High Earnings-Manipulation Risk (Beneish M-Score: {m_res.get('mScore')})")
        if f_res.get("available") and f_res.get("score", 9) <= 3:
            alerts_list.append(f"⚠️ Severely Weak Financial Health (Piotroski F-Score: {f_res.get('score')}/9)")
        if r_res.get("available") and r_res.get("category") == "Capital Destroyer":
            alerts_list.append(f"⚠️ Structural Value Destruction (ROIC {r_res.get('roic')}% < WACC {r_res.get('wacc')}%)")
            
        if alerts_list:
            alert = " | ".join(alerts_list)
            
        return {
            "available": True,
            "symbol": symbol,
            "piotroski": f_res,
            "beneish": m_res,
            "roicWacc": r_res,
            "forensicAlert": alert
        }
    except Exception as e:
        logger.error(f"[{symbol}] Forensic math failed: {e}")
        return {
            "available": False,
            "reason": str(e),
            "piotroski": {"available": False, "reason": "Error"},
            "beneish": {"available": False, "reason": "Error"},
            "roicWacc": {"available": False, "reason": "Error"},
            "forensicAlert": None
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== Running forensic_service.py self-check ===")
    
    # 1. Synthetic clean statements
    bs_clean = pd.DataFrame({
        "2025": [1000, 500, 200, 300, 100, 800, 100],
        "2024": [900, 450, 220, 250, 90, 700, 100]
    }, index=["Total Assets", "Current Assets", "Current Liabilities", "Receivables", "Total Debt", "Invested Capital", "Ordinary Shares Number"])
    inc_clean = pd.DataFrame({
        "2025": [1200, 400, 150, 10, 30],
        "2024": [1000, 320, 110, 12, 25]
    }, index=["Total Revenue", "Gross Profit", "Operating Income", "Interest Expense", "Net Income"])
    cf_clean = pd.DataFrame({
        "2025": [50],
        "2024": [40]
    }, index=["Operating Cash Flow"])
    
    frames_clean = (bs_clean, inc_clean, cf_clean)
    f_c = piotroski_f_score(frames_clean)
    m_c = beneish_m_score(frames_clean)
    r_c = roic_vs_wacc(frames_clean, beta=1.0, market_cap=5000)
    print("Clean -> F:", f_c.get("score"), "M:", m_c.get("mScore"), "ROIC:", r_c.get("roic"), "WACC:", r_c.get("wacc"), "Category:", r_c.get("category"))
    assert f_c.get("available") and f_c.get("score", 0) >= 7, "Clean synthetic F-Score assertion failed!"
    assert m_c.get("available") and m_c.get("mScore", 0) < -2.22, "Clean synthetic M-Score assertion failed!"
    assert r_c.get("available") and r_c.get("spread", -10) > 0, "Clean synthetic ROIC > WACC assertion failed!"
    
    # 2. Synthetic manipulated statements (inflate Receivables + Total Revenue, hold OCF flat)
    bs_manip = pd.DataFrame({
        "2025": [1500, 900, 200, 800, 300, 800, 100],
        "2024": [1000, 450, 200, 200, 100, 700, 100]
    }, index=["Total Assets", "Current Assets", "Current Liabilities", "Receivables", "Total Debt", "Invested Capital", "Ordinary Shares Number"])
    inc_manip = pd.DataFrame({
        "2025": [2000, 600, 200, 20, 100],
        "2024": [1000, 400, 110, 10, 50]
    }, index=["Total Revenue", "Gross Profit", "Operating Income", "Interest Expense", "Net Income"])
    cf_manip = pd.DataFrame({
        "2025": [10],
        "2024": [40]
    }, index=["Operating Cash Flow"])
    
    frames_manip = (bs_manip, inc_manip, cf_manip)
    m_m = beneish_m_score(frames_manip)
    print("Manipulated -> M:", m_m.get("mScore"), "Risk:", m_m.get("manipulatorRisk"), "Verdict:", m_m.get("verdict"))
    assert m_m.get("available") and m_m.get("mScore", -5) > -1.78, "Manipulated synthetic M-Score assertion failed!"
    assert m_m.get("manipulatorRisk") is True, "Manipulated synthetic manipulatorRisk assertion failed!"
    
    # 3. Single-year frame (asserts graceful partial behavior)
    bs_1y = pd.DataFrame({"2025": [1000, 500, 200, 300, 100, 800]}, index=["Total Assets", "Current Assets", "Current Liabilities", "Receivables", "Total Debt", "Invested Capital"])
    inc_1y = pd.DataFrame({"2025": [1200, 400, 150, 10, 30]}, index=["Total Revenue", "Gross Profit", "Operating Income", "Interest Expense", "Net Income"])
    cf_1y = pd.DataFrame({"2025": [50]}, index=["Operating Cash Flow"])
    
    frames_1y = (bs_1y, inc_1y, cf_1y)
    m_1y = beneish_m_score(frames_1y)
    r_1y = roic_vs_wacc(frames_1y, beta=1.0, market_cap=5000)
    print("Single Year -> Beneish Available:", m_1y.get("available"), "ROIC Available:", r_1y.get("available"), "ROIC:", r_1y.get("roic"))
    assert m_1y.get("available") is False, "Single year Beneish should be unavailable!"
    assert r_1y.get("available") is True, "Single year ROIC should be available (graceful partial)!"
    
    # 4. Live spot-check RELIANCE
    print("\n--- Live spot-check analyze_forensics('RELIANCE.NS') ---")
    try:
        res = analyze_forensics("RELIANCE.NS", beta=1.1, market_cap=17000000000000)
        print("Live RELIANCE:", json.dumps(res, indent=2))
    except Exception as ex:
        print("Live spot-check skipped/offline:", ex)
        
    print("\nALL SYNTHETIC ASSERTIONS PASSED SUCCESSFULLY! Task 1 complete.")
