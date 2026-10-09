"""STUB (BR0) — owner SIM replaces in SIM3. Working now: a fixed inventory."""
from __future__ import annotations

import numpy as np

from pitwall.types import TrackParams, TyreSet


def sample_inventory(P: TrackParams, rng: np.random.Generator) -> list[TyreSet]:
    """Fixed inventory: 2 new HARD, 2 new MEDIUM, 1 new SOFT, 2 used SOFT (age 3), 2 INTERMEDIATE, 1 WET."""
    return [
        TyreSet(set_id=0, compound="HARD", age_laps=0),
        TyreSet(set_id=1, compound="HARD", age_laps=0),
        TyreSet(set_id=2, compound="MEDIUM", age_laps=0),
        TyreSet(set_id=3, compound="MEDIUM", age_laps=0),
        TyreSet(set_id=4, compound="SOFT", age_laps=0),
        TyreSet(set_id=5, compound="SOFT", age_laps=3),
        TyreSet(set_id=6, compound="SOFT", age_laps=3),
        TyreSet(set_id=7, compound="INTERMEDIATE", age_laps=0),
        TyreSet(set_id=8, compound="INTERMEDIATE", age_laps=0),
        TyreSet(set_id=9, compound="WET", age_laps=0),
    ]
