"""The PitWall web server: a small JSON API for the React app, plus the built app itself.

    python -m pitwall.server            # then open http://127.0.0.1:8000

Endpoints (all GET, JSON):
    /api/meta                          tracks, modes, cars, where each track's numbers come from
    /api/race?track=&mode=&seed=&rain=&sc=&n=&rain_at=&heavy=&dry_at=&sc_at=   run one race live;
                                       rain_at / dry_at / sc_at: rain, dry or a safety car from that lap
    /api/map?track=                    the circuit outline for the map
    /api/proof?track=&mode=            results of the many-race test (from results/)
    /api/replay/drivers?track=         drivers that can be replaced in a real race
    /api/replay?track=&driver=         our strategist inside a real race
"""
from __future__ import annotations

import json
import math
import webbrowser
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pitwall.core import CAR_NAMES, COMPOUNDS, STATUS_NAMES
from pitwall.data.params import DATA_DIR, TRACKS, load_track
from pitwall.data.realrace import load_real
from pitwall.engine.inventory import sample_inventory
from pitwall.engine.race import run_race
from pitwall.engine.replay import midfield_drivers, replay_with_sanity
from pitwall.engine.scenario import sample_scenario
from pitwall.eval.metrics import RESULTS, paired, summarise
from pitwall.strategy.registry import make_cars

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
app = FastAPI(title="PitWall")


