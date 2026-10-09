"""Engine tests. Owner: Ashwin (SIM)."""
import numpy as np

from pitwall.core import HARD, INTER, MEDIUM, SOFT, STAY, Action, Decision
from pitwall.data.params import load_track
from pitwall.engine.inventory import sample_inventory
from pitwall.engine.lap import lap_time
from pitwall.engine.race import run_race
from pitwall.engine.scenario import sample_futures, sample_scenario
from pitwall.strategy.rules import RulesStrategy

P = load_track("bahrain")


def test_lap_time_vectorised_matches_scalar():
    cid = np.array([SOFT, MEDIUM, HARD, INTER])
    age = np.array([0, 5, 20, 3])
    fuel = np.array([100.0, 50.0, 10.0, 0.0])
    wet = np.array([0.0, 0.3, 0.6, 1.0])
    st = np.array([0, 1, 2, 0])
    nz = np.array([0.1, -0.2, 0.0, 0.3])
    vec = lap_time(P, cid, age, fuel, wet, st, nz)
    scal = [float(lap_time(P, *args)) for args in zip(cid, age, fuel, wet, st, nz)]
    assert np.allclose(vec, scal)


def test_older_tyres_and_more_fuel_are_slower():
    assert lap_time(P, MEDIUM, 20, 50, 0, 0, 0) > lap_time(P, MEDIUM, 5, 50, 0, 0, 0)
    assert lap_time(P, MEDIUM, 5, 100, 0, 0, 0) > lap_time(P, MEDIUM, 5, 10, 0, 0, 0)


def test_slicks_lose_more_than_inters_in_the_wet():
    assert lap_time(P, MEDIUM, 5, 50, 1.0, 0, 0) > lap_time(P, INTER, 5, 50, 1.0, 0, 0)
    assert lap_time(P, MEDIUM, 5, 50, 0.0, 0, 0) < lap_time(P, INTER, 5, 50, 0.0, 0, 0)


def test_same_seed_same_race():
    a, b = sample_scenario(P, 3), sample_scenario(P, 3)
    assert np.array_equal(a.status, b.status) and np.array_equal(a.noise, b.noise)


def test_futures_shape():
    f = sample_futures(P, 10, 0, 0.0, np.zeros(P.laps - 10), 50, np.random.default_rng(0))
    assert f["status"].shape == (50, P.laps - 10) and f["wetness"].shape == (50, P.laps - 10)


def test_race_completes_without_dnf():
    scn = sample_scenario(P, 1)
    log, finish = run_race(scn, [RulesStrategy()], P, sample_inventory(P, np.random.default_rng(1)))
    assert len(log) == P.laps and finish["rules"] == finish["rules"]


class NeverPits:
    name = "lazy"

    def reset(self, belief, car):
        pass

    def decide(self, car, obs):
        return Decision(Action(True, car.inventory[0].set_id)) if obs.lap == 0 else Decision(STAY)


def test_one_dry_compound_is_disqualified_in_a_dry_f1_race():
    scn = sample_scenario(P, 1, rain_prob=0.0)
    _, finish = run_race(scn, [NeverPits()], P, sample_inventory(P, np.random.default_rng(1)))
    assert finish["lazy"] != finish["lazy"]  # NaN = DNF / DSQ


def test_endurance_mode_refuels_and_finishes():
    Pe = load_track("bahrain", "endurance")
    assert Pe.fuel_start < Pe.laps * Pe.fuel_burn  # a refuel is necessary
    scn = sample_scenario(Pe, 2)
    log, finish = run_race(scn, [RulesStrategy()], Pe, sample_inventory(Pe, np.random.default_rng(2)))
    assert finish["rules"] == finish["rules"] and log["fuel_added"].sum() > 0


def test_forced_rain_is_a_surprise_for_the_fair_strategists():
    """'Rain now' at lap L must not change anything PitWall saw or did before lap L."""
    import numpy as np

    from pitwall.data.params import load_track
    from pitwall.engine.inventory import sample_inventory
    from pitwall.engine.race import run_race
    from pitwall.engine.scenario import sample_scenario
    from pitwall.strategy.rollout import RolloutStrategy

    P = load_track("bahrain")
    a = sample_scenario(P, 3, rain_prob=0.0)
    b = sample_scenario(P, 3, rain_prob=0.0, rain_start=20, rain_peak=1.0)
    assert np.allclose(a.forecast[:20], b.forecast[:20]) and b.wetness[21] > 0.2
    inv = sample_inventory(P, np.random.default_rng(3))
    la, _ = run_race(a, [RolloutStrategy(n=50, seed=1)], P, inv)
    lb, _ = run_race(b, [RolloutStrategy(n=50, seed=1)], P, inv)
    cols = ["lap", "compound", "pitted"]
    assert la[la["lap"] <= 20][cols].equals(lb[lb["lap"] <= 20][cols])
