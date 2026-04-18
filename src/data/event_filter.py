"""Workstream A1b: Stage-1 material event filter.

Applies GDELT-side heuristics to remove non-material events before AR
computation. Stage-2 filtering (AR-based, null-session drop) happens in A2.

Filter criteria (plan Section 4, A1b):
  1. abs(gdelt_tone) > GDELT_TONE_MAGNITUDE_MIN  (non-neutral framing)
  2. entity_confidence > GDELT_ENTITY_CONFIDENCE_MIN
  3. at least one theme tag present

See plan Section 9 (events_stage1.parquet schema) and Section 8 (R10).
"""

import logging

import pandas as pd

from src.config import GDELT_ENTITY_CONFIDENCE_MIN, GDELT_TONE_MAGNITUDE_MIN

logger = logging.getLogger(__name__)


def apply_stage1_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the three stage-1 material-event criteria to *df*.

    Parameters
    ----------
    df:
        Raw events DataFrame. Must contain columns: gdelt_tone,
        entity_confidence, gdelt_theme_tags. The is_sentinel column
        (if absent) is added as False.

    Returns
    -------
    pd.DataFrame
        Filtered copy with rows failing any criterion removed. Index reset.
    """
    if df.empty:
        logger.warning("apply_stage1_filter: input DataFrame is empty.")
        return df.copy()

    n_before = len(df)

    # Ensure is_sentinel column exists.
    if "is_sentinel" not in df.columns:
        df = df.copy()
        df["is_sentinel"] = False

    # Ensure entity_confidence column has a default if missing.
    if "entity_confidence" not in df.columns:
        df = df.copy()
        df["entity_confidence"] = 1.0

    # Criterion 1: tone magnitude.
    mask_tone = df["gdelt_tone"].abs() > GDELT_TONE_MAGNITUDE_MIN

    # Criterion 2: entity confidence.
    mask_conf = df["entity_confidence"] > GDELT_ENTITY_CONFIDENCE_MIN

    # Criterion 3: at least one theme tag.
    def _has_theme(tags) -> bool:
        if isinstance(tags, list):
            return len(tags) > 0
        if isinstance(tags, str):
            return bool(tags.strip())
        return False

    mask_theme = df["gdelt_theme_tags"].apply(_has_theme)

    combined_mask = mask_tone & mask_conf & mask_theme
    filtered = df[combined_mask].copy().reset_index(drop=True)

    n_after = len(filtered)
    logger.info(
        "Stage-1 filter: %d -> %d events "
        "(tone_fail=%d, conf_fail=%d, theme_fail=%d)",
        n_before,
        n_after,
        int((~mask_tone).sum()),
        int((~mask_conf).sum()),
        int((~mask_theme).sum()),
    )
    return filtered


def stage1_stats(df: pd.DataFrame) -> dict:
    """Return a summary dict of key filter statistics for logging/reporting."""
    if df.empty:
        return {"event_count": 0, "sentinel_count": 0, "tickers": []}

    return {
        "event_count": len(df),
        "sentinel_count": int(df["is_sentinel"].sum()) if "is_sentinel" in df.columns else 0,
        "tickers": sorted(df["ticker"].unique().tolist()) if "ticker" in df.columns else [],
        "tone_mean": round(float(df["gdelt_tone"].mean()), 4) if "gdelt_tone" in df.columns else None,
        "tone_abs_mean": round(float(df["gdelt_tone"].abs().mean()), 4) if "gdelt_tone" in df.columns else None,
    }
