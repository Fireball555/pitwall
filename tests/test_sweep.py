"""Extensive checks over every track, rule set and weather, through the same API the app uses.

Slow (a few minutes): run with  pytest -m slow  . CI runs the fast tests only.
Every race is checked against the rules of the simulation, not against fixed numbers.
"""
import math

import pytest
from fastapi.testclient import TestClient

from pitwall.data.params import TRACKS, load_track
from pitwall.server import app

client = TestClient(app)
DRY = {"SOFT", "MEDIUM", "HARD"}
pytestmark = pytest.mark.slow


def race(**p):
    r = client.get("/api/race", params={"n": 40, **p})
    assert r.status_code == 200, r.text
    return r.json()


def no_nan(x):
    if isinstance(x, dict):
        return all(no_nan(v) for v in x.values())
    if isinstance(x, list):
        return all(no_nan(v) for v in x)
    return not (isinstance(x, float) and not math.isfinite(x))


def check_race(d, mode):
    P = load_track(d["track"], mode)
    n = d["laps"]
    assert no_nan(d)
    assert len(d["status"]) == n and len(d["wetness"]) == n and len(d["forecast"]) == n
    for name, c in d["cars"].items():
        assert len(c["total"]) == n and len(c["compound"]) == n
        if c["out_after"] is not None or c["dsq"]:
            assert d["finish"][name] is None, f"{name}: out of the race but has a finish time"
            continue
        assert d["finish"][name] == pytest.approx(c["total"][-1], abs=1e-3), f"{name}: finish != last total"
        # time only moves forward, and no lap is absurd
        assert all(b > a for a, b in zip(c["total"], c["total"][1:])), f"{name}: total not increasing"
        assert all(0.5 * P.base_lap < t < 3.0 * P.base_lap for t in c["lap_time"]), f"{name}: odd lap time"
        assert all(x >= 0 for x in c["tyre_age"]) and all(x >= 0 for x in c["tyre_life"])
        # a car on fresh tyres after a stop
        for k in range(1, n):
            if c["pitted"][k]:
                assert c["tyre_age"][k] <= 4, f"{name}: lap {k + 1} pitted onto an old set"
        if mode == "endurance":
            assert min(c["fuel"]) >= -1e-6, f"{name}: ran out of fuel"
            assert max(c["fuel"]) <= P.tank + 1e-6, f"{name}: more fuel than the tank holds"
        # the 2023 two-compound rule, unless the race turned wet
        if mode == "f1" and max(d["wetness"]) <= 0.2:
            assert len(set(c["compound"]) & DRY) >= 2, f"{name}: broke the two-compound rule"
        for dec in c["decisions"]:
            assert 1 <= dec["lap"] <= n
            if "samples" in dec:
                assert set(dec["samples"]) <= set(dec["options"])


@pytest.mark.parametrize("track", TRACKS)
@pytest.mark.parametrize("mode", ["f1", "endurance"])
@pytest.mark.parametrize("weather", [0.0, None, 1.0])
def test_every_track_mode_and_weather(track, mode, weather):
    params = {"track": track, "mode": mode, "seed": 11}
    if weather is not None:
        params["rain"] = weather
    check_race(race(**params), mode)


@pytest.mark.parametrize("track", ["bahrain", "zandvoort"])
def test_forced_events_happen_where_asked(track):
    base = race(track=track, seed=5, rain=0.0)
    wet = race(track=track, seed=5, rain=0.0, rain_at=20, heavy=True)
    assert max(wet["wetness"][21:24]) > 0.5 and wet["wetness"][:20] == base["wetness"][:20]
    dry = race(track=track, seed=5, rain=0.0, rain_at=20, heavy=True, dry_at=30)
    assert dry["wetness"][45] < 0.05
    sc = race(track=track, seed=5, rain=0.0, sc_at=25)
    assert sc["status"][25:29] == ["SC"] * 4
    for d in (wet, dry, sc):
        check_race(d, "f1")


def test_same_inputs_same_race():
    a, b = race(track="monza", seed=99), race(track="monza", seed=99)
    assert a["finish"] == b["finish"]


@pytest.mark.parametrize("track", ["bahrain", "monza", "singapore"])
def test_every_replay_is_consistent(track):
    ds = client.get("/api/replay/drivers", params={"track": track}).json()
    for drv in ds["drivers"][:3]:
        rep = client.get("/api/replay", params={"track": track, "driver": drv}).json()
        assert no_nan({k: v for k, v in rep.items() if k not in ("ghost", "tyres")})
        n = len(rep["laps"])
        assert n == rep["laps_total"] and len(rep["ours"]) == n
        for L in rep["laps"]:
            assert "OURS" in L["order"] and drv not in L["order"] and len(L["order"]) <= 20
            times = [L["elapsed"][x] for x in L["order"]]
            assert times == sorted(times)
        assert rep["our_finish_pos"] == rep["laps"][-1]["order"].index("OURS") + 1
        assert 1 <= rep["sanity"]["real_strategy_pos"] <= 20


def test_bad_inputs_are_refused_politely():
    assert client.get("/api/race", params={"track": "mars"}).status_code == 404
    assert client.get("/api/race", params={"mode": "rally"}).status_code == 400
    assert client.get("/api/race", params={"rain": 2}).status_code == 400
    assert client.get("/api/race", params={"sc": 9}).status_code == 422
    assert client.get("/api/replay", params={"track": "zandvoort", "driver": "HAM"}).status_code == 400


def test_a_car_that_runs_out_of_fuel_is_shown_as_out():
    """Monza, endurance, wet, lots of safety cars, race 13: the Pirelli plan runs dry. The app still gets
    full-length arrays (the car is frozen where it stopped) and is told when it went out."""
    d = race(track="monza", mode="endurance", seed=13, rain=1.0, sc=3.0)
    out = {k: c["out_after"] for k, c in d["cars"].items() if c["out_after"] is not None}
    assert out, "expected at least one car to run out of fuel in this race"
    for k, lap in out.items():
        c = d["cars"][k]
        assert 0 < lap < d["laps"] and len(c["total"]) == d["laps"] and d["finish"][k] is None
        assert c["total"][lap:] == [c["total"][lap - 1]] * (d["laps"] - lap)
    assert d["finish"]["rollout"] is not None
