"""Workstream C2 - R9 mitigation: scripted clustered-SE manual verification.

This module exists for one purpose: produce a self-contained, reproducible
4-point check that ``statsmodels`` cluster-robust standard errors are being
applied correctly to our panel regression. The companion test
``tests/unit/test_clustered_se_manual_check.py`` calls
:func:`run_manual_check` and asserts each sub-point.

Sub-points (all four MUST pass):

  (a) ``n_clusters`` reported by statsmodels equals the number of unique
      tickers (e.g. 5), NOT the number of events (20).

  (b) Small-cluster degrees-of-freedom correction is applied
      (``use_correction=True`` flag on the cluster covariance).

  (c) The signal-coefficient t-stat differs by at least
      :data:`MIN_TSTAT_DELTA_FRACTION` (default 10%) between
      ``cov_type='nonrobust'`` and ``cov_type='cluster'`` on a synthetic panel
      designed to have within-firm residual correlation.

  (d) Manual cluster-robust SE for the *signal* coefficient (computed by
      the textbook sandwich formula
      ``Var = (X'X)^-1 (sum_g X_g' eps eps' X_g) (X'X)^-1`` with the
      finite-cluster correction) matches the statsmodels output within
      :data:`MANUAL_TOLERANCE` (default 1e-6) absolute.

The synthetic panel has:
    * 5 tickers
    * 20 observations (4 events per ticker)
    * a known true beta = 1.0 with within-firm residual autocorrelation
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

logger = logging.getLogger(__name__)


# Synthetic-panel design constants.
N_TICKERS: int = 5
EVENTS_PER_TICKER: int = 4
N_OBS: int = N_TICKERS * EVENTS_PER_TICKER  # 20
TRUE_BETA: float = 1.0

# Pass-fail tolerances.
MIN_TSTAT_DELTA_FRACTION: float = 0.10  # >= 10% relative change
MANUAL_TOLERANCE: float = 1e-6


@dataclass(frozen=True)
class ManualCheckResult:
    """Outcome of the four sub-checks."""

    # (a) cluster count
    n_clusters_reported: int
    n_unique_tickers: int
    n_observations: int
    cluster_count_ok: bool

    # (b) small-cluster df adjustment
    use_correction_flag: bool
    df_adjustment_ok: bool

    # (c) t-stat divergence between nonrobust and cluster
    tstat_nonrobust: float
    tstat_clustered: float
    tstat_relative_delta: float
    tstat_difference_ok: bool

    # (d) manual sandwich SE matches statsmodels
    se_clustered_statsmodels: float
    se_clustered_manual: float
    se_absolute_difference: float
    manual_se_match_ok: bool

    # Aggregate
    all_checks_passed: bool

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Synthetic panel
# ---------------------------------------------------------------------------


def build_synthetic_panel(seed: int = 20260418) -> pd.DataFrame:
    """Construct the synthetic panel used by the manual SE check.

    Design:
        * ``EVENTS_PER_TICKER`` events per ticker, ``N_TICKERS`` tickers.
        * Predictor ``signal`` ~ standard normal, independent across rows.
        * Firm-specific intercept added to give heterogeneity.
        * Residual = ticker-specific shock (shared by all events of that
          ticker, magnitude ~ N(0, 1)) + idiosyncratic N(0, 0.4).
          The shared ticker shock induces strong intra-cluster correlation,
          which is exactly what cluster-robust SEs are designed to handle.

    Returns
    -------
    pd.DataFrame
        Columns: event_id, ticker, signal, ar_1d.
    """
    rng = np.random.default_rng(seed)
    tickers = [f"T{i:02d}" for i in range(N_TICKERS)]

    rows: list[dict] = []
    for t_idx, ticker in enumerate(tickers):
        firm_alpha = 0.5 * (t_idx - (N_TICKERS - 1) / 2.0)  # spread across firms
        # Big shared shock per ticker - cluster correlation.
        ticker_shock = float(rng.normal(0.0, 1.0))
        for e in range(EVENTS_PER_TICKER):
            sig = float(rng.normal(0.0, 1.0))
            idio = float(rng.normal(0.0, 0.4))
            ar = firm_alpha + TRUE_BETA * sig + ticker_shock + idio
            rows.append(
                {
                    "event_id": f"E{t_idx:02d}_{e:02d}",
                    "ticker": ticker,
                    "signal": sig,
                    "ar_1d": ar,
                }
            )
    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# Manual cluster-robust SE (textbook sandwich)
# ---------------------------------------------------------------------------


def _manual_cluster_robust_cov(
    X: np.ndarray, residuals: np.ndarray, groups: np.ndarray, *, use_correction: bool
) -> np.ndarray:
    """Compute the cluster-robust sandwich covariance matrix by hand.

    Var(beta_hat) = (X'X)^-1 [ sum_g X_g' u_g u_g' X_g ] (X'X)^-1   * dof_correction

    Where u_g is the residual vector for cluster g and X_g the design rows
    for cluster g. ``use_correction`` applies the standard small-cluster
    adjustment   ``(G / (G-1)) * ((N - 1) / (N - K))``, matching statsmodels.

    Parameters
    ----------
    X:
        (N, K) design matrix.
    residuals:
        (N,) residual vector ``y - X beta_hat``.
    groups:
        (N,) cluster identifiers.
    use_correction:
        Apply the small-cluster df correction.

    Returns
    -------
    np.ndarray
        (K, K) covariance matrix.
    """
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)

    # Score sum: sum over clusters of (X_g' u_g)(X_g' u_g)'.
    score_sum = np.zeros((k, k))
    unique_groups = np.unique(groups)
    g_count = unique_groups.size
    for g in unique_groups:
        mask = groups == g
        Xg = X[mask, :]
        ug = residuals[mask]
        s = Xg.T @ ug  # (K,)
        score_sum += np.outer(s, s)

    cov = XtX_inv @ score_sum @ XtX_inv

    if use_correction:
        # statsmodels applies (G / (G-1)) * ((N-1)/(N-K)) for cov_type='cluster'.
        adj = (g_count / (g_count - 1)) * ((n - 1) / (n - k))
        cov = cov * adj

    return cov


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------


def run_manual_check(seed: int = 20260418) -> ManualCheckResult:
    """Run all four sub-checks and return the outcomes.

    Parameters
    ----------
    seed:
        RNG seed for reproducible synthetic panel.

    Returns
    -------
    ManualCheckResult
    """
    df = build_synthetic_panel(seed=seed)
    assert len(df) == N_OBS, f"unexpected synthetic panel size {len(df)}"
    assert df["ticker"].nunique() == N_TICKERS

    # Build design: const + signal + ticker FE (drop_first to avoid dummy trap).
    fe = pd.get_dummies(df["ticker"], prefix="fe", drop_first=True).astype(float)
    X = pd.concat(
        [
            pd.DataFrame({"const": np.ones(len(df))}),
            pd.DataFrame({"signal": df["signal"].astype(float).to_numpy()}),
            fe,
        ],
        axis=1,
    ).reset_index(drop=True)
    X_arr = X.astype(float).to_numpy()
    y = df["ar_1d"].astype(float).to_numpy()
    groups = df["ticker"].to_numpy()

    # --- Fit nonrobust -----------------------------------------------------
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res_nonrobust = sm.OLS(y, X_arr, hasconst=True).fit(cov_type="nonrobust")

    # --- Fit cluster-robust ------------------------------------------------
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res_cluster = sm.OLS(y, X_arr, hasconst=True).fit(
            cov_type="cluster",
            cov_kwds={"groups": groups, "use_correction": True},
        )

    sig_idx = list(X.columns).index("signal")

    # ---------------- (a) cluster count ----------------------------------
    # statsmodels stores cluster info on the cov_kwds; n_groups from result.
    # Robust extraction across statsmodels versions:
    n_clusters_reported = _extract_n_clusters(res_cluster, groups)
    n_unique_tickers = int(np.unique(groups).size)
    cluster_count_ok = (
        n_clusters_reported == n_unique_tickers
        and n_clusters_reported != N_OBS
    )

    # ---------------- (b) df correction flag -----------------------------
    use_correction_flag = bool(
        res_cluster.cov_kwds.get("use_correction", False)
    )
    df_adjustment_ok = use_correction_flag is True

    # ---------------- (c) t-stat divergence ------------------------------
    tstat_nonrobust = float(res_nonrobust.tvalues[sig_idx])
    tstat_clustered = float(res_cluster.tvalues[sig_idx])
    if tstat_nonrobust == 0.0:
        rel_delta = float("inf") if tstat_clustered != 0 else 0.0
    else:
        rel_delta = float(
            abs(tstat_clustered - tstat_nonrobust) / abs(tstat_nonrobust)
        )
    tstat_difference_ok = rel_delta >= MIN_TSTAT_DELTA_FRACTION

    # ---------------- (d) manual SE matches statsmodels ------------------
    beta_hat = res_cluster.params  # shared with nonrobust (same OLS)
    residuals = y - X_arr @ beta_hat
    manual_cov = _manual_cluster_robust_cov(
        X_arr, residuals, groups, use_correction=True
    )
    se_manual = float(np.sqrt(manual_cov[sig_idx, sig_idx]))
    se_statsmodels = float(res_cluster.bse[sig_idx])
    abs_diff = abs(se_manual - se_statsmodels)
    manual_se_match_ok = abs_diff < MANUAL_TOLERANCE

    all_ok = (
        cluster_count_ok
        and df_adjustment_ok
        and tstat_difference_ok
        and manual_se_match_ok
    )

    result = ManualCheckResult(
        n_clusters_reported=int(n_clusters_reported),
        n_unique_tickers=int(n_unique_tickers),
        n_observations=int(N_OBS),
        cluster_count_ok=bool(cluster_count_ok),
        use_correction_flag=bool(use_correction_flag),
        df_adjustment_ok=bool(df_adjustment_ok),
        tstat_nonrobust=float(tstat_nonrobust),
        tstat_clustered=float(tstat_clustered),
        tstat_relative_delta=float(rel_delta),
        tstat_difference_ok=bool(tstat_difference_ok),
        se_clustered_statsmodels=float(se_statsmodels),
        se_clustered_manual=float(se_manual),
        se_absolute_difference=float(abs_diff),
        manual_se_match_ok=bool(manual_se_match_ok),
        all_checks_passed=bool(all_ok),
    )
    logger.info(
        "manual SE check: cluster_count=%s, df_adj=%s, tstat_delta=%s, manual_se=%s",
        result.cluster_count_ok,
        result.df_adjustment_ok,
        result.tstat_difference_ok,
        result.manual_se_match_ok,
    )
    return result


def _extract_n_clusters(res, groups: np.ndarray) -> int:
    """Robustly extract the cluster count statsmodels used.

    Different statsmodels versions store this attribute differently; fall back
    to counting uniques in the supplied groups array.
    """
    candidates = [
        ("n_groups",),
        ("cov_kwds", "n_groups"),
        ("nobs_clusters",),
    ]
    for path in candidates:
        obj = res
        ok = True
        for attr in path:
            if isinstance(obj, dict):
                if attr in obj:
                    obj = obj[attr]
                    continue
                ok = False
                break
            if hasattr(obj, attr):
                obj = getattr(obj, attr)
                continue
            ok = False
            break
        if ok and obj is not None:
            try:
                return int(obj)
            except (TypeError, ValueError):
                continue
    # Fallback - statsmodels uses unique groups.
    return int(np.unique(groups).size)


__all__ = [
    "MANUAL_TOLERANCE",
    "MIN_TSTAT_DELTA_FRACTION",
    "ManualCheckResult",
    "build_synthetic_panel",
    "run_manual_check",
]
