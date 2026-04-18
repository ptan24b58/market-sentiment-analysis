"""Workstream C2: Full ablation table assembly.

For each of six pipelines

    1. lm_dictionary
    2. finbert
    3. nova_zero_shot
    4. persona_only
    5. persona_graph
    6. persona_graph_variance_signal   (IC computed on |variance| vs |AR|)

compute the primary table:

    * IC (Pearson)        + p-value
    * IC (Spearman rank)  + p-value
    * Panel beta, clustered SE, t-stat, p-value (only for non-variance rows;
      the variance-signal row is left as IC-only because the panel covariate
      is the absolute value of variance, which we do not regress on AR
      directly - that would conflate signed and unsigned effects).

and the supplementary section:

    * Tercile spread Sharpe with bootstrap 95% CI.

All computations are restricted to the SAME event set (intersection of
event_ids across all signal frames and the abnormal-returns frame). Outputs:

    * data/ablation_results.json   (per Section 9 schema)
    * data/ablation_table.csv      (UI / poster export)

See plan Section 4 (C2), Section 9 (ablation_results.json).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from src.config import DATA_DIR
from src.metrics.event_study import PanelResult, panel_regression
from src.metrics.supplementary_sharpe import (
    CAVEAT_TEXT,
    SharpeResult,
    tercile_sharpe,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline registration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineSpec:
    """Describes how to source a pipeline's signal frame."""

    name: str
    signal_path: Path
    signal_col: str = "mean_sentiment"
    is_persona: bool = False  # also has variance/bimodality columns


# Default registry. The orchestrator may override these with custom paths
# (e.g. for the e2e test using mock data).
DEFAULT_PIPELINES: list[PipelineSpec] = [
    PipelineSpec("lm_dictionary",  DATA_DIR / "signals_lm.parquet",            "mean_sentiment"),
    PipelineSpec("finbert",        DATA_DIR / "signals_finbert.parquet",       "mean_sentiment"),
    PipelineSpec("nova_zero_shot", DATA_DIR / "signals_zero_shot.parquet",     "mean_sentiment"),
    PipelineSpec("persona_only",   DATA_DIR / "signals_persona_only.parquet",  "mean_sentiment", is_persona=True),
    PipelineSpec("persona_graph",  DATA_DIR / "signals_persona_graph.parquet", "mean_sentiment", is_persona=True),
]


ABNORMAL_RETURNS_PATH: Path = DATA_DIR / "abnormal_returns.parquet"
ABLATION_RESULTS_JSON: Path = DATA_DIR / "ablation_results.json"
ABLATION_TABLE_CSV:    Path = DATA_DIR / "ablation_table.csv"


# ---------------------------------------------------------------------------
# IC helpers
# ---------------------------------------------------------------------------


def _ic(signal: np.ndarray, ar: np.ndarray) -> tuple[float, float, float, float]:
    """Return (pearson_r, pearson_p, spearman_rho, spearman_p).

    NaN-safe: drops rows with any NaN. If fewer than 3 valid observations or
    zero variance in either series, the corresponding statistic is NaN.
    """
    s = np.asarray(signal, dtype=float)
    a = np.asarray(ar, dtype=float)
    mask = ~(np.isnan(s) | np.isnan(a))
    s = s[mask]
    a = a[mask]
    if s.size < 3:
        return float("nan"), float("nan"), float("nan"), float("nan")
    if np.std(s) == 0.0 or np.std(a) == 0.0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    pr = stats.pearsonr(s, a)
    sr = stats.spearmanr(s, a)
    return float(pr.statistic), float(pr.pvalue), float(sr.statistic), float(sr.pvalue)


# ---------------------------------------------------------------------------
# Pipeline-row computation
# ---------------------------------------------------------------------------


