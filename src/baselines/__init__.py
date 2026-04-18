"""Workstream A3: Baseline sentiment signal modules.

Provides L-M dictionary scoring and FinBERT inference for the 5-way ablation.
Both produce signals_{pipeline}.parquet with schema: event_id, mean_sentiment,
sentiment_variance (null), bimodality_index (null).
"""
