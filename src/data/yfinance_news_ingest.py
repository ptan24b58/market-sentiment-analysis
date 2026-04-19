"""Workstream A1 fallback: Yahoo Finance news ingest when GDELT is rate-limited.

Plan R2 mitigation: "if raw GDELT pull < 40 events, immediately widen to Yahoo
Finance ticker-news RSS as secondary source."

Produces the same `data/events_stage1.parquet` schema as `gdelt_ingest.py`, so
the downstream pipeline (event_filter → sentinel_selector → A2 AR → B3/B5
sentinel+persona) is unchanged. Coverage is typically the past ~4 weeks of
per-ticker news, which is narrower than GDELT's window but sufficient for demo
validation.

Differences from GDELT schema:
  - `gdelt_tone` is approximated via a headline length heuristic OR left at 0.0
    (the event_filter stage-1 threshold is bypassed for yfinance events via a
    config override). `sentinel_selector` still picks by |approximated_tone|.
  - `gdelt_theme_tags` is derived from Yahoo article type / publisher heuristics.
  - `entity_tags` is just `[ticker]`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from src import config

logger = logging.getLogger(__name__)


_POLARIZING_KEYWORDS = {
    "esg": ["climate", "emissions", "environment", "spill", "pollution", "carbon", "green"],
    "political": ["biden", "trump", "congress", "tariff", "sanction", "regulation", "policy"],
    "policy": ["sec", "fed", "ftc", "antitrust", "lawsuit", "fine", "settlement"],
}


def _classify_themes(title: str, summary: str) -> list[str]:
    """Heuristic theme tagging from headline + summary text."""
    text = f"{title} {summary}".lower()
    themes: list[str] = []
    for theme, keywords in _POLARIZING_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            themes.append(theme)
    if not themes:
        themes.append("general")
    return themes


def _estimate_tone(title: str) -> float:
    """Crude tone estimate from headline word counts.

    Not a real GDELT tone — just enough to let sentinel_selector pick the
    most-opinionated-looking headlines. Counts positive/negative cue words.
    """
    positive = {"beats", "surges", "gains", "record", "profit", "growth", "upgrade", "strong"}
    negative = {"falls", "drops", "loss", "decline", "fine", "lawsuit", "fraud", "crash", "plunge"}
    tokens = set(title.lower().split())
    pos_hits = len(tokens & positive)
    neg_hits = len(tokens & negative)
    if pos_hits + neg_hits == 0:
        return 0.0
    return (pos_hits - neg_hits) * 3.0


def _article_to_event(art: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    """Normalize a yfinance news entry to the events_stage1 schema."""
    content = art.get("content") or art
    title = content.get("title") or art.get("title")
    if not title:
        return None
    summary = content.get("summary") or art.get("summary") or ""
    link_dict = content.get("canonicalUrl") or {}
    url = link_dict.get("url") if isinstance(link_dict, dict) else (art.get("link") or "")
    pub_date = content.get("pubDate") or art.get("providerPublishTime")
    if isinstance(pub_date, (int, float)):
        ts = datetime.fromtimestamp(pub_date, tz=timezone.utc)
    elif isinstance(pub_date, str):
        try:
            ts = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
        except ValueError:
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    return {
        "event_id": str(uuid.uuid4()),
        "headline_text": title,
        "source_url": url or "",
        "ticker": ticker,
        "timestamp": ts,
        "gdelt_tone": _estimate_tone(title),
        "gdelt_theme_tags": _classify_themes(title, summary),
        "entity_tags": [ticker],
        "is_sentinel": False,
    }


def ingest_yfinance_news(
    tickers: list[str] | None = None,
    write_parquet: bool = True,
) -> pd.DataFrame:
    """Pull recent news for each ticker from yfinance and normalize to the
    events_stage1 schema.

    Parameters
    ----------
    tickers : list[str], optional
        Ticker universe. Defaults to `config.TEXAS_15_TICKERS`.
    write_parquet : bool
        If True, also writes to `data/events_stage1.parquet`.

    Returns
    -------
    pd.DataFrame
        Same columns as `events_stage1.parquet` output of `gdelt_ingest`.
    """
    tickers = tickers or config.TEXAS_15_TICKERS
    events: list[dict[str, Any]] = []

    for ticker in tickers:
        try:
            news = yf.Ticker(ticker).news
        except Exception as exc:  # noqa: BLE001
            logger.warning("yfinance failed for %s: %s", ticker, exc)
            continue

        logger.info("Fetched %d news items for %s", len(news), ticker)
        for art in news:
            ev = _article_to_event(art, ticker)
            if ev is not None:
                events.append(ev)

    df = pd.DataFrame(events)
    if df.empty:
        logger.warning("No events from yfinance across %d tickers", len(tickers))
        return df

    # Drop duplicate headlines for the same ticker.
    df = df.drop_duplicates(subset=["ticker", "headline_text"], keep="first").reset_index(drop=True)
    logger.info("Total yfinance events after dedup: %d", len(df))

    if write_parquet:
        out = config.DATA_DIR / "events_stage1.parquet"
        df.to_parquet(out, index=False)
        logger.info("Wrote %d events to %s", len(df), out)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    ingest_yfinance_news()
