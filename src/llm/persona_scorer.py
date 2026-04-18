"""Score one event against a set of personas via Bedrock + parser.

Returns a tidy DataFrame: one row per (event_id, persona_id) with
raw_sentiment, parse_retried, parse_failed, latency_ms, cache_hit.

Used both by the sentinel gate (B3) and the full batch runner (B5).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

from src.config import BEDROCK_CONCURRENT_SEMAPHORE
from src.llm.bedrock_client import invoke_nova_lite
from src.llm.output_parser import GLOBAL_PARSE_STATS, ParseStats, parse_with_retry
from src.llm.prompts import RETRY_REINFORCEMENT, build_user_prompt

logger = logging.getLogger(__name__)


@dataclass
class ScoredCell:
    event_id: str
    persona_id: int
    raw_sentiment: float
    parse_retried: bool
    parse_failed: bool
    latency_ms: float
    cache_hit: bool
    attempts: int


InvokeFn = Callable[..., Awaitable[Mapping]]


async def _score_one(
    *,
    event_id: str,
    persona: Mapping,
    user_prompt: str,
    semaphore: asyncio.Semaphore,
    invoke_fn: InvokeFn,
    stats: ParseStats,
) -> ScoredCell:
    async with semaphore:
        t0 = time.perf_counter()
        try:
            resp = await invoke_fn(persona["system_prompt"], user_prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "bedrock_call_hard_fail",
                extra={
                    "event_id": event_id,
                    "persona_id": persona["persona_id"],
                    "error": repr(exc),
                },
            )
            stats.record(retried=False, failed=True)
            return ScoredCell(
                event_id=event_id,
                persona_id=int(persona["persona_id"]),
                raw_sentiment=math.nan,
                parse_retried=False,
                parse_failed=True,
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                cache_hit=False,
                attempts=0,
            )

        first_text = resp.get("response_text", "")

        async def _retry_call() -> str:
            retry_user = user_prompt + RETRY_REINFORCEMENT
            retry_resp = await invoke_fn(persona["system_prompt"], retry_user)
            return retry_resp.get("response_text", "")

        result = await parse_with_retry(
            first_text, retry_call=_retry_call, stats=stats
        )
        return ScoredCell(
            event_id=event_id,
            persona_id=int(persona["persona_id"]),
            raw_sentiment=float(result.value),
            parse_retried=result.retried,
            parse_failed=result.failed,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            cache_hit=bool(resp.get("cache_hit", False)),
            attempts=int(resp.get("attempts", 1)),
        )


async def score_event_against_personas(
    *,
    event: Mapping,
    personas: Sequence[Mapping],
    invoke_fn: InvokeFn = invoke_nova_lite,
    semaphore: Optional[asyncio.Semaphore] = None,
    stats: Optional[ParseStats] = None,
) -> pd.DataFrame:
    """Score `personas` for a single `event`. Returns a DataFrame.

    `event` must have keys: event_id, headline_text, ticker.
    Each persona must have keys: persona_id, system_prompt.
    """
    semaphore = semaphore or asyncio.Semaphore(BEDROCK_CONCURRENT_SEMAPHORE)
    stats = stats or GLOBAL_PARSE_STATS
    user_prompt = build_user_prompt(event["headline_text"], event["ticker"])
    tasks = [
        _score_one(
            event_id=str(event["event_id"]),
            persona=p,
            user_prompt=user_prompt,
            semaphore=semaphore,
            invoke_fn=invoke_fn,
            stats=stats,
        )
        for p in personas
    ]
    cells = await asyncio.gather(*tasks)
    return _cells_to_df(cells)


async def score_events_against_personas(
    *,
    events: Sequence[Mapping],
    personas: Sequence[Mapping],
    invoke_fn: InvokeFn = invoke_nova_lite,
    semaphore: Optional[asyncio.Semaphore] = None,
    stats: Optional[ParseStats] = None,
) -> pd.DataFrame:
    """Concatenate score_event_against_personas across all events."""
    semaphore = semaphore or asyncio.Semaphore(BEDROCK_CONCURRENT_SEMAPHORE)
    stats = stats or GLOBAL_PARSE_STATS
    frames: List[pd.DataFrame] = []
    for event in events:
        df = await score_event_against_personas(
            event=event,
            personas=personas,
            invoke_fn=invoke_fn,
            semaphore=semaphore,
            stats=stats,
        )
        frames.append(df)
    if not frames:
        return _cells_to_df([])
    return pd.concat(frames, ignore_index=True)


def _cells_to_df(cells: Iterable[ScoredCell]) -> pd.DataFrame:
    rows = [
        {
            "event_id": c.event_id,
            "persona_id": c.persona_id,
            "raw_sentiment": c.raw_sentiment,
            "parse_retried": c.parse_retried,
            "parse_failed": c.parse_failed,
            "latency_ms": c.latency_ms,
            "cache_hit": c.cache_hit,
            "attempts": c.attempts,
        }
        for c in cells
    ]
    return pd.DataFrame(rows)


__all__ = [
    "ScoredCell",
    "score_event_against_personas",
    "score_events_against_personas",
]
