"""Pytest tests for the simulate API.

invoke_nova_lite is mocked so no real Bedrock calls occur.
The mock returns a canned sentiment string "0.2" which the parser converts to
raw_sentiment=0.2.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Canned Bedrock response — parser reads "response_text" and extracts "0.2".
_CANNED = {"response_text": "0.2", "cache_hit": False, "attempts": 1}

# Patch target: the name *inside* src.api.simulate (already imported there).
_PATCH = "src.api.simulate.invoke_nova_lite"

_VALID_HEADLINE = "Exxon announces record Q4 profits driven by Permian output surge."
_VALID_TICKER = "XOM"
_VALID_BODY = {"headline_text": _VALID_HEADLINE, "ticker": _VALID_TICKER}


@pytest.fixture()
def client():
    """Return a TestClient with invoke_nova_lite replaced by an AsyncMock."""
    mock_invoke = AsyncMock(return_value=_CANNED)
    with patch(_PATCH, mock_invoke):
        # Import after patch so the bound reference in simulate.py is replaced.
        from src.api.simulate import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_preview_happy_path(client):
    """Preview returns 200, phase=preview, sample_size <= 60, >= 6 zip regions."""
    resp = client.post("/simulate/preview", json=_VALID_BODY)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["phase"] == "preview"
    assert 0 < data["sample_size"] <= 60
    regions = {row["zip_region"] for row in data["persona_sentiments"]}
    # 8 regions exist in data/personas.json; stratified sample covers all.
    assert len(regions) >= 6
    assert "region_stats" in data
    assert "parse_failure_rate" in data
    assert "elapsed_ms" in data


def test_full_happy_path(client):
    """Full returns 200, phase=full, sample_size=300, dynamics columns present."""
    resp = client.post("/simulate/full", json=_VALID_BODY)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["phase"] == "full"
    assert data["sample_size"] == 300
    first_row = data["persona_sentiments"][0]
    assert "post_dynamics_0.2" in first_row
    dyn = data["region_stats_dyn"]
    assert "0.2" in dyn
    assert "0.3" in dyn
    assert "0.4" in dyn
    assert "region_stats_raw" in data


def test_invalid_ticker(client):
    """Ticker not in TEXAS_15_TICKERS returns 400 with error=invalid_ticker."""
    resp = client.post(
        "/simulate/preview",
        json={"headline_text": _VALID_HEADLINE, "ticker": "NVDA"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_ticker"


def test_headline_too_short(client):
    """Headline < 20 chars returns 400 with error=headline_too_short."""
    resp = client.post(
        "/simulate/preview",
        json={"headline_text": "Too short.", "ticker": _VALID_TICKER},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "headline_too_short"


def test_stratified_covers_regions():
    """Direct unit test: stratified_sample(personas, 60) covers >= 6 distinct regions."""
    import json
    from pathlib import Path

    from src.api.stratified import stratified_sample

    personas_path = (
        Path(__file__).resolve().parent.parent.parent / "data" / "personas.json"
    )
    personas = json.loads(personas_path.read_text())
    sample = stratified_sample(personas, 60, key="zip_region")
    regions = {p["zip_region"] for p in sample}
    assert len(regions) >= 6
