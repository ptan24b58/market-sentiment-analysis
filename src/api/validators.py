"""Request validation helpers for the simulate API."""

from __future__ import annotations

from fastapi import HTTPException

from src.config import TEXAS_15_TICKERS


def validate_request(body: dict) -> tuple[str, str]:
    """Validate and extract (headline_text, ticker) from a request body.

    Returns
    -------
    tuple[str, str]
        (headline_text, ticker) on success.

    Raises
    ------
    HTTPException(400)
        With ``{"error": "invalid_ticker"}`` if ticker is not in TEXAS_15_TICKERS.
        With ``{"error": "headline_too_short"}`` if stripped headline < 20 chars.
        With ``{"error": "headline_too_long"}`` if stripped headline > 2000 chars.
    """
    ticker: str = body.get("ticker", "")
    headline_text: str = body.get("headline_text", "")

    if ticker not in TEXAS_15_TICKERS:
        raise HTTPException(status_code=400, detail={"error": "invalid_ticker"})

    stripped = headline_text.strip()
    if len(stripped) < 20:
        raise HTTPException(status_code=400, detail={"error": "headline_too_short"})
    if len(stripped) > 2000:
        raise HTTPException(status_code=400, detail={"error": "headline_too_long"})

    return headline_text, ticker
