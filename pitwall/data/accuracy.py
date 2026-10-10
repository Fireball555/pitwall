"""How well does our lap-time model predict a race it has never seen? (written with the review panel)

    python -m pitwall.data.accuracy        # writes data/accuracy.json, shown on the Proof screen

Temporal hold-out: fit tyre wear, compound pace and fuel effect on the 2022 race exactly as
pitwall.data.fit does, then predict every clean dry green lap of the 2023 race. A new season's car
pace can't be predicted from tyre data, so one pace level per driver is removed before scoring.
skill = 1 - MSE(model) / MSE(flat line with the same levels): 0 = no better than flat, < 0 = worse.
"stint" skill removes one level per stint, so it scores only the shape within a stint (wear + fuel).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pitwall.data.fit import DRY, clean_laps, fit_pace  # noqa: E402

from pitwall.data.params import DATA_DIR, TRACKS  # noqa: E402

REAL = DATA_DIR / "real"


def load(track, years):
    parts = []
    for y in years:
        d = pd.read_parquet(REAL / f"{track}_{y}.parquet").sort_values(["driver", "lap"])
        d["stint"] = d.groupby("driver")["pit_out"].cumsum()
        parts.append(d.assign(driver=d["driver"] + f"@{y}", race_laps=int(d["lap"].max())))
    return pd.concat(parts, ignore_index=True)


def test_laps(d):
    """Same cleaning as training, minus MIN_LAPS (we must score every compound the race used)."""
    dry = ~d["rainfall"].astype(bool)
    t = d[(d["status"] == 0) & ~d["pit_in"] & ~d["pit_out"] & (d["lap"] > 1)
          & d["compound"].isin(DRY) & d["lap_time"].notna() & dry]
    return t[t["lap_time"] < 1.07 * t["lap_time"].median()].copy()


def fit(train):
    laps = int(train["lap"].max())
    f = fit_pace(clean_laps(train), laps)
    if not 0.02 <= f["fuel_effect"] <= 0.045:  # pipeline rule
        f = fit_pace(clean_laps(train), laps, fuel_effect=0.03)
    return f


def shipped(track):
    j = json.loads((DATA_DIR / "tracks" / f"{track}.json").read_text())
    v = lambda x: x["value"] if isinstance(x, dict) else x  # noqa: E731
    return {"fuel_effect": v(j["fuel_effect"]),
            "offset": {c: v(j["compounds"][c]["offset"]) for c in DRY},
            "deg": {c: v(j["compounds"][c]["deg"]) for c in DRY}, "noise_sd": v(j["noise_sd"])}


def predict(f, t, fallback):
    fuel = 110.0 - 110.0 / t["race_laps"] * 0.98 * (t["lap"] - 1)
    off = t["compound"].map(lambda c: f["offset"].get(c, fallback["offset"][c]))
    deg = t["compound"].map(lambda c: f["deg"].get(c, fallback["deg"][c]))
    return (f["fuel_effect"] * fuel + off + deg * t["tyre_life"]).to_numpy(float)


def scores(t, pred):
    out = {}
    for level, keys in (("race", None), ("driver", ["driver"]), ("stint", ["driver", "stint"])):
        r = pd.Series(t["lap_time"].to_numpy() - pred, index=t.index)
        y = t["lap_time"]
        e = r - (r.mean() if keys is None else r.groupby([t[k] for k in keys]).transform("mean"))
        e0 = y - (y.mean() if keys is None else y.groupby([t[k] for k in keys]).transform("mean"))
        out[level] = (np.abs(e).mean(), np.sqrt((e ** 2).mean()), 1 - (e ** 2).mean() / (e0 ** 2).mean(),
                      np.abs(e0).mean(), np.sqrt((e0 ** 2).mean()))
    return out


def row(name, track, n, s, extra=""):
    print(f"{track:9s} {name:22s} n={n:4d} " + "  ".join(
        f"{lv}: MAE {m:.3f} RMSE {r:.3f} skill {k:+.2f} (null {m0:.3f}/{r0:.3f})"
        for lv, (m, r, k, m0, r0) in s.items() if lv != "race") + f"  race-RMSE {s['race'][1]:.2f}{extra}")


def main() -> dict:
    out = {}
    for tr in TRACKS:
        ship = shipped(tr)
        test = test_laps(load(tr, (2023,)))
        f22 = fit(load(tr, (2022,)))
        s = scores(test, predict(f22, test, ship))
        out[tr] = {"mae_s": round(float(s["driver"][0]), 2), "rmse_s": round(float(s["driver"][1]), 2),
                   "skill": round(float(s["driver"][2]), 2), "stint_skill": round(float(s["stint"][2]), 2),
                   "laps": int(len(test)), "method": "fit on the 2022 race, predict the 2023 race"}
        print(f"{tr:10s} lap-time error {out[tr]['mae_s']:.2f} s  skill {out[tr]['skill']:+.2f}  within-stint skill {out[tr]['stint_skill']:+.2f}")
    (DATA_DIR / "accuracy.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
