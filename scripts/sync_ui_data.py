"""Copy pipeline outputs to ui/public/data/ for the Next.js app.

Converts parquet → JSON and renames columns where Python uses dots but JS can't
(e.g. `post_dynamics_0.3` → `post_dynamics_03`).

Usage:
    python -m scripts.sync_ui_data

Idempotent — safe to run multiple times. Overwrites any existing files in
ui/public/data/. After running, refresh localhost:3000 to see real data.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path

import pandas as pd

from src import config

logger = logging.getLogger(__name__)


UI_DATA_DIR = config.PROJECT_ROOT / "ui" / "public" / "data"


def _df_to_json_records(df: pd.DataFrame, path: Path) -> None:
    """Write DataFrame as JSON array of records, stringifying non-JSON-safe types."""
    # Stringify timestamps
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)
    # Convert numpy lists (e.g. gdelt_theme_tags) to regular lists
    path.write_text(df.to_json(orient="records", date_format="iso"))


def _rename_dotted_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename `post_dynamics_0.2/0.3/0.4` → `post_dynamics_02/03/04` for JS."""
    rename_map = {c: c.replace(".", "") for c in df.columns if "post_dynamics_" in c}
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def sync_events() -> int:
    p = config.DATA_DIR / "events.parquet"
    if not p.exists():
        logger.warning("Missing %s; UI will fall back to mock events", p.name)
        return 0
    df = pd.read_parquet(p)
    # Serialize list columns (gdelt_theme_tags, entity_tags) properly
    for col in ("gdelt_theme_tags", "entity_tags"):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: list(v) if v is not None else [])
    _df_to_json_records(df, UI_DATA_DIR / "events.json")
    logger.info("events.json: %d rows (%d sentinels)",
                len(df), int(df.get("is_sentinel", pd.Series()).sum()))
    return len(df)


def sync_persona_sentiments() -> int:
    p = config.DATA_DIR / "persona_sentiments.parquet"
    if not p.exists():
        logger.warning("Missing %s; UI will fall back to mock sentiments", p.name)
        return 0
    df = pd.read_parquet(p)
    df = _rename_dotted_columns(df)
    _df_to_json_records(df, UI_DATA_DIR / "persona_sentiments.json")
    logger.info("persona_sentiments.json: %d rows", len(df))
    return len(df)


def sync_signals() -> None:
    """Convert all 5+1 signal parquets to a single signals.json bundle."""
    bundle: dict[str, list] = {}
    for name in ("lm", "finbert", "zero_shot", "persona_only", "persona_graph",
                 "persona_graph_eps_sweep"):
        p = config.DATA_DIR / f"signals_{name}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            df = _rename_dotted_columns(df)
            bundle[name] = df.to_dict(orient="records")
            logger.info("  signals_%s: %d rows", name, len(df))
    (UI_DATA_DIR / "signals.json").write_text(json.dumps(bundle, default=str))


def copy_json_file(name: str) -> None:
    src = config.DATA_DIR / name
    if not src.exists():
        logger.warning("Missing %s; UI will fall back to mock", name)
        return
    shutil.copy2(src, UI_DATA_DIR / name)
    logger.info("Copied %s (%d bytes)", name, src.stat().st_size)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    UI_DATA_DIR.mkdir(parents=True, exist_ok=True)

    event_count = sync_events()
    sync_persona_sentiments()
    sync_signals()

    for name in ("ablation_results.json", "sentinel_diagnostics.json",
                 "personas.json", "social_graph.json", "graph_diagnostics.json"):
        copy_json_file(name)

    logger.info("UI data sync complete → %s (%d events)", UI_DATA_DIR, event_count)
    logger.info("Refresh localhost:3000 to see real data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
