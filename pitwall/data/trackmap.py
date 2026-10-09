"""Track outlines for the app's map, from real F1 car-position data.

    python -m pitwall.data.trackmap            # all 4 tracks (needs internet the first time)

Takes the fastest lap of the 2023 race, rotates it the way F1 broadcasts show the circuit,
resamples it to 400 evenly spaced points and saves data/maps/<track>.json. The first point is
the timing line, so the app can place cars by how far round the lap they are.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from pitwall.data.params import DATA_DIR, TRACKS
from pitwall.data.realrace import FASTF1_EVENT

MAP_DIR = DATA_DIR / "maps"
N_POINTS = 400


def resample(xy: np.ndarray, n: int = N_POINTS) -> np.ndarray:
    """n points evenly spaced along the path (by distance, not by time)."""
    seg = np.hypot(*np.diff(xy, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0.0, s[-1], n, endpoint=False)
    return np.column_stack([np.interp(t, s, xy[:, 0]), np.interp(t, s, xy[:, 1])])


def normalise(xy: np.ndarray, size: float = 1000.0) -> np.ndarray:
    """Fit inside a size x size box, keep the shape, flip y for SVG (y grows downwards)."""
    xy = xy - xy.min(0)
    xy = xy / xy.max() * size
    xy[:, 1] = xy[:, 1].max() - xy[:, 1]
    return xy


def extract(track: str, year: int = 2023, cache: str = "cache") -> dict:
    import fastf1

    Path(cache).mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(cache)
    s = fastf1.get_session(year, FASTF1_EVENT[track], "R")
    s.load(laps=True, telemetry=True, weather=False, messages=False)
    lap = s.laps.pick_fastest()
    if lap is None or (hasattr(lap, "empty") and lap.empty):
        lap = s.laps.pick_drivers(s.results["Abbreviation"].iloc[0]).iloc[10]
    pos = lap.get_pos_data()
    xy = pos[["X", "Y"]].to_numpy(float)
    xy = xy[~np.isnan(xy).any(1)]
    rot = math.radians(float(s.get_circuit_info().rotation))
    c, si = math.cos(rot), math.sin(rot)
    xy = xy @ np.array([[c, si], [-si, c]])
    pts = normalise(resample(xy))
    return {"track": track, "points": [[round(x, 1), round(y, 1)] for x, y in pts],
            "source": f"FastF1 car position data, fastest lap of the {year} race"}


def main() -> None:
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    for t in TRACKS:
        try:
            m = extract(t)
        except Exception as e:  # keep going: the app falls back to a plain oval for a missing map
            print(f"  {t}: failed ({e})")
            continue
        (MAP_DIR / f"{t}.json").write_text(json.dumps(m))
        print(f"  {t}: {len(m['points'])} points")


if __name__ == "__main__":
    main()
