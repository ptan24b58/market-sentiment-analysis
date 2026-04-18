"""Workstream C1: Signal aggregation across personas per event.

For each event, reduces a vector of per-persona sentiment scores to a small
set of aggregate signals consumed by the ablation table:

    * ``mean_sentiment``     - arithmetic mean across personas
    * ``sentiment_variance`` - inter-persona variance (population, ddof=0)
    * ``bimodality_index``   - Sarle's coefficient ``(g1**2 + 1) / g2``,
                               where ``g1`` is sample skewness and ``g2`` is
                               kurtosis (NOT excess - i.e. excess + 3).
                               Values > 0.555 suggest bimodality.

Two output parquets are produced from ``data/persona_sentiments.parquet``:

    * ``signals_persona_only.parquet``   - on ``raw_sentiment`` (pre-dynamics)
    * ``signals_persona_graph.parquet``  - on ``post_dynamics_<eps>`` for the
                                           primary epsilon (default 0.3).

A diagnostic ``signals_persona_graph_eps_sweep.parquet`` is also persisted
with mean/variance for every epsilon column present.

See plan Section 4 (C1) and Section 9 (signals_{pipeline}.parquet schema).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DATA_DIR, DEFFUANT_EPSILON_PRIMARY, DEFFUANT_EPSILON_SWEEP

logger = logging.getLogger(__name__)


# Output paths.
PERSONA_SENTIMENTS_PATH: Path = DATA_DIR / "persona_sentiments.parquet"
SIGNALS_PERSONA_ONLY_PATH: Path = DATA_DIR / "signals_persona_only.parquet"
SIGNALS_PERSONA_GRAPH_PATH: Path = DATA_DIR / "signals_persona_graph.parquet"
SIGNALS_PERSONA_GRAPH_SWEEP_PATH: Path = (
    DATA_DIR / "signals_persona_graph_eps_sweep.parquet"
)

# Sarle-bimodality decision threshold (informational; reported in diagnostics).
SARLE_BIMODAL_THRESHOLD: float = 5.0 / 9.0  # ~ 0.5556

# Numerical-zero tolerance: arrays whose population variance falls below
# this threshold are treated as constant (m2 ~= 0 due to float arithmetic
# alone, e.g. ``np.var(np.full(N, c)) ~ 1e-32``).
_VARIANCE_ZERO_TOL: float = 1e-15


@dataclass(frozen=True)
class AggregateSignals:
    """Three primary aggregate signals per event."""

    mean_sentiment: float
    sentiment_variance: float
    bimodality_index: float


# ---------------------------------------------------------------------------
# Pure-numpy primitives (testable in isolation)
# ---------------------------------------------------------------------------


def _drop_nan(values: np.ndarray) -> np.ndarray:
    """Remove NaN entries from *values*; returns a new ndarray."""
    arr = np.asarray(values, dtype=float).ravel()
    return arr[~np.isnan(arr)]


def population_variance(values: np.ndarray) -> float:
    """Inter-persona variance with ``ddof=0``.

    Returns ``nan`` when fewer than 2 non-NaN observations are present.
    Degenerate (all-equal) inputs return 0.0 by definition. To guard
    against float-arithmetic dust (e.g. ``np.var(np.full(N, c))`` returning
    ~1e-32 instead of exactly 0.0) we snap any sub-tolerance variance to 0.
    """
    arr = _drop_nan(values)
    if arr.size < 2:
        return float("nan")
    var = float(np.var(arr, ddof=0))
    if abs(var) < _VARIANCE_ZERO_TOL:
        return 0.0
    return var


def sample_skewness(values: np.ndarray) -> float:
    """Sample skewness ``g1`` (Fisher-Pearson, biased / population form).

    ``g1 = m3 / m2**1.5`` where ``mk`` is the kth central moment. Returns
    ``nan`` for fewer than 3 observations or numerically-zero variance.
    """
    arr = _drop_nan(values)
    if arr.size < 3:
        return float("nan")
    mean = float(arr.mean())
    centered = arr - mean
    m2 = float(np.mean(centered ** 2))
    m3 = float(np.mean(centered ** 3))
    if m2 <= _VARIANCE_ZERO_TOL:
        return float("nan")
    return m3 / (m2 ** 1.5)


def sample_kurtosis(values: np.ndarray) -> float:
    """Sample kurtosis ``g2`` (NOT excess; i.e. ``m4 / m2**2``).

    Returns ``nan`` for fewer than 4 observations or numerically-zero
    variance. A normal distribution has g2 = 3.0 (excess kurtosis = 0).
    """
    arr = _drop_nan(values)
    if arr.size < 4:
        return float("nan")
    mean = float(arr.mean())
    centered = arr - mean
    m2 = float(np.mean(centered ** 2))
    m4 = float(np.mean(centered ** 4))
    if m2 <= _VARIANCE_ZERO_TOL:
        return float("nan")
    return m4 / (m2 ** 2)


def sarle_bimodality(values: np.ndarray) -> float:
    """Sarle's bimodality coefficient.

    Definition (per spec): ``b = (g1**2 + 1) / g2`` where ``g1`` is sample
    skewness and ``g2`` is kurtosis (excess kurtosis + 3). Values > 5/9
    (~0.5556) suggest bimodality.

    Edge cases:
        * fewer than 4 non-NaN points              -> NaN
        * numerically-zero variance (constant arr) -> NaN
        * g2 == 0                                  -> NaN (avoid /0)
    """
    arr = _drop_nan(values)
    if arr.size < 4:
        return float("nan")
    # Detect "constant" arrays before computing moments to avoid divide-by-
    # tiny-floating-point-dust returning a finite junk value.
    if population_variance(arr) == 0.0:
        return float("nan")
    g1 = sample_skewness(arr)
    g2 = sample_kurtosis(arr)
    if not np.isfinite(g1) or not np.isfinite(g2) or g2 == 0.0:
        return float("nan")
    return float((g1 ** 2 + 1.0) / g2)


def aggregate_event(values: np.ndarray) -> AggregateSignals:
    """Compute the three primary aggregate signals for one event."""
    arr = _drop_nan(values)
    if arr.size == 0:
        return AggregateSignals(float("nan"), float("nan"), float("nan"))
    mean = float(arr.mean()) if arr.size >= 1 else float("nan")
    var = population_variance(arr)
    bimod = sarle_bimodality(arr)
    return AggregateSignals(mean, var, bimod)


# ---------------------------------------------------------------------------
# DataFrame entry points
# ---------------------------------------------------------------------------


def _aggregate_by_event(
    df: pd.DataFrame,
    score_col: str,
) -> pd.DataFrame:
    """Group *df* by ``event_id`` and apply :func:`aggregate_event` to *score_col*.

    Returns a tidy frame with columns
    ``[event_id, mean_sentiment, sentiment_variance, bimodality_index]``.
    """
    if score_col not in df.columns:
        raise KeyError(
            f"Column {score_col!r} not present in persona sentiments DataFrame "
            f"(have: {sorted(df.columns)})"
        )

    rows: list[dict[str, float | str]] = []
    for event_id, group in df.groupby("event_id", sort=True):
        agg = aggregate_event(group[score_col].to_numpy(dtype=float))
        rows.append(
            {
                "event_id": str(event_id),
                "mean_sentiment": agg.mean_sentiment,
                "sentiment_variance": agg.sentiment_variance,
                "bimodality_index": agg.bimodality_index,
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("event_id").reset_index(drop=True)
    logger.info(
        "Aggregated %d events from column %r (mean_sentiment summary: "
        "mean=%.4f, std=%.4f)",
        len(out),
        score_col,
        float(out["mean_sentiment"].mean()) if len(out) else float("nan"),
        float(out["mean_sentiment"].std(ddof=0)) if len(out) > 1 else float("nan"),
    )
    return out


def aggregate_persona_only(
    persona_sentiments: pd.DataFrame,
) -> pd.DataFrame:
    """Build the persona-only signal frame (``raw_sentiment``)."""
    return _aggregate_by_event(persona_sentiments, "raw_sentiment")


def aggregate_persona_graph(
    persona_sentiments: pd.DataFrame,
    epsilon: float = DEFFUANT_EPSILON_PRIMARY,
) -> pd.DataFrame:
    """Build the persona+graph signal frame from ``post_dynamics_{eps}``."""
    col = _post_dynamics_col(epsilon)
    return _aggregate_by_event(persona_sentiments, col)


def aggregate_persona_graph_sweep(
    persona_sentiments: pd.DataFrame,
    epsilons: list[float] | None = None,
) -> pd.DataFrame:
    """Wide table with mean/variance per epsilon column.

    Useful for the sensitivity-to-epsilon supplementary appendix referenced in
    plan Section 10 open-question 1.
    """
    epsilons = epsilons if epsilons is not None else list(DEFFUANT_EPSILON_SWEEP)
    frames: list[pd.DataFrame] = []
    for eps in epsilons:
        col = _post_dynamics_col(eps)
        if col not in persona_sentiments.columns:
            logger.warning("Skipping epsilon=%.2f: column %s missing", eps, col)
            continue
        agg = _aggregate_by_event(persona_sentiments, col)
        agg = agg.rename(
            columns={
                "mean_sentiment": f"mean_sentiment_{eps:g}",
                "sentiment_variance": f"sentiment_variance_{eps:g}",
                "bimodality_index": f"bimodality_index_{eps:g}",
            }
        )
        frames.append(agg)

    if not frames:
        logger.warning("No epsilon columns found for sweep aggregation.")
        return pd.DataFrame(columns=["event_id"])

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on="event_id", how="outer")
    return merged.sort_values("event_id").reset_index(drop=True)


def _post_dynamics_col(epsilon: float) -> str:
    """Return the parquet column name for the given Deffuant epsilon."""
    # The columns are persisted as e.g. ``post_dynamics_0.3`` per spec.
    return f"post_dynamics_{epsilon:g}"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def build_signal_files(
    persona_sentiments_path: Path | str = PERSONA_SENTIMENTS_PATH,
    write: bool = True,
) -> dict[str, pd.DataFrame]:
    """Build both signal files from a persona-sentiments parquet.

    Parameters
    ----------
    persona_sentiments_path:
        Source parquet (output of B5/B4 with raw + post-dynamics columns).
    write:
        If True, persist all three output parquets under ``DATA_DIR``.

    Returns
    -------
    dict[str, pd.DataFrame]
        ``{"persona_only": df1, "persona_graph": df2, "persona_graph_sweep": df3}``
    """
    src_path = Path(persona_sentiments_path)
    if not src_path.exists():
        raise FileNotFoundError(
            f"persona_sentiments parquet not found at {src_path}. "
            "Run workstream B5 + B4 first."
        )

    df = pd.read_parquet(src_path, engine="pyarrow")
    logger.info(
        "Loaded persona_sentiments.parquet: %d rows, %d unique events, %d unique personas",
        len(df),
        df["event_id"].nunique() if "event_id" in df.columns else 0,
        df["persona_id"].nunique() if "persona_id" in df.columns else 0,
    )

    persona_only = aggregate_persona_only(df)
    persona_graph = aggregate_persona_graph(df, DEFFUANT_EPSILON_PRIMARY)
    persona_graph_sweep = aggregate_persona_graph_sweep(df)

    if write:
        persona_only.to_parquet(SIGNALS_PERSONA_ONLY_PATH, index=False, engine="pyarrow")
        persona_graph.to_parquet(SIGNALS_PERSONA_GRAPH_PATH, index=False, engine="pyarrow")
        persona_graph_sweep.to_parquet(
            SIGNALS_PERSONA_GRAPH_SWEEP_PATH, index=False, engine="pyarrow"
        )
        logger.info(
            "Wrote %s, %s, %s",
            SIGNALS_PERSONA_ONLY_PATH,
            SIGNALS_PERSONA_GRAPH_PATH,
            SIGNALS_PERSONA_GRAPH_SWEEP_PATH,
        )

    return {
        "persona_only": persona_only,
        "persona_graph": persona_graph,
        "persona_graph_sweep": persona_graph_sweep,
    }


__all__ = [
    "AggregateSignals",
    "SARLE_BIMODAL_THRESHOLD",
    "PERSONA_SENTIMENTS_PATH",
    "SIGNALS_PERSONA_ONLY_PATH",
    "SIGNALS_PERSONA_GRAPH_PATH",
    "SIGNALS_PERSONA_GRAPH_SWEEP_PATH",
    "population_variance",
    "sample_skewness",
    "sample_kurtosis",
    "sarle_bimodality",
    "aggregate_event",
    "aggregate_persona_only",
    "aggregate_persona_graph",
    "aggregate_persona_graph_sweep",
    "build_signal_files",
]
