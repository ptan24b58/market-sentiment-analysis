"""Synthetic 300-node social graph with calibrated homophily.

Approach
--------
Edges are sampled with per-pair probability of the form

    p(i, j) = clip(p_base * w_pol^[same_pol] * w_inc^[same_inc] * w_geo^[same_geo], 0, 1)

i.e. a separate multiplicative weight per attribute dimension. This lets the
calibrator independently tune each dimension's homophily without coupling
through a single shared-count variable, which is essential because the
geographic baseline (~0.18) and political baseline (~0.49) are very
different and need to land at very different `same_share` targets.

We grid-search `(w_pol, w_inc, w_geo)` and pick the configuration that lands
within tolerance on all three dims while keeping mean degree in
`GRAPH_MEAN_DEGREE_RANGE`. `p_base` is solved analytically per candidate so
expected edge count matches the midpoint of that range. If no candidate
lands fully inside tolerance, we return the closest config (sum of squared
dim errors). Largest connected component is also returned in diagnostics; we
attach a small number of "bridge" edges if the largest component drops
below 95% to satisfy the connectivity floor.
"""

from __future__ import annotations

import json
import random
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import networkx as nx

from src.config import (
    DATA_DIR,
    GRAPH_MEAN_DEGREE_RANGE,
    HOMOPHILY_TARGETS,
    HOMOPHILY_TOLERANCE,
)
from src.graph.homophily_calibration import (
    homophily_diagnostics,
    measure_homophily,
)


def _node_attr_lookup(personas: Sequence[Mapping]) -> Dict[str, Dict[int, object]]:
    return {
        "political": {p["persona_id"]: p["political_lean"] for p in personas},
        "income": {p["persona_id"]: p["income_bin"] for p in personas},
        "geographic": {p["persona_id"]: p["zip_region"] for p in personas},
    }


_DIMS = ("political_lean", "income_bin", "zip_region")


def _pair_weight(
    a: Mapping, b: Mapping, w_pol: float, w_inc: float, w_geo: float
) -> float:
    w = 1.0
    if a["political_lean"] == b["political_lean"]:
        w *= w_pol
    if a["income_bin"] == b["income_bin"]:
        w *= w_inc
    if a["zip_region"] == b["zip_region"]:
        w *= w_geo
    return w


def _sample_edges(
    personas: Sequence[Mapping],
    p_base: float,
    weights: Tuple[float, float, float],
    rng: random.Random,
) -> List[Tuple[int, int]]:
    w_pol, w_inc, w_geo = weights
    edges: List[Tuple[int, int]] = []
    for i, j in combinations(range(len(personas)), 2):
        prob = p_base * _pair_weight(personas[i], personas[j], w_pol, w_inc, w_geo)
        if prob >= 1.0 or rng.random() < prob:
            edges.append((i, j))
    return edges


def _solve_pbase(
    personas: Sequence[Mapping],
    weights: Tuple[float, float, float],
    target_edges: int,
) -> float:
    """Pick p_base so the unclipped expectation of edges = target_edges."""
    w_pol, w_inc, w_geo = weights
    sum_w = 0.0
    for i, j in combinations(range(len(personas)), 2):
        sum_w += _pair_weight(personas[i], personas[j], w_pol, w_inc, w_geo)
    return target_edges / sum_w if sum_w > 0 else 0.0


def _grid_search_edges(
    personas: Sequence[Mapping],
    rng: random.Random,
) -> Tuple[List[Tuple[int, int]], Tuple[float, Tuple[float, float, float]]]:
    n = len(personas)
    target_mean_deg = (
        GRAPH_MEAN_DEGREE_RANGE[0] + GRAPH_MEAN_DEGREE_RANGE[1]
    ) / 2.0
    target_edges = int(target_mean_deg * n / 2)
    nodes_by_attr = _node_attr_lookup(personas)

    # Per-dimension multiplicative weight grid. Geographic gets the largest
    # weights because its baseline (~0.18) is far below the high target.
    # Political needs moderate weighting (target Coleman idx 0.35 from
    # baseline ~0.49 means same-share ~0.67).
    pol_grid = [2.0, 2.3, 2.6, 2.9, 3.2, 3.5]
    inc_grid = [1.5, 1.8, 2.1, 2.4, 2.8]
    geo_grid = [6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0]

    best = None
    best_err = float("inf")
    best_edges: List[Tuple[int, int]] = []

    for w_pol in pol_grid:
        for w_inc in inc_grid:
            for w_geo in geo_grid:
                weights = (w_pol, w_inc, w_geo)
                p_base = _solve_pbase(personas, weights, target_edges)
                local_rng = random.Random(rng.randint(0, 2**31 - 1))
                edges = _sample_edges(personas, p_base, weights, local_rng)
                mean_deg = 2 * len(edges) / n
                if not (
                    GRAPH_MEAN_DEGREE_RANGE[0]
                    <= mean_deg
                    <= GRAPH_MEAN_DEGREE_RANGE[1]
                ):
                    continue
                results = measure_homophily(edges, nodes_by_attr)
                err = sum(
                    (r.coleman_index - HOMOPHILY_TARGETS[d]) ** 2
                    for d, r in results.items()
                )
                if all(r.within_tolerance for r in results.values()):
                    return edges, (p_base, weights)
                if err < best_err:
                    best_err = err
                    best = (p_base, weights)
                    best_edges = edges
    if best is None:
        weights = (2.0, 1.6, 8.0)
        p_base = _solve_pbase(personas, weights, target_edges)
        edges = _sample_edges(personas, p_base, weights, rng)
        return edges, (p_base, weights)
    return best_edges, best


