"""Deterministic stratified sampling over a list of persona dicts.

Splits personas into buckets by `key`, picks ceil(n / num_keys) from each
bucket (shuffled with `seed`), concatenates and truncates to exactly `n`.

If any bucket has fewer personas than the per-bucket quota, all of that
bucket is taken and the overall count may fall short of n — this is
intentional and documented here so callers can handle it downstream.
"""

from __future__ import annotations

import math
import random
from typing import Any


def stratified_sample(
    personas: list[dict[str, Any]],
    n: int,
    key: str = "zip_region",
    seed: int = 7,
) -> list[dict[str, Any]]:
    """Return up to `n` personas sampled proportionally from each `key` bucket.

    Parameters
    ----------
    personas:
        Full list of persona dicts.
    n:
        Target sample size.
    key:
        Field name to stratify on (default "zip_region").
    seed:
        RNG seed for reproducibility.

    Returns
    -------
    list[dict]
        Sampled personas, length <= n. Order is deterministic for a given seed.
    """
    rng = random.Random(seed)

    # Build buckets preserving insertion order of first appearance.
    buckets: dict[str, list[dict[str, Any]]] = {}
    for p in personas:
        val = p[key]
        buckets.setdefault(val, []).append(p)

    num_keys = len(buckets)
    if num_keys == 0:
        return []

    per_bucket = math.ceil(n / num_keys)

    collected: list[dict[str, Any]] = []
    for bucket in buckets.values():
        shuffled = bucket[:]
        rng.shuffle(shuffled)
        collected.extend(shuffled[:per_bucket])

    # Truncate to exactly n (or fewer if total < n due to small buckets).
    return collected[:n]
