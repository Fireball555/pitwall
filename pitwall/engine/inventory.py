"""Which tyre sets a car has left for the race. Owner: Ashwin (SIM).

Real teams start the race with whatever survived practice and qualifying:
a few new hard/medium sets, mostly used softs, plus rain tyres.
"""
from __future__ import annotations

import numpy as np

from pitwall.core import HARD, INTER, MEDIUM, SOFT, WET, TrackParams, TyreSet


def sample_inventory(P: TrackParams, rng: np.random.Generator) -> list[TyreSet]:
    sets: list[TyreSet] = []

    def add(cid: int, count: int, age_lo: int = 0, age_hi: int = 0) -> None:
        for _ in range(count):
            sets.append(TyreSet(len(sets), cid, int(rng.integers(age_lo, age_hi + 1))))

    add(HARD, int(rng.integers(1, 3)))
    add(MEDIUM, int(rng.integers(1, 3)))
    add(SOFT, 1)
    add(SOFT, int(rng.integers(2, 4)), 2, 6)   # used softs from qualifying
    add(INTER, 2)
    add(WET, 1)
    return sets
