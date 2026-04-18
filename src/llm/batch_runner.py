"""Full-pipeline async batch runner: 300 personas x ~37 events.

Orchestration:
    - asyncio.Semaphore(BEDROCK_CONCURRENT_SEMAPHORE) caps in-flight calls.
    - Throughput logged per checkpoint (every 100 events).
    - Latency p50/p95/p99 + cache hit rate + parse_failure_rate all logged.
    - Intermediate parquet checkpoints written every CHECKPOINT_EVERY events
      so a crash doesn't lose more than one chunk.

Output schema (data/persona_sentiments.parquet) per plan section 9:
    event_id, persona_id, raw_sentiment, post_dynamics_0.2, post_dynamics_0.3,
    post_dynamics_0.4, parse_retried, parse_failed, latency_ms, cache_hit,
    timestamp.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from src.config import (
    BEDROCK_CONCURRENT_SEMAPHORE,
    DATA_DIR,
    PARSE_FAILURE_TEMPLATE_SWITCH_THRESHOLD,
)
from src.llm.bedrock_client import invoke_nova_lite
from src.llm.output_parser import GLOBAL_PARSE_STATS, ParseStats
from src.llm.persona_scorer import score_event_against_personas

logger = logging.getLogger(__name__)


CHECKPOINT_EVERY = 100  # events


@dataclass
class BatchProgress:
    events_done: int = 0
    cells_done: int = 0
    cache_hits: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)

    def percentiles(self) -> dict:
        if not self.latencies_ms:
            return {"p50": float("nan"), "p95": float("nan"), "p99": float("nan")}
        arr = np.asarray(self.latencies_ms)
        return {
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
        }

    def throughput_per_min(self) -> float:
        elapsed = max(1e-6, time.perf_counter() - self.started)
        return self.cells_done / elapsed * 60.0

    def cache_hit_rate(self) -> float:
        return (self.cache_hits / self.cells_done) if self.cells_done else 0.0

    def log(self, parse_stats: ParseStats) -> None:
        snap = parse_stats.snapshot()
        pct = self.percentiles()
        logger.info(
            "batch_progress",
            extra={
                "events_done": self.events_done,
                "cells_done": self.cells_done,
                "throughput_per_min": self.throughput_per_min(),
                "cache_hit_rate": self.cache_hit_rate(),
                "latency_p50_ms": pct["p50"],
                "latency_p95_ms": pct["p95"],
                "latency_p99_ms": pct["p99"],
                "parse_failure_rate": snap["parse_failure_rate"],
                "parse_retry_rate": snap["parse_retry_rate"],
            },
        )


def _checkpoint_path(base: Path, idx: int) -> Path:
    return base.parent / f"{base.stem}.checkpoint_{idx:04d}{base.suffix}"


async def run_full_batch(
    *,
    events: Sequence[Mapping],
    personas: Sequence[Mapping],
    invoke_fn: Callable[..., Awaitable[Mapping]] = invoke_nova_lite,
    semaphore: Optional[asyncio.Semaphore] = None,
    output_path: Optional[Path] = None,
    checkpoint_every: int = CHECKPOINT_EVERY,
    stats: Optional[ParseStats] = None,
) -> pd.DataFrame:
    """Score all events x personas. Persists data/persona_sentiments.parquet.

    Returns the assembled DataFrame (parse_retried, parse_failed columns
    included). Empty post_dynamics_* columns are added so downstream
    `runner.py` can fill them in-place.
    """
    output_path = output_path or (DATA_DIR / "persona_sentiments.parquet")
    semaphore = semaphore or asyncio.Semaphore(BEDROCK_CONCURRENT_SEMAPHORE)
    if stats is None:
        stats = GLOBAL_PARSE_STATS
        stats.reset()
    progress = BatchProgress()
    frames: List[pd.DataFrame] = []
    template_switch_warned = False

    for idx, event in enumerate(events):
        df = await score_event_against_personas(
            event=event,
            personas=personas,
            invoke_fn=invoke_fn,
            semaphore=semaphore,
            stats=stats,
        )
        frames.append(df)
        progress.events_done += 1
        progress.cells_done += len(df)
        progress.cache_hits += int(df["cache_hit"].sum())
        progress.latencies_ms.extend(df["latency_ms"].tolist())

        snap = stats.snapshot()
        if (
            not template_switch_warned
            and snap["parse_failure_rate"] > PARSE_FAILURE_TEMPLATE_SWITCH_THRESHOLD
        ):
            logger.warning(
                "parse_failure_template_switch_triggered",
                extra={
                    "parse_failure_rate": snap["parse_failure_rate"],
                    "threshold": PARSE_FAILURE_TEMPLATE_SWITCH_THRESHOLD,
                },
            )
            template_switch_warned = True

        if (idx + 1) % checkpoint_every == 0:
            progress.log(stats)
            ckpt = _checkpoint_path(output_path, idx + 1)
            ckpt.parent.mkdir(parents=True, exist_ok=True)
            pd.concat(frames, ignore_index=True).to_parquet(ckpt, index=False)

    progress.log(stats)
    full = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not full.empty:
        full["timestamp"] = pd.Timestamp.now("UTC").isoformat()
        for col in ("post_dynamics_0.2", "post_dynamics_0.3", "post_dynamics_0.4"):
            full[col] = np.nan
    output_path.parent.mkdir(parents=True, exist_ok=True)
    full.to_parquet(output_path, index=False)
    return full


__all__ = ["BatchProgress", "run_full_batch"]
