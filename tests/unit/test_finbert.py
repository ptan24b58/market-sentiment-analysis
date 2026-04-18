"""Unit tests for FinBERT sentiment baseline (Workstream A3).

Tests: test_finbert_scoring — FinBERT returns sentiment in [-1, 1] for
5 sample headlines.

Uses a lightweight mock of the transformer model to avoid network calls and
GPU requirements during unit testing. The mock returns deterministic logits.

See plan Section 3 (Unit Tests).
"""

import pandas as pd
from unittest.mock import MagicMock


def _make_mock_tokenizer(texts):
    """Return a mock tokenizer that produces dummy tensors."""
    import torch

    mock_tok = MagicMock()

    def tokenizer_call(texts_arg, **kwargs):
        batch_size = len(texts_arg) if isinstance(texts_arg, list) else 1
        return {
            "input_ids": torch.zeros(batch_size, 10, dtype=torch.long),
            "attention_mask": torch.ones(batch_size, 10, dtype=torch.long),
        }

    mock_tok.side_effect = tokenizer_call
    return mock_tok


def _make_mock_model(batch_size: int, logit_pattern: str = "positive"):
    """Return a mock FinBERT model with fixed logits.

    logit_pattern:
        'positive'  -> high P(positive), low P(negative)
        'negative'  -> low P(positive), high P(negative)
        'neutral'   -> balanced
    """
    import torch

    class MockOutput:
        def __init__(self, logits):
            self.logits = logits

    mock_model = MagicMock()

    if logit_pattern == "positive":
        # logits: [positive=5, negative=-5, neutral=0]
        logits_template = torch.tensor([[5.0, -5.0, 0.0]])
    elif logit_pattern == "negative":
        # logits: [positive=-5, negative=5, neutral=0]
        logits_template = torch.tensor([[-5.0, 5.0, 0.0]])
    else:
        # neutral: balanced
        logits_template = torch.tensor([[0.0, 0.0, 1.0]])

    def model_call(**kwargs):
        bs = kwargs["input_ids"].shape[0]
        logits = logits_template.repeat(bs, 1)
        return MockOutput(logits)

    mock_model.side_effect = model_call
    mock_model.__call__ = mock_model
    return mock_model


class TestFinBERTScoring:
    """test_finbert_scoring: [-1, 1] for 5 sample headlines."""

    SAMPLE_HEADLINES = [
        "Tesla reports record quarterly profit and raises full-year guidance.",
        "ExxonMobil faces massive environmental fine over Gulf spill.",
        "AT&T announces strategic partnership to expand 5G coverage nationwide.",
        "Halliburton reports quarterly earnings in line with analyst expectations.",
        "ConocoPhillips cuts capital expenditure amid oil price uncertainty.",
    ]

    def test_score_range_with_mock(self):
        """All 5 sample headlines score in [-1, 1] with mock model."""
        from src.baselines.finbert_baseline import score_headlines

        import torch

        mock_tokenizer = MagicMock()

        def tok_call(texts, **kwargs):
            bs = len(texts) if isinstance(texts, list) else 1
            return {
                "input_ids": torch.zeros(bs, 10, dtype=torch.long),
                "attention_mask": torch.ones(bs, 10, dtype=torch.long),
            }

        mock_tokenizer.side_effect = tok_call

        # Mixed logits: alternate positive/negative per item.
        call_count = [0]

        class MockOutput:
            def __init__(self, logits):
                self.logits = logits

        mock_model = MagicMock()

        def model_call(**kwargs):
            import torch

            bs = kwargs["input_ids"].shape[0]
            # Alternate: positive for even indices, negative for odd.
            logits = []
            for i in range(bs):
                if (call_count[0] + i) % 2 == 0:
                    logits.append([5.0, -5.0, 0.0])
                else:
                    logits.append([-5.0, 5.0, 0.0])
            call_count[0] += bs
            return MockOutput(torch.tensor(logits))

        mock_model.side_effect = model_call
        mock_model.__call__ = mock_model

        scores = score_headlines(self.SAMPLE_HEADLINES, mock_tokenizer, mock_model)

        assert len(scores) == len(self.SAMPLE_HEADLINES)
        for i, score in enumerate(scores):
            assert -1.0 <= score <= 1.0, (
                f"Score {score} out of [-1, 1] for headline {i}: {self.SAMPLE_HEADLINES[i]!r}"
            )

    def test_positive_logits_give_positive_score(self):
        """When model returns high positive logits, score > 0."""
        from src.baselines.finbert_baseline import score_headlines
        import torch

        mock_tokenizer = MagicMock()
        mock_tokenizer.side_effect = lambda texts, **kw: MagicMock(
            input_ids=torch.zeros(len(texts), 10, dtype=torch.long),
            attention_mask=torch.ones(len(texts), 10, dtype=torch.long),
        )

        class Out:
            logits = torch.tensor([[5.0, -5.0, 0.0]])

        mock_model = MagicMock()
        mock_model.side_effect = lambda **kw: Out()
        mock_model.__call__ = mock_model

        scores = score_headlines(["Tesla beats earnings estimates."], mock_tokenizer, mock_model)
        assert scores[0] > 0.0, f"Expected positive score, got {scores[0]}."

    def test_negative_logits_give_negative_score(self):
        """When model returns high negative logits, score < 0."""
        from src.baselines.finbert_baseline import score_headlines
        import torch

        mock_tokenizer = MagicMock()
        mock_tokenizer.side_effect = lambda texts, **kw: MagicMock(
            input_ids=torch.zeros(len(texts), 10, dtype=torch.long),
            attention_mask=torch.ones(len(texts), 10, dtype=torch.long),
        )

        class Out:
            logits = torch.tensor([[-5.0, 5.0, 0.0]])

        mock_model = MagicMock()
        mock_model.side_effect = lambda **kw: Out()
        mock_model.__call__ = mock_model

        scores = score_headlines(["Company faces bankruptcy and fraud investigation."], mock_tokenizer, mock_model)
        assert scores[0] < 0.0, f"Expected negative score, got {scores[0]}."

    def test_score_events_schema(self):
        """score_events returns correct DataFrame schema."""
        import torch
        from src.baselines.finbert_baseline import score_events

        df = pd.DataFrame(
            {
                "event_id": ["e1", "e2"],
                "headline_text": [
                    "Record profits reported.",
                    "Severe losses and layoffs announced.",
                ],
            }
        )

        mock_tokenizer = MagicMock()
        mock_tokenizer.side_effect = lambda texts, **kw: {
            "input_ids": torch.zeros(len(texts), 10, dtype=torch.long),
            "attention_mask": torch.ones(len(texts), 10, dtype=torch.long),
        }

        class Out:
            def __init__(self, bs):
                self.logits = torch.tensor([[2.0, -2.0, 0.0]] * bs)

        mock_model = MagicMock()
        mock_model.side_effect = lambda **kw: Out(kw["input_ids"].shape[0])
        mock_model.__call__ = mock_model

        result = score_events(df, tokenizer=mock_tokenizer, model=mock_model)

        assert list(result.columns) == [
            "event_id",
            "mean_sentiment",
            "sentiment_variance",
            "bimodality_index",
        ]
        assert len(result) == 2
        assert (result["mean_sentiment"].between(-1.0, 1.0)).all()

    def test_score_events_empty(self):
        from src.baselines.finbert_baseline import score_events

        df = pd.DataFrame(columns=["event_id", "headline_text"])
        result = score_events(df)
        assert len(result) == 0
