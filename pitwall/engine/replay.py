"""Replay a real race with our strategist in place of one real driver. Owner: Ashwin (SIM).

The other 19 cars are recordings: they drive exactly their real lap times. Our car is simulated
with the track numbers plus the replaced driver's pace, and decides its own pit stops.
Safety cars and rain happen when they really did, but the strategist only sees a forecast.

Traffic rule (assumed): within 1.0 s of the car ahead and not much faster -> stuck behind it,
with a chance to pass that grows with the pace difference. Under a safety car the gap closes up.

Sanity check: replaying the real driver's OWN pit stops should finish near his real position.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.core import COMPOUNDS, INTER, SC, STATUS_NAMES, STAY, WET, Action, CarState, Decision, TyreSet
from pitwall.data.params import load_track
from pitwall.data.realrace import compound_id, load_real
from pitwall.engine.race import observe, step
from pitwall.engine.scenario import Scenario, _forecast

RESULTS = Path(__file__).resolve().parents[2] / "results"
STUCK_GAP, STUCK_PACE, HOLD = 1.0, 0.8, 0.2


class RealStrategy:
    """Copies the real driver's stops (used for the sanity check)."""
    name = "real"

    def __init__(self, real_driver_laps: pd.DataFrame):
        d = real_driver_laps.sort_values("lap")
        self.start = compound_id(d.iloc[0]["compound"])
        self.stops = {int(r.lap) - 1: compound_id(r.compound) for r in d.itertuples() if r.pit_out and r.lap > 1}

    def reset(self, belief, car):
        self.P = belief

    def decide(self, car: CarState, obs) -> Decision:
        want = self.start if obs.lap == 0 else self.stops.get(obs.lap)
        if want is None:
            return Decision(STAY)
        sets = [s for s in car.inventory if s.cid == want] or car.inventory
        s = min(sets, key=lambda t: t.age)
        return Decision(Action(True, s.set_id), f"Lap {obs.lap}: real stop for {COMPOUNDS[want]}")


def real_scenario(df: pd.DataFrame, track: str, laps: int) -> Scenario:
    lead = df.sort_values(["lap", "position"]).groupby("lap").first()
    status = lead["status"].reindex(range(1, laps + 1)).fillna(0).to_numpy(np.int8)
    on_rain = df.assign(r=df["compound"].isin(["INTER", "WET"])).groupby("lap")["r"].mean()
    wet = np.clip(on_rain.reindex(range(1, laps + 1)).fillna(0).to_numpy(float), 0, 1)
    P = load_track(track)
    fc = _forecast(P, wet, np.random.default_rng(0))
    tags = ("wet",) if wet.max() > 0.2 else ("dry",)
    return Scenario(track, 0, laps, status, wet, np.zeros(laps), fc, tags)


def field_correction(df: pd.DataFrame, driver: str, P, scn: Scenario) -> np.ndarray:
    """Per-lap gap between what the real field did and what our model predicts for a typical car.

    Adding it to our car's lap anchors the simulation to reality (track evolution, weather and safety
    cars as they really affected lap times), so only the DIFFERENCE our strategy makes is modelled.
    """
    from pitwall.engine.lap import lap_time
    o = df[(df["driver"] != driver) & (~df["pit_in"]) & (~df["pit_out"])]
    corr = np.zeros(scn.laps)
    for k in range(1, scn.laps):
        g = o[o["lap"] == k + 1]
        if len(g) < 3:
            continue
        cid = compound_id(g["compound"].mode().iloc[0])
        age = float(g["tyre_life"].median())
        fuel = P.fuel_start - P.fuel_burn * k
        model = float(lap_time(P, cid, age, fuel, scn.wetness[k], scn.status[k], 0.0))
        corr[k] = float(g["lap_time"].median()) - model
    return corr


