"""Persona generation: stratified sampling against bundled TX ACS proportions.

Modules:
    demographics  -- ACS strata loader, distribution helpers, contextual anchor pool
    persona_generator  -- stratified sampler emitting `data/personas.json`
"""

from src.personas.demographics import (
    INCOME_BINS,
    AGE_BINS,
    ZIP_REGIONS,
    POLITICAL_LEANS,
    load_acs_strata,
    income_bracket_label,
    region_centroid,
    sample_contextual_anchor,
)
from src.personas.persona_generator import generate_personas, write_personas_json

__all__ = [
    "INCOME_BINS",
    "AGE_BINS",
    "ZIP_REGIONS",
    "POLITICAL_LEANS",
    "load_acs_strata",
    "income_bracket_label",
    "region_centroid",
    "sample_contextual_anchor",
    "generate_personas",
    "write_personas_json",
]
