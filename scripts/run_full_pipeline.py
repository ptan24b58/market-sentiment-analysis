"""Run the full end-to-end pipeline: GDELT → prices → baselines → personas → dynamics → ablation.

Usage:
    python -m scripts.run_full_pipeline [--skip-ingest] [--skip-baselines] [--skip-personas]

Runs stages in order. Requires AWS credentials (see .env.example) for
Bedrock-backed stages. Use flags to resume from an intermediate stage when
the corresponding data files already exist.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

import pandas as pd

from src import config

logger = logging.getLogger(__name__)


async def _amain(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Full pipeline orchestrator")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-baselines", action="store_true")
    parser.add_argument("--skip-personas", action="store_true")
    parser.add_argument("--skip-zero-shot", action="store_true")
    parser.add_argument("--skip-ablation", action="store_true")
    args = parser.parse_args(argv)

    if not args.skip_ingest:
        logger.info("[1/5] GDELT ingest + stage-1 filter + sentinel selection")
        from src.data.gdelt_ingest import ingest_gdelt
        from src.data.event_filter import apply_stage1_filter
        from src.data.sentinel_selector import select_sentinels
        from src.data.price_ingest import download_prices
        from src.metrics.abnormal_returns import run_a2_pipeline

        df_events = ingest_gdelt(
            tickers=config.TEXAS_15_TICKERS,
            start_date=config.EVENT_WINDOW_START,
            end_date=config.EVENT_WINDOW_END,
            write_parquet=False,
        )
        df_events = apply_stage1_filter(df_events)
        df_events = select_sentinels(df_events)
        df_events.to_parquet(config.DATA_DIR / "events_stage1.parquet", index=False)
        logger.info("Stage-1 events: %d (sentinels: %d)", len(df_events), int(df_events["is_sentinel"].sum()))

        logger.info("[1b/5] Price download + AR + stage-2 filter")
        download_prices(
            tickers=[*config.TEXAS_15_TICKERS, config.MARKET_PROXY_TICKER],
            start_date=config.EVENT_WINDOW_START,
            end_date=config.EVENT_WINDOW_END,
        )
        df_events_final, df_ar = run_a2_pipeline(write_parquet=True)
        logger.info("Final events (post stage-2): %d", len(df_events_final))

    if not args.skip_baselines:
        logger.info("[2/5] L-M dictionary + FinBERT baselines")
        from src.baselines.lm_dictionary import run_lm_baseline
        from src.baselines.finbert_baseline import run_finbert_baseline

        df_events_final = pd.read_parquet(config.DATA_DIR / "events.parquet")
        run_lm_baseline(df_events_final)
        run_finbert_baseline(df_events_final)

    if not args.skip_personas:
        logger.info("[3/5] Persona pipeline: sentinel → full batch → dynamics → aggregation")
        from src.llm.bedrock_client import invoke_nova_lite
        from src.llm.sentinel_gate import run_sentinel_gate
        from src.llm.batch_runner import run_full_batch
        from src.dynamics.runner import run_dynamics_sweep
        from src.metrics.signal_aggregation import build_signal_files

        personas = json.loads((config.DATA_DIR / "personas.json").read_text())
        events_final_df = pd.read_parquet(config.DATA_DIR / "events.parquet")
        sentinel_events = events_final_df[events_final_df["is_sentinel"]].to_dict("records")
        all_events = events_final_df.to_dict("records")

        sentinel_result = await run_sentinel_gate(
            sentinel_events=sentinel_events,
            personas=personas,
            invoke_fn=invoke_nova_lite,
        )
        if not sentinel_result.get("diagnostics", {}).get("gate_pass"):
            logger.error("SENTINEL FAILED — abort. See data/sentinel_diagnostics.json.")
            return 1

        batch_result = await run_full_batch(
            events=all_events,
            personas=personas,
            invoke_fn=invoke_nova_lite,
        )
        df_persona_sentiments = batch_result.get("sentiments") if isinstance(batch_result, dict) else batch_result
        if df_persona_sentiments is None:
            df_persona_sentiments = pd.read_parquet(config.DATA_DIR / "persona_sentiments.parquet")

        graph = json.loads((config.DATA_DIR / "social_graph.json").read_text())
        df_persona_sentiments = run_dynamics_sweep(persona_sentiments=df_persona_sentiments, graph=graph)
        df_persona_sentiments.to_parquet(config.DATA_DIR / "persona_sentiments.parquet", index=False)

        build_signal_files(persona_sentiments_path=config.DATA_DIR / "persona_sentiments.parquet")

    if not args.skip_zero_shot:
        logger.info("[4/5] Zero-shot baseline")
        from src.baselines.nova_zero_shot import run_zero_shot_baseline
        from src.llm.bedrock_client import invoke_nova_lite

        events_final_df = pd.read_parquet(config.DATA_DIR / "events.parquet")
        await run_zero_shot_baseline(
            events=events_final_df.to_dict("records"),
            invoke_fn=invoke_nova_lite,
        )

    if not args.skip_ablation:
        logger.info("[5/5] 5-way ablation")
        from src.metrics.ablation import build_ablation
        build_ablation()

    logger.info("Pipeline complete. See data/ablation_results.json.")
    return 0


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
