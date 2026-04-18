"""Unit tests for ``src.metrics.signal_aggregation`` (Workstream C1).

Synthetic-array contracts:
    (a) uniform input        -> mean / variance match closed-form values.
    (b) bimodal input        -> Sarle bimodality coefficient > 5/9 (~0.555).
    (c) collapsed input      -> variance == 0, bimodality == NaN (no /0 errors).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.metrics import signal_aggregation as sa


# ---------------------------------------------------------------------------
# (a) Uniform persona array -> expected mean / variance
# ---------------------------------------------------------------------------


def test_uniform_array_returns_expected_mean_and_variance() -> None:
    """Symmetric uniform array around 0 has known mean = 0 and known variance."""
    rng = np.random.default_rng(seed=42)
    values = rng.uniform(low=-1.0, high=1.0, size=300)

    agg = sa.aggregate_event(values)

    # Sample mean approaches 0 with 300 draws but is not exactly 0;
    # check both arithmetic agreement and tightness.
    assert agg.mean_sentiment == pytest.approx(float(values.mean()))
    assert agg.sentiment_variance == pytest.approx(
        float(np.var(values, ddof=0))
    )
    # Theoretical variance of U(-1, 1) = (b-a)^2 / 12 = 4/12 = 1/3.
    assert abs(agg.sentiment_variance - (1.0 / 3.0)) < 0.05


# ---------------------------------------------------------------------------
# (b) Bimodal input -> Sarle > 0.555
# ---------------------------------------------------------------------------


def test_bimodal_array_has_sarle_above_threshold() -> None:
    """A clearly bimodal mixture (two peaks at +/-0.8) exceeds Sarle threshold."""
    rng = np.random.default_rng(seed=2026)
    left = rng.normal(loc=-0.8, scale=0.05, size=150)
    right = rng.normal(loc=0.8, scale=0.05, size=150)
    values = np.concatenate([left, right])

    bimod = sa.sarle_bimodality(values)
    assert np.isfinite(bimod)
    assert bimod > sa.SARLE_BIMODAL_THRESHOLD, (
        f"Expected Sarle > {sa.SARLE_BIMODAL_THRESHOLD:.4f} for clearly bimodal "
        f"input, got {bimod:.4f}"
    )


# ---------------------------------------------------------------------------
# (c) Collapsed input -> var=0, Sarle NaN handled
# ---------------------------------------------------------------------------


def test_collapsed_array_variance_zero_and_bimodality_nan() -> None:
    """All-equal personas: variance is exactly 0, bimodality NaN, no exceptions."""
    values = np.full(200, 0.42, dtype=float)
    agg = sa.aggregate_event(values)
    assert agg.mean_sentiment == pytest.approx(0.42)
    assert agg.sentiment_variance == 0.0
    assert np.isnan(agg.bimodality_index)


def test_too_few_personas_returns_nan_bimodality() -> None:
    """Below 4 personas the Sarle coefficient is undefined; expect NaN."""
    values = np.array([0.1, -0.2, 0.3], dtype=float)
    bimod = sa.sarle_bimodality(values)
    assert np.isnan(bimod)


def test_aggregate_event_handles_all_nan() -> None:
    """All-NaN input does not blow up; returns all-NaN signals."""
    values = np.array([np.nan, np.nan, np.nan], dtype=float)
    agg = sa.aggregate_event(values)
    assert np.isnan(agg.mean_sentiment)
    assert np.isnan(agg.sentiment_variance)
    assert np.isnan(agg.bimodality_index)


# ---------------------------------------------------------------------------
# DataFrame-level entry points
# ---------------------------------------------------------------------------


def _synthetic_persona_sentiments(
    *, n_events: int = 4, n_personas: int = 50
) -> pd.DataFrame:
    """Build a small persona-sentiments parquet-like frame."""
    rng = np.random.default_rng(0)
    rows: list[dict[str, float | str | int]] = []
    for e in range(n_events):
        for p in range(n_personas):
            raw = float(rng.uniform(-1.0, 1.0))
            # Post-dynamics columns: smaller spread to mimic Deffuant convergence.
            post02 = 0.85 * raw
            post03 = 0.70 * raw
            post04 = 0.55 * raw
            rows.append(
                {
                    "event_id": f"E{e:02d}",
                    "persona_id": p,
                    "raw_sentiment": raw,
                    "post_dynamics_0.2": post02,
                    "post_dynamics_0.3": post03,
                    "post_dynamics_0.4": post04,
                }
            )
    return pd.DataFrame(rows)


def test_aggregate_persona_only_yields_one_row_per_event() -> None:
    df = _synthetic_persona_sentiments(n_events=4, n_personas=80)
    out = sa.aggregate_persona_only(df)
    assert set(out["event_id"]) == {f"E{e:02d}" for e in range(4)}
    assert (out["sentiment_variance"].notna()).all()
    assert (out["bimodality_index"].notna()).all()


def test_aggregate_persona_graph_uses_primary_epsilon() -> None:
    df = _synthetic_persona_sentiments(n_events=4, n_personas=80)
    out_primary = sa.aggregate_persona_graph(df, epsilon=0.3)
    out_other = sa.aggregate_persona_graph(df, epsilon=0.4)

    # Primary epsilon (0.3) gives larger spread than 0.4 in our synthetic data
    # (post04 = 0.55 * raw vs post03 = 0.70 * raw), so var(0.3) > var(0.4).
    assert (out_primary["sentiment_variance"].mean()
            > out_other["sentiment_variance"].mean())


def test_aggregate_persona_graph_sweep_has_all_epsilons() -> None:
    df = _synthetic_persona_sentiments(n_events=2, n_personas=60)
    sweep = sa.aggregate_persona_graph_sweep(df)
    assert "mean_sentiment_0.2" in sweep.columns
    assert "mean_sentiment_0.3" in sweep.columns
    assert "mean_sentiment_0.4" in sweep.columns
    assert len(sweep) == 2


def test_build_signal_files_round_trip(tmp_path) -> None:
    """End-to-end: write a fake persona_sentiments.parquet, run the driver,
    verify both signal parquets are produced with the expected schema."""
    df = _synthetic_persona_sentiments(n_events=3, n_personas=40)
    src_path = tmp_path / "persona_sentiments.parquet"
    df.to_parquet(src_path, engine="pyarrow", index=False)

    # Redirect output paths to tmp_path by monkeypatching module constants.
    import importlib

    out_only = tmp_path / "signals_persona_only.parquet"
    out_graph = tmp_path / "signals_persona_graph.parquet"
    out_sweep = tmp_path / "signals_persona_graph_eps_sweep.parquet"

    sa.SIGNALS_PERSONA_ONLY_PATH = out_only      # type: ignore[assignment]
    sa.SIGNALS_PERSONA_GRAPH_PATH = out_graph    # type: ignore[assignment]
    sa.SIGNALS_PERSONA_GRAPH_SWEEP_PATH = out_sweep  # type: ignore[assignment]

    try:
        result = sa.build_signal_files(src_path, write=True)
        assert out_only.exists()
        assert out_graph.exists()
        assert out_sweep.exists()
        assert set(result["persona_only"].columns) >= {
            "event_id",
            "mean_sentiment",
            "sentiment_variance",
            "bimodality_index",
        }
    finally:
        importlib.reload(sa)
