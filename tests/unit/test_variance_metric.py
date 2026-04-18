"""Unit tests for inter-persona variance computation.

Sentinel acceptance criterion: ``population_variance`` returns the right value
for both uniform and collapsed inputs and is robust to NaNs.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.metrics.signal_aggregation import population_variance


def test_uniform_distribution_variance_close_to_theoretical() -> None:
    """U(-1, 1) variance approaches 1/3 in the large-sample limit."""
    rng = np.random.default_rng(seed=12)
    values = rng.uniform(-1.0, 1.0, size=10_000)
    var = population_variance(values)
    assert var == pytest.approx(1.0 / 3.0, abs=0.02)


def test_collapsed_input_variance_zero() -> None:
    values = np.full(50, -0.42)
    var = population_variance(values)
    assert var == 0.0


def test_two_point_variance_known() -> None:
    """Symmetric two-point distribution at +/-0.5 has variance = 0.25."""
    values = np.concatenate([np.full(100, -0.5), np.full(100, 0.5)])
    var = population_variance(values)
    assert var == pytest.approx(0.25, abs=1e-9)


def test_single_observation_returns_nan() -> None:
    var = population_variance(np.array([0.3]))
    assert np.isnan(var)


def test_all_nan_input_returns_nan() -> None:
    var = population_variance(np.array([np.nan, np.nan]))
    assert np.isnan(var)


def test_partial_nan_dropped_then_computed() -> None:
    values = np.array([0.0, 0.0, np.nan, 0.0, 0.0])
    var = population_variance(values)
    assert var == pytest.approx(0.0)


def test_ddof_zero_matches_numpy() -> None:
    """Verify our implementation uses ddof=0 (population) not ddof=1 (sample)."""
    rng = np.random.default_rng(seed=5)
    values = rng.normal(0.0, 1.0, size=100)
    assert population_variance(values) == pytest.approx(
        float(np.var(values, ddof=0))
    )
    # And make sure it does NOT match ddof=1 (would be off by factor n/(n-1)).
    assert population_variance(values) != pytest.approx(
        float(np.var(values, ddof=1))
    )
