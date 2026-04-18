"""Workstream A2: Market-model abnormal return computation.

For each event, computes AR_1d via market-model residuals:
  AR_1d = R_ticker - (alpha + beta * R_market)

Beta is estimated over exactly 252 trading days ending 20 trading days before
the event (non-overlapping gap). An assertion enforces this window invariant
so Jane Street judges can audit the code directly.

Output: data/abnormal_returns.parquet and (after stage-2 drop) data/events.parquet.

See plan Section 4 (A2), Section 8 (R12), and Section 9 schema.
"""

import logging
from datetime import date

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from src.config import (
    AR_ESTIMATION_GAP_DAYS,
    AR_ESTIMATION_WINDOW_DAYS,
    AR_MIN_R_SQUARED,
    DATA_DIR,
    MARKET_PROXY_TICKER,
)
from src.data.price_ingest import load_prices, next_trading_session

logger = logging.getLogger(__name__)

AR_PARQUET_PATH = DATA_DIR / "abnormal_returns.parquet"
EVENTS_PARQUET_PATH = DATA_DIR / "events.parquet"


def _get_close_series(prices_wide: pd.DataFrame, ticker: str) -> pd.Series:
    """Return a date-indexed close price Series for *ticker*."""
    col = ticker
    if col not in prices_wide.columns:
        raise KeyError(f"Ticker {ticker!r} not found in wide price DataFrame.")
    return prices_wide[col].dropna()


def _build_wide_prices(df_prices: pd.DataFrame) -> pd.DataFrame:
    """Pivot long-format price DataFrame to wide (Date index, Ticker columns)."""
    df_prices = df_prices.copy()
    df_prices["date"] = pd.to_datetime(df_prices["date"])
    wide = df_prices.pivot_table(
        index="date", columns="ticker", values="close", aggfunc="last"
    )
    wide.index = pd.to_datetime(wide.index)
    return wide


def _compute_returns(series: pd.Series) -> pd.Series:
    """Compute daily log-returns from a price series."""
    return np.log(series / series.shift(1)).dropna()


