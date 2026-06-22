"""Phase 4 tests: news-split + sector-analysis endpoints for RELIANCE."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stock-sentinel-india-1.preview.emergentagent.com").rstrip("/")
SYMBOL = "RELIANCE"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- news-split ----------
class TestNewsSplit:
    def test_status_and_shape(self, session):
        r = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/news-split", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("sector", "company", "sector_news", "market", "counts"):
            assert k in d, f"missing {k}"
        for k in ("company", "sector", "market"):
            assert k in d["counts"]
            assert isinstance(d["counts"][k], int)
        assert isinstance(d["company"], list)
        assert isinstance(d["sector_news"], list)
        assert isinstance(d["market"], list)

    def test_counts_match_lists(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/news-split", timeout=60).json()
        assert d["counts"]["company"] == len(d["company"])
        assert d["counts"]["sector"] == len(d["sector_news"])
        assert d["counts"]["market"] == len(d["market"])

    def test_reliance_has_sector_and_company_items(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/news-split", timeout=60).json()
        assert d["sector"] == "Energy"
        # company expected ~19, sector ~25 per agent context
        assert d["counts"]["company"] >= 5, f"company too low: {d['counts']}"
        assert d["counts"]["sector"] >= 10, f"sector too low: {d['counts']}"

    def test_items_have_required_fields(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/news-split", timeout=60).json()
        sample = (d["company"] + d["sector_news"] + d["market"])[:5]
        assert sample, "no items returned"
        for it in sample:
            assert "title" in it
            assert "source" in it

    def test_company_news_mentions_reliance(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/news-split", timeout=60).json()
        hits = 0
        for it in d["company"][:10]:
            blob = (it.get("title", "") + " " + it.get("summary", "")).lower()
            if "reliance" in blob:
                hits += 1
        assert hits >= 1, "no reliance mentions found in company bucket"

    def test_sentiment_label_present(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/news-split", timeout=60).json()
        # at least one bucket should have items with sentimentLabel
        all_items = d["company"] + d["sector_news"] + d["market"]
        with_sent = [n for n in all_items if "sentimentLabel" in n]
        assert len(with_sent) > 0, "no sentimentLabel found on any news item"


# ---------- sector-analysis ----------
class TestSectorAnalysis:
    def test_status_and_top_shape(self, session):
        r = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/sector-analysis", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("sector", "sector_index", "benchmark", "relative_perf_1m", "verdict", "deep_links"):
            assert k in d, f"missing {k}"

    def test_reliance_sector_is_energy(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/sector-analysis", timeout=60).json()
        assert d["sector"] == "Energy"
        assert d["sector_index"]["ticker"] == "^CNXENERGY"
        assert d["sector_index"]["label"] == "NIFTY ENERGY"
        assert d["benchmark"]["ticker"] == "^NSEI"

    def test_index_has_price_and_perf(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/sector-analysis", timeout=60).json()
        si = d["sector_index"]
        for k in ("price", "changePercent", "perf_1m", "perf_3m"):
            assert k in si
        assert si["price"] is not None and si["price"] > 0

    def test_verdict_string(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/sector-analysis", timeout=60).json()
        assert d["verdict"] in (
            "Sector outperforming Nifty 50",
            "Sector underperforming Nifty 50",
            "Sector tracking Nifty 50",
        )

    def test_deep_links(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/sector-analysis", timeout=60).json()
        dl = d["deep_links"]
        for k in ("trendlyne", "stockedge", "aftermarkets", "moneycontrol_sector", "nse_indices"):
            assert k in dl and dl[k].startswith("http"), f"{k} bad"
        assert "trendlyne.com" in dl["trendlyne"]
        assert "stockedge.com" in dl["stockedge"]
        assert "aftermarkets.in" in dl["aftermarkets"]

    def test_peer_aggregates_and_stock_vs_peers(self, session):
        d = session.get(f"{BASE_URL}/api/stock/{SYMBOL}/sector-analysis", timeout=60).json()
        pa = d.get("peer_aggregates")
        assert pa is not None, "peer_aggregates missing"
        assert pa["count"] >= 1
        for k in ("avg_pe", "avg_pb", "avg_roe", "avg_profit_margin", "avg_revenue_growth", "top_gainer", "top_loser"):
            assert k in pa
        svp = d.get("stock_vs_peers")
        if svp:
            assert svp["pe_vs_peer_avg"] in ("Cheaper", "Pricier")
            assert isinstance(svp["pe_diff_pct"], (int, float))


# ---------- regression: prior endpoints still work ----------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/overview", "/news", "/red-flags", "/events", "/legal", "/social",
    ])
    def test_prior_endpoints(self, session, path):
        r = session.get(f"{BASE_URL}/api/stock/{SYMBOL}{path}", timeout=60)
        assert r.status_code == 200, f"{path} failed: {r.status_code} {r.text[:200]}"
