"""Unit tests for abnormal return computation (Workstream A2).

Tests: test_abnormal_return_computation — Market-model residual matches
hand-calculated AR for 3 synthetic events with known prices and market returns.

See plan Section 3 (Unit Tests) and Section 4 (A2 exit criteria).
"""

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.metrics.abnormal_returns import (
    _build_wide_prices,
    _compute_returns,
    compute_ar_for_event,
)


def _make_price_df(
    ticker: str,
    market: str,
    ticker_prices: list[float],
    market_prices: list[float],
    start_date: date,
) -> pd.DataFrame:
    """Build a long-format price DataFrame for testing."""
    n = len(ticker_prices)
    dates = [start_date + timedelta(days=i) for i in range(n)]
    rows = []
    for d, tp, mp in zip(dates, ticker_prices, market_prices):
        rows.append({"date": d, "ticker": ticker, "close": tp})
        rows.append({"date": d, "ticker": market, "close": mp})
    return pd.DataFrame(rows)


def _make_synthetic_scenario(
    beta: float,
    alpha: float,
    n_estimation: int = 260,
    n_gap: int = 20,
) -> tuple[pd.DataFrame, list[date], date]:
    """Construct a synthetic price scenario with known beta.

    Returns (df_prices, trading_dates, event_date).
    Prices are generated so OLS will recover approximately *beta* and *alpha*.
    """
    rng = np.random.default_rng(42)
    start = date(2022, 1, 3)

    # Generate market returns from N(0, 0.01).
    market_rets = rng.normal(0.0, 0.01, n_estimation + n_gap + 5)
    # Generate ticker returns as alpha + beta * market_ret + small noise.
    ticker_rets = alpha + beta * market_rets + rng.normal(0.0, 0.002, len(market_rets))

    # Convert returns to prices (cumulative log-return).
    market_prices = 100.0 * np.exp(np.concatenate([[0.0], np.cumsum(market_rets)]))
    ticker_prices = 50.0 * np.exp(np.concatenate([[0.0], np.cumsum(ticker_rets)]))

    all_dates = [start + timedelta(days=i) for i in range(len(market_prices))]

    df = _make_price_df("TKR", "^GSPC", list(ticker_prices), list(market_prices), start)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    # event_date is at position n_estimation + n_gap (0-indexed: after estimation window + gap).
    event_date = all_dates[n_estimation + n_gap]

    return df, all_dates, event_date


