"""Stratified persona sampler.

Generates 300 personas matching bundled TX ACS marginals within +/- 10% on
each dimension. Each persona is composed via
`build_persona_system_prompt(DEMOGRAPHIC_SUFFIX_TEMPLATE.format(**fields))`
so the cached SHARED_PREFIX remains identical across all personas.

Output: data/personas.json (list of objects, one per persona). Schema matches
plan Section 9 (`personas.json`).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from src.config import DATA_DIR, DEFAULT_PERSONA_COUNT
from src.llm.prompts import (
    DEMOGRAPHIC_SUFFIX_TEMPLATE,
    build_persona_system_prompt,
)
from src.personas.demographics import (
    AGE_RANGES,
    INCOME_RANGES,
    load_acs_strata,
    region_centroid,
    sample_contextual_anchor,
)

_PARTY_LABEL = {"R": "Republican", "D": "Democratic", "I": "Independent"}


def _quotas(strata: Dict[str, float], total: int) -> Dict[str, int]:
    """Largest-remainder allocation so per-bin counts sum exactly to `total`.

    This bounds the worst-case marginal error to one persona per bin,
    well inside the +/- 10% tolerance.
    """
    raw = {k: total * v for k, v in strata.items()}
    floors = {k: int(v) for k, v in raw.items()}
    remaining = total - sum(floors.values())
    # Distribute remaining seats by largest fractional remainder.
    by_remainder = sorted(
        ((raw[k] - floors[k], k) for k in strata),
        key=lambda t: (-t[0], t[1]),
    )
    for _, k in by_remainder[:remaining]:
        floors[k] += 1
    assert sum(floors.values()) == total
    return floors


def generate_personas(
    n: int = DEFAULT_PERSONA_COUNT,
    *,
    seed: int = 17,
    acs_strata: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Dict]:
    """Stratified-sample n personas.

    Strategy: allocate per-dimension quotas independently (income, age, region,
    political_lean), shuffle each list, then zip. With n=300 the quotas land
    on integers within +/- 1 of the target proportions, which is well within
    the +/- 10% tolerance demanded by the test.

    Each persona's system_prompt is composed via the locked shared-prefix +
    demographic-suffix structure (cache-safe).
    """
    if acs_strata is None:
        acs_strata = load_acs_strata()
    rng = random.Random(seed)

    income_quota = _quotas(acs_strata["income_bin"], n)
    age_quota = _quotas(acs_strata["age_bin"], n)
    region_quota = _quotas(acs_strata["zip_region"], n)
    political_quota = _quotas(acs_strata["political_lean"], n)

    def _expand(quota: Dict[str, int]) -> List[str]:
        out: List[str] = []
        for k, c in quota.items():
            out.extend([k] * c)
        rng.shuffle(out)
        return out

    incomes = _expand(income_quota)
    ages = _expand(age_quota)
    regions = _expand(region_quota)
    politics = _expand(political_quota)

    personas: List[Dict] = []
    seen_prompts: set[str] = set()
    for pid in range(n):
        income_bin = incomes[pid]
        age_bin = ages[pid]
        zip_region = regions[pid]
        political_lean = politics[pid]

        age = rng.randint(*AGE_RANGES[age_bin])
        annual_income = int(rng.randint(*INCOME_RANGES[income_bin]) // 500 * 500)
        lat, lon = region_centroid(zip_region, rng)
        anchor = sample_contextual_anchor(
            political_lean, income_bin, zip_region, rng
        )
        suffix = DEMOGRAPHIC_SUFFIX_TEMPLATE.format(
            age=age,
            income_bracket=income_bin,
            zip_region=zip_region,
            annual_income=annual_income,
            party_reg=_PARTY_LABEL[political_lean],
            contextual_anchor=anchor,
        )
        system_prompt = build_persona_system_prompt(suffix)
        # Disambiguate identical prompts deterministically — append "(persona N)"
        # to the contextual_anchor only on collision so cache prefix remains
        # identical for the vast majority.
        if system_prompt in seen_prompts:
            anchor = anchor.rstrip(".") + f" (persona {pid})."
            suffix = DEMOGRAPHIC_SUFFIX_TEMPLATE.format(
                age=age,
                income_bracket=income_bin,
                zip_region=zip_region,
                annual_income=annual_income,
                party_reg=_PARTY_LABEL[political_lean],
                contextual_anchor=anchor,
            )
            system_prompt = build_persona_system_prompt(suffix)
        seen_prompts.add(system_prompt)
        personas.append(
            {
                "persona_id": pid,
                "income_bin": income_bin,
                "age_bin": age_bin,
                "zip_region": zip_region,
                "political_lean": political_lean,
                "age": age,
                "annual_income": annual_income,
                "lat": lat,
                "lon": lon,
                "contextual_anchor": anchor,
                "system_prompt": system_prompt,
            }
        )
    return personas


def write_personas_json(
    personas: List[Dict], path: Optional[Path] = None
) -> Path:
    """Persist persona list as JSON (UTF-8, indented for diff-friendliness)."""
    path = path or (DATA_DIR / "personas.json")
    path.write_text(json.dumps(personas, indent=2))
    return path


if __name__ == "__main__":
    out = generate_personas()
    p = write_personas_json(out)
    print(f"Wrote {len(out)} personas -> {p}")
