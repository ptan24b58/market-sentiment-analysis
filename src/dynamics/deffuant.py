"""Deffuant bounded-confidence opinion dynamics.

Update rule (per round):
    For each undirected edge (i, j) in `graph`:
        if |o_i - o_j| < epsilon:
            o_i' = o_i + mu * (o_j - o_i)
            o_j' = o_j + mu * (o_i - o_j)

We process edges in randomised order each round to avoid systematic ordering
bias. NO LLM calls -- this is pure math on cached float arrays. Caller must
ensure `opinions` is a 1D float ndarray indexed by persona_id.

`graph` accepts either:
    {"edges": [[u, v, w], ...], ...}        (our JSON contract)
    {"edges": [[u, v], ...], ...}
    [(u, v), ...]                            (raw edge list)
"""

from __future__ import annotations

import logging
from typing import List, Mapping, Sequence, Tuple, Union

import numpy as np

from src.config import DEFFUANT_MU, DEFFUANT_ROUNDS

logger = logging.getLogger(__name__)


GraphLike = Union[Mapping, Sequence[Tuple[int, int]], Sequence[Sequence[int]]]


def _extract_edges(graph: GraphLike) -> List[Tuple[int, int]]:
    if isinstance(graph, Mapping):
        raw = graph.get("edges", [])
    else:
        raw = graph
    edges: List[Tuple[int, int]] = []
    for e in raw:
        if len(e) >= 2:
            edges.append((int(e[0]), int(e[1])))
    return edges


def deffuant_round(
    opinions: np.ndarray,
    graph: GraphLike,
    epsilon: float,
    mu: float = DEFFUANT_MU,
    *,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """One Deffuant pass over all edges. Returns a NEW array (caller-safe).

    Edges are processed in a randomised order each call so the result is not
    biased by edge-list ordering. The Deffuant invariant holds per-edge: a
    persona shifts by at most `mu * (o_j - o_i)`, magnitude < `mu * epsilon`,
    so for `mu = 0.5, epsilon = 0.4` the cap is 0.2 < epsilon.
    """
    if rng is None:
        rng = np.random.default_rng(0)
    out = np.array(opinions, dtype=float, copy=True)
    edges = _extract_edges(graph)
    if not edges:
        return out
    order = rng.permutation(len(edges))
    for k in order:
        u, v = edges[int(k)]
        oi = out[u]
        oj = out[v]
        if abs(oi - oj) < epsilon:
            delta = mu * (oj - oi)
            out[u] = oi + delta
            out[v] = oj - delta
    return out


def deffuant_run(
    opinions: np.ndarray,
    graph: GraphLike,
    epsilon: float,
    *,
    mu: float = DEFFUANT_MU,
    rounds: int = DEFFUANT_ROUNDS,
    seed: int = 0,
) -> Tuple[np.ndarray, List[float]]:
    """Run multiple rounds and return (final_opinions, per_round_shift_l1).

    `per_round_shift_l1[r]` is the mean absolute opinion shift between
    rounds r and r+1 (a convergence diagnostic).
    """
    rng = np.random.default_rng(seed)
    current = np.array(opinions, dtype=float, copy=True)
    shifts: List[float] = []
    for r in range(rounds):
        prev = current
        current = deffuant_round(prev, graph, epsilon, mu=mu, rng=rng)
        shifts.append(float(np.mean(np.abs(current - prev))))
    return current, shifts


__all__ = ["deffuant_round", "deffuant_run"]
