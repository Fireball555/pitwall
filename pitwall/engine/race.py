"""Run a race: all cars share one scenario and never block each other ("ghost cars"). Owner: Ashwin (SIM).

Timing rules:
- car.lap = laps completed. Index i = car.lap is the lap about to be driven.
- A decision after lap L applies to lap L+1; a pit stop's cost is added to that lap.
- At lap 0 the decision picks the start tyre (pit=True + set_id), at no time cost.
- Lap times use the TRUE params; each strategy plans with its own BELIEF params.

Run `python -m pitwall.engine.race` for a demo race.
"""
from __future__ import annotations

import json
from copy import deepcopy

import numpy as np
import pandas as pd

from pitwall.core import (COMPOUNDS, DRY_IDS, SC, VSC, Action, CarState, Decision, Observation,
                          TrackParams, TyreSet)
from pitwall.engine.lap import lap_time
from pitwall.engine.scenario import Scenario

REFUEL_OVERLAP_S = 3.0   # the tyre change happens while refuelling


def observe(scn: Scenario, lap: int) -> Observation:
    return Observation(
        lap=lap, laps=scn.laps,
        status=int(scn.status[lap]) if lap < scn.laps else 0,
        wetness=float(scn.wetness[lap - 1]) if lap > 0 else 0.0,
        rain_forecast=scn.forecast[lap, lap:] if lap < scn.laps else np.zeros(0),
        race_was_wet=bool(lap > 0 and scn.wetness[:lap].max() > 0.2),
    )


def pit_cost(P: TrackParams, status: int, fuel_added: float) -> float:
    loss = P.pit_loss_sc if status in (SC, VSC) else P.pit_loss
    if P.mode == "endurance" and fuel_added > 0:
        loss += max(0.0, fuel_added / P.refuel_rate - REFUEL_OVERLAP_S)
    return loss


def step(car: CarState, d: Decision, scn: Scenario, P: TrackParams) -> dict:
    """Apply the decision, drive one lap, return the lap record."""
    i, a = car.lap, d.action
    status, wet, noise = int(scn.status[i]), float(scn.wetness[i]), float(scn.noise[i])
    pit_loss, fuel_added, pitted = 0.0, 0.0, False
    if i == 0 and not a.pit:
        raise ValueError("lap 0 needs a start tyre: Action(pit=True, set_id=...)")
    if a.pit:
        tyre = next((s for s in car.inventory if s.set_id == a.set_id), None)
        if tyre is None:
            raise ValueError(f"{car.name}: set {a.set_id} not available")
        car.inventory = [s for s in car.inventory if s.set_id != a.set_id]
        if P.mode == "endurance" and a.fuel_add > 0:
            fuel_added = max(0.0, min(a.fuel_add, P.tank - car.fuel))
            car.fuel += fuel_added
        if i > 0:
            pit_loss = pit_cost(P, status, fuel_added)
            car.stops += 1
            pitted = True
        car.cid, car.age = tyre.cid, tyre.age
        if tyre.cid in DRY_IDS:
            car.used_dry.add(tyre.cid)
    lt = float(lap_time(P, car.cid, car.age, car.fuel, wet, status, noise))
    car.total += lt + pit_loss
    car.age += 1
    car.fuel -= P.fuel_burn
    car.lap += 1
    if car.fuel < -1e-9 and not car.dnf:
        car.dnf, car.dnf_reason = True, "out of fuel"
    return {
        "car": car.name, "lap": car.lap, "lap_time": lt + pit_loss, "total": car.total,
        "compound": COMPOUNDS[car.cid], "tyre_age": car.age, "fuel": max(car.fuel, 0.0),
        "fuel_added": fuel_added, "pitted": pitted, "status": status, "wetness": wet,
        "reason": d.reason, "options": json.dumps(d.options) if d.options else "",
        "samples": json.dumps(d.samples) if d.samples else "",
    }


def run_race(scn: Scenario, strategies: list, P_true: TrackParams, inventory: list[TyreSet],
             beliefs: dict[str, TrackParams] | None = None) -> tuple[pd.DataFrame, dict[str, float]]:
    """Race every strategy on the same scenario. Returns (lap log, finish time per car; NaN = DNF)."""
    beliefs = beliefs or {}
    cars = []
    for s in strategies:
        car = CarState(name=s.name, fuel=P_true.fuel_start, inventory=deepcopy(inventory))
        s.reset(beliefs.get(s.name, P_true), car)
        cars.append(car)
    rows = []
    for lap in range(scn.laps):
        obs = observe(scn, lap)
        for s, car in zip(strategies, cars):
            if car.dnf:
                continue
            rows.append(step(car, s.decide(car, obs), scn, P_true))
    race_wet = bool(scn.wetness.max() > 0.2)
    finish = {}
    for car in cars:
        if P_true.mode == "f1" and not race_wet and len(car.used_dry) < 2 and not car.dnf:
            car.dnf, car.dnf_reason = True, "disqualified: used only one dry compound"
        finish[car.name] = float("nan") if car.dnf else car.total
    return pd.DataFrame(rows), finish


def _demo() -> None:
    from pitwall.data.params import load_track
    from pitwall.engine.inventory import sample_inventory
    from pitwall.engine.scenario import sample_scenario
    from pitwall.strategy.registry import make_cars

    P = load_track("bahrain")
    scn = sample_scenario(P, seed=7)
    inv = sample_inventory(P, np.random.default_rng(7))
    log, finish = run_race(scn, make_cars(P, scn), P, inv)
    best = min(v for v in finish.values() if v == v)
    print(f"Bahrain, seed 7, conditions: {scn.tags[0]}")
    for name, t in sorted(finish.items(), key=lambda kv: (kv[1] != kv[1], kv[1])):
        print(f"  {name:8s} {'DNF' if t != t else f'{t:9.1f} s  (+{t - best:5.1f})'}")


if __name__ == "__main__":
    _demo()
