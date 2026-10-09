# pitwall/types.py — THE CONTRACT (Python 3.12). Do not edit without a 'contract' PR.
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Protocol
import numpy as np

COMPOUNDS: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")  # index = compound id
DRY = ("SOFT", "MEDIUM", "HARD")
GREEN, VSC, SC = 0, 1, 2   # track status codes
Mode = Literal["f1", "endurance"]

@dataclass(frozen=True)
class CompoundParams:
    offset_s: float            # pace vs fresh MEDIUM (SOFT negative)
    deg_s_per_lap: float       # linear wear, s lost per lap of tyre age
    cliff_lap: int             # tyre age where the cliff starts
    cliff_s_per_lap2: float    # quadratic loss after the cliff
    warmup_s: float            # extra time on the first lap of a set
    wet_penalty_s: tuple[float, float, float]  # penalty at wetness 0.0, 0.5, 1.0 (linear between)

@dataclass(frozen=True)
class TrackParams:
    track: str                 # 'bahrain' | 'monza' | 'zandvoort' | 'singapore' | 'mock'
    laps: int
    base_lap_s: float          # dry, fresh MEDIUM, empty tank
    compounds: dict[str, CompoundParams]
    fuel_start_kg: float       # F1 mode: 110.0 (2023 max race fuel)
    fuel_burn_kg_per_lap: float
    fuel_s_per_kg: float       # fitted; sanity range 0.02-0.04
    pit_loss_s: float          # green-flag pit loss (tyres only)
    pit_loss_sc_s: float       # pit loss under SC/VSC
    sc_lap_factor: float       # SC lap time / green lap time
    vsc_lap_factor: float
    p_sc_per_lap: float
    p_vsc_per_lap: float
    sc_len_laps: tuple[int, int]
    p_rain_race: float
    noise_sd_s: float
    allocation: dict[str, int] # sets per compound at weekend start
    mode: Mode = "f1"
    tank_kg: float = 110.0     # endurance mode: assumed smaller tank
    refuel_kg_per_s: float = 9.0  # endurance mode: assumed, ~2009-era F1 rigs

@dataclass(frozen=True)
class Scenario:
    """One random race world. All four cars race the SAME scenario."""
    track: str
    seed: int
    laps: int
    status: np.ndarray         # (laps,) int8 GREEN/VSC/SC per lap
    wetness: np.ndarray        # (laps,) float 0..1
    noise: np.ndarray          # (laps,) seconds, identical for every car
    forecast: np.ndarray       # (laps, laps): forecast[l, k] = P(rain on lap k) known after lap l
    tags: tuple[str, ...]      # subset of ('dry', 'wet', 'chaotic')

@dataclass(frozen=True)
class TyreSet:
    set_id: int
    compound: str
    age_laps: int              # laps used before the race

@dataclass
class CarState:
    name: str                  # 'pirelli' | 'rules' | 'rollout' | 'oracle'
    lap: int                   # laps completed (0 = on the grid)
    total_time_s: float
    compound: str              # '' before the start-tyre choice
    tyre_age: int
    fuel_kg: float
    inventory: list[TyreSet]   # sets still available (not the fitted one)
    compounds_used: set[str]
    pit_stops: int = 0
    dnf: bool = False

@dataclass(frozen=True)
class Action:
    pit: bool
    set_id: int | None = None  # required when pit=True (lap 0: the start set)
    fuel_kg: float = 0.0       # fuel to add; endurance mode only

STAY = Action(pit=False)

@dataclass(frozen=True)
class Observation:
    """Everything a FAIR strategy may see after lap `lap`. No future truth, no true params."""
    lap: int
    laps_total: int
    status: int                # status of the lap about to be driven
    wetness: float
    rain_forecast: np.ndarray  # (laps_total - lap,) P(rain) per remaining lap

@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str                # one line for the live feed
    expected_s: dict[str, float] = field(default_factory=dict)  # option label -> expected finish time

class Strategy(Protocol):
    name: str
    def reset(self, belief: TrackParams, start: CarState) -> None: ...  # belief = the numbers it PLANS with
    def decide(self, car: CarState, obs: Observation) -> Decision: ...

@dataclass(frozen=True)
class LapRecord:
    car: str; lap: int; lap_time_s: float; total_time_s: float
    compound: str; tyre_age: int; fuel_kg: float; fuel_added_kg: float; pitted: bool
    status: int; wetness: float; reason: str
    expected_json: str         # json.dumps(Decision.expected_s), '' when no decision
