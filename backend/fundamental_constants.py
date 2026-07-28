# fundamental_constants.py
# Master constants, alias reconciliation lists, thresholds, severities, and sector taxonomy
# for the 10-Pillar Fundamental & Forensic Equity Research Deck (Version 3.1)

# Severity Taxonomy
SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_RED = "RED"
SEVERITY_CRITICAL = "CRITICAL"

# Pillar Weights Table (Section 1.4)
PILLAR_WEIGHTS = {
    "incomeStatement": 0,
    "balanceSheet": 0,
    "cashFlow": 0,
    "profitability": 30,
    "solvency": 20,
    "efficiency": 15,
    "forensicAccounting": 0,
    "valuation": 10,
    "growth": 25,
    "peerBenchmarking": 0
}

# Altman Z Thresholds Table (Section 1.6 / 2.7)
ALTMAN_THRESHOLDS = {
    "Z_1968": {"distress_below": 1.81, "safe_above": 2.99, "name": "Standard Z-Score (1968 - Mfg)"},
    "Z_PRIME_1983": {"distress_below": 1.23, "safe_above": 2.90, "name": "Z'-Score (1983 - Private/Non-Mfg)"},
    "Z_DOUBLE_PRIME_1995": {"distress_below": 1.10, "safe_above": 2.60, "name": "Z''-Score (1995 - Non-Mfg/Service)"},
    "Z_DOUBLE_PRIME_EM_1995": {"distress_below": 3.75, "safe_above": 5.85, "name": "Z'' EM (1995 - Emerging Markets)"}
}

# Sector Bucket Priority List (Section 4.1)
SECTOR_BUCKET_RULES = [
    ("HOLDING_COMPANY", "gate", []),
    ("BFSI", "gate", []),
    ("TELECOM", "industry", ["telecom"]),
    ("AIRLINES", "industry", ["airlines"]),
    ("REAL_ESTATE_CONSTRUCTION", "sector", ["real estate"]),
    ("EPC_CAPITAL_GOODS_DEFENSE_INFRA", "industry", ["engineering & construction", "aerospace & defense", "specialty industrial machinery", "conglomerates"]),
    ("PHARMA_API_CDMO_CHEMICALS", "industry", ["drug manufacturers", "pharmaceutical", "biotechnology", "chemicals"]),
    ("IT_SOFTWARE_SERVICES", "sector_or_industry", ["technology", "information technology services", "software"]),
    ("FMCG_CONSUMER_STAPLES", "sector", ["consumer defensive"]),
    ("COMMODITIES_METALS_OG_MINING", "sector_or_industry", ["energy", "basic materials", "metals", "mining", "steel"]),
    ("AUTO_MANUFACTURING", "sector_and_industry", ["consumer cyclical", "auto"]),
    ("RENEWABLE_POWER_INFRA_80IA", "industry", ["renewable", "utilities—renewable"]),
    ("GENERAL_OTHER", "default", [])
]

# Sloan Accrual Growth-Adjusted Threshold Bands (Section 2.7)
SLOAN_GROWTH_BANDS = {
    "high_growth_gt_20": {"warning": 15.0, "red": 30.0, "label": ">20% revenue CAGR"},
    "moderate_growth_10_20": {"warning": 12.0, "red": 25.0, "label": "10-20% revenue CAGR"},
    "mature_lt_10": {"warning": 10.0, "red": 20.0, "label": "<10% revenue CAGR"}
}

# ==========================================
# ALIAS RECONCILIATION LISTS (Section 2 & Task 1 Recon)
# ==========================================

# Income Statement Aliases
REVENUE_ALIASES = [
    "Total Revenue", "Operating Revenue", "Revenue", "Gross Revenue", "Sales"
]
COGS_ALIASES = [
    "Cost Of Revenue", "Reconciled Cost Of Revenue", "Cost Of Goods Sold", "Cost Of Sales", "Operating Expense"
]
GROSS_PROFIT_ALIASES = [
    "Gross Profit", "Total Gross Profit"
]
OPERATING_INCOME_ALIASES = [
    "Operating Income", "EBIT", "Operating Profit", "Total Operating Income As Reported"
]
EBIT_ALIASES = [
    "EBIT", "Operating Income", "Operating Profit"
]
EBITDA_ALIASES = [
    "EBITDA", "Normalized EBITDA", "Operating Income Plus Depreciation"
]
NET_INCOME_ALIASES = [
    "Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations", 
    "Net Income From Continuing And Discontinued Operation", "Net Income Including Noncontrolling Interests"
]
INTEREST_EXPENSE_ALIASES = [
    "Interest Expense", "Interest Expense Non Operating", "Total Interest Expense", "Net Interest Expense"
]
DEPRECIATION_ALIASES = [
    "Depreciation Amortization Depletion Income Statement", "Depreciation And Amortization In Income Statement", 
    "Reconciled Depreciation", "Depreciation Income Statement", "Depreciation And Amortization"
]
PRETAX_INCOME_ALIASES = [
    "Pretax Income", "Income Before Tax", "EBT", "Pretax Profit"
]
TAX_PROVISION_ALIASES = [
    "Tax Provision", "Income Tax Expense", "Provision For Income Taxes", "Total Tax Payable"
]
OTHER_INCOME_ALIASES = [
    "Other Non Operating Income Expenses", "Interest Income", "Interest Income Non Operating", 
    "Other Income", "Non Operating Income"
]

