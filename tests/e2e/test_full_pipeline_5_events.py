"""End-to-end ablation test on synthetic data (5 events, 5 personas, 2 tickers).

Verifies that all 5+1 pipelines produce IC, panel t-stat, and supplementary
Sharpe entries without errors and that the resulting ``ablation_results.json``
matches the Section 9 schema:

    {
      "primary_table": {
        "lm_dictionary": { ... },
        "finbert": { ... },
        "nova_zero_shot": { ... },
        "persona_only": { ... },
        "persona_graph": { ... },
        "persona_graph_variance_signal": { ... }
      },
      "supplementary_sharpe": { ..., "caveat": str },
      "event_count": int,
      "event_ids": list[str],
      "sentinel_diagnostics": { ... }
    }

We bypass disk-side sources (no Bedrock, no GDELT) by writing mock parquet
files into a tmp directory, redirecting the pipeline registry to them, and
running ``build_ablation`` against an in-memory abnormal-returns frame.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.metrics.ablation import (
    PipelineSpec,
    build_ablation,
)
from src.metrics.signal_aggregation import build_signal_files
from src.metrics.interpret import interpret_results


N_EVENTS = 5
N_PERSONAS = 5
N_TICKERS = 2


def _make_events(tmp_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build synthetic events + abnormal-returns frames.

    Two tickers (TEXA, TEXB), 5 events, AR generated from the persona-graph
    "true" sentiment with noise so that the persona-graph IC > zero-shot IC
    by construction (lets us test both branches of interpret_results).
    """
    rng = np.random.default_rng(seed=2026_04_18)
    tickers = ["TEXA", "TEXB"]
    rows: list[dict[str, object]] = []
    for e in range(N_EVENTS):
        tick = tickers[e % len(tickers)]
        rows.append({"event_id": f"E{e:02d}", "ticker": tick})
    events = pd.DataFrame(rows)

    # Generate "true" persona-graph signal in [-1, 1].
    true_signal = rng.uniform(-0.8, 0.8, size=N_EVENTS)

    # AR = beta * true_signal + noise. beta=0.02, noise N(0, 0.01).
    ar_per_event = 0.02 * true_signal + rng.normal(0.0, 0.01, size=N_EVENTS)
    events["ar_1d"] = ar_per_event
    events["true_signal"] = true_signal

    ar_df = events[["event_id", "ticker", "ar_1d"]].copy()
    ar_df["market_return"] = 0.0
    ar_df["residual"] = ar_df["ar_1d"]
    ar_df["r_squared"] = 0.45
    ar_df["beta"] = 1.05
    ar_df["estimation_window_start"] = "2024-09-01"
    ar_df["estimation_window_end"] = "2025-08-31"

    return events, ar_df


def _make_persona_sentiments(events: pd.DataFrame, tmp_path: Path) -> Path:
    """Persona sentiments: per-event, per-persona, with post-dynamics columns.

    raw_sentiment has substantial noise so persona_only IC ~ moderate.
    post_dynamics_0.3 (the primary epsilon) is closer to true_signal so the
    persona+graph signal beats the persona_only signal.
    """
    rng = np.random.default_rng(seed=42)
    rows: list[dict[str, object]] = []
    for _, ev in events.iterrows():
        true_s = float(ev["true_signal"])
        for p in range(N_PERSONAS):
            raw = true_s + rng.normal(0.0, 0.45)
            raw = float(np.clip(raw, -1.0, 1.0))
            post02 = 0.7 * raw + 0.3 * true_s + rng.normal(0.0, 0.05)
            post03 = 0.5 * raw + 0.5 * true_s + rng.normal(0.0, 0.04)
            post04 = 0.3 * raw + 0.7 * true_s + rng.normal(0.0, 0.03)
            rows.append(
                {
                    "event_id": str(ev["event_id"]),
                    "persona_id": p,
                    "raw_sentiment": raw,
                    "post_dynamics_0.2": float(np.clip(post02, -1.0, 1.0)),
                    "post_dynamics_0.3": float(np.clip(post03, -1.0, 1.0)),
                    "post_dynamics_0.4": float(np.clip(post04, -1.0, 1.0)),
                }
            )
    df = pd.DataFrame(rows)
    out = tmp_path / "persona_sentiments.parquet"
    df.to_parquet(out, engine="pyarrow", index=False)
    return out