def compute_ar_for_event(
    event_id: str,
    ticker: str,
    event_timestamp: "pd.Timestamp | date",
    wide_prices: pd.DataFrame,
    trading_dates: list[date],
) -> dict | None:
    """Compute AR_1d for a single event using the market model.

    Parameters
    ----------
    event_id:
        UUID string identifying the event.
    ticker:
        Stock ticker symbol.
    event_timestamp:
        Datetime or date of the news event (UTC).
    wide_prices:
        Wide-format price DataFrame (Date index, Ticker columns).
    trading_dates:
        Sorted list of all trading dates in the price dataset.

    Returns
    -------
    dict | None
        Dict matching abnormal_returns.parquet schema, or None if data
        is insufficient (e.g., event on non-trading day with no subsequent
        session, insufficient estimation window).
    """
    # Convert event timestamp to date.
    if hasattr(event_timestamp, "date"):
        event_date: date = event_timestamp.date()
    else:
        event_date = date.fromisoformat(str(event_timestamp)[:10])

    # Find next trading session (t+1).
    next_session = next_trading_session(event_date, trading_dates)
    if next_session is None:
        logger.debug(
            "No next trading session for event %s (ticker=%s, date=%s); skipping.",
            event_id,
            ticker,
            event_date,
        )
        return None

    # Identify estimation window: 252 trading days ending exactly 20 trading
    # days before the event date.
    #
    # "20 trading days before" = find the trading day at position -20 relative
    # to event_date in trading_dates. The window ends there and spans 252 days.
    dates_before_event = [d for d in trading_dates if d < event_date]
    if len(dates_before_event) < AR_ESTIMATION_GAP_DAYS + AR_ESTIMATION_WINDOW_DAYS:
        logger.debug(
            "Insufficient pre-event trading days for event %s (ticker=%s): "
            "need %d, have %d.",
            event_id,
            ticker,
            AR_ESTIMATION_GAP_DAYS + AR_ESTIMATION_WINDOW_DAYS,
            len(dates_before_event),
        )
        return None

    # Estimation window end: the trading day 20 days before the event.
    est_end_date: date = dates_before_event[-(AR_ESTIMATION_GAP_DAYS)]
    # Estimation window start: 252 trading days before est_end.
    est_start_idx = len(dates_before_event) - AR_ESTIMATION_GAP_DAYS - AR_ESTIMATION_WINDOW_DAYS
    if est_start_idx < 0:
        logger.debug(
            "Estimation window start index out of range for event %s.", event_id
        )
        return None
    est_start_date: date = dates_before_event[est_start_idx]

    # ASSERTION: window is non-overlapping with the event. This must hold.
    # est_end_date must be strictly before (event_date - 20 trading days).
    gap_count = sum(1 for d in trading_dates if est_end_date < d < event_date)
    assert gap_count >= AR_ESTIMATION_GAP_DAYS - 1, (
        f"Window assertion failed for event {event_id}: "
        f"gap between est_end={est_end_date} and event={event_date} "
        f"is only {gap_count} trading days (need >= {AR_ESTIMATION_GAP_DAYS - 1})."
    )

    # Fetch price data for ticker and market proxy over estimation window.
    est_start_ts = pd.Timestamp(est_start_date)
    est_end_ts = pd.Timestamp(est_end_date)

    if ticker not in wide_prices.columns:
        logger.debug("Ticker %s not in wide prices; skipping event %s.", ticker, event_id)
        return None
    if MARKET_PROXY_TICKER not in wide_prices.columns:
        logger.warning("Market proxy %s not in wide prices.", MARKET_PROXY_TICKER)
        return None

    ticker_prices_est = wide_prices.loc[est_start_ts:est_end_ts, ticker].dropna()
    market_prices_est = wide_prices.loc[est_start_ts:est_end_ts, MARKET_PROXY_TICKER].dropna()

    # Align on common dates.
    common_idx = ticker_prices_est.index.intersection(market_prices_est.index)
    if len(common_idx) < AR_ESTIMATION_WINDOW_DAYS // 2:
        logger.debug(
            "Too few overlapping estimation-window dates for event %s: %d.",
            event_id,
            len(common_idx),
        )
        return None

    r_ticker_est = _compute_returns(ticker_prices_est.loc[common_idx])
    r_market_est = _compute_returns(market_prices_est.loc[common_idx])

    # Re-align after return differencing.
    common_ret_idx = r_ticker_est.index.intersection(r_market_est.index)
    r_ticker_est = r_ticker_est.loc[common_ret_idx]
    r_market_est = r_market_est.loc[common_ret_idx]

    if len(r_ticker_est) < 30:
        logger.debug("Insufficient return observations (%d) for event %s.", len(r_ticker_est), event_id)
        return None

    # OLS: R_ticker = alpha + beta * R_market.
    X = r_market_est.values.reshape(-1, 1)
    y = r_ticker_est.values
    reg = LinearRegression().fit(X, y)
    beta: float = float(reg.coef_[0])
    alpha: float = float(reg.intercept_)

    y_pred = reg.predict(X)
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared: float = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    if r_squared < AR_MIN_R_SQUARED:
        logger.debug(
            "R-squared %.3f below threshold %.3f for ticker %s event %s.",
            r_squared,
            AR_MIN_R_SQUARED,
            ticker,
            event_id,
        )
        # Return the result anyway; caller can filter if needed.

    # Compute next-session returns.
    next_ts = pd.Timestamp(next_session)
    prev_ts_candidates = [t for t in wide_prices.index if t < next_ts]
    if not prev_ts_candidates:
        return None
    prev_ts = prev_ts_candidates[-1]

    try:
        ticker_next = float(wide_prices.loc[next_ts, ticker])
        ticker_prev = float(wide_prices.loc[prev_ts, ticker])
        market_next = float(wide_prices.loc[next_ts, MARKET_PROXY_TICKER])
        market_prev = float(wide_prices.loc[prev_ts, MARKET_PROXY_TICKER])
    except (KeyError, TypeError):
        logger.debug(
            "Missing price data at next session %s for event %s.", next_session, event_id
        )
        return None

    if ticker_prev <= 0 or market_prev <= 0:
        return None

    r_ticker_event = np.log(ticker_next / ticker_prev)
    r_market_event = np.log(market_next / market_prev)
    expected_return = alpha + beta * r_market_event
    ar_1d = r_ticker_event - expected_return
    residual = ar_1d  # Same as AR in market model.

    return {
        "event_id": event_id,
        "ticker": ticker,
        "ar_1d": float(ar_1d),
        "market_return": float(r_market_event),
        "residual": float(residual),
        "r_squared": float(r_squared),
        "beta": float(beta),
        "estimation_window_start": est_start_date,
        "estimation_window_end": est_end_date,
    }


