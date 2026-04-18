"""Texas demographic stratification (ACS-like marginal proportions).

We bundle a compact CSV (data/acs_strata.csv) with marginal proportions for
income x age x region x political_lean drawn from public TX ACS 5-year
summary stats and TX precinct totals (52R/47D/1I per
`POLITICAL_LEAN_DISTRIBUTION_TX`).

A live ACS pull is out of scope in 24h; the bundled marginals are a transparent
approximation. The downstream calibration test only requires sampler proportions
land within +/- 10% of these targets, so small marginal noise is fine.

The module also exposes:
- region centroids (lat/lon) used when assigning persona coordinates
- a contextual-anchor pool indexed by (political_lean, income_bin, region) so
  generated prompts vary in framing while remaining demographically plausible.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Dict, List, Tuple

from src.config import DATA_DIR, POLITICAL_LEAN_DISTRIBUTION_TX

INCOME_BINS: Tuple[str, ...] = ("low", "mid", "high")
AGE_BINS: Tuple[str, ...] = ("18-29", "30-44", "45-64", "65+")
ZIP_REGIONS: Tuple[str, ...] = (
    "Austin Metro",
    "Houston Metro",
    "Dallas-Fort Worth",
    "San Antonio Metro",
    "Permian Basin",
    "Rio Grande Valley",
    "East Texas",
    "Panhandle",
)
POLITICAL_LEANS: Tuple[str, ...] = ("R", "D", "I")

# Approximate centroid lat/lon per region; jitter is added per persona.
REGION_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "Austin Metro": (30.27, -97.74),
    "Houston Metro": (29.76, -95.37),
    "Dallas-Fort Worth": (32.78, -96.80),
    "San Antonio Metro": (29.42, -98.49),
    "Permian Basin": (31.99, -102.08),
    "Rio Grande Valley": (26.20, -98.23),
    "East Texas": (32.35, -95.30),
    "Panhandle": (35.22, -101.83),
}

# Annual income range per income_bin (used to sample exact $ amount).
INCOME_RANGES: Dict[str, Tuple[int, int]] = {
    "low": (15_000, 35_000),
    "mid": (35_000, 100_000),
    "high": (100_000, 350_000),
}

# Exact age range per age_bin (used to sample integer age).
AGE_RANGES: Dict[str, Tuple[int, int]] = {
    "18-29": (18, 29),
    "30-44": (30, 44),
    "45-64": (45, 64),
    "65+": (65, 88),
}


def income_bracket_label(income_bin: str) -> str:
    """Human label used in the demographic suffix template."""
    return income_bin


def region_centroid(zip_region: str, jitter_rng: random.Random) -> Tuple[float, float]:
    """Return centroid +/- small jitter so personas don't collide on the map."""
    lat0, lon0 = REGION_CENTROIDS[zip_region]
    return (
        round(lat0 + jitter_rng.uniform(-0.35, 0.35), 4),
        round(lon0 + jitter_rng.uniform(-0.45, 0.45), 4),
    )


# Contextual anchor pool — keyed by (political_lean, income_bin). Region is
# folded into selection where it changes the natural anchor (oil & gas in
# Permian, agriculture in RGV/Panhandle, tech in Austin/DFW, etc.).
_ANCHOR_POOL: Dict[Tuple[str, str], List[str]] = {
    ("R", "low"): [
        "You work in the oil and gas industry and follow energy prices daily.",
        "You drive a pickup, attend church on Sundays, and worry about gas prices.",
        "You work shifts at a refinery and prioritize job stability over change.",
        "You run a small auto-repair shop and watch fuel costs closely.",
    ],
    ("R", "mid"): [
        "You manage a logistics team and pay close attention to fuel and freight costs.",
        "You own a small business and follow tax policy and energy news.",
        "You work in midstream pipeline operations and track commodity headlines.",
        "You are a long-haul trucker concerned with diesel prices and trade flows.",
    ],
    ("R", "high"): [
        "You are an executive in the energy sector and read the WSJ every morning.",
        "You own multiple rental properties and track interest rates carefully.",
        "You manage a family ranch and watch commodity and weather news.",
        "You are a partner at a Houston law firm focused on energy contracts.",
    ],
    ("D", "low"): [
        "You work in food service in a major city and worry about rent and inflation.",
        "You are a home health aide and follow healthcare policy news.",
        "You work in retail and are concerned about wages and benefits.",
        "You are a single parent who relies on public transit and follows local policy.",
    ],
    ("D", "mid"): [
        "You teach public school and follow education policy and state funding news.",
        "You are a registered nurse who follows healthcare and pharma headlines.",
        "You work in city government and follow infrastructure funding news.",
        "You work in nonprofit advocacy and pay attention to environmental policy.",
    ],
    ("D", "high"): [
        "You are a software engineer in Austin and invest in tech ETFs.",
        "You are a physician who follows healthcare policy and biotech news.",
        "You are a startup founder and watch venture funding and rate moves closely.",
        "You are a tenured professor with diversified retirement holdings.",
    ],
    ("I", "low"): [
        "You are a student worker who follows headlines casually and forms your own views.",
        "You work seasonal jobs and don't strongly identify with either party.",
        "You are skeptical of both parties and read news from multiple sources.",
        "You are a retiree on a fixed income who votes by issue rather than party.",
    ],
    ("I", "mid"): [
        "You are a freelance contractor who avoids partisan media and reads broadly.",
        "You work in tech and weigh issues independently of party platform.",
        "You are a healthcare worker who votes the issue, not the party.",
        "You run a consulting firm and care most about pragmatic outcomes.",
    ],
    ("I", "high"): [
        "You are a portfolio manager who reads across the political spectrum.",
        "You are a corporate consultant who avoids partisan framing of news.",
        "You manage your own investments and weigh policy on its merits.",
        "You are a retired executive who follows markets and forms independent views.",
    ],
}

