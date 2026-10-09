"""STUB (BR0) — owner DAT replaces in DAT5. Working now: reads data/params/{track}.json."""
from __future__ import annotations

import json
from pathlib import Path

from pitwall.types import CompoundParams, Mode, TrackParams

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "params"


def _unwrap(value):
    """A JSON value may be a plain number or {"value": x, "source": "..."}; accept both."""
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _compound_params(raw: dict) -> CompoundParams:
    return CompoundParams(
        offset_s=_unwrap(raw["offset_s"]),
        deg_s_per_lap=_unwrap(raw["deg_s_per_lap"]),
        cliff_lap=int(_unwrap(raw["cliff_lap"])),
        cliff_s_per_lap2=_unwrap(raw["cliff_s_per_lap2"]),
        warmup_s=_unwrap(raw["warmup_s"]),
        wet_penalty_s=tuple(_unwrap(v) for v in raw["wet_penalty_s"]),
    )


def load_params(track: str, mode: Mode = "f1") -> TrackParams:
    """Load TrackParams for `track` (looks up data/params/{track}.json)."""
    path = DATA_DIR / f"{track}.json"
    raw = json.loads(path.read_text())

    compounds = {name: _compound_params(c) for name, c in raw["compounds"].items()}

    kwargs = dict(
        track=raw["track"],
        laps=int(_unwrap(raw["laps"])),
        base_lap_s=_unwrap(raw["base_lap_s"]),
        compounds=compounds,
        fuel_start_kg=_unwrap(raw["fuel_start_kg"]),
        fuel_burn_kg_per_lap=_unwrap(raw["fuel_burn_kg_per_lap"]),
        fuel_s_per_kg=_unwrap(raw["fuel_s_per_kg"]),
        pit_loss_s=_unwrap(raw["pit_loss_s"]),
        pit_loss_sc_s=_unwrap(raw["pit_loss_sc_s"]),
        sc_lap_factor=_unwrap(raw["sc_lap_factor"]),
        vsc_lap_factor=_unwrap(raw["vsc_lap_factor"]),
        p_sc_per_lap=_unwrap(raw["p_sc_per_lap"]),
        p_vsc_per_lap=_unwrap(raw["p_vsc_per_lap"]),
        sc_len_laps=tuple(_unwrap(v) for v in raw["sc_len_laps"]),
        p_rain_race=_unwrap(raw["p_rain_race"]),
        noise_sd_s=_unwrap(raw["noise_sd_s"]),
        allocation={k: int(_unwrap(v)) for k, v in raw["allocation"].items()},
        mode="f1",
    )

    if mode == "endurance":
        endurance = raw.get("endurance", {})
        tank_kg = _unwrap(endurance.get("tank_kg", kwargs["fuel_start_kg"]))
        refuel_kg_per_s = _unwrap(endurance.get("refuel_kg_per_s", 9.0))
        kwargs["mode"] = "endurance"
        kwargs["tank_kg"] = tank_kg
        kwargs["refuel_kg_per_s"] = refuel_kg_per_s
        kwargs["fuel_start_kg"] = tank_kg

    return TrackParams(**kwargs)


def load_param_samples(track: str) -> list[TrackParams]:
    """Load uncertainty samples for the fairness test. Falls back to 5 hand-perturbed copies."""
    samples_path = DATA_DIR / f"{track}_samples.json"
    if samples_path.exists():
        raw_list = json.loads(samples_path.read_text())
        samples = []
        for raw in raw_list:
            compounds = {name: _compound_params(c) for name, c in raw["compounds"].items()}
            samples.append(
                TrackParams(
                    track=raw["track"],
                    laps=int(_unwrap(raw["laps"])),
                    base_lap_s=_unwrap(raw["base_lap_s"]),
                    compounds=compounds,
                    fuel_start_kg=_unwrap(raw["fuel_start_kg"]),
                    fuel_burn_kg_per_lap=_unwrap(raw["fuel_burn_kg_per_lap"]),
                    fuel_s_per_kg=_unwrap(raw["fuel_s_per_kg"]),
                    pit_loss_s=_unwrap(raw["pit_loss_s"]),
                    pit_loss_sc_s=_unwrap(raw["pit_loss_sc_s"]),
                    sc_lap_factor=_unwrap(raw["sc_lap_factor"]),
                    vsc_lap_factor=_unwrap(raw["vsc_lap_factor"]),
                    p_sc_per_lap=_unwrap(raw["p_sc_per_lap"]),
                    p_vsc_per_lap=_unwrap(raw["p_vsc_per_lap"]),
                    sc_len_laps=tuple(_unwrap(v) for v in raw["sc_len_laps"]),
                    p_rain_race=_unwrap(raw["p_rain_race"]),
                    noise_sd_s=_unwrap(raw["noise_sd_s"]),
                    allocation={k: int(_unwrap(v)) for k, v in raw["allocation"].items()},
                )
            )
        return samples

    base = load_params(track)
    factors = (0.8, 0.9, 1.0, 1.1, 1.2)
    offsets = (-1.0, -0.5, 0.0, 0.5, 1.0)
    samples = []
    for factor, pit_offset in zip(factors, offsets):
        compounds = {
            name: CompoundParams(
                offset_s=c.offset_s,
                deg_s_per_lap=c.deg_s_per_lap * factor,
                cliff_lap=c.cliff_lap,
                cliff_s_per_lap2=c.cliff_s_per_lap2,
                warmup_s=c.warmup_s,
                wet_penalty_s=c.wet_penalty_s,
            )
            for name, c in base.compounds.items()
        }
        samples.append(
            TrackParams(
                track=base.track,
                laps=base.laps,
                base_lap_s=base.base_lap_s,
                compounds=compounds,
                fuel_start_kg=base.fuel_start_kg,
                fuel_burn_kg_per_lap=base.fuel_burn_kg_per_lap,
                fuel_s_per_kg=base.fuel_s_per_kg,
                pit_loss_s=base.pit_loss_s + pit_offset,
                pit_loss_sc_s=base.pit_loss_sc_s,
                sc_lap_factor=base.sc_lap_factor,
                vsc_lap_factor=base.vsc_lap_factor,
                p_sc_per_lap=base.p_sc_per_lap,
                p_vsc_per_lap=base.p_vsc_per_lap,
                sc_len_laps=base.sc_len_laps,
                p_rain_race=base.p_rain_race,
                noise_sd_s=base.noise_sd_s,
                allocation=base.allocation,
                mode=base.mode,
                tank_kg=base.tank_kg,
                refuel_kg_per_s=base.refuel_kg_per_s,
            )
        )
    return samples
