"""Synthetic graph hits homophily targets and basic structural invariants."""

from __future__ import annotations

import json

import pytest

from src.config import (
    DATA_DIR,
    GRAPH_MEAN_DEGREE_RANGE,
    HOMOPHILY_TARGETS,
    HOMOPHILY_TOLERANCE,
)
from src.graph import build_social_graph, measure_homophily
from src.graph.social_graph import graph_diagnostics
from src.personas import generate_personas


@pytest.fixture(scope="module")
def personas():
    return generate_personas()


@pytest.fixture(scope="module")
def graph(personas):
    # Use the cached on-disk graph if present (faster); otherwise build.
    p = DATA_DIR / "social_graph.json"
    if p.exists():
        return json.loads(p.read_text())
    return build_social_graph(personas)


def test_node_count(graph):
    assert graph["n_nodes"] == 300


def test_largest_component(graph, personas):
    diag = graph_diagnostics(graph, personas)
    assert diag["largest_component_share"] >= 0.95


def test_mean_degree_in_band(graph, personas):
    diag = graph_diagnostics(graph, personas)
    lo, hi = GRAPH_MEAN_DEGREE_RANGE
    assert lo <= diag["mean_degree"] <= hi


def test_homophily_within_tolerance(graph, personas):
    edges = [(u, v) for u, v, _ in graph["edges"]]
    nodes_by_attr = {
        "political": {p["persona_id"]: p["political_lean"] for p in personas},
        "income": {p["persona_id"]: p["income_bin"] for p in personas},
        "geographic": {p["persona_id"]: p["zip_region"] for p in personas},
    }
    results = measure_homophily(edges, nodes_by_attr)
    for dim, target in HOMOPHILY_TARGETS.items():
        r = results[dim]
        assert (
            abs(r.coleman_index - target) <= HOMOPHILY_TOLERANCE
        ), f"{dim}: coleman={r.coleman_index} target={target}"
