"""Generate methodology.md, ablation_poster.md, and pitch_talking_points.md.

Usage:
    python -m scripts.generate_reports

Reads ablation_results.json + sentinel_diagnostics.json and selects the
appropriate narrative branch (Case A: signal / Case B: honest-collapse) via
`src.metrics.interpret`.
"""

from __future__ import annotations

import json
import logging
import sys

from src import config
from src.metrics.interpret import interpret_results

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    ablation_path = config.DATA_DIR / "ablation_results.json"
    sentinel_path = config.DATA_DIR / "sentinel_diagnostics.json"

    if not ablation_path.exists():
        logger.error("Missing ablation_results.json — run scripts.run_ablation first")
        return 2

    ablation = json.loads(ablation_path.read_text())
    sentinel = json.loads(sentinel_path.read_text()) if sentinel_path.exists() else {}

    narrative = interpret_results(ablation, sentinel)
    logger.info("Narrative branch: %s", narrative.get("branch"))
    logger.info("Reports written to reports/methodology.md, ablation_poster.md, pitch_talking_points.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
