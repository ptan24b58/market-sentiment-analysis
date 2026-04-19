"""Deterministic stratified sampling over a list of persona dicts.

Round-robin across `key` buckets: every bucket gets one persona before
any bucket gets a second. This guarantees every bucket value is represented
in the sample as long as the sample size >= number of buckets.

If any bucket runs out of personas, it's skipped on subsequent rounds.
Returns exactly `n` personas (or fewer if the total pool is smaller than `n`).
"""

from __future__ import annotations

import random
from typing import Any


def stratified_sample(
    personas: list[dict[str, Any]],
    n: int,
    key: str = "zip_region",
    seed: int = 7,
) -> list[dict[str, Any]]:
    """Return up to `n` personas, round-robin across buckets keyed on `key`.

    Every unique value of `key` is guaranteed at least one sample so long as
    that bucket is non-empty AND n >= num_keys. Remaining picks continue
    round-robin, cycling through buckets in their original insertion order,
    so the sample stays proportional in the limit without starving small
    buckets (the earlier ceil-truncate approach dropped 2 regions at n=60
    across 14 regions).

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
        buckets.setdefault(p[key], []).append(p)

    if not buckets:
        return []

    # Shuffle each bucket so picks within a bucket are random.
    for bucket in buckets.values():
        rng.shuffle(bucket)

    # Round-robin pop from each bucket. One pass = 1 per bucket; then repeat.
    collected: list[dict[str, Any]] = []
    indices = {k: 0 for k in buckets}
    keys_in_order = list(buckets.keys())
    # Safety bound: can't collect more than total personas available.
    max_possible = sum(len(b) for b in buckets.values())
    target = min(n, max_possible)

    while len(collected) < target:
        any_added = False
        for k in keys_in_order:
            if len(collected) >= target:
                break
            i = indices[k]
            if i < len(buckets[k]):
                collected.append(buckets[k][i])
                indices[k] = i + 1
                any_added = True
        if not any_added:
            # All buckets exhausted.
            break

    return collected
