"""Workstream A1: GDELT 2.0 DOC API ingest for Texas-15 tickers.

Queries the GDELT DOC API for each ticker's name variants over the configured
event window, parses responses, and writes events_stage1.parquet.

See plan Section 4 (A1) and Section 9 (events_stage1.parquet schema).
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from src.config import (
    DATA_DIR,
    EVENT_WINDOW_END,
    EVENT_WINDOW_START,
    GDELT_DOC_API_ENDPOINT,
    TEXAS_15_TICKERS,
)
from src.data.ticker_aliases import alias_table
from src.data.event_filter import apply_stage1_filter
from src.data.sentinel_selector import select_sentinels

logger = logging.getLogger(__name__)

# GDELT DOC API parameters.
_MAX_RECORDS = 250  # API hard cap per request.
_BACKOFF_BASE = 5.0  # seconds — raised from 2s because GDELT's rate-limit
                     # window is ~15s; a 2s retry almost always re-trips it.
_BACKOFF_MAX = 60.0  # seconds
_MAX_RETRIES = 5


def _stage1_parquet_path():
    """Return the stage-1 parquet path (evaluated at call time for testability)."""
    return DATA_DIR / "events_stage1.parquet"


def _gdelt_query_params(query_term: str, start_date: str, end_date: str) -> dict:
    """Build GDELT DOC API query parameters for a single search term."""
    # GDELT DOC API uses YYYYMMDDHHMMSS date format.
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d%H%M%S")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m%d%H%M%S")
    return {
        "query": query_term,
        "mode": "artlist",
        "format": "json",
        "maxrecords": _MAX_RECORDS,
        "startdatetime": start_dt,
        "enddatetime": end_dt,
        "sort": "DateDesc",
    }


def _fetch_gdelt_articles(
    query_term: str,
    start_date: str,
    end_date: str,
    session: requests.Session,
) -> list[dict[str, Any]]:
    """Fetch articles from GDELT DOC API with exponential backoff on errors.

    Returns a list of raw article dicts from the 'articles' key of the response.
    """
    params = _gdelt_query_params(query_term, start_date, end_date)
    backoff = _BACKOFF_BASE
    for attempt in range(_MAX_RETRIES):
        try:
            resp = session.get(
                GDELT_DOC_API_ENDPOINT, params=params, timeout=30
            )
            if resp.status_code == 429:
                wait = min(backoff * (2**attempt), _BACKOFF_MAX)
                logger.warning(
                    "GDELT rate-limited (429) for %r; sleeping %.1fs", query_term, wait
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            articles: list[dict[str, Any]] = data.get("articles") or []
            logger.debug(
                "GDELT query %r returned %d articles", query_term, len(articles)
            )
            return articles
        except requests.exceptions.RequestException as exc:
            wait = min(backoff * (2**attempt), _BACKOFF_MAX)
            logger.warning(
                "GDELT request error for %r (attempt %d/%d): %s; retrying in %.1fs",
                query_term,
                attempt + 1,
                _MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
    logger.error(
        "GDELT query %r failed after %d attempts; returning empty list.",
        query_term,
        _MAX_RETRIES,
    )
    return []


def _parse_timestamp(seendate: str | None) -> datetime | None:
    """Parse GDELT seendate string (YYYYMMDDTHHMMSSZ) to UTC datetime."""
    if not seendate:
        return None
    fmt_variants = [
        "%Y%m%dT%H%M%SZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y%m%d%H%M%S",
    ]
    for fmt in fmt_variants:
        try:
            dt = datetime.strptime(seendate, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    logger.debug("Could not parse GDELT seendate %r", seendate)
    return None


def _article_to_event(
    article: dict[str, Any], ticker: str
) -> dict[str, Any] | None:
    """Convert a raw GDELT article dict to the events_stage1 schema dict.

    Returns None if required fields are missing.
    """
    url: str = article.get("url") or ""
    title: str = article.get("title") or ""
    seendate: str | None = article.get("seendate")

    if not title or not url:
        return None

    ts = _parse_timestamp(seendate)
    if ts is None:
        return None

    # GDELT tone (overall sentiment tone of the article, -100 to +100 scale).
    tone_raw = article.get("tone")
    try:
        gdelt_tone = float(tone_raw) if tone_raw is not None else 0.0
    except (TypeError, ValueError):
        gdelt_tone = 0.0

    # Theme tags: GDELT categories/themes.
    themes_raw = article.get("categories") or []
    if isinstance(themes_raw, str):
        themes_raw = [t.strip() for t in themes_raw.split(",") if t.strip()]
    gdelt_theme_tags: list[str] = list(themes_raw)

    # Entity tags from 'socialimage' or 'domain' or organisations field.
    # GDELT artlist mode returns limited entity info; use domain + title tokens.
    domain: str = article.get("domain") or ""
    entity_tags: list[str] = [domain] if domain else []

    # Entity confidence proxy: use 1.0 for direct ticker-name searches,
    # partial credit for fuzzy matches (handled downstream in filter).
    entity_confidence: float = article.get("entity_confidence", 1.0)

    return {
        "event_id": str(uuid.uuid4()),
        "headline_text": title.strip(),
        "source_url": url.strip(),
        "ticker": ticker,
        "timestamp": ts,
        "gdelt_tone": gdelt_tone,
        "gdelt_theme_tags": gdelt_theme_tags,
        "entity_tags": entity_tags,
        "entity_confidence": entity_confidence,
        "is_sentinel": False,
    }


def _deduplicate(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate events by (headline_text, ticker) pair.

    GDELT can return the same article for multiple alias queries.
    """
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for ev in events:
        key = (ev["headline_text"].lower()[:120], ev["ticker"])
        if key not in seen:
            seen.add(key)
            deduped.append(ev)
    logger.info(
        "Deduplication: %d -> %d events", len(events), len(deduped)
    )
    return deduped


