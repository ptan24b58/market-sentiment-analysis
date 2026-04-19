"""FastAPI sidecar for the interactive headline-simulation mode.

Two endpoints:
  POST /simulate/preview  — 60 stratified personas, no dynamics (~15s)
  POST /simulate/full     — all 300 personas + Deffuant sweep (~60s)

Load personas and social graph once at import time (module-level cache).
CORS is enabled for http://localhost:3000 (Next.js dev server).
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.stratified import stratified_sample
from src.api.validators import validate_request
from src.config import (
    BEDROCK_CONCURRENT_SEMAPHORE,
    DEFFUANT_EPSILON_SWEEP,
    DEFFUANT_MU,
    DEFFUANT_ROUNDS,
)
from src.dynamics.runner import run_dynamics_sweep
from src.llm.bedrock_client import invoke_nova_lite
from src.llm.persona_scorer import score_event_against_personas

# ---------------------------------------------------------------------------
# Module-level data cache
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

with open(_DATA_DIR / "personas.json") as _f:
    _PERSONAS: list[dict[str, Any]] = json.load(_f)

with open(_DATA_DIR / "social_graph.json") as _f:
    _GRAPH: dict[str, Any] = json.load(_f)

# Index personas by persona_id for O(1) demographic lookup.
_PERSONA_BY_ID: dict[int, dict[str, Any]] = {
    int(p["persona_id"]): p for p in _PERSONAS
}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Simulate API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_DEMO_FIELDS = ("zip_region", "political_lean", "income_bin", "age_bin", "lat", "lon")


def _build_event(headline_text: str, ticker: str) -> dict[str, Any]:
    ts = int(time.time())
    return {
        "event_id": f"custom-{ts}-{ticker}",
        "headline_text": headline_text[:2000],
        "ticker": ticker,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "is_custom": True,
    }


def _merge_demographics(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join demographic fields from _PERSONA_BY_ID into each scored row."""
    out = []
    for row in rows:
        pid = int(row["persona_id"])
        demo = _PERSONA_BY_ID.get(pid, {})
        merged = {**row}
        for field in _DEMO_FIELDS:
            merged[field] = demo.get(field)
        out.append(merged)
    return out


def _region_stats(
    rows: list[dict[str, Any]],
    sentiment_col: str = "raw_sentiment",
) -> dict[str, float]:
    """Compute mean sentiment per zip_region."""
    totals: dict[str, list[float]] = {}
    for row in rows:
        region = row.get("zip_region")
        val = row.get(sentiment_col)
        if region is None or val is None:
            continue
        # Skip NaN (failed parses stored as None or float nan).
        try:
            f = float(val)
        except (TypeError, ValueError):
            continue
        import math
        if math.isnan(f):
            continue
        totals.setdefault(region, []).append(f)
    return {r: sum(vs) / len(vs) for r, vs in totals.items()}


def _parse_failure_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    failed = sum(1 for r in rows if r.get("parse_failed"))
    return failed / len(rows)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/simulate/preview")
async def simulate_preview(body: dict) -> JSONResponse:
    """Score 60 stratified personas; no dynamics."""
    headline_text, ticker = validate_request(body)

    t0 = time.perf_counter()
    event = _build_event(headline_text, ticker)

    sample = stratified_sample(_PERSONAS, n=60, key="zip_region", seed=7)
    semaphore = asyncio.Semaphore(BEDROCK_CONCURRENT_SEMAPHORE)

    df = await score_event_against_personas(
        event=event,
        personas=sample,
        invoke_fn=invoke_nova_lite,
        semaphore=semaphore,
    )

    rows: list[dict[str, Any]] = df.to_dict(orient="records")

    # Bedrock hard-failure guard: >30% failures → 503.
    pfr = _parse_failure_rate(rows)
    if pfr > 0.30:
        return JSONResponse(
            status_code=503,
            content={
                "error": "bedrock_unavailable",
                "detail": f"Parse failure rate {pfr:.0%} exceeds threshold (30%).",
            },
        )

    rows_with_demo = _merge_demographics(rows)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return JSONResponse(
        content={
            "phase": "preview",
            "event": event,
            "persona_sentiments": rows_with_demo,
            "region_stats": _region_stats(rows_with_demo),
            "parse_failure_rate": pfr,
            "elapsed_ms": elapsed_ms,
            "sample_size": len(rows_with_demo),
        }
    )


@app.post("/simulate/full")
async def simulate_full(body: dict) -> JSONResponse:
    """Score all 300 personas and run Deffuant epsilon sweep."""
    headline_text, ticker = validate_request(body)

    t0 = time.perf_counter()
    event = _build_event(headline_text, ticker)

    semaphore = asyncio.Semaphore(BEDROCK_CONCURRENT_SEMAPHORE)

    df = await score_event_against_personas(
        event=event,
        personas=_PERSONAS,
        invoke_fn=invoke_nova_lite,
        semaphore=semaphore,
    )

    rows: list[dict[str, Any]] = df.to_dict(orient="records")
    pfr = _parse_failure_rate(rows)
    if pfr > 0.30:
        return JSONResponse(
            status_code=503,
            content={
                "error": "bedrock_unavailable",
                "detail": f"Parse failure rate {pfr:.0%} exceeds threshold (30%).",
            },
        )

    # Run Deffuant sweep.
    df_dyn, _diagnostics = run_dynamics_sweep(
        df,
        _GRAPH,
        epsilons=DEFFUANT_EPSILON_SWEEP,
        mu=DEFFUANT_MU,
        rounds=DEFFUANT_ROUNDS,
        seed=7,
    )

    rows_dyn: list[dict[str, Any]] = df_dyn.to_dict(orient="records")
    rows_with_demo = _merge_demographics(rows_dyn)

    # Build region_stats_dyn: {epsilon_str: {region: mean}}.
    region_stats_dyn: dict[str, dict[str, float]] = {}
    for eps in DEFFUANT_EPSILON_SWEEP:
        col = f"post_dynamics_{eps:g}"
        region_stats_dyn[f"{eps:g}"] = _region_stats(rows_with_demo, sentiment_col=col)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return JSONResponse(
        content={
            "phase": "full",
            "event": event,
            "persona_sentiments": rows_with_demo,
            "region_stats_raw": _region_stats(rows_with_demo, sentiment_col="raw_sentiment"),
            "region_stats_dyn": region_stats_dyn,
            "parse_failure_rate": pfr,
            "elapsed_ms": elapsed_ms,
            "sample_size": len(rows_with_demo),
        }
    )
