"""Phase 5 tests: /external-scrape (Playwright) + expanded sector keyword library."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TIMEOUT_LONG = 90  # first scrape can be 8-12s + safety


# --- External scrape ---
class TestExternalScrape:
    def test_reliance_external_scrape(self):
        r = requests.get(f"{BASE_URL}/api/stock/RELIANCE/external-scrape", timeout=TIMEOUT_LONG)
        assert r.status_code == 200
        d = r.json()
        # aftermarkets shape
        am = d.get("aftermarkets")
        assert am is not None
        assert am.get("source") == "Aftermarkets"
        assert am.get("available") is True
        assert "url" in am
        assert isinstance(am.get("businessScore"), int)
        assert 0 <= am["businessScore"] <= 100
        # subScores
        ss = am.get("subScores", {})
        for k in ("valuation", "growth", "returnsMargins", "financialHealth"):
            assert k in ss, f"missing subScore {k}"
            assert "rating" in ss[k] and "score" in ss[k] and "description" in ss[k]
            assert isinstance(ss[k]["score"], int)
        # safety checks
        sc = am.get("safetyChecks", {})
        for k in ("Promoter pledge", "ASM list", "GSM list", "F&O ban", "Default probability"):
            assert k in sc, f"missing safetyCheck {k}"
        # live price
        lp = am.get("livePrice")
        assert lp and "price" in lp and "changePercent" in lp
        # trendlyne + stockedge blocked honestly
        for src in ("trendlyne", "stockedge"):
            b = d.get(src)
            assert b is not None
            assert b.get("available") is False
            assert "url" in b
            assert "reason" in b and len(b["reason"]) > 20
        assert "WAF" in d["trendlyne"]["reason"]
        assert "login" in d["stockedge"]["reason"].lower() or "stock ID" in d["stockedge"]["reason"]

    def test_cache_speedup(self):
        # second call should be <2s (cache TTL 30 min)
        import time
        t = time.time()
        r = requests.get(f"{BASE_URL}/api/stock/RELIANCE/external-scrape", timeout=TIMEOUT_LONG)
        elapsed = time.time() - t
        assert r.status_code == 200
        assert elapsed < 3.0, f"cached call took {elapsed:.2f}s (expected <3s)"


# --- Expanded keyword library ---
class TestNewsSplitKeywords:
    def test_sunpharma_sector_news_populated(self):
        r = requests.get(f"{BASE_URL}/api/stock/SUNPHARMA/news-split", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "sector" in d.get("counts", {})
        sector = d.get("sector_news", [])
        assert len(sector) > 0, "SUNPHARMA sector_news bucket should be non-empty with expanded pharma keywords"
        # at least some item should reference pharma terms
        text_blob = " ".join((it.get("title", "") + " " + it.get("summary", "")).lower() for it in sector)
        pharma_terms = ["pharma", "drug", "usfda", "molecule", "clinical", "vaccine", "api", "generic"]
        assert any(t in text_blob for t in pharma_terms), f"sector news for SUNPHARMA lacks pharma keywords: hits={[t for t in pharma_terms if t in text_blob]}"

    def test_tatamotors_sector_news_populated(self):
        r = requests.get(f"{BASE_URL}/api/stock/TATAMOTORS/news-split", timeout=60)
        assert r.status_code == 200
        d = r.json()
        sector = d.get("sector_news", [])
        assert len(sector) > 0, "TATAMOTORS sector_news bucket should be non-empty"
        blob = " ".join((it.get("title", "") + " " + it.get("summary", "")).lower() for it in sector)
        auto_terms = ["auto", "ev", "vehicle", "two-wheeler", "passenger", "car", "suv", "truck"]
        assert any(t in blob for t in auto_terms)


# --- Regression: prior phase endpoints still alive ---
@pytest.mark.parametrize("ep,method", [
    ("/news-split", "GET"), ("/sector-analysis", "GET"), ("/red-flags", "GET"),
    ("/events", "GET"), ("/legal", "GET"), ("/social", "GET"), ("/ai-verdict", "POST"),
    ("/options", "GET"), ("/insider", "GET"),
])
def test_regression_endpoints(ep, method):
    url = f"{BASE_URL}/api/stock/RELIANCE{ep}"
    r = requests.post(url, json={}, timeout=90) if method == "POST" else requests.get(url, timeout=60)
    assert r.status_code == 200, f"{ep} returned {r.status_code}"
    assert isinstance(r.json(), dict)
