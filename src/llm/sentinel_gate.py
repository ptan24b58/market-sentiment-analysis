"""Sentinel-event gate: variance + bimodality on first 3 events.

Gate logic (plan section 4 / B3):
    PASS if inter-persona sigma >= SENTINEL_VARIANCE_THRESHOLD on at least
    SENTINEL_PASS_REQUIRED of SENTINEL_EVENT_COUNT events.

We compute Sarle's bimodality coefficient alongside variance and persist
the parse_failure_rate so downstream callers can decide whether to switch
to STRUCTURED_FALLBACK_PROMPT (>10% failure threshold).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Awaitable, Callable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from src.config import (
    BEDROCK_CONCURRENT_SEMAPHORE,
    DATA_DIR,
    PARSE_FAILURE_TEMPLATE_SWITCH_THRESHOLD,
    SENTINEL_EVENT_COUNT,
    SENTINEL_PASS_REQUIRED,
    SENTINEL_VARIANCE_THRESHOLD,
)
from src.llm.bedrock_client import invoke_nova_lite
from src.llm.output_parser import GLOBAL_PARSE_STATS, ParseStats
from src.llm.persona_scorer import score_event_against_personas
from src.metrics.signal_aggregation import sarle_bimodality

logger = logging.getLogger(__name__)


@dataclass
class SentinelEventDiagnostics:
    event_id: str
    n_personas: int
    n_valid: int
    variance: float
    std: float
    mean: float
    bimodality_index: float
    passes_threshold: bool


@dataclass
class SentinelDiagnostics:
    per_event: List[SentinelEventDiagnostics]
    parse_failure_rate: float
    parse_retry_rate: float
    pass_count: int
    pass_required: int
    gate_pass: bool
    template_switch_recommended: bool

    def to_json(self) -> dict:
        return {
            "per_event": [asdict(e) for e in self.per_event],
            "parse_failure_rate": self.parse_failure_rate,
            "parse_retry_rate": self.parse_retry_rate,
            "pass_count": self.pass_count,
            "pass_required": self.pass_required,
            "gate_pass": self.gate_pass,
            "template_switch_recommended": self.template_switch_recommended,
            "thresholds": {
                "variance_min": SENTINEL_VARIANCE_THRESHOLD,
                "events_required": SENTINEL_EVENT_COUNT,
                "passes_required": SENTINEL_PASS_REQUIRED,
                "parse_failure_template_switch": PARSE_FAILURE_TEMPLATE_SWITCH_THRESHOLD,
            },
        }


def _event_diagnostics(
    event_id: str, scores: np.ndarray
) -> SentinelEventDiagnostics:
    valid = scores[~np.isnan(scores)]
    var = float(np.var(valid, ddof=0)) if valid.size > 0 else float("nan")
    std = float(np.std(valid, ddof=0)) if valid.size > 0 else float("nan")
    mean = float(np.mean(valid)) if valid.size > 0 else float("nan")
    return SentinelEventDiagnostics(
        event_id=event_id,
        n_personas=int(scores.size),
        n_valid=int(valid.size),
        variance=var,
        std=std,
        mean=mean,
        bimodality_index=sarle_bimodality(scores),
        passes_threshold=bool(std >= SENTINEL_VARIANCE_THRESHOLD)
        if not np.isnan(std)
        else False,
    )


async def run_sentinel_gate(
    *,
    sentinel_events: Sequence[Mapping],
    personas: Sequence[Mapping],
    invoke_fn: Callable[..., Awaitable[Mapping]] = invoke_nova_lite,
    semaphore: Optional[asyncio.Semaphore] = None,
    stats: Optional[ParseStats] = None,
    results_path: Optional[Path] = None,
    diagnostics_path: Optional[Path] = None,
) -> SentinelDiagnostics:
    """Score sentinel events x personas and emit pass/fail diagnostics.

    Persists `data/sentinel_results.json` (per-persona scores) and
    `data/sentinel_diagnostics.json` (summary + gate flag).
    """
    if stats is None:
        stats = GLOBAL_PARSE_STATS
        stats.reset()
    semaphore = semaphore or asyncio.Semaphore(BEDROCK_CONCURRENT_SEMAPHORE)
    results_path = results_path or (DATA_DIR / "sentinel_results.json")
    diagnostics_path = diagnostics_path or (DATA_DIR / "sentinel_diagnostics.json")

    per_event_dfs: List[pd.DataFrame] = []
    per_event_diag: List[SentinelEventDiagnostics] = []
    for event in sentinel_events:
        df = await score_event_against_personas(
            event=event,
            personas=personas,
            invoke_fn=invoke_fn,
            semaphore=semaphore,
            stats=stats,
        )
        per_event_dfs.append(df)
        per_event_diag.append(
            _event_diagnostics(str(event["event_id"]), df["raw_sentiment"].to_numpy())
        )

    pass_count = sum(1 for e in per_event_diag if e.passes_threshold)
    snap = stats.snapshot()
    diagnostics = SentinelDiagnostics(
        per_event=per_event_diag,
        parse_failure_rate=snap["parse_failure_rate"],
        parse_retry_rate=snap["parse_retry_rate"],
        pass_count=pass_count,
        pass_required=SENTINEL_PASS_REQUIRED,
        gate_pass=pass_count >= SENTINEL_PASS_REQUIRED,
        template_switch_recommended=snap["parse_failure_rate"]
        > PARSE_FAILURE_TEMPLATE_SWITCH_THRESHOLD,
    )

    # Persist per-persona results.
    if per_event_dfs:
        all_scores = pd.concat(per_event_dfs, ignore_index=True)
        results_path.write_text(
            json.dumps(all_scores.to_dict(orient="records"), indent=2, default=str)
        )
    else:
        results_path.write_text("[]")
    diagnostics_path.write_text(json.dumps(diagnostics.to_json(), indent=2))

    logger.info(
        "sentinel_gate_decision",
        extra={
            "gate_pass": diagnostics.gate_pass,
            "pass_count": pass_count,
            "pass_required": SENTINEL_PASS_REQUIRED,
            "parse_failure_rate": snap["parse_failure_rate"],
        },
    )
    return diagnostics


__all__ = [
    "SentinelDiagnostics",
    "SentinelEventDiagnostics",
    "run_sentinel_gate",
]
