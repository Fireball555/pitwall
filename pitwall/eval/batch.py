"""Race many random races and save every car's finish time. Owner: Smaran (BR).

    python -m pitwall.eval.batch --track bahrain --n 1000                     # F1 mode, main test
    python -m pitwall.eval.batch --track bahrain --n 500 --mode endurance
    python -m pitwall.eval.batch --track bahrain --n 500 --test mismatch       # fairness test
    python -m pitwall.eval.batch --track zandvoort --n 200 --test rain_sweep   # rain 0..0.5
    python -m pitwall.eval.batch --all                                         # everything for the demo

Seeds 0-99999 are for evaluation only. Never tune anything on them (tune on seeds >= 100000).
"""
from __future__ import annotations

import argparse
import os
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.data.params import TRACKS, load_param_samples, load_track
from pitwall.engine.inventory import sample_inventory
from pitwall.engine.race import run_race
from pitwall.engine.scenario import sample_scenario
from pitwall.strategy.registry import make_cars

RESULTS = Path(__file__).resolve().parents[2] / "results"


def one_race(job: tuple) -> list[dict]:
    track, mode, seed, test, rain_prob, n_futures = job
    P = load_track(track, mode)
    belief, sample_id = P, -1
    if test == "mismatch":
        samples = load_param_samples(track, mode)
        sample_id = seed % len(samples)
        P = samples[sample_id]            # the TRUE world is slightly different...
    scn = sample_scenario(P, seed, rain_prob=rain_prob)
    inv = sample_inventory(P, np.random.default_rng(seed + 1))
    cars = make_cars(P, scn, n_futures)
    beliefs = {c.name: belief for c in cars if c.name != "oracle"}   # ...from what the fair cars believe
    _, finish = run_race(scn, cars, P, inv, beliefs)
    return [{"track": track, "mode": mode, "test": test, "seed": seed,
             "rain_prob": -1.0 if rain_prob is None else rain_prob, "sample_id": sample_id,
             "car": car, "finish_s": t, "dnf": t != t, "tag": scn.tags[0]} for car, t in finish.items()]


def out_path(track: str, mode: str, test: str) -> Path:
    if test == "main":
        return RESULTS / f"eval_{mode}_{track}.parquet"
    return RESULTS / f"{test}_{mode}_{track}.parquet"


def evaluate(track: str, mode: str = "f1", n: int = 1000, seed0: int = 0, test: str = "main",
             workers: int | None = None, n_futures: int = 200, save: bool = True) -> pd.DataFrame:
    if test == "rain_sweep":
        jobs = [(track, mode, seed0 + i, test, rp, n_futures) for rp in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5) for i in range(n)]
    else:
        jobs = [(track, mode, seed0 + i, test, None, n_futures) for i in range(n)]
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    if workers == 1:
        rows = [r for j in jobs for r in one_race(j)]
    else:
        with Pool(workers) as pool:
            rows = [r for chunk in pool.imap_unordered(one_race, jobs, chunksize=4) for r in chunk]
    df = pd.DataFrame(rows).sort_values(["rain_prob", "seed", "car"]).reset_index(drop=True)
    if save:
        RESULTS.mkdir(exist_ok=True)
        df.to_parquet(out_path(track, mode, test), index=False)
    return df


def run_all(n: int = 1000) -> None:
    for t in TRACKS:
        evaluate(t, "f1", n)
        print("done f1", t)
    for t in ("bahrain", "singapore"):
        evaluate(t, "endurance", n // 2)
        evaluate(t, "f1", n // 2, test="mismatch")
        print("done endurance + mismatch", t)
    evaluate("zandvoort", "f1", n // 5, test="rain_sweep")
    print("done rain sweep")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", default="bahrain", choices=TRACKS)
    ap.add_argument("--mode", default="f1", choices=("f1", "endurance"))
    ap.add_argument("--test", default="main", choices=("main", "mismatch", "rain_sweep"))
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--all", action="store_true", help="run every test used by the Proof screen")
    a = ap.parse_args()
    if a.all:
        run_all(a.n)
    else:
        d = evaluate(a.track, a.mode, a.n, test=a.test, workers=a.workers)
        print(d.groupby("car")["finish_s"].describe())
    from pitwall.eval.metrics import summarise
    summarise()
    print("wrote results/summary.json")
