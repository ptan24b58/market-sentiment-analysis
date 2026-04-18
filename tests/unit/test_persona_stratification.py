"""Persona generator hits ACS proportions within 10% on every dimension."""

from __future__ import annotations

from collections import Counter

import pytest

from src.config import (
    DEFAULT_PERSONA_COUNT,
    POLITICAL_LEAN_DISTRIBUTION_TX,
)
from src.llm.prompts import SHARED_PREFIX
from src.personas import (
    AGE_BINS,
    INCOME_BINS,
    POLITICAL_LEANS,
    ZIP_REGIONS,
    generate_personas,
    load_acs_strata,
)


@pytest.fixture(scope="module")
def personas():
    return generate_personas()


@pytest.fixture(scope="module")
def strata():
    return load_acs_strata()


def _bin_shares(personas, key):
    counter = Counter(p[key] for p in personas)
    n = len(personas)
    return {k: c / n for k, c in counter.items()}


def test_persona_count(personas):
    assert len(personas) == DEFAULT_PERSONA_COUNT


def test_income_within_10pct(personas, strata):
    shares = _bin_shares(personas, "income_bin")
    for b in INCOME_BINS:
        target = strata["income_bin"][b]
        assert abs(shares.get(b, 0) - target) <= 0.10, (b, shares.get(b, 0), target)


def test_age_within_10pct(personas, strata):
    shares = _bin_shares(personas, "age_bin")
    for b in AGE_BINS:
        target = strata["age_bin"][b]
        assert abs(shares.get(b, 0) - target) <= 0.10, (b, shares.get(b, 0), target)


def test_zip_region_within_10pct(personas, strata):
    shares = _bin_shares(personas, "zip_region")
    for r in ZIP_REGIONS:
        target = strata["zip_region"][r]
        assert abs(shares.get(r, 0) - target) <= 0.10, (r, shares.get(r, 0), target)


def test_political_lean_within_2pct(personas):
    shares = _bin_shares(personas, "political_lean")
    for lean in POLITICAL_LEANS:
        target = POLITICAL_LEAN_DISTRIBUTION_TX[lean]
        assert abs(shares.get(lean, 0) - target) <= 0.02, (
            lean,
            shares.get(lean, 0),
            target,
        )


def test_all_strata_present(personas):
    incomes = {p["income_bin"] for p in personas}
    ages = {p["age_bin"] for p in personas}
    regions = {p["zip_region"] for p in personas}
    leans = {p["political_lean"] for p in personas}
    assert incomes == set(INCOME_BINS)
    assert ages == set(AGE_BINS)
    assert regions == set(ZIP_REGIONS)
    # Independents are 1% of 300 -> 3 personas; should be present.
    assert "I" in leans and "R" in leans and "D" in leans


def test_unique_system_prompts(personas):
    assert len({p["system_prompt"] for p in personas}) == len(personas)


def test_prompts_use_shared_prefix(personas):
    for p in personas[:50]:
        assert p["system_prompt"].startswith(SHARED_PREFIX)
        assert "Texas" in p["system_prompt"]
        assert str(p["age"]) in p["system_prompt"]
