"""Turn the raw race results into the numbers on the Proof screen. Owner: Smaran (BR).

Paired comparison: for each seed, every car raced the same conditions, so
gain = baseline finish time - our finish time (positive = we were faster).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RESULTS = Path(__file__).resolve().parents[2] / "results"
BASELINES = ("pirelli", "rules")


def paired(df: pd.DataFrame) -> pd.DataFrame:
    """One row per race: columns = cars, values = finish time."""
    keys = ["track", "mode", "test", "seed", "rain_prob", "sample_id", "tag"]
    w = df.set_index(keys + ["car"])["finish_s"].unstack("car").reset_index()
    w.columns.name = None
    return w


def bootstrap_ci(x: np.ndarray, reps: int = 2000, seed: int = 0) -> tuple[float, float]:
    if len(x) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(reps, len(x)), replace=True).mean(1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def stats(w: pd.DataFrame) -> dict:
    out = {"n_races": int(len(w)), "gain_vs": {}, "win_rate_vs": {}, "dnf": {}}
    for car in ("pirelli", "rules", "rollout", "oracle"):
        if car in w:
            out["dnf"][car] = int(w[car].isna().sum())
    for b in BASELINES:
        if b not in w or "rollout" not in w:
            continue
        g = (w[b] - w["rollout"]).dropna().to_numpy()
        lo, hi = bootstrap_ci(g)
        out["gain_vs"][b] = [float(g.mean()) if len(g) else float("nan"), lo, hi]
        out["win_rate_vs"][b] = float((g > 0).mean()) if len(g) else float("nan")
    if {"pirelli", "rollout", "oracle"} <= set(w.columns):
        ok = w[["pirelli", "rollout", "oracle"]].dropna()
        possible = (ok["pirelli"] - ok["oracle"]).mean()
        out["oracle_share"] = float((ok["pirelli"] - ok["rollout"]).mean() / possible) if possible > 0 else float("nan")
    return out


def summarise() -> dict:
    files = sorted(RESULTS.glob("*.parquet"))
    files = [f for f in files if f.name.split("_")[0] in ("eval", "mismatch", "rain")]
    if not files:
        return {}
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    w = paired(df)
    summary: dict = {"main": {}, "mismatch": {}, "rain_sweep": []}
    for (test, mode, track), g in w.groupby(["test", "mode", "track"]):
        if test == "rain_sweep":
            for rp, gg in g.groupby("rain_prob"):
                s = stats(gg)
                summary["rain_sweep"].append({"track": track, "rain_prob": float(rp),
                                              "gain_vs_pirelli": s["gain_vs"].get("pirelli", [np.nan])[0]})
            continue
        entry = stats(g)
        entry["by_tag"] = {tag: stats(gg) for tag, gg in g.groupby("tag")}
        summary[test].setdefault(mode, {})[track] = entry
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    return summary


if __name__ == "__main__":
    print(json.dumps(summarise(), indent=2, default=float)[:3000])
