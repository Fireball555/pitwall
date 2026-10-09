"""STUB (BR0) — owner BR replaces in BR3. Working now: wraps RulesStrategy."""
from __future__ import annotations

from pitwall.strategy.rules import RulesStrategy
from pitwall.types import CarState, Decision, Observation, Scenario, TrackParams


class Oracle:
    """STUB (BR0) — owner BR replaces in BR3. "Knows the future": sees the true Scenario."""

    name = "oracle"

    def __init__(self, scn: Scenario) -> None:
        self.scn = scn
        self._inner = RulesStrategy()

    def reset(self, belief: TrackParams, start: CarState) -> None:
        self._inner.reset(belief, start)

    def decide(self, car: CarState, obs: Observation) -> Decision:
        return self._inner.decide(car, obs)
