"""Workstream A1c: Sentinel event selection.

Among events tagged ESG / political / policy by GDELT theme tags, select the
top-3 by absolute GDELT tone score (most opinionated source framing) and mark
is_sentinel = True. This is reproducible and avoids manual curation bias.

See plan Section 4 (A1c), Section 8 (MF8), and Section 9 (is_sentinel field).
"""

import logging

import pandas as pd

from src.config import SENTINEL_EVENT_COUNT

logger = logging.getLogger(__name__)

# GDELT theme tag substrings that qualify an event as ESG / political / policy.
# These are checked case-insensitively against each tag in gdelt_theme_tags.
_SENTINEL_THEME_KEYWORDS: list[str] = [
    # ESG / environmental.
    "env",
    "climate",
    "esg",
    "carbon",
    "emission",
    "renewable",
    "sustain",
    "pollution",
    # Political / government.
    "gov",
    "polit",
    "elect",
    "congress",
    "senate",
    "legislat",
    "democrat",
    "republican",
    "white_house",
    "executive",
    # Policy / regulation.
    "polic",
    "regulat",
    "sanction",
    "tariff",
    "tax",
    "subsid",
    "antitrust",
    "sec_",
    "federal",
]


def _is_sentinel_eligible(theme_tags: list | str | None) -> bool:
    """Return True if any theme tag matches ESG / political / policy keywords."""
    if isinstance(theme_tags, str):
        theme_tags = [theme_tags]
    if not isinstance(theme_tags, list):
        return False
    combined = " ".join(str(t).lower() for t in theme_tags)
    return any(kw in combined for kw in _SENTINEL_THEME_KEYWORDS)


def select_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    """Mark the top-N events by |gdelt_tone| among ESG/political/policy-tagged
    events as sentinels.

    Algorithm (plan A1c / MF8):
      1. Filter to rows where gdelt_theme_tags contains an ESG/political/policy
         keyword.
      2. Sort descending by abs(gdelt_tone).
      3. Mark the top SENTINEL_EVENT_COUNT rows as is_sentinel = True.
      4. If fewer than SENTINEL_EVENT_COUNT themed events exist, fall back to
         top-N by |tone| across ALL events and log a warning.

    Parameters
    ----------
    df:
        Stage-1 filtered events DataFrame. Modified in-place copy returned.

    Returns
    -------
    pd.DataFrame
        Copy of df with is_sentinel column updated.
    """
    if df.empty:
        logger.warning("select_sentinels: input DataFrame is empty.")
        return df.copy()

    result = df.copy()
    result["is_sentinel"] = False
    result["_abs_tone"] = result["gdelt_tone"].abs()

    eligible_mask = result["gdelt_theme_tags"].apply(_is_sentinel_eligible)
    eligible_df = result[eligible_mask]

    if len(eligible_df) >= SENTINEL_EVENT_COUNT:
        top_idx = (
            eligible_df.nlargest(SENTINEL_EVENT_COUNT, "_abs_tone").index
        )
        logger.info(
            "Selected %d sentinels from %d ESG/political/policy-tagged events.",
            SENTINEL_EVENT_COUNT,
            len(eligible_df),
        )
    else:
        logger.warning(
            "Only %d ESG/political/policy-tagged events found (need %d); "
            "falling back to top-%d by |tone| across all events.",
            len(eligible_df),
            SENTINEL_EVENT_COUNT,
            SENTINEL_EVENT_COUNT,
        )
        top_idx = result.nlargest(SENTINEL_EVENT_COUNT, "_abs_tone").index

    result.loc[top_idx, "is_sentinel"] = True
    result = result.drop(columns=["_abs_tone"])

    sentinel_tones = result.loc[top_idx, "gdelt_tone"].tolist()
    logger.info("Sentinel |tone| values: %s", [abs(t) for t in sentinel_tones])

    return result