def _ensure_connected(
    edges: List[Tuple[int, int]],
    n: int,
    rng: random.Random,
    largest_min_share: float = 0.95,
) -> List[Tuple[int, int]]:
    """Add bridge edges if the largest connected component < threshold."""
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(edges)
    components = sorted(nx.connected_components(g), key=len, reverse=True)
    if not components:
        return edges
    largest = components[0]
    if len(largest) / n >= largest_min_share:
        return edges
    main = list(largest)
    new_edges = list(edges)
    for comp in components[1:]:
        # Add a single bridge per orphan component into the main one.
        u = rng.choice(main)
        v = rng.choice(list(comp))
        new_edges.append((min(u, v), max(u, v)))
        main.append(v)
    return new_edges


def build_social_graph(
    personas: Sequence[Mapping],
    *,
    seed: int = 42,
) -> Dict:
    """Build the calibrated synthetic graph.

    Returns a JSON-friendly dict:
        {
          "n_nodes": int,
          "edges": [[u, v, weight], ...],
          "adjacency": {node_id: [neighbour_id, ...], ...},
          "config": {"p_base": float, "mix": [m0, m1, m2, m3]},
        }
    """
    rng = random.Random(seed)
    n = len(personas)
    edges, (p_base, weights) = _grid_search_edges(personas, rng)
    edges = _ensure_connected(edges, n, rng)
    edges = sorted({(min(u, v), max(u, v)) for u, v in edges})
    weighted_edges = [[u, v, 1.0] for u, v in edges]
    adjacency: Dict[int, List[int]] = {i: [] for i in range(n)}
    for u, v in edges:
        adjacency[u].append(v)
        adjacency[v].append(u)
    return {
        "n_nodes": n,
        "edges": weighted_edges,
        "adjacency": {str(k): v for k, v in adjacency.items()},
        "config": {
            "p_base": p_base,
            "w_political": weights[0],
            "w_income": weights[1],
            "w_geographic": weights[2],
            "seed": seed,
        },
    }


def graph_diagnostics(
    graph: Mapping,
    personas: Sequence[Mapping],
) -> Dict:
    """Compute measured homophily, degree stats, component summary."""
    edges = [(u, v) for u, v, _ in graph["edges"]]
    n = graph["n_nodes"]
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(edges)
    degs = [d for _, d in g.degree()]
    components = sorted([len(c) for c in nx.connected_components(g)], reverse=True)
    nodes_by_attr = _node_attr_lookup(personas)
    homophily = homophily_diagnostics(edges, nodes_by_attr)
    return {
        "n_nodes": n,
        "n_edges": len(edges),
        "mean_degree": sum(degs) / max(n, 1),
        "median_degree": float(sorted(degs)[n // 2]) if degs else 0.0,
        "min_degree": min(degs) if degs else 0,
        "max_degree": max(degs) if degs else 0,
        "n_components": len(components),
        "largest_component_size": components[0] if components else 0,
        "largest_component_share": (components[0] / n) if components else 0.0,
        "homophily": homophily,
        "tolerance": HOMOPHILY_TOLERANCE,
    }


def write_graph_json(
    graph: Mapping,
    diagnostics: Mapping,
    *,
    graph_path: Optional[Path] = None,
    diagnostics_path: Optional[Path] = None,
) -> Tuple[Path, Path]:
    graph_path = graph_path or (DATA_DIR / "social_graph.json")
    diagnostics_path = diagnostics_path or (DATA_DIR / "graph_diagnostics.json")
    graph_path.write_text(json.dumps(graph))
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2))
    return graph_path, diagnostics_path


if __name__ == "__main__":
    personas_path = DATA_DIR / "personas.json"
    personas = json.loads(personas_path.read_text())
    graph = build_social_graph(personas)
    diag = graph_diagnostics(graph, personas)
    gp, dp = write_graph_json(graph, diag)
    print(f"Wrote {gp} ({diag['n_edges']} edges, mean deg {diag['mean_degree']:.2f})")
    print(f"Wrote {dp}")
