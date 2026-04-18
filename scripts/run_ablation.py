"""Compute the 5-way ablation table from existing signal parquets.

Usage:
    python -m scripts.run_ablation

Reads signals_{lm,finbert,zero_shot,persona_only,persona_graph}.parquet and
abnormal_returns.parquet, writes ablation_results.json and ablation_table.csv.
Does NOT require Bedrock — pure post-processing.
"""

from __future__ import annotations

import logging
import sys

from src import config
from src.metrics.ablation import build_ablation

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    required = [
        "events.parquet",
        "abnormal_returns.parquet",
        "signals_lm.parquet",
        "signals_finbert.parquet",
        "signals_zero_shot.parquet",
        "signals_persona_only.parquet",
        "signals_persona_graph.parquet",
    ]
    missing = [f for f in required if not (config.DATA_DIR / f).exists()]
    if missing:
        logger.error("Missing required files: %s", missing)
        return 2

    build_ablation()
    logger.info("Ablation complete — see data/ablation_results.json and data/ablation_table.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
