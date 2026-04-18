"""Five-case robustness sweep for the Nova Lite output parser."""

from __future__ import annotations

import asyncio
import math

import pytest

from src.llm.output_parser import GLOBAL_PARSE_STATS, ParseStats, parse_with_retry


@pytest.fixture(autouse=True)
def _reset_global_stats():
    GLOBAL_PARSE_STATS.reset()
    yield
    GLOBAL_PARSE_STATS.reset()


def _run(initial, retry):
    stats = ParseStats()

    async def retry_call():
        return retry

    res = asyncio.run(parse_with_retry(initial, retry_call=retry_call, stats=stats))
    return res, stats


def test_case_a_prose_response_triggers_retry_then_succeeds():
    res, stats = _run("The sentiment is positive", "0.4")
    assert res.value == pytest.approx(0.4)
    assert res.retried is True
    assert res.failed is False
    snap = stats.snapshot()
    assert snap["retried"] == 1
    assert snap["failed"] == 0


def test_case_b_truncated_response_triggers_retry():
    # "-0." has no decimal digit after the point so regex `-?[01]?\\.\\d+`
    # must NOT match; retry recovers.
    res, stats = _run("-0.", "-0.45")
    assert res.value == pytest.approx(-0.45)
    assert res.retried is True


def test_case_c_multiple_numbers_extracts_first():
    res, stats = _run("between -0.3 and 0.5", "ignored")
    assert res.value == pytest.approx(-0.3)
    assert res.retried is False
    snap = stats.snapshot()
    assert snap["retried"] == 0
    assert snap["failed"] == 0


def test_case_d_empty_then_empty_returns_nan():
    res, stats = _run("", "")
    assert math.isnan(res.value)
    assert res.retried is True
    assert res.failed is True
    snap = stats.snapshot()
    assert snap["failed"] == 1
    assert snap["parse_failure_rate"] == 1.0


def test_case_e_valid_first_response_no_retry():
    captured_calls = {"n": 0}

    async def retry_call():
        captured_calls["n"] += 1
        return "should not be used"

    stats = ParseStats()
    res = asyncio.run(
        parse_with_retry("-0.73", retry_call=retry_call, stats=stats)
    )
    assert res.value == pytest.approx(-0.73)
    assert res.retried is False
    assert captured_calls["n"] == 0
    snap = stats.snapshot()
    assert snap["retried"] == 0
    assert snap["failed"] == 0


def test_clamp_in_pipeline():
    # Regex matches "1.7" with leading 1 consumed, clamp pulls 1.7 -> 1.0.
    res, _ = _run("prose", "score is 1.7")
    assert res.value == 1.0
    # Symmetric for negative side.
    res2, _ = _run("prose", "-1.4")
    assert res2.value == -1.0


def test_counter_aggregates_over_batch():
    stats = ParseStats()

    async def good():
        return "0.3"

    async def bad():
        return "still no number"

    asyncio.run(parse_with_retry("0.1", retry_call=good, stats=stats))
    asyncio.run(parse_with_retry("prose", retry_call=good, stats=stats))
    asyncio.run(parse_with_retry("prose", retry_call=bad, stats=stats))
    snap = stats.snapshot()
    assert snap["total"] == 3
    assert snap["retried"] == 2
    assert snap["failed"] == 1
    assert snap["parse_failure_rate"] == pytest.approx(1 / 3)
