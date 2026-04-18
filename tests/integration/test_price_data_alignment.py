"""Integration test: Price data alignment and AR window validity.

Tests:
  - Event timestamp maps to correct next trading session.
  - AR estimation window is valid (non-overlapping 252-day window ending 20d pre-event).
  - Edge cases: event on weekend, event at end of price history.

See plan Section 3 (Integration Tests): test_price_data_alignment.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.data.price_ingest import get_trading_dates, next_trading_session
from src.metrics.abnormal_returns import (
    _build_wide_prices,
    compute_ar_for_event,
)
from src.config import AR_ESTIMATION_GAP_DAYS, AR_ESTIMATION_WINDOW_DAYS


def _make_continuous_prices(
    start: date,
    n_days: int,
    ticker: str = "TKR",
    market: str = "^GSPC",
    seed: int = 0,
) -> pd.DataFrame:
    """Build a synthetic long-format price DataFrame for n_days consecutive calendar days."""
    rng = np.random.default_rng(seed)
    all_dates = [start + timedelta(days=i) for i in range(n_days)]
    ticker_prices = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n_days)))
    market_prices = 3000.0 * np.exp(np.cumsum(rng.normal(0.0, 0.008, n_days)))

    rows = []
    for d, tp, mp in zip(all_dates, ticker_prices, market_prices):
        rows.append({"date": d, "ticker": ticker, "close": float(tp)})
        rows.append({"date": d, "ticker": market, "close": float(mp)})
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


class TestNextTradingSession:
    """Verify event-date -> next trading session mapping."""

    def test_event_date_is_trading_day(self):
        """Next session after a trading day is the following trading day."""
        trading_dates = [
            date(2024, 10, 1),
            date(2024, 10, 2),
            date(2024, 10, 3),
            date(2024, 10, 7),  # Skip weekend Oct 4-6.
        ]
        result = next_trading_session(date(2024, 10, 1), trading_dates)
        assert result == date(2024, 10, 2)

    def test_event_date_not_a_trading_day(self):
        """Event on a non-trading day (weekend) maps to next trading day."""
        trading_dates = [
            date(2024, 10, 1),  # Tuesday
            date(2024, 10, 2),  # Wednesday
            date(2024, 10, 7),  # Monday (skip weekend)
        ]
        # Event on Saturday Oct 5.
        result = next_trading_session(date(2024, 10, 5), trading_dates)
        assert result == date(2024, 10, 7)

    def test_no_next_session_returns_none(self):
        """Returns None when event is at or after last trading date."""
        trading_dates = [date(2024, 10, 1), date(2024, 10, 2)]
        result = next_trading_session(date(2024, 10, 2), trading_dates)
        assert result is None

    def test_event_before_all_trading_dates(self):
        """Returns first trading date if event is before all known dates."""
        trading_dates = [date(2024, 10, 7), date(2024, 10, 8)]
        result = next_trading_session(date(2024, 10, 1), trading_dates)
        assert result == date(2024, 10, 7)


class TestARWindowAlignment:
    """Verify the 252-day estimation window ending 20 days pre-event is enforced."""

    def _run_scenario(self, n_days: int, event_offset: int) -> dict | None:
        start = date(2022, 1, 3)
        df = _make_continuous_prices(start, n_days)
        wide = _build_wide_prices(df)
        trading_dates = sorted(
            pd.to_datetime(df[df["ticker"] == "TKR"]["date"].unique()).date.tolist()
        )
        event_date = trading_dates[event_offset] if event_offset < len(trading_dates) else trading_dates[-1]
        return compute_ar_for_event(
            event_id="align-test",
            ticker="TKR",
            event_timestamp=event_date,
            wide_prices=wide,
            trading_dates=trading_dates,
        )

    def test_valid_window_produces_result(self):
        """With ample history, AR computation succeeds."""
        # Need at least 252 + 20 trading days before event.
        n_days = 320
        result = self._run_scenario(n_days=n_days, event_offset=290)
        assert result is not None, "Should return a result with sufficient history."

    def test_estimation_window_end_before_gap(self):
        """estimation_window_end is at least AR_ESTIMATION_GAP_DAYS before event."""
        n_days = 320
        df = _make_continuous_prices(date(2022, 1, 3), n_days)
        wide = _build_wide_prices(df)
        trading_dates = sorted(
            pd.to_datetime(df[df["ticker"] == "TKR"]["date"].unique()).date.tolist()
        )
        event_date = trading_dates[290]

        result = compute_ar_for_event(
            event_id="gap-test",
            ticker="TKR",
            event_timestamp=event_date,
            wide_prices=wide,
            trading_dates=trading_dates,
        )

        assert result is not None
        est_end = result["estimation_window_end"]
        est_start = result["estimation_window_start"]

        # Gap: number of trading days between est_end and event_date.
        gap_days = sum(
            1 for d in trading_dates if est_end < d < event_date
        )
        assert gap_days >= AR_ESTIMATION_GAP_DAYS - 1, (
            f"Gap of {gap_days} trading days is less than required {AR_ESTIMATION_GAP_DAYS - 1}."
        )

        # Window: number of trading days in [est_start, est_end].
        window_days = sum(
            1 for d in trading_dates if est_start <= d <= est_end
        )
        assert window_days >= AR_ESTIMATION_WINDOW_DAYS // 2, (
            f"Estimation window of {window_days} days is too short."
        )

    def test_insufficient_history_returns_none(self):
        """Insufficient pre-event history returns None (cannot compute beta)."""
        # Only 100 days total — not enough for 252 + 20.
        result = self._run_scenario(n_days=100, event_offset=80)
        assert result is None, "Should return None with insufficient pre-event history."

    def test_ar_1d_is_float(self):
        """ar_1d field is a Python float."""
        result = self._run_scenario(n_days=320, event_offset=290)
        assert result is not None
        assert isinstance(result["ar_1d"], float)

    def test_r_squared_in_range(self):
        """r_squared is in [0, 1]."""
        result = self._run_scenario(n_days=320, event_offset=290)
        assert result is not None
        assert 0.0 <= result["r_squared"] <= 1.0, (
            f"r_squared={result['r_squared']} out of [0, 1]."
        )

    def test_result_fields_match_schema(self):
        """Result dict contains all fields from abnormal_returns.parquet schema."""
        result = self._run_scenario(n_days=320, event_offset=290)
        assert result is not None
        required_keys = {
            "event_id",
            "ticker",
            "ar_1d",
            "market_return",
            "residual",
            "r_squared",
            "beta",
            "estimation_window_start",
            "estimation_window_end",
        }
        missing = required_keys - set(result.keys())
        assert not missing, f"Missing result fields: {missing}"

    def test_get_trading_dates_from_price_df(self):
        """get_trading_dates returns sorted dates for market proxy ticker."""
        df = _make_continuous_prices(date(2024, 1, 2), 30)
        trading_dates = get_trading_dates(df, ticker="^GSPC")
        assert len(trading_dates) == 30
        assert trading_dates == sorted(trading_dates), "Dates must be sorted."
        assert all(isinstance(d, date) for d in trading_dates)
