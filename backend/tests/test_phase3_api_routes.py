"""Unit tests for Phase 3 FastAPI Backend Routes.

Verifies:
1. Route import smoke test (`/api/macro/global-monte-carlo` and `/api/stock/{symbol}/beta-coupled-simulation`).
2. FastAPI response shape check (status 200 OK and exact dictionary schema).
3. Bad symbol check (verifying graceful 200/404 handling without 500 crashes).
4. Low-history fallback check (verifying clean insufficient_history response payload).
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from server import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_route_import_smoke():
    """Verifies server imports and checks that both Phase 3 routes are registered."""
    routes = [r.path for r in app.routes]
    assert "/api/macro/global-monte-carlo" in routes, "Global Monte Carlo route missing from FastAPI app"
    assert "/api/stock/{symbol}/beta-coupled-simulation" in routes, "Beta Coupled Simulation route missing from FastAPI app"


def test_fastapi_response_shape(client):
    """Verifies GET /api/macro/global-monte-carlo returns 200 OK and correct JSON schema."""
    response = client.get("/api/macro/global-monte-carlo?horizon_days=10&paths=500&seed=42")
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"
    data = response.json()
    assert isinstance(data, dict)
    assert data["status"] == "success"
    assert "expected_return" in data
    assert "var_95" in data
    assert "dominant_risk_driver" in data
    assert "path_percentiles" in data


def test_bad_symbol_handling(client):
    """Verifies requesting TOTALLY_FAKE_SYMBOL_999 does not cause a 500 Internal Server Error crash."""
    response = client.get("/api/stock/TOTALLY_FAKE_SYMBOL_999/beta-coupled-simulation?horizon_days=10&paths=500&seed=42")
    # Must not crash with 500
    assert response.status_code in [200, 400, 404], f"Bad symbol caused crash {response.status_code}"
    if response.status_code == 200:
        data = response.json()
        assert data["status"] in ["insufficient_history", "error", "success"]


def test_low_history_fallback(client):
    """Verifies low/missing history returns safe structured fallback without unhandled exceptions."""
    response = client.get("/api/stock/INVALID_SHORT_SYM/beta-coupled-simulation?horizon_days=10&paths=500&seed=42")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "insufficient_history"
    assert data["upside_beta"] == 1.0
    assert data["downside_beta"] == 1.0
