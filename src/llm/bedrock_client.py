"""Async wrapper around boto3 Bedrock invoke_model with prompt caching.

Uses Anthropic's messages schema for Claude models on Bedrock
(model ID in src/config.BEDROCK_MODEL_ID, currently Claude Sonnet 4.5).

We expose `invoke_nova_lite(system_prompt, user_prompt)` returning a dict
with response_text, cache_hit (best-effort from response metadata), and
latency_ms. The function name is kept as `invoke_nova_lite` for backward
compatibility with existing call sites; it now dispatches to Claude.

Retry policy: exponential backoff with jitter on HTTP 429 and
boto3 transient ClientError codes.

The boto3 client is created lazily on first call so unit tests can run
without AWS credentials. Tests should monkeypatch this module's
`invoke_nova_lite` directly (not the underlying boto3 call).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, Optional

from src.config import (
    BEDROCK_BASE_BACKOFF_SECONDS,
    BEDROCK_CONCURRENT_SEMAPHORE,
    BEDROCK_MAX_BACKOFF_SECONDS,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
)
from src.llm.prompts import build_user_prompt

logger = logging.getLogger(__name__)

_TRANSIENT_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailable",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelStreamErrorException",
    "ModelTimeoutException",
}

_client = None
_client_lock = asyncio.Lock()


def _make_boto_client():
    """Lazy boto3 client factory; raises if boto3 not installed.

    Sizes the HTTP connection pool to match the async semaphore so concurrent
    invoke_model calls don't churn connections. Boto3's default is 10 which is
    far below our live concurrency (BEDROCK_CONCURRENT_SEMAPHORE).
    """
    import boto3  # noqa: WPS433  intentional lazy import
    from botocore.config import Config  # noqa: WPS433

    # Keep a little headroom above the semaphore for retries / reaper.
    pool_size = max(BEDROCK_CONCURRENT_SEMAPHORE + 5, 20)
    cfg = Config(
        region_name=BEDROCK_REGION,
        max_pool_connections=pool_size,
        retries={"mode": "standard", "max_attempts": 1},  # our wrapper does retries
    )
    return boto3.client("bedrock-runtime", config=cfg)


async def _get_client():
    global _client
    if _client is None:
        async with _client_lock:
            if _client is None:
                _client = _make_boto_client()
    return _client


def _build_payload(
    system_prompt: str,
    user_prompt: str,
    *,
    enable_caching: bool,
) -> Dict[str, Any]:
    """Compose an Anthropic-schema request body for Claude on Bedrock.

    The persona `system_prompt` is the static part shared across every call
    for a given persona, so we mark it as ephemeral-cacheable. `user_prompt`
    is the per-event headline/ticker and is never cached.
    """
    system_block: Dict[str, Any] = {"type": "text", "text": system_prompt}
    if enable_caching:
        # Anthropic's prompt caching marker. Cache TTL defaults to 5 min.
        # Bedrock silently ignores this if the model doesn't support caching.
        system_block["cache_control"] = {"type": "ephemeral"}
    # Claude Sonnet 4.5 rejects top_p + temperature together; keep temperature only.
    # Bumped 0.7 -> 1.0 because Claude at 0.7 was collapsing persona variance
    # (sentinel std 0.05-0.07 << 0.10 threshold). 1.0 widens the roleplay spread.
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 32,
        "temperature": 1.0,
        "system": [system_block],
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}],
            }
        ],
    }


def _parse_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract response_text and cache metadata from a Claude response."""
    text_chunks = []
    for block in raw.get("content", []) or []:
        if block.get("type") == "text":
            t = block.get("text")
            if t:
                text_chunks.append(t)
    response_text = "".join(text_chunks)
    usage = raw.get("usage", {}) or {}
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    cache_write = usage.get("cache_creation_input_tokens", 0) or 0
    return {
        "response_text": response_text,
        "cache_hit": cache_read > 0,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


def _is_transient(exc: Exception) -> bool:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
    if code in _TRANSIENT_ERROR_CODES:
        return True
    status = getattr(exc, "response", {}).get(
        "ResponseMetadata", {}
    ).get("HTTPStatusCode")
    return status in (429, 500, 502, 503, 504)


async def invoke_nova_lite(
    system_prompt: str,
    user_prompt: str,
    *,
    enable_caching: bool = True,
    model_id: str = BEDROCK_MODEL_ID,
    max_retries: int = 5,
) -> Dict[str, Any]:
    """Single Bedrock call returning a dict with response_text, cache_hit, latency_ms.

    Retries on transient errors with exponential backoff + jitter.
    """
    payload = _build_payload(system_prompt, user_prompt, enable_caching=enable_caching)
    body = json.dumps(payload).encode("utf-8")
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries):
        client = await _get_client()
        t0 = time.perf_counter()
        try:
            response = await asyncio.to_thread(
                client.invoke_model,
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            raw = json.loads(response["body"].read())
            parsed = _parse_response(raw)
            parsed["latency_ms"] = (time.perf_counter() - t0) * 1000.0
            parsed["attempts"] = attempt + 1
            return parsed
        except Exception as exc:  # noqa: BLE001  intentional broad catch
            last_exc = exc
            if not _is_transient(exc):
                raise
            backoff = min(
                BEDROCK_MAX_BACKOFF_SECONDS,
                BEDROCK_BASE_BACKOFF_SECONDS * (2 ** attempt),
            ) * (0.5 + random.random())
            logger.warning(
                "bedrock_transient",
                extra={
                    "attempt": attempt + 1,
                    "backoff_s": backoff,
                    "error": repr(exc),
                },
            )
            await asyncio.sleep(backoff)
    assert last_exc is not None
    raise last_exc


def reset_client() -> None:
    """Test helper: drop cached boto3 client so monkeypatching takes effect."""
    global _client
    _client = None


__all__ = ["invoke_nova_lite", "build_user_prompt", "reset_client"]
