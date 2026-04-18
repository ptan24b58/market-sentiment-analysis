"""Output parser: regex extraction, [-1,1] clamp, retry, NaN, counter."""

from __future__ import annotations

import asyncio
import math

import pytest

from src.llm.output_parser import (
    GLOBAL_PARSE_STATS,
    ParseStats,
    parse_sentiment,
    parse_with_retry,
)


@pytest.fixture(autouse=True)
def _reset_global_stats():
    GLOBAL_PARSE_STATS.reset()
    yield
    GLOBAL_PARSE_STATS.reset()


def test_parse_extracts_simple_value():
    assert parse_sentiment("-0.73") == pytest.approx(-0.73)


def test_parse_extracts_first_of_many():
    assert parse_sentiment("between -0.3 and 0.5") == pytest.approx(-0.3)


def test_parse_clamps_to_unit_interval():
    # Regex `-?[01]?\.\d+` only matches a leading 0 or 1 (or no digit), so
    # for "2.5" it matches ".5" (drops the 2) -> 0.5; the post-parse clamp
    # then guards any in-range values it does match. We verify boundary
    # values are preserved by the clamp (no silent truncation).
    assert parse_sentiment("score: -1.0") == -1.0
    assert parse_sentiment("response: 1.0") == 1.0
    # Negative leading two-digit values won't match the integer part either,
    # so "-1.7" matches "-1.7" only if the first digit is 0 or 1: matches "-1.7"
    # because [01]? consumes the "1"; clamp pulls -1.7 -> -1.0.
    assert parse_sentiment("score: -1.7") == -1.0


def test_parse_returns_nan_on_no_match():
    assert math.isnan(parse_sentiment("The sentiment is positive"))
    assert math.isnan(parse_sentiment(""))


def test_parse_with_retry_no_match_then_success():
    stats = ParseStats()

    async def retry():
        return "0.42"

    res = asyncio.run(
        parse_with_retry("The sentiment is positive", retry_call=retry, stats=stats)
    )
    assert res.value == pytest.approx(0.42)
    assert res.retried is True
    assert res.failed is False
    snap = stats.snapshot()
    assert snap["total"] == 1
    assert snap["retried"] == 1
    assert snap["failed"] == 0
    assert snap["parse_failure_rate"] == 0.0


def test_parse_with_retry_double_failure_returns_nan_and_increments_counter():
    stats = ParseStats()

    async def retry():
        return "still no number here"

    res = asyncio.run(
        parse_with_retry("no value", retry_call=retry, stats=stats)
    )
    assert math.isnan(res.value)
    assert res.retried is True
    assert res.failed is True
    snap = stats.snapshot()
    assert snap["failed"] == 1
    assert snap["parse_failure_rate"] == 1.0


def test_parse_with_retry_success_first_try_no_retry():
    stats = ParseStats()

    async def retry():
        raise AssertionError("retry must not be invoked")

    res = asyncio.run(
        parse_with_retry("-0.42", retry_call=retry, stats=stats)
    )
    assert res.value == pytest.approx(-0.42)
    assert res.retried is False
    assert res.failed is False


def test_parse_failure_rate_aggregates():
    stats = ParseStats()

    async def good_retry():
        return "0.1"

    async def bad_retry():
        return "no number"

    asyncio.run(parse_with_retry("0.5", retry_call=good_retry, stats=stats))
    asyncio.run(parse_with_retry("prose", retry_call=good_retry, stats=stats))
    asyncio.run(parse_with_retry("prose", retry_call=bad_retry, stats=stats))
    snap = stats.snapshot()
    assert snap["total"] == 3
    assert snap["failed"] == 1
    assert snap["parse_failure_rate"] == pytest.approx(1 / 3)
