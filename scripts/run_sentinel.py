"""Run the H+4 sentinel gate: 3 polarizing events × 300 personas → variance check.

Usage:
    python -m scripts.run_sentinel

Requires AWS credentials (see .env.example). Writes
`data/sentinel_results.json` and `data/sentinel_diagnostics.json`.
Exits with status 0 on PASS (σ ≥ 0.1 on ≥ 2/3 events), status 1 on FAIL.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

import pandas as pd

from src import config
from src.llm.bedrock_client import invoke_nova_lite
from src.llm.sentinel_gate import run_sentinel_gate

logger = logging.getLogger(__name__)


async def _amain() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    personas_path = config.DATA_DIR / "personas.json"
    events_path = config.DATA_DIR / "events_stage1.parquet"

    if not personas_path.exists():
        logger.error("Missing personas.json — run persona generator first")
        return 2
    if not events_path.exists():
        logger.error("Missing events_stage1.parquet — run GDELT ingest first")
        return 2

    personas = json.loads(personas_path.read_text())
    events_df = pd.read_parquet(events_path)
    sentinel_events = events_df[events_df["is_sentinel"]].to_dict("records")
    if not sentinel_events:
        logger.error("No events marked is_sentinel=True")
        return 2

    result = await run_sentinel_gate(
        sentinel_events=sentinel_events,
        personas=personas,
        invoke_fn=invoke_nova_lite,
    )

    diag = result.get("diagnostics", {})
    logger.info(
        "Sentinel gate: gate_pass=%s variances=%s parse_failure_rate=%s",
        diag.get("gate_pass"),
        diag.get("variances"),
        diag.get("parse_failure_rate"),
    )
    return 0 if diag.get("gate_pass") else 1


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
