"""STUB (BR0) — owner BR replaces/extends in BR6. Working now: serial loop over seeds."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.params import load_param_samples, load_params
from pitwall.sim.inventory import sample_inventory
from pitwall.sim.race import run_race
from pitwall.sim.scenario import sample_scenario
from pitwall.strategy.oracle import Oracle
from pitwall.strategy.pirelli import PirelliStrategy
from pitwall.strategy.rollout import RolloutStrategy
from pitwall.strategy.rules import RulesStrategy

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"


def evaluate(track: str, mode: str = "f1", n: int = 50, seed0: int = 0, test: str = "main") -> pd.DataFrame:
    """Run n races (seeds seed0..seed0+n-1) and write results/eval_{mode}_{track}.parquet (Section 3 schema)."""
    belief = load_params(track, mode=mode)
    samples = load_param_samples(track) if test == "mismatch" else None

    rows = []
    for i in range(n):
        seed = seed0 + i
        rng = np.random.default_rng(seed)
        scn = sample_scenario(belief, seed=seed)
        inventory = sample_inventory(belief, rng)

        if test == "mismatch" and samples:
            sample_id = seed % len(samples)
            P_true = samples[sample_id]
        else:
            sample_id = -1
            P_true = belief

        strategies = {
            "pirelli": PirelliStrategy(track=track),
            "rules": RulesStrategy(),
            "rollout": RolloutStrategy(),
            "oracle": Oracle(scn),
        }
        beliefs = {name: belief for name in strategies}
        beliefs["oracle"] = P_true

        df, finish_times = run_race(scn, strategies, P_true, beliefs, inventory)

        for name in strategies:
            car_df = df[df.car == name]
            finish = finish_times[name]
            rows.append(
                {
                    "track": track, "mode": mode, "test": test, "seed": seed,
                    "rain_prob": belief.p_rain_race, "sample_id": sample_id,
                    "car": name, "finish_s": finish, "dnf": bool(np.isnan(finish)),
                    "pit_stops": int(car_df["pitted"].sum()) if not car_df.empty else 0,
                    "tags": ",".join(scn.tags),
                }
            )

    out = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(exist_ok=True)
    if test == "mismatch":
        out_path = RESULTS_DIR / f"mismatch_{track}.parquet"
    elif test == "rain_sweep":
        out_path = RESULTS_DIR / f"rain_sweep_{track}.parquet"
    else:
        out_path = RESULTS_DIR / f"eval_{mode}_{track}.parquet"
    out.to_parquet(out_path, index=False)
    return out
