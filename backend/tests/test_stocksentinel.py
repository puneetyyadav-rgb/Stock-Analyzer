"""Backend API tests for StockSentinel India MVP."""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://stock-sentinel-india-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
SYM = "RELIANCE"
TIMEOUT = 90


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# --- Root / search ---
def test_root(s):
    r = s.get(f"{API}/", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "app" in d and d.get("status") == "ok"


def test_search(s):
    r = s.get(f"{API}/search", params={"q": "RELIANCE"}, timeout=TIMEOUT)
    assert r.status_code == 200
    d = r.json()
    assert "results" in d and isinstance(d["results"], list)
    assert len(d["results"]) >= 1


# --- Stock endpoints ---
def test_overview(s):
    r = s.get(f"{API}/stock/{SYM}/overview", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d.get("price") is not None
    # presence checks for required fields
    for k in ["sector", "marketCap", "peRatio"]:
        assert k in d, f"missing {k}"


@pytest.mark.parametrize("period", ["1y", "1mo"])
def test_chart(s, period):
    r = s.get(f"{API}/stock/{SYM}/chart", params={"period": period}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    # data could be {"data": [...]} or list directly
    arr = d.get("data") if isinstance(d, dict) else d
    assert isinstance(arr, list)
    assert len(arr) > 0
    sample = arr[0]
    # OHLC keys
    assert any(k in sample for k in ["close", "Close", "c"])


def test_technicals(s):
    r = s.get(f"{API}/stock/{SYM}/technicals", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    for k in ["rsi", "macd", "sma50", "sma200", "trend"]:
        assert k in d, f"missing {k}"


def test_financials(s):
    r = s.get(f"{API}/stock/{SYM}/financials", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    for k in ["quarterly", "annual", "balanceSheet", "cashFlow"]:
        assert k in d, f"missing {k}"


def test_corporate(s):
    r = s.get(f"{API}/stock/{SYM}/corporate", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert "dividends" in d and "splits" in d


def test_holders(s):
    r = s.get(f"{API}/stock/{SYM}/holders", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert any(k in d for k in ["institutional", "majorHolders", "insiderTransactions"])


def test_news(s):
    r = s.get(f"{API}/stock/{SYM}/news", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert "items" in d and isinstance(d["items"], list)


def test_screener(s):
    r = s.get(f"{API}/stock/{SYM}/screener", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    # may include ratios/pros/cons/about
    assert isinstance(d, dict)


# --- Macro / sectors ---
def test_macro(s):
    r = s.get(f"{API}/macro", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    # accept dict-of-indicators or {"indicators": [...]}
    if isinstance(d, dict) and "indicators" in d:
        inds = d["indicators"]
    elif isinstance(d, list):
        inds = d
    else:
        inds = list(d.values()) if isinstance(d, dict) else []
    assert len(inds) >= 8


def test_sectors(s):
    r = s.get(f"{API}/sectors", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    arr = d.get("sectors") if isinstance(d, dict) else d
    assert isinstance(arr, list)
    assert len(arr) >= 5


# --- AI verdict (slow) ---
def test_ai_verdict(s):
    r = s.post(f"{API}/stock/{SYM}/ai-verdict", timeout=180)
    assert r.status_code == 200, r.text[:800]
    d = r.json()
    for k in ["verdict", "summary"]:
        assert k in d, f"missing {k}"
