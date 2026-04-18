"""Smoke test for batch_runner orchestration with mocked Bedrock.

We verify the orchestration produces the expected schema, throughput
diagnostics, and never makes a real Bedrock call. This is NOT the live
B5 run -- that is gated behind real AWS credentials.
"""

from __future__ import annotations

import asyncio

import pytest

from src.llm.batch_runner import run_full_batch
from src.personas import generate_personas


@pytest.fixture
def mini_events():
    return [
        {
            "event_id": f"ev_{i}",
            "headline_text": f"Mock headline number {i} about energy markets",
            "ticker": "OXY",
        }
        for i in range(5)
    ]


def test_batch_runner_returns_expected_schema(mini_events, tmp_path):
    async def fake_invoke(system_prompt, user_prompt, **kwargs):
        return {
            "response_text": "0.13",
            "cache_hit": True,
            "latency_ms": 4.2,
            "attempts": 1,
        }

    personas = generate_personas()[:5]
    out = asyncio.run(
        run_full_batch(
            events=mini_events,
            personas=personas,
            invoke_fn=fake_invoke,
            output_path=tmp_path / "persona_sentiments.parquet",
            checkpoint_every=2,
        )
    )
    assert len(out) == 5 * 5  # events x personas
    expected = {
        "event_id",
        "persona_id",
        "raw_sentiment",
        "parse_retried",
        "parse_failed",
        "latency_ms",
        "cache_hit",
        "attempts",
        "post_dynamics_0.2",
        "post_dynamics_0.3",
        "post_dynamics_0.4",
        "timestamp",
    }
    assert expected.issubset(set(out.columns))
    # Persisted parquet exists.
    assert (tmp_path / "persona_sentiments.parquet").exists()


def test_batch_runner_propagates_parse_failures(mini_events, tmp_path):
    """Bedrock returns prose -> parser retries -> still no number -> NaN."""

    call_count = {"n": 0}

    async def fake_invoke(system_prompt, user_prompt, **kwargs):
        call_count["n"] += 1
        return {
            "response_text": "no number here",
            "cache_hit": False,
            "latency_ms": 1.0,
            "attempts": 1,
        }

    personas = generate_personas()[:2]
    out = asyncio.run(
        run_full_batch(
            events=mini_events[:1],
            personas=personas,
            invoke_fn=fake_invoke,
            output_path=tmp_path / "p.parquet",
        )
    )
    # 2 personas * (1 initial + 1 retry) = 4 calls.
    assert call_count["n"] == 4
    assert out["parse_failed"].all()
    assert out["raw_sentiment"].isna().all()
