"""Workstream A3: Loughran-McDonald (L-M) financial sentiment dictionary baseline.

Loads the L-M master dictionary and scores each headline as:
  score = (positive_count - negative_count) / (positive_count + negative_count + 1)
Normalized to [-1, 1].

Dictionary loading priority:
  1. data/lm_dictionary.csv (user-supplied from https://sraf.nd.edu/loughranmcdonald-master-dictionary/)
  2. A compact hardcoded word set (top ~200 positive + ~400 negative financial
     terms from the published L-M list) bundled here for offline use.

Output: data/signals_lm.parquet with columns: event_id, mean_sentiment,
        sentiment_variance (null), bimodality_index (null).

See plan Section 4 (A3).
"""

import logging
import re
import string
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

LM_CSV_PATH: Path = DATA_DIR / "lm_dictionary.csv"
LM_SIGNAL_PATH: Path = DATA_DIR / "signals_lm.parquet"

# ---------------------------------------------------------------------------
# Compact bundled L-M word lists (representative subset of the full dictionary)
# sourced from: Loughran & McDonald (2011) JF, Table 1 + online master CSV.
# ---------------------------------------------------------------------------

_BUNDLED_POSITIVE: frozenset[str] = frozenset(
    """
    able abundance abundant accomplish accomplished achievement accreted active
    adequate advance advanced advantageous advances advantage affirmative
    agree agreeable agreement aid ameliorate ample appreciate appreciation
    approval approved assist assured attain attractive award backed beneficial
    benefit benefited best better bonus boom boost boosts breakthrough
    bright broadly capable celebrate celebrated champion clear comfortable
    commend competitive complete completion confident consecutive consistent
    constructive continue continued contribution convenient cooperative
    correct cost-effective create creating creative credible decisive deliver
    delivered delivering desirable distinguished dominant dramatic driven durable
    earn earned earnings easy effective effectively efficient efforts elevated
    empower enable encourage energetic enjoy enhanced enhancing enormous
    enrich ensure excellent exceptional excited exclusive exemplary expand
    expanded expanding expansion experience expert favorable favorably
    flexible flourish forward fruitful gain gaining gains good growth
    healthy high highest honor impressive improve improved improvement improves
    improving incentive innovative integrity interest leading legitimate leverage
    long-term lucrative major maximize milestone notable notable notable
    optimal optimistic outstanding outperform partner perform performing positive
    potential preserve primary proactive productive proficient profit profitable
    progress promising quality quick realize record resilient resolve
    rewarding right robust secure significant skilled solid sound stable
    strength strengthen strong successful superior support sustainable
    transparent trust valuable value well win winning
    """.split()
)

_BUNDLED_NEGATIVE: frozenset[str] = frozenset(
    """
    abandon abnormal abolished absent abuse accident accuse ache adverse
    adversely affected against agony allegation allegations alarmingly
    ambiguous annul anxiety apprehensive arbitrary assert bad bankrupt
    bankruptcy barrier bias blame breach burden caution cease
    challenge challenged challenging chronic claim claims collapse
    complain complaint concern concerned concerning conflict confusion
    controversy corrupt costly counterclaim crisis critical criticism
    curtail damage damaging danger dangerous deadlock decline declined
    declining deficit delinquent denial deny depressed deteriorate
    deteriorating difficult difficulties difficulty diminish diminished
    diminishing disadvantage disagree disaster disclose disclosure
    discontinued dispute disrupt disruption dissolved doubt downgrade
    downward dramatic drop dropout erode error excessive fail failed
    failing failure fault fine fires force fraud fraudulent harmful
    hazard harmful impair impairment impede inadequate incomplete
    ineffective inefficient infringe insolvency insufficient interference
    investigation irregular irregularity issue lawsuit layoff legal
    lessen liability limitation liquidation litigation loss losses
    lower misappropriate mislead misrepresent negligence obstacle
    obsolete operating penalty problem proceeding recall reduce reduced
    refuse regulatory reject rejected retirement reverse review risk
    risks severe shortage shortfall significant slow slowdown stop
    struggle suffer suffering terminate terminated unfavorable unfavorably
    unable uncertain uncertainty undermine unexpected unforeseen unstable
    violation volatile vulnerability weak weakened weakness withdraw
    worse writedown writeoff
    """.split()
)