def _make_baseline_signal(
    name: str, events: pd.DataFrame, tmp_path: Path, *, noise_sigma: float
) -> Path:
    """Generate a baseline pipeline signal frame at *tmp_path/{name}.parquet*."""
    rng = np.random.default_rng(seed=hash(name) & 0xFFFF)
    rows = []
    for _, ev in events.iterrows():
        raw = float(ev["true_signal"]) + rng.normal(0.0, noise_sigma)
        raw = float(np.clip(raw, -1.0, 1.0))
        rows.append(
            {
                "event_id": str(ev["event_id"]),
                "mean_sentiment": raw,
                "sentiment_variance": None,
                "bimodality_index": None,
            }
        )
    df = pd.DataFrame(rows)
    out = tmp_path / f"signals_{name}.parquet"
    df.to_parquet(out, engine="pyarrow", index=False)
    return out


@pytest.fixture()
def ablation_tmp_setup(tmp_path: Path):
    events, ar_df = _make_events(tmp_path)

    # Persona sentiments + persona-only / persona-graph signal frames via C1.
    ps_path = _make_persona_sentiments(events, tmp_path)
    so_path = tmp_path / "signals_persona_only.parquet"
    sg_path = tmp_path / "signals_persona_graph.parquet"
    sg_sweep_path = tmp_path / "signals_persona_graph_eps_sweep.parquet"

    # Patch signal_aggregation outputs into tmp.
    from src.metrics import signal_aggregation as sa_mod

    sa_mod.SIGNALS_PERSONA_ONLY_PATH = so_path        # type: ignore[assignment]
    sa_mod.SIGNALS_PERSONA_GRAPH_PATH = sg_path       # type: ignore[assignment]
    sa_mod.SIGNALS_PERSONA_GRAPH_SWEEP_PATH = sg_sweep_path  # type: ignore[assignment]
    build_signal_files(persona_sentiments_path=ps_path, write=True)

    # Baselines.
    lm_path = _make_baseline_signal("lm", events, tmp_path, noise_sigma=0.50)
    fb_path = _make_baseline_signal("finbert", events, tmp_path, noise_sigma=0.40)
    zs_path = _make_baseline_signal(
        "zero_shot", events, tmp_path, noise_sigma=0.35
    )

    pipelines = [
        PipelineSpec("lm_dictionary", lm_path),
        PipelineSpec("finbert", fb_path),
        PipelineSpec("nova_zero_shot", zs_path),
        PipelineSpec("persona_only", so_path, is_persona=True),
        PipelineSpec("persona_graph", sg_path, is_persona=True),
    ]

    ar_path = tmp_path / "abnormal_returns.parquet"
    ar_df.to_parquet(ar_path, engine="pyarrow", index=False)

    sentinel_diag = {
        "variances": [0.18, 0.20, 0.16],
        "bimodality": [0.45, 0.62, 0.51],
        "gate_pass": True,
        "parse_failure_rate": 0.01,
    }
    sd_path = tmp_path / "sentinel_diagnostics.json"
    with sd_path.open("w", encoding="utf-8") as fh:
        json.dump(sentinel_diag, fh)

    # Patch ablation module output paths to tmp.
    from src.metrics import ablation as ab_mod

    ab_mod.ABLATION_RESULTS_JSON = tmp_path / "ablation_results.json"  # type: ignore[assignment]
    ab_mod.ABLATION_TABLE_CSV = tmp_path / "ablation_table.csv"        # type: ignore[assignment]
    ab_mod.ABNORMAL_RETURNS_PATH = ar_path                              # type: ignore[assignment]

    return {
        "pipelines": pipelines,
        "ar_path": ar_path,
        "tmp_path": tmp_path,
        "sentinel_diagnostics_path": sd_path,
    }


def test_ablation_produces_all_six_pipelines(ablation_tmp_setup) -> None:
    setup = ablation_tmp_setup
    result = build_ablation(
        pipelines=setup["pipelines"],
        ar_path=setup["ar_path"],
        sentinel_diagnostics_path=setup["sentinel_diagnostics_path"],
        bootstrap_resamples=200,  # smaller for speed
        write=True,
    )

    expected = {
        "lm_dictionary",
        "finbert",
        "nova_zero_shot",
        "persona_only",
        "persona_graph",
        "persona_graph_variance_signal",
    }
    assert set(result["primary_table"].keys()) == expected
    assert result["event_count"] == N_EVENTS
    assert len(result["event_ids"]) == N_EVENTS

    # Schema sanity: every non-variance row has IC + panel; variance row has
    # IC + note only.
    for name in expected - {"persona_graph_variance_signal"}:
        row = result["primary_table"][name]
        for k in (
            "ic_pearson",
            "ic_pearson_pvalue",
            "ic_spearman",
            "ic_spearman_pvalue",
            "panel_beta",
            "panel_se_clustered",
            "panel_tstat",
            "panel_pvalue",
        ):
            assert k in row, f"missing key {k!r} on pipeline {name!r}"

    var_row = result["primary_table"]["persona_graph_variance_signal"]
    assert "ic_pearson" in var_row
    assert "note" in var_row
    assert "variance" in var_row["note"].lower()

    # Supplementary Sharpe section.
    assert "caveat" in result["supplementary_sharpe"]
    for name in expected - {"persona_graph_variance_signal"}:
        entry = result["supplementary_sharpe"][name]
        if entry is None:
            continue
        assert "sharpe" in entry
        assert "sharpe_bootstrap_ci_95" in entry
        assert len(entry["sharpe_bootstrap_ci_95"]) == 2

    # Sentinel diagnostics passed through.
    assert result["sentinel_diagnostics"]["gate_pass"] is True

    # JSON file written and re-readable.
    from src.metrics import ablation as ab_mod

    payload = json.loads(ab_mod.ABLATION_RESULTS_JSON.read_text())
    assert payload["event_count"] == N_EVENTS
    assert payload["sentinel_diagnostics"]["gate_pass"] is True


