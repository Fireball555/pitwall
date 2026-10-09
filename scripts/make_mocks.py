"""BR0: generates every mock results file so UI and tests have something to run against from H0."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from pitwall.eval.batch import evaluate
from pitwall.eval.metrics import summarise
from pitwall.params import load_params
from pitwall.sim.inventory import sample_inventory
from pitwall.sim.race import run_race
from pitwall.sim.scenario import sample_scenario
from pitwall.strategy.oracle import Oracle
from pitwall.strategy.pirelli import PirelliStrategy
from pitwall.strategy.rollout import RolloutStrategy
from pitwall.strategy.rules import RulesStrategy
from pitwall.types import COMPOUNDS

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"


def make_race_log() -> None:
    P = load_params("mock")
    rng = np.random.default_rng(7)
    scn = sample_scenario(P, seed=7)
    inventory = sample_inventory(P, rng)
    strategies = {
        "pirelli": PirelliStrategy(track="mock"),
        "rules": RulesStrategy(),
        "rollout": RolloutStrategy(),
        "oracle": Oracle(scn),
    }
    beliefs = {name: P for name in strategies}
    df, _ = run_race(scn, strategies, P, beliefs, inventory)
    df.to_parquet(RESULTS_DIR / "mock_race_log.parquet", index=False)


def make_eval() -> None:
    rng = np.random.default_rng(0)
    frames = [
        evaluate("mock", mode="f1", n=50, seed0=0, test="main"),
        evaluate("mock", mode="endurance", n=50, seed0=0, test="main"),
        evaluate("mock", mode="f1", n=50, seed0=0, test="mismatch"),
    ]
    combined = pd.concat(frames, ignore_index=True)
    combined["finish_s"] = combined["finish_s"] + rng.normal(0.0, 0.5, size=len(combined))
    combined.to_parquet(RESULTS_DIR / "mock_eval.parquet", index=False)


def make_summary() -> None:
    summary = summarise()
    (RESULTS_DIR / "mock_summary.json").write_text(json.dumps(summary, indent=2))


def make_replay() -> None:
    rng = np.random.default_rng(42)
    laps_total = 57
    drivers = [f"D{i:02d}" for i in range(19)] + ["OURS"]
    replaced = "D05"

    base_pace = {d: 95.0 + rng.normal(0, 1.0) for d in drivers}
    elapsed = {d: 0.0 for d in drivers}
    laps_out = []
    ours_laps = []
    real_driver_laps = []
    order: list[str] = drivers

    for lap in range(1, laps_total + 1):
        lap_elapsed = {}
        for d in drivers:
            lt = base_pace[d] + rng.normal(0, 0.3)
            elapsed[d] += lt
            lap_elapsed[d] = elapsed[d]
        order = sorted(drivers, key=lambda d: lap_elapsed[d])
        laps_out.append({"lap": lap, "order": order, "elapsed": {d: round(lap_elapsed[d], 2) for d in drivers}})

        compound = COMPOUNDS[(lap // 20) % 3]
        pitted = lap % 20 == 0
        ours_laps.append({"lap": lap, "compound": compound, "tyre_age": lap % 20, "pitted": pitted, "reason": "mock"})
        real_driver_laps.append({"lap": lap, "compound": compound, "pitted": pitted})

    real_grid = 11
    real_finish_pos = 11
    our_finish_pos = order.index("OURS") + 1

    replay = {
        "track": "mock", "driver": replaced,
        "real_grid": real_grid, "real_finish_pos": real_finish_pos,
        "our_finish_pos": our_finish_pos,
        "real_time_s": round(elapsed[replaced], 2), "our_time_s": round(elapsed["OURS"], 2),
        "laps": laps_out, "ours": ours_laps, "real_driver": real_driver_laps,
        "sanity": {"real_strategy_pos": real_finish_pos, "real_pos": real_finish_pos},
    }
    (RESULTS_DIR / "mock_replay.json").write_text(json.dumps(replay, indent=2))

    index = [{"track": "mock", "driver": replaced, "file": "mock_replay.json"}]
    (RESULTS_DIR / "replay_index.json").write_text(json.dumps(index, indent=2))


if __name__ == "__main__":
    RESULTS_DIR.mkdir(exist_ok=True)
    make_race_log()
    make_eval()
    make_summary()
    make_replay()
    print("Mock files written to results/")