def ingest_gdelt(
    tickers: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    write_parquet: bool = True,
) -> pd.DataFrame:
    """Run the full GDELT ingest pipeline for the given tickers and date range.

    For each ticker, queries GDELT using the ticker symbol and all alias
    variants. Deduplicates, applies stage-1 material filter, selects
    sentinels, and optionally writes events_stage1.parquet.

    Parameters
    ----------
    tickers:
        Ticker list; defaults to TEXAS_15_TICKERS.
    start_date:
        ISO date string "YYYY-MM-DD"; defaults to EVENT_WINDOW_START.
    end_date:
        ISO date string "YYYY-MM-DD"; defaults to EVENT_WINDOW_END.
    write_parquet:
        If True, write output to data/events_stage1.parquet.

    Returns
    -------
    pd.DataFrame
        Stage-1 filtered events with schema matching events_stage1.parquet.
    """
    tickers = tickers or TEXAS_15_TICKERS
    start_date = start_date or EVENT_WINDOW_START
    end_date = end_date or EVENT_WINDOW_END

    aliases = alias_table()
    session = requests.Session()
    session.headers.update({"User-Agent": "persona-sentiment-pipeline/1.0"})

    all_raw: list[dict[str, Any]] = []

    for ticker in tickers:
        query_terms: list[str] = [ticker]
        # Add first two alias variants to avoid overly broad queries.
        ticker_aliases = aliases.get(ticker, [])
        query_terms.extend(ticker_aliases[:2])

        for term in query_terms:
            logger.info("Querying GDELT: ticker=%s term=%r", ticker, term)
            articles = _fetch_gdelt_articles(term, start_date, end_date, session)
            for art in articles:
                ev = _article_to_event(art, ticker)
                if ev is not None:
                    all_raw.append(ev)
            # Polite delay between queries — GDELT free tier rate-limits
            # aggressively at <5s spacing. 5s stays below their trigger.
            time.sleep(5.0)

    logger.info("Total raw events before dedup: %d", len(all_raw))
    deduped = _deduplicate(all_raw)

    # Apply stage-1 filter.
    df_filtered = apply_stage1_filter(pd.DataFrame(deduped))
    logger.info("Events after stage-1 filter: %d", len(df_filtered))

    # Mark sentinels.
    if len(df_filtered) > 0:
        df_filtered = select_sentinels(df_filtered)

    sentinel_count = int(df_filtered["is_sentinel"].sum()) if len(df_filtered) > 0 else 0
    logger.info(
        "Stage-1 complete: %d events, %d sentinels", len(df_filtered), sentinel_count
    )

    if write_parquet and len(df_filtered) > 0:
        _write_stage1(df_filtered)

    return df_filtered


def _write_stage1(df: pd.DataFrame) -> None:
    """Serialize df to events_stage1.parquet with correct schema types."""
    # Ensure list columns are stored as Python objects (not Arrow list types
    # that cause issues with some parquet readers).
    out = df.copy()
    for col in ("gdelt_theme_tags", "entity_tags"):
        if col in out.columns:
            out[col] = out[col].apply(
                lambda v: list(v) if isinstance(v, (list, tuple)) else []
            )

    path = _stage1_parquet_path()
    out.to_parquet(path, index=False, engine="pyarrow")
    logger.info("Wrote events_stage1.parquet (%d rows) to %s", len(out), path)


def load_stage1() -> pd.DataFrame:
    """Load events_stage1.parquet; raises FileNotFoundError if not yet generated."""
    path = _stage1_parquet_path()
    if not path.exists():
        raise FileNotFoundError(
            f"events_stage1.parquet not found at {path}. "
            "Run ingest_gdelt() first."
        )
    return pd.read_parquet(path, engine="pyarrow")
