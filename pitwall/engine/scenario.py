"""Random race conditions: safety cars, rain, lap noise and the forecast. Owner: Ashwin (SIM).

sample_scenario() = one "true" race world that all four cars share.
sample_futures()  = many imagined futures for the strategist, built ONLY from what it can see.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pitwall.core import GREEN, SC, VSC, TrackParams

RAIN_RISE, RAIN_DRY = 0.15, 0.08      # wetness change per lap
FORECAST_HORIZON = 15                 # laps until the forecast is no better than the base rate


@dataclass(frozen=True, eq=False)
class Scenario:
    track: str
    seed: int
    laps: int
    status: np.ndarray     # (laps,) GREEN/VSC/SC on each lap
    wetness: np.ndarray    # (laps,) 0..1
    noise: np.ndarray      # (laps,) seconds, the same for every car
    forecast: np.ndarray   # (laps, laps): forecast[l, k] = chance lap k is wet, as known after lap l
    tags: tuple[str, ...]


def _safety_cars(P: TrackParams, laps: int, rng: np.random.Generator, sc_mult: float) -> np.ndarray:
    status = np.full(laps, GREEN, dtype=np.int8)
    i = 0
    while i < laps:
        u = rng.random()
        if u < P.p_sc * sc_mult:
            kind = SC
        elif u < (P.p_sc + P.p_vsc) * sc_mult:
            kind = VSC
        else:
            i += 1
            continue
        length = int(rng.integers(P.sc_len[0], P.sc_len[1] + 1))
        status[i:i + length] = kind
        i += length + 2  # a couple of green laps before the next one
    return status


def _rain(P: TrackParams, laps: int, rng: np.random.Generator, rain_prob: float) -> np.ndarray:
    wet = np.zeros(laps)
    if rng.random() >= rain_prob:
        return wet
    start = int(rng.integers(3, max(4, laps - 8)))
    peak = rng.uniform(0.4, 1.0)
    hold = int(rng.integers(5, 21))
    level = 0.0
    for k in range(start, laps):
        raining = k < start + hold
        level = min(peak, level + RAIN_RISE) if raining else max(0.0, level - RAIN_DRY)
        wet[k] = level
    return wet


def _forecast(P: TrackParams, wet: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    laps = len(wet)
    truth = (wet > 0.2).astype(float)
    base = min(0.5, P.p_rain * 0.3)
    fc = np.zeros((laps, laps))
    for l in range(laps):
        h = np.arange(laps - l)
        acc = np.clip(1.0 - h / FORECAST_HORIZON, 0.0, 1.0)
        f = acc * truth[l:] + (1 - acc) * base + rng.normal(0, 0.05, laps - l)
        fc[l, l:] = np.clip(f, 0.0, 1.0)
    return fc


def sample_scenario(P: TrackParams, seed: int, rain_prob: float | None = None, sc_mult: float = 1.0) -> Scenario:
    """One reproducible race world (same seed -> same race)."""
    rng = np.random.default_rng(seed)
    status = _safety_cars(P, P.laps, rng, sc_mult)
    wet = _rain(P, P.laps, rng, P.p_rain if rain_prob is None else rain_prob)
    noise = rng.normal(0.0, P.noise_sd, P.laps)
    fc = _forecast(P, wet, rng)
    n_events = int(np.sum(np.diff(np.concatenate([[GREEN], status])) != 0) // 2 + (status[-1] != GREEN))
    tags = ("wet",) if wet.max() > 0.2 else (("chaotic",) if n_events >= 2 else ("dry",))
    return Scenario(P.name, seed, P.laps, status, wet, noise, fc, tags)


def sample_futures(P: TrackParams, lap: int, status_now: int, wet_now: float, rain_forecast: np.ndarray,
                   n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """n imagined continuations of the race from lap `lap` (arrays of shape (n, laps_left)).

    Uses only what the strategist can see: current status and wetness, the forecast and track rates.
    Rain: each future draws one threshold u; laps whose forecast is above u are raining.
    This keeps rain spells continuous and matches the forecast probabilities exactly.
    """
    R = P.laps - lap
    status = np.zeros((n, R), dtype=np.int8)
    remaining = np.zeros(n, dtype=int)
    kind = np.full(n, GREEN, dtype=np.int8)
    if status_now != GREEN:
        remaining = rng.integers(1, P.sc_len[1], size=n)
        kind[:] = status_now
    cooldown = np.zeros(n, dtype=int)
    for k in range(R):
        active = remaining > 0
        status[:, k] = np.where(active, kind, GREEN)
        remaining = np.where(active, remaining - 1, 0)
        cooldown = np.where(active & (remaining == 0), 2, np.maximum(cooldown - 1, 0))
        u = rng.random(n)
        start_sc = (~active) & (cooldown == 0) & (u < P.p_sc)
        start_vsc = (~active) & (cooldown == 0) & (u >= P.p_sc) & (u < P.p_sc + P.p_vsc)
        new_len = rng.integers(P.sc_len[0], P.sc_len[1] + 1, size=n)
        kind = np.where(start_sc, SC, np.where(start_vsc, VSC, kind)).astype(np.int8)
        remaining = np.where(start_sc | start_vsc, new_len, remaining)

    thresh = rng.random(n)[:, None]
    raining = np.asarray(rain_forecast)[None, :R] > thresh            # (n, R)
    peak = rng.uniform(0.4, 1.0, size=n)
    wet = np.zeros((n, R))
    level = np.full(n, float(wet_now))
    for k in range(R):
        level = np.where(raining[:, k], np.minimum(np.maximum(peak, level), level + RAIN_RISE),
                         np.maximum(0.0, level - RAIN_DRY))
        wet[:, k] = level
    noise = rng.normal(0.0, P.noise_sd, size=(n, R))
    return {"status": status, "wetness": wet, "noise": noise}
