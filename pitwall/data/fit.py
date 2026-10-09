"""Work out a track's real numbers from real laps. Owner: Dharshini (DAT).

Input: a real-race file (see realrace.py). Output: the numbers in data/tracks/<track>.json,
each marked with where it came from, plus 200 bootstrap samples in data/samples/<track>.json
for the fairness test.

Model (least squares, one fixed pace offset per driver):
    lap_time = driver_offset + fuel_effect * fuel_on_board + offset[compound] + deg[compound] * tyre_age
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.core import GREEN, SC, VSC

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DRY = ("SOFT", "MEDIUM", "HARD")
MIN_LAPS = 60  # fewer clean laps than this on a compound and its wear is noise, not signal


def clean_laps(df: pd.DataFrame) -> pd.DataFrame:
    """Green-flag dry laps only: no pit in/out laps, no lap 1, no outliers."""
    dry_weather = ~df["rainfall"].astype(bool) if "rainfall" in df.columns else True
    d = df[(df["status"] == GREEN) & (~df["pit_in"]) & (~df["pit_out"]) & (df["lap"] > 1)
           & (df["compound"].isin(DRY)) & df["lap_time"].notna() & dry_weather]
    d = d[d["lap_time"] < 1.07 * d["lap_time"].median()]
    counts = d["compound"].value_counts()
    return d[d["compound"].map(counts) >= MIN_LAPS].copy()


def ordered(values: dict, weight: dict, increasing: bool) -> dict:
    """Pool-adjacent-violators in SOFT -> MEDIUM -> HARD order: where the fit breaks the order,
    the offending compounds get their lap-weighted average (the data can't tell them apart)."""
    keys = [c for c in DRY if c in values]
    blocks = [[values[c] * (1 if increasing else -1), weight[c], [c]] for c in keys]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] > blocks[i + 1][0]:
            a, b = blocks[i], blocks.pop(i + 1)
            w = a[1] + b[1]
            blocks[i] = [(a[0] * a[1] + b[0] * b[1]) / w, w, a[2] + b[2]]
            i = max(i - 1, 0)
        else:
            i += 1
    return {c: v * (1 if increasing else -1) for v, _, cs in blocks for c in cs}


def fit_pace(clean: pd.DataFrame, laps: int, fuel_start: float = 110.0, fuel_effect: float | None = None) -> dict:
    """Least-squares fit. Returns base_lap, fuel_effect, offset{}, deg{}, noise_sd and driver offsets."""
    burn = fuel_start / laps * 0.98
    race_laps = clean["race_laps"].to_numpy(float) if "race_laps" in clean else np.full(len(clean), laps)
    fuel = fuel_start - fuel_start / race_laps * 0.98 * (clean["lap"].to_numpy() - 1)
    drivers = sorted(clean["driver"].unique())
    comps = [c for c in DRY if (clean["compound"] == c).any()]
    ref = "MEDIUM" if "MEDIUM" in comps else comps[0]
    cols, names = [], []
    for d in drivers:
        cols.append((clean["driver"] == d).to_numpy(float)); names.append(f"drv:{d}")
    for c in comps:
        if c != ref:
            cols.append((clean["compound"] == c).to_numpy(float)); names.append(f"off:{c}")
        cols.append(((clean["compound"] == c) * clean["tyre_life"]).to_numpy(float)); names.append(f"deg:{c}")
    y = clean["lap_time"].to_numpy(float)
    if fuel_effect is None:
        cols.append(fuel); names.append("fuel")
    else:
        y = y - fuel_effect * fuel
    X = np.column_stack(cols)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    coef = dict(zip(names, beta))
    resid = y - X @ beta
    fe = coef.get("fuel", fuel_effect)
    drv = {d: coef[f"drv:{d}"] for d in drivers}
    # Pooled seasons have drivers named "VER@2023": take the base pace from the latest season.
    years = sorted({d.split("@")[1] for d in drivers if "@" in d})
    latest = [v for d, v in drv.items() if not years or d.endswith("@" + years[-1])]
    base = float(np.median(latest))
    offset = {c: (0.0 if c == ref else float(coef[f"off:{c}"])) for c in comps}
    deg = {c: float(coef[f"deg:{c}"]) for c in comps}
    weight = {c: float((clean["compound"] == c).sum()) for c in comps}
    # Physics we trust more than one noisy race: softer is never slower, and never wears slower.
    offset = ordered(offset, weight, increasing=True)
    deg = ordered(deg, weight, increasing=False)
    # MEDIUM is the zero point; without medium laps, use the middle of the others
    mid = offset["MEDIUM"] if "MEDIUM" in offset else float(np.mean(list(offset.values())))
    offset = {c: v - mid for c, v in offset.items()}
    base += mid
    return {
        "base_lap": base, "fuel_effect": float(fe), "fuel_burn": float(burn),
        "offset": offset,
        "deg": deg,
        "noise_sd": float(np.clip(resid.std(), 0.2, 0.8)),
        "driver_offset": {d: v - base for d, v in drv.items()},
        "n_laps": int(len(clean)),
    }


