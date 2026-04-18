"""Homophily diagnostics: measure normalised excess-above-baseline.

Definitions
-----------
For a given attribute (e.g. political_lean):
    same_share   = share of edges whose endpoints share the attribute value
    baseline     = expected same-share under random pairing = sum_g p_g^2
    coleman_idx  = (same_share - baseline) / (1 - baseline)   in (-., 1]

`coleman_idx` is the standard Coleman-style normalised homophily index
(McPherson 2001; Halberstam-Knight 2016) and is what the plan's
HOMOPHILY_TARGETS refer to: a number in [0, 1] denoting the share of the
"available room above baseline" that intra-group edges actually occupy.

Targets:
    political   ~ 0.35   (Halberstam-Knight 2016 echo-chamber estimate)
    income      ~ 0.25
    geographic  ~ 0.50   (geographic homophily is structurally strong)

`measure_homophily` reports same_share, baseline, AND coleman_idx and
flags `within_tolerance` based on coleman_idx vs. target +/- tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from src.config import HOMOPHILY_TARGETS, HOMOPHILY_TOLERANCE


@dataclass(frozen=True)
class HomophilyResult:
    dimension: str
    same_share: float
    baseline: float
    coleman_index: float
    target: float
    tolerance: float
    within_tolerance: bool


def _baseline_share(attr_values: Sequence) -> float:
    """Probability two random nodes share an attribute value (sum p_g^2)."""
    counts: Dict = {}
    for v in attr_values:
        counts[v] = counts.get(v, 0) + 1
    n = len(attr_values)
    if n == 0:
        return 0.0
    return sum((c / n) ** 2 for c in counts.values())


def _same_edge_share(
    edges: Iterable[Tuple[int, int]],
    attr_by_node: Mapping[int, object],
) -> Tuple[float, int]:
    edge_list = list(edges)
    if not edge_list:
        return 0.0, 0
    same = sum(1 for u, v in edge_list if attr_by_node[u] == attr_by_node[v])
    return same / len(edge_list), len(edge_list)


def measure_homophily(
    edges: Iterable[Tuple[int, int]],
    nodes_by_attr: Mapping[str, Mapping[int, object]],
    *,
    targets: Mapping[str, float] = HOMOPHILY_TARGETS,
    tolerance: float = HOMOPHILY_TOLERANCE,
) -> Dict[str, HomophilyResult]:
    """Compute homophily per attribute dimension and compare against targets.

    Parameters
    ----------
    edges:
        Iterable of (u, v) integer node-id pairs (undirected; each edge counted
        once).
    nodes_by_attr:
        {dim_name: {node_id: attr_value}} for each dimension we want to score.
        Targets dict keys must overlap with these dimension names.
    targets:
        Per-dimension `same_share` target (default: HOMOPHILY_TARGETS).
    tolerance:
        Absolute tolerance for `within_tolerance` flag.
    """
    edge_list = list(edges)
    out: Dict[str, HomophilyResult] = {}
    for dim, target in targets.items():
        if dim not in nodes_by_attr:
            continue
        attr_by_node = nodes_by_attr[dim]
        same_share, _ = _same_edge_share(edge_list, attr_by_node)
        baseline = _baseline_share(list(attr_by_node.values()))
        denom = 1 - baseline
        coleman = (same_share - baseline) / denom if denom > 1e-9 else 0.0
        out[dim] = HomophilyResult(
            dimension=dim,
            same_share=same_share,
            baseline=baseline,
            coleman_index=coleman,
            target=target,
            tolerance=tolerance,
            within_tolerance=abs(coleman - target) <= tolerance,
        )
    return out


def homophily_diagnostics(
    edges: Iterable[Tuple[int, int]],
    nodes_by_attr: Mapping[str, Mapping[int, object]],
) -> Dict[str, Dict[str, float]]:
    """JSON-friendly variant of `measure_homophily`."""
    results = measure_homophily(edges, nodes_by_attr)
    return {
        dim: {
            "same_share": r.same_share,
            "baseline": r.baseline,
            "coleman_index": r.coleman_index,
            "target": r.target,
            "tolerance": r.tolerance,
            "within_tolerance": bool(r.within_tolerance),
        }
        for dim, r in results.items()
    }


def all_within_tolerance(results: Mapping[str, HomophilyResult]) -> bool:
    return all(r.within_tolerance for r in results.values())