def replay(track: str, driver: str, strategy, save: bool = True) -> dict:
    df, is_real = load_real(track)
    laps = int(df["lap"].max())
    me = df[df["driver"] == driver].sort_values("lap")
    others = df[df["driver"] != driver]
    elapsed = others.pivot(index="lap", columns="driver", values="elapsed")      # recordings
    lap_times = others.pivot(index="lap", columns="driver", values="lap_time")
    P = load_track(track)
    clean = df[(df["status"] == 0) & (~df["pit_in"]) & (~df["pit_out"]) & (df["lap"] > 1)]
    field_med = clean["lap_time"].median()
    drv_med = clean[clean["driver"] == driver]["lap_time"].median()
    Pd = replace(P, base_lap=P.base_lap + float(drv_med - field_med), laps=laps)
    scn = real_scenario(df, track, laps)
    corr = field_correction(df, driver, P, scn)
    start_cid = compound_id(me.iloc[0]["compound"])
    inv = [TyreSet(i, c, a) for i, (c, a) in enumerate([(start_cid, 0), (0, 0), (0, 3), (1, 0), (1, 0), (2, 0), (2, 0), (INTER, 0), (INTER, 0), (WET, 0)])]
    car = CarState(name="OURS", fuel=Pd.fuel_start, inventory=inv)
    strategy.reset(Pd, car)
    rng = np.random.default_rng(1)
    ours_rows, order_rows = [], []
    E = 0.0
    for lap in range(laps):
        obs = observe(scn, lap)
        dec = strategy.decide(car, obs) if lap > 0 else Decision(Action(True, 0), "Start on the real driver's tyre")
        prev = car.total
        rec = step(car, dec, scn, Pd)
        my_lap = car.total - prev + corr[lap]      # anchor to what the real field did on this lap
        if lap == 0:
            my_lap = float(me.iloc[0]["elapsed"])   # copy the real start
        E += my_lap
        L = lap + 1
        if L in elapsed.index:
            row = elapsed.loc[L].dropna()
            ahead = row[row < E]
            if len(ahead):
                a_drv = ahead.idxmax()
                gap = E - ahead.max()
                their = float(lap_times.loc[L, a_drv])
                if scn.status[lap] == SC and gap > 0.8:
                    E = ahead.max() + 0.8                       # field bunches up behind the safety car
                elif gap < STUCK_GAP and their - my_lap < STUCK_PACE:
                    p_pass = float(np.clip((their - my_lap - 0.3) / 1.0, 0, 0.9))
                    if rng.random() >= p_pass:
                        E = max(E, ahead.max() + HOLD)          # stuck behind
            car.total = E
            order = sorted(list(row.items()) + [("OURS", E)], key=lambda kv: kv[1])
            order_rows.append({"lap": L, "order": [k for k, _ in order], "elapsed": {k: round(v, 3) for k, v in order}})
        ours_rows.append({"lap": L, "compound": rec["compound"], "tyre_age": rec["tyre_age"],
                          "pitted": bool(rec["pitted"]), "reason": dec.reason,
                          "options": {k: round(float(v), 2) for k, v in (dec.options or {}).items()},
                          **({"samples": dec.samples} if dec.reason and dec.samples else {})})
    final_order = order_rows[-1]["order"] if order_rows else []
    out = {
        "track": track, "driver": driver, "is_real_data": is_real, "laps_total": laps,
        "real_grid": int(me.iloc[0]["grid"]), "real_finish_pos": int(me.iloc[-1]["final_pos"]) if me.iloc[-1]["final_pos"] == me.iloc[-1]["final_pos"] else None,
        "our_finish_pos": final_order.index("OURS") + 1 if final_order else None,
        "real_time_s": float(me.iloc[-1]["elapsed"]), "our_time_s": float(E),
        "laps": order_rows, "ours": ours_rows,
        "real_driver": [{"lap": int(r.lap), "compound": r.compound, "pitted": bool(r.pit_out),
                         "position": int(r.position) if r.position == r.position else None} for r in me.itertuples()],
        "strategy": getattr(strategy, "name", "?"),
    }
    out.update(race_extras(df, driver, scn))
    if save:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / f"replay_{track}_{driver}_{out['strategy']}.json").write_text(json.dumps(out))
    return out


def race_extras(df: pd.DataFrame, driver: str, scn: Scenario | None = None) -> dict:
    """What the app needs to draw the real race: flags, weather, the grid, every car's tyres and
    stops, the replaced driver's real progress (the "ghost") and a typical lap time per lap."""
    laps = int(df["lap"].max())
    lead = df.sort_values(["lap", "position"]).groupby("lap").first()
    status = lead["status"].reindex(range(1, laps + 1)).fillna(0).astype(int).tolist()
    on_rain = df.assign(r=df["compound"].isin(["INTER", "WET"])).groupby("lap")["r"].mean()
    wet = on_rain.reindex(range(1, laps + 1)).fillna(0).clip(0, 1).round(3).tolist()
    grid = df.groupby("driver")["grid"].first()
    tyres = df.pivot(index="lap", columns="driver", values="compound").reindex(range(1, laps + 1))
    pits = df[df["pit_out"] & (df["lap"] > 1)].groupby("driver")["lap"].apply(lambda x: sorted(int(v) for v in x))
    me = df[df["driver"] == driver].set_index("lap")["elapsed"].reindex(range(1, laps + 1))
    lap_ref = df[(~df["pit_in"]) & (~df["pit_out"])].groupby("lap")["lap_time"].median().reindex(range(1, laps + 1))
    return {
        "status": [STATUS_NAMES[s] for s in status], "wetness": wet,
        "grid": {d: int(g) for d, g in grid.items() if g == g and g > 0} | {"OURS": int(grid.get(driver, 0) or 0)},
        "tyres": {d: [c if isinstance(c, str) else None for c in tyres[d].tolist()] for d in tyres.columns if d != driver},
        "pits": {d: v for d, v in pits.items() if d != driver},
        "ghost": [None if v != v else round(float(v), 3) for v in me.tolist()],
        "lap_ref": [None if v != v else round(float(v), 3) for v in lap_ref.interpolate().bfill().tolist()],
    }


def replay_with_sanity(track: str, driver: str, n_futures: int = 100) -> dict:
    """Our strategist + the real-strategy sanity check, saved together for the app."""
    from pitwall.strategy.rollout import RolloutStrategy
    df, _ = load_real(track)
    ours = replay(track, driver, RolloutStrategy(n=n_futures, seed=1), save=False)
    sanity = replay(track, driver, RealStrategy(df[df["driver"] == driver]), save=False)
    ours["sanity"] = {"real_strategy_pos": sanity["our_finish_pos"], "real_pos": ours["real_finish_pos"],
                      "real_strategy_time_s": sanity["our_time_s"], "real_time_s": ours["real_time_s"]}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"replay_{track}_{driver}.json").write_text(json.dumps(ours))
    return ours


def midfield_drivers(track: str) -> list[str]:
    df, _ = load_real(track)
    g = df.groupby("driver").agg(grid=("grid", "first"), laps=("lap", "max"))
    full = g[(g["laps"] == df["lap"].max()) & (g["grid"].between(8, 15))]
    return sorted(full.index)


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "bahrain"
    for d in midfield_drivers(t)[:3]:
        r = replay_with_sanity(t, d)
        print(f"{t} {d}: real P{r['real_finish_pos']}  ours P{r['our_finish_pos']}  "
              f"(sanity: real strategy in our sim P{r['sanity']['real_strategy_pos']})")