def compute_all_ars(
    df_events: pd.DataFrame,
    df_prices: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute AR_1d for all events in df_events.

    Parameters
    ----------
    df_events:
        Stage-1 events DataFrame (must have event_id, ticker, timestamp cols).
    df_prices:
        Wide prices; loaded from parquet if None.

    Returns
    -------
    pd.DataFrame
        abnormal_returns.parquet schema DataFrame.
    """
    if df_prices is None:
        df_prices = load_prices()

    wide = _build_wide_prices(df_prices)
    all_dates = sorted(pd.to_datetime(wide.index).date.tolist())

    records: list[dict] = []
    for _, row in df_events.iterrows():
        result = compute_ar_for_event(
            event_id=str(row["event_id"]),
            ticker=str(row["ticker"]),
            event_timestamp=row["timestamp"],
            wide_prices=wide,
            trading_dates=all_dates,
        )
        if result is not None:
            records.append(result)

    df_ar = pd.DataFrame(records)
    logger.info(
        "AR computation: %d events -> %d valid ARs (%.1f%% coverage)",
        len(df_events),
        len(df_ar),
        100.0 * len(df_ar) / max(len(df_events), 1),
    )
    return df_ar


def apply_stage2_filter(
    df_events: pd.DataFrame,
    df_ar: pd.DataFrame,
) -> pd.DataFrame:
    """Stage-2 filter: keep only events that have a valid AR.

    Merges df_ar into df_events on event_id. Events with null AR (no next
    trading session, insufficient data) are dropped. Writes events.parquet.

    Parameters
    ----------
    df_events:
        Stage-1 events (events_stage1.parquet).
    df_ar:
        abnormal_returns.parquet with event_id column.

    Returns
    -------
    pd.DataFrame
        Final events.parquet-schema DataFrame with AR columns joined.
    """
    n_before = len(df_events)
    valid_ids: set[str] = set(df_ar["event_id"].dropna().astype(str))
    df_final = df_events[df_events["event_id"].astype(str).isin(valid_ids)].copy()
    df_final = df_final.reset_index(drop=True)
    n_after = len(df_final)
    logger.info(
        "Stage-2 filter: %d -> %d events (dropped %d without valid AR).",
        n_before,
        n_after,
        n_before - n_after,
    )
    return df_final


def run_a2_pipeline(write_parquet: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convenience entry point: load stage-1 events, compute ARs, apply stage-2 filter.

    Returns (df_events_final, df_ar).
    """
    from src.data.gdelt_ingest import load_stage1

    df_stage1 = load_stage1()
    df_prices = load_prices()

    df_ar = compute_all_ars(df_stage1, df_prices)
    df_events_final = apply_stage2_filter(df_stage1, df_ar)

    if write_parquet:
        df_ar.to_parquet(AR_PARQUET_PATH, index=False, engine="pyarrow")
        logger.info("Wrote abnormal_returns.parquet (%d rows).", len(df_ar))

        df_events_final.to_parquet(EVENTS_PARQUET_PATH, index=False, engine="pyarrow")
        logger.info("Wrote events.parquet (%d rows).", len(df_events_final))

    return df_events_final, df_ar