@dataclass
class PipelineRow:
    """Single row of the primary ablation table."""

    name: str
    ic_pearson: float
    ic_pearson_pvalue: float
    ic_spearman: float
    ic_spearman_pvalue: float
    panel: PanelResult | None = None
    mean_variance: float | None = None
    mean_bimodality: float | None = None
    note: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_primary_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ic_pearson": self.ic_pearson,
            "ic_pearson_pvalue": self.ic_pearson_pvalue,
            "ic_spearman": self.ic_spearman,
            "ic_spearman_pvalue": self.ic_spearman_pvalue,
        }
        if self.panel is not None:
            out["panel_beta"] = self.panel.beta
            out["panel_se_clustered"] = self.panel.se_clustered
            out["panel_tstat"] = self.panel.tstat
            out["panel_pvalue"] = self.panel.pvalue
            out["panel_n_obs"] = self.panel.n_obs
            out["panel_n_clusters"] = self.panel.n_clusters
            out["panel_used_correction"] = self.panel.used_correction
        if self.mean_variance is not None:
            out["mean_variance"] = self.mean_variance
        if self.mean_bimodality is not None:
            out["mean_bimodality"] = self.mean_bimodality
        if self.note:
            out["note"] = self.note
        out.update(self.extra)
        return out


def _load_signal(spec: PipelineSpec) -> pd.DataFrame:
    if not spec.signal_path.exists():
        raise FileNotFoundError(
            f"Signal parquet for pipeline {spec.name!r} not found at "
            f"{spec.signal_path}."
        )
    df = pd.read_parquet(spec.signal_path, engine="pyarrow")
    if spec.signal_col not in df.columns:
        raise KeyError(
            f"Pipeline {spec.name!r}: column {spec.signal_col!r} missing from "
            f"{spec.signal_path}; have {sorted(df.columns)}"
        )
    if "event_id" not in df.columns:
        raise KeyError(f"Pipeline {spec.name!r}: 'event_id' column missing from {spec.signal_path}")
    return df


def _restrict_to_event_set(
    signal_df: pd.DataFrame, ar_df: pd.DataFrame, event_ids: list[str]
) -> pd.DataFrame:
    """Inner-join signal x AR on event_id, restricted to *event_ids*.

    Returns one row per (event, ticker) so the panel regression has the
    correct shape.
    """
    sig = signal_df[signal_df["event_id"].isin(event_ids)].copy()
    ar = ar_df[ar_df["event_id"].isin(event_ids)].copy()
    merged = ar.merge(sig, on="event_id", how="inner", validate="many_to_one")
    return merged


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def compute_pipeline_row(
    spec: PipelineSpec,
    ar_df: pd.DataFrame,
    event_ids: list[str],
) -> PipelineRow:
    """Compute IC + panel metrics for one pipeline."""
    sig_df = _load_signal(spec)
    panel_df = _restrict_to_event_set(sig_df, ar_df, event_ids)
    panel_df = panel_df.rename(columns={spec.signal_col: "signal"})

    ic_pr, ic_pp, ic_sr, ic_sp = _ic(
        panel_df["signal"].to_numpy(), panel_df["ar_1d"].to_numpy()
    )

    panel: PanelResult | None
    try:
        panel = panel_regression(
            panel_df,
            signal_col="signal",
            ar_col="ar_1d",
            cluster_col="ticker",
        )
    except Exception as exc:  # pragma: no cover - degenerate ablation rows
        logger.warning(
            "Panel regression failed for %s: %s", spec.name, exc
        )
        panel = None

    mean_var: float | None = None
    mean_bimod: float | None = None
    if spec.is_persona:
        if "sentiment_variance" in sig_df.columns:
            v = sig_df.loc[sig_df["event_id"].isin(event_ids), "sentiment_variance"]
            mean_var = float(v.dropna().mean()) if not v.empty else None
        if "bimodality_index" in sig_df.columns:
            b = sig_df.loc[sig_df["event_id"].isin(event_ids), "bimodality_index"]
            mean_bimod = float(b.dropna().mean()) if not b.empty else None

    return PipelineRow(
        name=spec.name,
        ic_pearson=ic_pr,
        ic_pearson_pvalue=ic_pp,
        ic_spearman=ic_sr,
        ic_spearman_pvalue=ic_sp,
        panel=panel,
        mean_variance=mean_var,
        mean_bimodality=mean_bimod,
    )


