"""Deffuant bounded-confidence dynamics on cached persona sentiment scores.

CRITICAL: NO LLM calls. Pure NumPy on float arrays.
"""

from src.dynamics.deffuant import deffuant_round, deffuant_run
from src.dynamics.runner import run_dynamics_sweep, sweep_diagnostics

__all__ = [
    "deffuant_round",
    "deffuant_run",
    "run_dynamics_sweep",
    "sweep_diagnostics",
]
