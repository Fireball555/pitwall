"""The 'Pirelli plan' car (purple): follows the published pre-race plan. Owner: Smaran (BR).

It ignores safety cars. It only reacts to rain late (wetness >= 0.5), like a cautious team, and it
puts off a planned stop while the track is wet, so it is a fair baseline rather than a straw man.
"""
from __future__ import annotations

from pitwall.core import COMPOUNDS, DRY_IDS, INTER, STAY, CarState, Decision, Observation, TrackParams
from pitwall.data.params import load_pirelli_plan
from pitwall.strategy.rules import RULES, dry_choice, pit_to


class PirelliStrategy:
    name = "pirelli"

    def __init__(self, plan: dict | None = None):
        self.plan = plan

    def reset(self, belief: TrackParams, car: CarState) -> None:
        self.P = belief
        plan = self.plan or load_pirelli_plan(belief.name)
        self.start = COMPOUNDS.index(plan["start"])
        self.stops = {s["lap"]: COMPOUNDS.index(s["compound"]) for s in plan["stops"]}
        self.pending = None  # a planned stop put off because the track was wet

    def decide(self, car: CarState, obs: Observation) -> Decision:
        P, left = self.P, obs.laps - obs.lap
        if obs.lap == 0:
            return pit_to(P, car, self.start, left, "Start (Pirelli plan)")
        if left <= 1:
            return Decision(STAY)
        if obs.wetness >= 0.5 and car.cid in DRY_IDS:
            return pit_to(P, car, INTER, left, f"Lap {obs.lap}: heavy rain, finally pitting")
        if car.cid not in DRY_IDS and obs.wetness < RULES["slick_at"]:
            self.pending = None  # fresh slicks now, so the planned stop is covered
            return pit_to(P, car, dry_choice(left, car.used_dry, car.inventory), left, f"Lap {obs.lap}: back to slicks")
        if obs.lap in self.stops or self.pending is not None:
            target = self.stops.get(obs.lap, self.pending)
            if obs.wetness >= RULES["slick_at"]:  # no team fits fresh slicks on a wet track: wait
                self.pending = target
                return Decision(STAY)
            self.pending = None
            return pit_to(P, car, target, left, f"Lap {obs.lap}: planned stop")
        if P.mode == "endurance" and car.fuel < P.fuel_burn * RULES["fuel_margin_laps"]:
            return pit_to(P, car, car.cid, left, f"Lap {obs.lap}: low fuel")
        if (P.mode == "f1" and not obs.race_was_wet and len(car.used_dry) < 2
                and left <= RULES["two_compound_by"] and car.cid in DRY_IDS):
            return pit_to(P, car, dry_choice(left, car.used_dry, car.inventory), left, f"Lap {obs.lap}: second compound required")
        return Decision(STAY)
