"""R9 mitigation: scripted clustered-SE manual verification (4-point check).

This is the test Architect MUST-FIX AI-3 requires. It must NEVER be skipped.

Sub-points (each is its own assertion):

    (a) cluster count reported by statsmodels equals the number of unique
        tickers (5), NOT the number of events (20).
    (b) ``use_correction=True`` flag is applied to the cluster covariance.
    (c) signal-coefficient t-stat differs by >= 10% (relative) between
        nonrobust and cluster-robust.
    (d) manual sandwich-formula cluster-robust SE for the signal coefficient
        matches statsmodels output within 1e-6 absolute.

The synthetic panel (5 tickers x 4 events) is constructed in
``src.metrics.clustered_se_test.build_synthetic_panel`` with a known
within-firm residual shock, so cluster correction is *meant* to bite.
"""

from __future__ import annotations

import pytest

from src.metrics.clustered_se_test import (
    MANUAL_TOLERANCE,
    MIN_TSTAT_DELTA_FRACTION,
    N_OBS,
    N_TICKERS,
    run_manual_check,
)


@pytest.fixture(scope="module")
def manual_result():
    return run_manual_check()


def test_a_cluster_count_equals_unique_tickers(manual_result) -> None:
    """(a) cluster count must equal unique tickers, not unique events."""
    assert manual_result.n_clusters_reported == N_TICKERS, (
        f"statsmodels reported n_clusters={manual_result.n_clusters_reported}, "
        f"expected {N_TICKERS} (number of unique tickers)."
    )
    assert manual_result.n_clusters_reported != N_OBS, (
        "Cluster count equals event count - statsmodels is treating each "
        "observation as its own cluster, which is wrong."
    )
    assert manual_result.n_unique_tickers == N_TICKERS
    assert manual_result.cluster_count_ok is True


def test_b_small_cluster_df_correction_is_applied(manual_result) -> None:
    """(b) statsmodels' ``use_correction=True`` flag must be on the cov."""
    assert manual_result.use_correction_flag is True
    assert manual_result.df_adjustment_ok is True


def test_c_tstat_changes_meaningfully_between_nonrobust_and_clustered(
    manual_result,
) -> None:
    """(c) Cluster-robust SE should change the t-stat by at least 10%."""
    assert manual_result.tstat_relative_delta >= MIN_TSTAT_DELTA_FRACTION, (
        f"Expected |t_clustered - t_nonrobust| / |t_nonrobust| >= "
        f"{MIN_TSTAT_DELTA_FRACTION:.0%}; got "
        f"{manual_result.tstat_relative_delta:.3%}. "
        f"t_nonrobust={manual_result.tstat_nonrobust:.3f}, "
        f"t_clustered={manual_result.tstat_clustered:.3f}."
    )
    assert manual_result.tstat_difference_ok is True


def test_d_manual_sandwich_se_matches_statsmodels(manual_result) -> None:
    """(d) Hand-computed cluster-robust SE within 1e-6 of statsmodels."""
    assert manual_result.se_absolute_difference < MANUAL_TOLERANCE, (
        f"Manual SE = {manual_result.se_clustered_manual:.10f}, "
        f"statsmodels SE = {manual_result.se_clustered_statsmodels:.10f}, "
        f"|diff| = {manual_result.se_absolute_difference:.2e} >= "
        f"tolerance {MANUAL_TOLERANCE:.2e}."
    )
    assert manual_result.manual_se_match_ok is True


def test_all_four_subpoints_pass_simultaneously(manual_result) -> None:
    """Convenience aggregate assertion: every sub-point passed."""
    assert manual_result.all_checks_passed is True, (
        f"At least one of the four R9 sub-points failed: "
        f"a={manual_result.cluster_count_ok}, "
        f"b={manual_result.df_adjustment_ok}, "
        f"c={manual_result.tstat_difference_ok}, "
        f"d={manual_result.manual_se_match_ok}"
    )