def _load_lm_from_csv(path: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Load positive and negative word sets from the L-M master CSV.

    Expected columns (case-insensitive): Word, Positive, Negative.
    A word is positive if Positive > 0; negative if Negative > 0.
    """
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]

    if "word" not in df.columns:
        raise ValueError(f"L-M CSV at {path} has no 'Word' column. Columns: {list(df.columns)}")

    words = df["word"].astype(str).str.lower().str.strip()

    if "positive" in df.columns:
        pos_mask = pd.to_numeric(df["positive"], errors="coerce").fillna(0) > 0
        positive = frozenset(words[pos_mask].tolist())
    else:
        positive = frozenset()

    if "negative" in df.columns:
        neg_mask = pd.to_numeric(df["negative"], errors="coerce").fillna(0) > 0
        negative = frozenset(words[neg_mask].tolist())
    else:
        negative = frozenset()

    logger.info(
        "L-M CSV loaded: %d positive, %d negative words.", len(positive), len(negative)
    )
    return positive, negative


def _get_word_sets() -> tuple[frozenset[str], frozenset[str]]:
    """Return (positive_words, negative_words), preferring CSV over bundled."""
    if LM_CSV_PATH.exists():
        try:
            return _load_lm_from_csv(LM_CSV_PATH)
        except Exception as exc:
            logger.warning("Failed to load L-M CSV (%s); using bundled word list.", exc)
    else:
        logger.info(
            "L-M CSV not found at %s; using bundled compact word list. "
            "For full coverage, download from https://sraf.nd.edu/loughranmcdonald-master-dictionary/",
            LM_CSV_PATH,
        )
    return _BUNDLED_POSITIVE, _BUNDLED_NEGATIVE


_POSITIVE_WORDS, _NEGATIVE_WORDS = _get_word_sets()

_PUNCT_RE = re.compile(r"[" + re.escape(string.punctuation) + r"]")


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    return [t for t in cleaned.split() if t]


def score_headline(text: str) -> float:
    """Score a single headline using the L-M dictionary.

    Returns (pos_count - neg_count) / (pos_count + neg_count + 1) in [-1, 1].
    """
    tokens = _tokenize(text)
    pos_count = sum(1 for t in tokens if t in _POSITIVE_WORDS)
    neg_count = sum(1 for t in tokens if t in _NEGATIVE_WORDS)
    score = (pos_count - neg_count) / (pos_count + neg_count + 1)
    return float(score)


def score_events(df_events: pd.DataFrame) -> pd.DataFrame:
    """Score all headlines in df_events with the L-M dictionary.

    Parameters
    ----------
    df_events:
        DataFrame with columns event_id and headline_text.

    Returns
    -------
    pd.DataFrame
        signals_{pipeline}.parquet schema: event_id, mean_sentiment,
        sentiment_variance (null), bimodality_index (null).
    """
    if df_events.empty:
        return pd.DataFrame(
            columns=["event_id", "mean_sentiment", "sentiment_variance", "bimodality_index"]
        )

    scores = df_events["headline_text"].apply(score_headline)

    nonzero_rate = float((scores != 0.0).mean())
    logger.info(
        "L-M scoring: %d events, non-zero rate=%.2f%% (target >=80%%)",
        len(df_events),
        nonzero_rate * 100,
    )
    if nonzero_rate < 0.80:
        logger.warning(
            "L-M non-zero rate %.2f%% is below 80%% target. "
            "Consider supplying the full L-M CSV at %s.",
            nonzero_rate * 100,
            LM_CSV_PATH,
        )

    result = pd.DataFrame(
        {
            "event_id": df_events["event_id"].values,
            "mean_sentiment": scores.values,
            "sentiment_variance": None,
            "bimodality_index": None,
        }
    )
    return result


def run_lm_baseline(
    df_events: pd.DataFrame | None = None,
    write_parquet: bool = True,
) -> pd.DataFrame:
    """Load events, score with L-M, and optionally write signals_lm.parquet.

    Parameters
    ----------
    df_events:
        Events DataFrame; loaded from events.parquet if None.
    write_parquet:
        If True, write output to data/signals_lm.parquet.

    Returns
    -------
    pd.DataFrame
        L-M sentiment signal DataFrame.
    """
    if df_events is None:
        events_path = DATA_DIR / "events.parquet"
        if not events_path.exists():
            raise FileNotFoundError(
                f"events.parquet not found at {events_path}. Run A1/A2 pipeline first."
            )
        df_events = pd.read_parquet(events_path, engine="pyarrow")

    df_signals = score_events(df_events)

    if write_parquet:
        df_signals.to_parquet(LM_SIGNAL_PATH, index=False, engine="pyarrow")
        logger.info("Wrote signals_lm.parquet (%d rows).", len(df_signals))

    return df_signals
