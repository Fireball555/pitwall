"""Data tests. Owner: Dharshini (DAT)."""
import numpy as np

from pitwall.data.fit import clean_laps, fit_pace
from pitwall.data.params import TRACKS, load_param_samples, load_track
from pitwall.data.realrace import make_synthetic


def test_every_track_loads_in_both_modes():
    for t in TRACKS:
        P = load_track(t)
        E = load_track(t, "endurance")
        assert P.laps > 40 and P.fuel_start >= P.laps * P.fuel_burn * 0.95
        assert E.mode == "endurance" and E.tank < P.fuel_start


def test_samples_differ_from_main_numbers():
    s = load_param_samples("bahrain", n=5)
    assert len(s) == 5 and not np.allclose(s[0].deg, load_track("bahrain").deg)


def test_fit_recovers_known_numbers_from_synthetic_race():
    df = make_synthetic("monza")
    P = load_track("monza")
    fit = fit_pace(clean_laps(df), int(df["lap"].max()))
    assert abs(fit["fuel_effect"] - P.fuel_effect) < 0.01
    assert abs(fit["deg"]["MEDIUM"] - P.deg[1]) < 0.5 * P.deg[1] + 0.02
