"""Integration test: GDELT ingest -> stage-1 filter produces >= 1 event for TSLA.

Uses monkeypatched requests to avoid live API calls. The mock returns a
pre-built fixture response with 3 TSLA articles.

See plan Section 3 (Integration Tests): test_gdelt_to_event_set.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


import src.data.gdelt_ingest as _gdelt_mod

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture() -> dict:
    body_path = FIXTURES_DIR / "gdelt_mock_response.json"
    with body_path.open() as fh:
        return json.load(fh)


def _make_mock_response(body: dict | None = None) -> MagicMock:
    """Build a mock requests.Response-like object."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=body or _load_fixture())
    return mock_resp


class TestGdeltToEventSet:
    """test_gdelt_to_event_set: mocked GDELT produces >= 1 event for TSLA."""

    def test_produces_tsla_events_with_mock(self, tmp_path, monkeypatch):
        """GDELT ingest with mocked HTTP produces at least 1 event for TSLA."""
        monkeypatch.setattr(_gdelt_mod, "DATA_DIR", tmp_path)

        mock_resp = _make_mock_response()

        with patch("requests.Session.get", return_value=mock_resp):
            df = _gdelt_mod.ingest_gdelt(
                tickers=["TSLA"],
                start_date="2024-10-01",
                end_date="2025-01-01",
                write_parquet=False,
            )

        assert len(df) >= 1, (
            f"Expected >= 1 event for TSLA, got {len(df)}."
        )
        assert "TSLA" in df["ticker"].values, "TSLA should appear as a ticker."

    def test_event_schema_correct(self, tmp_path, monkeypatch):
        """Events produced by ingest have all required schema columns."""
        monkeypatch.setattr(_gdelt_mod, "DATA_DIR", tmp_path)

        with patch("requests.Session.get", return_value=_make_mock_response()):
            df = _gdelt_mod.ingest_gdelt(
                tickers=["TSLA"],
                start_date="2024-10-01",
                end_date="2025-01-01",
                write_parquet=False,
            )

        required_cols = {
            "event_id",
            "headline_text",
            "source_url",
            "ticker",
            "timestamp",
            "gdelt_tone",
            "gdelt_theme_tags",
            "entity_tags",
            "is_sentinel",
        }
        missing = required_cols - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_no_duplicate_event_ids(self, tmp_path, monkeypatch):
        """event_id column must be unique (no duplicate UUIDs)."""
        monkeypatch.setattr(_gdelt_mod, "DATA_DIR", tmp_path)

        with patch("requests.Session.get", return_value=_make_mock_response()):
            df = _gdelt_mod.ingest_gdelt(
                tickers=["TSLA"],
                start_date="2024-10-01",
                end_date="2025-01-01",
                write_parquet=False,
            )

        if len(df) > 0:
            assert df["event_id"].is_unique, "event_id values must be unique."

    def test_stage1_filter_applied(self, tmp_path, monkeypatch):
        """Events returned from ingest have abs(gdelt_tone) > 2.0 (stage-1 filter)."""
        monkeypatch.setattr(_gdelt_mod, "DATA_DIR", tmp_path)

        with patch("requests.Session.get", return_value=_make_mock_response()):
            df = _gdelt_mod.ingest_gdelt(
                tickers=["TSLA"],
                start_date="2024-10-01",
                end_date="2025-01-01",
                write_parquet=False,
            )

        if len(df) > 0:
            assert (df["gdelt_tone"].abs() > 2.0).all(), (
                "All stage-1 events must have |tone| > 2.0."
            )

    def test_rate_limit_retry_on_429(self, tmp_path, monkeypatch):
        """On HTTP 429, ingest retries and eventually succeeds."""
        monkeypatch.setattr(_gdelt_mod, "DATA_DIR", tmp_path)
        # Speed up backoff for tests.
        monkeypatch.setattr(_gdelt_mod, "_BACKOFF_BASE", 0.01)

        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.raise_for_status = MagicMock()

        mock_ok = _make_mock_response()
        responses = [mock_429, mock_ok]
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            idx = min(call_count["n"], len(responses) - 1)
            call_count["n"] += 1
            return responses[idx]

        with patch("requests.Session.get", side_effect=side_effect):
            _ = _gdelt_mod.ingest_gdelt(
                tickers=["TSLA"],
                start_date="2024-10-01",
                end_date="2025-01-01",
                write_parquet=False,
            )

        # At least two calls: the 429 and one successful retry.
        assert call_count["n"] >= 2, "Expected at least 2 calls (1 retry after 429)."