# Region-specific overrides (drawn first if available).
_REGION_ANCHORS: Dict[Tuple[str, str], List[str]] = {
    ("R", "Permian Basin"): [
        "You work in the oil and gas industry in Midland and follow WTI crude prices daily.",
        "You drive frac trucks in the Permian and track rig-count releases each Friday.",
    ],
    ("D", "Austin Metro"): [
        "You work for a tech startup in Austin and follow venture funding and AI news.",
        "You are a UT Austin researcher who follows climate and energy policy news.",
    ],
    ("R", "East Texas"): [
        "You manage a timber operation and follow housing-starts and lumber news.",
        "You are a retired refinery worker in Beaumont and follow petrochemical headlines.",
    ],
    ("D", "Houston Metro"): [
        "You work at a Texas Medical Center hospital and follow healthcare policy.",
        "You are a port worker in Houston and follow trade and shipping news.",
    ],
    ("R", "Panhandle"): [
        "You manage a cattle ranch near Amarillo and follow beef and grain prices.",
        "You work at a wind farm in the Panhandle and track power-grid headlines.",
    ],
    ("D", "Rio Grande Valley"): [
        "You are a community college instructor in McAllen and follow border policy news.",
        "You work in cross-border logistics and follow trade and tariff headlines.",
    ],
}


def sample_contextual_anchor(
    political_lean: str,
    income_bin: str,
    zip_region: str,
    rng: random.Random,
) -> str:
    """Pick a one-sentence demographic anchor.

    Region-specific anchors are preferred when available, then fall back to
    the (political_lean, income_bin) pool. Always returns a non-empty string.
    """
    region_pool = _REGION_ANCHORS.get((political_lean, zip_region))
    if region_pool and rng.random() < 0.6:
        return rng.choice(region_pool)
    pool = _ANCHOR_POOL.get((political_lean, income_bin))
    if not pool:
        # Defensive fallback: never raise, never duplicate prefix structure.
        return "You follow national news regularly and form your own market views."
    return rng.choice(pool)


def load_acs_strata(csv_path: Path | None = None) -> Dict[str, Dict[str, float]]:
    """Load bundled ACS-like marginal proportions.

    Returns a nested dict: {dimension: {bin_name: proportion}}.
    Validates that proportions per dimension sum to 1.0 within 0.01.
    """
    csv_path = csv_path or (DATA_DIR / "acs_strata.csv")
    out: Dict[str, Dict[str, float]] = {}
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dim = row["dimension"]
            out.setdefault(dim, {})[row["bin"]] = float(row["proportion"])
    for dim, bins in out.items():
        total = sum(bins.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"ACS strata for dim={dim!r} sum to {total:.3f}, expected 1.0"
            )
    # Sanity: political_lean must match the locked TX distribution within 0.01
    for lean, share in POLITICAL_LEAN_DISTRIBUTION_TX.items():
        loaded = out["political_lean"].get(lean, 0.0)
        if abs(loaded - share) > 0.01:
            raise ValueError(
                f"political_lean[{lean}] in CSV ({loaded}) drifts from "
                f"POLITICAL_LEAN_DISTRIBUTION_TX ({share})"
            )
    return out
