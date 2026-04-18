"""Workstream C2 - Appendix A: Supplementary tercile-Sharpe with bootstrap CI.

Sharpe = (mean(AR_top_tercile) - mean(AR_bottom_tercile)) /
        std(AR_top_tercile - AR_bottom_tercile)

* Tercile boundaries determined by signal rank (top third / bottom third).
* Equal-weight within each tercile.
* Per-event AR (not cumulative); not annualised (single cross-section).
* Bootstrap 95% CI computed with 1000 resamples (paired stratified bootstrap).

Caveat (always reported in JSON output):
    n=13 per leg, Sharpe SE ~ 0.28 - included for completeness, not statistical
    inference.

See plan Appendix A.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_BOOTSTRAP_RESAMPLES: int = 1000
DEFAULT_BOOTSTRAP_CI: float = 0.95
DEFAULT_RNG_SEED: int = 20260418

CAVEAT_TEXT: str = (
    "n approx 13 per tercile leg; Sharpe SE approx 0.28. "
    "Included for completeness, not statistical inference."
)


@dataclass(frozen=True)
class SharpeResult:
    """Output of :func:`tercile_sharpe`."""

    sharpe: float
    sharpe_bootstrap_ci_95: tuple[float, float]
    n_top: int
    n_bottom: int
    bootstrap_resamples: int
    caveat: str = CAVEAT_TEXT

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert tuple to list for JSON friendliness.
        d["sharpe_bootstrap_ci_95"] = list(d["sharpe_bootstrap_ci_95"])
        return d


def _tercile_split(
    signal: np.ndarray, ar: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return (ar_top, ar_bottom) by signal-rank tercile.

    Ties resolved by stable sort. With n events, top tercile = top
    ``n // 3`` ranks, bottom tercile = bottom ``n // 3`` ranks.
    """
    n = signal.size
    if n < 3:
        raise ValueError(f"tercile_sharpe: need at least 3 events, got {n}")
    third = max(1, n // 3)
    order = np.argsort(signal, kind="stable")
    bottom_idx = order[:third]
    top_idx = order[-third:]
    return ar[top_idx], ar[bottom_idx]


def _sharpe_from_legs(ar_top: np.ndarray, ar_bottom: np.ndarray) -> float:
    """Compute the spread-Sharpe from top/bottom AR arrays.

    Pairs are aligned in rank order so the spread series has length
    ``min(len(top), len(bottom))``. Returns NaN when std of spread is 0
    or sample size < 2.
    """
    m = min(ar_top.size, ar_bottom.size)
    if m < 2:
        return float("nan")
    # Both legs are sorted ascending by signal rank within tercile; align
    # paired by position within tercile (deterministic).
    spread = ar_top[:m] - ar_bottom[:m]
    sigma = float(np.std(spread, ddof=1))
    if sigma == 0.0 or not np.isfinite(sigma):
        return float("nan")
    return float(np.mean(spread) / sigma)


def tercile_sharpe(
    signal: np.ndarray | pd.Series,
    ar: np.ndarray | pd.Series,
    bootstrap_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    ci: float = DEFAULT_BOOTSTRAP_CI,
    rng_seed: int = DEFAULT_RNG_SEED,
) -> SharpeResult:
    """Tercile spread Sharpe with stratified bootstrap CI.

    Parameters
    ----------
    signal:
        Per-event signal values used to rank events into terciles.
    ar:
        Per-event abnormal returns aligned with *signal*.
    bootstrap_resamples:
        Number of bootstrap samples (default 1000, per Appendix A).
    ci:
        Confidence-interval coverage (default 0.95).
    rng_seed:
        Reproducible RNG seed.

    Returns
    -------
    SharpeResult
    """
    s = np.asarray(signal, dtype=float).ravel()
    a = np.asarray(ar, dtype=float).ravel()
    if s.shape != a.shape:
        raise ValueError(
            f"signal/ar shape mismatch: {s.shape} vs {a.shape}"
        )

    mask = ~(np.isnan(s) | np.isnan(a))
    s = s[mask]
    a = a[mask]

    ar_top, ar_bottom = _tercile_split(s, a)
    point_sharpe = _sharpe_from_legs(ar_top, ar_bottom)

    # Bootstrap stratified within tercile assignments to preserve
    # tercile size and group composition.
    rng = np.random.default_rng(rng_seed)
    boot_sharpes: list[float] = []
    n_top = ar_top.size
    n_bottom = ar_bottom.size
    for _ in range(int(bootstrap_resamples)):
        top_resample = rng.choice(ar_top, size=n_top, replace=True)
        bot_resample = rng.choice(ar_bottom, size=n_bottom, replace=True)
        sh = _sharpe_from_legs(top_resample, bot_resample)
        if np.isfinite(sh):
            boot_sharpes.append(sh)

    if not boot_sharpes:
        ci_low, ci_high = float("nan"), float("nan")
    else:
        alpha = (1.0 - ci) / 2.0
        boot_arr = np.asarray(boot_sharpes, dtype=float)
        ci_low = float(np.quantile(boot_arr, alpha))
        ci_high = float(np.quantile(boot_arr, 1.0 - alpha))

    result = SharpeResult(
        sharpe=point_sharpe,
        sharpe_bootstrap_ci_95=(ci_low, ci_high),
        n_top=int(n_top),
        n_bottom=int(n_bottom),
        bootstrap_resamples=int(bootstrap_resamples),
    )
    logger.info(
        "tercile_sharpe: sharpe=%.4f, 95%% CI=[%.4f, %.4f], n_top=%d, "
        "n_bottom=%d, n_boot_finite=%d",
        result.sharpe,
        ci_low,
        ci_high,
        n_top,
        n_bottom,
        len(boot_sharpes),
    )
    return result


__all__ = [
    "CAVEAT_TEXT",
    "DEFAULT_BOOTSTRAP_RESAMPLES",
    "SharpeResult",
    "tercile_sharpe",
]
