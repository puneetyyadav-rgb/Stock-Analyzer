"""BFSI / Banking Fundamental Analysis engine.

Computes a banking-native fundamental scorecard for NSE/BSE-listed financial
entities (banks, NBFCs, insurance, fintech). The industrial 10-pillar engine in
fundamental_service.py suppresses its solvency/efficiency/forensic pillars for
BFSI because those models (Altman Z, Beneish M, Sloan accrual, working-capital
cycles) are mathematically invalid for lenders — money is their inventory, debt
is their raw material, and loans-given-out are an investing (cash-outflow)
activity. This module is the BFSI-native replacement mounted at that gate.

Data reality: GNPA/NNPA/PCR/CRAR/CASA/LCR/VNB/EV/Persistency/ALM are NOT in
yfinance (they live in quarterly BSE/NSE filings, RBI Pillar 3, and IRDAI
disclosures). Those are emitted as explicit Phase-2 stubs (available: False),
never omitted and never hallucinated. Everything computable comes from
balance_sheet / financials / cashflow / info via fundamental_service helpers.

Reuses fundamental_service._annual_frames / _val / _safe_divide / _to_crores /
get_sector_bucket so units (INR Crores), caching, and conventions match the
industrial deck exactly.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fundamental_service import (
    _annual_frames,
    _val,
    _safe_divide,
    _to_crores,
    get_sector_bucket,
)

logger = logging.getLogger(__name__)

try:
    from scrapers.database import get_latest_metrics
except ImportError:
    get_latest_metrics = None

# --------------------------------------------------------------------------
# yfinance field alias lists (banking-oriented). All extraction via _val().
# --------------------------------------------------------------------------
AL_INTEREST_INCOME = ["Total Revenue", "Interest Income", "Net Interest Income", "Operating Revenue"]
AL_NET_INTEREST_INCOME = ["Net Interest Income"]
AL_INTEREST_EXPENSE = ["Interest Expense", "Net Non Operating Interest Income Expense"]
AL_OTHER_INCOME = ["Other Income Expense", "Non Interest Income", "Total Other Finance Cost"]
AL_PROVISIONS = ["Credit Losses", "Provision For Doubtful Accounts", "Provision For Loan Losses"]
AL_OPEX = ["Operating Expense", "Total Operating Expenses", "Selling General And Administration"]
AL_NET_INCOME = ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operations"]
AL_PRETAX = ["Pretax Income", "Income Before Tax"]
AL_TAX = ["Tax Provision", "Income Tax Expense"]

AL_CASH = ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash And Short Term Investments"]
AL_ST_INV = ["Short Term Investments", "Available For Sale Securities"]
AL_LT_INV = ["Long Term Investments", "Investments And Advances"]
AL_NET_LOANS = ["Net Receivables", "Net Loans", "Accounts Receivable Net", "Gross Accounts Receivable"]
AL_ALLOWANCE = ["Allowance For Doubtful Accounts Receivable", "Provision For Credit Losses"]
AL_DEPOSITS = ["Total Deposits", "Payable", "Customer Deposits", "Other Current Liabilities"]
AL_BORROWINGS = ["Long Term Debt", "Short Long Term Debt", "Other Short Term Borrowings"]
AL_TOTAL_ASSETS = ["Total Assets"]
AL_TOTAL_LIAB = ["Total Liabilities Net Minority Interest", "Total Liabilities"]
AL_EQUITY = ["Common Stock Equity", "Stockholders Equity", "Total Equity Gross Minority Interest"]
AL_RETAINED = ["Retained Earnings"]
AL_SHARES = ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"]
AL_GOODWILL = ["Goodwill And Other Intangible Assets", "Goodwill", "Other Intangible Assets"]
AL_RECEIVABLES = ["Receivables", "Accounts Receivable", "Gross Accounts Receivable"]


def _pct(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
    """Safe ratio * 100 for percentage metrics."""
    r = _safe_divide(numer, denom)
    return round(r * 100.0, 2) if r is not None else None


def _growth(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    """YoY growth % ; None if either side missing or prev <= 0."""
    if cur is None or prev is None or prev == 0:
        return None
    try:
        return round(((float(cur) - float(prev)) / abs(float(prev))) * 100.0, 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def _series(df_dict, aliases, n=5) -> List[Optional[float]]:
    """Pull up to n most-recent-year values (crores) for an alias set."""
    return [_to_crores(_val(df_dict, aliases, i)) for i in range(n)]


def _stub(reason: str) -> Dict[str, Any]:
    return {"available": False, "reason": reason}


# --------------------------------------------------------------------------
# Sub-sector classifier (finer layer on top of get_sector_bucket's BFSI bucket)
# --------------------------------------------------------------------------
_PSU_BANK_KEYWORDS = [
    "state bank", "sbi", "punjab national", "pnb", "bank of baroda", "canara",
    "union bank", "indian bank", "central bank", "bank of india", "syndicate",
    "uco", "allahabad", "vijaya", "dena", "corporation bank", "andhra bank",
    "oriental bank", "obc",
]
_GOLD_NBFC = ["muthoot", "manappuram", "iifl", "rupeek"]


def _bfsi_subsector(info: Dict[str, Any], raw_sector: str, raw_industry: str) -> Dict[str, Any]:
    """Classify a BFSI entity into a finer sub-sector bucket.

    Returns {subSector, confidence, primaryKpis}.
    """
    name = str(info.get("longName") or info.get("shortName") or "").lower()
    ind = str(raw_industry or "").lower()
    sec = str(raw_sector or "").lower()
    desc = str(info.get("longBusinessSummary") or "").lower()
    hay = f"{name} {ind} {desc}"

    is_bank = "bank" in ind
    is_insurance = "insurance" in ind
    is_finance = ("finance" in ind) or ("credit services" in ind) or ("mortgage" in ind)

    # Insurance first (most distinct).
    if is_insurance:
        if "life" in hay or "lic" in name:
            return {"subSector": "INSURANCE_LIFE", "confidence": "high",
                    "primaryKpis": ["VNB", "VNB Margin", "Embedded Value", "Persistency 13M/61M", "Claim Settlement Ratio", "Solvency Ratio"]}
        return {"subSector": "INSURANCE_GENERAL", "confidence": "high",
                "primaryKpis": ["Combined Ratio", "Loss Ratio", "Expense Ratio", "Premium Growth", "Solvency Ratio", "Investment Yield"]}

    # Banks.
    if is_bank:
        if "small finance" in hay:
            return {"subSector": "SFB", "confidence": "high",
                    "primaryKpis": ["NIM", "GNPA", "PCR", "CRAR", "Customer Concentration", "Yield on Advances"]}
        if any(k in name for k in _PSU_BANK_KEYWORDS):
            return {"subSector": "PSU_BANK", "confidence": "high",
                    "primaryKpis": ["NIM", "GNPA", "NNPA", "PCR", "CRAR", "RoA", "RoE", "CASA", "Credit Cost"]}
        return {"subSector": "PRIVATE_BANK", "confidence": "high",
                "primaryKpis": ["NIM", "GNPA", "NNPA", "PCR", "CRAR", "RoA", "RoE", "CASA", "Cost-to-Income", "Credit Cost"]}

    # NBFCs.
    if is_finance:
        if any(k in name for k in _GOLD_NBFC) or "gold loan" in hay:
            return {"subSector": "NBFC_GOLD", "confidence": "medium",
                    "primaryKpis": ["Yield on AUM", "LTV", "Auction Rate", "Branch Density"]}
        if "housing" in hay or "mortgage" in hay or "home" in name:
            return {"subSector": "NBFC_HOUSING", "confidence": "medium",
                    "primaryKpis": ["Spread", "NIM", "GNPA", "PCR", "LTV", "Funding Mix", "ALM"]}
        if "micro" in hay or "microfinance" in hay or "vehicle" in hay or "auto loan" in hay:
            return {"subSector": "NBFC_MFI", "confidence": "medium",
                    "primaryKpis": ["Yield on AUM", "PAR 30/90", "GNPA", "Borrower Growth", "Geographic Concentration"]}
        return {"subSector": "NBFC_VEHICLE", "confidence": "low",
                "primaryKpis": ["Spread", "NIM", "GNPA", "PCR", "Funding Mix"]}

    # Fintech / asset-light capital markets & credit services.
    if "capital markets" in ind or "credit services" in ind or "asset management" in ind:
        return {"subSector": "FINTECH", "confidence": "low",
                "primaryKpis": ["Revenue Growth", "Take Rate", "GMV", "Operating Leverage"]}

    return {"subSector": "PRIVATE_BANK", "confidence": "low",
            "primaryKpis": ["NIM", "GNPA", "RoA", "RoE"]}

# --------------------------------------------------------------------------
# Shared extraction bundle used across pillars
# --------------------------------------------------------------------------
def _extract(frames):
    """Pull the raw crores series every pillar needs, in one place."""
    bs = frames.get("balance_sheet", {}) if isinstance(frames, dict) else {}
    fin = frames.get("financials", {}) if isinstance(frames, dict) else {}
    info = frames.get("info", {}) if isinstance(frames, dict) else {}
    n = 5
    e = {
        "bs": bs, "fin": fin, "info": info,
        "fy": (frames.get("fiscal_year_ends", []) if isinstance(frames, dict) else [])[:n],
        "interest_income": _series(fin, AL_INTEREST_INCOME, n),
        "nii": _series(fin, AL_NET_INTEREST_INCOME, n),
        "interest_expense": _series(fin, AL_INTEREST_EXPENSE, n),
        "other_income": _series(fin, AL_OTHER_INCOME, n),
        "provisions": _series(fin, AL_PROVISIONS, n),
        "opex": _series(fin, AL_OPEX, n),
        "net_income": _series(fin, AL_NET_INCOME, n),
        "pretax": _series(fin, AL_PRETAX, n),
        "tax": _series(fin, AL_TAX, n),
        "cash": _series(bs, AL_CASH, n),
        "st_inv": _series(bs, AL_ST_INV, n),
        "lt_inv": _series(bs, AL_LT_INV, n),
        "net_loans": _series(bs, AL_NET_LOANS, n),
        "allowance": _series(bs, AL_ALLOWANCE, n),
        "deposits": _series(bs, AL_DEPOSITS, n),
        "borrowings": _series(bs, AL_BORROWINGS, n),
        "total_assets": _series(bs, AL_TOTAL_ASSETS, n),
        "total_liab": _series(bs, AL_TOTAL_LIAB, n),
        "equity": _series(bs, AL_EQUITY, n),
        "retained": _series(bs, AL_RETAINED, n),
        "shares": _series(bs, AL_SHARES, n),
        "goodwill": _series(bs, AL_GOODWILL, n),
    }
    # NII fallback: Interest Income - Interest Expense when not directly present.
    e["nii_computed"] = []
    for i in range(n):
        nii = e["nii"][i]
        if nii is None:
            ii, ie = e["interest_income"][i], e["interest_expense"][i]
            if ii is not None and ie is not None:
                nii = round(ii - abs(ie), 2)
        e["nii_computed"].append(nii)
    # Earning assets proxy = loans + investments.
    e["earning_assets"] = []
    for i in range(n):
        parts = [x for x in (e["net_loans"][i], e["st_inv"][i], e["lt_inv"][i]) if x is not None]
        e["earning_assets"].append(round(sum(parts), 2) if parts else None)
    return e


def _avg(series, i):
    """Average of consecutive years (i and i+1) for RoA/RoE/NIM denominators."""
    if i + 1 < len(series) and series[i] is not None and series[i + 1] is not None:
        return (series[i] + series[i + 1]) / 2.0
    return series[i]


def _pillar_asset_quality(e):
    ta0 = e["total_assets"][0]
    loans0 = e["net_loans"][0]
    prov = e["provisions"]
    allow = e["allowance"]

    provision_series = [p for p in prov if p is not None]
    prov_growth_1y = _growth(prov[0], prov[1]) if len(prov) > 1 else None
    loan_growth_1y = _growth(loans0, e["net_loans"][1]) if len(e["net_loans"]) > 1 else None

    proxy_flag = None
    if prov_growth_1y is not None and loan_growth_1y is not None:
        if prov_growth_1y > (loan_growth_1y + 25):
            proxy_flag = ("Provisions growing %.1f%% while loan book grows %.1f%% — provisioning "
                          "outpacing asset growth signals deteriorating asset quality." % (prov_growth_1y, loan_growth_1y))

    phase2 = {
        "grossNPA_pct": _stub("GNPA data is a quarterly BSE/NSE filing disclosure — requires XBRL financial results scrape. Phase 2 data source."),
        "netNPA_pct": _stub("NNPA data is a quarterly BSE/NSE filing disclosure. Phase 2."),
        "provisionCoverageRatio_pct": _stub("PCR requires quarterly disclosure. Phase 2."),
        "creditCost_pct": _stub("Credit cost requires quarterly loan book data. Phase 2."),
        "slippage_pct": _stub("Slippage requires quarterly NPA movement disclosures. Phase 2."),
        "restructuredBook_pct": _stub("Restructured book requires quarterly filing. Phase 2."),
        "securityCoverage_pct": _stub("Collateral and security coverage requires annual report notes. Phase 2."),
    }

    return {
        "available": ta0 is not None,
        "netLoansToTotalAssets_pct": _pct(loans0, ta0),
        "provisionSeries_cr": provision_series[:5],
        "provisionGrowth1Y_pct": prov_growth_1y,
        "allowanceSeries_cr": [a for a in allow if a is not None][:5],
        "assetQualityProxyFlag": proxy_flag,
        "note": "Direct GNPA/NNPA/PCR are regulatory quarterly disclosures not present in yfinance; only balance-sheet proxies are computable here.",
        "phase2Stubs": phase2,
        "subScore": None,
    }


def _pillar_nim_profitability(e):
    nii = e["nii_computed"]
    ni = e["net_income"]
    ta = e["total_assets"]
    eq = e["equity"]
    earn = e["earning_assets"]
    oi = e["other_income"]
    opex = e["opex"]

    nii0 = nii[0]
    nii_growth_1y = _growth(nii[0], nii[1]) if len(nii) > 1 else None

    nim_proxy = None
    avg_earn = _avg(earn, 0)
    if nii0 is not None and avg_earn:
        r = _safe_divide(nii0, avg_earn)
        nim_proxy = round(r * 100.0, 2) if r is not None else None

    spread_ratio = None
    if e["interest_income"][0] is not None and e["interest_expense"][0] is not None:
        r = _safe_divide(e["interest_income"][0], abs(e["interest_expense"][0]))
        spread_ratio = round(r, 3) if r is not None else None

    fee_share = None
    if oi[0] is not None and nii0 is not None and (nii0 + oi[0]) != 0:
        fee_share = _pct(oi[0], nii0 + oi[0])

    roa = None
    avg_ta = _avg(ta, 0)
    if ni[0] is not None and avg_ta:
        r = _safe_divide(ni[0], avg_ta)
        roa = round(r * 100.0, 2) if r is not None else None

    roe = None
    avg_eq = _avg(eq, 0)
    if ni[0] is not None and avg_eq:
        r = _safe_divide(ni[0], avg_eq)
        roe = round(r * 100.0, 2) if r is not None else None

    cost_to_income = None
    if nii0 is not None and opex[0] is not None:
        net_rev = nii0 + (oi[0] or 0.0)
        if net_rev:
            cost_to_income = _pct(opex[0], net_rev)

    ppop = None
    if nii0 is not None and opex[0] is not None:
        ppop = round((nii0 + (oi[0] or 0.0)) - opex[0], 2)
    ppop_margin = _pct(ppop, ta[0]) if (ppop is not None and ta[0]) else None

    def roa_pts(r):
        if r is None: return None
        if r >= 1.5: return 100
        if r >= 1.0: return 75
        if r >= 0.5: return 50
        return 20

    def roe_pts(r):
        if r is None: return None
        if r >= 15: return 100
        if r >= 12: return 70
        if r >= 10: return 50
        return 20

    pts = [p for p in (roa_pts(roa), roe_pts(roe)) if p is not None]
    sub = round(sum(pts) / len(pts), 1) if pts else None

    return {
        "available": nii0 is not None or roa is not None,
        "nii_cr": nii0,
        "niiSeries_cr": [x for x in nii if x is not None][:5],
        "niiGrowth1Y_pct": nii_growth_1y,
        "nimProxy_pct": nim_proxy,
        "spreadRatio": spread_ratio,
        "feeIncomeShare_pct": fee_share,
        "roa_pct": roa,
        "roe_pct": roe,
        "costToIncome_pct": cost_to_income,
        "ppop_cr": ppop,
        "ppopMargin_pct": ppop_margin,
        "note": "NIM/RoA/PPOP are annual yfinance proxies, not regulatory disclosures; they indicate trend, not basis-point accuracy.",
        "phase2Stubs": {"roRWA_pct": _stub("Return on Risk-Weighted Assets requires RWA data from RBI Pillar 3 disclosures. Phase 2.")},
        "subScore": sub,
    }


def _pillar_deposit_franchise(e):
    dep = e["deposits"]
    borr = e["borrowings"]
    liab = e["total_liab"]
    ie = e["interest_expense"]

    dep0 = dep[0]
    dep_growth_1y = _growth(dep[0], dep[1]) if len(dep) > 1 else None
    dep_to_liab = _pct(dep0, liab[0]) if (dep0 is not None and liab[0]) else None

    cost_of_deposits = None
    avg_dep = _avg(dep, 0)
    if ie[0] is not None and avg_dep:
        cost_of_deposits = _pct(abs(ie[0]), avg_dep)

    borrow_to_dep = None
    if borr[0] is not None and dep0:
        borrow_to_dep = _pct(borr[0], dep0)

    sub = None
    if dep_to_liab is not None:
        if dep_to_liab >= 80: sub = 90
        elif dep_to_liab >= 65: sub = 70
        elif dep_to_liab >= 50: sub = 50
        else: sub = 30
        if borrow_to_dep is not None and borrow_to_dep > 40:
            sub = max(20, sub - 20)

    return {
        "available": dep0 is not None,
        "totalDeposits_cr": dep0,
        "depositGrowth1Y_pct": dep_growth_1y,
        "depositsToLiabilities_pct": dep_to_liab,
        "costOfDepositsProxy_pct": cost_of_deposits,
        "borrowingsToDeposits_pct": borrow_to_dep,
        "note": "CASA breakdown is a quarterly disclosure; deposit/cost-of-funds here are balance-sheet proxies.",
        "phase2Stubs": {"casaRatio_pct": _stub("CASA breakdown requires quarterly BSE/NSE financial results disclosures. Phase 2.")},
        "subScore": sub,
    }


def _pillar_capital_adequacy(e):
    eq = e["equity"]
    ta = e["total_assets"]
    sh = e["shares"]
    gw = e["goodwill"]

    eq_to_assets = _pct(eq[0], ta[0]) if (eq[0] is not None and ta[0]) else None

    def _bvps_at(i):
        if eq[i] is not None and sh[i]:
            r = _safe_divide(eq[i], sh[i])
            return r * 1e7 if r is not None else None
        return None

    bvps = _bvps_at(0)
    tbvps = None
    if eq[0] is not None and sh[0]:
        tangible = eq[0] - (gw[0] or 0.0)
        r = _safe_divide(tangible, sh[0])
        tbvps = round(r * 1e7, 2) if r is not None else None

    bvps_growth_1y = _growth(_bvps_at(0), _bvps_at(1)) if len(eq) > 1 else None

    sub = None
    if eq_to_assets is not None:
        if eq_to_assets >= 7: sub = 95
        elif eq_to_assets >= 5: sub = 70
        elif eq_to_assets >= 3: sub = 45
        else: sub = 20

    return {
        "available": eq_to_assets is not None,
        "equityToTotalAssets_pct": eq_to_assets,
        "bvps_inr": bvps,
        "tbvps_inr": tbvps,
        "bvpsGrowth1Y_pct": bvps_growth_1y,
        "note": "CRAR/Tier1/CET1/Leverage are RBI Pillar 3 regulatory disclosures; equity/assets is a simple leverage proxy.",
        "phase2Stubs": {
            "CRAR_pct": _stub("CRAR requires RBI Pillar 3 quarterly disclosures. Regulatory minimum 10.875% (incl. CCB). Phase 2."),
            "Tier1Capital_pct": _stub("Tier 1 Capital Ratio requires Pillar 3 disclosures. Phase 2."),
            "CET1_pct": _stub("Common Equity Tier 1 ratio requires Pillar 3 disclosures. Phase 2."),
            "leverageRatio_pct": _stub("Basel III Leverage Ratio requires RBI Pillar 3 disclosure. Phase 2."),
        },
        "subScore": sub,
    }


def _pillar_liquidity(e):
    cash = e["cash"]
    st = e["st_inv"]
    lt = e["lt_inv"]
    ta = e["total_assets"]
    loans = e["net_loans"]
    dep = e["deposits"]

    cash_to_assets = _pct(cash[0], ta[0]) if (cash[0] is not None and ta[0]) else None

    inv0 = None
    inv_parts = [x for x in (st[0], lt[0]) if x is not None]
    if inv_parts:
        inv0 = round(sum(inv_parts), 2)
    inv_to_assets = _pct(inv0, ta[0]) if (inv0 is not None and ta[0]) else None

    ldr = _pct(loans[0], dep[0]) if (loans[0] is not None and dep[0]) else None

    scored = []
    if cash_to_assets is not None:
        scored.append(90 if cash_to_assets >= 5 else 70 if cash_to_assets >= 2 else 35)
    if ldr is not None:
        scored.append(90 if ldr < 75 else 70 if ldr <= 90 else 35)
    sub = round(sum(scored) / len(scored), 1) if scored else None

    return {
        "available": cash_to_assets is not None or ldr is not None,
        "cashToTotalAssets_pct": cash_to_assets,
        "investmentsToTotalAssets_pct": inv_to_assets,
        "loanToDepositRatio_pct": ldr,
        "note": "LCR/NSFR/ALM are RBI regulatory disclosures; cash/investment/LDR here are balance-sheet liquidity proxies.",
        "phase2Stubs": {
            "LCR_pct": _stub("Liquidity Coverage Ratio requires RBI regulatory disclosure (min 100%). Phase 2."),
            "NSFR_pct": _stub("Net Stable Funding Ratio requires RBI Pillar 3. Phase 2."),
            "ALM_mismatch": _stub("Asset-Liability Mismatch requires Annual Report ALM duration disclosures. Phase 2."),
        },
        "subScore": sub,
    }


def _pillar_loan_growth(e):
    loans = e["net_loans"]
    ta = e["total_assets"]

    loan_series = [x for x in loans if x is not None][:5]
    growth_1y = _growth(loans[0], loans[1]) if len(loans) > 1 else None

    cagr_3y = None
    if len(loan_series) >= 4 and loan_series[3] and loan_series[0] and loan_series[3] > 0:
        try:
            cagr_3y = round((((loan_series[0] / loan_series[3]) ** (1.0 / 3.0)) - 1.0) * 100.0, 2)
        except (ZeroDivisionError, ValueError):
            cagr_3y = None

    earning_to_total = None
    if e["earning_assets"][0] is not None and ta[0]:
        earning_to_total = _pct(e["earning_assets"][0], ta[0])

    sub = None
    if growth_1y is not None:
        if 8 <= growth_1y <= 25: sub = 90
        elif 0 <= growth_1y < 8 or 25 < growth_1y <= 35: sub = 60
        elif growth_1y > 35: sub = 40
        else: sub = 25

    return {
        "available": growth_1y is not None,
        "loanBookSeries_cr": loan_series,
        "loanBookGrowth1Y_pct": growth_1y,
        "loanBookCAGR3Y_pct": cagr_3y,
        "earningAssetsToTotal_pct": earning_to_total,
        "note": "Segment (retail/corporate/SME) and geographic split require quarterly investor presentations. Phase 2.",
        "phase2Stubs": {
            "segmentSplit": _stub("Segment-level loan book breakdown requires quarterly investor presentations. Phase 2."),
            "geographicConcentration": _stub("Branch-level geography requires RBI quarterly filings. Phase 2."),
        },
        "subScore": sub,
    }


def _pillar_insurance_override(e, sub_sector):
    ni = e["net_income"]
    eq = e["equity"]
    roe = None
    avg_eq = _avg(eq, 0)
    if ni[0] is not None and avg_eq:
        r = _safe_divide(ni[0], avg_eq)
        roe = round(r * 100.0, 2) if r is not None else None

    common_stubs = {
        "solvencyRatio_pct": _stub("Solvency Ratio is an IRDAI regulatory disclosure (minimum 150%). Phase 2."),
    }
    if sub_sector == "INSURANCE_LIFE":
        common_stubs.update({
            "vnb_cr": _stub("Value of New Business requires the insurer actuarial disclosures. Phase 2."),
            "vnbMargin_pct": _stub("VNB Margin requires actuarial disclosures. Phase 2."),
            "embeddedValue_cr": _stub("Embedded Value requires actuarial disclosures. Phase 2."),
            "persistency13M_pct": _stub("Persistency rates require IRDAI/company disclosures. Phase 2."),
            "persistency61M_pct": _stub("Persistency rates require IRDAI/company disclosures. Phase 2."),
            "claimSettlementRatio_pct": _stub("Claim Settlement Ratio requires IRDAI data. Phase 2."),
        })
    else:
        common_stubs.update({
            "combinedRatio_pct": _stub("Combined Ratio (Loss + Expense) requires premium and claims disclosures. Phase 2."),
            "lossRatio_pct": _stub("Loss Ratio requires Net Incurred Claims / Net Earned Premiums disclosures. Phase 2."),
            "expenseRatio_pct": _stub("Expense Ratio requires underwriting expense disclosures. Phase 2."),
            "premiumGrowth_pct": _stub("Gross Written Premium growth requires insurance disclosures. Phase 2."),
        })

    return {
        "available": True,
        "isInsuranceOverride": True,
        "roe_pct": roe,
        "note": "Insurance entities use actuarial/regulatory KPIs (VNB, EV, persistency, combined ratio, solvency) not present in yfinance; these are Phase-2 stubs. Banking Pillars 1-4 do not apply.",
        "phase2Stubs": common_stubs,
        "subScore": None,
    }


# --------------------------------------------------------------------------
# PILLAR 8: BFSI Valuation (excluded from grade by design)
# --------------------------------------------------------------------------
def _pillar_bfsi_valuation(e):
    info = e["info"]
    mc = info.get("marketCap")
    eq0 = e["equity"][0]
    nii0 = e["nii_computed"][0]
    ppop = None
    if nii0 is not None and e["opex"][0] is not None:
        ppop = (nii0 + (e["other_income"][0] or 0.0)) - e["opex"][0]

    mc_cr = _to_crores(mc) if mc is not None else None

    pb = None
    if mc is not None and eq0:
        r = _safe_divide(mc_cr, eq0)
        pb = round(r, 2) if r is not None else None
    pe = info.get("trailingPE")

    p_ppop = None
    if mc_cr is not None and ppop:
        r = _safe_divide(mc_cr, ppop)
        p_ppop = round(r, 2) if r is not None else None

    p_nii = None
    if mc_cr is not None and nii0:
        r = _safe_divide(mc_cr, nii0)
        p_nii = round(r, 2) if r is not None else None

    # Justified P/B = RoE / CoE x (1 - g/RoE). CoE proxy 13%, g proxy 5%.
    roe = None
    avg_eq = _avg(e["equity"], 0)
    if e["net_income"][0] is not None and avg_eq:
        r = _safe_divide(e["net_income"][0], avg_eq)
        roe = round(r * 100.0, 2) if r is not None else None
    justified_pb = None
    if roe is not None and roe > 0:
        coe, g = 13.0, 5.0
        justified_pb = round((roe / coe) * (1.0 - (g / roe)), 2)

    return {
        "available": pb is not None or pe is not None,
        "pbRatio": pb,
        "peRatio": pe,
        "pToPPOP": p_ppop,
        "pToNII": p_nii,
        "justifiedPB": justified_pb,
        "note": "P/B is the primary banking multiple; P/B < 1 often prices hidden NPAs. Valuation is excluded from the fundamental grade by design.",
        "phase2Stubs": {
            "pToABV": _stub("Adjusted Book Value (net of uncovered GNPA) requires GNPA and PCR data. Phase 2."),
            "evToAUM": _stub("AUM data requires quarterly investor disclosures. Phase 2."),
            "vnbToEV": _stub("VNB and Embedded Value require actuarial disclosures. Phase 2."),
        },
        "subScore": None,
    }


# --------------------------------------------------------------------------
# PILLAR 9: Peer Benchmarking (recursion-guarded)
# --------------------------------------------------------------------------
# Static same-sub-sector peer universes (PSU vs PSU, private vs private, etc.)
_PEER_MAP = {
    "PSU_BANK": ["SBIN.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS"],
    "PRIVATE_BANK": ["HDFCBANK.NS", "ICICIBANK.NS", "AXISBANK.NS", "KOTAKBANK.NS", "INDUSINDBK.NS"],
    "SFB": ["AUBANK.NS", "UJJIVANSFB.NS", "EQUITASBNK.NS"],
    "NBFC_HOUSING": ["HDFCLTD.NS", "LICHSGFIN.NS", "PNBHOUSING.NS", "AAVAS.NS"],
    "NBFC_GOLD": ["MUTHOOTFIN.NS", "MANAPPURAM.NS", "IIFL.NS"],
    "NBFC_MFI": ["BAJFINANCE.NS", "CHOLAFIN.NS", "M&MFIN.NS", "SHRIRAMFIN.NS"],
    "NBFC_VEHICLE": ["BAJFINANCE.NS", "CHOLAFIN.NS", "M&MFIN.NS", "SHRIRAMFIN.NS"],
    "INSURANCE_LIFE": ["SBILIFE.NS", "HDFCLIFE.NS", "ICICIPRULI.NS", "LICI.NS"],
    "INSURANCE_GENERAL": ["ICICIGI.NS", "BAJAJFINSV.NS", "STARHEALTH.NS", "NIACL.NS"],
    "FINTECH": ["PAYTM.NS", "POLICYBZR.NS", "ANGELONE.NS", "CDSL.NS"],
}

# 14-metric peer matrix columns (label, extractor key, higher_is_better)
_PEER_METRICS = [
    ("NII Growth 1Y", "niiGrowth1Y_pct", True),
    ("Revenue Growth 1Y", "revGrowth1Y_pct", True),
    ("RoA %", "roa_pct", True),
    ("RoE %", "roe_pct", True),
    ("NIM proxy %", "nimProxy_pct", True),
    ("Cost-to-Income %", "costToIncome_pct", False),
    ("Equity/Assets %", "equityToTotalAssets_pct", True),
    ("Loan Growth 1Y", "loanBookGrowth1Y_pct", True),
    ("BVPS", "bvps_inr", True),
    ("P/B", "pbRatio", None),
    ("P/E", "peRatio", None),
    ("Loan-to-Deposit %", "loanToDepositRatio_pct", None),
    ("Liquidity proxy %", "cashToTotalAssets_pct", True),
    ("Provision Growth", "provisionGrowth1Y_pct", False),
]


def _peer_row(symbol):
    """Compute the flat metric dict for one peer (recursion-guarded, no nested peers)."""
    frames = _annual_frames(symbol)
    e = _extract(frames)
    aq = _pillar_asset_quality(e)
    prof = _pillar_nim_profitability(e)
    cap = _pillar_capital_adequacy(e)
    liq = _pillar_liquidity(e)
    grow = _pillar_loan_growth(e)
    val = _pillar_bfsi_valuation(e)
    info = e["info"]
    # Revenue (interest income) growth.
    rev_growth = _growth(e["interest_income"][0], e["interest_income"][1]) if len(e["interest_income"]) > 1 else None
    return {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "niiGrowth1Y_pct": prof.get("niiGrowth1Y_pct"),
        "revGrowth1Y_pct": rev_growth,
        "roa_pct": prof.get("roa_pct"),
        "roe_pct": prof.get("roe_pct"),
        "nimProxy_pct": prof.get("nimProxy_pct"),
        "costToIncome_pct": prof.get("costToIncome_pct"),
        "equityToTotalAssets_pct": cap.get("equityToTotalAssets_pct"),
        "loanBookGrowth1Y_pct": grow.get("loanBookGrowth1Y_pct"),
        "bvps_inr": cap.get("bvps_inr"),
        "pbRatio": val.get("pbRatio"),
        "peRatio": val.get("peRatio"),
        "loanToDepositRatio_pct": liq.get("loanToDepositRatio_pct"),
        "cashToTotalAssets_pct": liq.get("cashToTotalAssets_pct"),
        "provisionGrowth1Y_pct": aq.get("provisionGrowth1Y_pct"),
    }


def _pillar_bfsi_peers(symbol, sub_sector):
    universe = list(_PEER_MAP.get(sub_sector, _PEER_MAP["PRIVATE_BANK"]))
    # Ensure the target symbol leads its own row.
    ordered = [symbol] + [s for s in universe if s != symbol]
    ordered = ordered[:6]

    rows = []
    for s in ordered:
        try:
            rows.append(_peer_row(s))
        except Exception as exc:
            logger.warning("peer row failed for %s: %s", s, exc)
    if not rows:
        return {"available": False, "reason": "no peer data"}

    # Rank each metric column across rows.
    matrix_cols = []
    for label, key, higher_better in _PEER_METRICS:
        vals = [(i, r.get(key)) for i, r in enumerate(rows) if r.get(key) is not None]
        ranks = {}
        if higher_better is not None and vals:
            sorted_idx = sorted(vals, key=lambda t: t[1], reverse=higher_better)
            for rank, (i, _) in enumerate(sorted_idx, start=1):
                ranks[i] = rank
        matrix_cols.append({"label": label, "key": key, "higherIsBetter": higher_better, "ranks": ranks})

    # NIM vs RoA quadrant points.
    quadrant = [
        {"symbol": r["symbol"], "name": r["name"], "nim": r.get("nimProxy_pct"), "roa": r.get("roa_pct")}
        for r in rows if r.get("nimProxy_pct") is not None and r.get("roa_pct") is not None
    ]

    return {
        "available": True,
        "subSector": sub_sector,
        "rows": rows,
        "columns": matrix_cols,
        "nimRoaQuadrant": quadrant,
        "note": "Peers are same-sub-sector only (PSU vs PSU, private vs private). Ranks computed across available peers.",
    }


# --------------------------------------------------------------------------
# PILLAR 7: 16 banking red flags
# --------------------------------------------------------------------------
def _bfsi_red_flags(e, prof, cap, liq, grow, val):
    flags = []

    def add(fid, name, severity, triggered, alert, available=True):
        flags.append({"id": fid, "name": name, "severity": severity,
                      "triggered": bool(triggered) if available else False,
                      "available": available, "alert": alert})

    nii = e["nii_computed"]
    loans = e["net_loans"]
    prov = e["provisions"]
    ii = e["interest_income"]
    ie = e["interest_expense"]
    oi = e["other_income"]
    opex = e["opex"]
    ta = e["total_assets"]
    eq = e["equity"]
    sh = e["shares"]
    ret = e["retained"]
    borr = e["borrowings"]
    dep = e["deposits"]

    roe = prof.get("roe_pct")
    roa = prof.get("roa_pct")
    nim_proxy = prof.get("nimProxy_pct")
    pb = val.get("pbRatio")

    # 1 NIM compression spiral: NII growth < loan growth for 3 years.
    yrs = 0
    for i in range(3):
        ng = _growth(nii[i], nii[i + 1]) if i + 1 < len(nii) else None
        lg = _growth(loans[i], loans[i + 1]) if i + 1 < len(loans) else None
        if ng is not None and lg is not None and ng < lg:
            yrs += 1
    add("nim_compression", "NIM Compression Spiral", "WARNING", yrs >= 3,
        "⚠️ Net interest margin is being eroded: loan book growing faster than NII for 3 years. Cost of funds rising faster than asset yields. Likely CASA loss or pricing pressure.",
        available=all(nii[i] is not None for i in range(4)) and all(loans[i] is not None for i in range(4)))

    # 2 Provision surge.
    pg = _growth(prov[0], prov[1]) if len(prov) > 1 else None
    add("provision_surge", "Provision Surge (Stress Event)", "SEVERE", (pg is not None and pg > 50),
        ("🔴 SEVERE: Provisions surged %.1f%% this year. A significant NPA recognition event is likely underway or reserves are being built for an anticipated bad loan cycle." % pg) if pg is not None else "",
        available=pg is not None)

    # 3 RoE below cost of equity for 2+ years.
    roe_series = []
    for i in range(2):
        avg_eq = _avg(eq, i)
        if e["net_income"][i] is not None and avg_eq:
            r = _safe_divide(e["net_income"][i], avg_eq)
            roe_series.append(round(r * 100.0, 2) if r is not None else None)
        else:
            roe_series.append(None)
    low_roe_yrs = sum(1 for r in roe_series if r is not None and r < 10)
    add("roe_below_coe", "Profitability Below Cost of Equity", "WARNING", low_roe_yrs >= 2,
        ("⚠️ Return on Equity of %.1f%% is below the estimated cost of equity (~12-14%% for Indian banks). This bank is destroying shareholder value." % (roe or 0.0)),
        available=roe is not None)

    # 4 Book value erosion.
    def _bvps(i):
        if eq[i] is not None and sh[i]:
            r = _safe_divide(eq[i], sh[i])
            return r * 1e7 if r is not None else None
        return None
    b0, b1 = _bvps(0), _bvps(1)
    add("bvps_erosion", "Book Value Erosion", "SEVERE", (b0 is not None and b1 is not None and b0 < b1),
        ("🔴 Book value per share declined from ₹%.2f to ₹%.2f. The bank absorbed losses or provisions exceeding its earnings. Asset quality stress likely." % (b1 or 0.0, b0 or 0.0)),
        available=(b0 is not None and b1 is not None))

    # 5 Leverage build-up without capital support.
    tag = _growth(ta[0], ta[1]) if len(ta) > 1 else None
    eqg = _growth(eq[0], eq[1]) if len(eq) > 1 else None
    add("leverage_buildup", "Leverage Build-Up Without Capital", "WARNING",
        (tag is not None and eqg is not None and tag > 20 and eqg < 5),
        ("⚠️ Total assets expanded %.1f%% while equity grew only %.1f%%. Leveraging up without commensurate capital; capital adequacy may be thinning." % (tag or 0.0, eqg or 0.0)),
        available=(tag is not None and eqg is not None))

    # 6 Funding mix fragility.
    bg = _growth(borr[0], borr[1]) if len(borr) > 1 else None
    dg = _growth(dep[0], dep[1]) if len(dep) > 1 else None
    add("funding_fragility", "Funding Mix Fragility", "WARNING",
        (bg is not None and dg is not None and bg > 25 and dg < 10),
        ("⚠️ Increasingly reliant on short-term market borrowings (+%.1f%%) vs sticky deposits (+%.1f%%). Funding fragility and ALM risk." % (bg or 0.0, dg or 0.0)),
        available=(bg is not None and dg is not None))

    # 7 Sustained thin spread.
    spread_declining = 0
    for i in range(3):
        if i + 1 < len(ii) and ii[i] is not None and ie[i] is not None and ii[i + 1] is not None and ie[i + 1] is not None:
            r0 = _safe_divide(ii[i], abs(ie[i]))
            r1 = _safe_divide(ii[i + 1], abs(ie[i + 1]))
            if r0 is not None and r1 is not None and r0 < r1:
                spread_declining += 1
    add("thin_spread", "Sustained Thin Spread", "WARNING", spread_declining >= 3,
        ("⚠️ Interest spread is narrowing for %d consecutive years. Rising cost of liabilities or repricing pressure is compressing the core revenue engine." % spread_declining),
        available=all(ii[i] is not None and ie[i] is not None for i in range(4)))

    # 8 Equity dilution without RoE recovery.
    sg = _growth(sh[0], sh[1]) if len(sh) > 1 else None
    add("dilution_low_roe", "Equity Dilution Without RoE Recovery", "WARNING",
        (sg is not None and sg > 5 and roe is not None and roe < 10),
        ("⚠️ Raised capital (shares +%.1f%%) while RoE is only %.1f%% — diluting shareholders into a low-return business." % (sg or 0.0, roe or 0.0)),
        available=(sg is not None and roe is not None))

    # 9 Investment book explosion.
    inv0_parts = [x for x in (e["st_inv"][0], e["lt_inv"][0]) if x is not None]
    inv1_parts = [x for x in (e["st_inv"][1], e["lt_inv"][1]) if x is not None] if len(e["st_inv"]) > 1 else []
    inv_shift = None
    lg_slow = None
    if inv0_parts and ta[0] and inv1_parts and len(ta) > 1 and ta[1]:
        inv_pct0 = (sum(inv0_parts) / ta[0]) * 100.0
        inv_pct1 = (sum(inv1_parts) / ta[1]) * 100.0
        inv_shift = inv_pct0 - inv_pct1
        lg_slow = grow.get("loanBookGrowth1Y_pct")
    add("investment_explosion", "Investment Book Explosion (Risk Aversion)", "WARNING",
        (inv_shift is not None and inv_shift > 10),
        ("⚠️ Shifted aggressively into investments (+%.1f pp of assets) as loan growth slowed. Signals inability to find quality borrowers, risk aversion, or deployment constraint." % (inv_shift or 0.0)),
        available=(inv_shift is not None))

    # 10 Interest income-expense inversion.
    inv_ratio = None
    if ii[0] is not None and ie[0] is not None and ii[0] != 0:
        inv_ratio = (abs(ie[0]) / ii[0]) * 100.0
    add("interest_inversion", "Interest Income-Expense Inversion", "SEVERE",
        (inv_ratio is not None and inv_ratio > 75),
        ("🔴 Interest expense consumed %.1f%% of interest income — core lending spread near zero. NIM collapse imminent." % (inv_ratio or 0.0)),
        available=(inv_ratio is not None))

    # 11 Non-interest income dependence.
    nii0 = nii[0]
    non_int_share = None
    if oi[0] is not None and nii0 is not None and (nii0 + oi[0]) != 0:
        non_int_share = (oi[0] / (nii0 + oi[0])) * 100.0
    add("noninterest_dependence", "Non-Interest Income Dependence", "WARNING",
        (non_int_share is not None and non_int_share > 40),
        ("⚠️ %.1f%% of net revenue from non-interest sources (trading/fees). High dependence creates earnings volatility." % (non_int_share or 0.0)),
        available=(non_int_share is not None))

    # 12 Cost-to-income deterioration (2+ years > 60%).
    cir_high = 0
    cir_val = None
    for i in range(2):
        if nii[i] is not None and opex[i] is not None:
            net_rev = nii[i] + (oi[i] or 0.0)
            if net_rev:
                c = (opex[i] / net_rev) * 100.0
                if i == 0:
                    cir_val = c
                if c > 60:
                    cir_high += 1
    add("cost_income_creep", "Operating Expense Creep", "WARNING", cir_high >= 2,
        ("⚠️ Cost-to-Income ratio of %.1f%% for %d years signals operational inefficiency. Best-in-class is below 45%%." % (cir_val or 0.0, cir_high)),
        available=(cir_val is not None))

    # 13 Negative retained earnings.
    add("negative_retained", "Accumulated Deficit", "SEVERE",
        (ret[0] is not None and ret[0] < 0),
        ("🔴 Accumulated deficit of ₹%.1f Cr. Years of losses have eroded the equity base." % (ret[0] or 0.0)),
        available=(ret[0] is not None))

    # 14 LDR above safe level.
    ldr = liq.get("loanToDepositRatio_pct")
    add("high_ldr", "Loan-to-Deposit Above Safe Level", "WARNING",
        (ldr is not None and ldr > 90),
        ("⚠️ Loan-to-Deposit Ratio of %.1f%% signals tight liquidity — nearly all deposits deployed as loans. Safe zone is 75-85%%." % (ldr or 0.0)),
        available=(ldr is not None))

    # 15 RoA persistently below breakeven (3+ years < 0.5%).
    roa_low = 0
    for i in range(3):
        avg_ta = _avg(ta, i)
        if e["net_income"][i] is not None and avg_ta:
            r = _safe_divide(e["net_income"][i], avg_ta)
            if r is not None and (r * 100.0) < 0.5:
                roa_low += 1
    add("roa_below_breakeven", "RoA Persistently Below Breakeven", "SEVERE", roa_low >= 3,
        ("🔴 Return on Assets below 0.5%% for %d consecutive years — the bank struggles to generate internal capital to fund growth." % roa_low),
        available=(roa is not None))

    # 16 P/B premium with deteriorating fundamentals.
    nim_declining = False
    if len(nii) > 1 and nim_proxy is not None:
        n1 = _growth(nii[0], nii[1])
        nim_declining = n1 is not None and n1 < 0
    add("pb_premium_weak", "P/B Premium with Deteriorating Fundamentals", "WARNING",
        (pb is not None and pb > 2.0 and roe is not None and roe < 10 and nim_declining),
        ("⚠️ Market prices this bank at %.2f× book while fundamentals deteriorate (RoE %.1f%%, NIM declining). Valuation mismatch risk." % (pb or 0.0, roe or 0.0)),
        available=(pb is not None and roe is not None))

    triggered = sum(1 for f in flags if f["triggered"])
    severe = sum(1 for f in flags if f["triggered"] and f["severity"] == "SEVERE")
    return {"available": True, "flags": flags, "triggeredCount": triggered, "severeCount": severe}


# --------------------------------------------------------------------------
# Overall grade (re-normalized over available pillars) + coverage
# --------------------------------------------------------------------------
_GRADE_WEIGHTS = {
    "assetQuality": 0.30,
    "nimProfitability": 0.25,
    "depositFranchise": 0.10,
    "capitalAdequacy": 0.15,
    "liquidityManagement": 0.10,
    "loanBookGrowth": 0.10,
}


def _letter(score):
    if score >= 80: return "A+"
    if score >= 70: return "A"
    if score >= 60: return "B"
    if score >= 50: return "C"
    if score >= 40: return "D"
    return "F"


def _bfsi_overall_grade(pillars, red_flags, sub_sector):
    kept = []
    for name, w in _GRADE_WEIGHTS.items():
        p = pillars.get(name, {})
        sub = p.get("subScore") if isinstance(p, dict) else None
        if isinstance(p, dict) and p.get("available") and sub is not None:
            kept.append((name, w, sub))

    coverage = round(sum(w for _, w, _ in kept) * 100.0, 1)
    if not kept:
        return {"available": False, "reason": "no scorable pillars", "coveragePct": 0.0}

    total_w = sum(w for _, w, _ in kept)
    overall = sum((w / total_w) * sub for _, w, sub in kept)
    overall = round(overall, 1)
    letter = _letter(overall)

    breakdown = [{"pillar": n, "originalWeight": round(w * 100, 1),
                  "normalizedWeight": round((w / total_w) * 100, 1), "subScore": s} for n, w, s in kept]

    trig = [f for f in red_flags.get("flags", []) if f.get("triggered")]
    top_flag = trig[0]["name"] if trig else "no major red flags"
    verdict = ("%s — %s. Computed over %.0f%% of the ideal pillar weighting (Phase-2 regulatory data pending). Top watch item: %s."
               % (letter, sub_sector.replace("_", " ").title(), coverage, top_flag))

    return {
        "available": True,
        "overallScore": overall,
        "letterGrade": letter,
        "verdictSentence": verdict,
        "weightingBreakdown": breakdown,
        "coveragePct": coverage,
        "redFlagCount": red_flags.get("triggeredCount", 0),
        "severeFlagCount": red_flags.get("severeCount", 0),
    }


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def analyze_bfsi(symbol, include_peers=True):
    """Banking-native fundamental scorecard for a BFSI symbol.

    Mirrors fundamental_service.analyze_fundamentals structure: per-pillar
    try/except + available flags, then meta/gates/pillars/overallGrade.
    """
    frames = {}
    try:
        frames = _annual_frames(symbol)
    except Exception as exc:
        logger.warning("[_annual_frames] failed for %s: %s", symbol, exc)
        frames = {}

    info = frames.get("info", {}) if isinstance(frames, dict) else {}
    fys = frames.get("fiscal_year_ends", []) if isinstance(frames, dict) else []

    sector_info = {}
    try:
        sector_info = get_sector_bucket(symbol, frames)
    except Exception as exc:
        logger.warning("[get_sector_bucket] failed for %s: %s", symbol, exc)
    raw_sector = sector_info.get("raw_sector", info.get("sector") or "")
    raw_industry = sector_info.get("raw_industry", info.get("industry") or "")

    sub = _bfsi_subsector(info, raw_sector, raw_industry)
    sub_sector = sub.get("subSector", "PRIVATE_BANK")
    is_insurance = sub_sector in ("INSURANCE_LIFE", "INSURANCE_GENERAL")

    e = _extract(frames)

    def _safe(fn, *args):
        try:
            return fn(*args)
        except Exception as exc:
            logger.warning("[%s] failed for %s: %s", fn.__name__, symbol, exc)
            return {"available": False, "reason": str(exc), "subScore": None}

    if is_insurance:
        ins = _safe(_pillar_insurance_override, e, sub_sector)
        asset_q = ins
        prof = _safe(_pillar_nim_profitability, e)
        dep_f = ins
        cap_a = ins
    else:
        asset_q = _safe(_pillar_asset_quality, e)
        prof = _safe(_pillar_nim_profitability, e)
        dep_f = _safe(_pillar_deposit_franchise, e)
        cap_a = _safe(_pillar_capital_adequacy, e)

    liq = _safe(_pillar_liquidity, e)
    grow = _safe(_pillar_loan_growth, e)
    val = _safe(_pillar_bfsi_valuation, e)

    red_flags = {"available": False, "flags": [], "triggeredCount": 0, "severeCount": 0}
    try:
        red_flags = _bfsi_red_flags(e, prof, cap_a, liq, grow, val)
    except Exception as exc:
        logger.warning("[_bfsi_red_flags] failed for %s: %s", symbol, exc)

    pillars = {
        "assetQuality": asset_q,
        "nimProfitability": prof,
        "depositFranchise": dep_f,
        "capitalAdequacy": cap_a,
        "liquidityManagement": liq,
        "loanBookGrowth": grow,
    }

    grade = {"available": False, "reason": "not computed"}
    try:
        grade = _bfsi_overall_grade(pillars, red_flags, sub_sector)
    except Exception as exc:
        logger.warning("[_bfsi_overall_grade] failed for %s: %s", symbol, exc)

    peers = {"available": False, "reason": "include_peers=False (peer sub-call or disabled)"}
    if include_peers:
        try:
            peers = _pillar_bfsi_peers(symbol, sub_sector)
        except Exception as exc:
            logger.warning("[_pillar_bfsi_peers] failed for %s: %s", symbol, exc)
            peers = {"available": False, "reason": str(exc)}

    # --------------------------------------------------------------------------
    # Inject Phase-2 scraped metrics from SQLite DB & Trigger Background Scrape
    # --------------------------------------------------------------------------
    scraper_status = "IDLE"
    if get_latest_metrics:
        try:
            db_metrics = get_latest_metrics(symbol)
            logger.info(f"DIAGNOSTIC - db_metrics for {symbol}: {db_metrics}")
            
            # Auto-trigger the scraper in the background if we have NO data for this symbol!
            if not db_metrics:
                import threading
                global _SCRAPE_TASKS
                logger.info(f"DIAGNOSTIC - _SCRAPE_TASKS: {_SCRAPE_TASKS if '_SCRAPE_TASKS' in globals() else 'NOT DEFINED'}")
                if "_SCRAPE_TASKS" not in globals():
                    _SCRAPE_TASKS = {}
                
                if not _SCRAPE_TASKS.get(symbol):
                    try:
                        from scrapers.pipeline import run_scraper_pipeline
                        logger.info("No Phase-2 data found in DB for %s. Spawning background scraper thread...", symbol)
                        
                        def _run_and_clear():
                            _SCRAPE_TASKS[symbol] = True
                            try:
                                run_scraper_pipeline(symbol)
                            finally:
                                _SCRAPE_TASKS[symbol] = False
                                
                        threading.Thread(target=_run_and_clear, daemon=True).start()
                        scraper_status = "RUNNING"
                    except ImportError as e:
                        logger.warning("Scraper pipeline not available: %s", e)
                else:
                    scraper_status = "RUNNING"
                    
            if db_metrics:
                # GNPA / NNPA / PCR / Credit Cost / Slippage / Restructured / Security Coverage -> assetQuality
                if "GNPA" in db_metrics and db_metrics["GNPA"] is not None:
                    asset_q["grossNPA_pct"] = db_metrics["GNPA"]
                    if "phase2Stubs" in asset_q: asset_q["phase2Stubs"].pop("grossNPA_pct", None)
                if "NNPA" in db_metrics and db_metrics["NNPA"] is not None:
                    asset_q["netNPA_pct"] = db_metrics["NNPA"]
                    if "phase2Stubs" in asset_q: asset_q["phase2Stubs"].pop("netNPA_pct", None)
                if "PCR" in db_metrics and db_metrics["PCR"] is not None:
                    asset_q["pcr_pct"] = db_metrics["PCR"]
                    if "phase2Stubs" in asset_q: asset_q["phase2Stubs"].pop("provisionCoverageRatio_pct", None)
                if "creditCost_pct" in db_metrics and db_metrics["creditCost_pct"] is not None:
                    asset_q["creditCost_pct"] = db_metrics["creditCost_pct"]
                    if "phase2Stubs" in asset_q: asset_q["phase2Stubs"].pop("creditCost_pct", None)
                if "slippage_pct" in db_metrics and db_metrics["slippage_pct"] is not None:
                    asset_q["slippage_pct"] = db_metrics["slippage_pct"]
                    if "phase2Stubs" in asset_q: asset_q["phase2Stubs"].pop("slippage_pct", None)
                if "restructuredBook_pct" in db_metrics and db_metrics["restructuredBook_pct"] is not None:
                    asset_q["restructuredBook_pct"] = db_metrics["restructuredBook_pct"]
                    if "phase2Stubs" in asset_q: asset_q["phase2Stubs"].pop("restructuredBook_pct", None)
                if "securityCoverage_pct" in db_metrics and db_metrics["securityCoverage_pct"] is not None:
                    asset_q["securityCoverage_pct"] = db_metrics["securityCoverage_pct"]
                    if "phase2Stubs" in asset_q: asset_q["phase2Stubs"].pop("securityCoverage_pct", None)
                
                # CASA -> depositFranchise
                if "CASA" in db_metrics and db_metrics["CASA"] is not None:
                    dep_f["casaRatio_pct"] = db_metrics["CASA"]
                    if "phase2Stubs" in dep_f: dep_f["phase2Stubs"].pop("casaRatio_pct", None)
                    
                # roRWA_pct -> nimProfitability
                if "roRWA_pct" in db_metrics and db_metrics["roRWA_pct"] is not None:
                    prof["roRWA_pct"] = db_metrics["roRWA_pct"]
                    if "phase2Stubs" in prof: prof["phase2Stubs"].pop("roRWA_pct", None)
                    
                # CRAR, Tier1Capital_pct, CET1_pct, leverageRatio_pct -> capitalAdequacy
                if "CRAR" in db_metrics and db_metrics["CRAR"] is not None:
                    cap_a["crar_pct"] = db_metrics["CRAR"]
                    if "phase2Stubs" in cap_a: cap_a["phase2Stubs"].pop("CRAR_pct", None)
                if "Tier1Capital_pct" in db_metrics and db_metrics["Tier1Capital_pct"] is not None:
                    cap_a["Tier1Capital_pct"] = db_metrics["Tier1Capital_pct"]
                    if "phase2Stubs" in cap_a: cap_a["phase2Stubs"].pop("Tier1Capital_pct", None)
                if "CET1_pct" in db_metrics and db_metrics["CET1_pct"] is not None:
                    cap_a["CET1_pct"] = db_metrics["CET1_pct"]
                    if "phase2Stubs" in cap_a: cap_a["phase2Stubs"].pop("CET1_pct", None)
                if "leverageRatio_pct" in db_metrics and db_metrics["leverageRatio_pct"] is not None:
                    cap_a["leverageRatio_pct"] = db_metrics["leverageRatio_pct"]
                    if "phase2Stubs" in cap_a: cap_a["phase2Stubs"].pop("leverageRatio_pct", None)
                    
                # segmentSplit / geographicConcentration -> loanBookGrowth
                if "segmentSplit" in db_metrics and db_metrics["segmentSplit"] is not None:
                    grow["segmentSplit"] = db_metrics["segmentSplit"]
                    if "phase2Stubs" in grow: grow["phase2Stubs"].pop("segmentSplit", None)
                if "geographicConcentration" in db_metrics and db_metrics["geographicConcentration"] is not None:
                    grow["geographicConcentration"] = db_metrics["geographicConcentration"]
                    if "phase2Stubs" in grow: grow["phase2Stubs"].pop("geographicConcentration", None)

                # LCR_pct, NSFR_pct, ALM_mismatch -> liquidityManagement
                if "LCR_pct" in db_metrics and db_metrics["LCR_pct"] is not None:
                    liq["LCR_pct"] = db_metrics["LCR_pct"]
                    if "phase2Stubs" in liq: liq["phase2Stubs"].pop("LCR_pct", None)
                if "NSFR_pct" in db_metrics and db_metrics["NSFR_pct"] is not None:
                    liq["NSFR_pct"] = db_metrics["NSFR_pct"]
                    if "phase2Stubs" in liq: liq["phase2Stubs"].pop("NSFR_pct", None)
                if "ALM_mismatch" in db_metrics and db_metrics["ALM_mismatch"] is not None:
                    liq["ALM_mismatch"] = db_metrics["ALM_mismatch"]
                    if "phase2Stubs" in liq: liq["phase2Stubs"].pop("ALM_mismatch", None)
                    
                # Calculate pToABV if possible
                gnpa = db_metrics.get("GNPA")
                pcr = db_metrics.get("PCR")
                pb = val.get("pbRatio")
                if gnpa is not None and pcr is not None and pb is not None:
                    uncovered_npa_pct = gnpa * (1 - (pcr / 100.0))
                    abv_factor = 1.0 - (uncovered_npa_pct / 100.0)
                    if abv_factor > 0:
                        val["pToABV"] = round(pb / abv_factor, 2)
                        if "phase2Stubs" in val: val["phase2Stubs"].pop("pToABV", None)
                        
            # Filter non-bank metrics for Banks and NBFCs
            if not is_insurance:
                if "phase2Stubs" in val:
                    val["phase2Stubs"].pop("evToAUM", None)
                    val["phase2Stubs"].pop("vnbToEV", None)
                    
        except Exception as exc:
            logger.warning("Failed to inject DB metrics for %s: %s", symbol, exc)

    # Count Phase-2 stubs across pillars for the data-gap badge.
    phase2 = {}
    for pname, p in pillars.items():
        if isinstance(p, dict):
            for k, v in (p.get("phase2Stubs") or {}).items():
                phase2["%s.%s" % (pname, k)] = v
    for k, v in (val.get("phase2Stubs") or {}).items():
        phase2["valuation.%s" % k] = v

    grade["phase2StubCount"] = len(phase2)

    meta = {
        "symbol": symbol,
        "companyName": info.get("longName") or info.get("shortName") or symbol,
        "bfsiSubSector": sub_sector,
        "subSectorConfidence": sub.get("confidence"),
        "primaryKpis": sub.get("primaryKpis", []),
        "yahooSector": raw_sector,
        "currencyUnit": "INR Crores" if symbol.endswith(".NS") or symbol.endswith(".BO") else (info.get("currency") or "INR Crores"),
        "fiscalYearEnds": fys[:5] if fys else [],
        "dataAsOf": datetime.utcnow().isoformat() + "Z",
        "phase2GapCount": len(phase2),
        "isInsuranceOverride": is_insurance,
        "isPeerCall": not include_peers,
        "scraperStatus": scraper_status,
    }

    return {
        "meta": meta,
        "gates": {"isBFSI": True, "bfsiSubSector": sub_sector, "isInsuranceOverride": is_insurance},
        "assetQuality": asset_q,
        "nimProfitability": prof,
        "depositFranchise": dep_f,
        "capitalAdequacy": cap_a,
        "liquidityManagement": liq,
        "loanBookGrowth": grow,
        "bfsiRedFlags": red_flags,
        "bfsiValuation": val,
        "bfsiPeerBenchmark": peers,
        "overallGrade": grade,
        "phase2Stubs": phase2,
    }


# --------------------------------------------------------------------------
# Self-check (synthetic, no network) + live spot-check (offline-skippable)
# --------------------------------------------------------------------------
def _syn_frames(clean=True):
    """Build a synthetic fundamental_service-shaped frames dict.

    clean=True  -> healthy private bank (high RoA/RoE, low provisions, good capital)
    clean=False -> stressed bank (provision surge, low RoE, BVPS erosion)
    Values are RAW rupees (the helpers convert to crores).
    """
    CR = 1e7
    if clean:
        net_income = [18000 * CR, 15000 * CR, 12000 * CR, 9500 * CR, 7000 * CR]
        equity = [120000 * CR, 100000 * CR, 85000 * CR, 70000 * CR, 58000 * CR]
        ta = [1500000 * CR, 1300000 * CR, 1150000 * CR, 1000000 * CR, 880000 * CR]
        loans = [1000000 * CR, 880000 * CR, 780000 * CR, 700000 * CR, 630000 * CR]
        prov = [1200 * CR, 1100 * CR, 1050 * CR, 1000 * CR, 950 * CR]
        ii = [130000 * CR, 115000 * CR, 102000 * CR, 90000 * CR, 80000 * CR]
        ie = [60000 * CR, 54000 * CR, 49000 * CR, 44000 * CR, 40000 * CR]
        dep = [1200000 * CR, 1080000 * CR, 970000 * CR, 870000 * CR, 780000 * CR]
        borr = [40000 * CR, 38000 * CR, 36000 * CR, 34000 * CR, 32000 * CR]
        sh = [550 * 1e6, 550 * 1e6, 550 * 1e6, 550 * 1e6, 550 * 1e6]
        ret = [80000 * CR, 68000 * CR, 57000 * CR, 47000 * CR, 38000 * CR]
    else:
        net_income = [1500 * CR, 2000 * CR, 4000 * CR, 5000 * CR, 5500 * CR]
        equity = [60000 * CR, 65000 * CR, 62000 * CR, 58000 * CR, 55000 * CR]
        ta = [1400000 * CR, 1150000 * CR, 1000000 * CR, 900000 * CR, 820000 * CR]
        loans = [900000 * CR, 800000 * CR, 720000 * CR, 660000 * CR, 610000 * CR]
        prov = [9000 * CR, 4000 * CR, 3200 * CR, 2800 * CR, 2500 * CR]  # surge
        ii = [120000 * CR, 110000 * CR, 100000 * CR, 92000 * CR, 85000 * CR]
        ie = [105000 * CR, 90000 * CR, 80000 * CR, 72000 * CR, 66000 * CR]  # inversion
        dep = [1100000 * CR, 1000000 * CR, 920000 * CR, 850000 * CR, 790000 * CR]
        borr = [150000 * CR, 100000 * CR, 80000 * CR, 65000 * CR, 55000 * CR]  # fragile
        sh = [700 * 1e6, 600 * 1e6, 550 * 1e6, 550 * 1e6, 550 * 1e6]
        ret = [5000 * CR, 8000 * CR, 6000 * CR, 4000 * CR, 3000 * CR]

    def cols(series):
        return {k: list(v) for k, v in series.items()}

    fin = cols({
        "Net Income": net_income,
        "Total Revenue": ii,
        "Interest Expense": [-x for x in ie],
        "Net Interest Income": [a - b for a, b in zip(ii, ie)],
        "Other Income Expense": [0.08 * x for x in ii],
        "Operating Expense": [0.35 * (a - b) for a, b in zip(ii, ie)],
        "Credit Losses": prov,
    })
    bs = cols({
        "Total Assets": ta,
        "Total Liabilities Net Minority Interest": [a - b for a, b in zip(ta, equity)],
        "Stockholders Equity": equity,
        "Net Receivables": loans,
        "Total Deposits": dep,
        "Long Term Debt": borr,
        "Cash And Cash Equivalents": [0.05 * x for x in ta],
        "Short Term Investments": [0.08 * x for x in ta],
        "Long Term Investments": [0.06 * x for x in ta],
        "Retained Earnings": ret,
        "Ordinary Shares Number": sh,
    })
    return {
        "financials": fin,
        "balance_sheet": bs,
        "cashflow": {},
        "info": {"longName": "Synthetic Bank", "shortName": "SynBank", "sector": "Financial Services", "industry": "Banks", "marketCap": 600000 * CR},
        "fiscal_year_ends": ["2024-03-31", "2023-03-31", "2022-03-31", "2021-03-31", "2020-03-31"],
    }


def _run_synthetic():
    # Clean bank: should score well, few/no red flags.
    e = _extract(_syn_frames(clean=True))
    prof = _pillar_nim_profitability(e)
    cap = _pillar_capital_adequacy(e)
    liq = _pillar_liquidity(e)
    grow = _pillar_loan_growth(e)
    val = _pillar_bfsi_valuation(e)
    rf = _bfsi_red_flags(e, prof, cap, liq, grow, val)
    assert prof["roa_pct"] is not None and prof["roa_pct"] >= 1.0, ("clean RoA", prof["roa_pct"])
    assert prof["roe_pct"] is not None and prof["roe_pct"] >= 12, ("clean RoE", prof["roe_pct"])
    assert rf["severeCount"] == 0, ("clean severe flags", rf["severeCount"])
    grade = _bfsi_overall_grade({"nimProfitability": prof, "capitalAdequacy": cap, "liquidityManagement": liq, "loanBookGrowth": grow, "assetQuality": {"available": True, "subScore": None}, "depositFranchise": {"available": False}}, rf, "PRIVATE_BANK")
    assert grade["available"] and grade["letterGrade"] in ("A+", "A", "B"), ("clean grade", grade)
    assert 0 < grade["coveragePct"] < 100, ("coverage reflects dropped pillars", grade["coveragePct"])

    # Stressed bank: provision surge + interest inversion + RoE/earnings weakness fire.
    e2 = _extract(_syn_frames(clean=False))
    prof2 = _pillar_nim_profitability(e2)
    cap2 = _pillar_capital_adequacy(e2)
    liq2 = _pillar_liquidity(e2)
    grow2 = _pillar_loan_growth(e2)
    val2 = _pillar_bfsi_valuation(e2)
    rf2 = _bfsi_red_flags(e2, prof2, cap2, liq2, grow2, val2)
    fired = {f["id"] for f in rf2["flags"] if f["triggered"]}
    assert "provision_surge" in fired, ("stressed provision surge", fired)
    assert "interest_inversion" in fired, ("stressed inversion", fired)
    assert rf2["severeCount"] >= 2, ("stressed severe count", rf2["severeCount"])

    # Single-year frame: YoY-dependent flags unavailable but module still computes.
    one = _syn_frames(clean=True)
    for stmt in ("financials", "balance_sheet"):
        one[stmt] = {k: v[:1] for k, v in one[stmt].items()}
    one["fiscal_year_ends"] = one["fiscal_year_ends"][:1]
    e3 = _extract(one)
    prof3 = _pillar_nim_profitability(e3)
    assert prof3["niiGrowth1Y_pct"] is None, ("single-year growth None", prof3["niiGrowth1Y_pct"])
    assert prof3["roa_pct"] is not None, ("single-year RoA still computable", prof3["roa_pct"])
    print("ok synthetic  clean_grade=%s(%s) cov=%s%%  stressed_flags=%d severe=%d" % (
        grade["letterGrade"], grade["overallScore"], grade["coveragePct"], rf2["triggeredCount"], rf2["severeCount"]))


if __name__ == "__main__":
    _run_synthetic()
    for sym in ("HDFCBANK.NS", "SBIN.NS"):
        try:
            res = analyze_bfsi(sym, include_peers=False)
            g = res.get("overallGrade", {})
            print("live %s  sub=%s  grade=%s(%s) cov=%s%%  phase2=%d  flags=%d" % (
                sym, res["meta"]["bfsiSubSector"], g.get("letterGrade"), g.get("overallScore"),
                g.get("coveragePct"), res["meta"]["phase2GapCount"], g.get("redFlagCount")))
        except Exception as exc:
            print("live %s skipped (offline/network): %s" % (sym, exc))
