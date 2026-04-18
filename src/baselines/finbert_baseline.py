"""Workstream A3: FinBERT sentiment baseline.

Loads ProsusAI/finbert via HuggingFace transformers and scores each headline
as P(positive) - P(negative) in [-1, 1].

Batched CPU inference; estimated < 30 min for ~40 events on a modern laptop.

Output: data/signals_finbert.parquet with columns: event_id, mean_sentiment,
        sentiment_variance (null), bimodality_index (null).

See plan Section 4 (A3) and Section 8 (R6: FinBERT OOM fallback).
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

FINBERT_MODEL_ID = "ProsusAI/finbert"
FINBERT_SIGNAL_PATH = DATA_DIR / "signals_finbert.parquet"

_BATCH_SIZE = 16
_MAX_LENGTH = 512


def _load_finbert() -> tuple[Any, Any]:
    """Load FinBERT tokenizer and model.

    Returns (tokenizer, model). Falls back to distilbert-base-uncased with
    a warning if ProsusAI/finbert is unavailable (R6 fallback).
    """
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch  # noqa: F401

        tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL_ID)
        model.eval()
        logger.info("FinBERT loaded: %s", FINBERT_MODEL_ID)
        return tokenizer, model
    except Exception as exc:
        logger.error(
            "Failed to load %s: %s. Check network / disk space.", FINBERT_MODEL_ID, exc
        )
        raise


def _score_batch(
    texts: list[str],
    tokenizer: Any,
    model: Any,
) -> list[float]:
    """Run FinBERT inference on a batch of texts.

    Returns list of (P_positive - P_negative) values in [-1, 1].

    FinBERT label order: positive=0, negative=1, neutral=2 (ProsusAI convention).
    """
    import torch
    import torch.nn.functional as F

    inputs = tokenizer(
        texts,
        return_tensors="pt",
        truncation=True,
        max_length=_MAX_LENGTH,
        padding=True,
    )

    with torch.no_grad():
        outputs = model(**inputs)
        probs = F.softmax(outputs.logits, dim=-1)  # shape: (batch, 3)

    # ProsusAI/finbert label mapping: 0=positive, 1=negative, 2=neutral
    p_pos = probs[:, 0].numpy()
    p_neg = probs[:, 1].numpy()
    scores = (p_pos - p_neg).tolist()
    return [float(s) for s in scores]


def score_headlines(
    texts: list[str],
    tokenizer: Any,
    model: Any,
) -> list[float]:
    """Score a list of headlines with FinBERT in batches.

    Parameters
    ----------
    texts:
        List of headline strings.
    tokenizer, model:
        Pre-loaded FinBERT components from _load_finbert().

    Returns
    -------
    list[float]
        Sentiment scores in [-1, 1] for each text.
    """
    scores: list[float] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        batch_scores = _score_batch(batch, tokenizer, model)
        scores.extend(batch_scores)
        logger.debug("FinBERT scored batch %d-%d.", i, i + len(batch))
    return scores


def score_events(
    df_events: pd.DataFrame,
    tokenizer: Any = None,
    model: Any = None,
) -> pd.DataFrame:
    """Score all headlines in df_events with FinBERT.

    Loads model lazily if tokenizer/model are not supplied.

    Parameters
    ----------
    df_events:
        DataFrame with event_id and headline_text columns.
    tokenizer, model:
        Optional pre-loaded components (useful for testing with mocks).

    Returns
    -------
    pd.DataFrame
        signals_{pipeline} schema: event_id, mean_sentiment,
        sentiment_variance (null), bimodality_index (null).
    """
    if df_events.empty:
        return pd.DataFrame(
            columns=["event_id", "mean_sentiment", "sentiment_variance", "bimodality_index"]
        )

    if tokenizer is None or model is None:
        tokenizer, model = _load_finbert()

    texts = df_events["headline_text"].fillna("").tolist()
    raw_scores = score_headlines(texts, tokenizer, model)

    # Validate range.
    arr = np.array(raw_scores, dtype=float)
    out_of_range = int(np.sum((arr < -1.0) | (arr > 1.0)))
    if out_of_range > 0:
        logger.warning(
            "%d FinBERT scores outside [-1, 1]; clipping.", out_of_range
        )
        arr = np.clip(arr, -1.0, 1.0)

    logger.info(
        "FinBERT scoring complete: %d events, mean=%.3f, std=%.3f.",
        len(df_events),
        float(np.mean(arr)),
        float(np.std(arr)),
    )

    return pd.DataFrame(
        {
            "event_id": df_events["event_id"].values,
            "mean_sentiment": arr,
            "sentiment_variance": None,
            "bimodality_index": None,
        }
    )


def run_finbert_baseline(
    df_events: pd.DataFrame | None = None,
    write_parquet: bool = True,
) -> pd.DataFrame:
    """Load events, run FinBERT, optionally write signals_finbert.parquet.

    Parameters
    ----------
    df_events:
        Events DataFrame; loaded from events.parquet if None.
    write_parquet:
        If True, write output to data/signals_finbert.parquet.

    Returns
    -------
    pd.DataFrame
        FinBERT sentiment signal DataFrame.
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
        df_signals.to_parquet(FINBERT_SIGNAL_PATH, index=False, engine="pyarrow")
        logger.info("Wrote signals_finbert.parquet (%d rows).", len(df_signals))

    return df_signals
