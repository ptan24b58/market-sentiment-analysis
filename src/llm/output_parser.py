"""Parse Nova Lite sentiment responses with retry + clamp.

Spec (plan section 4 / B3):
    1. Apply regex `r'-?[01]?\\.\\d+'` to the response text.
    2. Clamp the matched value to [-1.0, 1.0].
    3. If no match: invoke the caller-provided async retry once with
       RETRY_REINFORCEMENT appended to the user prompt.
    4. If still no match: log, return NaN.
    5. Track parse_failure_rate via the module-level `ParseStats` counter.
       Caller can call `ParseStats.snapshot()` to get current rate.

The clamp is critical because the regex matches values like `2.5` or
`-1.7` that the LLM occasionally returns.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from src.config import SENTIMENT_REGEX

logger = logging.getLogger(__name__)

_SENTIMENT_PATTERN = re.compile(SENTIMENT_REGEX)


def _extract_first(text: str) -> Optional[float]:
    """Return the first numeric match clamped to [-1, 1], or None."""
    if not text:
        return None
    m = _SENTIMENT_PATTERN.search(text)
    if not m:
        return None
    try:
        v = float(m.group(0))
    except ValueError:
        return None
    return max(-1.0, min(1.0, v))


@dataclass
class ParseStats:
    """Thread-safe parse-failure-rate counter (singleton instance below)."""

    total: int = 0
    retried: int = 0
    failed: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, *, retried: bool, failed: bool) -> None:
        with self._lock:
            self.total += 1
            if retried:
                self.retried += 1
            if failed:
                self.failed += 1

    def reset(self) -> None:
        with self._lock:
            self.total = 0
            self.retried = 0
            self.failed = 0

    def snapshot(self) -> dict:
        with self._lock:
            total = self.total
            failed = self.failed
            retried = self.retried
        return {
            "total": total,
            "retried": retried,
            "failed": failed,
            "parse_failure_rate": (failed / total) if total else 0.0,
            "parse_retry_rate": (retried / total) if total else 0.0,
        }


GLOBAL_PARSE_STATS = ParseStats()


@dataclass
class ParseResult:
    value: float  # NaN on double-failure
    retried: bool
    failed: bool
    raw_first: str
    raw_retry: Optional[str]


async def parse_with_retry(
    initial_response: str,
    *,
    retry_call: Callable[[], Awaitable[str]],
    stats: Optional[ParseStats] = None,
) -> ParseResult:
    """Apply regex; on failure, await `retry_call()` once and re-parse.

    `retry_call` is a no-arg async closure provided by the caller (typically
    a partial of `invoke_nova_lite` with RETRY_REINFORCEMENT already appended
    to the user prompt). This keeps the parser oblivious to the LLM client.
    """
    stats = stats or GLOBAL_PARSE_STATS
    val = _extract_first(initial_response)
    if val is not None:
        stats.record(retried=False, failed=False)
        return ParseResult(
            value=val,
            retried=False,
            failed=False,
            raw_first=initial_response,
            raw_retry=None,
        )

    # Retry once.
    retry_text = ""
    try:
        retry_text = await retry_call()
    except Exception as exc:  # noqa: BLE001
        logger.warning("parse_retry_call_failed", extra={"error": repr(exc)})
    val = _extract_first(retry_text)
    if val is not None:
        stats.record(retried=True, failed=False)
        return ParseResult(
            value=val,
            retried=True,
            failed=False,
            raw_first=initial_response,
            raw_retry=retry_text,
        )

    stats.record(retried=True, failed=True)
    logger.warning(
        "parse_failed_after_retry",
        extra={
            "initial_text": initial_response[:120],
            "retry_text": retry_text[:120],
        },
    )
    return ParseResult(
        value=math.nan,
        retried=True,
        failed=True,
        raw_first=initial_response,
        raw_retry=retry_text,
    )


def parse_sentiment(text: str) -> float:
    """Synchronous helper: extract first match clamped, return NaN on failure.

    Convenience for tests / one-off callers that don't need retry semantics.
    """
    v = _extract_first(text)
    return v if v is not None else math.nan


__all__ = [
    "GLOBAL_PARSE_STATS",
    "ParseResult",
    "ParseStats",
    "parse_sentiment",
    "parse_with_retry",
]
