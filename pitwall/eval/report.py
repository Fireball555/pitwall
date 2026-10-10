"""Write the README's Results section straight from results/ (so the numbers can never go stale).

    python -m pitwall.eval.report          # after pitwall.eval.batch + pitwall.eval.metrics + the replays

Replaces everything between <!-- results:start --> and <!-- results:end --> in README.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pitwall.eval.metrics import RESULTS, paired, summarise

ROOT = Path(__file__).resolve().parents[2]
NAMES = {"bahrain": "Bahrain", "monza": "Monza", "zandvoort": "Zandvoort", "singapore": "Singapore"}


def s(x: float, d: int = 1) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x):.{d}f}"


def ci(g) -> str:
    return f"{s(g[0])} s ({s(g[1])} to {s(g[2])})"


def wet_share(track: str) -> float | None:
    """Share of the average gain on the pre-race plan that comes from wet races."""
    f = RESULTS / f"eval_f1_{track}.parquet"
    if not f.exists():
        return None
    w = paired(pd.read_parquet(f))
    g = w["pirelli"] - w["rollout"]
    total = g.sum()
    return float(g[w["tag"] == "wet"].sum() / total) if total > 0 and "tag" in w else None


def build() -> str:
    S = summarise()
    main = S.get("main", {}).get("f1", {})
    lines = [
        "1000 random races per track (F1 rules), 500 for endurance and the fairness test. All four cars race the same "
        "weather, safety cars and lap noise. \"Gain\" is how many seconds earlier PitWall finished. The 95% interval is a "
        "bootstrap over simulated races: it covers simulation noise only, assuming our fitted tyre, rain and safety-car "
        "numbers are right. Full numbers: `results/summary.json`, or the app's **Proof** tab. This section is written by "
        "`python -m pitwall.eval.report`.",
        "",
        "| Track (F1) | Gain vs pre-race plan | Won | Gain vs simple rules | Won |",
        "| --- | --- | --- | --- | --- |",
    ]
    for t, name in NAMES.items():
        m = main.get(t)
        if m:
            lines.append(f"| {name} | {ci(m['gain_vs']['pirelli'])} | {m['win_rate_vs']['pirelli']:.0%} | "
                         f"{ci(m['gain_vs']['rules'])} | {m['win_rate_vs']['rules']:.0%} |")
    lines += ["", "What this shows, honestly:"]
    wet = {t: m["by_tag"].get("wet", {}).get("gain_vs", {}).get("pirelli", [None])[0] for t, m in main.items()}
    dry = {t: m["by_tag"].get("dry", {}).get("gain_vs", {}).get("pirelli", [None])[0] for t, m in main.items()}
    shares = {t: wet_share(t) for t in main}
    wv = [v for v in wet.values() if v is not None]
    if wv:
        lines.append(f"- **The advantage comes mostly from changing conditions.** In wet races PitWall gains {s(min(wv))} to "
                     f"{s(max(wv))} s on the pre-race plan; in dry races " +
                     ", ".join(f"{s(v)} s at {NAMES[t]}" for t, v in dry.items() if v is not None) + ". Wet races supply " +
                     ", ".join(f"{v:.0%} of the {NAMES[t]} gain" for t, v in shares.items() if v is not None) + ".")
    sweep = sorted(S.get("rain_sweep", []), key=lambda r: r["rain_prob"])
    if sweep:
        lines.append(f"- **More rain, bigger advantage** (Zandvoort, same 200 races at each rain chance): "
                     f"{s(sweep[0]['gain_vs_pirelli'])} s with no rain, {s(sweep[-1]['gain_vs_pirelli'])} s at a "
                     f"{sweep[-1]['rain_prob']:.0%} rain chance.")
    if "monza" in main:
        r = main["monza"]
        lines.append(f"- **Monza vs the simple rules:** {ci(r['gain_vs']['rules'])} on average, but the simple rules finish "
                     f"ahead in {1 - r['win_rate_vs']['rules']:.0%} of races. Monza's three dry tyres come out identical "
                     "(our soft-never-slower constraint merges them), so there is little to optimise.")
    mm = S.get("mismatch", {}).get("f1", {})
    if mm:
        lines.append("- **Fairness test** (true tyre wear, compound pace and pit loss secretly different from what every "
                     "strategist believes; rain and safety-car rates unchanged): " +
                     ", ".join(f"{s(v['gain_vs']['pirelli'][0])} s at {NAMES[t]}" for t, v in mm.items()) + ".")
    en = S.get("main", {}).get("endurance", {})
    if en:
        lines.append("- **Endurance mode** (fuel calls too): " + ", ".join(
            f"{s(v['gain_vs']['pirelli'][0])} s at {NAMES[t]}" for t, v in en.items()) +
            " vs the pre-race plan. Part of the Singapore number is the fixed plans' late fuel stop.")
    lines += [
        "- The pre-race plan never fits slicks on a wet track, but it does not see the rain radar PitWall uses, so part of "
        "the wet gain is information, not cleverness.",
        "- At Singapore the assumed pre-race plan and the simple rules often make the same stops, so both baselines score alike.",
        "",
        "**Real 2023 races.** PitWall replaced one midfield driver; we compare it with that driver's real pit stops run "
        "through the same simulator (the fair comparison: same model for both).",
        "",
        "| Race | Driver | Real finish | Real stops in our sim | PitWall |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in sorted(RESULTS.glob("replay_*_*.json")):
        parts = f.stem.split("_")
        if len(parts) != 3:
            continue
        r = json.loads(f.read_text())
        san = r.get("sanity", {})
        lines.append(f"| {NAMES.get(r['track'], r['track'])} | {r['driver']} | P{r['real_finish_pos']} | "
                     f"P{san.get('real_strategy_pos', '?')} | **P{r['our_finish_pos']}** |")
    lines += ["", "The tyre numbers were fitted on these same races, so the replays are a demonstration, not proof of a "
              "real-world gain. Our simulator runs the real strategies faster than they really went, so we only compare "
              "PitWall with the real stops inside the same simulator."]
    acc = ROOT / "data" / "accuracy.json"
    if acc.exists():
        a = json.loads(acc.read_text())
        lines += ["", "**Lap-time model on a race it has never seen** (fit on 2022, predict 2023, "
                  "`python -m pitwall.data.accuracy`): " + ", ".join(
                      f"{NAMES[t]} {v['mae_s']:.2f} s per lap (skill {s(v['skill'], 2)})" for t, v in a.items()) +
                  ". Skill compares with a flat line: Bahrain is genuinely predictive; Monza and Zandvoort predict the "
                  "average well but not the shape within a stint; Singapore does not transfer from 2022 (a wet race) to "
                  "2023, so its numbers rest on the 2023 race alone."]
    return "\n".join(lines)


def main() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text()
    a, b = "<!-- results:start -->", "<!-- results:end -->"
    if a not in text:
        raise SystemExit("README.md has no <!-- results:start --> marker")
    head, rest = text.split(a, 1)
    _, tail = rest.split(b, 1)
    readme.write_text(f"{head}{a}\n{build()}\n{b}{tail}")
    print("README results section updated")


if __name__ == "__main__":
    main()