def fit_pit_loss(df: pd.DataFrame) -> tuple[float, float, int, int]:
    """(green pit loss, SC pit loss, n green stops, n SC stops).

    Loss = time of the in-lap + out-lap minus what the cars that did NOT pit did on those same
    two laps (same race, same lap). That reference makes the SC loss fair too: everyone is slow
    under a safety car, so only the extra time of the stop counts."""
    d = df.copy()
    d["race"] = d["driver"].str.split("@").str[1].fillna("")
    stopping = d["pit_in"] | d["pit_out"]
    ref = d[~stopping & d["lap_time"].notna()].groupby(["race", "lap"])["lap_time"].median()
    green, sc = [], []
    for drv, g in d.sort_values(["driver", "lap"]).groupby("driver"):
        g = g.set_index("lap")
        race = g["race"].iloc[0]
        for lap in g.index[g["pit_in"]]:
            if lap + 1 not in g.index or lap <= 1 or (race, lap) not in ref or (race, lap + 1) not in ref:
                continue
            loss = g.at[lap, "lap_time"] + g.at[lap + 1, "lap_time"] - ref[(race, lap)] - ref[(race, lap + 1)]
            if not np.isfinite(loss) or not 5 < loss < 60:  # missing time, or a drive-through/repair
                continue
            (sc if g.at[lap, "status"] in (SC, VSC) else green).append(loss)
    g_loss = float(np.median(green)) if green else float("nan")
    s_loss = float(np.median(sc)) if len(sc) >= 3 else 0.55 * g_loss
    return g_loss, s_loss, len(green), len(sc)


def fit_sc_factor(df: pd.DataFrame) -> float:
    sc = df[df["status"] == SC]["lap_time"].median()
    green = clean_laps(df)["lap_time"].median()
    return float(sc / green) if sc == sc and green else 1.4


def bootstrap(df: pd.DataFrame, laps: int, n: int = 200, seed: int = 0) -> list[dict]:
    """Refit on resampled drivers: the spread is our honest uncertainty."""
    rng = np.random.default_rng(seed)
    clean = clean_laps(df)
    drivers = clean["driver"].unique()
    base = fit_pace(clean, laps)
    g_loss, *_ = fit_pit_loss(df)
    out = []
    for _ in range(n):
        pick = rng.choice(drivers, size=len(drivers), replace=True)
        sample = pd.concat([clean[clean["driver"] == d].assign(driver=f"{d}_{i}") for i, d in enumerate(pick)])
        f = fit_pace(sample, laps, fuel_effect=base["fuel_effect"])
        out.append({
            "deg": [max(0.0, f["deg"].get(c, base["deg"].get(c, 0.05))) for c in DRY] + [0.05, 0.04],
            "offset": [f["offset"].get(c, 0.0) for c in DRY] + [0.0, 0.0],
            "pit_loss": float(g_loss + rng.normal(0, 0.8)),
            "fuel_effect": base["fuel_effect"],
        })
    return out


def update_track_json(track: str, df: pd.DataFrame, source: str) -> dict:
    """Fit everything we can from one race and write it into data/tracks/<track>.json."""
    path = DATA_DIR / "tracks" / f"{track}.json"
    j = json.loads(path.read_text())
    laps = int(df["lap"].max())
    fit = fit_pace(clean_laps(df), laps)
    if not 0.02 <= fit["fuel_effect"] <= 0.045:   # outside the known range: fix it and refit
        fit = fit_pace(clean_laps(df), laps, fuel_effect=0.03)
        fe_src = "assumed 0.03 s/kg (fitted value out of range)"
    else:
        fe_src = source
    tag = lambda v, s=source: {"value": round(float(v), 4), "source": s}  # noqa: E731
    j["laps"], j["base_lap"] = laps, tag(fit["base_lap"])
    j["fuel_effect"], j["fuel_burn"] = tag(fit["fuel_effect"], fe_src), tag(fit["fuel_burn"], "110 kg / laps")
    j["noise_sd"] = tag(fit["noise_sd"])
    soft_fast = fit["offset"].get("SOFT", -0.5)
    for c in DRY:
        if c in fit["deg"] and fit["deg"][c] >= 0:
            j["compounds"][c]["deg"] = tag(fit["deg"][c])
        if c in fit["offset"]:
            j["compounds"][c]["offset"] = tag(fit["offset"][c])
    if "SOFT" not in fit["offset"]:
        j["compounds"]["SOFT"]["offset"] = {"value": min(soft_fast, -0.3), "source": "assumed (no soft laps)"}
    g_loss, s_loss, n_g, n_s = fit_pit_loss(df)
    if g_loss == g_loss:
        j["pit_loss"] = tag(g_loss, f"{source}, median of {n_g} stops")
        if n_s >= 5 and s_loss < g_loss:
            j["pit_loss_sc"] = tag(s_loss, f"{source}, median of {n_s} SC/VSC stops")
        else:  # too few stops, or the field queueing behind the SC swamps the measurement
            j["pit_loss_sc"] = tag(0.55 * g_loss, f"assumed 0.55 x pit loss ({n_s} SC stops, too few or unreliable)")
    j["sc_factor"] = tag(fit_sc_factor(df))
    j.setdefault("sources", {})["_all"] = f"{source} where marked; unmarked values are placeholders"
    path.write_text(json.dumps(j, indent=2))
    (DATA_DIR / "samples").mkdir(exist_ok=True)
    (DATA_DIR / "samples" / f"{track}.json").write_text(json.dumps(bootstrap(df, laps)))
    (DATA_DIR / "real").mkdir(exist_ok=True)
    (DATA_DIR / "real" / f"{track}_offsets.json").write_text(json.dumps(fit["driver_offset"], indent=2))
    return fit

