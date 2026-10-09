"""STUB (BR0) — owner SIM replaces in SIM5. Working now: runs ghost cars on one scenario."""
from __future__ import annotations

import argparse
import dataclasses
import json

import numpy as np
import pandas as pd

from pitwall.params import load_params
from pitwall.sim.engine import observe, step
from pitwall.sim.inventory import sample_inventory
from pitwall.sim.scenario import sample_scenario
from pitwall.strategy.oracle import Oracle
from pitwall.strategy.pirelli import PirelliStrategy
from pitwall.strategy.rollout import RolloutStrategy
from pitwall.strategy.rules import RulesStrategy
from pitwall.types import CarState, Scenario, Strategy, TrackParams, TyreSet


def run_race(
    scn: Scenario,
    strategies: dict[str, Strategy],
    P_true: TrackParams,
    beliefs: dict[str, TrackParams],
    inventory: list[TyreSet],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Run every strategy as a ghost car on the same scenario. Returns (LapRecord DataFrame, finish times)."""
    records = []
    finish_times: dict[str, float] = {}

    for name, strat in strategies.items():
        belief = beliefs[name]
        car_inventory = [TyreSet(set_id=s.set_id, compound=s.compound, age_laps=s.age_laps) for s in inventory]
        car = CarState(
            name=name, lap=0, total_time_s=0.0, compound="", tyre_age=0,
            fuel_kg=belief.fuel_start_kg, inventory=car_inventory, compounds_used=set(),
        )
        strat.reset(belief, car)

        for _ in range(scn.laps):
            if car.dnf:
                break
            obs = observe(car, scn)
            decision = strat.decide(car, obs)
            car, record = step(car, decision.action, scn, P_true)
            record = dataclasses.replace(
                record, reason=decision.reason, expected_json=json.dumps(decision.expected_s),
            )
            records.append(record)

        finish_times[name] = float("nan") if car.dnf else car.total_time_s

    df = pd.DataFrame([dataclasses.asdict(r) for r in records])
    return df, finish_times


def _demo() -> None:
    P = load_params("mock")
    rng = np.random.default_rng(7)
    scn = sample_scenario(P, seed=7)
    inventory = sample_inventory(P, rng)

    strategies: dict[str, Strategy] = {
        "pirelli": PirelliStrategy(track="mock"),
        "rules": RulesStrategy(),
        "rollout": RolloutStrategy(),
        "oracle": Oracle(scn),
    }
    beliefs = {name: P for name in strategies}

    df, finish_times = run_race(scn, strategies, P, beliefs, inventory)

    print(f"PitWall demo race — track={P.track}, laps={P.laps}, seed={scn.seed}")
    print(f"{'car':<10}{'finish_s':>12}{'pit_stops':>12}")
    for name in strategies:
        finish = finish_times[name]
        stops = int(df[df.car == name]["pitted"].sum())
        print(f"{name:<10}{finish:>12.2f}{stops:>12d}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        _demo()
