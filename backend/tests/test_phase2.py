"""Phase 2 backend tests: FII/DII, concalls, peers, options, insider, fixed holders/technicals/overview."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://stock-sentinel-india-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
SYM = "RELIANCE"
TIMEOUT = 120


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# --- FII/DII ---
def test_fii_dii(s):
    r = s.get(f"{API}/fii-dii", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    rows = d.get("rows") if isinstance(d, dict) else d
    if not rows:
        pytest.skip(f"FII/DII source unavailable (likely HTTP 403 from Moneycontrol): {d}")
    assert isinstance(rows, list) and len(rows) >= 1, f"expected rows, got {d}"
    sample = rows[0]
    # presence checks - at least some of expected fields
    keys = set(sample.keys())
    assert keys & {"fiiCash", "diiCash", "niftyClose", "sensexClose"}, f"missing FII/DII keys, got {keys}"


# --- Concalls ---
def test_concalls(s):
    r = s.get(f"{API}/stock/{SYM}/concalls", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    items = d.get("items") or d.get("concalls") if isinstance(d, dict) else d
    assert isinstance(items, list)
    if items:
        c = items[0]
        assert "date" in c or "transcriptUrl" in c or "ppt" in c or "transcript" in c


def test_concall_summary(s):
    # First grab a concall
    r = s.get(f"{API}/stock/{SYM}/concalls", timeout=TIMEOUT)
    if r.status_code != 200:
        pytest.skip("concalls endpoint not available")
    items = r.json().get("items") or r.json().get("concalls", []) if isinstance(r.json(), dict) else r.json()
    if not items:
        pytest.skip("no concalls available")
    c = items[0]
    transcript_url = c.get("transcriptUrl") or c.get("transcript") or ""
    date = c.get("date") or ""
    body = {"transcriptUrl": transcript_url, "date": date}
    r2 = s.post(f"{API}/stock/{SYM}/concall-summary", json=body, timeout=180)
    assert r2.status_code == 200, r2.text[:800]
    d = r2.json()
    # source can be 'transcript' or 'alternative'
    assert "source" in d
    assert d.get("source") in ("transcript", "alternative", "bse_pdf")
    # core fields
    for k in ["sentimentLabel", "verdict", "highlights"]:
        assert k in d, f"missing {k}"


# --- Peers ---
def test_peers(s):
    r = s.get(f"{API}/stock/{SYM}/peers", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    peers = d.get("peers") if isinstance(d, dict) else d
    assert isinstance(peers, list) and len(peers) >= 1
    sample = peers[0]
    assert "symbol" in sample or "name" in sample


# --- Options chain (graceful) ---
def test_options(s):
    r = s.get(f"{API}/stock/{SYM}/options", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert "available" in d
    if d.get("available"):
        assert "pcr" in d or "rows" in d
    else:
        assert "error" in d or "reason" in d


# --- Insider ---
def test_insider(s):
    r = s.get(f"{API}/stock/{SYM}/insider", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    items = d.get("items") or d.get("insider") if isinstance(d, dict) else (d if isinstance(d, list) else d.get("transactions", []))
    assert isinstance(items, list)
    if items:
        sample = items[0]
        # transaction must be populated
        assert "transaction" in sample
        if sample.get("transaction") is not None:
            assert isinstance(sample.get("transaction"), str)


# --- Holders fix ---
def test_holders_major_breakdown(s):
    r = s.get(f"{API}/stock/{SYM}/holders", timeout=TIMEOUT)
    assert r.status_code == 200
    d = r.json()
    mh = d.get("majorHoldersBreakdown") or d.get("major_holders_breakdown") or {}
    if mh:
        keys = set(mh.keys()) if isinstance(mh, dict) else set()
        assert keys & {"insidersPercentHeld", "institutionsPercentHeld", "institutionsCount"}, f"got {mh}"


# --- TCS technicals fix (NaN) ---
def test_tcs_technicals_nan_fix(s):
    r = s.get(f"{API}/stock/TCS/technicals", timeout=TIMEOUT)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    # verify no NaN literal (would fail JSON parse anyway)
    for k, v in d.items():
        if isinstance(v, float):
            import math
            assert not math.isnan(v), f"{k} is NaN"


# --- TCS overview dividendYield ---
def test_tcs_overview_dividend_yield(s):
    r = s.get(f"{API}/stock/TCS/overview", timeout=TIMEOUT)
    assert r.status_code == 200
    d = r.json()
    dy = d.get("dividendYield")
    # accept None or numeric
    if dy is not None:
        assert isinstance(dy, (int, float))