class TestAbnormalReturnComputation:
    """test_abnormal_return_computation: hand-verified AR for 3 synthetic events."""

    # ---------------------------------------------------------------------------
    # Scenario 1: beta = 1.0, no alpha drift
    # ---------------------------------------------------------------------------
    def test_scenario_1_beta_one_alpha_zero(self):
        """With beta=1.0 and alpha=0, AR should be near zero for a normal market day."""
        df_prices, all_dates, event_date = _make_synthetic_scenario(beta=1.0, alpha=0.0)

        wide = _build_wide_prices(df_prices)
        trading_dates = sorted(pd.to_datetime(df_prices["date"].unique()).date.tolist())

        result = compute_ar_for_event(
            event_id="test-event-1",
            ticker="TKR",
            event_timestamp=event_date,
            wide_prices=wide,
            trading_dates=trading_dates,
        )

        assert result is not None, "Should compute AR for scenario 1."
        assert result["event_id"] == "test-event-1"
        assert result["ticker"] == "TKR"
        assert -1.0 <= result["ar_1d"] <= 1.0, f"AR out of range: {result['ar_1d']}"
        # With beta~1.0 and alpha~0, residual should be small (noise only).
        assert abs(result["ar_1d"]) < 0.15, (
            f"AR {result['ar_1d']} should be small for beta=1, alpha=0 scenario."
        )
        # Beta should be estimated close to 1.0.
        assert 0.5 <= result["beta"] <= 1.5, f"Beta {result['beta']} far from 1.0."
        # R-squared should be reasonable given known linear relationship.
        assert result["r_squared"] > 0.0

    # ---------------------------------------------------------------------------
    # Scenario 2: beta = 1.5 (high beta stock)
    # ---------------------------------------------------------------------------
    def test_scenario_2_high_beta(self):
        """Estimated beta should be close to 1.5 for a high-beta stock."""
        df_prices, all_dates, event_date = _make_synthetic_scenario(beta=1.5, alpha=0.0)

        wide = _build_wide_prices(df_prices)
        trading_dates = sorted(pd.to_datetime(df_prices["date"].unique()).date.tolist())

        result = compute_ar_for_event(
            event_id="test-event-2",
            ticker="TKR",
            event_timestamp=event_date,
            wide_prices=wide,
            trading_dates=trading_dates,
        )

        assert result is not None, "Should compute AR for scenario 2."
        assert 1.0 <= result["beta"] <= 2.0, (
            f"Estimated beta {result['beta']} should be near 1.5."
        )
        # AR should still be bounded.
        assert -1.0 <= result["ar_1d"] <= 1.0

    # ---------------------------------------------------------------------------
    # Scenario 3: hand-computed AR with exact known prices
    # ---------------------------------------------------------------------------
    def test_scenario_3_hand_computed_ar(self):
        """Manually constructed example with known AR.

        Setup:
          - 280 trading days of prices (252 estimation + 20 gap + 8 extra).
          - Ticker and market move in lockstep (beta=1, alpha=0) during estimation.
          - On event+1 day: market_ret = +0.01, ticker_ret = +0.05.
          - Expected AR = ticker_ret - (alpha + beta * market_ret)
                       = 0.05 - (0 + 1.0 * 0.01) = 0.04 (approx, before OLS error).
        """
        n_est = 260
        n_gap = 20
        start = date(2022, 1, 3)

        # Perfect beta=1 during estimation window.
        market_est = list(100.0 * np.exp(np.linspace(0, 0.1, n_est + n_gap + 1)))
        ticker_est = list(50.0 * np.exp(np.linspace(0, 0.1, n_est + n_gap + 1)))

        # Append an event+1 day with known returns.
        # market: +1%, ticker: +5%
        market_est.append(market_est[-1] * 1.01)
        ticker_est.append(ticker_est[-1] * 1.05)

        all_dates = [start + timedelta(days=i) for i in range(len(market_est))]
        event_date = all_dates[n_est + n_gap]  # The "event" day.

        df = _make_price_df("TKR", "^GSPC", ticker_est, market_est, start)
        df["date"] = pd.to_datetime(df["date"]).dt.date

        wide = _build_wide_prices(df)
        trading_dates = sorted(pd.to_datetime(df["date"].unique()).date.tolist())

        result = compute_ar_for_event(
            event_id="test-event-3",
            ticker="TKR",
            event_timestamp=event_date,
            wide_prices=wide,
            trading_dates=trading_dates,
        )

        assert result is not None, "Should compute AR for scenario 3."

        # Market return on event+1 day.
        mkt_ret = math.log(1.01)  # ~0.00995
        # Ticker return on event+1 day.
        tkr_ret = math.log(1.05)  # ~0.04879
        # Expected AR ≈ tkr_ret - beta * mkt_ret (alpha ≈ 0 for linear prices).
        expected_ar_approx = tkr_ret - 1.0 * mkt_ret  # ~0.0388

        assert abs(result["market_return"] - mkt_ret) < 0.001, (
            f"Market return {result['market_return']} != expected {mkt_ret:.4f}"
        )
        # AR should be close to expected (within estimation noise tolerance).
        assert abs(result["ar_1d"] - expected_ar_approx) < 0.02, (
            f"AR {result['ar_1d']:.4f} deviates from hand-calc {expected_ar_approx:.4f} by "
            f"{abs(result['ar_1d'] - expected_ar_approx):.4f} (tolerance 0.02)."
        )

    # ---------------------------------------------------------------------------
    # Estimation window invariant assertions
    # ---------------------------------------------------------------------------
    def test_estimation_window_fields_present(self):
        """Result contains estimation_window_start and estimation_window_end."""
        df_prices, _, event_date = _make_synthetic_scenario(beta=1.0, alpha=0.0)
        wide = _build_wide_prices(df_prices)
        trading_dates = sorted(pd.to_datetime(df_prices["date"].unique()).date.tolist())

        result = compute_ar_for_event(
            event_id="test-window",
            ticker="TKR",
            event_timestamp=event_date,
            wide_prices=wide,
            trading_dates=trading_dates,
        )

        assert result is not None
        assert "estimation_window_start" in result
        assert "estimation_window_end" in result
        # Window end must be strictly before event date.
        assert result["estimation_window_end"] < event_date, (
            "Estimation window end must precede event date (non-overlapping gap)."
        )

    def test_insufficient_history_returns_none(self):
        """Returns None when there are fewer trading days than required."""
        # Only 10 days of price data — far too little.
        start = date(2024, 1, 2)
        dates = [start + timedelta(days=i) for i in range(10)]
        rows = []
        for d in dates:
            rows.append({"date": d, "ticker": "TKR", "close": 100.0})
            rows.append({"date": d, "ticker": "^GSPC", "close": 200.0})
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"]).dt.date

        wide = _build_wide_prices(df)
        trading_dates = sorted(pd.to_datetime(df["date"].unique()).date.tolist())

        result = compute_ar_for_event(
            event_id="test-insufficient",
            ticker="TKR",
            event_timestamp=dates[5],
            wide_prices=wide,
            trading_dates=trading_dates,
        )
        assert result is None, "Should return None with insufficient history."

    def test_compute_returns_log_returns(self):
        """_compute_returns returns log-returns."""
        prices = pd.Series([100.0, 110.0, 99.0])
        rets = _compute_returns(prices)
        assert len(rets) == 2
        assert abs(rets.iloc[0] - math.log(110.0 / 100.0)) < 1e-10
        assert abs(rets.iloc[1] - math.log(99.0 / 110.0)) < 1e-10
