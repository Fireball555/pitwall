"""Turn real 2023 F1 data into our track numbers. Owner: Dharshini (DAT).

    python -m pitwall.data.build --track bahrain         # one track (needs internet the first time)
    python -m pitwall.data.build --all                   # all 4 tracks + safety car and rain rates
    python -m pitwall.data.build --track bahrain --synthetic   # test the pipeline offline on fake data

What it does: downloads the race with FastF1 -> saves data/real/<track>_2023.parquet ->
fits tyre wear, fuel effect, pit loss and noise -> writes data/tracks/<track>.json (every value
marked with its source) -> writes 200 uncertainty samples -> (with --rates) fits safety car and
rain rates from 2018-2023.
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from pitwall.core import SC, VSC
from pitwall.data.fit import DATA_DIR, update_track_json
from pitwall.data.params import TRACKS
from pitwall.data.realrace import extract_from_fastf1, make_synthetic


def leader_status(df) -> np.ndarray:
    lead = df[df["position"] == 1].sort_values("lap")
    return lead["status"].to_numpy()


def count_events(status: np.ndarray, kind: int) -> list[int]:
    """Lengths of each SC (or VSC) period."""
    lengths, run = [], 0
    for s in status:
        if s == kind:
            run += 1
        elif run:
            lengths.append(run)
            run = 0
    if run:
        lengths.append(run)
    return lengths


def fit_rates(track: str, years=range(2018, 2024)) -> dict:
    sc_runs, vsc_runs, laps_total, races, rainy = [], [], 0, 0, 0
    for y in years:
        try:
            df = extract_from_fastf1(track, y)
        except Exception as e:  # race not held that year, or no data
            print(f"  skip {track} {y}: {e}")
            continue
        st = leader_status(df)
        sc_runs += count_events(st, SC)
        vsc_runs += count_events(st, VSC)
        laps_total += len(st)
        races += 1
        # A wet race = teams actually ran wet-weather tyres. The weather station's
        # "rainfall" flag also fires on a few drops, which would inflate p_rain.
        wet_laps = df["compound"].isin(["INTER", "WET"]).sum()
        rainy += int(wet_laps >= 5)
    if not races:
        return {}
    src = f"FastF1 {min(years)}-{max(years)}, {races} races at this track"
    allr = sc_runs + vsc_runs
    return {
        "p_sc": {"value": round(len(sc_runs) / laps_total, 4), "source": src},
        "p_vsc": {"value": round(len(vsc_runs) / laps_total, 4), "source": src},
        "sc_len": {"value": [int(min(allr)), int(max(allr))] if allr else [3, 6], "source": src if allr else "assumed"},
        "p_rain": {"value": round(max(0.02, rainy / races), 3), "source": src + " (share of races where inters or wets were used)"},
    }


# Seasons whose races we fit dry pace from: the 18-inch tyre era (2022+), pooled so every
# compound has enough laps (Bahrain 2023 had only 10 medium laps). Zandvoort 2023 was wet,
# so its dry numbers come from 2022 alone. The 2023 race is always downloaded for the replay.
PACE_YEARS = {"zandvoort": (2022,)}


def pace_data(track: str):
    import pandas as pd
    parts = []
    for y in PACE_YEARS.get(track, (2022, 2023)):
        d = extract_from_fastf1(track, y)
        parts.append(d.assign(driver=d["driver"] + f"@{y}", race_laps=int(d["lap"].max())))
    if 2023 not in PACE_YEARS.get(track, (2022, 2023)):
        extract_from_fastf1(track, 2023)
    return pd.concat(parts, ignore_index=True)


def build(track: str, synthetic: bool = False, rates: bool = True) -> None:
    print(f"== {track}")
    years = PACE_YEARS.get(track, (2022, 2023))
    df = make_synthetic(track) if synthetic else pace_data(track)
    src = "synthetic test data" if synthetic else f"fitted from {'+'.join(map(str, years))} races (FastF1)"
    fit = update_track_json(track, df, src)
    print(f"  base lap {fit['base_lap']:.2f} s, fuel {fit['fuel_effect']:.3f} s/kg, deg {fit['deg']}, laps used {fit['n_laps']}")
    if rates and not synthetic:
        r = fit_rates(track)
        if r:
            path = DATA_DIR / "tracks" / f"{track}.json"
            j = json.loads(path.read_text())
            j.update(r)
            path.write_text(json.dumps(j, indent=2))
            print(f"  rates: {r}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", choices=TRACKS)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--synthetic", action="store_true", help="offline test on fake data")
    ap.add_argument("--no-rates", action="store_true", help="skip the 2018-2023 safety car / rain download")
    a = ap.parse_args()
    for t in (TRACKS if a.all else [a.track or "bahrain"]):
        build(t, a.synthetic, not a.no_rates)
