"""BR0 — owner BR. Contract tests: types import, mocks load, H0 stubs behave sanely."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pitwall import types as pitwall_types
from pitwall.params import load_param_samples, load_params
from pitwall.sim.engine import lap_time
from pitwall.sim.inventory import sample_inventory
from pitwall.sim.race import run_race
from pitwall.sim.scenario import sample_scenario
from pitwall.strategy.oracle import Oracle
from pitwall.strategy.pirelli import PirelliStrategy
from pitwall.strategy.rollout import RolloutStrategy
from pitwall.strategy.rules import RulesStrategy

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
DATA_DIR = ROOT / "data"


def test_types_import() -> None:
    assert pitwall_types.COMPOUNDS == ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")
    assert pitwall_types.STAY.pit is False


def test_load_params_both_modes() -> None:
    f1 = load_params("mock", mode="f1")
    assert f1.mode == "f1"
    assert f1.track == "mock"
    assert f1.laps == 57

    endurance = load_params("mock", mode="endurance")
    assert endurance.mode == "endurance"
    assert endurance.tank_kg == 60.0
    assert endurance.fuel_start_kg == endurance.tank_kg


def test_load_param_samples() -> None:
    samples = load_param_samples("mock")
    assert len(samples) == 5


def test_mock_param_files_load() -> None:
    raw = json.loads((DATA_DIR / "params" / "mock.json").read_text())
    for key in ("track", "laps", "base_lap_s", "compounds", "fuel_start_kg", "pit_loss_s", "allocation"):
        assert key in raw

    pirelli_raw = json.loads((DATA_DIR / "pirelli" / "mock.json").read_text())
    for key in ("start", "stops", "source"):
        assert key in pirelli_raw


def test_mock_results_files_load() -> None:
    race_log = pd.read_parquet(RESULTS_DIR / "mock_race_log.parquet")
    for col in ("car", "lap", "lap_time_s", "total_time_s", "compound", "tyre_age", "fuel_kg",
                "fuel_added_kg", "pitted", "status", "wetness", "reason", "expected_json"):
        assert col in race_log.columns

    eval_df = pd.read_parquet(RESULTS_DIR / "mock_eval.parquet")
    for col in ("track", "mode", "test", "seed", "rain_prob", "sample_id", "car", "finish_s",
                "dnf", "pit_stops", "tags"):
        assert col in eval_df.columns

    summary = json.loads((RESULTS_DIR / "mock_summary.json").read_text())
    assert "f1" in summary

    replay = json.loads((RESULTS_DIR / "mock_replay.json").read_text())
    for key in ("track", "driver", "real_grid", "real_finish_pos", "our_finish_pos",
                "real_time_s", "our_time_s", "laps", "ours", "real_driver", "sanity"):
        assert key in replay

    index = json.loads((RESULTS_DIR / "replay_index.json").read_text())
    assert isinstance(index, list) and len(index) >= 1


def test_run_race_mock_57_laps_4_cars_no_dnf() -> None:
    P = load_params("mock")
    rng = np.random.default_rng(1)
    scn = sample_scenario(P, seed=1)
    inventory = sample_inventory(P, rng)
    strategies = {
        "pirelli": PirelliStrategy(track="mock"),
        "rules": RulesStrategy(),
        "rollout": RolloutStrategy(),
        "oracle": Oracle(scn),
    }
    beliefs = {name: P for name in strategies}

    df, finish_times = run_race(scn, strategies, P, beliefs, inventory)

    assert len(df) == 57 * 4
    for car in strategies:
        assert len(df[df.car == car]) == 57
        assert not np.isnan(finish_times[car])


def test_sample_scenario_deterministic() -> None:
    P = load_params("mock")
    a = sample_scenario(P, seed=42)
    b = sample_scenario(P, seed=42)
    np.testing.assert_array_equal(a.status, b.status)
    np.testing.assert_array_equal(a.wetness, b.wetness)
    np.testing.assert_array_equal(a.noise, b.noise)


def test_lap_time_array_equals_scalar_loop() -> None:
    P = load_params("mock")
    n = 10
    rng = np.random.default_rng(0)
    cid = rng.integers(0, 3, size=n)
    age = rng.integers(0, 20, size=n)
    fuel = rng.uniform(0, 110, size=n)
    wet = np.zeros(n)
    status = np.zeros(n, dtype=np.int8)
    noise = rng.normal(0, 0.3, size=n)

    array_result = lap_time(cid, age, fuel, wet, status, noise, P)
    scalar_result = np.array([
        lap_time(int(cid[i]), int(age[i]), float(fuel[i]), float(wet[i]), int(status[i]), float(noise[i]), P)
        for i in range(n)
    ])
    np.testing.assert_allclose(array_result, scalar_result)