def compute_variance_signal_row(
    persona_graph_signal_df: pd.DataFrame,
    ar_df: pd.DataFrame,
    event_ids: list[str],
) -> PipelineRow:
    """Special row: IC of |variance| vs |AR|.

    High inter-persona variance on polarising events may correlate with
    large |AR| magnitudes (regardless of sign). This is the "variance as
    signal" diagnostic Architect Violation 2 / Critic M2 require in the
    primary table.
    """
    if "sentiment_variance" not in persona_graph_signal_df.columns:
        raise KeyError(
            "persona_graph signal frame missing 'sentiment_variance' column"
        )
    sig = persona_graph_signal_df[
        persona_graph_signal_df["event_id"].isin(event_ids)
    ].copy()
    sig = sig[["event_id", "sentiment_variance"]].rename(
        columns={"sentiment_variance": "abs_variance"}
    )
    sig["abs_variance"] = sig["abs_variance"].astype(float).abs()

    ar = ar_df[ar_df["event_id"].isin(event_ids)].copy()
    # Aggregate to one row per event by averaging |ar_1d| (handles
    # multi-ticker per event).
    ar["abs_ar"] = ar["ar_1d"].astype(float).abs()
    ar_per_event = ar.groupby("event_id", as_index=False)["abs_ar"].mean()

    merged = sig.merge(ar_per_event, on="event_id", how="inner")

    ic_pr, ic_pp, ic_sr, ic_sp = _ic(
        merged["abs_variance"].to_numpy(), merged["abs_ar"].to_numpy()
    )

    return PipelineRow(
        name="persona_graph_variance_signal",
        ic_pearson=ic_pr,
        ic_pearson_pvalue=ic_pp,
        ic_spearman=ic_sr,
        ic_spearman_pvalue=ic_sp,
        panel=None,
        note="IC computed on |sentiment_variance| vs |AR|",
    )


def compute_supplementary_sharpe_row(
    spec: PipelineSpec,
    ar_df: pd.DataFrame,
    event_ids: list[str],
    bootstrap_resamples: int,
) -> SharpeResult | None:
    """One supplementary-Sharpe entry per non-variance pipeline."""
    sig_df = _load_signal(spec)
    panel_df = _restrict_to_event_set(sig_df, ar_df, event_ids)
    panel_df = panel_df.rename(columns={spec.signal_col: "signal"})
    # For Sharpe we want one row per event, so collapse to event-level by
    # averaging when multiple tickers map to the same event.
    per_event = panel_df.groupby("event_id", as_index=False).agg(
        {"signal": "mean", "ar_1d": "mean"}
    )
    if len(per_event) < 3:
        logger.warning(
            "Skipping supplementary Sharpe for %s: too few events (%d).",
            spec.name,
            len(per_event),
        )
        return None
    return tercile_sharpe(
        per_event["signal"].to_numpy(),
        per_event["ar_1d"].to_numpy(),
        bootstrap_resamples=bootstrap_resamples,
    )