def test_interpret_signal_branch_with_designed_persona_outperformance(
    ablation_tmp_setup,
) -> None:
    """The synthetic data is set up so persona_graph beats zero-shot.

    But because randomness can fluctuate, we only require the interpreter to
    run cleanly on whichever branch ends up; we then explicitly test BOTH
    branches by mocking inputs in :func:`test_interpret_collapse_branch`.
    """
    setup = ablation_tmp_setup
    result = build_ablation(
        pipelines=setup["pipelines"],
        ar_path=setup["ar_path"],
        sentinel_diagnostics_path=setup["sentinel_diagnostics_path"],
        bootstrap_resamples=100,
        write=False,
    )
    interp = interpret_results(result)
    assert interp.branch in {"signal", "collapse"}
    assert isinstance(interp.headline, str) and interp.headline
    assert isinstance(interp.narrative, str) and interp.narrative


def test_interpret_signal_branch_explicit() -> None:
    """Build a synthetic primary_table where persona_graph clearly beats
    zero-shot on both Pearson and Spearman, and verify the signal branch
    fires."""
    payload = {
        "primary_table": {
            "nova_zero_shot": {
                "ic_pearson": 0.05,
                "ic_pearson_pvalue": 0.45,
                "ic_spearman": 0.04,
                "ic_spearman_pvalue": 0.50,
            },
            "persona_graph": {
                "ic_pearson": 0.45,
                "ic_pearson_pvalue": 0.02,
                "ic_spearman": 0.40,
                "ic_spearman_pvalue": 0.04,
                "mean_variance": 0.21,
                "mean_bimodality": 0.62,
            },
        },
        "sentinel_diagnostics": {"gate_pass": True},
    }
    interp = interpret_results(payload)
    assert interp.branch == "signal"
    assert "social-graph" in interp.narrative.lower() or "graph" in interp.narrative.lower()


def test_interpret_collapse_branch_explicit() -> None:
    """Build a synthetic primary_table where persona_graph collapses (low
    variance, IC <= zero-shot)."""
    payload = {
        "primary_table": {
            "nova_zero_shot": {
                "ic_pearson": 0.30,
                "ic_pearson_pvalue": 0.02,
                "ic_spearman": 0.28,
                "ic_spearman_pvalue": 0.03,
            },
            "persona_graph": {
                "ic_pearson": 0.05,
                "ic_pearson_pvalue": 0.55,
                "ic_spearman": 0.04,
                "ic_spearman_pvalue": 0.60,
                "mean_variance": 0.04,
                "mean_bimodality": 0.31,
            },
        },
        "sentinel_diagnostics": {"gate_pass": False},
    }
    interp = interpret_results(payload)
    assert interp.branch == "collapse"
    assert "homogen" in interp.narrative.lower() or "collapse" in interp.narrative.lower()
    assert "0.04" in interp.narrative or "0.040" in interp.narrative


def test_ablation_csv_export_written(ablation_tmp_setup) -> None:
    setup = ablation_tmp_setup
    build_ablation(
        pipelines=setup["pipelines"],
        ar_path=setup["ar_path"],
        sentinel_diagnostics_path=setup["sentinel_diagnostics_path"],
        bootstrap_resamples=50,
        write=True,
    )
    from src.metrics import ablation as ab_mod
    csv_path = ab_mod.ABLATION_TABLE_CSV
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert "pipeline" in df.columns
    assert "ic_pearson" in df.columns
    # 5 base pipelines + variance row.
    assert len(df) == 6
