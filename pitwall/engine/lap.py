"""How long one lap takes. Owner: Ashwin (SIM).

Every argument may be a number or a numpy array (all broadcast together), so the strategist
can time 200 imagined futures in one call. Keep it pure numpy: no Python `if` on arrays.
"""
from __future__ import annotations

import numpy as np

from pitwall.core import SC, VSC, TrackParams


def wet_penalty(P: TrackParams, cid, wet) -> np.ndarray:
    """Seconds lost for running compound `cid` at wetness `wet` (linear between 0, 0.5, 1)."""
    cid = np.asarray(cid)
    wet = np.clip(np.asarray(wet, dtype=float), 0.0, 1.0)
    p0, p1, p2 = P.wet_pen[cid, 0], P.wet_pen[cid, 1], P.wet_pen[cid, 2]
    low = p0 + (p1 - p0) * (wet / 0.5)
    high = p1 + (p2 - p1) * ((wet - 0.5) / 0.5)
    return np.where(wet <= 0.5, low, high)


def lap_time(P: TrackParams, cid, age, fuel, wet, status, noise) -> np.ndarray:
    """Lap time in seconds.

    cid: compound id; age: laps already on this set (0 = first lap, adds warm-up);
    fuel: kg on board; wet: track wetness 0..1; status: GREEN/VSC/SC; noise: random seconds.
    """
    cid = np.asarray(cid)
    age = np.asarray(age, dtype=float)
    green = (
        P.base_lap
        + P.offset[cid]
        + P.deg[cid] * age
        + P.cliff_coef[cid] * np.maximum(0.0, age - P.cliff_lap[cid]) ** 2
        + np.where(age == 0, P.warmup[cid], 0.0)
        + P.fuel_effect * np.asarray(fuel, dtype=float)
        + wet_penalty(P, cid, wet)
        + noise
    )
    status = np.asarray(status)
    sc_lap = np.maximum(green, P.base_lap * P.sc_factor + 0.2 * np.asarray(noise))
    vsc_lap = np.maximum(green, P.base_lap * P.vsc_factor + 0.2 * np.asarray(noise))
    return np.where(status == SC, sc_lap, np.where(status == VSC, vsc_lap, green))