# Balance Sheet Aliases
TOTAL_ASSETS_ALIASES = [
    "Total Assets", "Assets Total"
]
CURRENT_ASSETS_ALIASES = [
    "Current Assets", "Total Current Assets"
]
CASH_ALIASES = [
    "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", 
    "Cash And Short Term Investments", "Cash"
]
RECEIVABLES_ALIASES = [
    "Accounts Receivable", "Receivables", "Gross Accounts Receivable", "Net Receivables", "Trade Receivables"
]
INVENTORY_ALIASES = [
    "Inventory", "Inventories Adjustments Allowances", "Total Inventories"
]
TOTAL_LIABILITIES_ALIASES = [
    "Total Liabilities Net Minority Interest", "Total Liabilities", "Liabilities Total"
]
CURRENT_LIABILITIES_ALIASES = [
    "Current Liabilities", "Total Current Liabilities"
]
ACCOUNTS_PAYABLE_ALIASES = [
    "Accounts Payable", "Payables", "Payables And Accrued Expenses", "Trade And Other Payables"
]
TOTAL_DEBT_ALIASES = [
    "Total Debt", "Net Debt Plus Total Cash", "Total Interest Bearing Debt"
]
LONG_TERM_DEBT_ALIASES = [
    "Long Term Debt", "Long Term Debt And Capital Lease Obligation", "Non Current Debt"
]
CURRENT_DEBT_ALIASES = [
    "Current Debt", "Current Debt And Capital Lease Obligation", "Short Term Debt", "Current Notes Payable"
]
LEASE_LIABILITIES_ALIASES = [
    "Capital Lease Obligations", "Long Term Capital Lease Obligation", "Current Capital Lease Obligation",
    "Lease Liabilities", "Total Lease Liabilities"
]
GOODWILL_INTANGIBLES_ALIASES = [
    "Goodwill And Other Intangible Assets", "Goodwill", "Other Intangible Assets", "Intangible Assets"
]
TOTAL_EQUITY_ALIASES = [
    "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest", "Total Shareholders Equity"
]
WORKING_CAPITAL_ALIASES = [
    "Working Capital", "Net Working Capital"
]
NET_TANGIBLE_ASSETS_ALIASES = [
    "Net Tangible Assets", "Tangible Book Value"
]
INVESTED_CAPITAL_ALIASES = [
    "Invested Capital"
]

# Cash Flow Aliases
OPERATING_CASH_FLOW_ALIASES = [
    "Operating Cash Flow", "Cash Flow From Continuing Operating Activities", "Cash Provided By Operating Activities"
]
CAPEX_ALIASES = [
    "Capital Expenditure", "Capital Expenditure Reported", "Payments For Property Plant And Equipment", "Capital Expenditures"
]
DIVIDENDS_PAID_ALIASES = [
    "Cash Dividends Paid", "Common Stock Dividend Paid", "Dividends Paid Direct", "Total Dividend Paid"
]
FREE_CASH_FLOW_ALIASES = [
    "Free Cash Flow"
]
DEFERRED_TAX_ALIASES = [
    "Deferred Tax", "Deferred Income Tax", "Deferred Tax Net"
]
CHANGE_IN_WORKING_CAPITAL_ALIASES = [
    "Change In Working Capital", "Change In Other Working Capital", "Working Capital Changes"
]

NON_CURRENT_ASSETS_ALIASES = ["Total Non Current Assets", "Non Current Assets"]
NET_PPE_ALIASES = ["Net PPE", "Gross PPE", "Property Plant And Equipment", "Net Property Plant And Equipment", "Properties"]
CWIP_ALIASES = ["Construction In Progress", "CWIP", "Capital Work In Progress"]
RETAINED_EARNINGS_ALIASES = ["Retained Earnings", "Retained Earnings Accumulated Deficit", "Retained Earnings Total Equity"]
CASH_EQUIVALENTS_ALIASES = CASH_ALIASES
INTANGIBLES_ALIASES = GOODWILL_INTANGIBLES_ALIASES
EQUITY_ALIASES = TOTAL_EQUITY_ALIASES
TRADE_PAYABLES_ALIASES = ACCOUNTS_PAYABLE_ALIASES
