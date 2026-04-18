"""Run Deffuant epsilon-sweep across all events.

Input: a long DataFrame indexed by (event_id, persona_id) with raw_sentiment
floats, plus the social_graph dict.
Output: same DataFrame with three new columns
    post_dynamics_0.2, post_dynamics_0.3, post_dynamics_0.4
plus a diagnostics dict (per-epsilon convergence + per-event variance shift).

CRITICAL: NO LLM calls anywhere in this module. Pure math on cached arrays.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from src.config import (
    DATA_DIR,
    DEFFUANT_EPSILON_SWEEP,
    DEFFUANT_MU,
    DEFFUANT_ROUNDS,
)
from src.dynamics.deffuant import deffuant_run

logger = logging.getLogger(__name__)


def _epsilon_column(epsilon: float) -> str:
    # f"{0.2:g}" -> "0.2", "0.3", "0.4" — matches plan section 9 schema.
    return f"post_dynamics_{epsilon:g}"


def run_dynamics_sweep(
    persona_sentiments: pd.DataFrame,
    graph: Mapping,
    *,
    n_personas: Optional[int] = None,
    epsilons: Sequence[float] = DEFFUANT_EPSILON_SWEEP,
    mu: float = DEFFUANT_MU,
    rounds: int = DEFFUANT_ROUNDS,
    seed: int = 7,
) -> tuple[pd.DataFrame, Dict]:
    """Apply Deffuant per event for each epsilon. Return (df, diagnostics).

    Per-event isolation: each event's persona vector is treated independently
    (Deffuant operates within an event's sentiment snapshot).

    NaN sentiment is preserved across rounds (NaN in -> NaN out).
    """
    if n_personas is None:
        if persona_sentiments.empty:
            n_personas = 0
        else:
            n_personas = int(persona_sentiments["persona_id"].max() + 1)
    df = persona_sentiments.copy()
    for eps in epsilons:
        df[_epsilon_column(eps)] = np.nan

    diagnostics: Dict[str, Dict] = {
        f"epsilon_{eps:g}": {
            "per_event_shift": {},
            "per_event_var_pre": {},
            "per_event_var_post": {},
            "max_round_shift": 0.0,
        }
        for eps in epsilons
    }

    for event_id, sub in df.groupby("event_id", sort=False):
        baseline = np.full(n_personas, np.nan)
        for _, row in sub.iterrows():
            baseline[int(row["persona_id"])] = float(row["raw_sentiment"])
        # NaN-safe seed: clamp NaN to 0.0 for the dynamics, but mask back at
        # the end so we don't fabricate signal for failed parses.
        nan_mask = np.isnan(baseline)
        seed_arr = np.where(nan_mask, 0.0, baseline)
        for eps in epsilons:
            final, shifts = deffuant_run(
                seed_arr,
                graph,
                eps,
                mu=mu,
                rounds=rounds,
                seed=seed,
            )
            final = np.where(nan_mask, np.nan, final)
            col = _epsilon_column(eps)
            for pid, val in enumerate(final):
                if nan_mask[pid]:
                    continue
                mask = (df["event_id"] == event_id) & (df["persona_id"] == pid)
                df.loc[mask, col] = float(val)
            ed = diagnostics[f"epsilon_{eps:g}"]
            ed["per_event_shift"][str(event_id)] = shifts
            ed["per_event_var_pre"][str(event_id)] = float(
                np.nanvar(baseline, ddof=0)
            )
            ed["per_event_var_post"][str(event_id)] = float(
                np.nanvar(final, ddof=0)
            )
            if shifts:
                ed["max_round_shift"] = max(ed["max_round_shift"], max(shifts))
    return df, diagnostics


def sweep_diagnostics(
    diagnostics: Mapping,
    out_path: Optional[Path] = None,
) -> Path:
    out_path = out_path or (DATA_DIR / "dynamics_diagnostics.json")
    out_path.write_text(json.dumps(diagnostics, indent=2))
    return out_path


__all__ = ["run_dynamics_sweep", "sweep_diagnostics"]
