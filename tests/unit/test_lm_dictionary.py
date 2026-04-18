"""Unit tests for L-M dictionary scoring (Workstream A3).

Tests: test_lm_dictionary_scoring — L-M dict returns signed float for known
positive/negative sentences.

See plan Section 3 (Unit Tests).
"""

import pandas as pd

from src.baselines.lm_dictionary import score_headline, score_events


class TestLMDictionaryScoring:
    """test_lm_dictionary_scoring: signed float for known positive/negative text."""

    def test_positive_sentence_returns_positive_score(self):
        text = "The company reported record earnings growth and strong profit gains."
        score = score_headline(text)
        assert isinstance(score, float), "Score must be a float."
        assert score > 0.0, f"Expected positive score for positive text, got {score}."

    def test_negative_sentence_returns_negative_score(self):
        text = "The company suffered a severe loss and faces bankruptcy risk amid fraud allegations."
        score = score_headline(text)
        assert isinstance(score, float), "Score must be a float."
        assert score < 0.0, f"Expected negative score for negative text, got {score}."

    def test_score_in_range(self):
        texts = [
            "Record profit and strong growth ahead.",
            "Severe loss, failure, and bankruptcy risk.",
            "The company released its quarterly report today.",
            "Significant decline in revenue due to supply chain disruption.",
            "Outstanding performance and excellent returns for investors.",
        ]
        for text in texts:
            score = score_headline(text)
            assert -1.0 <= score <= 1.0, (
                f"Score {score} out of [-1, 1] for: {text!r}"
            )

    def test_neutral_sentence_score_bounded(self):
        text = "The company held its annual meeting today."
        score = score_headline(text)
        # Neutral text may score 0 or near 0; must still be in range.
        assert -1.0 <= score <= 1.0

    def test_empty_string_returns_zero(self):
        score = score_headline("")
        # (0 - 0) / (0 + 0 + 1) = 0.0
        assert score == 0.0, f"Empty string should score 0.0, got {score}."

    def test_score_events_dataframe(self):
        df = pd.DataFrame(
            {
                "event_id": ["e1", "e2", "e3"],
                "headline_text": [
                    "Record profit and excellent earnings growth.",
                    "Bankruptcy, fraud, and severe loss reported.",
                    "The company published its annual report.",
                ],
            }
        )
        result = score_events(df)
        assert list(result.columns) == [
            "event_id",
            "mean_sentiment",
            "sentiment_variance",
            "bimodality_index",
        ]
        assert len(result) == 3
        assert result["mean_sentiment"].iloc[0] > 0.0, "First row should be positive."
        assert result["mean_sentiment"].iloc[1] < 0.0, "Second row should be negative."
        # All scores in range.
        assert (result["mean_sentiment"].between(-1.0, 1.0)).all()

    def test_score_events_empty_dataframe(self):
        df = pd.DataFrame(columns=["event_id", "headline_text"])
        result = score_events(df)
        assert len(result) == 0

    def test_predominantly_positive_beats_negative(self):
        positive_text = "Outstanding success with excellent earnings and strong growth profit award."
        negative_text = "Severe loss failure bankruptcy fraud risk damage crisis debt decline."
        pos_score = score_headline(positive_text)
        neg_score = score_headline(negative_text)
        assert pos_score > neg_score, (
            f"Positive text ({pos_score}) should outscore negative text ({neg_score})."
        )