def clean(x):
    """JSON-safe: NaN/inf -> None, numpy -> python."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else round(float(x), 3)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def check_track(track: str) -> None:
    if track not in TRACKS:
        raise HTTPException(404, f"Unknown track '{track}'. Choose one of {', '.join(TRACKS)}.")


@app.get("/api/meta")
def meta():
    tracks = []
    for t in TRACKS:
        j = json.loads((DATA_DIR / "tracks" / f"{t}.json").read_text())
        fitted = "fitted" in json.dumps(j.get("base_lap", ""))
        tracks.append({"id": t, "laps": j["laps"], "fitted": fitted, "note": j.get("sources", {}).get("_all", "")})
    return {"tracks": tracks, "cars": list(CAR_NAMES), "compounds": list(COMPOUNDS)}


@lru_cache(maxsize=64)
def _race(track: str, mode: str, seed: int, rain: float | None, sc: float, n: int,
          rain_at: int | None = None, heavy: bool = False, sc_at: int | None = None,
          dry_at: int | None = None) -> dict:
    P = load_track(track, mode)
    scn = sample_scenario(P, seed, rain_prob=rain, sc_mult=sc, rain_start=rain_at,
                          rain_peak=1.0 if heavy else 0.6, sc_start=sc_at, dry_start=dry_at)
    inv = sample_inventory(P, np.random.default_rng(seed + 1))
    log, finish = run_race(scn, make_cars(P, scn, n), P, inv)
    cars = {}
    for car, g in log.groupby("car"):
        g = g.sort_values("lap")
        cid = np.array([COMPOUNDS.index(x) for x in g["compound"]])
        cars[car] = {
            "total": g["total"].tolist(), "lap_time": g["lap_time"].tolist(), "compound": g["compound"].tolist(),
            "tyre_age": g["tyre_age"].tolist(), "fuel": g["fuel"].tolist(), "fuel_added": g["fuel_added"].tolist(),
            "pitted": g["pitted"].tolist(),
            # tyre condition: share of the set's useful life used, and seconds per lap lost to wear
            "tyre_life": (g["tyre_age"] / P.cliff_lap[cid]).tolist(),
            "tyre_loss": (P.deg[cid] * g["tyre_age"]
                          + P.cliff_coef[cid] * np.maximum(0.0, g["tyre_age"] - P.cliff_lap[cid]) ** 2).tolist(),
            "decisions": [{"lap": int(r.lap), "reason": r.reason, "options": json.loads(r.options) if r.options else {}}
                          for r in g.itertuples() if r.reason or r.options],
        }
    first = log[log["car"] == log["car"].iloc[0]].sort_values("lap")
    return clean({
        "track": track, "mode": mode, "seed": seed, "laps": P.laps, "tag": scn.tags[0],
        "status": [STATUS_NAMES[s] for s in first["status"]], "wetness": first["wetness"].tolist(),
        # what the teams' weather radar says on each lap: chance of rain for the next 10 laps
        "forecast": [scn.forecast[k, k:k + 10].tolist() for k in range(P.laps)],
        "finish": finish, "cars": cars,
    })


@app.get("/api/race")
def race(track: str = "bahrain", mode: str = "f1", seed: int = 7, rain: float | None = None,
         sc: float = Query(1.0, ge=0, le=5), n: int = Query(100, ge=20, le=400),
         rain_at: int | None = Query(None, ge=1), heavy: bool = False, sc_at: int | None = Query(None, ge=1),
         dry_at: int | None = Query(None, ge=1)):
    check_track(track)
    if mode not in ("f1", "endurance"):
        raise HTTPException(400, "mode must be 'f1' or 'endurance'")
    if rain is not None and not 0 <= rain <= 1:
        raise HTTPException(400, "rain must be between 0 and 1")
    return _race(track, mode, int(seed), rain, float(sc), int(n), rain_at, heavy, sc_at, dry_at)


@app.get("/api/map")
def track_map(track: str = "bahrain"):
    """The circuit outline (400 points, starting at the timing line). Missing -> the app draws an oval."""
    check_track(track)
    f = DATA_DIR / "maps" / f"{track}.json"
    if not f.exists():
        raise HTTPException(404, f"No map for {track} yet. Run: python -m pitwall.data.trackmap")
    return json.loads(f.read_text())


@app.get("/api/proof")
def proof(track: str = "bahrain", mode: str = "f1"):
    check_track(track)
    f = RESULTS / f"eval_{mode}_{track}.parquet"
    if not f.exists():
        return {"available": False, "track": track, "mode": mode}
    summary = summarise()
    w = paired(pd.read_parquet(f))
    gains = (w["pirelli"] - w["rollout"]).dropna()
    hist, edges = np.histogram(gains, bins=min(40, max(10, len(gains) // 10)))
    return clean({
        "available": True, "track": track, "mode": mode,
        "main": summary.get("main", {}).get(mode, {}).get(track),
        "mismatch": summary.get("mismatch", {}).get(mode, {}).get(track),
        "rain_sweep": [r for r in summary.get("rain_sweep", []) if r["rain_prob"] >= 0],
        "histogram": [{"from": float(edges[i]), "to": float(edges[i + 1]), "count": int(hist[i])} for i in range(len(hist))],
        "losses": int((gains < 0).sum()), "races": int(len(gains)), "worst": float(gains.min()) if len(gains) else None,
        "accuracy": json.loads((DATA_DIR / "accuracy.json").read_text()) if (DATA_DIR / "accuracy.json").exists() else None,
    })


NO_REPLAY = {"zandvoort": "Zandvoort 2023 had a 40-minute red flag, which our simulator doesn't model, so it can't be replayed fairly."}


def check_replay(track: str) -> None:
    check_track(track)
    if track in NO_REPLAY:
        raise HTTPException(400, NO_REPLAY[track])


@app.get("/api/replay/drivers")
def replay_drivers(track: str = "bahrain"):
    check_replay(track)
    df, is_real = load_real(track)
    return {"track": track, "is_real": is_real, "drivers": midfield_drivers(track) or sorted(df["driver"].unique())}


@app.get("/api/replay")
def replay(track: str = "bahrain", driver: str = "ALB"):
    check_replay(track)
    f = RESULTS / f"replay_{track}_{driver}.json"
    rep = json.loads(f.read_text()) if f.exists() else replay_with_sanity(track, driver)
    return clean(rep)


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        target = DIST / path
        return FileResponse(target if path and target.is_file() else DIST / "index.html")


def main() -> None:
    import argparse

    import uvicorn
    ap = argparse.ArgumentParser(description="Run the PitWall app")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if not a.no_browser:
        webbrowser.open(f"http://127.0.0.1:{a.port}")
    uvicorn.run(app, host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
