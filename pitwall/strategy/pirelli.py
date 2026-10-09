"""STUB (BR0) — owner DAT replaces in DAT3/DAT9. Working now: follows data/pirelli/{track}.json."""
from __future__ import annotations

import json
from pathlib import Path

from pitwall.types import Action, CarState, Decision, Observation, TrackParams

PIRELLI_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pirelli"


class PirelliStrategy:
    """STUB (BR0) — owner DAT replaces in DAT3. Follows the pre-race plan, ignores safety cars."""

    name = "pirelli"

    def __init__(self, track: str = "mock") -> None:
        self.track = track
        self._plan: dict | None = None
        self._stop_idx = 0

    def reset(self, belief: TrackParams, start: CarState) -> None:
        path = PIRELLI_DIR / f"{self.track}.json"
        if not path.exists():
            path = PIRELLI_DIR / "mock.json"
        self._plan = json.loads(path.read_text())
        self._stop_idx = 0

    def decide(self, car: CarState, obs: Observation) -> Decision:
        plan = self._plan or {}
        if obs.lap == 0:
            start_compound = plan.get("start", "MEDIUM")
            set_id = self._freshest(car, start_compound)
            return Decision(action=Action(pit=True, set_id=set_id), reason=f"Pre-race plan: start on {start_compound}")

        stops = plan.get("stops", [])
        if self._stop_idx < len(stops) and obs.lap >= stops[self._stop_idx]["lap"]:
            compound = stops[self._stop_idx]["compound"]
            set_id = self._freshest(car, compound)
            self._stop_idx += 1
            if set_id is not None:
                return Decision(action=Action(pit=True, set_id=set_id), reason=f"Lap {obs.lap}: plan says pit for {compound}")

        return Decision(action=Action(pit=False), reason="Following the pre-race plan")

    @staticmethod
    def _freshest(car: CarState, compound: str) -> int | None:
        candidates = [s for s in car.inventory if s.compound == compound]
        if not candidates:
            return None
        return min(candidates, key=lambda s: s.age_laps).set_id
