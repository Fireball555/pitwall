"""STUB (BR0) — owner SIM replaces in SIM2. Working now: all-green, dry, noisy scenarios."""
from __future__ import annotations

import numpy as np

from pitwall.types import GREEN, Observation, Scenario, TrackParams


def sample_scenario(P: TrackParams, seed: int, rain_prob: float | None = None, sc_mult: float = 1.0) -> Scenario:
    """All GREEN, dry, noise ~ N(0, noise_sd_s). Deterministic for a given seed."""
    rng = np.random.default_rng(seed)
    laps = P.laps
    status = np.full(laps, GREEN, dtype=np.int8)
    wetness = np.zeros(laps, dtype=float)
    noise = rng.normal(0.0, P.noise_sd_s, size=laps)
    forecast = np.zeros((laps, laps), dtype=float)
    return Scenario(
        track=P.track, seed=seed, laps=laps, status=status, wetness=wetness,
        noise=noise, forecast=forecast, tags=("dry",),
    )


def sample_futures(belief: TrackParams, obs: Observation, n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Sample n futures of the remaining race, from `obs` onward. Never sees the true Scenario."""
    remaining = belief.laps - obs.lap
    status = np.zeros((n, remaining), dtype=np.int8)
    wetness = np.zeros((n, remaining), dtype=float)
    noise = rng.normal(0.0, belief.noise_sd_s, size=(n, remaining))
    return {"status": status, "wetness": wetness, "noise": noise}
