"""Sentinel pipeline E2E with mocked Bedrock.

Verifies that 3 mock sentinel events x 10 personas (subset) produces
non-zero variance and a deterministic gate decision. Bedrock is mocked
to return persona-appropriate scores so variance is guaranteed > 0 even
under fully deterministic test runs.
"""

from __future__ import annotations

import asyncio
import json
import math

import pytest

from src.llm.sentinel_gate import run_sentinel_gate
from src.personas import generate_personas


@pytest.fixture
def personas_subset():
    return generate_personas()[:10]


@pytest.fixture
def sentinel_events():
    return [
        {
            "event_id": "ev_pol_1",
            "headline_text": "EPA tightens methane rules on Permian wells",
            "ticker": "XOM",
            "is_sentinel": True,
        },
        {
            "event_id": "ev_pol_2",
            "headline_text": "Texas attorney general sues federal agency over policy",
            "ticker": "OXY",
            "is_sentinel": True,
        },
        {
            "event_id": "ev_pol_3",
            "headline_text": "Tesla announces large layoffs in Austin",
            "ticker": "TSLA",
            "is_sentinel": True,
        },
    ]


def _make_diverse_invoke():
    """Returns an async invoke_fn whose output depends on persona+event.

    Republican personas score energy/regulation news negatively, Democratic
    personas positively, Independent personas neutral. This guarantees
    inter-persona variance > 0.
    """
    counter = {"n": 0}

    async def fake_invoke(system_prompt, user_prompt, **kwargs):
        counter["n"] += 1
        if "Republican voter" in system_prompt:
            score = -0.6
        elif "Democratic voter" in system_prompt:
            score = 0.5
        else:
            score = 0.05
        # Add small per-call jitter so variance computation isn't degenerate.
        jitter = ((counter["n"] * 17) % 13 - 6) / 100.0
        score = max(-1.0, min(1.0, score + jitter))
        return {
            "response_text": f"{score:.2f}",
            "cache_hit": counter["n"] > 1,
            "latency_ms": 12.3,
            "attempts": 1,
        }

    return fake_invoke


def test_sentinel_pipeline_e2e_variance_nonzero(
    sentinel_events, personas_subset, tmp_path
):
    invoke_fn = _make_diverse_invoke()
    diag = asyncio.run(
        run_sentinel_gate(
            sentinel_events=sentinel_events,
            personas=personas_subset,
            invoke_fn=invoke_fn,
            results_path=tmp_path / "sentinel_results.json",
            diagnostics_path=tmp_path / "sentinel_diagnostics.json",
        )
    )
    assert len(diag.per_event) == 3
    for ed in diag.per_event:
        assert ed.n_valid == 10
        assert ed.variance > 0.0
        assert not math.isnan(ed.std)
    # On-disk artefacts written.
    assert (tmp_path / "sentinel_results.json").exists()
    written = json.loads((tmp_path / "sentinel_diagnostics.json").read_text())
    assert "gate_pass" in written
    assert written["pass_required"] == diag.pass_required


def test_sentinel_pipeline_e2e_gate_pass_with_diverse_responses(
    sentinel_events, personas_subset, tmp_path
):
    invoke_fn = _make_diverse_invoke()
    diag = asyncio.run(
        run_sentinel_gate(
            sentinel_events=sentinel_events,
            personas=personas_subset,
            invoke_fn=invoke_fn,
            results_path=tmp_path / "results.json",
            diagnostics_path=tmp_path / "diag.json",
        )
    )
    # With R/D split + jitter, std on each event is well above 0.1.
    assert all(ed.std >= 0.1 for ed in diag.per_event)
    assert diag.gate_pass is True
    assert diag.parse_failure_rate == 0.0
