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


def _forced_rain(laps: int, start: int, peak: float, seed: int, level: float = 0.0) -> np.ndarray:
    """Rain that starts exactly at lap index `start` (for the app's "rain now" button). `level` is how
    wet the track already is, so pressing it during rain never makes the track drier."""
    hold = int(np.random.default_rng(seed + 7).integers(10, 21))
    wet, top = np.zeros(laps), max(peak, level)
    for k in range(start, laps):
        level = min(top, level + 2 * RAIN_RISE) if k < start + hold else max(0.0, level - RAIN_DRY)
        wet[k] = level
    return wet


def _forced_dry(wet: np.ndarray, start: int) -> np.ndarray:
    """Rain stops at lap index `start`; the track then dries over a few laps."""
    out, level = wet.copy(), (wet[start - 1] if start > 0 else 0.0)
    for k in range(start, len(wet)):
        level = max(0.0, level - 2 * RAIN_DRY)
        out[k] = level
    return out


def sample_scenario(P: TrackParams, seed: int, rain_prob: float | None = None, sc_mult: float = 1.0,
                    rain_start: int | None = None, rain_peak: float = 0.6, sc_start: int | None = None,
                    dry_start: int | None = None) -> Scenario:
    """One reproducible race world (same seed -> same race).

    rain_start / dry_start / sc_start (lap index) are the app's "rain now", "dry now" and "safety car
    now" buttons. They are surprises: the weather radar only shows them from that lap on, so nothing
    the fair strategists saw before the button was pressed changes. Everything else stays the same."""
    rng = np.random.default_rng(seed)
    status = _safety_cars(P, P.laps, rng, sc_mult)
    wet = _rain(P, P.laps, rng, P.p_rain if rain_prob is None else rain_prob)
    noise = rng.normal(0.0, P.noise_sd, P.laps)
    planned = wet
    if rain_start is not None:
        s0 = max(1, rain_start)
        wet = np.maximum(np.where(np.arange(P.laps) < s0, wet, 0.0),
                         _forced_rain(P.laps, s0, rain_peak, seed, float(wet[min(s0, P.laps) - 1])))
    if dry_start is not None and 1 <= dry_start < P.laps:
        wet = _forced_dry(wet, dry_start)
    if sc_start is not None and 1 <= sc_start < P.laps - 1:
        status = status.copy()
        status[sc_start:sc_start + 4] = SC
    fc_rng = np.random.Generator(np.random.PCG64())
    fc_rng.bit_generator.state = rng.bit_generator.state   # same radar noise for both versions
    fc = _forecast(P, wet, rng)
    first_change = min([k for k in (rain_start, dry_start) if k is not None], default=None)
    if first_change is not None:
        before = _forecast(P, planned, fc_rng)             # what the radar showed before the surprise
        fc[:first_change] = before[:first_change]
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
