"""STUB (BR0) — owner BR replaces in BR2. Working now: wraps RulesStrategy."""
from __future__ import annotations

from pitwall.strategy.rules import RulesStrategy
from pitwall.types import CarState, Decision, Observation, TrackParams


class RolloutStrategy:
    """STUB (BR0) — owner BR replaces in BR2 with the 200-futures Monte Carlo rollout."""

    name = "rollout"

    def __init__(self) -> None:
        self._inner = RulesStrategy()

    def reset(self, belief: TrackParams, start: CarState) -> None:
        self._inner.reset(belief, start)

    def decide(self, car: CarState, obs: Observation) -> Decision:
        return self._inner.decide(car, obs)
