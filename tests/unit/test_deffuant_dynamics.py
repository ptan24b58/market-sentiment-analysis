"""Deffuant dynamics: convergence on toy graph + assert-no-LLM-calls."""

from __future__ import annotations

import numpy as np
import pytest

import src.llm.bedrock_client as bedrock_client
from src.dynamics.deffuant import deffuant_round, deffuant_run


@pytest.fixture(autouse=True)
def _explode_if_bedrock_called(monkeypatch):
    """Any call into bedrock from the dynamics path must fail loudly."""

    async def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("Deffuant must NOT invoke Bedrock")

    monkeypatch.setattr(bedrock_client, "invoke_nova_lite", _boom)
    yield


def _toy_graph_5node():
    # Path graph: 0-1-2-3-4
    return {"edges": [[0, 1, 1.0], [1, 2, 1.0], [2, 3, 1.0], [3, 4, 1.0]]}


def test_deffuant_round_converges_when_within_epsilon():
    opinions = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    eps = 0.5
    g = _toy_graph_5node()
    new = deffuant_round(opinions, g, epsilon=eps, mu=0.5)
    # All pairs within epsilon: every node moves toward the mean of its
    # local neighbourhood. Per the *cumulative* round, each node's shift is
    # bounded by 0.5*epsilon per edge incident to it, but the convergence
    # property we verify is that the opinion range (max - min) shrinks.
    assert (new.max() - new.min()) < (opinions.max() - opinions.min())
    # Mean is preserved by symmetric Deffuant updates.
    assert abs(new.mean() - opinions.mean()) < 1e-9


def test_deffuant_round_no_change_outside_epsilon():
    opinions = np.array([-1.0, 1.0, -1.0, 1.0, -1.0])
    new = deffuant_round(opinions, _toy_graph_5node(), epsilon=0.1, mu=0.5)
    np.testing.assert_array_almost_equal(new, opinions)


def test_deffuant_2_round_converges_with_known_epsilon():
    # All five within epsilon=1.0, mu=0.5 => after 2 rounds opinions
    # should have collapsed toward the mean.
    opinions = np.array([0.0, 0.2, 0.4, 0.6, 0.8])
    final, shifts = deffuant_run(
        opinions, _toy_graph_5node(), epsilon=1.0, mu=0.5, rounds=2, seed=1
    )
    # Range of opinions must shrink.
    assert (final.max() - final.min()) < (opinions.max() - opinions.min())
    # Mean is preserved by symmetric Deffuant updates.
    assert abs(final.mean() - opinions.mean()) < 1e-9
    # Shift magnitude per round respects mu * epsilon cap.
    for s in shifts:
        assert s <= 0.5 * 1.0 + 1e-9


def test_deffuant_invariant_per_round_shift_bounded_by_epsilon():
    """Each persona shifts by at most epsilon per round.

    With mu=0.5 and the gate condition |o_i - o_j| < eps, every edge update
    moves an endpoint by at most mu*eps = 0.5*eps. A node touched by k
    incident edges accumulates at most k * 0.5*eps; but with a single
    edge per node only (matching the spec exit criterion), the bound is
    epsilon. We verify the strict bound on a 1-degree (matching) graph
    and a softer bound on a 2-regular cycle.
    """
    rng = np.random.default_rng(0)
    n = 20
    # Perfect matching: each node has degree 1.
    edges = [[2 * i, 2 * i + 1, 1.0] for i in range(n // 2)]
    opinions = rng.uniform(-1, 1, size=n)
    eps = 0.3
    new = deffuant_round(opinions, {"edges": edges}, epsilon=eps, mu=0.5)
    # On a matching graph, |delta_i| <= 0.5 * eps for every node.
    assert np.all(np.abs(new - opinions) <= 0.5 * eps + 1e-9)
    # On a cycle (degree 2), the loose bound is eps.
    cycle = [[i, (i + 1) % n, 1.0] for i in range(n)]
    new_cycle = deffuant_round(opinions, {"edges": cycle}, epsilon=eps, mu=0.5)
    assert np.all(np.abs(new_cycle - opinions) <= eps + 1e-9)


def test_runner_isolates_events_no_bedrock(monkeypatch):
    """End-to-end runner.py call must not touch Bedrock either."""
    import pandas as pd

    from src.dynamics.runner import run_dynamics_sweep

    df = pd.DataFrame(
        [
            {"event_id": "e1", "persona_id": 0, "raw_sentiment": 0.0},
            {"event_id": "e1", "persona_id": 1, "raw_sentiment": 0.1},
            {"event_id": "e1", "persona_id": 2, "raw_sentiment": 0.9},
            {"event_id": "e2", "persona_id": 0, "raw_sentiment": -0.3},
            {"event_id": "e2", "persona_id": 1, "raw_sentiment": -0.2},
            {"event_id": "e2", "persona_id": 2, "raw_sentiment": 0.8},
        ]
    )
    g = {"edges": [[0, 1, 1.0], [1, 2, 1.0]]}
    out, diag = run_dynamics_sweep(df, g, n_personas=3)
    for col in ("post_dynamics_0.2", "post_dynamics_0.3", "post_dynamics_0.4"):
        assert col in out.columns
    # epsilon_0.2 / 0.3 / 0.4 keys
    assert set(diag.keys()) == {"epsilon_0.2", "epsilon_0.3", "epsilon_0.4"}
    # NaN-safe: with all values populated, no post_dynamics value is NaN.
    for col in ("post_dynamics_0.2", "post_dynamics_0.3", "post_dynamics_0.4"):
        assert out[col].isna().sum() == 0


def test_runner_preserves_nan_for_failed_parses():
    import numpy as np
    import pandas as pd

    from src.dynamics.runner import run_dynamics_sweep

    df = pd.DataFrame(
        [
            {"event_id": "e1", "persona_id": 0, "raw_sentiment": 0.0},
            {"event_id": "e1", "persona_id": 1, "raw_sentiment": float("nan")},
            {"event_id": "e1", "persona_id": 2, "raw_sentiment": 0.5},
        ]
    )
    g = {"edges": [[0, 1, 1.0], [1, 2, 1.0]]}
    out, _ = run_dynamics_sweep(df, g, n_personas=3)
    nan_row = out[(out.event_id == "e1") & (out.persona_id == 1)].iloc[0]
    for col in ("post_dynamics_0.2", "post_dynamics_0.3", "post_dynamics_0.4"):
        assert np.isnan(nan_row[col])
