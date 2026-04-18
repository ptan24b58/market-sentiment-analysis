"""Bedrock client/scorer payload contract: SHARED_PREFIX + DEMOGRAPHIC_SUFFIX
in system prompt; ticker + headline in user prompt."""

from __future__ import annotations

import asyncio

import pytest

from src.llm.persona_scorer import score_event_against_personas
from src.llm.prompts import SHARED_PREFIX
from src.personas import generate_personas


@pytest.fixture
def event():
    return {
        "event_id": "ev_test_1",
        "headline_text": "Permian Basin output hits new record",
        "ticker": "OXY",
    }


def test_invoke_payload_contains_shared_prefix_and_suffix(event):
    captured = []

    async def fake_invoke(system_prompt, user_prompt, **kwargs):
        captured.append({"system": system_prompt, "user": user_prompt})
        return {
            "response_text": "0.21",
            "cache_hit": True,
            "latency_ms": 5.0,
            "attempts": 1,
        }

    personas = generate_personas()[:3]
    df = asyncio.run(
        score_event_against_personas(
            event=event, personas=personas, invoke_fn=fake_invoke
        )
    )
    assert len(df) == 3
    # All three personas hit the mock, so 3 captures total.
    assert len(captured) == 3
    for cap in captured:
        # SHARED_PREFIX must be the first portion of the system prompt
        # (cache key boundary).
        assert cap["system"].startswith(SHARED_PREFIX)
        assert "Texas" in cap["system"]
        # User prompt carries ticker + headline.
        assert "OXY" in cap["user"]
        assert "Permian Basin output hits new record" in cap["user"]
        # Suffix is non-empty (demographic anchor present).
        assert len(cap["system"]) > len(SHARED_PREFIX)


def test_scorer_returns_dataframe_with_required_columns(event):
    async def fake_invoke(system_prompt, user_prompt, **kwargs):
        return {
            "response_text": "-0.42",
            "cache_hit": False,
            "latency_ms": 7.5,
            "attempts": 1,
        }

    personas = generate_personas()[:2]
    df = asyncio.run(
        score_event_against_personas(
            event=event, personas=personas, invoke_fn=fake_invoke
        )
    )
    expected = {
        "event_id",
        "persona_id",
        "raw_sentiment",
        "parse_retried",
        "parse_failed",
        "latency_ms",
        "cache_hit",
        "attempts",
    }
    assert expected.issubset(set(df.columns))
    assert (df["raw_sentiment"] == -0.42).all()
    assert (df["parse_retried"] == False).all()  # noqa: E712
