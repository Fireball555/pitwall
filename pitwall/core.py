"""Shared types used by every module. Owner: Smaran (BR). Ask him before changing anything here.

Units everywhere: seconds, laps, kg. Wetness is 0 (dry) .. 1 (soaking).
Compounds are integer ids so numpy can vectorise over them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

COMPOUNDS: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD", "INTER", "WET")
SOFT, MEDIUM, HARD, INTER, WET = range(5)
DRY_IDS = (SOFT, MEDIUM, HARD)
GREEN, VSC, SC = 0, 1, 2
STATUS_NAMES = ("GREEN", "VSC", "SC")
CAR_NAMES = ("pirelli", "rules", "rollout", "oracle")


@dataclass(frozen=True, eq=False)
class TrackParams:
    """Everything the engine needs to know about one track. Built by pitwall.data.params.load_track()."""
    name: str
    laps: int
    base_lap: float               # dry lap on a fresh MEDIUM with an empty tank (s)
    offset: np.ndarray            # (5,) pace vs MEDIUM per compound (s)
    deg: np.ndarray               # (5,) seconds lost per lap of tyre age
    cliff_lap: np.ndarray         # (5,) tyre age where the cliff starts
    cliff_coef: np.ndarray        # (5,) quadratic loss after the cliff (s / lap^2)
    warmup: np.ndarray            # (5,) extra time on the first lap of a set (s)
    wet_pen: np.ndarray           # (5, 3) penalty at wetness 0, 0.5, 1.0 (s)
    fuel_start: float             # kg at the start (F1: 110)
    fuel_burn: float              # kg per lap
    fuel_effect: float            # s per kg
    pit_loss: float               # green-flag pit stop cost (s)
    pit_loss_sc: float            # pit stop cost under SC/VSC (s)
    sc_factor: float              # SC lap time / base lap
    vsc_factor: float
    p_sc: float                   # chance a green lap starts a safety car
    p_vsc: float
    sc_len: tuple[int, int]       # min, max laps of a SC/VSC period
    p_rain: float                 # chance that a race has rain at all
    noise_sd: float               # lap-to-lap randomness (s)
    allocation: dict[str, int] = field(default_factory=dict)
    mode: str = "f1"              # "f1" or "endurance"
    tank: float = 110.0           # endurance: tank size (kg)
    refuel_rate: float = 9.0      # endurance: kg per second at the pump
    sources: dict[str, str] = field(default_factory=dict)  # where each number came from


@dataclass(frozen=True)
class TyreSet:
    set_id: int
    cid: int                      # compound id
    age: int                      # laps used before the race


@dataclass
class CarState:
    name: str
    lap: int = 0                  # laps completed (0 = on the grid)
    total: float = 0.0            # race time so far (s)
    cid: int = -1                 # fitted compound (-1 before the start)
    age: int = 0                  # laps on the fitted set
    fuel: float = 0.0
    inventory: list[TyreSet] = field(default_factory=list)
    used_dry: set[int] = field(default_factory=set)
    stops: int = 0
    dnf: bool = False
    dnf_reason: str = ""


@dataclass(frozen=True)
class Action:
    pit: bool
    set_id: int | None = None     # which set to fit (lap 0: the start set)
    fuel_add: float = 0.0         # endurance mode only (kg)


STAY = Action(pit=False)


@dataclass(frozen=True)
class Observation:
    """All a fair strategy may see after `lap` laps. No future truth."""
    lap: int
    laps: int
    status: int                   # status of the lap about to be driven
    wetness: float                # current track wetness
    rain_forecast: np.ndarray     # (laps - lap,) chance of rain on each remaining lap
    race_was_wet: bool            # any lap so far with wetness > 0.2


@dataclass
class Decision:
    action: Action
    reason: str = ""
    options: dict[str, float] = field(default_factory=dict)  # option label -> expected finish time (s)
    samples: dict[str, list[float]] = field(default_factory=dict)  # option -> some imagined finish times (s)


def freshest(inventory: list[TyreSet], cid: int) -> TyreSet | None:
    """Least-used set of a compound, or None."""
    sets = [s for s in inventory if s.cid == cid]
    return min(sets, key=lambda s: s.age) if sets else None
