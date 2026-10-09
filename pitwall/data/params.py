"""Load track numbers from data/tracks/<track>.json. Owner: Dharshini (DAT).

A value in the JSON may be a plain number or {"value": x, "source": "..."}; both work.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from pitwall.core import COMPOUNDS, TrackParams

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TRACKS = ("bahrain", "monza", "zandvoort", "singapore")


def _val(x, sources: dict, key: str):
    if isinstance(x, dict) and "value" in x:
        sources[key] = x.get("source", "")
        return x["value"]
    return x


def load_track(name: str, mode: str = "f1") -> TrackParams:
    """Read one track. mode='endurance' switches on the smaller tank and refuelling."""
    raw = json.loads((DATA_DIR / "tracks" / f"{name}.json").read_text())
    src: dict[str, str] = dict(raw.get("sources", {}))
    comp = raw["compounds"]

    def arr(field: str) -> np.ndarray:
        return np.array([_val(comp[c][field], src, f"{c}.{field}") for c in COMPOUNDS], dtype=float)

    g = lambda k: _val(raw[k], src, k)  # noqa: E731
    P = TrackParams(
        name=name, laps=int(g("laps")), base_lap=float(g("base_lap")),
        offset=arr("offset"), deg=arr("deg"), cliff_lap=arr("cliff_lap"), cliff_coef=arr("cliff_coef"),
        warmup=arr("warmup"), wet_pen=np.array([_val(comp[c]["wet_pen"], src, f"{c}.wet_pen") for c in COMPOUNDS], float),
        fuel_start=float(g("fuel_start")), fuel_burn=float(g("fuel_burn")), fuel_effect=float(g("fuel_effect")),
        pit_loss=float(g("pit_loss")), pit_loss_sc=float(g("pit_loss_sc")),
        sc_factor=float(g("sc_factor")), vsc_factor=float(g("vsc_factor")),
        p_sc=float(g("p_sc")), p_vsc=float(g("p_vsc")), sc_len=tuple(int(v) for v in g("sc_len")),
        p_rain=float(g("p_rain")), noise_sd=float(g("noise_sd")),
        allocation=dict(raw.get("allocation", {})), sources=src,
    )
    if mode == "endurance":
        e = raw["endurance"]
        tank = float(_val(e["tank"], src, "endurance.tank"))
        P = replace(P, mode="endurance", tank=tank, fuel_start=tank,
                    refuel_rate=float(_val(e["refuel_rate"], src, "endurance.refuel_rate")))
    return P


def load_pirelli_plan(name: str) -> dict:
    plans = json.loads((DATA_DIR / "pirelli.json").read_text())
    return plans[name]


def perturb(P: TrackParams, rng: np.random.Generator) -> TrackParams:
    """A 'slightly wrong' copy of the numbers, for the fairness test."""
    return replace(
        P,
        deg=P.deg * rng.uniform(0.8, 1.2, size=5),
        offset=P.offset + rng.normal(0, 0.1, size=5),
        pit_loss=P.pit_loss + rng.uniform(-1.5, 1.5),
        fuel_effect=P.fuel_effect * rng.uniform(0.85, 1.15),
    )


def load_param_samples(name: str, mode: str = "f1", n: int = 200, seed: int = 0) -> list[TrackParams]:
    """Uncertainty samples for the fairness test.

    If data/samples/<track>.json exists (written by pitwall.data.fit with bootstrap), it is used.
    Otherwise falls back to random perturbations of the main numbers.
    """
    P = load_track(name, mode)
    f = DATA_DIR / "samples" / f"{name}.json"
    if f.exists():
        out = []
        for s in json.loads(f.read_text())[:n]:
            out.append(replace(P, deg=np.array(s["deg"], float), offset=np.array(s["offset"], float),
                               pit_loss=float(s["pit_loss"]), fuel_effect=float(s["fuel_effect"])))
        return out
    rng = np.random.default_rng(seed)
    return [perturb(P, rng) for _ in range(n)]
