"""Workstream A2 runner: download prices via yfinance, compute abnormal returns,
apply stage-2 filter.

Usage:
    python -m scripts.run_a2

Reads:
  - data/events_stage1.parquet  (must exist — run scripts.run_yfinance_ingest
    or scripts.run_full_pipeline first)

Writes:
  - data/prices.parquet
  - data/abnormal_returns.parquet
  - data/events.parquet          (stage-1 events that survived stage-2 filter)

Does NOT hit Bedrock — safe to run without AWS credentials.
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from src import config
from src.data.price_ingest import download_prices
from src.data.sentinel_selector import select_sentinels
from src.metrics.abnormal_returns import run_a2_pipeline

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    stage1 = config.DATA_DIR / "events_stage1.parquet"
    if not stage1.exists():
        logger.error(
            "Missing %s. Run scripts.run_yfinance_ingest (or scripts.run_full_pipeline) first.",
            stage1,
        )
        return 2

    logger.info("Downloading prices for %d tickers + market proxy", len(config.TEXAS_15_TICKERS))
    download_prices(
        tickers=[*config.TEXAS_15_TICKERS, config.MARKET_PROXY_TICKER],
        start_date=config.EVENT_WINDOW_START,
        end_date=config.EVENT_WINDOW_END,
    )

    logger.info("Running A2 pipeline: AR computation + stage-2 filter")
    df_events_final, df_ar = run_a2_pipeline(write_parquet=True)

    # Stage-2 filter drops events with null AR (non-trading day / missing price
    # data). Any sentinels selected in stage-1 may have been filtered out. Re-
    # select sentinels from the AR-valid survivors so the sentinel gate has
    # scoreable events.
    df_events_final["is_sentinel"] = False
    df_events_final = select_sentinels(df_events_final)
    df_events_final.to_parquet(config.DATA_DIR / "events.parquet", index=False)

    logger.info(
        "A2 complete: %d events final (post stage-2), %d AR rows, tickers=%d, sentinels=%d",
        len(df_events_final),
        len(df_ar),
        df_events_final["ticker"].nunique(),
        int(df_events_final["is_sentinel"].sum()),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