def build_ablation(
    pipelines: list[PipelineSpec] | None = None,
    ar_path: Path | str = ABNORMAL_RETURNS_PATH,
    sentinel_diagnostics_path: Path | str | None = DATA_DIR / "sentinel_diagnostics.json",
    bootstrap_resamples: int = 1000,
    write: bool = True,
) -> dict[str, Any]:
    """Compute the full ablation results dict and (optionally) persist it.

    Parameters
    ----------
    pipelines:
        List of pipeline specs. Defaults to :data:`DEFAULT_PIPELINES`.
    ar_path:
        Path to ``abnormal_returns.parquet``.
    sentinel_diagnostics_path:
        Path to ``sentinel_diagnostics.json`` (optional). If present, the
        contents are folded into the result under ``"sentinel_diagnostics"``.
    bootstrap_resamples:
        Bootstrap resample count for the supplementary Sharpe section.
    write:
        Persist ``ablation_results.json`` and ``ablation_table.csv`` under
        ``DATA_DIR``.

    Returns
    -------
    dict
        Matches the ``ablation_results.json`` schema in plan Section 9.
    """
    pipelines = pipelines or DEFAULT_PIPELINES
    ar_path = Path(ar_path)
    if not ar_path.exists():
        raise FileNotFoundError(
            f"abnormal_returns parquet not found at {ar_path}."
        )
    ar_df = pd.read_parquet(ar_path, engine="pyarrow")

    # Find common event-id intersection across all signal frames + AR frame.
    event_id_sets: list[set[str]] = [set(ar_df["event_id"].astype(str).unique())]
    for spec in pipelines:
        sig_df = _load_signal(spec)
        event_id_sets.append(set(sig_df["event_id"].astype(str).unique()))
    common = sorted(set.intersection(*event_id_sets))
    logger.info(
        "build_ablation: %d events in common across %d pipelines + AR",
        len(common),
        len(pipelines),
    )

    primary_table: dict[str, Any] = {}
    persona_graph_signal_df: pd.DataFrame | None = None
    for spec in pipelines:
        row = compute_pipeline_row(spec, ar_df, common)
        primary_table[spec.name] = row.to_primary_dict()
        if spec.name == "persona_graph":
            persona_graph_signal_df = _load_signal(spec)

    # Variance-signal row (only if persona_graph present).
    if persona_graph_signal_df is not None:
        try:
            variance_row = compute_variance_signal_row(
                persona_graph_signal_df, ar_df, common
            )
            primary_table[variance_row.name] = variance_row.to_primary_dict()
        except KeyError as e:
            logger.warning("variance-signal row skipped: %s", e)

    # Supplementary Sharpe.
    supplementary: dict[str, Any] = {"caveat": CAVEAT_TEXT}
    for spec in pipelines:
        sharpe = compute_supplementary_sharpe_row(
            spec, ar_df, common, bootstrap_resamples
        )
        if sharpe is None:
            supplementary[spec.name] = None
        else:
            supplementary[spec.name] = {
                "sharpe": sharpe.sharpe,
                "sharpe_bootstrap_ci_95": list(sharpe.sharpe_bootstrap_ci_95),
                "n_top": sharpe.n_top,
                "n_bottom": sharpe.n_bottom,
                "bootstrap_resamples": sharpe.bootstrap_resamples,
            }

    sentinel_diag: dict[str, Any] = {}
    if sentinel_diagnostics_path is not None:
        sd_path = Path(sentinel_diagnostics_path)
        if sd_path.exists():
            with sd_path.open("r", encoding="utf-8") as fh:
                sentinel_diag = json.load(fh)
        else:
            logger.info("sentinel_diagnostics.json not found at %s", sd_path)

    result: dict[str, Any] = {
        "primary_table": primary_table,
        "supplementary_sharpe": supplementary,
        "event_count": len(common),
        "event_ids": common,
        "sentinel_diagnostics": sentinel_diag,
    }

    if write:
        _write_outputs(result)

    return result


def _write_outputs(result: dict[str, Any]) -> None:
    """Persist JSON + CSV outputs."""
    ABLATION_RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with ABLATION_RESULTS_JSON.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=_json_default)
    logger.info("Wrote %s", ABLATION_RESULTS_JSON)

    rows: list[dict[str, Any]] = []
    for name, payload in result["primary_table"].items():
        flat = {"pipeline": name}
        flat.update(payload)
        rows.append(flat)
    df = pd.DataFrame(rows)
    df.to_csv(ABLATION_TABLE_CSV, index=False)
    logger.info("Wrote %s (%d rows)", ABLATION_TABLE_CSV, len(df))


def _json_default(obj: Any) -> Any:
    """JSON serialiser for numpy/pathlib types."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Cannot JSON-serialise {type(obj).__name__}: {obj!r}")


__all__ = [
    "PipelineSpec",
    "PipelineRow",
    "DEFAULT_PIPELINES",
    "ABNORMAL_RETURNS_PATH",
    "ABLATION_RESULTS_JSON",
    "ABLATION_TABLE_CSV",
    "compute_pipeline_row",
    "compute_variance_signal_row",
    "compute_supplementary_sharpe_row",
    "build_ablation",
]
