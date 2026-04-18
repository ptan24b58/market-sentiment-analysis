"""Synthetic social graph with calibrated homophily.

Modules:
    homophily_calibration  -- measure homophily ratios on a given edge list
    social_graph  -- SBM-based 300-node generator that grid-searches block
                     mixing matrices to hit the locked HOMOPHILY_TARGETS.
"""

from src.graph.homophily_calibration import (
    measure_homophily,
    homophily_diagnostics,
    HomophilyResult,
)
from src.graph.social_graph import (
    build_social_graph,
    write_graph_json,
)

__all__ = [
    "measure_homophily",
    "homophily_diagnostics",
    "HomophilyResult",
    "build_social_graph",
    "write_graph_json",
]
