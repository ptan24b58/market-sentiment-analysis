"""Unit tests for Sarle's bimodality coefficient on canonical distributions.

Reference values:

    * Standard normal N(0, 1):
        skew g1 ~ 0, excess kurtosis ~ 0 -> g2 ~ 3.
        Sarle = (0 + 1) / 3 ~ 0.333  -> well below the 0.555 threshold.

    * Symmetric two-point mixture (50% at -a, 50% at +a):
        skew g1 = 0, kurtosis g2 = 1.
        Sarle = (0 + 1) / 1 = 1.0  -> well above the 0.555 threshold
        (this is the unconditional "perfect bimodality" case).

    * Uniform on [-1, 1]:
        skew = 0, kurtosis = 1.8 -> Sarle = 1 / 1.8 ~ 0.556 (right at the
        threshold; we test a loose bound).
"""

from __future__ import annotations

import numpy as np
import pytest

from src.metrics.signal_aggregation import (
    SARLE_BIMODAL_THRESHOLD,
    sample_kurtosis,
    sample_skewness,
    sarle_bimodality,
)


def test_normal_distribution_below_threshold() -> None:
    rng = np.random.default_rng(seed=2026_04_18)
    values = rng.normal(0.0, 1.0, size=2000)
    bimod = sarle_bimodality(values)
    assert np.isfinite(bimod)
    assert bimod < SARLE_BIMODAL_THRESHOLD, (
        f"Standard normal should be < {SARLE_BIMODAL_THRESHOLD:.3f}; got {bimod:.3f}"
    )


def test_two_point_mixture_well_above_threshold() -> None:
    """Symmetric two-point distribution -> Sarle ~ 1.0."""
    half = 1000
    values = np.concatenate(
        [np.full(half, -0.5), np.full(half, 0.5)]
    )
    # NOTE: a true two-point distribution has g1 = 0, g2 = 1 -> Sarle = 1.0.
    # We verify Sarle is close to 1.0 and well above the threshold.
    bimod = sarle_bimodality(values)
    assert bimod == pytest.approx(1.0, abs=1e-9)
    assert bimod > SARLE_BIMODAL_THRESHOLD


def test_uniform_distribution_near_threshold() -> None:
    """U(-1, 1) has Sarle ~ 0.556 - very near the 5/9 threshold."""
    rng = np.random.default_rng(seed=7)
    values = rng.uniform(-1.0, 1.0, size=5000)
    bimod = sarle_bimodality(values)
    # Theoretical value 1 / 1.8 = 0.5556. Allow generous tolerance for finite
    # sample estimation.
    assert 0.45 < bimod < 0.65


def test_skewness_zero_for_symmetric() -> None:
    rng = np.random.default_rng(seed=3)
    values = rng.normal(0.0, 1.0, size=10_000)
    g1 = sample_skewness(values)
    assert abs(g1) < 0.1


def test_kurtosis_three_for_normal() -> None:
    rng = np.random.default_rng(seed=4)
    values = rng.normal(0.0, 1.0, size=20_000)
    g2 = sample_kurtosis(values)
    # g2 here is *non-excess* kurtosis; normal has g2 = 3.
    assert abs(g2 - 3.0) < 0.2


def test_kurtosis_one_for_two_point() -> None:
    """Two-point symmetric distribution has kurtosis exactly 1.0."""
    values = np.concatenate([np.full(500, -1.0), np.full(500, 1.0)])
    g2 = sample_kurtosis(values)
    assert g2 == pytest.approx(1.0, abs=1e-9)


def test_sarle_undefined_for_constant() -> None:
    values = np.full(100, 0.7)
    bimod = sarle_bimodality(values)
    assert np.isnan(bimod)


def test_sarle_handles_nans_gracefully() -> None:
    values = np.array([0.1, np.nan, -0.2, np.nan, 0.3, 0.4, 0.5, np.nan])
    bimod = sarle_bimodality(values)
    # 5 valid points, >=4 - should produce a finite or NaN value but not raise.
    assert np.isfinite(bimod) or np.isnan(bimod)
