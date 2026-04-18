"""Async wrapper around boto3 Bedrock invoke_model with prompt caching.

We expose `invoke_nova_lite(system_prompt, user_prompt)` returning a dict
with response_text, cache_hit (best-effort from response metadata), and
latency_ms. Retry policy: exponential backoff with jitter on HTTP 429 and
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
    """Lazy boto3 client factory; raises if boto3 not installed."""
    import boto3  # noqa: WPS433  intentional lazy import

    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


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
    """Compose Nova Lite request body with optional system-prompt caching."""
    system_block: Dict[str, Any] = {"text": system_prompt}
    if enable_caching:
        # Bedrock supports a cachePoint marker on the system block; falls back
        # silently if the runtime ignores it.
        system_block["cachePoint"] = {"type": "default"}
    return {
        "schemaVersion": "messages-v1",
        "system": [system_block],
        "messages": [
            {
                "role": "user",
                "content": [{"text": user_prompt}],
            }
        ],
        "inferenceConfig": {
            "maxTokens": 32,
            "temperature": 0.7,
            "topP": 0.9,
        },
    }


def _parse_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract response_text and cache metadata from a Nova Lite response."""
    text_chunks = []
    output = raw.get("output", {})
    message = output.get("message", {})
    for block in message.get("content", []):
        t = block.get("text")
        if t:
            text_chunks.append(t)
    response_text = "".join(text_chunks)
    usage = raw.get("usage", {}) or {}
    cache_read = usage.get("cacheReadInputTokens", 0) or 0
    cache_write = usage.get("cacheWriteInputTokens", 0) or 0
    return {
        "response_text": response_text,
        "cache_hit": cache_read > 0,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
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
