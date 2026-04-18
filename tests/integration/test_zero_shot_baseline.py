"""Smoke test for the Nova zero-shot baseline (mocked Bedrock)."""

from __future__ import annotations

import asyncio

import pytest

from src.baselines.nova_zero_shot import run_zero_shot_baseline
from src.llm.prompts import SHARED_PREFIX


@pytest.fixture
def events():
    return [
        {"event_id": "z1", "headline_text": "TSLA reports record deliveries", "ticker": "TSLA"},
        {"event_id": "z2", "headline_text": "OXY misses Q3 earnings", "ticker": "OXY"},
    ]


def test_zero_shot_uses_shared_prefix_only(events, tmp_path):
    captured = []

    async def fake_invoke(system_prompt, user_prompt, **kwargs):
        captured.append({"system": system_prompt, "user": user_prompt})
        return {
            "response_text": "0.42",
            "cache_hit": True,
            "latency_ms": 2.0,
            "attempts": 1,
        }

    df = asyncio.run(
        run_zero_shot_baseline(
            events,
            invoke_fn=fake_invoke,
            output_path=tmp_path / "signals_zero_shot.parquet",
        )
    )
    assert len(df) == 2
    assert {"event_id", "mean_sentiment"}.issubset(set(df.columns))
    # Crucially: zero-shot system prompt is EXACTLY SHARED_PREFIX (no demographic tail).
    for cap in captured:
        assert cap["system"] == SHARED_PREFIX
    assert (tmp_path / "signals_zero_shot.parquet").exists()
