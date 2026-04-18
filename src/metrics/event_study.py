"""Workstream C2: Panel-regression helper for event-study t-stats.

Fits ``AR = alpha + beta * signal + firm_FE + epsilon`` via ``statsmodels``
OLS with cluster-robust standard errors (clustered by ticker). The HC0
cluster-robust variance estimator with the small-cluster degrees-of-freedom
correction (``use_correction=True``) is the default.

Why clustered, why by ticker:

  * Multiple events per firm share firm-level shocks (residual autocorrelation
    within firm), so naive OLS SEs are too small.
  * Clustering at the ticker level allows arbitrary within-firm dependence
    while assuming independence across firms - the cleanest assumption given
    n events <= 40 and ~10-15 unique tickers.

Results returned as a frozen :class:`PanelResult` dataclass for easy
serialisation into ``ablation_results.json``.

See plan Section 4 (C2), Section 8 (R9) and Appendix A.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PanelResult:
    """Output of :func:`panel_regression`."""

    beta: float
    se_clustered: float
    tstat: float
    pvalue: float
    r_squared: float
    n_obs: int
    n_clusters: int
    df_resid: float
    used_correction: bool
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_inputs(df: pd.DataFrame, signal_col: str, ar_col: str, cluster_col: str) -> pd.DataFrame:
    """Drop rows with NaN signal/AR and ensure required columns exist."""
    required = {signal_col, ar_col, cluster_col}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"panel_regression: missing required columns {missing}; "
            f"have: {sorted(df.columns)}"
        )
    clean = df.dropna(subset=[signal_col, ar_col, cluster_col]).copy()
    if len(clean) < len(df):
        logger.info(
            "panel_regression: dropped %d rows with NaN in {signal, AR, cluster}",
            len(df) - len(clean),
        )
    return clean


def _build_design_matrix(
    df: pd.DataFrame, signal_col: str, cluster_col: str, include_fe: bool
) -> tuple[pd.DataFrame, np.ndarray]:
    """Construct (X, y) for OLS.

    ``X`` columns: const, ``signal``, plus one-hot dummies for each ticker
    except a baseline (drop_first to avoid dummy-trap). When ``include_fe``
    is False (e.g. only one cluster present), no firm dummies are added.
    """
    x_parts: list[pd.DataFrame] = [
        pd.DataFrame({"const": np.ones(len(df))}, index=df.index),
        pd.DataFrame({"signal": df[signal_col].astype(float).to_numpy()}, index=df.index),
    ]
    if include_fe and df[cluster_col].nunique() > 1:
        dummies = pd.get_dummies(df[cluster_col], prefix="fe", drop_first=True)
        # Cast bool dummies to float for numerical stability.
        dummies = dummies.astype(float)
        x_parts.append(dummies)

    X = pd.concat(x_parts, axis=1)
    return X, df[signal_col].index.to_numpy()  # placeholder y returned by caller


def panel_regression(
    df: pd.DataFrame,
    signal_col: str = "signal",
    ar_col: str = "ar_1d",
    cluster_col: str = "ticker",
    include_firm_fe: bool = True,
    use_correction: bool = True,
) -> PanelResult:
    """Fit AR ~ signal + firm_FE with cluster-robust SEs (clustered by ticker).

    Parameters
    ----------
    df:
        Panel DataFrame with one row per (event, ticker) observation.
    signal_col, ar_col, cluster_col:
        Column names for the predictor, response, and clustering variable.
    include_firm_fe:
        If True (default), one-hot ticker dummies (drop_first=True) are added.
        With a single ticker present, FE are skipped automatically.
    use_correction:
        If True (default), statsmodels applies the small-cluster
        degrees-of-freedom correction
        ``(G / (G - 1)) * ((N - 1) / (N - K))`` to the cluster-robust covariance.

    Returns
    -------
    PanelResult
        beta, clustered SE, t-stat, p-value, R^2, n_obs, n_clusters,
        df_resid, used_correction flag.
    """
    clean = _validate_inputs(df, signal_col, ar_col, cluster_col)
    if len(clean) < 3:
        raise ValueError(
            f"panel_regression: need at least 3 valid rows, got {len(clean)}."
        )

    n_clusters = int(clean[cluster_col].nunique())
    if n_clusters < 2:
        logger.warning(
            "panel_regression: only %d unique cluster(s); cluster-robust SE "
            "will degenerate. Reporting heteroskedasticity-robust HC0 instead.",
            n_clusters,
        )

    X, _ = _build_design_matrix(clean, signal_col, cluster_col, include_firm_fe)
    y = clean[ar_col].astype(float).to_numpy()
    groups = clean[cluster_col].to_numpy()

    # Fit OLS with cluster-robust covariance.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.OLS(y, X.astype(float).to_numpy(), hasconst=True)
        if n_clusters >= 2:
            res = model.fit(
                cov_type="cluster",
                cov_kwds={"groups": groups, "use_correction": use_correction},
            )
        else:
            res = model.fit(cov_type="HC0")

    # Locate the signal coefficient (column index 1 by construction).
    sig_col_idx = list(X.columns).index("signal")
    beta = float(res.params[sig_col_idx])
    se = float(res.bse[sig_col_idx])
    tstat = float(res.tvalues[sig_col_idx])
    pval = float(res.pvalues[sig_col_idx])

    notes = ""
    if n_clusters < 2:
        notes = "cluster-robust requires >=2 clusters; reported HC0 instead"

    result = PanelResult(
        beta=beta,
        se_clustered=se,
        tstat=tstat,
        pvalue=pval,
        r_squared=float(res.rsquared),
        n_obs=int(res.nobs),
        n_clusters=n_clusters,
        df_resid=float(res.df_resid),
        used_correction=bool(use_correction and n_clusters >= 2),
        notes=notes,
    )
    logger.info(
        "panel_regression %s: beta=%.4f, se=%.4f, t=%.3f, p=%.4f, "
        "n_obs=%d, n_clusters=%d, R^2=%.3f",
        signal_col,
        beta,
        se,
        tstat,
        pval,
        result.n_obs,
        result.n_clusters,
        result.r_squared,
    )
    return result


def naive_ols_for_comparison(
    df: pd.DataFrame,
    signal_col: str = "signal",
    ar_col: str = "ar_1d",
    cluster_col: str = "ticker",
    include_firm_fe: bool = True,
) -> PanelResult:
    """Same model fit with non-robust SEs - used by the SE-comparison test."""
    clean = _validate_inputs(df, signal_col, ar_col, cluster_col)
    X, _ = _build_design_matrix(clean, signal_col, cluster_col, include_firm_fe)
    y = clean[ar_col].astype(float).to_numpy()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sm.OLS(y, X.astype(float).to_numpy(), hasconst=True).fit(cov_type="nonrobust")

    sig_col_idx = list(X.columns).index("signal")
    beta = float(res.params[sig_col_idx])
    se = float(res.bse[sig_col_idx])
    tstat = float(res.tvalues[sig_col_idx])
    pval = float(res.pvalues[sig_col_idx])
    return PanelResult(
        beta=beta,
        se_clustered=se,
        tstat=tstat,
        pvalue=pval,
        r_squared=float(res.rsquared),
        n_obs=int(res.nobs),
        n_clusters=int(clean[cluster_col].nunique()),
        df_resid=float(res.df_resid),
        used_correction=False,
        notes="cov_type=nonrobust (for comparison)",
    )


__all__ = [
    "PanelResult",
    "panel_regression",
    "naive_ols_for_comparison",
]
