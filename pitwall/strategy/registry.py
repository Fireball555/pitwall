"""Builds the four cars for a race. Owner: Smaran (BR)."""
from __future__ import annotations

from pitwall.core import TrackParams
from pitwall.engine.scenario import Scenario
from pitwall.strategy.pirelli import PirelliStrategy
from pitwall.strategy.rollout import Oracle, RolloutStrategy
from pitwall.strategy.rules import RulesStrategy


def make_cars(P: TrackParams, scn: Scenario, n_futures: int = 100) -> list:
    """Pirelli plan, simple rules, our rollout strategist, and the Oracle (knows the future)."""
    return [PirelliStrategy(), RulesStrategy(), RolloutStrategy(n=n_futures, seed=scn.seed), Oracle(scn)]
