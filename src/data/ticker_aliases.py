"""Workstream A1a: Org-to-ticker fuzzy-match alias table.

Pre-built alias mapping for all 15 Texas tickers. Supports case-insensitive
exact lookup first, then falls back to difflib sequence-ratio fuzzy matching.
rapidfuzz is used when available for speed; difflib is the pure-stdlib fallback.

See plan Section 4 (A1: GDELT Ingest) and Section 8 (R10: alias table).
"""

import json
import logging
from pathlib import Path

from src.config import DATA_DIR, TEXAS_15_TICKERS

logger = logging.getLogger(__name__)

_ALIASES_PATH: Path = DATA_DIR / "ticker_aliases.json"

# Attempt to import rapidfuzz; fall back to difflib.
try:
    from rapidfuzz import fuzz as _fuzz  # type: ignore

    def _similarity(a: str, b: str) -> float:
        """Token-sort ratio in [0, 1] via rapidfuzz."""
        return _fuzz.token_sort_ratio(a, b) / 100.0

    _FUZZY_BACKEND = "rapidfuzz"
except ImportError:
    import difflib

    def _similarity(a: str, b: str) -> float:  # type: ignore[no-redef]
        """SequenceMatcher ratio in [0, 1] via stdlib difflib."""
        return difflib.SequenceMatcher(None, a, b).ratio()

    _FUZZY_BACKEND = "difflib"

logger.debug("Fuzzy-match backend: %s", _FUZZY_BACKEND)

# Similarity threshold for fuzzy matching (0.0–1.0).
_FUZZY_THRESHOLD: float = 0.80


def _load_aliases() -> dict[str, list[str]]:
    """Load alias table from JSON, falling back to the config ticker list."""
    if _ALIASES_PATH.exists():
        with _ALIASES_PATH.open("r", encoding="utf-8") as fh:
            data: dict[str, list[str]] = json.load(fh)
        logger.debug("Loaded ticker aliases from %s", _ALIASES_PATH)
        return data
    logger.warning(
        "ticker_aliases.json not found at %s; using empty alias table.", _ALIASES_PATH
    )
    return {ticker: [] for ticker in TEXAS_15_TICKERS}


# Module-level cache — loaded once on first import.
_ALIAS_TABLE: dict[str, list[str]] = _load_aliases()

# Flat lookup: normalised alias string -> ticker symbol.
_NORMALISED_LOOKUP: dict[str, str] = {}
for _ticker, _variants in _ALIAS_TABLE.items():
    _NORMALISED_LOOKUP[_ticker.lower()] = _ticker
    for _v in _variants:
        _NORMALISED_LOOKUP[_v.lower()] = _ticker


def match_org_name(org: str) -> str | None:
    """Return the ticker symbol for *org*, or None if no confident match found.

    Matching pipeline:
    1. Exact case-insensitive lookup in the alias table.
    2. Fuzzy similarity against all known aliases; returns best match if
       similarity >= _FUZZY_THRESHOLD.

    Parameters
    ----------
    org:
        Organisation name as it appears in a GDELT entity tag, e.g.
        "Exxon Mobil Corporation" or "tesla motors".

    Returns
    -------
    str | None
        Ticker symbol (e.g. "XOM") or None.
    """
    if not org or not isinstance(org, str):
        return None

    normalised = org.strip().lower()

    # 1. Exact lookup.
    if normalised in _NORMALISED_LOOKUP:
        ticker = _NORMALISED_LOOKUP[normalised]
        logger.debug("Exact alias match: %r -> %s", org, ticker)
        return ticker

    # 2. Fuzzy lookup.
    best_ticker: str | None = None
    best_score: float = 0.0
    for alias_lower, ticker in _NORMALISED_LOOKUP.items():
        score = _similarity(normalised, alias_lower)
        if score > best_score:
            best_score = score
            best_ticker = ticker

    if best_score >= _FUZZY_THRESHOLD and best_ticker is not None:
        logger.debug(
            "Fuzzy alias match: %r -> %s (score=%.3f)", org, best_ticker, best_score
        )
        return best_ticker

    logger.debug(
        "No alias match for %r (best score=%.3f, threshold=%.2f)",
        org,
        best_score,
        _FUZZY_THRESHOLD,
    )
    return None


def get_aliases(ticker: str) -> list[str]:
    """Return all known alias strings for *ticker*, or [] if unknown."""
    return _ALIAS_TABLE.get(ticker, [])


def alias_table() -> dict[str, list[str]]:
    """Return a copy of the full alias table."""
    return dict(_ALIAS_TABLE)
