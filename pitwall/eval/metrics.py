"""STUB (BR0) — owner SIM replaces/extends in SIM8. Working now: means + 95% CI (mean +/- 1.96*SE)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"


def _ci(values: np.ndarray) -> list[float]:
    mean = float(np.mean(values))
    se = float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0
    return [mean, mean - 1.96 * se, mean + 1.96 * se]


def _stats(df: pd.DataFrame) -> dict:
    ours = df[df.car == "rollout"].set_index("seed")
    gain_vs: dict[str, list[float]] = {}
    win_rate_vs: dict[str, float] = {}
    for other in ("pirelli", "rules"):
        other_df = df[df.car == other].set_index("seed")
        common = ours.index.intersection(other_df.index)
        if len(common) == 0:
            gain_vs[other] = [0.0, 0.0, 0.0]
            win_rate_vs[other] = 0.0
            continue
        fair = ~(ours.loc[common, "dnf"].to_numpy() | other_df.loc[common, "dnf"].to_numpy())
        gain = (other_df.loc[common, "finish_s"].to_numpy() - ours.loc[common, "finish_s"].to_numpy())[fair]
        gain_vs[other] = _ci(gain) if len(gain) else [0.0, 0.0, 0.0]
        win_rate_vs[other] = float(np.mean(gain > 0)) if len(gain) else 0.0

    oracle_df = df[df.car == "oracle"].set_index("seed")
    pirelli_df = df[df.car == "pirelli"].set_index("seed")
    common = ours.index.intersection(oracle_df.index).intersection(pirelli_df.index)
    oracle_share = 0.0
    if len(common):
        denom = pirelli_df.loc[common, "finish_s"].mean() - oracle_df.loc[common, "finish_s"].mean()
        if denom:
            oracle_share = float(
                (pirelli_df.loc[common, "finish_s"].mean() - ours.loc[common, "finish_s"].mean()) / denom
            )

    return {
        "gain_vs": gain_vs,
        "win_rate_vs": win_rate_vs,
        "oracle_share": oracle_share,
        "n_races": int(df["seed"].nunique()),
    }


def _block(df: pd.DataFrame) -> dict:
    block = _stats(df)
    by_tag: dict[str, dict] = {}
    for tag in ("dry", "wet", "chaotic"):
        tagged = df[df["tags"].str.contains(tag, na=False)]
        if not tagged.empty:
            by_tag[tag] = _stats(tagged)
    block["by_tag"] = by_tag
    return block


def summarise() -> dict:
    """Read results/eval_*.parquet, write results/summary.json (Section 3 schema)."""
    files = sorted(RESULTS_DIR.glob("eval_*.parquet")) + sorted(RESULTS_DIR.glob("mismatch_*.parquet")) + \
        sorted(RESULTS_DIR.glob("rain_sweep_*.parquet"))
    if not files:
        raise FileNotFoundError(f"no eval_*.parquet / mismatch_*.parquet / rain_sweep_*.parquet files in {RESULTS_DIR}")
    all_df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    summary: dict = {}

    main_df = all_df[all_df["test"] == "main"]
    for mode in sorted(main_df["mode"].unique()):
        summary[mode] = {}
        for track in sorted(main_df.loc[main_df["mode"] == mode, "track"].unique()):
            track_df = main_df[(main_df["mode"] == mode) & (main_df["track"] == track)]
            summary[mode][track] = _block(track_df)

    mismatch_df = all_df[all_df["test"] == "mismatch"]
    if not mismatch_df.empty:
        summary["mismatch"] = {
            track: _block(mismatch_df[mismatch_df["track"] == track])
            for track in sorted(mismatch_df["track"].unique())
        }

    rain_df = all_df[all_df["test"] == "rain_sweep"]
    rain_sweep = []
    for rain_prob in sorted(rain_df["rain_prob"].unique()):
        stats = _stats(rain_df[rain_df["rain_prob"] == rain_prob])
        rain_sweep.append({"rain_prob": float(rain_prob), "gain_vs_pirelli": stats["gain_vs"]["pirelli"][0]})
    summary["rain_sweep"] = rain_sweep

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary
