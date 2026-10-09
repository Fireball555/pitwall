"""STUB (BR0) — owner SIM replaces in SIM1/SIM4. Working now: linear-wear lap time + step/observe."""
from __future__ import annotations

import numpy as np

from pitwall.types import (
    GREEN,
    SC,
    VSC,
    Action,
    CarState,
    CompoundParams,
    Observation,
    Scenario,
    TrackParams,
    TyreSet,
    COMPOUNDS,
    DRY,
    LapRecord,
)


def lap_time(cid, age, fuel, wet, status, noise, P: TrackParams):
    """Numpy-broadcastable lap time, in seconds.

    Green = base + offset[c] + deg[c] * age + fuel_s_per_kg * fuel + noise.
    SC/VSC = base * factor. `wet` is accepted but not yet penalised (SIM1 adds it).
    """
    cid_arr = np.asarray(cid)
    age_arr = np.asarray(age)
    fuel_arr = np.asarray(fuel)
    status_arr = np.asarray(status)
    noise_arr = np.asarray(noise)

    offsets = np.array([P.compounds[c].offset_s for c in COMPOUNDS])
    degs = np.array([P.compounds[c].deg_s_per_lap for c in COMPOUNDS])

    offset = offsets[cid_arr]
    deg = degs[cid_arr]

    green = P.base_lap_s + offset + deg * age_arr + P.fuel_s_per_kg * fuel_arr + noise_arr
    sc_time = P.base_lap_s * P.sc_lap_factor + np.zeros_like(green)
    vsc_time = P.base_lap_s * P.vsc_lap_factor + np.zeros_like(green)

    out = np.where(status_arr == SC, sc_time, np.where(status_arr == VSC, vsc_time, green))
    if out.ndim == 0:
        return float(out)
    return out


def observe(car: CarState, scn: Scenario) -> Observation:
    """Everything a fair strategy may see after `car.lap`."""
    i = car.lap
    laps_total = scn.laps
    remaining = laps_total - i
    if i < laps_total:
        status = int(scn.status[i])
        wetness = float(scn.wetness[i])
        rain_forecast = scn.forecast[i, i:laps_total].copy() if scn.forecast.size else np.zeros(remaining)
    else:
        status = GREEN
        wetness = 0.0
        rain_forecast = np.zeros(0)
    return Observation(lap=i, laps_total=laps_total, status=status, wetness=wetness, rain_forecast=rain_forecast)


def step(car: CarState, action: Action, scn: Scenario, P_true: TrackParams) -> tuple[CarState, LapRecord]:
    """Apply `action` and drive one lap with the TRUE params. Returns (new CarState, LapRecord)."""
    i = car.lap
    pit_loss = 0.0
    fuel_added = 0.0
    pitted = False

    if i == 0 and (not action.pit or action.set_id is None):
        raise ValueError("STAY at lap 0 is illegal: Action(pit=True, set_id=...) picks the start set.")

    if action.pit:
        if i == 0:
            set_idx = next((k for k, s in enumerate(car.inventory) if s.set_id == action.set_id), None)
            if set_idx is None:
                raise ValueError(f"set_id {action.set_id} not in inventory")
            tyre_set = car.inventory.pop(set_idx)
            car.compound = tyre_set.compound
            car.tyre_age = tyre_set.age_laps
            car.compounds_used = set(car.compounds_used) | {tyre_set.compound}
        else:
            set_idx = next((k for k, s in enumerate(car.inventory) if s.set_id == action.set_id), None)
            if set_idx is None:
                raise ValueError(f"set_id {action.set_id} not in inventory")
            status_now = int(scn.status[min(i, scn.laps - 1)])
            pit_loss = P_true.pit_loss_sc_s if status_now in (SC, VSC) else P_true.pit_loss_s
            tyre_set = car.inventory.pop(set_idx)
            car.compound = tyre_set.compound
            car.tyre_age = tyre_set.age_laps
            car.compounds_used = set(car.compounds_used) | {tyre_set.compound}
            car.pit_stops += 1
            pitted = True

    if P_true.mode == "endurance" and action.fuel_kg:
        fuel_added = min(action.fuel_kg, P_true.tank_kg - car.fuel_kg)
        car.fuel_kg += fuel_added

    if i >= scn.laps:
        record = LapRecord(
            car=car.name, lap=i, lap_time_s=0.0, total_time_s=car.total_time_s,
            compound=car.compound, tyre_age=car.tyre_age, fuel_kg=car.fuel_kg,
            fuel_added_kg=fuel_added, pitted=pitted, status=GREEN, wetness=0.0,
            reason="", expected_json="",
        )
        return car, record

    cid = COMPOUNDS.index(car.compound)
    status = int(scn.status[i])
    wetness = float(scn.wetness[i])
    noise = float(scn.noise[i])

    lt = lap_time(cid, car.tyre_age, car.fuel_kg, wetness, status, noise, P_true)
    lt += pit_loss

    car.lap = i + 1
    car.total_time_s += lt
    car.tyre_age += 1
    car.fuel_kg = max(0.0, car.fuel_kg - P_true.fuel_burn_kg_per_lap)

    if P_true.mode == "f1" and car.lap == scn.laps:
        if wetness <= 0.2 and len(set(car.compounds_used) & set(DRY)) < 2:
            car.dnf = True

    record = LapRecord(
        car=car.name, lap=car.lap, lap_time_s=lt, total_time_s=car.total_time_s,
        compound=car.compound, tyre_age=car.tyre_age, fuel_kg=car.fuel_kg,
        fuel_added_kg=fuel_added, pitted=pitted, status=status, wetness=wetness,
        reason="", expected_json="",
    )
    return car, record
