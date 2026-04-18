"""Workstream A2: Daily OHLCV price ingest via yfinance.

Downloads daily bars for all Texas-15 tickers plus the S&P 500 proxy (^GSPC).
Date range extends 2 years before EVENT_WINDOW_START (for beta estimation) through
EVENT_WINDOW_END. Output: data/prices.parquet.

See plan Section 4 (A2) and Section 9 (abnormal_returns.parquet schema).
"""

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from src.config import (
    AR_ESTIMATION_WINDOW_DAYS,
    DATA_DIR,
    EVENT_WINDOW_END,
    EVENT_WINDOW_START,
    MARKET_PROXY_TICKER,
    TEXAS_15_TICKERS,
)

logger = logging.getLogger(__name__)

PRICES_PARQUET_PATH = DATA_DIR / "prices.parquet"

# 2 calendar years before EVENT_WINDOW_START to give ample trading-day buffer
# for 252-trading-day beta windows.
_CALENDAR_YEARS_BUFFER = 2


def _beta_estimation_start(event_window_start: str) -> str:
    """Return the download start date (2 years before event window start)."""
    start = date.fromisoformat(event_window_start)
    # 2 years = ~730 days; use 800 for safety margin.
    extended = start - timedelta(days=800)
    return extended.isoformat()


def download_prices(
    tickers: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    write_parquet: bool = True,
) -> pd.DataFrame:
    """Download daily adjusted close prices for all tickers.

    Parameters
    ----------
    tickers:
        Ticker list including market proxy; defaults to TEXAS_15_TICKERS + [^GSPC].
    start_date:
        ISO date; defaults to 2 years before EVENT_WINDOW_START.
    end_date:
        ISO date; defaults to EVENT_WINDOW_END.
    write_parquet:
        If True, write to data/prices.parquet.

    Returns
    -------
    pd.DataFrame
        MultiIndex DataFrame with (Date, Ticker) index and columns:
        Open, High, Low, Close, Volume, Adj_Close.
        (Long format for parquet compatibility.)
    """
    tickers = tickers or (TEXAS_15_TICKERS + [MARKET_PROXY_TICKER])
    start_date = start_date or _beta_estimation_start(EVENT_WINDOW_START)
    end_date = end_date or EVENT_WINDOW_END

    logger.info(
        "Downloading prices for %d tickers from %s to %s",
        len(tickers),
        start_date,
        end_date,
    )

    raw = yf.download(
        tickers=tickers,
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    if raw.empty:
        raise RuntimeError("yfinance returned empty DataFrame for all tickers.")

    # yfinance returns a MultiIndex columns: (field, ticker).
    # Melt to long format: Date, Ticker, Open, High, Low, Close, Volume.
    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                tkr_df = raw.xs(ticker, axis=1, level=1).copy()
            else:
                # Single ticker edge case.
                tkr_df = raw.copy()
            tkr_df = tkr_df.rename(columns=str)
            tkr_df["Ticker"] = ticker
            tkr_df.index.name = "Date"
            frames.append(tkr_df.reset_index())
        except KeyError:
            logger.warning("No price data for ticker %s; skipping.", ticker)

    if not frames:
        raise RuntimeError("No valid price data returned for any ticker.")

    df = pd.concat(frames, ignore_index=True)

    # Standardise column names.
    col_map = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    df = df.rename(columns=col_map)
    df["date"] = pd.to_datetime(df["Date"]).dt.date
    df["ticker"] = df["Ticker"]

    keep_cols = ["date", "ticker", "open", "high", "low", "close", "volume"]
    existing = [c for c in keep_cols if c in df.columns]
    df = df[existing].dropna(subset=["close"])

    logger.info("Price download complete: %d rows across %d tickers.", len(df), df["ticker"].nunique())

    if write_parquet:
        df.to_parquet(PRICES_PARQUET_PATH, index=False, engine="pyarrow")
        logger.info("Wrote prices.parquet (%d rows) to %s", len(df), PRICES_PARQUET_PATH)

    return df


def load_prices() -> pd.DataFrame:
    """Load prices.parquet. Raises FileNotFoundError if not yet generated."""
    if not PRICES_PARQUET_PATH.exists():
        raise FileNotFoundError(
            f"prices.parquet not found at {PRICES_PARQUET_PATH}. "
            "Run download_prices() first."
        )
    df = pd.read_parquet(PRICES_PARQUET_PATH, engine="pyarrow")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def get_trading_dates(df_prices: pd.DataFrame, ticker: str | None = None) -> list[date]:
    """Return sorted list of trading dates present in the price DataFrame."""
    if ticker:
        subset = df_prices[df_prices["ticker"] == ticker]
    else:
        # Use market proxy for universal trading calendar.
        subset = df_prices[df_prices["ticker"] == MARKET_PROXY_TICKER]
        if subset.empty:
            subset = df_prices
    return sorted(pd.to_datetime(subset["date"]).dt.date.unique().tolist())


def next_trading_session(
    event_date: date, trading_dates: list[date]
) -> date | None:
    """Return the first trading date strictly after *event_date*.

    Returns None if no subsequent trading session exists in *trading_dates*.
    """
    for td in trading_dates:
        if td > event_date:
            return td
    return None
