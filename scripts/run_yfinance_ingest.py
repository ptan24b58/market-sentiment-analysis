"""Quick bootstrap: yfinance news → events_stage1.parquet (GDELT-free).

Use when GDELT's public API is rate-limiting your IP. Plan R2 mitigation.

Usage:
    python -m scripts.run_yfinance_ingest

After this, run A2 (price + AR + stage-2 filter) + sentinel normally.
"""

from __future__ import annotations

import logging
import sys

from src import config
from src.data.event_filter import apply_stage1_filter_relaxed
from src.data.sentinel_selector import select_sentinels
from src.data.yfinance_news_ingest import ingest_yfinance_news

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    df = ingest_yfinance_news(write_parquet=False)
    if df.empty:
        logger.error("yfinance returned zero events; check network/yfinance version")
        return 2

    # yfinance gdelt_tone is heuristic; skip the |tone|>2 filter but keep
    # dedup + sentinel selection. We use a relaxed filter that only checks
    # non-null headline + non-null timestamp + ticker.
    before = len(df)
    df = apply_stage1_filter_relaxed(df)
    logger.info("After relaxed stage-1 filter: %d (was %d)", len(df), before)

    df = select_sentinels(df)
    sentinel_count = int(df["is_sentinel"].sum())
    logger.info("Total: %d events | Sentinels: %d | Tickers: %d",
                len(df), sentinel_count, df["ticker"].nunique())

    out = config.DATA_DIR / "events_stage1.parquet"
    df.to_parquet(out, index=False)
    logger.info("Wrote %d events to %s", len(df), out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
