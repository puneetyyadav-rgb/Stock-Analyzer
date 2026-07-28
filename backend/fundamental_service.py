# -*- coding: utf-8 -*-
"""
Fundamental Service - Core 10-Pillar & Forensic Accounting Equity Research Engine
Version 3.1 - Repository-Grounded & Audit-Corrected
"""
import json
import logging
import os
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

import yfinance as yf
import fundamental_constants as fc

logger = logging.getLogger(__name__)

_CACHE_PATH = os.environ.get(
    "FUNDAMENTAL_CACHE_PATH",
    os.path.join(os.path.dirname(__file__), "fundamental_cache.json"),
)
_TTL_DAYS = int(os.environ.get("FUNDAMENTAL_TTL_DAYS", "7"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(updated_at: Optional[str]) -> bool:
    if not updated_at:
        return False
    try:
        dt = datetime.fromisoformat(updated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return _now() - dt <= timedelta(days=_TTL_DAYS)
    except Exception:
        return False


def _load_cache() -> Dict[str, dict]:
    try:
        if not os.path.exists(_CACHE_PATH):
            return {}
        with open(_CACHE_PATH, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return raw.get("symbols", {}) if isinstance(raw, dict) else {}
    except Exception as exc:
        logger.warning("fundamental cache read failed: %s", exc)
        return {}


def _save_cache(symbols: Dict[str, dict]) -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"updatedAt": _now().isoformat(), "symbols": symbols}, fh, indent=2, sort_keys=True)
    except Exception as exc:
        logger.warning("fundamental cache write failed: %s", exc)


def _df_to_dict(df) -> Dict[str, List[Optional[float]]]:
    if df is None or getattr(df, "empty", True):
        return {}
    out = {}
    for idx, row in df.iterrows():
        key = str(idx).strip()
        vals = []
        for val in row.values:
            try:
                if val is None or (isinstance(val, float) and (val != val)):  # check NaN
                    vals.append(None)
                else:
                    vals.append(float(val))
            except Exception:
                vals.append(None)
        out[key] = vals
    return out


def _clean_info(info: dict) -> dict:
    if not isinstance(info, dict):
        return {}
    out = {}
    for k, v in info.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = str(v)
    return out


def _annual_frames(symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch and cache annual balance sheet, financials, cash flow, and info from yfinance.
    Returns structured dictionary with lists of values ordered from most recent to oldest fiscal year.
    """
    clean_sym = str(symbol or "").strip().upper()
    if not clean_sym:
        return {}

    cache = _load_cache()
    entry = cache.get(clean_sym, {})
    if not force_refresh and _is_fresh(entry.get("updatedAt")):
        return entry.get("data", {})

    logger.info("Fetching yfinance annual frames for %s", clean_sym)
    try:
        t = yf.Ticker(clean_sym)
        bs_df = t.balance_sheet
        fin_df = t.financials
        cf_df = t.cashflow
        info = _clean_info(t.info or {})

        # Extract fiscal year ends from column names (usually timestamps)
        fy_ends = []
        if bs_df is not None and not getattr(bs_df, "empty", True):
            fy_ends = [str(col)[:10] for col in bs_df.columns]
        elif fin_df is not None and not getattr(fin_df, "empty", True):
            fy_ends = [str(col)[:10] for col in fin_df.columns]
        elif cf_df is not None and not getattr(cf_df, "empty", True):
            fy_ends = [str(col)[:10] for col in cf_df.columns]

        data = {
            "symbol": clean_sym,
            "balance_sheet": _df_to_dict(bs_df),
            "financials": _df_to_dict(fin_df),
            "cashflow": _df_to_dict(cf_df),
            "info": info,
            "fiscal_year_ends": fy_ends,
            "fetched_at": _now().isoformat()
        }

        cache[clean_sym] = {
            "updatedAt": _now().isoformat(),
            "data": data
        }
        _save_cache(cache)
        return data
    except Exception as exc:
        logger.error("Error fetching annual frames for %s: %s", clean_sym, exc)
        return cache.get(clean_sym, {}).get("data", {})


def _val(df_dict: Dict[str, List[Optional[float]]], aliases: List[str], year_idx: int = 0) -> Optional[float]:
    """
    Case-insensitive row lookup in a statement dictionary.
    Tries each alias in order until one resolves to a non-None float at year_idx.
    """
    if not df_dict or not aliases or not isinstance(df_dict, dict):
        return None

    lower_map = {k.lower().strip(): v for k, v in df_dict.items()}

    for alias in aliases:
        clean_alias = str(alias).lower().strip()
        if clean_alias in lower_map:
            vals = lower_map[clean_alias]
            if isinstance(vals, list) and 0 <= year_idx < len(vals):
                val = vals[year_idx]
                if val is not None:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
    return None


def _to_crores(raw: Optional[float]) -> Optional[float]:
    """Convert raw INR amount to Crores (divided by 10^7). Returns None if raw is None."""
    if raw is None:
        return None
    try:
        return float(raw) / 1e7
    except (ValueError, TypeError):
        return None


def _safe_divide(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Safe division returning None on zero/None denominator or None numerator."""
    if a is None or b is None:
        return None
    try:
        bf = float(b)
        if bf == 0.0:
            return None
        return float(a) / bf
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def _is_holding_company(info: dict, financials: dict, balance_sheet: dict) -> bool:
    """
    Detect holding companies via ratio gates (Section 1.5):
    OtherIncome / TotalIncome > 70% AND Investments / TotalAssets > 50%, or Investments > 70% of Total Assets.
    """
    try:
        other_inc = _val(financials, fc.OTHER_INCOME_ALIASES, 0) or 0.0
        tot_rev = _val(financials, fc.REVENUE_ALIASES, 0) or 0.0
        tot_inc = tot_rev + other_inc

        inv_aliases = [
            "Investments And Advances", "Long Term Equity Investment", "Available For Sale Securities",
            "Investmentin Financial Assets", "Financial Assets Designatedas Fair Value Through Profitor Loss Total",
            "Financial Assets", "Investments", "Total Investments", "Short Term Investments",
            "Long Term Investments", "Other Non Current Assets"
        ]
        inv = _val(balance_sheet, inv_aliases, 0) or 0.0
        tot_assets = _val(balance_sheet, fc.TOTAL_ASSETS_ALIASES, 0) or 0.0

        if tot_assets <= 0:
            return False

        inv_ratio = inv / tot_assets
        inc_ratio = 0.0
        if tot_inc > 0:
            inc_ratio = other_inc / tot_inc
        elif other_inc > 0 and tot_rev <= 0:
            inc_ratio = 1.0

        if inc_ratio > 0.70 and inv_ratio > 0.50:
            return True

        if inv_ratio > 0.70:
            return True

        ind = str(info.get("industry", "")).lower()
        sec = str(info.get("sector", "")).lower()
        if any(k in ind or k in sec for k in ["holding", "conglomerate", "asset management"]):
            if inv_ratio > 0.50:
                return True
        return False
    except Exception:
        return False


def _is_bfsi(sector_bucket: str) -> bool:
    """Check if the sector bucket is BFSI."""
    return str(sector_bucket or "").strip().upper() == "BFSI"


def get_sector_bucket(symbol: str, frames: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Priority-ordered sector classifier (Section 4.1).
    Evaluated against holding company gate, raw Yahoo sector, and industry string.
    Returns dict with 'bucket', 'confidence', 'raw_sector', 'raw_industry'.
    """
    import sector_map
    clean_sym = str(symbol or "").strip().upper()
    if not frames:
        frames = _annual_frames(clean_sym)

    info = frames.get("info", {})
    financials = frames.get("financials", {})
    balance_sheet = frames.get("balance_sheet", {})

    raw_sec_map = sector_map.get_sector_map([clean_sym])
    raw_sec = str(raw_sec_map.get(clean_sym) or info.get("sector") or "").strip()
    raw_ind = str(info.get("industry") or "").strip()

    sec_lower = raw_sec.lower()
    ind_lower = raw_ind.lower()

    if _is_holding_company(info, financials, balance_sheet):
        return {"bucket": "HOLDING_COMPANY", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    bfsi_keywords = ["bank", "insurance", "asset management", "financial - credit services", "financial - capital markets", "shadow banks", "mortgage", "credit"]
    if sec_lower == "financial services" and any(k in ind_lower for k in bfsi_keywords):
        return {"bucket": "BFSI", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}
    if "bank" in ind_lower or "insurance" in ind_lower:
        return {"bucket": "BFSI", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    if "telecom" in ind_lower:
        return {"bucket": "TELECOM", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    if "airlines" in ind_lower or "airline" in ind_lower:
        return {"bucket": "AIRLINES", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    if sec_lower == "real estate" or "real estate" in ind_lower:
        return {"bucket": "REAL_ESTATE_CONSTRUCTION", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    epc_keywords = ["engineering & construction", "aerospace & defense", "specialty industrial machinery", "conglomerates", "infrastructure", "construction", "heavy construction"]
    if any(k in ind_lower for k in epc_keywords):
        return {"bucket": "EPC_CAPITAL_GOODS_DEFENSE_INFRA", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    pharma_keywords = ["drug manufacturers", "pharmaceutical", "biotechnology", "chemicals", "health"]
    if any(k in ind_lower for k in pharma_keywords):
        return {"bucket": "PHARMA_API_CDMO_CHEMICALS", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    it_keywords = ["information technology services", "software", "it services", "computer hardware"]
    if sec_lower == "technology" or any(k in ind_lower for k in it_keywords):
        return {"bucket": "IT_SOFTWARE_SERVICES", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    fmcg_keywords = ["consumer defensive", "household", "beverages", "food", "tobacco", "personal services"]
    if sec_lower == "consumer defensive" or any(k in ind_lower for k in fmcg_keywords):
        return {"bucket": "FMCG_CONSUMER_STAPLES", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    comm_keywords = ["metals", "mining", "steel", "oil", "gas", "aluminum", "copper", "coal"]
    if sec_lower in ["energy", "basic materials"] or any(k in ind_lower for k in comm_keywords):
        return {"bucket": "COMMODITIES_METALS_OG_MINING", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    if sec_lower == "consumer cyclical" and "auto" in ind_lower:
        return {"bucket": "AUTO_MANUFACTURING", "confidence": "high", "raw_sector": raw_sec, "raw_industry": raw_ind}

    renew_keywords = ["renewable", "utilities—renewable", "solar", "wind", "green power"]
    if any(k in ind_lower for k in renew_keywords):
        return {"bucket": "RENEWABLE_POWER_INFRA_80IA", "confidence": "heuristic", "raw_sector": raw_sec, "raw_industry": raw_ind}

    return {"bucket": "GENERAL_OTHER", "confidence": "default", "raw_sector": raw_sec, "raw_industry": raw_ind}


def _capital_raise_years(shares_series: List[Optional[float]], fiscal_years: Optional[List[str]] = None) -> List[int]:
    """
    Detect years with significant share count dilution (>5% YoY increase).
    Returns list of indices (0-based from most recent year) where a capital raise occurred.
    """
    if not shares_series or len(shares_series) < 2:
        return []
    raised_indices = []
    for idx in range(len(shares_series) - 1):
        curr = shares_series[idx]
        prev = shares_series[idx + 1]
        if curr is not None and prev is not None and prev > 0:
            if (curr / prev) > 1.05:
                raised_indices.append(idx)
    return raised_indices


def _ind_as_116_transition_in_range(fiscal_year_ends: List[str]) -> bool:
    """
    Check if the analyzed fiscal year range includes the Ind AS 116 transition window
    (FY ends between Apr 2019 and Mar 2021 inclusive).
    """
    if not fiscal_year_ends:
        return False
    for fy in fiscal_year_ends:
        try:
            dt = str(fy)[:10]
            if "2019-04-01" <= dt <= "2021-03-31":
                return True
        except Exception:
            pass
    return False


def _pillar_income_statement(frames: Dict[str, Any], sector_bucket: str = "GENERAL_OTHER") -> Dict[str, Any]:
    """Pillar 1 calculator — Income Statement (Section 2.1)."""
    fin = frames.get("financials", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "reason": "No financial statement data available"}

    rev_list = [_to_crores(_val(fin, fc.REVENUE_ALIASES, i)) for i in range(num_yrs)]
    cogs_list = [_to_crores(_val(fin, fc.COGS_ALIASES, i)) for i in range(num_yrs)]
    gp_list = []
    for i in range(num_yrs):
        gp = _to_crores(_val(fin, fc.GROSS_PROFIT_ALIASES, i))
        if gp is None and rev_list[i] is not None and cogs_list[i] is not None:
            gp = rev_list[i] - cogs_list[i]
        gp_list.append(gp)

    ebit_list = [_to_crores(_val(fin, fc.OPERATING_INCOME_ALIASES, i)) for i in range(num_yrs)]
    ebitda_list = [_to_crores(_val(fin, fc.EBITDA_ALIASES, i)) for i in range(num_yrs)]
    for i in range(num_yrs):
        if ebitda_list[i] is None and ebit_list[i] is not None:
            dep = _to_crores(_val(fin, fc.DEPRECIATION_ALIASES, i)) or 0.0
            ebitda_list[i] = ebit_list[i] + dep

    pbt_list = [_to_crores(_val(fin, fc.PRETAX_INCOME_ALIASES, i)) for i in range(num_yrs)]
    tax_list = [_to_crores(_val(fin, fc.TAX_PROVISION_ALIASES, i)) for i in range(num_yrs)]
    net_list = [_to_crores(_val(fin, fc.NET_INCOME_ALIASES, i)) for i in range(num_yrs)]
    int_list = [_to_crores(_val(fin, fc.INTEREST_EXPENSE_ALIASES, i)) for i in range(num_yrs)]
    other_list = [_to_crores(_val(fin, fc.OTHER_INCOME_ALIASES, i)) for i in range(num_yrs)]
    sga_list = [_to_crores(_val(fin, ["Selling General And Administration", "SGA Expense", "Operating Expense", "Other Operating Expenses"], i)) for i in range(num_yrs)]
    eps_list = [_val(fin, ["Basic EPS", "Diluted EPS", "Basic Average Shares", "Diluted Average Shares"], i) for i in range(num_yrs)]

    rev_yoy = []
    for i in range(num_yrs):
        if i + 1 < num_yrs and rev_list[i] and rev_list[i+1] and rev_list[i+1] > 0:
            rev_yoy.append(round((rev_list[i] / rev_list[i+1] - 1.0) * 100, 2))
        else:
            rev_yoy.append(None)

    def _calc_cagr(val_list, n):
        if len(val_list) > n and val_list[0] and val_list[n] and val_list[n] > 0 and val_list[0] > 0:
            return round(((val_list[0] / val_list[n]) ** (1.0 / n) - 1.0) * 100, 2)
        return None

    rev_3y_cagr = _calc_cagr(rev_list, 3)
    rev_5y_cagr = _calc_cagr(rev_list, 4) if len(rev_list) >= 5 else None

    gp_margin = [round(_safe_divide(gp_list[i], rev_list[i]) * 100, 2) if gp_list[i] and rev_list[i] else None for i in range(num_yrs)]
    op_margin = [round(_safe_divide(ebit_list[i], rev_list[i]) * 100, 2) if ebit_list[i] and rev_list[i] else None for i in range(num_yrs)]
    ebitda_margin = [round(_safe_divide(ebitda_list[i], rev_list[i]) * 100, 2) if ebitda_list[i] and rev_list[i] else None for i in range(num_yrs)]
    net_margin = [round(_safe_divide(net_list[i], rev_list[i]) * 100, 2) if net_list[i] and rev_list[i] else None for i in range(num_yrs)]
    cogs_pct = [round(_safe_divide(cogs_list[i], rev_list[i]) * 100, 2) if cogs_list[i] and rev_list[i] else None for i in range(num_yrs)]
    sga_pct = [round(_safe_divide(sga_list[i], rev_list[i]) * 100, 2) if sga_list[i] and rev_list[i] else None for i in range(num_yrs)]
    int_pct_ebit = [round(_safe_divide(int_list[i], ebit_list[i]) * 100, 2) if int_list[i] and ebit_list[i] else None for i in range(num_yrs)]
    other_pct_pbt = [round(_safe_divide(other_list[i], pbt_list[i]) * 100, 2) if other_list[i] and pbt_list[i] else None for i in range(num_yrs)]

    tot_tax_3y = sum(x for x in tax_list[:3] if x is not None)
    tot_pbt_3y = sum(x for x in pbt_list[:3] if x is not None)
    etr_3y = round((tot_tax_3y / tot_pbt_3y) * 100, 2) if tot_pbt_3y > 0 else None

    eps_3y_cagr = _calc_cagr(eps_list, 3)
    eps_5y_cagr = _calc_cagr(eps_list, 4) if len(eps_list) >= 5 else None

    eps_rev_div = None
    if eps_3y_cagr is not None and rev_3y_cagr is not None and rev_3y_cagr != 0:
        eps_rev_div = round(eps_3y_cagr / rev_3y_cagr, 2)

    return {
        "available": True,
        "totalRevenue": rev_list,
        "revenueYoyGrowthPct": rev_yoy,
        "revenue3yCagr": rev_3y_cagr,
        "revenue5yCagr": rev_5y_cagr,
        "cogsPctOfRevenue": cogs_pct,
        "grossProfit": gp_list,
        "grossMarginPct": gp_margin,
        "employeeAndSgaPctRev": sga_pct,
        "ebit": ebit_list,
        "operatingMarginPct": op_margin,
        "ebitda": ebitda_list,
        "ebitdaMarginPct": ebitda_margin,
        "indAS116ComparabilityFlag": _ind_as_116_transition_in_range(fy_ends),
        "interestExpPctOfEbitReported": int_pct_ebit,
        "interestBurdenExLease": int_pct_ebit,
        "effectiveTaxRate3yAvg": etr_3y,
        "otherIncomePctOfPbt": other_pct_pbt,
        "basicEps": eps_list,
        "eps3yCagr": eps_3y_cagr,
        "eps5yCagr": eps_5y_cagr,
        "epsVsRevCagrDivergence": eps_rev_div,
        "marginCascade": {
            "gross": gp_margin[0] if gp_margin else None,
            "operating": op_margin[0] if op_margin else None,
            "net": net_margin[0] if net_margin else None
        }
    }


def _pillar_balance_sheet(frames: Dict[str, Any], sector_bucket: str = "GENERAL_OTHER") -> Dict[str, Any]:
    """Pillar 2 calculator — Balance Sheet (Section 2.2)."""
    bs = frames.get("balance_sheet", {})
    fin = frames.get("financials", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "reason": "No balance sheet data available"}

    rev_list = [_to_crores(_val(fin, fc.REVENUE_ALIASES, i)) for i in range(num_yrs)]
    cogs_list = [_to_crores(_val(fin, fc.COGS_ALIASES, i)) for i in range(num_yrs)]
    ebitda_list = [_to_crores(_val(fin, fc.EBITDA_ALIASES, i)) for i in range(num_yrs)]
    for i in range(num_yrs):
        if ebitda_list[i] is None:
            ebit = _to_crores(_val(fin, fc.OPERATING_INCOME_ALIASES, i))
            dep = _to_crores(_val(fin, fc.DEPRECIATION_ALIASES, i)) or 0.0
            if ebit is not None:
                ebitda_list[i] = ebit + dep

    tot_assets = [_to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    curr_assets = [_to_crores(_val(bs, fc.CURRENT_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    non_curr_assets = [_to_crores(_val(bs, fc.NON_CURRENT_ASSETS_ALIASES, i)) for i in range(num_yrs)]

    curr_pct = [round(_safe_divide(curr_assets[i], tot_assets[i]) * 100, 2) if curr_assets[i] and tot_assets[i] else None for i in range(num_yrs)]
    non_curr_pct = [round(_safe_divide(non_curr_assets[i], tot_assets[i]) * 100, 2) if non_curr_assets[i] and tot_assets[i] else None for i in range(num_yrs)]

    cash_list = [_to_crores(_val(bs, fc.CASH_EQUIVALENTS_ALIASES, i)) for i in range(num_yrs)]
    cash_pct = [round(_safe_divide(cash_list[i], tot_assets[i]) * 100, 2) if cash_list[i] and tot_assets[i] else None for i in range(num_yrs)]

    recv_list = [_to_crores(_val(bs, fc.RECEIVABLES_ALIASES, i)) for i in range(num_yrs)]
    dso_list = [round(_safe_divide(recv_list[i] * 365.0, rev_list[i]), 1) if recv_list[i] is not None and rev_list[i] and rev_list[i] > 0 else None for i in range(num_yrs)]

    inv_list = [_to_crores(_val(bs, fc.INVENTORY_ALIASES, i)) for i in range(num_yrs)]
    dio_list = [round(_safe_divide(inv_list[i] * 365.0, cogs_list[i]), 1) if inv_list[i] is not None and cogs_list[i] and cogs_list[i] > 0 else None for i in range(num_yrs)]

    net_ppe = [_to_crores(_val(bs, fc.NET_PPE_ALIASES, i)) for i in range(num_yrs)]
    fat_list = [round(_safe_divide(rev_list[i], net_ppe[i]), 2) if rev_list[i] and net_ppe[i] and net_ppe[i] > 0 else None for i in range(num_yrs)]

    intangibles = [_to_crores(_val(bs, fc.INTANGIBLES_ALIASES, i)) for i in range(num_yrs)]
    int_pct = [round(_safe_divide(intangibles[i], tot_assets[i]) * 100, 2) if intangibles[i] and tot_assets[i] else None for i in range(num_yrs)]

    cwip_list = [_to_crores(_val(bs, fc.CWIP_ALIASES, i)) for i in range(num_yrs)]
    cwip_pct = [round(_safe_divide(cwip_list[i], tot_assets[i]) * 100, 2) if cwip_list[i] and tot_assets[i] else None for i in range(num_yrs)]

    stalled_project = False
    if num_yrs >= 2 and cwip_list[0] is not None and cwip_list[1] is not None and cwip_pct[0] is not None and cwip_pct[0] > 5.0:
        if abs(cwip_list[0] - cwip_list[1]) < (0.02 * cwip_list[0]):
            stalled_project = True

    fin_debt = []
    lease_liab = []
    tot_debt_ref = []
    for i in range(num_yrs):
        lt = _to_crores(_val(bs, ["Long Term Debt", "Non Current Borrowings", "Long Term Borrowings"], i)) or 0.0
        st = _to_crores(_val(bs, ["Current Debt", "Short Term Debt", "Short Term Borrowings", "Current Borrowings"], i)) or 0.0
        fd = lt + st
        if fd == 0.0:
            fd_val = _to_crores(_val(bs, ["Financial Debt", "Total Borrowings"], i))
            if fd_val is not None:
                fd = fd_val
        fin_debt.append(round(fd, 2))

        ll = _to_crores(_val(bs, fc.LEASE_LIABILITIES_ALIASES, i)) or 0.0
        lease_liab.append(round(ll, 2))
        tot_debt_ref.append(round(fd + ll, 2))

    equity_list = [_to_crores(_val(bs, fc.EQUITY_ALIASES, i)) for i in range(num_yrs)]
    de_primary = [round(_safe_divide(fin_debt[i], equity_list[i]), 2) if equity_list[i] and equity_list[i] > 0 else None for i in range(num_yrs)]
    de_secondary = [round(_safe_divide(tot_debt_ref[i], equity_list[i]), 2) if equity_list[i] and equity_list[i] > 0 else None for i in range(num_yrs)]

    nde_reported = [round(_safe_divide(tot_debt_ref[i] - (cash_list[i] or 0.0), ebitda_list[i]), 2) if ebitda_list[i] and ebitda_list[i] > 0 else None for i in range(num_yrs)]
    nde_ex_lease = [round(_safe_divide(fin_debt[i] - (cash_list[i] or 0.0), ebitda_list[i]), 2) if ebitda_list[i] and ebitda_list[i] > 0 else None for i in range(num_yrs)]

    pay_list = [_to_crores(_val(bs, fc.TRADE_PAYABLES_ALIASES, i)) for i in range(num_yrs)]
    dpo_list = [round(_safe_divide(pay_list[i] * 365.0, cogs_list[i]), 1) if pay_list[i] is not None and cogs_list[i] and cogs_list[i] > 0 else None for i in range(num_yrs)]

    curr_liab = [_to_crores(_val(bs, fc.CURRENT_LIABILITIES_ALIASES, i)) for i in range(num_yrs)]
    nwc_list = [round(curr_assets[i] - curr_liab[i], 2) if curr_assets[i] is not None and curr_liab[i] is not None else None for i in range(num_yrs)]
    nwc_pct_rev = [round(_safe_divide(nwc_list[i], rev_list[i]) * 100, 2) if nwc_list[i] is not None and rev_list[i] and rev_list[i] > 0 else None for i in range(num_yrs)]

    ccc_list = []
    for i in range(num_yrs):
        if dso_list[i] is not None and dio_list[i] is not None and dpo_list[i] is not None:
            ccc_list.append(round(dso_list[i] + dio_list[i] - dpo_list[i], 1))
        else:
            ccc_list.append(None)

    ccc_suppressed = (sector_bucket in ["REAL_ESTATE_CONSTRUCTION", "EPC_CAPITAL_GOODS_DEFENSE_INFRA"])

    shares_list = [_val(bs, ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"], i) or _val(fin, ["Basic Average Shares", "Diluted Average Shares"], i) for i in range(num_yrs)]
    bvps_list = [round(_safe_divide(equity_list[i] * 1e7, shares_list[i]), 2) if equity_list[i] and shares_list[i] and shares_list[i] > 0 else None for i in range(num_yrs)]
    tbvps_list = [round(_safe_divide((equity_list[i] - (intangibles[i] or 0.0)) * 1e7, shares_list[i]), 2) if equity_list[i] and shares_list[i] and shares_list[i] > 0 else None for i in range(num_yrs)]

    ret_earn = [_to_crores(_val(bs, fc.RETAINED_EARNINGS_ALIASES, i)) for i in range(num_yrs)]
    re_growth = []
    for i in range(num_yrs):
        if i + 1 < num_yrs and ret_earn[i] is not None and ret_earn[i+1] is not None and ret_earn[i+1] != 0:
            re_growth.append(round(((ret_earn[i] - ret_earn[i+1]) / abs(ret_earn[i+1])) * 100, 2))
        else:
            re_growth.append(None)

    return {
        "available": True,
        "assets": {
            "totalAssets": tot_assets,
            "currentPct": curr_pct,
            "nonCurrentPct": non_curr_pct,
            "cash": cash_list,
            "cashPctOfAssets": cash_pct,
            "receivables": recv_list,
            "dso": dso_list,
            "inventory": inv_list,
            "dio": dio_list,
            "netPPE": net_ppe,
            "fixedAssetTurnover": fat_list,
            "intangiblesGoodwill": intangibles,
            "intangiblesPctOfAssets": int_pct,
            "cwip": cwip_list,
            "cwipPctOfAssets": cwip_pct,
            "stalledProjectFlag": stalled_project
        },
        "liabilities": {
            "financialDebt": fin_debt,
            "leaseLiabilities": lease_liab,
            "totalDebtReference": tot_debt_ref,
            "debtToEquity": {
                "financialPrimary": de_primary,
                "totalSecondary": de_secondary
            },
            "netDebtEbitda": {
                "reported": nde_reported,
                "exLease": nde_ex_lease
            },
            "tradePayables": pay_list,
            "dpo": dpo_list,
            "contingentLiabilities": {
                "available": False,
                "reason": "Annual Report notes disclosure — not in yfinance statement DataFrames. Phase 2 data source."
            }
        },
        "workingCapital": {
            "nwc": nwc_list,
            "nwcPctOfRevenue": nwc_pct_rev,
            "ccc": ccc_list,
            "cccPrimaryFlagSuppressed": ccc_suppressed,
            "indAS116ComparabilityFlag": _ind_as_116_transition_in_range(fy_ends)
        },
        "bookValue": {
            "bvps": bvps_list,
            "tbvps": tbvps_list,
            "retainedEarningsGrowthPct": re_growth
        }
    }


def _pillar_cash_flow(frames: Dict[str, Any], capital_raise_years: List[int] = None) -> Dict[str, Any]:
    """Pillar 3 calculator — Cash Flow (Section 2.3)."""
    cf = frames.get("cashflow", {})
    fin = frames.get("financials", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "reason": "No cash flow statement data available"}
    if capital_raise_years is None:
        capital_raise_years = []

    ocf_list = [_to_crores(_val(cf, fc.OPERATING_CASH_FLOW_ALIASES, i)) for i in range(num_yrs)]
    net_list = [_to_crores(_val(fin, fc.NET_INCOME_ALIASES, i)) for i in range(num_yrs)]
    ebitda_list = [_to_crores(_val(fin, fc.EBITDA_ALIASES, i)) for i in range(num_yrs)]
    for i in range(num_yrs):
        if ebitda_list[i] is None:
            ebit = _to_crores(_val(fin, fc.OPERATING_INCOME_ALIASES, i))
            dep = _to_crores(_val(fin, fc.DEPRECIATION_ALIASES, i)) or 0.0
            if ebit is not None:
                ebitda_list[i] = ebit + dep

    rev_list = [_to_crores(_val(fin, fc.REVENUE_ALIASES, i)) for i in range(num_yrs)]
    capex_list = [abs(_to_crores(_val(cf, fc.CAPEX_ALIASES, i)) or 0.0) for i in range(num_yrs)]
    dep_list = [_to_crores(_val(fin, fc.DEPRECIATION_ALIASES, i)) or _to_crores(_val(cf, ["Depreciation And Amortization", "Depreciation"], i)) for i in range(num_yrs)]

    fcf_list = []
    for i in range(num_yrs):
        fcf_val = _to_crores(_val(cf, fc.FREE_CASH_FLOW_ALIASES, i))
        if fcf_val is None and ocf_list[i] is not None:
            fcf_val = ocf_list[i] - capex_list[i]
        fcf_list.append(round(fcf_val, 2) if fcf_val is not None else None)

    fcf_margin = [round(_safe_divide(fcf_list[i], rev_list[i]) * 100, 2) if fcf_list[i] is not None and rev_list[i] and rev_list[i] > 0 else None for i in range(num_yrs)]

    ocf_to_ni = [round(_safe_divide(ocf_list[i], net_list[i]), 2) if ocf_list[i] is not None and net_list[i] and net_list[i] > 0 else None for i in range(num_yrs)]
    ocf_to_ni_class = []
    for val in ocf_to_ni:
        if val is None:
            ocf_to_ni_class.append(None)
        elif val >= 1.0:
            ocf_to_ni_class.append("Strong")
        elif val >= 0.8:
            ocf_to_ni_class.append("Adequate")
        else:
            ocf_to_ni_class.append("Weak/Red Flag")

    ocf_to_ebitda = [round(_safe_divide(ocf_list[i], ebitda_list[i]), 2) if ocf_list[i] is not None and ebitda_list[i] and ebitda_list[i] > 0 else None for i in range(num_yrs)]

    cum_ocf_flag = False
    valid_ocf = [x for x in ocf_list if x is not None]
    valid_net = [x for x in net_list if x is not None]
    if len(valid_ocf) >= 3 and len(valid_net) >= 3:
        if sum(valid_ocf) < sum(valid_net):
            cum_ocf_flag = True

    capex_pct_rev = [round(_safe_divide(capex_list[i], rev_list[i]) * 100, 2) if capex_list[i] and rev_list[i] and rev_list[i] > 0 else None for i in range(num_yrs)]
    capex_to_dep = [round(_safe_divide(capex_list[i], dep_list[i]), 2) if capex_list[i] and dep_list[i] and dep_list[i] > 0 else None for i in range(num_yrs)]
    growth_capex = [round(max(0.0, capex_list[i] - (dep_list[i] or 0.0)), 2) if capex_list[i] is not None else None for i in range(num_yrs)]
    def_tax = [_to_crores(_val(cf, fc.DEFERRED_TAX_ALIASES, i)) or _to_crores(_val(fin, fc.DEFERRED_TAX_ALIASES, i)) for i in range(num_yrs)]

    net_borrow = [_to_crores(_val(cf, ["Net Issuance Payments Of Debt", "Net Borrowings", "Issuance Of Debt", "Repayment Of Debt", "Net Debt Issuance"], i)) for i in range(num_yrs)]
    net_dilution = [_to_crores(_val(cf, ["Net Common Stock Issuance", "Issuance Of Capital Stock", "Repurchase Of Capital Stock", "Common Stock Issuance"], i)) for i in range(num_yrs)]
    div_list = [abs(_to_crores(_val(cf, fc.DIVIDENDS_PAID_ALIASES, i)) or 0.0) for i in range(num_yrs)]

    div_payout = [round(_safe_divide(div_list[i], net_list[i]) * 100, 2) if div_list[i] is not None and net_list[i] and net_list[i] > 0 else None for i in range(num_yrs)]
    fcf_div_cov = [round(_safe_divide(fcf_list[i], div_list[i]), 2) if fcf_list[i] is not None and div_list[i] and div_list[i] > 0 else None for i in range(num_yrs)]

    self_suff = []
    for i in range(num_yrs):
        if ocf_list[i] is not None:
            req = capex_list[i] + div_list[i]
            self_suff.append(ocf_list[i] >= req)
        else:
            self_suff.append(None)

    cap_raise_flags = [(i in capital_raise_years) for i in range(num_yrs)]

    return {
        "available": True,
        "ocfQuality": {
            "ocf": ocf_list,
            "ocfToNi": ocf_to_ni,
            "ocfToNiClassifications": ocf_to_ni_class,
            "ocfToEbitda": ocf_to_ebitda,
            "fcf": fcf_list,
            "fcfMarginPct": fcf_margin,
            "cumulative5yOcfVsNiFlag": cum_ocf_flag
        },
        "capex": {
            "capex": capex_list,
            "capexPctOfRevenue": capex_pct_rev,
            "capexToDepreciation": capex_to_dep,
            "growthCapexProxy": growth_capex,
            "deferredTaxPnlImpact": def_tax
        },
        "financing": {
            "netBorrowingTrend": net_borrow,
            "netDilutionOrBuybackTrend": net_dilution,
            "dividendPayoutRatio": div_payout,
            "fcfDividendCoverage": fcf_div_cov,
            "totalShareholderYieldPct": div_payout,
            "capitalRaiseYearFlags": cap_raise_flags
        },
        "cashSelfSufficiencyTest": self_suff
    }


def _wacc(frames: Dict[str, Any], fin_debt_series: List[Optional[float]] = None, equity_series: List[Optional[float]] = None) -> List[Optional[float]]:
    """CAPM WACC helper (Section 2.4 / Task 11)."""
    info = frames.get("info", {})
    fin = frames.get("financials", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return []

    beta = info.get("beta")
    try:
        beta_val = float(beta)
        beta_val = min(1.8, max(0.6, beta_val))
    except (ValueError, TypeError):
        beta_val = 1.0

    rf = 7.0
    erp = 6.0
    ke = round(rf + beta_val * erp, 2)

    wacc_list = []
    for i in range(num_yrs):
        fd = fin_debt_series[i] if fin_debt_series and i < len(fin_debt_series) else _to_crores(_val(frames.get("balance_sheet", {}), ["Long Term Debt", "Total Debt", "Short Long Term Debt"], i))
        eq = equity_series[i] if equity_series and i < len(equity_series) else _to_crores(_val(frames.get("balance_sheet", {}), fc.EQUITY_ALIASES, i))
        int_exp = _to_crores(_val(fin, fc.INTEREST_EXPENSE_ALIASES, i))

        if fd and fd > 0 and int_exp is not None:
            kd = (int_exp / fd) * 100.0
            kd = min(15.0, max(5.0, kd))
        else:
            kd = 8.5

        pbt = _to_crores(_val(fin, fc.PRETAX_INCOME_ALIASES, i))
        tax = _to_crores(_val(fin, fc.TAX_PROVISION_ALIASES, i))
        if pbt and pbt > 0 and tax is not None:
            t_val = tax / pbt
            t_val = min(0.35, max(0.15, t_val))
        else:
            t_val = 0.25

        if eq and eq > 0 and fd is not None and fd >= 0:
            tot = eq + fd
            we = eq / tot
            wd = fd / tot
        else:
            we, wd = 0.8, 0.2

        wacc_val = round(we * ke + wd * kd * (1.0 - t_val), 2)
        wacc_list.append(wacc_val)
    return wacc_list


def _pillar_profitability(frames: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
    """Pillar 4 calculator — Profitability & Returns (Section 2.4)."""
    is_holding_comp = kwargs.get("is_holding_comp", False)
    wacc_series = kwargs.get("wacc_series", None)
    if len(args) == 1:
        if isinstance(args[0], bool):
            is_holding_comp = args[0]
        elif isinstance(args[0], list):
            wacc_series = args[0]
    elif len(args) == 2:
        if isinstance(args[0], bool):
            is_holding_comp = args[0]
        if isinstance(args[1], (list, type(None))):
            wacc_series = args[1]
    elif len(args) >= 5:
        if isinstance(args[4], bool):
            is_holding_comp = args[4]
    if is_holding_comp:
        return {
            "available": False,
            "reason": "Suppressed by Holding Company gate (Section 1.5): investment holding structure returns are driven by NAV growth and dividend pass-through, not operating ROIC/ROE."
        }

    fin = frames.get("financials", {})
    bs = frames.get("balance_sheet", {})
    cf = frames.get("cashflow", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "reason": "No financial statement data available"}

    if not wacc_series:
        wacc_series = _wacc(frames)

    net_list = [_to_crores(_val(fin, fc.NET_INCOME_ALIASES, i)) for i in range(num_yrs)]
    ebit_list = [_to_crores(_val(fin, fc.OPERATING_INCOME_ALIASES, i)) for i in range(num_yrs)]
    rev_list = [_to_crores(_val(fin, fc.REVENUE_ALIASES, i)) for i in range(num_yrs)]
    pbt_list = [_to_crores(_val(fin, fc.PRETAX_INCOME_ALIASES, i)) for i in range(num_yrs)]
    tax_list = [_to_crores(_val(fin, fc.TAX_PROVISION_ALIASES, i)) for i in range(num_yrs)]

    tot_assets = [_to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    curr_liab = [_to_crores(_val(bs, fc.CURRENT_LIABILITIES_ALIASES, i)) for i in range(num_yrs)]
    equity_list = [_to_crores(_val(bs, fc.EQUITY_ALIASES, i)) for i in range(num_yrs)]
    cash_list = [_to_crores(_val(bs, fc.CASH_EQUIVALENTS_ALIASES, i)) for i in range(num_yrs)]

    fin_debt = []
    for i in range(num_yrs):
        lt = _to_crores(_val(bs, ["Long Term Debt", "Non Current Borrowings", "Long Term Borrowings"], i)) or 0.0
        st = _to_crores(_val(bs, ["Current Debt", "Short Term Debt", "Short Term Borrowings", "Current Borrowings"], i)) or 0.0
        fd = lt + st
        if fd == 0.0:
            fd_val = _to_crores(_val(bs, ["Financial Debt", "Total Borrowings"], i))
            if fd_val is not None:
                fd = fd_val
        fin_debt.append(fd)

    roe_list = [round(_safe_divide(net_list[i], equity_list[i]) * 100, 2) if net_list[i] is not None and equity_list[i] and equity_list[i] > 0 else None for i in range(num_yrs)]
    roa_list = [round(_safe_divide(net_list[i], tot_assets[i]) * 100, 2) if net_list[i] is not None and tot_assets[i] and tot_assets[i] > 0 else None for i in range(num_yrs)]

    roce_list = []
    for i in range(num_yrs):
        if ebit_list[i] is not None and tot_assets[i] and curr_liab[i] is not None:
            ce = tot_assets[i] - curr_liab[i]
            if ce > 0:
                roce_list.append(round((ebit_list[i] / ce) * 100, 2))
            else:
                roce_list.append(None)
        else:
            roce_list.append(None)

    roic_list = []
    nopat_list = []
    inv_cap_list = []
    for i in range(num_yrs):
        if ebit_list[i] is not None:
            t_val = 0.25
            if pbt_list[i] and pbt_list[i] > 0 and tax_list[i] is not None:
                t_val = min(0.35, max(0.15, tax_list[i] / pbt_list[i]))
            nopat = ebit_list[i] * (1.0 - t_val)
            nopat_list.append(nopat)
            ic = (fin_debt[i] or 0.0) + (equity_list[i] or 0.0) - (cash_list[i] or 0.0)
            inv_cap_list.append(ic)
            if ic > 0:
                roic_list.append(round((nopat / ic) * 100, 2))
            else:
                roic_list.append(None)
        else:
            nopat_list.append(None)
            inv_cap_list.append(None)
            roic_list.append(None)

    net_margin = [round(_safe_divide(net_list[i], rev_list[i]) * 100, 2) if net_list[i] and rev_list[i] else None for i in range(num_yrs)]
    asset_turnover = [round(_safe_divide(rev_list[i], tot_assets[i]), 2) if rev_list[i] and tot_assets[i] and tot_assets[i] > 0 else None for i in range(num_yrs)]
    equity_mult = [round(_safe_divide(tot_assets[i], equity_list[i]), 2) if tot_assets[i] and equity_list[i] and equity_list[i] > 0 else None for i in range(num_yrs)]

    dupont3_roe_check = []
    for i in range(num_yrs):
        if net_margin[i] is not None and asset_turnover[i] is not None and equity_mult[i] is not None:
            dupont3_roe_check.append(round(net_margin[i] * asset_turnover[i] * equity_mult[i], 2))
        else:
            dupont3_roe_check.append(None)

    tax_burden = [round(_safe_divide(net_list[i], pbt_list[i]), 2) if net_list[i] is not None and pbt_list[i] and pbt_list[i] != 0 else None for i in range(num_yrs)]
    int_burden = [round(_safe_divide(pbt_list[i], ebit_list[i]), 2) if pbt_list[i] is not None and ebit_list[i] and ebit_list[i] != 0 else None for i in range(num_yrs)]
    ebit_margin = [round(_safe_divide(ebit_list[i], rev_list[i]) * 100, 2) if ebit_list[i] and rev_list[i] else None for i in range(num_yrs)]

    dupont5_roe_check = []
    for i in range(num_yrs):
        if tax_burden[i] is not None and int_burden[i] is not None and ebit_margin[i] is not None and asset_turnover[i] is not None and equity_mult[i] is not None:
            dupont5_roe_check.append(round(tax_burden[i] * int_burden[i] * ebit_margin[i] * asset_turnover[i] * equity_mult[i], 2))
        else:
            dupont5_roe_check.append(None)

    inc_roe = []
    inc_roic = []
    for i in range(min(4, num_yrs - 1)):
        if net_list[i] is not None and net_list[i+1] is not None and equity_list[i] is not None and equity_list[i+1] is not None:
            delta_eq = equity_list[i] - equity_list[i+1]
            if abs(delta_eq) > 1.0:
                inc_roe.append(round(((net_list[i] - net_list[i+1]) / delta_eq) * 100, 2))
            else:
                inc_roe.append(roe_list[i])
        else:
            inc_roe.append(None)

        if nopat_list[i] is not None and nopat_list[i+1] is not None and inv_cap_list[i] is not None and inv_cap_list[i+1] is not None:
            delta_ic = inv_cap_list[i] - inv_cap_list[i+1]
            if abs(delta_ic) > 1.0:
                inc_roic.append(round(((nopat_list[i] - nopat_list[i+1]) / delta_ic) * 100, 2))
            else:
                inc_roic.append(roic_list[i])
        else:
            inc_roic.append(None)

    capex_list = [abs(_to_crores(_val(cf, fc.CAPEX_ALIASES, i)) or 0.0) for i in range(num_yrs)]
    dep_list = [_to_crores(_val(fin, fc.DEPRECIATION_ALIASES, i)) or _to_crores(_val(cf, ["Depreciation And Amortization", "Depreciation"], i)) for i in range(num_yrs)]

    reinv_rate = []
    for i in range(min(4, num_yrs)):
        if nopat_list[i] and nopat_list[i] > 0:
            net_capex = max(0.0, capex_list[i] - (dep_list[i] or 0.0))
            reinv = (net_capex / nopat_list[i]) * 100.0
            reinv_rate.append(round(reinv, 2))
        else:
            reinv_rate.append(None)

    curr_reinv = reinv_rate[0] if reinv_rate and reinv_rate[0] is not None else 30.0
    curr_roic = roic_list[0] if roic_list and roic_list[0] is not None else 10.0
    wacc_val = wacc_series[0] if wacc_series and wacc_series[0] is not None else 10.0

    if curr_reinv > 40.0 and curr_roic > wacc_val:
        quadrant = "Compounder"
        verdict = "High return capital reinvested aggressively — compounding intrinsic value."
    elif curr_reinv <= 40.0 and curr_roic > wacc_val:
        quadrant = "Cash Cow"
        verdict = "High return on capital but limited reinvestment opportunities — generating excess cash."
    elif curr_reinv > 40.0 and curr_roic <= wacc_val:
        quadrant = "Capital Destroyer"
        verdict = "Aggressively reinvesting capital at substandard returns — destroying value."
    else:
        quadrant = "Stagnant / Restructuring"
        verdict = "Low returns with minimal capital reinvestment — stagnant or restructuring."

    return {
        "available": True,
        "returns": {
            "roe": roe_list,
            "roa": roa_list,
            "roce": roce_list,
            "roic": roic_list,
            "wacc": wacc_series
        },
        "dupont3Factor": {
            "netMargin": net_margin,
            "assetTurnover": asset_turnover,
            "equityMultiplier": equity_mult,
            "roeCheck": dupont3_roe_check
        },
        "dupont5Factor": {
            "taxBurden": tax_burden,
            "interestBurdenExLease": int_burden,
            "ebitMargin": ebit_margin,
            "assetTurnover": asset_turnover,
            "equityMultiplier": equity_mult,
            "roeCheck": dupont5_roe_check
        },
        "incremental": {
            "incrementalRoe": inc_roe,
            "incrementalRoic": inc_roic
        },
        "reinvestmentRate": reinv_rate,
        "capitalAllocationQuadrant": {
            "reinvestmentRate": reinv_rate,
            "incrementalRoic": inc_roic,
            "currentQuadrant": quadrant,
            "verdictSentence": verdict
        }
    }


def _pillar_solvency(frames: Dict[str, Any], sector_bucket: str = "GENERAL_OTHER", is_bfsi: bool = False, wacc_series: List[Optional[float]] = None) -> Dict[str, Any]:
    """Pillar 5 calculator — Liquidity & Solvency (Section 2.5)."""
    if is_bfsi:
        return {
            "available": False,
            "reason": "Suppressed for BFSI (Section 1.5): industrial liquidity and solvency metrics do not apply to financial institutions."
        }

    bs = frames.get("balance_sheet", {})
    fin = frames.get("financials", {})
    cf = frames.get("cashflow", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "reason": "No financial statement data available"}

    if not wacc_series:
        wacc_series = _wacc(frames)

    curr_assets = [_to_crores(_val(bs, fc.CURRENT_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    curr_liab = [_to_crores(_val(bs, fc.CURRENT_LIABILITIES_ALIASES, i)) for i in range(num_yrs)]
    inv_list = [_to_crores(_val(bs, fc.INVENTORY_ALIASES, i)) for i in range(num_yrs)]
    cash_list = [_to_crores(_val(bs, fc.CASH_EQUIVALENTS_ALIASES, i)) for i in range(num_yrs)]

    curr_ratio = [round(_safe_divide(curr_assets[i], curr_liab[i]), 2) if curr_assets[i] is not None and curr_liab[i] and curr_liab[i] > 0 else None for i in range(num_yrs)]
    quick_ratio = [round(_safe_divide(curr_assets[i] - (inv_list[i] or 0.0), curr_liab[i]), 2) if curr_assets[i] is not None and curr_liab[i] and curr_liab[i] > 0 else None for i in range(num_yrs)]
    cash_ratio = [round(_safe_divide(cash_list[i], curr_liab[i]), 2) if cash_list[i] is not None and curr_liab[i] and curr_liab[i] > 0 else None for i in range(num_yrs)]

    cr_suppressed = (sector_bucket in ["REAL_ESTATE_CONSTRUCTION", "EPC_CAPITAL_GOODS_DEFENSE_INFRA"])

    cogs_list = [_to_crores(_val(fin, fc.COGS_ALIASES, i)) for i in range(num_yrs)]
    sga_list = [_to_crores(_val(fin, ["Selling General And Administration", "SGA Expense", "Operating Expense", "Other Operating Expenses"], i)) for i in range(num_yrs)]

    monthly_opex = []
    runway_months = []
    surv_flag = []
    for i in range(num_yrs):
        opex = (abs(cogs_list[i] or 0.0) + abs(sga_list[i] or 0.0)) / 12.0
        monthly_opex.append(round(opex, 2) if opex > 0 else None)
        if cash_list[i] is not None and opex > 0:
            rw = cash_list[i] / opex
            runway_months.append(round(rw, 1))
            surv_flag.append(rw >= 6.0)
        else:
            runway_months.append(None)
            surv_flag.append(None)

    ebit_list = [_to_crores(_val(fin, fc.OPERATING_INCOME_ALIASES, i)) for i in range(num_yrs)]
    ebitda_list = [_to_crores(_val(fin, fc.EBITDA_ALIASES, i)) for i in range(num_yrs)]
    for i in range(num_yrs):
        if ebitda_list[i] is None and ebit_list[i] is not None:
            dep = _to_crores(_val(fin, fc.DEPRECIATION_ALIASES, i)) or 0.0
            ebitda_list[i] = ebit_list[i] + dep

    fin_debt = []
    lease_liab = []
    for i in range(num_yrs):
        lt = _to_crores(_val(bs, ["Long Term Debt", "Non Current Borrowings", "Long Term Borrowings"], i)) or 0.0
        st = _to_crores(_val(bs, ["Current Debt", "Short Term Debt", "Short Term Borrowings", "Current Borrowings"], i)) or 0.0
        fd = lt + st
        if fd == 0.0:
            fd_val = _to_crores(_val(bs, ["Financial Debt", "Total Borrowings"], i))
            if fd_val is not None:
                fd = fd_val
        fin_debt.append(round(fd, 2))
        ll = _to_crores(_val(bs, fc.LEASE_LIABILITIES_ALIASES, i)) or 0.0
        lease_liab.append(round(ll, 2))

    nde_ex_lease = [round(_safe_divide(fin_debt[i] - (cash_list[i] or 0.0), ebitda_list[i]), 2) if ebitda_list[i] and ebitda_list[i] > 0 else None for i in range(num_yrs)]
    red_nde = (nde_ex_lease[0] > 3.5) if nde_ex_lease and nde_ex_lease[0] is not None else False

    int_exp = [_to_crores(_val(fin, fc.INTEREST_EXPENSE_ALIASES, i)) for i in range(num_yrs)]
    int_cov = [round(_safe_divide(ebit_list[i], int_exp[i]), 2) if ebit_list[i] is not None and int_exp[i] and int_exp[i] > 0 else None for i in range(num_yrs)]
    red_int_cov = (int_cov[0] < 2.0) if int_cov and int_cov[0] is not None else False

    ocf_list = [_to_crores(_val(cf, fc.OPERATING_CASH_FLOW_ALIASES, i)) for i in range(num_yrs)]
    repay_list = [abs(_to_crores(_val(cf, ["Repayment Of Debt", "Repayments Of Borrowings"], i)) or 0.0) for i in range(num_yrs)]

    dscr_list = []
    for i in range(num_yrs):
        if ocf_list[i] is not None and int_exp[i] is not None:
            denom = int_exp[i] + repay_list[i]
            if denom > 0:
                dscr_list.append(round(ocf_list[i] / denom, 2))
            else:
                dscr_list.append(None)
        else:
            dscr_list.append(None)
    red_dscr = (dscr_list[0] < 1.0) if dscr_list and dscr_list[0] is not None else False

    op_lease_pay = [abs(_to_crores(_val(cf, ["Operating Lease Payments", "Lease Payments"], i)) or (lease_liab[i] * 0.10 if lease_liab[i] else 0.0)) for i in range(num_yrs)]
    fcc_list = []
    for i in range(num_yrs):
        if ebit_list[i] is not None and int_exp[i] is not None:
            num = ebit_list[i] + op_lease_pay[i]
            den = int_exp[i] + op_lease_pay[i]
            if den > 0:
                fcc_list.append(round(num / den, 2))
            else:
                fcc_list.append(None)
        else:
            fcc_list.append(None)

    equity_list = [_to_crores(_val(bs, fc.EQUITY_ALIASES, i)) for i in range(num_yrs)]
    eq_pct = [round(_safe_divide(equity_list[i], (equity_list[i] + fin_debt[i])) * 100, 2) if equity_list[i] and (equity_list[i] + fin_debt[i]) > 0 else None for i in range(num_yrs)]
    fd_pct = [round(_safe_divide(fin_debt[i], (equity_list[i] + fin_debt[i])) * 100, 2) if equity_list[i] and (equity_list[i] + fin_debt[i]) > 0 else None for i in range(num_yrs)]

    is_tele_air = (sector_bucket in ["TELECOM_MEDIA", "AVIATION_AIRLINES"])
    fcf_list = []
    for i in range(num_yrs):
        fcf_val = _to_crores(_val(cf, fc.FREE_CASH_FLOW_ALIASES, i))
        if fcf_val is None and ocf_list[i] is not None:
            capex_val = abs(_to_crores(_val(cf, fc.CAPEX_ALIASES, i)) or 0.0)
            fcf_val = ocf_list[i] - capex_val
        fcf_list.append(round(fcf_val, 2) if fcf_val is not None else None)

    altman_rep = {
        "applicable": is_tele_air,
        "netDebtEbitda5yTrend": nde_ex_lease if is_tele_air else [],
        "fcfTrend": fcf_list if is_tele_air else [],
        "verdictSentence": "Sector override active: evaluated via 5Y rolling Net Debt/EBITDA and Free Cash Flow trajectory instead of static Altman Z." if is_tele_air else "Not applicable."
    }

    return {
        "available": True,
        "currentRatio": curr_ratio,
        "currentRatioPrimaryFlagSuppressed": cr_suppressed,
        "quickRatio": quick_ratio,
        "cashRatio": cash_ratio,
        "sixMonthSurvivalTest": {
            "monthlyOpexProxy": monthly_opex,
            "cashRunwayMonths": runway_months,
            "survivalFlag": surv_flag
        },
        "netDebtEbitdaExLease": nde_ex_lease,
        "redFlagNetDebtEbitda": red_nde,
        "interestCoverageExLease": int_cov,
        "redFlagInterestCoverage": red_int_cov,
        "dscr": dscr_list,
        "redFlagDscr": red_dscr,
        "fixedChargeCoverage": fcc_list,
        "capitalStructureMixExLease": {
            "equityPct": eq_pct,
            "financialDebtPct": fd_pct
        },
        "waccCrossReference": wacc_series,
        "telecomAirlinesAltmanReplacement": altman_rep,
        "thresholdsSummary": {
            "netDebtEbitdaMax": 3.5,
            "interestCoverageMin": 2.0,
            "dscrMin": 1.0
        }
    }


def _pillar_efficiency(frames: Dict[str, Any], sector_bucket: str = "GENERAL_OTHER", is_holding_comp: bool = False, is_bfsi: bool = False) -> Dict[str, Any]:
    """Pillar 6 calculator — Efficiency & Activity (Section 2.6)."""
    if is_holding_comp or is_bfsi:
        return {
            "available": False,
            "reason": "Suppressed for Holding Companies and BFSI (Section 1.5): turnover and cash conversion cycle metrics do not apply to financial or holding structures."
        }

    bs = frames.get("balance_sheet", {})
    fin = frames.get("financials", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "reason": "No financial statement data available"}

    rev_list = [_to_crores(_val(fin, fc.REVENUE_ALIASES, i)) for i in range(num_yrs)]
    cogs_list = [_to_crores(_val(fin, fc.COGS_ALIASES, i)) for i in range(num_yrs)]
    tot_assets = [_to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    net_ppe = [_to_crores(_val(bs, fc.NET_PPE_ALIASES, i)) for i in range(num_yrs)]

    curr_assets = [_to_crores(_val(bs, fc.CURRENT_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    curr_liab = [_to_crores(_val(bs, fc.CURRENT_LIABILITIES_ALIASES, i)) for i in range(num_yrs)]
    nwc_list = [round(curr_assets[i] - curr_liab[i], 2) if curr_assets[i] is not None and curr_liab[i] is not None else None for i in range(num_yrs)]

    inv_list = [_to_crores(_val(bs, fc.INVENTORY_ALIASES, i)) for i in range(num_yrs)]

    recv_list = []
    contract_merged = False
    for i in range(num_yrs):
        rec = _to_crores(_val(bs, fc.RECEIVABLES_ALIASES, i)) or 0.0
        ca = _to_crores(_val(bs, ["Contract Assets", "Unbilled Revenue", "Unbilled Receivables"], i))
        if ca is not None and ca > 0:
            contract_merged = True
            rec += ca
        recv_list.append(round(rec, 2) if rec > 0 or _val(bs, fc.RECEIVABLES_ALIASES, i) is not None else None)

    pay_list = [_to_crores(_val(bs, fc.TRADE_PAYABLES_ALIASES, i)) for i in range(num_yrs)]

    at_list = [round(_safe_divide(rev_list[i], tot_assets[i]), 2) if rev_list[i] and tot_assets[i] and tot_assets[i] > 0 else None for i in range(num_yrs)]
    fat_list = [round(_safe_divide(rev_list[i], net_ppe[i]), 2) if rev_list[i] and net_ppe[i] and net_ppe[i] > 0 else None for i in range(num_yrs)]
    wct_list = [round(_safe_divide(rev_list[i], nwc_list[i]), 2) if rev_list[i] and nwc_list[i] and abs(nwc_list[i]) > 0 else None for i in range(num_yrs)]

    inv_turn_values = [round(_safe_divide(cogs_list[i], inv_list[i]), 2) if cogs_list[i] and inv_list[i] and inv_list[i] > 0 else None for i in range(num_yrs)]
    inv_applicable = (sector_bucket != "IT_SOFTWARE_SERVICES" and any(x is not None and x > 0 for x in inv_list))

    recv_turn_values = [round(_safe_divide(rev_list[i], recv_list[i]), 2) if rev_list[i] and recv_list[i] and recv_list[i] > 0 else None for i in range(num_yrs)]
    pay_turn_values = [round(_safe_divide(cogs_list[i], pay_list[i]), 2) if cogs_list[i] and pay_list[i] and pay_list[i] > 0 else None for i in range(num_yrs)]

    dso_list = [round(_safe_divide(recv_list[i] * 365.0, rev_list[i]), 1) if recv_list[i] is not None and rev_list[i] and rev_list[i] > 0 else None for i in range(num_yrs)]
    dio_list = [round(_safe_divide(inv_list[i] * 365.0, cogs_list[i]), 1) if inv_list[i] is not None and cogs_list[i] and cogs_list[i] > 0 else None for i in range(num_yrs)]
    dpo_list = [round(_safe_divide(pay_list[i] * 365.0, cogs_list[i]), 1) if pay_list[i] is not None and cogs_list[i] and cogs_list[i] > 0 else None for i in range(num_yrs)]

    ccc_list = []
    for i in range(num_yrs):
        if dso_list[i] is not None and dio_list[i] is not None and dpo_list[i] is not None:
            ccc_list.append(round(dso_list[i] + dio_list[i] - dpo_list[i], 1))
        else:
            ccc_list.append(None)

    exp_flag_20pct = False
    if len(ccc_list) >= 2 and ccc_list[0] is not None and ccc_list[1] is not None:
        if ccc_list[1] > 0 and ((ccc_list[0] - ccc_list[1]) / ccc_list[1]) > 0.20:
            exp_flag_20pct = True
        elif ccc_list[1] <= 0 and (ccc_list[0] - ccc_list[1]) > 15.0:
            exp_flag_20pct = True

    ccc_suppressed = (sector_bucket in ["REAL_ESTATE_CONSTRUCTION", "EPC_CAPITAL_GOODS_DEFENSE_INFRA"])
    is_fmcg_retail = (sector_bucket in ["FMCG_CONSUMER_STAPLES", "RETAIL_CONSUMER_DISCRETIONARY"])
    neg_ccc_signal = [(ccc_list[i] is not None and ccc_list[i] < 0 and is_fmcg_retail) for i in range(num_yrs)]
    it_deemph = (sector_bucket == "IT_SOFTWARE_SERVICES")

    return {
        "available": True,
        "totalAssetTurnover": {
            "values": at_list,
            "itSectorDeemphasize": it_deemph
        },
        "fixedAssetTurnover": {
            "values": fat_list,
            "itSectorDeemphasize": it_deemph
        },
        "workingCapitalTurnover": wct_list,
        "inventoryTurnover": {
            "values": inv_turn_values,
            "applicable": inv_applicable
        },
        "receivablesTurnover": {
            "values": recv_turn_values,
            "contractAssetsMergedFlag": contract_merged
        },
        "payablesTurnover": pay_turn_values,
        "cccTrajectory": {
            "values": ccc_list,
            "expansionFlag20pct": exp_flag_20pct,
            "suppressedForRealEstateEpc": ccc_suppressed
        },
        "cccNegativeSignalFmcgRetail": neg_ccc_signal
    }


def _piotroski_f_score(frames: Dict[str, Any], p1: Dict[str, Any], p2: Dict[str, Any], p3: Dict[str, Any], p6: Dict[str, Any]) -> Dict[str, Any]:
    """Piotroski F-Score calculator (Section 2.7 / Task 14)."""
    bs = frames.get("balance_sheet", {})
    fin = frames.get("financials", {})
    cf = frames.get("cashflow", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs < 2:
        return {"available": False, "reason": "Requires at least 2 fiscal years of data for Piotroski YoY comparisons."}

    net_0 = _to_crores(_val(fin, fc.NET_INCOME_ALIASES, 0))
    net_1 = _to_crores(_val(fin, fc.NET_INCOME_ALIASES, 1))
    ta_0 = _to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, 0))
    ta_1 = _to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, 1))

    roa_0 = (net_0 / ta_0) if net_0 is not None and ta_0 and ta_0 > 0 else None
    roa_1 = (net_1 / ta_1) if net_1 is not None and ta_1 and ta_1 > 0 else None

    t1 = (roa_0 is not None and roa_0 > 0)

    ocf_0 = p3.get("ocfQuality", {}).get("ocf", [None])[0]
    t2 = (ocf_0 is not None and ocf_0 > 0)

    t3 = (roa_0 is not None and roa_1 is not None and roa_0 > roa_1)

    t4 = (ocf_0 is not None and net_0 is not None and ocf_0 > net_0)

    lt_0 = _to_crores(_val(bs, ["Long Term Debt", "Non Current Borrowings", "Long Term Borrowings"], 0)) or 0.0
    lt_1 = _to_crores(_val(bs, ["Long Term Debt", "Non Current Borrowings", "Long Term Borrowings"], 1)) or 0.0
    lev_0 = (lt_0 / ta_0) if ta_0 and ta_0 > 0 else 0.0
    lev_1 = (lt_1 / ta_1) if ta_1 and ta_1 > 0 else 0.0
    t5 = (lev_0 <= lev_1)

    ca_0 = _to_crores(_val(bs, fc.CURRENT_ASSETS_ALIASES, 0))
    ca_1 = _to_crores(_val(bs, fc.CURRENT_ASSETS_ALIASES, 1))
    cl_0 = _to_crores(_val(bs, fc.CURRENT_LIABILITIES_ALIASES, 0))
    cl_1 = _to_crores(_val(bs, fc.CURRENT_LIABILITIES_ALIASES, 1))
    cr_0 = (ca_0 / cl_0) if ca_0 is not None and cl_0 and cl_0 > 0 else None
    cr_1 = (ca_1 / cl_1) if ca_1 is not None and cl_1 and cl_1 > 0 else None
    t6 = (cr_0 is not None and cr_1 is not None and cr_0 > cr_1)

    sh_0 = _val(bs, ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"], 0) or _val(fin, ["Basic Average Shares", "Diluted Average Shares"], 0)
    sh_1 = _val(bs, ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"], 1) or _val(fin, ["Basic Average Shares", "Diluted Average Shares"], 1)
    t7 = True
    if sh_0 is not None and sh_1 is not None and sh_1 > 0:
        if sh_0 > sh_1 * 1.02:
            t7 = False

    gm_0 = p1.get("grossMarginPct", [None])[0]
    gm_1 = p1.get("grossMarginPct", [None, None])[1]
    t8 = (gm_0 is not None and gm_1 is not None and gm_0 > gm_1)

    at_0 = p6.get("totalAssetTurnover", {}).get("values", [None])[0]
    at_1 = p6.get("totalAssetTurnover", {}).get("values", [None, None])[1]
    t9 = (at_0 is not None and at_1 is not None and at_0 > at_1)

    tests = [t1, t2, t3, t4, t5, t6, t7, t8, t9]
    score = sum(1 for t in tests if t)

    if score >= 7:
        classification = "Strong"
    elif score >= 4:
        classification = "Moderate"
    else:
        classification = "Weak"

    return {
        "available": True,
        "score": score,
        "classification": classification,
        "tests": {
            "roaPositive": t1,
            "cfoPositive": t2,
            "deltaRoaPositive": t3,
            "cfoGreaterThanNi": t4,
            "deltaLeverageNegative": t5,
            "deltaCurrentRatioPositive": t6,
            "noNewShares": t7,
            "deltaGrossMarginPositive": t8,
            "deltaAssetTurnoverPositive": t9
        }
    }


def _beneish_m_score(frames: Dict[str, Any], p1: Dict[str, Any], p2: Dict[str, Any], p3: Dict[str, Any], p6: Dict[str, Any], is_bfsi: bool = False) -> Dict[str, Any]:
    """Beneish M-Score calculator with audit corrections (Section 2.8 / Task 15)."""
    if is_bfsi:
        return {
            "available": False,
            "reason": "Suppressed for BFSI (Section 1.5): accrual and asset quality manipulation models do not apply to banks or financial institutions."
        }

    bs = frames.get("balance_sheet", {})
    fin = frames.get("financials", {})
    cf = frames.get("cashflow", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "reason": "No financial statement data available"}

    rev_list = [_to_crores(_val(fin, fc.REVENUE_ALIASES, i)) for i in range(num_yrs)]
    rec_list = [_to_crores(_val(bs, fc.RECEIVABLES_ALIASES, i)) for i in range(num_yrs)]
    gp_list = [_to_crores(_val(fin, fc.GROSS_PROFIT_ALIASES, i)) for i in range(num_yrs)]
    net_list = [_to_crores(_val(fin, fc.NET_INCOME_ALIASES, i)) for i in range(num_yrs)]
    sga_list = [_to_crores(_val(fin, ["Selling General And Administration", "SGA Expense", "Operating Expense", "Other Operating Expenses"], i)) for i in range(num_yrs)]
    dep_list = [_to_crores(_val(fin, fc.DEPRECIATION_ALIASES, i)) or _to_crores(_val(cf, ["Depreciation And Amortization", "Depreciation"], i)) for i in range(num_yrs)]

    ta_list = [_to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    ca_list = [_to_crores(_val(bs, fc.CURRENT_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    ppe_list = [_to_crores(_val(bs, fc.NET_PPE_ALIASES, i)) for i in range(num_yrs)]
    cwip_list = [_to_crores(_val(bs, ["Capital Work In Progress", "Construction In Progress"], i)) or 0.0 for i in range(num_yrs)]

    ocf_list = [_to_crores(_val(cf, fc.OPERATING_CASH_FLOW_ALIASES, i)) for i in range(num_yrs)]

    debt_list = []
    for i in range(num_yrs):
        lt = _to_crores(_val(bs, ["Long Term Debt", "Non Current Borrowings", "Long Term Borrowings"], i)) or 0.0
        st = _to_crores(_val(bs, ["Current Debt", "Short Term Debt", "Short Term Borrowings", "Current Borrowings"], i)) or 0.0
        fd = lt + st
        if fd == 0.0:
            fd_val = _to_crores(_val(bs, ["Financial Debt", "Total Borrowings"], i))
            if fd_val is not None:
                fd = fd_val
        ll = _to_crores(_val(bs, fc.LEASE_LIABILITIES_ALIASES, i)) or 0.0
        debt_list.append(fd + ll)

    shares_list = [_to_crores(_val(bs, ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"], i)) or _to_crores(_val(fin, ["Basic Average Shares", "Diluted Average Shares"], i)) for i in range(num_yrs)]
    cap_raises = _capital_raise_years([sh or 0.0 for sh in shares_list])

    dsri_list, gmi_list, aqi_list, sgi_list = [], [], [], []
    depi_list, sgai_list, lvgi_list, tata_list = [], [], [], []
    m_score_list = []
    risk_band_list = []
    sgai_lvgi_supp_list = []
    depi_cwip_check_list = []
    corrob_flag_list = []

    for i in range(num_yrs):
        if i < num_yrs - 1 and ta_list[i] and ta_list[i] > 0 and ta_list[i+1] and ta_list[i+1] > 0:
            if rec_list[i] is not None and rev_list[i] and rev_list[i] > 0 and rec_list[i+1] is not None and rev_list[i+1] and rev_list[i+1] > 0:
                dsri = (rec_list[i] / rev_list[i]) / (rec_list[i+1] / rev_list[i+1])
            else:
                dsri = 1.0
            dsri_list.append(round(dsri, 2))

            if gp_list[i] is not None and rev_list[i] and rev_list[i] > 0 and gp_list[i+1] is not None and rev_list[i+1] and rev_list[i+1] > 0:
                gm_t = gp_list[i] / rev_list[i]
                gm_prev = gp_list[i+1] / rev_list[i+1]
                gmi = (gm_prev / gm_t) if gm_t > 0 else 1.0
            else:
                gmi = 1.0
            gmi_list.append(round(gmi, 2))

            if ca_list[i] is not None and ppe_list[i] is not None and ca_list[i+1] is not None and ppe_list[i+1] is not None:
                aq_t = 1.0 - ((ca_list[i] + ppe_list[i]) / ta_list[i])
                aq_prev = 1.0 - ((ca_list[i+1] + ppe_list[i+1]) / ta_list[i+1])
                aqi = (aq_t / aq_prev) if aq_prev != 0 else 1.0
            else:
                aqi = 1.0
            aqi_list.append(round(aqi, 2))

            if rev_list[i] and rev_list[i+1] and rev_list[i+1] > 0:
                sgi = rev_list[i] / rev_list[i+1]
            else:
                sgi = 1.0
            sgi_list.append(round(sgi, 2))

            if dep_list[i] is not None and ppe_list[i] is not None and dep_list[i+1] is not None and ppe_list[i+1] is not None:
                gross_t = ppe_list[i] + dep_list[i]
                gross_prev = ppe_list[i+1] + dep_list[i+1]
                dep_rate_t = (dep_list[i] / gross_t) if gross_t > 0 else 0.0
                dep_rate_prev = (dep_list[i+1] / gross_prev) if gross_prev > 0 else 0.0
                depi = (dep_rate_prev / dep_rate_t) if dep_rate_t > 0 else 1.0
            else:
                depi = 1.0
            depi_list.append(round(depi, 2))

            cwip_check = False
            if depi > 1.3 and cwip_list[i+1] > cwip_list[i]:
                cwip_check = True
            depi_cwip_check_list.append(cwip_check)

            if sga_list[i] is not None and rev_list[i] and rev_list[i] > 0 and sga_list[i+1] is not None and rev_list[i+1] and rev_list[i+1] > 0:
                sga_t = sga_list[i] / rev_list[i]
                sga_prev = sga_list[i+1] / rev_list[i+1]
                sgai = (sga_t / sga_prev) if sga_prev > 0 else 1.0
            else:
                sgai = 1.0
            sgai_list.append(round(sgai, 2))

            lev_t = debt_list[i] / ta_list[i]
            lev_prev = debt_list[i+1] / ta_list[i+1]
            lvgi = (lev_t / lev_prev) if lev_prev > 0 else 1.0
            lvgi_list.append(round(lvgi, 2))

            supp = (i in cap_raises or (i - 1) in cap_raises or (i + 1) in cap_raises)
            sgai_lvgi_supp_list.append(supp)

            gross_ta = ta_list[i] + (dep_list[i] or 0.0)
            if net_list[i] is not None and ocf_list[i] is not None and gross_ta > 0:
                tata = (net_list[i] - ocf_list[i]) / gross_ta
            else:
                tata = 0.0
            tata_list.append(round(tata, 4))

            m = -4.84 + 0.920 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi
            m_round = round(m, 2)
            m_score_list.append(m_round)

            if m_round > -1.78:
                risk_band = "High"
            elif m_round > -2.22:
                risk_band = "Moderate"
            else:
                risk_band = "Low/Clean"
            risk_band_list.append(risk_band)

            ocf_ni = (ocf_list[i] / net_list[i]) if net_list[i] and net_list[i] > 0 and ocf_list[i] is not None else 1.0
            corrob = (m_round > -1.78 and tata > 0.10 and ocf_ni < 0.8)
            corrob_flag_list.append(corrob)
        else:
            dsri_list.append(None)
            gmi_list.append(None)
            aqi_list.append(None)
            sgi_list.append(None)
            depi_list.append(None)
            sgai_list.append(None)
            lvgi_list.append(None)
            tata_list.append(None)
            m_score_list.append(None)
            risk_band_list.append(None)
            sgai_lvgi_supp_list.append(False)
            depi_cwip_check_list.append(False)
            corrob_flag_list.append(False)

    return {
        "available": True,
        "dsri": dsri_list,
        "gmi": gmi_list,
        "aqi": aqi_list,
        "sgi": sgi_list,
        "depi": depi_list,
        "sgai": sgai_list,
        "lvgi": lvgi_list,
        "tata": tata_list,
        "mScore": m_score_list,
        "riskBand": risk_band_list,
        "depiCwipCrossCheckApplied": depi_cwip_check_list,
        "sgaiLvgiSuppressedThisYear": sgai_lvgi_supp_list,
        "beneishCorroboratedFlag": corrob_flag_list,
        "corroboratingFlagCount": 0,
        "escalatedToRed": False
    }


def _altman_z_router(frames: Dict[str, Any], sector_bucket: str = "GENERAL_OTHER", is_bfsi: bool = False, p5: Dict[str, Any] = None) -> Dict[str, Any]:
    """Altman Z-Score priority-ordered sector router (Section 1.6 & 2.9 / Task 16)."""
    bs = frames.get("balance_sheet", {})
    fin = frames.get("financials", {})
    info = frames.get("info", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "model": None, "modelUsed": None, "reason": "No financial data"}

    eq_0 = _to_crores(_val(bs, fc.EQUITY_ALIASES, 0))
    if is_bfsi or sector_bucket == "BANKING_FINANCIAL_SERVICES":
        return {
            "available": False,
            "model": None,
            "modelUsed": None,
            "score": [None]*num_yrs,
            "zScore": [None]*num_yrs,
            "zone": ["Distress"]*num_yrs,
            "selectionReason": "Suppressed for BFSI (Section 1.6 rule 1): standard distress models do not apply.",
            "altmanModel": None,
            "altmanModelSelectionReason": "Suppressed for BFSI (Section 1.6 rule 1): standard distress models do not apply."
        }
    if sector_bucket in ["TELECOM_MEDIA", "AVIATION_AIRLINES"]:
        return {
            "available": True,
            "model": "ALTMAN_REPLACED_BY_ROLLING_FCF_AND_NET_DEBT",
            "modelUsed": "ALTMAN_REPLACED_BY_ROLLING_FCF_AND_NET_DEBT",
            "score": [None]*num_yrs,
            "zScore": [None]*num_yrs,
            "zone": ["Safe"]*num_yrs,
            "selectionReason": "Suppressed for Telecom/Airlines (Section 1.6 rule 1): replaced by 5Y rolling Net Debt/EBITDA and FCF.",
            "altmanModel": "ALTMAN_REPLACED_BY_ROLLING_FCF_AND_NET_DEBT",
            "altmanModelSelectionReason": "Suppressed for Telecom/Airlines (Section 1.6 rule 1): replaced by 5Y rolling Net Debt/EBITDA and FCF."
        }
    if eq_0 is not None and eq_0 <= 0:
        return {
            "available": False,
            "model": None,
            "modelUsed": None,
            "score": [None]*num_yrs,
            "zScore": [None]*num_yrs,
            "zone": ["Distress"]*num_yrs,
            "selectionReason": "Suppressed: negative book equity (Section 1.6 rule 1).",
            "altmanModel": None,
            "altmanModelSelectionReason": "Suppressed: negative book equity (Section 1.6 rule 1)."
        }

    model = None
    reason = ""

    if sector_bucket in ["IT_SOFTWARE_SERVICES", "FMCG_CONSUMER_STAPLES", "RETAIL_CONSUMER_DISCRETIONARY"]:
        model = "Z_DOUBLE_PRIME_NON_MFG"
        reason = "Non-manufacturing/service sector (Section 1.6 rule 2): uses Z''-Score without Asset Turnover term."
    elif sector_bucket == "PHARMA_API_CDMO_CHEMICALS":
        ta_0 = _to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, 0)) or 1.0
        ppe_0 = _to_crores(_val(bs, fc.NET_PPE_ALIASES, 0)) or 0.0
        if (ppe_0 / ta_0) > 0.40:
            model = "Z_PRIME_1983"
            reason = "Pharma/API asset-heavy sub-split (PPE/TA > 0.40): routed to Z'-Score (Section 1.6 rule 3)."
        else:
            model = "Z_DOUBLE_PRIME_NON_MFG"
            reason = "Pharma formulations/light sub-split (PPE/TA <= 0.40): routed to Z''-Score (Section 1.6 rule 3)."
    else:
        mcap = info.get("marketCap")
        if mcap is None or mcap < (5000 * 1e7):
            model = "Z_PRIME_1983"
            reason = "Thin/illiquid small-cap (mcap < 5000 Cr or stale > 30d): routed to Z'-Score (Section 1.6 rule 4)."
        elif sector_bucket in ["AUTO_MANUFACTURING", "COMMODITIES_METALS_OIL_GAS_MINING", "EPC_CAPITAL_GOODS_DEFENSE_INFRA"]:
            model = "Z_1968"
            reason = "Standard manufacturing sector with reliable market equity (Section 1.6 rule 5): routed to original Z-Score (1968)."
        else:
            model = "Z_PRIME_1983"
            reason = "default fallback — sector bucket unmapped"

    score_list = []
    zone_list = []
    mcap_crores = (info.get("marketCap") / 1e7) if info.get("marketCap") else None

    for i in range(num_yrs):
        ta = _to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, i))
        if not ta or ta <= 0:
            score_list.append(None)
            zone_list.append(None)
            continue

        ca = _to_crores(_val(bs, fc.CURRENT_ASSETS_ALIASES, i)) or 0.0
        cl = _to_crores(_val(bs, fc.CURRENT_LIABILITIES_ALIASES, i)) or 0.0
        re = _to_crores(_val(bs, ["Retained Earnings", "Retained Earnings Accumulated Deficit", "RetainedEarnings"], i))
        ebit = _to_crores(_val(fin, fc.OPERATING_INCOME_ALIASES, i)) or 0.0
        rev = _to_crores(_val(fin, fc.REVENUE_ALIASES, i)) or 0.0
        eq = _to_crores(_val(bs, fc.EQUITY_ALIASES, i)) or 0.0
        tl = _to_crores(_val(bs, ["Total Liabilities Net Minority Interest", "Total Liabilities Net Minority", "Total Liabilities"], i))
        if not tl or tl <= 0:
            tl = ta - eq
            if tl <= 0:
                tl = ta * 0.5

        x1 = (ca - cl) / ta
        if re is None:
            re = eq * 0.5
        x2 = re / ta
        x3 = ebit / ta
        x4_book = eq / tl
        if i == 0 and mcap_crores:
            x4_mcap = mcap_crores / tl
        else:
            x4_mcap = x4_book * 2.0
        x5 = rev / ta

        if model == "Z_1968":
            z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4_mcap + 1.0 * x5
            z_round = round(z, 2)
            zone = "Safe" if z_round > 2.99 else ("Grey" if z_round >= 1.81 else "Distress")
        elif model == "Z_PRIME_1983":
            z = 0.717 * x1 + 0.847 * x2 + 3.107 * x3 + 0.420 * x4_book + 0.998 * x5
            z_round = round(z, 2)
            zone = "Safe" if z_round > 2.90 else ("Grey" if z_round >= 1.23 else "Distress")
        else:
            z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4_book
            z_round = round(z, 2)
            zone = "Safe" if z_round > 2.60 else ("Grey" if z_round >= 1.10 else "Distress")

        score_list.append(z_round)
        zone_list.append(zone)

    return {
        "available": True,
        "model": model,
        "modelUsed": model,
        "score": score_list,
        "zScore": score_list,
        "zone": zone_list,
        "selectionReason": reason,
        "altmanModel": model,
        "altmanModelSelectionReason": reason
    }


def _sloan_accrual(frames: Dict[str, Any], p1: Dict[str, Any], p3: Dict[str, Any], is_bfsi: bool = False, is_holding_comp: bool = False) -> Dict[str, Any]:
    """Sloan Accrual Ratio calculator with growth-adjusted thresholds (Section 2.10 / Task 17)."""
    if is_bfsi or is_holding_comp:
        return {
            "available": False,
            "reason": "Suppressed for BFSI / Holding Companies (Section 1.5): accrual anomalies do not apply to financial or holding structures."
        }

    bs = frames.get("balance_sheet", {})
    fin = frames.get("financials", {})
    cf = frames.get("cashflow", {})
    fy_ends = frames.get("fiscal_year_ends", [])
    num_yrs = min(5, len(fy_ends))
    if num_yrs == 0:
        return {"available": False, "reason": "No financial statement data available"}

    rev_list = [_to_crores(_val(fin, fc.REVENUE_ALIASES, i)) for i in range(num_yrs)]
    net_list = [_to_crores(_val(fin, fc.NET_INCOME_ALIASES, i)) for i in range(num_yrs)]
    ta_list = [_to_crores(_val(bs, fc.TOTAL_ASSETS_ALIASES, i)) for i in range(num_yrs)]
    ocf_list = p3.get("ocfQuality", {}).get("ocf", [None]*num_yrs)
    icf_list = [_to_crores(_val(cf, ["Investing Cash Flow", "Total Cashflows From Investing Activities", "Cash Flow From Investing Activities", "Net Cash Used For Investing Activities"], i)) or 0.0 for i in range(num_yrs)]
    def_tax_list = [_to_crores(_val(fin, ["Deferred Income Tax", "Deferred Tax", "Change In Deferred Tax", "Provision For Deferred Income Tax"], i)) or _to_crores(_val(cf, ["Deferred Income Tax", "Deferred Tax", "Change In Deferred Tax"], i)) or 0.0 for i in range(num_yrs)]

    cagr = p1.get("revenue3yCagr")
    if cagr is None:
        if len(rev_list) >= 4 and rev_list[0] and rev_list[3] and rev_list[3] > 0:
            cagr = ((rev_list[0] / rev_list[3]) ** (1.0 / 3.0) - 1.0) * 100.0
        else:
            cagr = 0.0

    if cagr > 20.0:
        band = ">20%"
        mod_thresh = 15.0
        sev_thresh = 30.0
        growth_adj = True
    elif cagr >= 10.0:
        band = "10-20%"
        mod_thresh = 12.0
        sev_thresh = 27.0
        growth_adj = True
    else:
        band = "<10%"
        mod_thresh = 10.0
        sev_thresh = 25.0
        growth_adj = False

    accrual_ratio_list = []
    raw_sloan_list = []
    def_tax_adj_list = []
    flagged_list = []
    flag_level_list = []

    for i in range(num_yrs):
        ta = ta_list[i]
        if not ta or ta <= 0:
            accrual_ratio_list.append(None)
            raw_sloan_list.append(None)
            def_tax_adj_list.append(None)
            flagged_list.append(False)
            flag_level_list.append("Normal")
            continue

        if i < num_yrs - 1 and ta_list[i+1] and ta_list[i+1] > 0:
            avg_ta = (ta + ta_list[i+1]) / 2.0
        else:
            avg_ta = ta

        net = net_list[i]
        ocf = ocf_list[i] if i < len(ocf_list) else None
        icf = icf_list[i]
        def_tax = def_tax_list[i]

        if net is not None and ocf is not None and avg_ta > 0:
            ar = (net - ocf) / avg_ta
            ar_round = round(ar, 4)
            accrual_ratio_list.append(ar_round)

            raw_s = (net - ocf - icf) / avg_ta
            raw_sloan_list.append(round(raw_s, 4))

            dt_s = (net - def_tax - ocf - icf) / avg_ta
            dt_s_round = round(dt_s, 4)
            def_tax_adj_list.append(dt_s_round)

            pct_val = abs(ar_round) * 100.0
            if pct_val > sev_thresh:
                flagged_list.append(True)
                flag_level_list.append("Severe")
            elif pct_val > mod_thresh:
                flagged_list.append(True)
                flag_level_list.append("Moderate")
            else:
                flagged_list.append(False)
                flag_level_list.append("Normal")
        else:
            accrual_ratio_list.append(None)
            raw_sloan_list.append(None)
            def_tax_adj_list.append(None)
            flagged_list.append(False)
            flag_level_list.append("Normal")

    return {
        "available": True,
        "accrualRatio": accrual_ratio_list,
        "rawSloan": raw_sloan_list,
        "deferredTaxAdjustedSloan": def_tax_adj_list,
        "revenue3yCagrBand": band,
        "moderateThresholdPct": mod_thresh,
        "severeThresholdPct": sev_thresh,
        "growthAdjustedThresholdApplied": growth_adj,
        "flagged": flagged_list,
        "flagLevel": flag_level_list
    }


def _pillar_valuation(*args, **kwargs) -> Dict[str, Any]:
    """Pillar 8 calculator — Valuation (Section 2.8 / Task 19). Deliberately excluded from overallGrade."""
    info = kwargs.get("info", {})
    frames = kwargs.get("frames", {})
    sector_bucket = kwargs.get("sector_bucket", "GENERAL_OTHER")
    wacc_series = kwargs.get("wacc_series", None)

    for arg in args:
        if isinstance(arg, str):
            sector_bucket = arg
        elif isinstance(arg, dict):
            if "financials" in arg or "balance_sheet" in arg or "cashflow" in arg:
                frames = arg
            elif "currentPrice" in arg or "trailingPE" in arg or "marketCap" in arg:
                info = arg
        elif isinstance(arg, list):
            wacc_series = arg

    if not info and isinstance(frames, dict):
        info = frames.get("info", {})

    fin = frames.get("financials", {}) if isinstance(frames, dict) else {}
    bs = frames.get("balance_sheet", {}) if isinstance(frames, dict) else {}
    cf = frames.get("cashflow", {}) if isinstance(frames, dict) else {}

    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    mcap = info.get("marketCap")
    ev = info.get("enterpriseValue")
    shares = info.get("sharesOutstanding") or _val(bs, ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"], 0)

    # 1. Trailing P/E
    trailing_pe = info.get("trailingPE")
    eps_0 = _val(fin, ["Basic EPS", "Diluted EPS"], 0) or info.get("trailingEps")
    if trailing_pe is None and price is not None and eps_0 is not None and eps_0 > 0:
        trailing_pe = round(price / eps_0, 2)
    elif trailing_pe is not None:
        trailing_pe = round(trailing_pe, 2)

    # 2. Forward P/E
    forward_pe = info.get("forwardPE")
    if forward_pe is not None:
        forward_pe = round(forward_pe, 2)

    # 3. P/B
    pb = info.get("priceToBook")
    eq_0 = _val(bs, fc.EQUITY_ALIASES, 0)
    bvps_0 = eq_0 / shares if eq_0 and shares and shares > 0 else info.get("bookValue")
    if pb is None and price is not None and bvps_0 is not None and bvps_0 > 0:
        pb = round(price / bvps_0, 2)
    elif pb is not None:
        pb = round(pb, 2)

    # 4. Price to Tangible Book
    int_0 = _val(bs, fc.INTANGIBLES_ALIASES, 0) or 0.0
    tangible_eq_0 = (eq_0 - int_0) if eq_0 is not None else None
    tbvps_0 = tangible_eq_0 / shares if tangible_eq_0 is not None and shares and shares > 0 else None
    ptb = round(price / tbvps_0, 2) if price is not None and tbvps_0 is not None and tbvps_0 > 0 else None

    # 5. P/S
    ps = info.get("priceToSalesTrailing12Months")
    rev_0 = _val(fin, fc.REVENUE_ALIASES, 0)
    if ps is None and mcap is not None and rev_0 is not None and rev_0 > 0:
        ps = round(mcap / rev_0, 2)
    elif ps is not None:
        ps = round(ps, 2)

    # 6. EV / EBITDA
    ev_ebitda = info.get("enterpriseToEbitda")
    ebitda_0 = info.get("ebitda") or _val(fin, ["EBITDA", "Normalized EBITDA"], 0)
    if ev_ebitda is None and ev is not None and ebitda_0 is not None and ebitda_0 > 0:
        ev_ebitda = round(ev / ebitda_0, 2)
    elif ev_ebitda is not None:
        ev_ebitda = round(ev_ebitda, 2)

    # 7. EV / EBIT
    ebit_0 = _val(fin, fc.EBIT_ALIASES, 0)
    ev_ebit = round(ev / ebit_0, 2) if ev is not None and ebit_0 is not None and ebit_0 > 0 else None

    # 8. EV / Revenue
    ev_rev = info.get("enterpriseToRevenue")
    if ev_rev is None and ev is not None and rev_0 is not None and rev_0 > 0:
        ev_rev = round(ev / rev_0, 2)
    elif ev_rev is not None:
        ev_rev = round(ev_rev, 2)

    # 9. PEG Ratio
    peg = info.get("pegRatio") or info.get("trailingPegRatio")
    if peg is not None:
        peg = round(peg, 2)
    else:
        eps_list = [_val(fin, ["Basic EPS", "Diluted EPS"], i) for i in range(4)]
        if trailing_pe is not None and trailing_pe > 0 and eps_list and len(eps_list) >= 4 and eps_list[0] and eps_list[3] and eps_list[3] > 0:
            cagr = ((eps_list[0] / eps_list[3]) ** (1.0 / 3.0) - 1.0) * 100.0
            if cagr > 0:
                peg = round(trailing_pe / cagr, 2)

    # 10. FCF Yield
    fcf_0 = info.get("freeCashflow")
    if fcf_0 is None:
        ocf_0 = _val(cf, fc.OPERATING_CASH_FLOW_ALIASES, 0)
        capex_0 = _val(cf, fc.CAPEX_ALIASES, 0)
        if ocf_0 is not None and capex_0 is not None:
            fcf_0 = ocf_0 - abs(capex_0)
    fcf_yield = round((fcf_0 / mcap) * 100.0, 2) if fcf_0 is not None and mcap and mcap > 0 else None

    # 11. Earnings Yield vs Rf (7% G-Sec)
    ey_spread = round((1.0 / trailing_pe) * 100.0 - 7.0, 2) if trailing_pe is not None and trailing_pe > 0 else None

    # 12. Dividend Yield
    div_yield = info.get("dividendYield") or info.get("trailingAnnualDividendYield")
    if div_yield is not None:
        if div_yield < 1.0 and div_yield > 0:
            div_yield = round(div_yield * 100.0, 2)
        else:
            div_yield = round(div_yield, 2)

    # 13. Graham Number
    graham_num = round(math.sqrt(22.5 * eps_0 * bvps_0), 2) if eps_0 is not None and bvps_0 is not None and eps_0 > 0 and bvps_0 > 0 else None

    # 14. EPV (Earnings Power Value)
    if not wacc_series:
        wacc_series = _wacc(frames) if isinstance(frames, dict) and frames else [10.0]
    wacc_val = wacc_series[0] if wacc_series and wacc_series[0] is not None and wacc_series[0] > 0 else 10.0
    
    ebits = [_to_crores(_val(fin, fc.EBIT_ALIASES, i)) for i in range(5)]
    ebits_pos = [x for x in ebits if x is not None and x > 0]
    norm_ebit_cr = sum(ebits_pos) / len(ebits_pos) if ebits_pos else 0.0
    
    p1_temp = _pillar_income_statement(frames, sector_bucket) if isinstance(frames, dict) and frames else {}
    etr_obj = p1_temp.get("effectiveTaxRate3yAvg")
    etr_val = etr_obj[0] if isinstance(etr_obj, list) and etr_obj else (etr_obj if isinstance(etr_obj, (int, float)) else 25.0)
    t_rate = (etr_val / 100.0) if etr_val is not None and 0.0 < etr_val < 50.0 else 0.25
    
    epv_cr = round(norm_ebit_cr * (1.0 - t_rate) / (wacc_val / 100.0), 2) if norm_ebit_cr > 0 else 0.0
    epv_per_share = round((epv_cr * 1e7) / shares, 2) if shares and shares > 0 and epv_cr > 0 else 0.0

    # 15. Margin of Safety
    mos_pct = None
    mos_verdict = "N/A"
    if epv_per_share > 0 and price is not None and price > 0:
        mos_pct = round(((epv_per_share - price) / epv_per_share) * 100.0, 2)
        if mos_pct > 30.0:
            mos_verdict = ">30% ✅ (Undervalued)"
        elif mos_pct >= 0.0:
            mos_verdict = "0-30% 🟡 (Fairly Valued)"
        else:
            mos_verdict = "<0 🔴 (Overvalued)"

    # 16. Own-history & FMCG note
    is_fmcg = (sector_bucket == "CONSUMER_FMCG_RET_QSR")
    is_commodity_energy = (sector_bucket in ["COMMODITIES_CHEMICALS", "METALS_MINING", "OIL_GAS_CONSUMABLE_FUELS"])
    own_history = {
        "fmcgAutoFlagSuppressed": is_fmcg,
        "fmcgNote": "Never auto-flag high P/E or P/B for FMCG; flag only >50% premium to own 5Y median. Brand premium justifies structurally higher multiples." if is_fmcg else None,
        "note": "Primary valuation metric for Commodities/Metals/O&G is EV/EBITDA." if is_commodity_energy else "Trailing P/E and EV/EBITDA evaluated in sector context."
    }

    return {
        "available": True,
        "excludedFromGrade": True,
        "reason": "Valuation is deliberately excluded from the Grade per Section 2.8 design principle.",
        "metrics": {
            "trailingPE": trailing_pe,
            "forwardPE": forward_pe,
            "priceToBook": pb,
            "priceToTangibleBook": ptb,
            "priceToSales": ps,
            "evToEbitda": ev_ebitda,
            "evToEbit": ev_ebit,
            "evToRevenue": ev_rev,
            "pegRatio": peg,
            "fcfYield": fcf_yield,
            "earningsYieldVsRf": ey_spread,
            "dividendYield": div_yield,
            "grahamNumber": graham_num,
            "epv": epv_per_share,
            "epvTotalCrores": epv_cr,
            "marginOfSafety": mos_pct,
            "marginOfSafetyVerdict": mos_verdict,
            "ownHistory": own_history
        },
        "grahamNumber": graham_num,
        "epv": epv_per_share,
        "marginOfSafety": mos_pct
    }


def _pillar_growth(*args, **kwargs) -> Dict[str, Any]:
    """Pillar 9 calculator — Growth (Section 2.9 / Task 20). Handles 3Y rolling average override for Real Estate."""
    frames = kwargs.get("frames", {})
    sector_bucket = kwargs.get("sector_bucket", "GENERAL_OTHER")
    p1 = kwargs.get("p1", {})
    p2 = kwargs.get("p2", {})
    p3 = kwargs.get("p3", {})
    p4 = kwargs.get("p4", {})

    for arg in args:
        if isinstance(arg, str):
            sector_bucket = arg
        elif isinstance(arg, dict):
            if "financials" in arg or "balance_sheet" in arg or "cashflow" in arg:
                frames = arg
            elif "revenueYoyGrowthPct" in arg or "ebitdaMargins" in arg or "ebit" in arg:
                p1 = arg
            elif "assets" in arg or "equity" in arg or "bvps" in arg:
                p2 = arg
            elif "ocfQuality" in arg or "fcf" in arg or "operatingCashFlow" in arg:
                p3 = arg
            elif "roe" in arg or "roic" in arg or "reinvestmentRate" in arg:
                p4 = arg

    is_re = (sector_bucket == "REAL_ESTATE_CONSTRUCTION")
    fin = frames.get("financials", {}) if isinstance(frames, dict) else {}
    bs = frames.get("balance_sheet", {}) if isinstance(frames, dict) else {}
    cf = frames.get("cashflow", {}) if isinstance(frames, dict) else {}
    info = frames.get("info", {}) if isinstance(frames, dict) else {}

    def _get_series_list(stmt, aliases):
        return [_val(stmt, aliases, i) for i in range(6)]

    rev_series = _get_series_list(fin, fc.REVENUE_ALIASES)
    ebitda_series = [_val(fin, ["EBITDA", "Normalized EBITDA"], i) for i in range(6)]
    ni_series = _get_series_list(fin, fc.NET_INCOME_ALIASES)
    eps_series = _get_series_list(fin, ["Basic EPS", "Diluted EPS"])
    
    eq_series = _get_series_list(bs, fc.EQUITY_ALIASES)
    sh_series = [_val(bs, ["Ordinary Shares Number", "Share Issued"], i) or info.get("sharesOutstanding") for i in range(6)]
    bvps_series = [
        (eq / sh) if eq is not None and sh is not None and sh > 0 else None
        for eq, sh in zip(eq_series, sh_series)
    ]
    
    ocf_series = _get_series_list(cf, fc.OPERATING_CASH_FLOW_ALIASES)
    capex_series = _get_series_list(cf, fc.CAPEX_ALIASES)
    fcf_series = [
        (ocf - abs(capex)) if ocf is not None and capex is not None else None
        for ocf, capex in zip(ocf_series, capex_series)
    ]
    assets_series = _get_series_list(bs, fc.TOTAL_ASSETS_ALIASES)

    def _calc_cagr(series, periods):
        if not series or len(series) <= periods:
            return None
        val_curr = series[0]
        val_prev = series[periods]
        if val_curr is None or val_prev is None:
            return None
        if is_re and periods == 1:
            valid_curr = [x for x in series[:3] if x is not None]
            valid_prev = [x for x in series[1:4] if x is not None]
            if len(valid_curr) >= 2 and len(valid_prev) >= 2:
                avg_curr = sum(valid_curr) / len(valid_curr)
                avg_prev = sum(valid_prev) / len(valid_prev)
                if avg_prev != 0:
                    return round(((avg_curr - avg_prev) / abs(avg_prev)) * 100.0, 2)
        if val_prev > 0 and val_curr > 0:
            if periods == 1:
                return round(((val_curr - val_prev) / val_prev) * 100.0, 2)
            else:
                return round(((val_curr / val_prev) ** (1.0 / periods) - 1.0) * 100.0, 2)
        elif periods == 1 and val_prev != 0:
            return round(((val_curr - val_prev) / abs(val_prev)) * 100.0, 2)
        return None

    # 1. Revenue CAGRs
    rev_1y = _calc_cagr(rev_series, 1)
    rev_3y = _calc_cagr(rev_series, 3)
    rev_5y = _calc_cagr(rev_series, 5)

    # 2. EBITDA CAGRs
    ebitda_1y = _calc_cagr(ebitda_series, 1)
    ebitda_3y = _calc_cagr(ebitda_series, 3)
    ebitda_5y = _calc_cagr(ebitda_series, 5)

    # 3. Net Income CAGRs
    ni_1y = _calc_cagr(ni_series, 1)
    ni_3y = _calc_cagr(ni_series, 3)
    ni_5y = _calc_cagr(ni_series, 5)

    # 4. EPS CAGRs
    eps_1y = _calc_cagr(eps_series, 1)
    eps_3y = _calc_cagr(eps_series, 3)
    eps_5y = _calc_cagr(eps_series, 5)

    # 5. BVPS CAGRs
    bvps_3y = _calc_cagr(bvps_series, 3)
    bvps_5y = _calc_cagr(bvps_series, 5)

    # 6. OCF CAGRs
    ocf_1y = _calc_cagr(ocf_series, 1)
    ocf_3y = _calc_cagr(ocf_series, 3)
    ocf_5y = _calc_cagr(ocf_series, 5)

    # 7. FCF CAGRs
    fcf_1y = _calc_cagr(fcf_series, 1)
    fcf_3y = _calc_cagr(fcf_series, 3)

    # 8. Profit vs Revenue CAGR divergence
    div_profit_rev = None
    if ni_3y is not None and rev_3y is not None:
        div_profit_rev = round(ni_3y - rev_3y, 2)

    # 9. Revenue vs Asset CAGR divergence
    assets_3y = _calc_cagr(assets_series, 3)
    div_rev_assets = None
    if rev_3y is not None and assets_3y is not None:
        div_rev_assets = round(rev_3y - assets_3y, 2)

    # 10. SGR (Sustainable Growth Rate) = ROE * (1 - PayoutRatio)
    roe_val = p4.get("roe") or (info.get("returnOnEquity") * 100.0 if info.get("returnOnEquity") is not None else None)
    payout_val = info.get("payoutRatio")
    if payout_val is None:
        div_paid = _val(cf, fc.DIVIDENDS_PAID_ALIASES, 0)
        ni_0 = ni_series[0] if ni_series else None
        if div_paid is not None and ni_0 is not None and ni_0 > 0:
            payout_val = abs(div_paid) / ni_0
    sgr = round(roe_val * (1.0 - (payout_val or 0.0)), 2) if roe_val is not None else None

    # 11. Reinvestment Rate (cross-ref from Pillar 4)
    reinvest_rate = p4.get("reinvestmentRate")

    # 12. Growth Consistency Score (count of positive YoY revenue growth years out of up to 5)
    pos_years = 0
    total_years = 0
    for i in range(5):
        if i + 1 < len(rev_series) and rev_series[i] is not None and rev_series[i + 1] is not None and rev_series[i + 1] != 0:
            total_years += 1
            if rev_series[i] > rev_series[i + 1]:
                pos_years += 1
    consistency_score = f"{pos_years} of {total_years} positive growth years (Score: {pos_years}/{total_years})" if total_years > 0 else "N/A"
    consistency_num = pos_years

    # 13. Real Estate 3Y rolling override note
    re_note = "3Y rolling average applied to YoY growth figures per Finding 6 (Ind AS 115 POCM revenue smoothing)." if is_re else None

    # Determine growth quality score / band
    score = 0
    if rev_3y is not None and rev_3y > 10.0: score += 1
    if eps_3y is not None and eps_3y > 10.0: score += 1
    if ocf_3y is not None and ocf_3y > 10.0: score += 1
    if consistency_num >= 4: score += 1
    if div_profit_rev is not None and abs(div_profit_rev) <= 15.0: score += 1

    return {
        "available": True,
        "score": score,
        "maxScore": 5,
        "metrics": {
            "revenueCagr": {"1Y": rev_1y, "3Y": rev_3y, "5Y": rev_5y},
            "ebitdaCagr": {"1Y": ebitda_1y, "3Y": ebitda_3y, "5Y": ebitda_5y},
            "netIncomeCagr": {"1Y": ni_1y, "3Y": ni_3y, "5Y": ni_5y},
            "epsCagr": {"1Y": eps_1y, "3Y": eps_3y, "5Y": eps_5y},
            "bvpsCagr": {"3Y": bvps_3y, "5Y": bvps_5y},
            "ocfCagr": {"1Y": ocf_1y, "3Y": ocf_3y, "5Y": ocf_5y},
            "fcfCagr": {"1Y": fcf_1y, "3Y": fcf_3y},
            "profitVsRevDivergence": div_profit_rev,
            "revVsAssetDivergence": div_rev_assets,
            "sgr": sgr,
            "reinvestmentRate": reinvest_rate,
            "growthConsistencyScore": consistency_score,
            "growthConsistencyNum": consistency_num,
            "realEstateRollingOverride": is_re,
            "realEstateNote": re_note
        }
    }


def _red_flag_engine(pillars_dict: Dict[str, Any], sector_bucket: str, beneish: Dict[str, Any], altman_result: Dict[str, Any], sloan_result: Dict[str, Any], frames: Dict[str, Any] = None) -> Dict[str, Any]:
    """16-point Red Flag Engine + Phase-2 stubs + Beneish corroboration wiring (Section 3 & 2.7 / Task 18)."""
    p1 = pillars_dict.get("incomeStatement", {})
    p2 = pillars_dict.get("balanceSheet", {})
    p3 = pillars_dict.get("cashFlow", {})
    p4 = pillars_dict.get("profitability", {})
    p5 = pillars_dict.get("solvency", {})
    p6 = pillars_dict.get("efficiency", {})
    p7 = pillars_dict.get("sloanAccrual", {}) if pillars_dict.get("sloanAccrual") else sloan_result

    def _get_val0(obj):
        if isinstance(obj, list) and len(obj) > 0:
            return obj[0]
        if isinstance(obj, dict):
            for k in ["value", "values", "financialPrimary", "ocf", "fcf"]:
                if k in obj and isinstance(obj[k], list) and len(obj[k]) > 0:
                    return obj[k][0]
                elif k in obj and isinstance(obj[k], (int, float)):
                    return obj[k]
        if isinstance(obj, (int, float)):
            return obj
        return None

    def _get_series(obj, default_len=2):
        if isinstance(obj, list):
            return obj if len(obj) > 0 else [None] * default_len
        if isinstance(obj, dict):
            for k in ["values", "value", "financialPrimary", "roic", "wacc", "ocf", "fcf"]:
                if k in obj and isinstance(obj[k], list):
                    return obj[k] if len(obj[k]) > 0 else [None] * default_len
        return [None] * default_len

    flags = []

    # 1. Revenue vs Receivables Divergence
    rev_growth = _get_val0(p1.get("revenueYoyGrowthPct"))
    rec_series = _get_series(p2.get("assets", {}).get("receivables"))
    rec_growth = ((rec_series[0] - rec_series[1]) / rec_series[1] * 100.0) if rec_series and len(rec_series) >= 2 and rec_series[0] is not None and rec_series[1] and rec_series[1] > 0 else None
    
    t1 = False
    override1 = False
    if rev_growth is not None and rec_growth is not None and rev_growth > 0 and rec_growth > 0:
        if sector_bucket == "EPC_CAPITAL_GOODS_DEFENSE_INFRA":
            override1 = True
            rec_growth_prev = ((rec_series[1] - rec_series[2]) / rec_series[2] * 100.0) if len(rec_series) >= 3 and rec_series[1] is not None and rec_series[2] and rec_series[2] > 0 else 0.0
            rev_series = _get_series(p1.get("revenueYoyGrowthPct"))
            rev_growth_prev = rev_series[1] if len(rev_series) >= 2 and rev_series[1] is not None else 0.0
            if rec_growth > 2.5 * rev_growth and rec_growth_prev > 2.5 * rev_growth_prev:
                t1 = True
        else:
            if rec_growth > 1.5 * rev_growth:
                t1 = True

    flags.append({
        "id": 1,
        "name": "Revenue vs Receivables Divergence",
        "severity": "WARNING",
        "triggered": t1,
        "sectorOverrideApplied": override1,
        "alertString": f"⚠️ Sales grew {round(rev_growth or 0.0, 1)}% but uncollected bills surged {round(rec_growth or 0.0, 1)}%. Possible channel stuffing, round-tripping, or aggressive revenue recognition."
    })

    # 2. Profit vs Cash Flow Divergence (CRITICAL)
    net_0 = _get_val0(p1.get("basicEps"))
    ocf_0 = _get_val0(p3.get("ocfQuality", {}).get("ocf"))
    ocf_ni_0 = _get_val0(p3.get("ocfQuality", {}).get("ocfToNi"))
    ni_pos = (ocf_0 is not None and ocf_ni_0 is not None and ocf_0 < 0 and ocf_ni_0 < 0) or (net_0 is not None and net_0 > 0 and ocf_0 is not None and ocf_0 < 0)
    t2 = (ni_pos and ocf_0 is not None and ocf_0 < 0)
    flags.append({
        "id": 2,
        "name": "Profit vs Cash Flow Divergence",
        "severity": "CRITICAL",
        "triggered": t2,
        "sectorOverrideApplied": False,
        "alertString": f"Company reports profit but burned ₹{round(abs(ocf_0 or 0.0), 1)} Cr cash. Reported profit is being driven by accruals, not real cash."
    })

    # 3. Rising Inventory Without Revenue Growth
    inv_series = _get_series(p2.get("assets", {}).get("inventory"))
    inv_growth = ((inv_series[0] - inv_series[1]) / inv_series[1] * 100.0) if inv_series and len(inv_series) >= 2 and inv_series[0] is not None and inv_series[1] and inv_series[1] > 0 else None
    t3 = False
    override3 = False
    if rev_growth is not None and inv_growth is not None and rev_growth > 0 and inv_growth > 0:
        if sector_bucket == "PHARMA_API_CDMO_CHEMICALS":
            override3 = True
            gm_series = _get_series(p1.get("grossMarginPct"))
            gm_0 = gm_series[0] if len(gm_series) >= 1 else None
            gm_1 = gm_series[1] if len(gm_series) >= 2 else None
            if inv_growth > 3.0 * rev_growth and (gm_0 is not None and gm_1 is not None and gm_0 < gm_1):
                t3 = True
        else:
            if inv_growth > 2.0 * rev_growth:
                t3 = True
    flags.append({
        "id": 3,
        "name": "Rising Inventory Without Revenue Growth",
        "severity": "WARNING",
        "triggered": t3,
        "sectorOverrideApplied": override3,
        "alertString": f"⚠️ Inventory piling up {round(inv_growth or 0.0, 1)}% while sales grew only {round(rev_growth or 0.0, 1)}%. Possible obsolescence risk or demand slowdown — check if gross margin is also compressing; if not, may reflect strategic supply-chain buffering, not a demand problem."
    })

    # 4. Other Income Dependence
    other_pct = _get_val0(p1.get("otherIncomePctOfPbt"))
    t4 = (other_pct is not None and other_pct > 20.0)
    flags.append({
        "id": 4,
        "name": "Other Income Dependence",
        "severity": "WARNING",
        "triggered": t4,
        "sectorOverrideApplied": False,
        "alertString": f"⚠️ Core business profitability is weak. {round(other_pct or 0.0, 1)}% of pre-tax profit comes from non-operational sources."
    })

    # 5. Debt Spiral Detection
    fd_series = _get_series(p2.get("liabilities", {}).get("financialDebt"), 4)
    t5 = False
    debt_cagr = 0.0
    if fd_series and len(fd_series) >= 4 and all(v is not None and v > 0 for v in fd_series[:4]):
        if fd_series[0] > 1.15 * fd_series[1] and fd_series[1] > 1.15 * fd_series[2] and fd_series[2] > 1.15 * fd_series[3]:
            ocf_series = _get_series(p3.get("ocfQuality", {}).get("ocf"))
            ocf_1 = ocf_series[1] if len(ocf_series) >= 2 else None
            if ocf_0 is not None and ocf_1 is not None and ocf_0 <= ocf_1:
                t5 = True
        debt_cagr = ((fd_series[0] / fd_series[3]) ** (1.0 / 3.0) - 1.0) * 100.0
    flags.append({
        "id": 5,
        "name": "Debt Spiral Detection",
        "severity": "RED",
        "triggered": t5,
        "sectorOverrideApplied": False,
        "alertString": f"Financial borrowings compounded at {round(debt_cagr, 1)}% annually for 3 years while OCF stagnated."
    })

    # 6. Equity Dilution
    dilution_pct = 0.0
    if frames and frames.get("balance_sheet") and frames.get("financials"):
        sh_0 = _val(frames["balance_sheet"], ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"], 0) or _val(frames["financials"], ["Basic Average Shares", "Diluted Average Shares"], 0)
        sh_1 = _val(frames["balance_sheet"], ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"], 1) or _val(frames["financials"], ["Basic Average Shares", "Diluted Average Shares"], 1)
        if sh_0 and sh_1 and sh_1 > 0:
            dilution_pct = ((sh_0 - sh_1) / sh_1) * 100.0
    t6 = (dilution_pct > 2.0)
    flags.append({
        "id": 6,
        "name": "Equity Dilution",
        "severity": "WARNING",
        "triggered": t6,
        "sectorOverrideApplied": False,
        "alertString": f"⚠️ Shareholder dilution: {round(dilution_pct, 1)}% new shares issued. If this coincides with a QIP/rights issue, Beneish SGAI/LVGI are suppressed for this year."
    })

    # 7. Goodwill / Intangible Bloat
    int_pct = _get_val0(p2.get("assets", {}).get("intangiblesPctOfAssets"))
    t7 = (int_pct is not None and int_pct > 30.0)
    flags.append({
        "id": 7,
        "name": "Goodwill / Intangible Bloat",
        "severity": "WARNING",
        "triggered": t7,
        "sectorOverrideApplied": False,
        "alertString": f"⚠️ {round(int_pct or 0.0, 1)}% of the balance sheet is intangible. High impairment risk."
    })

    # 8. CapEx Collapse (Asset Milking)
    capex_dep = _get_series(p3.get("capex", {}).get("capexToDepreciation"))
    t8 = (capex_dep and len(capex_dep) >= 2 and capex_dep[0] is not None and capex_dep[0] < 0.5 and capex_dep[1] is not None and capex_dep[1] < 0.5)
    flags.append({
        "id": 8,
        "name": "CapEx Collapse (Asset Milking)",
        "severity": "WARNING",
        "triggered": t8,
        "sectorOverrideApplied": False,
        "alertString": f"⚠️ CapEx is only {round(capex_dep[0] or 0.0, 2) if capex_dep else 0.0}× depreciation for 2+ years. Assets are being milked without reinvestment."
    })

    # 9. Unsustainable Dividend
    fcf_cov = _get_val0(p3.get("financing", {}).get("fcfDividendCoverage"))
    fcf_val = _get_val0(p3.get("ocfQuality", {}).get("fcf"))
    t9 = (fcf_cov is not None and fcf_cov < 1.0 and fcf_val is not None)
    div_val = round(fcf_val / fcf_cov, 1) if fcf_cov and fcf_cov > 0 and fcf_val else 0.0
    flags.append({
        "id": 9,
        "name": "Unsustainable Dividend",
        "severity": "RED",
        "triggered": t9,
        "sectorOverrideApplied": False,
        "alertString": f"Unsustainable dividend: ₹{div_val} Cr paid but only ₹{round(fcf_val or 0.0, 1)} Cr FCF generated. Funded from debt or reserves."
    })

    # 10. Interest Coverage Crunch
    int_cov = _get_val0(p1.get("interestBurdenExLease"))
    t10 = (int_cov is not None and int_cov < 1.5)
    flags.append({
        "id": 10,
        "name": "Interest Coverage Crunch",
        "severity": "RED",
        "triggered": t10,
        "sectorOverrideApplied": False,
        "alertString": f"Financial interest barely covered ({round(int_cov or 0.0, 1)}× ex-lease). One bad quarter from technical default risk."
    })

    # 11. Tax Rate Anomaly
    etr_3y = _get_val0(p1.get("effectiveTaxRate3yAvg"))
    t11 = False
    sev11 = "WARNING"
    override11 = False
    alert11 = ""
    if etr_3y is not None:
        if etr_3y > 40.0:
            t11 = True
            sev11 = "RED"
            alert11 = f"Effective tax rate averaged {round(etr_3y, 1)}% over 3 years — unusually high; investigate one-time items."
        elif etr_3y < 10.0:
            t11 = True
            if sector_bucket in ["IT_SOFTWARE_SERVICES", "RENEWABLE_POWER_INFRA_80IA"]:
                sev11 = "INFO"
                override11 = True
                alert11 = f"ℹ️ ETR averaged {round(etr_3y, 1)}% over 3 years — consistent with known statutory tax holiday exposure. Not flagged as anomalous."
            else:
                sev11 = "WARNING"
                alert11 = f"🟡 ETR of {round(etr_3y, 1)}% is unusually low for this sector — investigate."
    if not alert11:
        alert11 = f"ETR averaged {round(etr_3y or 0.0, 1)}% over 3 years — normal range."
    flags.append({
        "id": 11,
        "name": "Tax Rate Anomaly",
        "severity": sev11,
        "triggered": t11,
        "sectorOverrideApplied": override11,
        "alertString": alert11
    })

    # 12. Leverage-Price Divergence
    de_series = _get_series(p2.get("liabilities", {}).get("debtToEquity"))
    de_growth = 0.0
    if de_series and len(de_series) >= 2 and de_series[0] is not None and de_series[1] and de_series[1] > 0:
        de_growth = ((de_series[0] - de_series[1]) / de_series[1]) * 100.0
    price_change = frames.get("info", {}).get("52WeekChange", 0.0) * 100.0 if frames and frames.get("info") else 0.0
    t12 = (de_growth > 20.0 and price_change < -20.0)
    flags.append({
        "id": 12,
        "name": "Leverage-Price Divergence",
        "severity": "WARNING",
        "triggered": t12,
        "sectorOverrideApplied": False,
        "alertString": f"⚠️ Leverage increasing during price decline — potential promoter margin-call or forced-selling risk."
    })

    # 13. CCC Deterioration
    ccc_series = _get_series(p6.get("cccTrajectory"))
    t13 = False
    override13 = False
    ccc_prev = 0.0
    ccc_curr = 0.0
    if ccc_series and len(ccc_series) >= 2 and ccc_series[0] is not None and ccc_series[1] is not None and ccc_series[1] > 0:
        ccc_curr = ccc_series[0]
        ccc_prev = ccc_series[1]
        if sector_bucket in ["REAL_ESTATE_CONSTRUCTION", "EPC_CAPITAL_GOODS_DEFENSE_INFRA"]:
            override13 = True
            t13 = False
        elif ccc_curr > ccc_prev * 1.20:
            t13 = True
    flags.append({
        "id": 13,
        "name": "CCC Deterioration",
        "severity": "WARNING",
        "triggered": t13,
        "sectorOverrideApplied": override13,
        "alertString": f"⚠️ CCC expanded from {round(ccc_prev, 1)} to {round(ccc_curr, 1)} days ({round(((ccc_curr - ccc_prev)/ccc_prev*100.0) if ccc_prev else 0.0, 1)}% deterioration)."
    })

    # 14. Aggressive Depreciation Policy (DEPI)
    depi_0 = _get_val0(beneish.get("depi"))
    cwip_check = _get_val0(beneish.get("depiCwipCrossCheckApplied")) or False
    t14 = (depi_0 is not None and depi_0 > 1.3 and not cwip_check)
    flags.append({
        "id": 14,
        "name": "Aggressive Depreciation Policy (DEPI)",
        "severity": "WARNING",
        "triggered": t14,
        "sectorOverrideApplied": cwip_check,
        "alertString": f"⚠️ Depreciation rates slowing (DEPI: {round(depi_0 or 0.0, 2)}) without a proportional asset-commissioning event. May be artificially inflating current-year profits."
    })

    # 15. Persistent Capital Destruction
    roic_series = _get_series(p4.get("returns", {}).get("roic"), 3)
    wacc_series = _get_series(p4.get("returns", {}).get("wacc"), 3)
    if not any(wacc_series) and frames:
        wacc_series = _wacc(frames)
    elif not any(wacc_series):
        wacc_series = [10.0] * len(roic_series)
    t15 = False
    if roic_series and wacc_series and len(roic_series) >= 3 and len(wacc_series) >= 3:
        if all(r is not None and w is not None and r < w for r, w in zip(roic_series[:3], wacc_series[:3])):
            t15 = True
    flags.append({
        "id": 15,
        "name": "Persistent Capital Destruction",
        "severity": "RED",
        "triggered": t15,
        "sectorOverrideApplied": False,
        "alertString": f"Persistent capital destruction for 3+ years. ROIC ({round(roic_series[0] or 0.0, 1) if roic_series else 0.0}%) < WACC ({round(wacc_series[0] or 0.0, 1) if wacc_series else 0.0}%) - systematically destroying shareholder wealth."
    })

    # 16. Promoter Shareholding Decline
    promoter_decline = frames.get("info", {}).get("promoterHoldingChange", 0.0) if frames and frames.get("info") else 0.0
    t16 = (promoter_decline < -3.0)
    flags.append({
        "id": 16,
        "name": "Promoter Shareholding Decline",
        "severity": "WARNING",
        "triggered": t16,
        "sectorOverrideApplied": False,
        "alertString": f"⚠️ Promoter/insider shareholding fell {round(abs(promoter_decline), 1)}pp YoY. Cross-check against pledge disclosures and open-market sale filings."
    })

    custom_triggered_count = sum(1 for f in flags if f["triggered"])
    if isinstance(beneish, dict):
        beneish["corroboratingFlagCount"] = custom_triggered_count
        beneish["escalatedToRed"] = (custom_triggered_count >= 2)

    # 17. Altman Z Distress Signal
    alt_zone = _get_val0(altman_result.get("zone"))
    t17 = (alt_zone in ["Grey", "Distress"] and altman_result.get("available", False) and altman_result.get("modelUsed") != "ALTMAN_REPLACED_BY_ROLLING_FCF_AND_NET_DEBT")
    sev17 = "RED" if alt_zone == "Distress" else "WARNING"
    flags.append({
        "id": 17,
        "name": "Altman Z Distress Signal",
        "severity": sev17,
        "triggered": t17,
        "sectorOverrideApplied": not altman_result.get("available", True),
        "alertString": f"Altman Z ({altman_result.get('modelUsed', 'N/A')}) of {round(_get_val0(altman_result.get('score')) or 0.0, 2)} places the company in the {alt_zone} zone for its sector-appropriate model."
    })

    # 18. Sloan Accrual Breach
    sloan_flag = _get_val0(sloan_result.get("flagged"))
    sloan_level = _get_val0(sloan_result.get("flagLevel")) or "Normal"
    t18 = (sloan_flag == True)
    sev18 = "RED" if sloan_level == "Severe" else "WARNING"
    flags.append({
        "id": 18,
        "name": "Sloan Accrual Breach",
        "severity": sev18,
        "triggered": t18,
        "sectorOverrideApplied": not sloan_result.get("available", True),
        "alertString": f"Accrual ratio of {round((_get_val0(sloan_result.get('accrualRatio')) or 0.0)*100.0, 1)}% exceeds the {sloan_result.get('revenue3yCagrBand', '<10%')}-growth threshold of {sloan_result.get('moderateThresholdPct', 10.0)}% — a large share of reported earnings is not yet cash."
    })

    phase2_stubs = {
        "rpt": {"available": False, "reason": "Requires SEBI LODR BSE/NSE filing scrape — Phase 2"},
        "promoterPledge": {"available": False, "reason": "Requires BSE/NSE shareholding XBRL — Phase 2"},
        "auditorChange": {"available": False, "reason": "Requires BSE corporate announcements + AR text-mining — Phase 2. Historically high-signal (Satyam, DHFL, IL&FS)."},
        "contingentLiabilities": {"available": False, "reason": "AR notes disclosure — not in yfinance. Phase 2."}
    }
    if sector_bucket == "HOLDING_COMPANY":
        phase2_stubs["navDiscount"] = {"available": False, "reason": "Requires holding company investments schedule and market valuations — Phase 2"}

    return {
        "available": True,
        "redFlags": flags,
        "phase2Stubs": phase2_stubs,
        "triggeredCount": sum(1 for f in flags if f["triggered"]),
        "customTriggeredCount": custom_triggered_count
    }


def _overall_grade(pillars_dict: Dict[str, Any], forensics_dict: Dict[str, Any] = None, active_pillar_weights: Dict[str, float] = None, *args, **kwargs) -> Dict[str, Any]:
    """Overall Fundamental Grade Weighting Algorithm (Section 1.4 / Task 21). Deliberately excludes valuation."""
    for arg in args:
        if isinstance(arg, dict):
            if "redFlags" in arg or "flagLevel" in arg or "triggeredCount" in arg:
                forensics_dict = arg
            elif "forensics" in arg or "cashFlow" in arg or "profitability" in arg:
                active_pillar_weights = arg

    default_weights = {
        "forensics": 30.0,
        "cashFlow": 20.0,
        "profitability": 20.0,
        "solvency": 15.0,
        "growth": 10.0,
        "efficiency": 5.0
    }
    raw_weights = {}
    if active_pillar_weights and isinstance(active_pillar_weights, dict):
        raw_weights = {k: float(v) for k, v in active_pillar_weights.items() if v is not None and float(v) > 0}
    else:
        for k, default_w in default_weights.items():
            res_obj = None
            if k == "forensics":
                res_obj = forensics_dict or pillars_dict.get("forensics") or pillars_dict.get("redFlagEngine")
            else:
                res_obj = pillars_dict.get(k)
            
            is_active = True
            if isinstance(res_obj, dict):
                if res_obj.get("available") is False or res_obj.get("suppressed") is True:
                    is_active = False
            if is_active:
                raw_weights[k] = default_w

    if not raw_weights:
        raw_weights = default_weights.copy()

    total_raw = sum(raw_weights.values())
    renorm_weights = {}
    if total_raw > 0:
        for k, w in raw_weights.items():
            renorm_weights[k] = round((w / total_raw) * 100.0, 4)
    else:
        renorm_weights = {k: round(w, 4) for k, w in default_weights.items()}

    diff = round(100.0 - sum(renorm_weights.values()), 4)
    if abs(diff) > 0 and renorm_weights:
        max_k = max(renorm_weights, key=renorm_weights.get)
        renorm_weights[max_k] = round(renorm_weights[max_k] + diff, 4)

    # 1. Forensics Subscore
    forensics_res = forensics_dict or pillars_dict.get("forensics") or pillars_dict.get("redFlagEngine") or {}
    red_flags = forensics_res.get("redFlags", [])
    w_cnt = sum(1 for f in red_flags if f.get("triggered") and f.get("severity") == "WARNING")
    r_cnt = sum(1 for f in red_flags if f.get("triggered") and f.get("severity") in ["RED", "CRITICAL"])
    f_sub = max(0.0, 100.0 - (10.0 * w_cnt) - (20.0 * r_cnt))
    f_score = pillars_dict.get("piotroski", {}).get("score") or pillars_dict.get("efficiency", {}).get("piotroski", {}).get("score")
    if f_score is not None:
        if f_score >= 7: f_sub += 10.0
        elif f_score <= 3: f_sub -= 10.0
    forensics_subscore = round(max(0.0, min(100.0, f_sub)), 2)

    # 2. Cash Flow Subscore
    cf_res = pillars_dict.get("cashFlow", {})
    if "score" in cf_res and "maxScore" in cf_res and cf_res["maxScore"]:
        cf_sub = (cf_res["score"] / cf_res["maxScore"]) * 100.0
    else:
        cf_sub = 0.0
        ocf_qual = cf_res.get("ocfQuality", {}) if isinstance(cf_res.get("ocfQuality"), dict) else {}
        ocf_ni = ocf_qual.get("ocfToNi") or ocf_qual.get("ocfToNetIncomeRatio")
        ocf_ni_val = ocf_ni[0] if isinstance(ocf_ni, list) and ocf_ni else (ocf_ni if isinstance(ocf_ni, (int, float)) else None)
        if ocf_ni_val is not None:
            if ocf_ni_val >= 1.0: cf_sub += 35.0
            elif ocf_ni_val >= 0.8: cf_sub += 25.0
            elif ocf_ni_val > 0.0: cf_sub += 15.0
        ocf_ebitda = ocf_qual.get("ocfToEbitda") or ocf_qual.get("ocfToEbitdaRatio")
        ocf_ebitda_val = ocf_ebitda[0] if isinstance(ocf_ebitda, list) and ocf_ebitda else (ocf_ebitda if isinstance(ocf_ebitda, (int, float)) else None)
        if ocf_ebitda_val is not None:
            if ocf_ebitda_val >= 0.7: cf_sub += 35.0
            elif ocf_ebitda_val >= 0.5: cf_sub += 25.0
            elif ocf_ebitda_val > 0.0: cf_sub += 15.0
        fcf_series = ocf_qual.get("fcf") or ocf_qual.get("fcfSeries") or cf_res.get("fcfSeries") or []
        pos_fcf = sum(1 for x in fcf_series[:5] if x is not None and x > 0)
        cf_sub += (pos_fcf / 5.0) * 30.0 if fcf_series else 15.0
    cashflow_subscore = round(max(0.0, min(100.0, cf_sub)), 2)

    # 3. Profitability Subscore
    prof_res = pillars_dict.get("profitability", {})
    if "score" in prof_res and "maxScore" in prof_res and prof_res["maxScore"]:
        prof_sub = (prof_res["score"] / prof_res["maxScore"]) * 100.0
    else:
        prof_sub = 0.0
        returns_dict = prof_res.get("returns", {}) if isinstance(prof_res.get("returns"), dict) else {}
        roic_list = returns_dict.get("roic", [])
        wacc_list = returns_dict.get("wacc", [])
        roic_val = roic_list[0] if roic_list and roic_list[0] is not None else None
        wacc_val = wacc_list[0] if wacc_list and wacc_list[0] is not None else 10.0
        if roic_val is not None and wacc_val is not None:
            spread = roic_val - wacc_val
            if spread > 5.0: prof_sub += 40.0
            elif spread > 0.0: prof_sub += 25.0
            else: prof_sub += 10.0
        else:
            prof_sub += 20.0
        
        roe_list = returns_dict.get("roe", [])
        roe_val = roe_list[0] if roe_list and roe_list[0] is not None else None
        if roe_val is not None:
            if roe_val >= 20.0: prof_sub += 30.0
            elif roe_val >= 15.0: prof_sub += 20.0
            elif roe_val >= 10.0: prof_sub += 10.0
        else:
            prof_sub += 15.0
            
        dupont = prof_res.get("dupont3Factor", {}) if isinstance(prof_res.get("dupont3Factor"), dict) else {}
        nm_list = dupont.get("netMargin", [])
        em_list = dupont.get("equityMultiplier", [])
        nm_val = nm_list[0] if nm_list and nm_list[0] is not None else None
        em_val = em_list[0] if em_list and em_list[0] is not None else None
        if nm_val is not None and em_val is not None:
            if nm_val > 10.0 and em_val < 3.0: prof_sub += 30.0
            elif nm_val > 5.0: prof_sub += 20.0
            else: prof_sub += 10.0
        else:
            prof_sub += 15.0
    profitability_subscore = round(max(0.0, min(100.0, prof_sub)), 2)

    # 4. Solvency Subscore
    solv_res = pillars_dict.get("solvency", {})
    if "score" in solv_res and "maxScore" in solv_res and solv_res["maxScore"]:
        solv_sub = (solv_res["score"] / solv_res["maxScore"]) * 100.0
    else:
        solv_sub = 0.0
        nde = solv_res.get("netDebtEbitdaExLease")
        if isinstance(nde, dict): nde = nde.get("netDebtEbitdaExLease")
        nde_val = nde[0] if isinstance(nde, list) and nde else (nde if isinstance(nde, (int, float)) else None)
        if nde_val is not None:
            if nde_val < 1.0: solv_sub += 35.0
            elif nde_val < 2.0: solv_sub += 25.0
            elif nde_val < 3.0: solv_sub += 15.0
            else: solv_sub += 5.0
        else: solv_sub += 20.0
        
        ic = solv_res.get("interestCoverageExLease")
        if isinstance(ic, dict): ic = ic.get("interestCoverageExLease")
        ic_val = ic[0] if isinstance(ic, list) and ic else (ic if isinstance(ic, (int, float)) else None)
        if ic_val is not None:
            if ic_val > 5.0: solv_sub += 35.0
            elif ic_val > 3.0: solv_sub += 25.0
            elif ic_val > 1.5: solv_sub += 15.0
            else: solv_sub += 5.0
        else: solv_sub += 20.0
        
        ds = solv_res.get("dscr")
        if isinstance(ds, dict): ds = ds.get("dscr")
        ds_val = ds[0] if isinstance(ds, list) and ds else (ds if isinstance(ds, (int, float)) else None)
        if ds_val is not None:
            if ds_val > 2.0: solv_sub += 30.0
            elif ds_val > 1.5: solv_sub += 20.0
            elif ds_val > 1.0: solv_sub += 10.0
            else: solv_sub += 0.0
        else: solv_sub += 15.0
    solvency_subscore = round(max(0.0, min(100.0, solv_sub)), 2)

    # 5. Growth Subscore
    growth_res = pillars_dict.get("growth", {})
    if "score" in growth_res and "maxScore" in growth_res and growth_res["maxScore"]:
        base_g = (growth_res["score"] / growth_res["maxScore"]) * 100.0
    elif "growthConsistencyNum" in growth_res.get("metrics", {}):
        base_g = (growth_res["metrics"]["growthConsistencyNum"] / 5.0) * 100.0
    else:
        base_g = 50.0
    div_pr = growth_res.get("metrics", {}).get("profitVsRevDivergence")
    if div_pr is not None and div_pr < -10.0: base_g -= 15.0
    div_ra = growth_res.get("metrics", {}).get("revVsAssetDivergence")
    if div_ra is not None and div_ra < -10.0: base_g -= 15.0
    growth_subscore = round(max(0.0, min(100.0, base_g)), 2)

    # 6. Efficiency Subscore
    eff_res = pillars_dict.get("efficiency", {})
    if "score" in eff_res and "maxScore" in eff_res and eff_res["maxScore"]:
        eff_sub = (eff_res["score"] / eff_res["maxScore"]) * 100.0
    else:
        eff_sub = 50.0
        tat = eff_res.get("totalAssetTurnover")
        tat_val = tat[0] if isinstance(tat, list) and tat else (tat if isinstance(tat, (int, float)) else None)
        if tat_val is not None and tat_val >= 1.0: eff_sub += 25.0
        ccc_traj = eff_res.get("cccTrajectory", {}).get("flagLevel") if isinstance(eff_res.get("cccTrajectory"), dict) else None
        if ccc_traj == "INFO" or not ccc_traj: eff_sub += 25.0
    efficiency_subscore = round(max(0.0, min(100.0, eff_sub)), 2)

    subscores = {
        "forensics": forensics_subscore,
        "cashFlow": cashflow_subscore,
        "profitability": profitability_subscore,
        "solvency": solvency_subscore,
        "growth": growth_subscore,
        "efficiency": efficiency_subscore
    }

    overall_score = 0.0
    for k, rw in renorm_weights.items():
        sub_val = subscores.get(k, 0.0)
        overall_score += (sub_val * rw) / 100.0
    overall_score = round(overall_score, 2)

    if overall_score >= 90.0: letter = "A+"
    elif overall_score >= 80.0: letter = "A"
    elif overall_score >= 70.0: letter = "B+"
    elif overall_score >= 60.0: letter = "B"
    elif overall_score >= 50.0: letter = "C"
    elif overall_score >= 35.0: letter = "D"
    else: letter = "F"

    active_subscores = {k: subscores[k] for k in renorm_weights.keys()}
    weakest_pillar = min(active_subscores, key=active_subscores.get) if active_subscores else "forensics"

    verdict_templates = {
        "A_BAND": {
            "efficiency": [
                "A wealth-compounding franchise with pristine accounting; efficiency metrics lag peers but are not a quality concern at this grade.",
                "Exceptional fundamental strength across all primary pillars; minor inefficiencies in asset turnover or cash conversion cycle do not detract from its elite grade."
            ],
            "growth": [
                "High-quality earnings and robust balance sheet; top-line expansion is currently moderate, but core profitability and cash conversion remain pristine.",
                "An outstanding operating franchise generating strong free cash flow; revenue growth is steady rather than explosive, fitting a mature compounder."
            ],
            "solvency": [
                "An elite business model with exceptional earnings quality; leverage is present but comfortably serviced by massive cash generation.",
                "Superb profitability and accounting transparency; balance sheet leverage requires standard monitoring but is well within safe operating limits."
            ],
            "profitability": [
                "Rock-solid accounting and financial health; returns on capital are currently stable rather than exceptional, supported by a fortress balance sheet.",
                "High-integrity financial statements with strong solvency; margin expansion is the primary lever for future earnings compounding."
            ],
            "cashFlow": [
                "A top-tier company with verified accounting cleanliness; cash conversion timing differences exist but core earnings power is undeniable.",
                "Excellent fundamental health and balance sheet strength; temporary working capital reinvestment is currently absorbing some operating cash flow."
            ],
            "forensics": [
                "Strong financial performance and high returns on capital; minor red flag disclosures require monitoring but do not impair the overall business quality.",
                "An exceptional operating business; conservative scrutiny highlights minor disclosure items that should be tracked over upcoming quarters."
            ]
        },
        "B_BAND": {
            "efficiency": [
                "A solid, high-quality business with dependable cash flows; working capital management and asset turnover offer room for operational improvement.",
                "Good fundamental health across earnings and solvency; tightening the cash conversion cycle would elevate the company into the elite quality tier."
            ],
            "growth": [
                "Sound accounting practices and healthy returns on capital; top-line growth is mature, requiring margin resilience to drive earnings expansion.",
                "A stable financial profile with clean disclosures; growth metrics lag higher-flying peers, but cash flow generation remains reliable."
            ],
            "solvency": [
                "Good operating profitability and cash flow conversion; debt service and balance sheet leverage are the primary constraints on financial flexibility.",
                "A profitable core enterprise; moderate debt load requires continued discipline in capital allocation and cash flow retention."
            ],
            "profitability": [
                "Reliable accounting quality and sound balance sheet structure; return on capital employed is currently average for the sector.",
                "A financially sound business with clean cash conversion; boosting operating margins is necessary to achieve top-tier wealth compounding."
            ],
            "cashFlow": [
                "Good operating margins and solid solvency; cash flow realization is lagging reported net income due to working capital intensity.",
                "A decent fundamental profile; monitoring cash conversion efficiency is recommended to ensure reported earnings translate into liquid cash."
            ],
            "forensics": [
                "Solid operating performance and healthy returns; specific red flags in working capital or accounting disclosures warrant closer inspection.",
                "A fundamentally capable business; audit-style checks reveal areas of divergence between reported profits and cash or balance sheet trends."
            ]
        },
        "C_BAND": {
            "efficiency": [
                "An average-quality fundamental profile; sluggish inventory or receivables turnover is dragging on overall capital efficiency.",
                "Moderate business quality with stable core operations; improving working capital velocity is essential to lift return on capital."
            ],
            "growth": [
                "Fair fundamental standing; stagnation in revenue or operating income growth limits long-term compounding potential without strategic catalysts.",
                "A middle-of-the-road financial profile; top-line expansion has slowed, placing greater burden on cost control to maintain margins."
            ],
            "solvency": [
                "Average operating performance overshadowed by balance sheet constraints; debt levels require careful management in a softer earnings environment.",
                "Moderate business strength; leverage metrics approach thresholds where capital preservation must take priority over aggressive expansion."
            ],
            "profitability": [
                "A functioning business with basic financial stability; return on invested capital struggles to consistently exceed the cost of capital.",
                "Fair accounting transparency; weak operating margins and muted ROE prevent the company from generating economic value add."
            ],
            "cashFlow": [
                "Moderate fundamental health; weak conversion of accounting profits into free cash flow raises questions about earnings sustainability.",
                "An average operating profile; persistent capital expenditure and working capital needs are consuming the majority of generated cash."
            ],
            "forensics": [
                "Mixed fundamental quality; multiple red flags around accruals, receivables, or earnings quality suggest cautious interpretation of reported metrics.",
                "A mediocre quality score; forensic checks highlight divergences that require active verification before relying on stated profit growth."
            ]
        },
        "DF_BAND": {
            "forensics": [
                "Severe earnings-quality and red-flag concentration — treat reported numbers with active skepticism until the flagged items are independently resolved.",
                "High forensic risk profile with multiple triggered red flags; reported profitability diverges significantly from underlying cash generation and balance sheet reality."
            ],
            "solvency": [
                "Capital destruction and covenant-level solvency stress dominate the picture; the accounting itself may be clean, but the balance sheet is not.",
                "Severe balance sheet vulnerability and elevated distress risk; heavy debt burden and weak interest coverage threaten ongoing financial stability."
            ],
            "cashFlow": [
                "Critical weakness in cash flow generation; chronic inability to convert accounting earnings into cash creates severe funding and operational risk.",
                "A distressed financial profile marked by negative free cash flow and persistent cash drain, necessitating external capital dependence."
            ],
            "profitability": [
                "Systematic capital destruction; return on capital is severely depressed below the cost of capital, eroding shareholder wealth over multi-year periods.",
                "Deep fundamental weakness characterized by chronic operating losses or negligible margins, making ongoing business viability a primary concern."
            ],
            "growth": [
                "Severe fundamental deterioration; contracting revenues and earnings reflect structural business headwinds or loss of competitive positioning.",
                "A deeply challenged business profile with negative multi-year growth trajectories across all key financial statement lines."
            ],
            "efficiency": [
                "Severe operational drag; ballooning working capital and collapsing asset turnover indicate deep inefficiencies or potential inventory/receivables distress.",
                "Critical breakdown in operating velocity; trapped capital in uncollected bills or stagnant inventory severely impairs financial liquidity."
            ]
        }
    }

    band_key = "A_BAND" if letter in ["A+", "A"] else ("B_BAND" if letter in ["B+", "B"] else ("C_BAND" if letter == "C" else "DF_BAND"))
    variants = verdict_templates.get(band_key, {}).get(weakest_pillar, [f"Fundamental Grade {letter} dominated by {weakest_pillar} profile."])
    verdict_idx = int(overall_score * 100) % len(variants) if variants else 0
    verdict_sentence = variants[verdict_idx] if variants else f"Fundamental Grade {letter}."

    weighting_breakdown = []
    for k, default_w in default_weights.items():
        is_active = (k in renorm_weights)
        weighting_breakdown.append({
            "pillar": k,
            "rawWeight": default_w,
            "activeWeight": renorm_weights.get(k, 0.0),
            "subScore": subscores.get(k, 0.0),
            "renormalized": is_active and (renorm_weights.get(k, 0.0) != default_w)
        })

    return {
        "available": True,
        "overallGrade": round(overall_score, 2),
        "letterGrade": letter,
        "weakestPillar": weakest_pillar,
        "verdictSentence": verdict_sentence,
        "renormalizationApplied": any(item["renormalized"] for item in weighting_breakdown),
        "weightingBreakdown": weighting_breakdown
    }


def _pillar_peer_benchmarking(
    target_symbol: str, target_info: dict, target_frames: dict,
    p1: dict, p2: dict, p3: dict, p4: dict, p5: dict, p6: dict, p8: dict, p9: dict,
    forensics: dict = None
) -> Dict[str, Any]:
    """
    Pillar 10: Peer Benchmarking (Section 2.10 / Task 23).
    Discovers top 4 peers via extra_service.get_peers, calls analyze_fundamentals(peer, include_peers=False) for each,
    assembles the 18-metric matrix, CCC vs ROCE quadrant, and plain-English Relative Strengths bullets.
    """
    import extra_service as es
    def _safe_float(v):
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    peers_raw = es.get_peers(target_symbol)
    if not peers_raw:
        return {
            "available": False,
            "reason": "No peers discovered via extra_service.get_peers",
            "peers": [], "matrix": {}, "cccRoceQuadrant": [], "relativeStrengths": []
        }

    # Sort by marketCap descending, take top 4
    sorted_peers = sorted(peers_raw, key=lambda x: (_safe_float(x.get("marketCap")) or 0.0), reverse=True)[:4]
    if not sorted_peers:
        return {
            "available": False,
            "reason": "No valid peers after sorting by market cap",
            "peers": [], "matrix": {}, "cccRoceQuadrant": [], "relativeStrengths": []
        }

    peer_symbols = [target_symbol]
    peer_meta_list = []
    target_res_wrap = {
        "incomeStatement": p1, "balanceSheet": p2, "cashFlow": p3,
        "profitability": p4, "solvency": p5, "efficiency": p6,
        "valuation": p8, "growth": p9, "forensics": forensics or {},
        "meta": {"fiiDiiHoldingPct": _safe_float(target_info.get("heldPercentInstitutions", target_info.get("heldPercentInsiders", None)))}
    }

    def _extract_all_18_metrics(res: dict, meta_dict: dict) -> dict:
        out = {}
        def _get_val(obj, *keys):
            curr = obj
            for k in keys:
                if isinstance(curr, dict):
                    curr = curr.get(k)
                else:
                    return None
            if isinstance(curr, list):
                for x in curr:
                    if x is not None:
                        return _safe_float(x)
                return None
            return _safe_float(curr)

        out["revenueGrowth1y"] = _get_val(res, "growth", "metrics", "revenueCagr", "1Y") or _get_val(res, "incomeStatement", "revenueYoyGrowthPct")
        out["revenueGrowth3y"] = _get_val(res, "growth", "metrics", "revenueCagr", "3Y") or _get_val(res, "incomeStatement", "revenue3yCagr")
        out["grossMarginPct"] = _get_val(res, "incomeStatement", "marginCascade", "gross") or _get_val(res, "incomeStatement", "grossMarginPct")
        out["operatingMarginPct"] = _get_val(res, "incomeStatement", "marginCascade", "operating") or _get_val(res, "incomeStatement", "operatingMarginPct")
        out["netMarginPct"] = _get_val(res, "incomeStatement", "marginCascade", "net") or _get_val(res, "incomeStatement", "marginCascade", "netMarginPct")
        out["roe"] = _get_val(res, "profitability", "returns", "roe")
        out["roic"] = _get_val(res, "profitability", "returns", "roic")
        out["debtToEquityExLease"] = _get_val(res, "balanceSheet", "liabilities", "debtToEquity", "financialPrimary") or _get_val(res, "balanceSheet", "liabilities", "debtToEquity", "totalSecondary")
        out["netDebtEbitdaExLease"] = _get_val(res, "solvency", "netDebtEbitdaExLease")
        out["interestCoverageExLease"] = _get_val(res, "solvency", "interestCoverageExLease")
        out["currentRatio"] = _get_val(res, "solvency", "currentRatio")
        out["pe"] = _get_val(res, "valuation", "metrics", "trailingPE") or _get_val(res, "valuation", "metrics", "forwardPE")
        out["evToEbitda"] = _get_val(res, "valuation", "metrics", "evToEbitda")
        out["pb"] = _get_val(res, "valuation", "metrics", "priceToBook")
        out["fcfYieldPct"] = _get_val(res, "valuation", "metrics", "fcfYield")
        if out["fcfYieldPct"] is not None and abs(out["fcfYieldPct"]) <= 1.5 and out["fcfYieldPct"] != 0:
            out["fcfYieldPct"] = round(out["fcfYieldPct"] * 100, 2)
        out["piotroskiScore"] = _get_val(res, "forensics", "piotroski", "score")
        out["altmanZScore"] = _get_val(res, "forensics", "altmanZ", "score")
        out["fiiDiiHoldingPct"] = _get_val(res, "meta", "fiiDiiHoldingPct") or _get_val(meta_dict, "fiiDiiHoldingPct") or _safe_float(meta_dict.get("heldPercentInstitutions", meta_dict.get("heldPercentInsiders")))
        if out["fiiDiiHoldingPct"] is not None and out["fiiDiiHoldingPct"] <= 1.0 and out["fiiDiiHoldingPct"] > 0:
            out["fiiDiiHoldingPct"] = round(out["fiiDiiHoldingPct"] * 100, 2)
        return out

    all_extracted = {target_symbol: _extract_all_18_metrics(target_res_wrap, target_info)}
    all_res_map = {target_symbol: target_res_wrap}

    for p in sorted_peers:
        p_sym = p.get("symbol")
        if not p_sym or p_sym == target_symbol:
            continue
        try:
            p_res = analyze_fundamentals(p_sym, include_peers=False)
            if not p_res:
                continue
            peer_symbols.append(p_sym)
            peer_meta_list.append({
                "symbol": p_sym,
                "name": p.get("name") or p_sym,
                "marketCap": _safe_float(p.get("marketCap")),
                "peerSource": p.get("peerSource", "UNKNOWN")
            })
            all_extracted[p_sym] = _extract_all_18_metrics(p_res, p_res.get("meta", {}))
            all_res_map[p_sym] = p_res
        except Exception as e:
            logger.warning(f"[_pillar_peer_benchmarking] Failed to analyze peer {p_sym}: {e}")
            continue

    if not peer_meta_list:
        return {
            "available": False,
            "reason": "Could not analyze any peer fundamentals successfully",
            "peers": [], "matrix": {}, "cccRoceQuadrant": [], "relativeStrengths": []
        }

    _METRIC_NAMES = {
        "revenueGrowth1y": "1Y Revenue Growth",
        "revenueGrowth3y": "3Y Revenue Growth",
        "grossMarginPct": "Gross Margin",
        "operatingMarginPct": "Operating Margin",
        "netMarginPct": "Net Margin",
        "roe": "Return on Equity (ROE)",
        "roic": "Return on Invested Capital (ROIC)",
        "debtToEquityExLease": "Debt-to-Equity (ex-Lease)",
        "netDebtEbitdaExLease": "Net Debt / EBITDA",
        "interestCoverageExLease": "Interest Coverage",
        "currentRatio": "Current Ratio",
        "pe": "P/E Ratio",
        "evToEbitda": "EV / EBITDA",
        "pb": "P/B Ratio",
        "fcfYieldPct": "FCF Yield",
        "piotroskiScore": "Piotroski Score",
        "altmanZScore": "Altman Z-Score",
        "fiiDiiHoldingPct": "FII + DII Holding"
    }
    _LOWER_IS_BETTER = {"debtToEquityExLease", "netDebtEbitdaExLease", "pe", "evToEbitda", "pb"}

    matrix = {}
    target_ranks = {}

    for m_key in _METRIC_NAMES.keys():
        items = []
        for sym in peer_symbols:
            val = all_extracted.get(sym, {}).get(m_key)
            items.append({"symbol": sym, "value": val})
        
        valid_items = [it for it in items if it["value"] is not None]
        if m_key in _LOWER_IS_BETTER:
            valid_items.sort(key=lambda x: (x["value"], 0 if x["symbol"] == target_symbol else 1))
        else:
            valid_items.sort(key=lambda x: (-x["value"], 0 if x["symbol"] == target_symbol else 1))
        
        rank_map = {}
        for idx, it in enumerate(valid_items):
            rank_map[it["symbol"]] = idx + 1
            if it["symbol"] == target_symbol:
                target_ranks[m_key] = (idx + 1, len(valid_items))
        
        matrix_list = []
        for it in items:
            matrix_list.append({
                "symbol": it["symbol"],
                "value": it["value"],
                "rankAmongSet": rank_map.get(it["symbol"], None)
            })
        matrix[m_key] = matrix_list

    ccc_roce_list = []
    for sym in peer_symbols:
        res_obj = all_res_map.get(sym, {})
        ccc_val = None
        ccc_traj = res_obj.get("efficiency", {}).get("cccTrajectory", {})
        if isinstance(ccc_traj, dict):
            vals = ccc_traj.get("values", [])
            if isinstance(vals, list):
                for v in vals:
                    if v is not None:
                        ccc_val = _safe_float(v)
                        break
        if ccc_val is None:
            ccc_val = 0.0
        
        roce_val = all_extracted.get(sym, {}).get("roe") or all_extracted.get(sym, {}).get("roic") or 0.0
        returns_obj = res_obj.get("profitability", {}).get("returns", {})
        if isinstance(returns_obj, dict):
            r_list = returns_obj.get("roce", [])
            if isinstance(r_list, list):
                for r in r_list:
                    if r is not None:
                        roce_val = _safe_float(r)
                        break
            elif returns_obj.get("roce") is not None:
                roce_val = _safe_float(returns_obj.get("roce"))

        if roce_val >= 15.0:
            quad_label = "Quality Compounder" if ccc_val <= 60.0 else "Capital-Intensive Winner"
        else:
            quad_label = "Efficient but Marginal" if ccc_val <= 60.0 else "Value Trap/Avoid"

        sym_name = sym
        if sym == target_symbol:
            sym_name = target_info.get("longName") or target_info.get("shortName") or sym
        else:
            for pm in peer_meta_list:
                if pm["symbol"] == sym:
                    sym_name = pm["name"]
                    break

        ccc_roce_list.append({
            "symbol": sym,
            "name": sym_name,
            "ccc": ccc_val,
            "roce": roce_val,
            "quadrant": quad_label
        })

    relative_strengths = []
    top_ranks = []
    for m_key, (rnk, tot) in target_ranks.items():
        if tot >= 2:
            top_ranks.append((rnk, tot, _METRIC_NAMES[m_key]))
    
    top_ranks.sort(key=lambda x: (x[0], -x[1]))
    for rnk, tot, name in top_ranks:
        if rnk <= 2 and len(relative_strengths) < 3:
            relative_strengths.append(f"Rank {rnk} of {tot} on {name}")
    if not relative_strengths and top_ranks:
        for rnk, tot, name in top_ranks[:2]:
            relative_strengths.append(f"Rank {rnk} of {tot} on {name}")

    return {
        "available": True,
        "reason": None,
        "peers": peer_meta_list,
        "matrix": matrix,
        "cccRoceQuadrant": ccc_roce_list,
        "relativeStrengths": relative_strengths
    }


def analyze_fundamentals(symbol: str, include_peers: bool = True) -> Dict[str, Any]:
    """Public API - orchestrates the 10-pillar Fundamental & Forensic Equity Research Deck (Section 1.2 / Task 22)."""
    import datetime
    
    # 1. Fetch frames
    frames = {}
    try:
        frames = _annual_frames(symbol)
    except Exception as e:
        logger.warning(f"[_annual_frames] Failed for {symbol}: {e}")
        frames = {}

    info = frames.get("info", {}) if isinstance(frames, dict) else {}
    fys = frames.get("fiscal_year_ends", []) if isinstance(frames, dict) else []
    
    # Determine sector & bucket
    sector_info = {}
    try:
        sector_info = get_sector_bucket(symbol, frames)
    except Exception as e:
        logger.warning(f"[get_sector_bucket] Failed for {symbol}: {e}")
    sector_bucket = sector_info.get("bucket", "GENERAL_OTHER")
    raw_sector = sector_info.get("raw_sector", info.get("sector") or "General")
    matched_industry = sector_info.get("raw_industry", info.get("industry"))
    
    # 2. Gates (Holding Company, BFSI, Capital Raise, Ind AS 116)
    gates_res = {}
    try:
        fin_df = frames.get("financials", {}) if isinstance(frames, dict) else {}
        bs_df = frames.get("balance_sheet", {}) if isinstance(frames, dict) else {}
        is_hc = _is_holding_company(info, fin_df, bs_df)
        is_bfsi_flag = (sector_bucket in ["BFSI", "BFSI_BANKS", "BFSI_NBFC", "BFSI_INSURANCE", "BANKING_FINANCIAL_SERVICES"] or _is_bfsi(sector_bucket))
        num_yrs = len(fys) if fys else 5
        shares_list = [_val(bs_df, ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"], i) or _val(fin_df, ["Basic Average Shares", "Diluted Average Shares"], i) for i in range(num_yrs)]
        cap_raises = _capital_raise_years([sh or 0.0 for sh in shares_list], fys[:num_yrs])
        ind116_in_range = _ind_as_116_transition_in_range(fys)
        
        oi_pct = None
        inv_pct = None
        if isinstance(fin_df, dict) or hasattr(fin_df, "columns"):
            rev_0 = _val(fin_df, fc.REVENUE_ALIASES, 0) or 0.0
            oi_0 = _val(fin_df, fc.OTHER_INCOME_ALIASES, 0) or 0.0
            tot_0 = rev_0 + oi_0
            if tot_0 > 0: oi_pct = round((oi_0 / tot_0) * 100.0, 2)
        if isinstance(bs_df, dict) or hasattr(bs_df, "columns"):
            ta_0 = _val(bs_df, fc.TOTAL_ASSETS_ALIASES, 0) or 0.0
            inv_aliases = ["Investments And Advances", "Long Term Equity Investment", "Available For Sale Securities", "Investmentin Financial Assets", "Financial Assets Designatedas Fair Value Through Profitor Loss Total", "Financial Assets", "Investments", "Total Investments", "Short Term Investments", "Long Term Investments", "Other Non Current Assets"]
            inv_0 = _val(bs_df, inv_aliases, 0) or 0.0
            if ta_0 > 0: inv_pct = round((inv_0 / ta_0) * 100.0, 2)

        gates_res = {
            "isHoldingCompany": is_hc,
            "otherIncomeToTotalIncomePct": oi_pct,
            "investmentsToAssetsPct": inv_pct,
            "isBFSI": is_bfsi_flag,
            "matchedIndustryTag": matched_industry,
            "capitalRaiseYears": cap_raises,
            "indAS116TransitionInRange": ind116_in_range,
            "indAS116TransitionYear": "2020-03-31" if ind116_in_range else None
        }
    except Exception as e:
        logger.warning(f"[gates] Failed for {symbol}: {e}")
        gates_res = {"isHoldingCompany": False, "isBFSI": False, "capitalRaiseYears": [], "indAS116TransitionInRange": False}

    # 3. Pillar 1: Income Statement
    p1 = {"available": False, "reason": "Not calculated"}
    try:
        p1 = _pillar_income_statement(frames)
    except Exception as e:
        logger.warning(f"[_pillar_income_statement] Failed for {symbol}: {e}")
        p1 = {"available": False, "reason": str(e)}

    # 4. Pillar 2: Balance Sheet
    p2 = {"available": False, "reason": "Not calculated"}
    try:
        p2 = _pillar_balance_sheet(frames, sector_bucket)
    except Exception as e:
        logger.warning(f"[_pillar_balance_sheet] Failed for {symbol}: {e}")
        p2 = {"available": False, "reason": str(e)}

    # 5. Pillar 3: Cash Flow
    p3 = {"available": False, "reason": "Not calculated"}
    try:
        p3 = _pillar_cash_flow(frames, capital_raise_years=gates_res.get("capitalRaiseYears", []))
    except Exception as e:
        logger.warning(f"[_pillar_cash_flow] Failed for {symbol}: {e}")
        p3 = {"available": False, "reason": str(e)}

    # 6. Pillar 4: Profitability
    p4 = {"available": False, "reason": "Not calculated"}
    try:
        p4 = _pillar_profitability(frames, sector_bucket, is_holding_company=gates_res.get("isHoldingCompany", False))
    except Exception as e:
        logger.warning(f"[_pillar_profitability] Failed for {symbol}: {e}")
        p4 = {"available": False, "reason": str(e)}

    # 7. Pillar 5: Solvency
    p5 = {"available": False, "reason": "Not calculated"}
    try:
        wacc_ser = p4.get("returns", {}).get("wacc") if isinstance(p4.get("returns"), dict) else None
        p5 = _pillar_solvency(frames, sector_bucket, is_bfsi=gates_res.get("isBFSI", False), wacc_series=wacc_ser)
    except Exception as e:
        logger.warning(f"[_pillar_solvency] Failed for {symbol}: {e}")
        p5 = {"available": False, "reason": str(e)}

    # 8. Pillar 6: Efficiency
    p6 = {"available": False, "reason": "Not calculated"}
    try:
        p6 = _pillar_efficiency(frames, sector_bucket, is_holding_comp=gates_res.get("isHoldingCompany", False), is_bfsi=gates_res.get("isBFSI", False))
    except Exception as e:
        logger.warning(f"[_pillar_efficiency] Failed for {symbol}: {e}")
        p6 = {"available": False, "reason": str(e)}

    # 9. Forensics sub-calculators
    piotr = {"score": 0, "verdict": "N/A", "available": False}
    try:
        piotr = _piotroski_f_score(frames, p1, p2, p3, p6)
    except Exception as e:
        logger.warning(f"[_piotroski_f_score] Failed for {symbol}: {e}")

    beneish_res = {"available": False, "mScore": None, "riskBand": "Low/Clean"}
    try:
        beneish_res = _beneish_m_score(frames, p1, p2, p3, p6, is_bfsi=gates_res.get("isBFSI", False))
    except Exception as e:
        logger.warning(f"[_beneish_m_score] Failed for {symbol}: {e}")

    altman_res = {"available": False, "score": None, "zone": "Grey"}
    try:
        altman_res = _altman_z_router(frames, sector_bucket, is_bfsi=gates_res.get("isBFSI", False), p5=p5)
    except Exception as e:
        logger.warning(f"[_altman_z_router] Failed for {symbol}: {e}")

    sloan_res = {"available": False, "flagged": False}
    try:
        sloan_res = _sloan_accrual(frames, p1, p3, is_bfsi=gates_res.get("isBFSI", False), is_holding_comp=gates_res.get("isHoldingCompany", False))
    except Exception as e:
        logger.warning(f"[_sloan_accrual] Failed for {symbol}: {e}")

    # 10. Pillar 8: Valuation
    p8 = {"available": False, "reason": "Not calculated"}
    try:
        p8 = _pillar_valuation(frames, sector_bucket, wacc_series=p4.get("returns", {}).get("wacc") if isinstance(p4.get("returns"), dict) else None)
    except Exception as e:
        logger.warning(f"[_pillar_valuation] Failed for {symbol}: {e}")
        p8 = {"available": False, "reason": str(e)}

    # 11. Pillar 9: Growth
    p9 = {"available": False, "reason": "Not calculated"}
    try:
        p9 = _pillar_growth(frames, sector_bucket, p1=p1, p2=p2, p3=p3, p4=p4)
    except Exception as e:
        logger.warning(f"[_pillar_growth] Failed for {symbol}: {e}")
        p9 = {"available": False, "reason": str(e)}

    # 12. Red Flag Engine
    pillars_for_rfe = {
        "incomeStatement": p1,
        "balanceSheet": p2,
        "cashFlow": p3,
        "profitability": p4,
        "solvency": p5,
        "efficiency": p6,
        "sloanAccrual": sloan_res
    }
    rfe_res = {"available": False, "redFlags": [], "phase2Stubs": {}}
    try:
        rfe_res = _red_flag_engine(pillars_for_rfe, sector_bucket, beneish_res, altman_res, sloan_res, frames)
    except Exception as e:
        logger.warning(f"[_red_flag_engine] Failed for {symbol}: {e}")

    forensics_full = {
        "piotroski": piotr,
        "beneish": beneish_res,
        "altmanZ": altman_res,
        "sloanAccrual": sloan_res,
        "redFlags": rfe_res.get("redFlags", []),
        "phase2Stubs": rfe_res.get("phase2Stubs", {})
    }

    # 13. Overall Grade Weighting
    pillars_for_grade = {
        "forensics": forensics_full,
        "cashFlow": p3,
        "profitability": p4,
        "solvency": p5,
        "growth": p9,
        "efficiency": p6
    }
    grade_res = {}
    try:
        grade_res = _overall_grade(pillars_for_grade, forensics_dict=forensics_full)
    except Exception as e:
        logger.warning(f"[_overall_grade] Failed for {symbol}: {e}")
        grade_res = {"available": False, "overallGrade": 0.0, "letterGrade": "N/A", "weightingBreakdown": []}

    r_flags = rfe_res.get("redFlags", [])
    grade_res["redFlagCount"] = sum(1 for f in r_flags if f.get("triggered") and f.get("severity") in ["RED", "CRITICAL"])
    grade_res["suppressedFlagCount"] = sum(1 for f in r_flags if f.get("sectorOverrideApplied"))

    # 14. Peer Benchmarking (Pillar 10) - recursion guarded!
    peer_res = {"available": False, "reason": "include_peers=False (peer sub-call or disabled)"}
    if include_peers:
        try:
            peer_res = _pillar_peer_benchmarking(symbol, info, frames, p1, p2, p3, p4, p5, p6, p8, p9, forensics=forensics_full)
        except Exception as e:
            logger.warning(f"[_pillar_peer_benchmarking] Failed for {symbol}: {e}")
            peer_res = {"available": False, "reason": str(e)}

    # 15. Assemble Meta
    meta_obj = {
        "symbol": symbol,
        "companyName": info.get("longName") or info.get("shortName") or symbol,
        "yahooSector": raw_sector,
        "sectorBucket": sector_bucket,
        "fiscalYearEnds": fys[:5] if fys else [],
        "currencyUnit": "INR Crores" if symbol.endswith(".NS") or symbol.endswith(".BO") else (info.get("currency") or "INR Crores"),
        "dataAsOf": datetime.datetime.utcnow().isoformat() + "Z",
        "cacheAgeDays": 0,
        "isPeerCall": not include_peers
    }

    return {
        "meta": meta_obj,
        "gates": gates_res,
        "incomeStatement": p1,
        "balanceSheet": p2,
        "cashFlow": p3,
        "profitability": p4,
        "solvency": p5,
        "efficiency": p6,
        "forensics": forensics_full,
        "valuation": p8,
        "growth": p9,
        "peerBenchmark": peer_res,
        "overallGrade": grade_res
    }


if __name__ == "__main__":
    import time
    test_sym = "RELIANCE.NS"
    print(f"=== Testing _annual_frames for {test_sym} (First Run) ===")
    t0 = time.time()
    res1 = _annual_frames(test_sym)
    t1 = time.time()
    print(f"First run took: {t1 - t0:.2f}s")
    print(f"FY ends: {res1.get('fiscal_year_ends')}")

    print("\n=== Testing Task 7 Detectors (Synthetic Inputs) ===")
    syn_shares = [110.0, 100.0, 99.0, 98.0]  # 10% jump from index 1 (100) to index 0 (110)
    print("Capital raise indices (expect [0]):", _capital_raise_years(syn_shares))
    syn_fys_116 = ["2022-03-31", "2021-03-31", "2020-03-31"]  # includes 2020 and 2021
    print("Ind AS 116 in range (expect True):", _ind_as_116_transition_in_range(syn_fys_116))
    syn_fys_recent = ["2025-03-31", "2024-03-31", "2023-03-31", "2022-03-31"]
    print("Ind AS 116 in range recent (expect False):", _ind_as_116_transition_in_range(syn_fys_recent))
