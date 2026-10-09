"""STUB (BR0) — owner DAT replaces in DAT2. Working now: MEDIUM -> HARD at half distance."""
from __future__ import annotations

from pitwall.types import Action, CarState, Decision, Observation, TrackParams


class RulesStrategy:
    """STUB (BR0) — owner DAT replaces in DAT2. Simple thresholds, no numpy."""

    name = "rules"

    def __init__(self) -> None:
        self._belief: TrackParams | None = None
        self._pitted_at_half = False

    def reset(self, belief: TrackParams, start: CarState) -> None:
        self._belief = belief
        self._pitted_at_half = False

    def decide(self, car: CarState, obs: Observation) -> Decision:
        if obs.lap == 0:
            set_id = self._freshest(car, "MEDIUM")
            return Decision(action=Action(pit=True, set_id=set_id), reason="Start on the freshest MEDIUM")

        half = obs.laps_total // 2
        if not self._pitted_at_half and obs.lap >= half:
            set_id = self._freshest(car, "HARD")
            if set_id is not None:
                self._pitted_at_half = True
                return Decision(action=Action(pit=True, set_id=set_id), reason=f"Lap {obs.lap}: one stop, onto HARD")

        return Decision(action=Action(pit=False), reason="Stay out")

    @staticmethod
    def _freshest(car: CarState, compound: str) -> int | None:
        candidates = [s for s in car.inventory if s.compound == compound]
        if not candidates:
            return None
        return min(candidates, key=lambda s: s.age_laps).set_id
