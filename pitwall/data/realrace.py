"""Real-race files used by the replay screen. Owner: Dharshini (DAT).

One parquet per race: data/real/<track>_2023.parquet (real, from FastF1) or
data/real/<track>_synthetic.parquet (made by our own engine so the screen works before real data).

Columns, one row per (driver, lap):
  driver, lap, elapsed (s since the start, at the end of the lap), lap_time (s), compound
  (SOFT/MEDIUM/HARD/INTER/WET), tyre_life (laps), pit_in, pit_out (bool), status (0 green, 1 VSC, 2 SC),
  position, grid, final_pos, rainfall (bool)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.core import COMPOUNDS, GREEN, SC, VSC

REAL_DIR = Path(__file__).resolve().parents[2] / "data" / "real"
FASTF1_EVENT = {"bahrain": "Bahrain Grand Prix", "monza": "Italian Grand Prix", "zandvoort": "Dutch Grand Prix",
                "singapore": "Singapore Grand Prix"}
DRIVERS = ["VER", "PER", "HAM", "RUS", "LEC", "SAI", "NOR", "PIA", "ALO", "STR",
           "GAS", "OCO", "ALB", "SAR", "TSU", "RIC", "BOT", "ZHO", "HUL", "MAG"]


def status_code(track_status: str) -> int:
    s = str(track_status)
    if "4" in s:
        return SC
    if "6" in s or "7" in s:
        return VSC
    return GREEN


def real_path(track: str) -> Path:
    real = REAL_DIR / f"{track}_2023.parquet"
    return real if real.exists() else REAL_DIR / f"{track}_synthetic.parquet"


def load_real(track: str) -> tuple[pd.DataFrame, bool]:
    """Returns (laps, is_real). Makes the synthetic file on first use if needed."""
    p = real_path(track)
    if not p.exists():
        make_synthetic(track)
    return pd.read_parquet(p), "_2023" in p.name


def extract_from_fastf1(track: str, year: int = 2023, cache: str = "cache") -> pd.DataFrame:
    """Download one real race with FastF1 and save it in our format. Needs internet the first time."""
    import fastf1  # imported here so the rest of the project works without it

    Path(cache).mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(cache)
    s = fastf1.get_session(year, FASTF1_EVENT[track], "R")
    # FastF1 fuzzy-matches names: in a year without this race it silently returns another one
    # (e.g. "Dutch Grand Prix" 2019 -> Chinese GP). Refuse anything but the exact event.
    if s.event["EventName"] != FASTF1_EVENT[track]:
        raise ValueError(f"no {FASTF1_EVENT[track]} in {year} (FastF1 matched {s.event['EventName']})")
    s.load(laps=True, telemetry=False, weather=True, messages=False)
    laps = s.laps
    t0 = laps["LapStartTime"].min()
    comp = laps["Compound"].fillna("UNKNOWN").astype(str).str.upper().replace({"INTERMEDIATE": "INTER"})
    df = pd.DataFrame({
        "driver": laps["Driver"].astype(str),
        "lap": laps["LapNumber"].astype(int),
        "elapsed": (laps["Time"] - t0).dt.total_seconds(),
        "lap_time": laps["LapTime"].dt.total_seconds(),
        "compound": comp,
        "tyre_life": laps["TyreLife"].astype(float),
        "pit_in": laps["PitInTime"].notna(),
        "pit_out": laps["PitOutTime"].notna(),
        "status": laps["TrackStatus"].fillna("1").map(status_code).astype(int),
        "position": laps["Position"],
    })
    res = s.results[["Abbreviation", "GridPosition", "Position"]].rename(
        columns={"Abbreviation": "driver", "GridPosition": "grid", "Position": "final_pos"})
    df = df.merge(res, on="driver", how="left")
    wx = s.weather_data[["Time", "Rainfall"]].sort_values("Time")
    lap_end = laps[["Driver", "LapNumber", "Time"]].rename(columns={"Driver": "driver", "LapNumber": "lap"})
    rain = pd.merge_asof(lap_end.sort_values("Time"), wx, on="Time", direction="backward")
    df = df.merge(rain[["driver", "lap", "Rainfall"]].rename(columns={"Rainfall": "rainfall"}), on=["driver", "lap"], how="left")
    df["rainfall"] = df["rainfall"].fillna(False).astype(bool)
    REAL_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(REAL_DIR / f"{track}_{year}.parquet", index=False)
    return df


def make_synthetic(track: str, seed: int = 2023) -> pd.DataFrame:
    """A fake 20-car race made with our own engine (clearly labelled synthetic in the app)."""
    from dataclasses import replace

    from pitwall.core import CarState
    from pitwall.data.params import load_track
    from pitwall.engine.inventory import sample_inventory
    from pitwall.engine.race import observe, step
    from pitwall.engine.scenario import sample_scenario
    from pitwall.strategy.rules import RulesStrategy

    P = load_track(track)
    scn = sample_scenario(P, seed, sc_mult=1.5)
    rng = np.random.default_rng(seed)
    pace = np.sort(rng.normal(0, 0.45, len(DRIVERS)))
    rows = []
    for d, (drv, off) in enumerate(zip(DRIVERS, pace)):
        Pd = replace(P, base_lap=P.base_lap + off)
        belief = replace(Pd, cliff_lap=P.cliff_lap * rng.uniform(0.75, 1.1))  # teams judge tyre life differently
        strat = RulesStrategy()
        car = CarState(name=drv, fuel=P.fuel_start, inventory=sample_inventory(P, np.random.default_rng(seed + d)))
        strat.reset(belief, car)
        elapsed = d * 0.3  # grid gaps
        for lap in range(P.laps):
            prev = car.total
            rec = step(car, strat.decide(car, observe(scn, lap)), scn, Pd)
            lt = car.total - prev
            elapsed += lt
            rows.append({"driver": drv, "lap": lap + 1, "elapsed": elapsed, "lap_time": lt,
                         "compound": rec["compound"], "tyre_life": float(car.age), "pit_in": False,
                         "pit_out": bool(rec["pitted"]), "status": int(scn.status[lap]), "position": 0,
                         "grid": d + 1, "final_pos": 0, "rainfall": bool(scn.wetness[lap] > 0.2)})
    df = pd.DataFrame(rows)
    df["position"] = df.groupby("lap")["elapsed"].rank(method="first").astype(int)
    final = df[df["lap"] == df["lap"].max()].set_index("driver")["position"]
    df["final_pos"] = df["driver"].map(final)
    df = df.sort_values(["driver", "lap"]).reset_index(drop=True)
    df["pit_in"] = df.groupby("driver")["pit_out"].shift(-1, fill_value=False)  # pit_in = lap before the out-lap
    REAL_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(REAL_DIR / f"{track}_synthetic.parquet", index=False)
    return df


def compound_id(name: str) -> int:
    return COMPOUNDS.index(name) if name in COMPOUNDS else 1

