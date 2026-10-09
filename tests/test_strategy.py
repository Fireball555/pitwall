"""Strategy tests. Owner: Smaran (BR)."""
import time
from dataclasses import replace

import numpy as np

from pitwall.data.params import load_track
from pitwall.engine.inventory import sample_inventory
from pitwall.engine.race import run_race
from pitwall.engine.scenario import sample_scenario
from pitwall.strategy.registry import make_cars
from pitwall.strategy.rollout import RolloutStrategy

P = load_track("bahrain")


def test_all_four_cars_finish():
    scn = sample_scenario(P, 11)
    _, finish = run_race(scn, make_cars(P, scn, 50), P, sample_inventory(P, np.random.default_rng(11)))
    assert all(v == v for v in finish.values())


def test_rollout_is_fast_enough():
    scn = sample_scenario(P, 5)
    t = time.time()
    run_race(scn, [RolloutStrategy(n=100, seed=5)], P, sample_inventory(P, np.random.default_rng(5)))
    assert time.time() - t < 6.0  # one full race, every lap re-planned


def test_no_peeking_at_the_future():
    """Changing what happens AFTER lap L must not change any decision up to lap L."""
    scn = sample_scenario(P, 21, rain_prob=0.0)
    L = 25
    status, noise = scn.status.copy(), scn.noise.copy()
    status[L + 1:] = 2          # safety car for the rest of the race...
    noise[L + 1:] += 3.0        # ...and very different lap times
    scn2 = replace(scn, status=status, noise=noise)
    inv = sample_inventory(P, np.random.default_rng(21))
    a, _ = run_race(scn, [RolloutStrategy(n=100, seed=1)], P, inv)
    b, _ = run_race(scn2, [RolloutStrategy(n=100, seed=1)], P, inv)
    cols = ["lap", "compound", "pitted"]
    assert a[a["lap"] <= L][cols].equals(b[b["lap"] <= L][cols])
