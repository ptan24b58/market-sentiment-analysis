"""Nova Lite zero-shot baseline: one call per event, no demographic suffix.

The system prompt is the SHARED_PREFIX only (via build_zero_shot_system_prompt),
so cache hits should be 100% after the first call. Output parser is identical
to B3/B5 so behaviour is comparable across pipelines.

Output: data/signals_zero_shot.parquet with columns event_id, sentiment_score.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from pathlib import Path
from typing import Awaitable, Callable, List, Mapping, Optional, Sequence

import pandas as pd

from src.config import BEDROCK_CONCURRENT_SEMAPHORE, DATA_DIR
from src.llm.bedrock_client import invoke_nova_lite
from src.llm.output_parser import GLOBAL_PARSE_STATS, ParseStats, parse_with_retry
from src.llm.prompts import (
    RETRY_REINFORCEMENT,
    build_user_prompt,
    build_zero_shot_system_prompt,
)

logger = logging.getLogger(__name__)


async def _score_event(
    event: Mapping,
    *,
    invoke_fn: Callable[..., Awaitable[Mapping]],
    semaphore: asyncio.Semaphore,
    stats: ParseStats,
) -> dict:
    system_prompt = build_zero_shot_system_prompt()
    user_prompt = build_user_prompt(event["headline_text"], event["ticker"])
    async with semaphore:
        t0 = time.perf_counter()
        try:
            resp = await invoke_fn(system_prompt, user_prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "zero_shot_hard_fail",
                extra={"event_id": event["event_id"], "error": repr(exc)},
            )
            stats.record(retried=False, failed=True)
            return {
                "event_id": str(event["event_id"]),
                "mean_sentiment": math.nan,
                "parse_retried": False,
                "parse_failed": True,
                "latency_ms": (time.perf_counter() - t0) * 1000.0,
                "cache_hit": False,
            }
        text = resp.get("response_text", "")

        async def _retry_call() -> str:
            retry_resp = await invoke_fn(
                system_prompt, user_prompt + RETRY_REINFORCEMENT
            )
            return retry_resp.get("response_text", "")

        result = await parse_with_retry(text, retry_call=_retry_call, stats=stats)
        return {
            "event_id": str(event["event_id"]),
            "mean_sentiment": float(result.value),
            "parse_retried": result.retried,
            "parse_failed": result.failed,
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
            "cache_hit": bool(resp.get("cache_hit", False)),
        }


async def run_zero_shot_baseline(
    events: Sequence[Mapping],
    *,
    invoke_fn: Callable[..., Awaitable[Mapping]] = invoke_nova_lite,
    semaphore: Optional[asyncio.Semaphore] = None,
    output_path: Optional[Path] = None,
    stats: Optional[ParseStats] = None,
) -> pd.DataFrame:
    """Score every event once with the shared-prefix-only system prompt.

    Persists `data/signals_zero_shot.parquet`. Returns the DataFrame.
    """
    output_path = output_path or (DATA_DIR / "signals_zero_shot.parquet")
    semaphore = semaphore or asyncio.Semaphore(BEDROCK_CONCURRENT_SEMAPHORE)
    if stats is None:
        stats = GLOBAL_PARSE_STATS
        stats.reset()
    rows: List[dict] = []
    tasks = [
        _score_event(e, invoke_fn=invoke_fn, semaphore=semaphore, stats=stats)
        for e in events
    ]
    rows = await asyncio.gather(*tasks)
    df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return df


__all__ = ["run_zero_shot_baseline"]
