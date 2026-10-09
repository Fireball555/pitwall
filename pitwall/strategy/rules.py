"""The 'simple rules' car (orange) and the shared pit-stop helpers. Owner: Smaran (BR).

The rollout strategist re-implements exactly these rules in numpy (rollout.py) for its imagined
futures, so both read the same RULES numbers. Change a threshold here and both follow.
"""
from __future__ import annotations

from pitwall.core import (COMPOUNDS, DRY_IDS, HARD, INTER, MEDIUM, SOFT, STAY, WET, Action, CarState,
                          Decision, Observation, TrackParams, freshest)

RULES = {
    "wear_frac": 0.8,          # pit when tyre age reaches 80% of the compound's cliff lap
    "hard_if_left": 25,        # laps left above which we fit HARD
    "medium_if_left": 12,      # laps left above which we fit MEDIUM (else SOFT)
    "inter_at": 0.35,          # wetness that calls for INTER
    "wet_at": 0.75,            # wetness that calls for full WET
    "slick_at": 0.25,          # wetness below which we go back to slicks
    "two_compound_by": 8,      # laps left by which the 2nd dry compound must be fitted
    "fuel_margin_laps": 1.5,   # endurance: refuel when fuel lasts fewer laps than this
}


def wanted_compound(wet: float, cid: int) -> int | None:
    """Compound the weather demands, or None if the current tyre is fine for the weather."""
    if wet >= RULES["wet_at"]:
        return WET if cid != WET else None
    if wet >= RULES["inter_at"]:
        return INTER if cid not in (INTER, WET) else None
    if cid in (INTER, WET) and wet < RULES["slick_at"]:
        return -1  # any dry compound
    return None


def dry_choice(laps_left: int, used_dry: set[int], inventory) -> int:
    """Dry compound for a new stint; prefers one not used yet if the 2-compound rule is still open."""
    if laps_left > RULES["hard_if_left"]:
        order = [HARD, MEDIUM, SOFT]
    elif laps_left > RULES["medium_if_left"]:
        order = [MEDIUM, HARD, SOFT]
    else:
        order = [SOFT, MEDIUM, HARD]
    if len(used_dry) < 2:
        order = [c for c in order if c not in used_dry] + [c for c in order if c in used_dry]
    for c in order:
        if freshest(inventory, c) is not None:
            return c
    return order[0]


def fuel_to_add(P: TrackParams, car: CarState, laps_left: int) -> float:
    """Endurance: enough to finish if it fits in the tank, otherwise a full tank."""
    if P.mode != "endurance":
        return 0.0
    need = laps_left * P.fuel_burn + 0.5 - car.fuel
    return float(max(0.0, min(P.tank - car.fuel, need)))


def pit_to(P: TrackParams, car: CarState, cid: int, laps_left: int, reason: str) -> Decision:
    tyre = freshest(car.inventory, cid)
    if tyre is None:  # fall back to any set of a similar type
        pool = DRY_IDS if cid in DRY_IDS else (INTER, WET)
        tyre = min((s for s in car.inventory if s.cid in pool), key=lambda s: s.age, default=None)
    if tyre is None:
        return Decision(STAY, "wanted to pit but no tyres left")
    return Decision(Action(True, tyre.set_id, fuel_to_add(P, car, laps_left)),
                    f"{reason}: pit for {COMPOUNDS[tyre.cid]}")


class RulesStrategy:
    name = "rules"

    def reset(self, belief: TrackParams, car: CarState) -> None:
        self.P = belief

    def decide(self, car: CarState, obs: Observation) -> Decision:
        P, left = self.P, obs.laps - obs.lap
        if obs.lap == 0:
            start = wanted_compound(obs.wetness, MEDIUM)
            cid = MEDIUM if start in (None, -1) else start
            return pit_to(P, car, cid, left, "Start")
        if left <= 1:
            return Decision(STAY)
        w = wanted_compound(obs.wetness, car.cid)
        if w is not None:
            cid = dry_choice(left, car.used_dry, car.inventory) if w == -1 else w
            return pit_to(P, car, cid, left, f"Lap {obs.lap}: wetness {obs.wetness:.2f}")
        if P.mode == "endurance" and car.fuel < P.fuel_burn * RULES["fuel_margin_laps"]:
            return pit_to(P, car, car.cid, left, f"Lap {obs.lap}: low fuel")
        if car.cid in DRY_IDS:
            if car.age >= RULES["wear_frac"] * P.cliff_lap[car.cid] and left > 5:
                return pit_to(P, car, dry_choice(left, car.used_dry, car.inventory), left,
                              f"Lap {obs.lap}: tyres worn ({car.age} laps)")
            other_dry = any(s.cid in DRY_IDS and s.cid not in car.used_dry for s in car.inventory)
            if not obs.race_was_wet and len(car.used_dry) < 2 and left <= RULES["two_compound_by"] and other_dry:
                return pit_to(P, car, dry_choice(left, car.used_dry, car.inventory), left,
                              f"Lap {obs.lap}: second compound required")
        return Decision(STAY)
