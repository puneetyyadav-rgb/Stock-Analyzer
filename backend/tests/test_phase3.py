"""Phase 3 regression: social / legal / events / red-flags / news VADER / ai-verdict sector & disclaimer."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stock-sentinel-india-1.preview.emergentagent.com").rstrip("/")
S = "RELIANCE"


@pytest.fixture(scope="module")
def session():
    return requests.Session()


# --- P0-1 Social ---
def test_social_three_blocks(session):
    r = session.get(f"{BASE_URL}/api/stock/{S}/social", timeout=60)
    assert r.status_code == 200
    d = r.json()
    for key in ("reddit", "stocktwits", "twitter_x"):
        assert key in d
        assert d[key]["available"] is False
    assert "REDDIT_CLIENT_ID" in d["reddit"]["reason"]
    assert "X discontinued" in d["twitter_x"]["reason"]


# --- P0-2 Legal ---
def test_legal_well_formed(session):
    r = session.get(f"{BASE_URL}/api/stock/{S}/legal", timeout=120)
    assert r.status_code == 200
    d = r.json()
    assert "items" in d and isinstance(d["items"], list)
    assert "NSE corporate-announcements" in d["source"]
    assert isinstance(d["announcements_scanned"], int)
    if d["items"]:
        it = d["items"][0]
        assert it.get("severity") in ("Critical", "High", "Medium", "Low")
        assert "summary" in it and "category" in it


# --- P0-3 News VADER ---
def test_news_has_vader_sentiment(session):
    r = session.get(f"{BASE_URL}/api/stock/{S}/news", timeout=30)
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert len(items) > 0
    n = items[0]
    assert "sentimentScore" in n and isinstance(n["sentimentScore"], (int, float))
    assert n.get("sentimentLabel") in ("Positive", "Negative", "Neutral")


# --- P0-4 + P1-1 AI verdict ---
def test_ai_verdict_disclaimer_and_sector(session):
    r = session.post(f"{BASE_URL}/api/stock/{S}/ai-verdict", timeout=180)
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d.get("disclaimer"), str) and len(d["disclaimer"]) > 30
    assert d.get("sectorBucket") == "Oil & Gas"
    ss = d.get("sectorSpecific") or []
    assert isinstance(ss, list) and len(ss) > 0
    for s in ss:
        assert "factor" in s and "assessment" in s and "dataAvailable" in s


# --- P1-2 Events ---
def test_events_merged(session):
    r = session.get(f"{BASE_URL}/api/stock/{S}/events", timeout=60)
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert isinstance(items, list)
    # Allow zero (yfinance can be empty) but if present must have required keys
    for ev in items:
        assert "event" in ev and "date" in ev and "type" in ev and "source" in ev


# --- P1-3 Red Flags ---
def test_red_flags_structure(session):
    r = session.get(f"{BASE_URL}/api/stock/{S}/red-flags", timeout=120)
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d.get("items"), list)
    assert "promoterPledge" in d
    assert isinstance(d.get("specialEvents"), list)
    sevs = ["Critical", "High", "Medium", "Low"]
    last = -1
    for it in d["items"]:
        assert it["severity"] in sevs
        idx = sevs.index(it["severity"])
        assert idx >= last
        last = idx
