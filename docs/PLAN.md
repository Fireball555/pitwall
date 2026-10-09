# PitWall — CommitCon Execution Plan

Oct 9, 2026 · Smaran (lead). Source of truth: the shared PitWall doc; this file is a frozen copy for the AIs.

## 1. Locked scope

We build **PitWall**: a race strategist that decides every lap whether to pit, which tyre to fit and (in endurance mode) how much fuel to add. It is calibrated on real 2023 F1 data, and we prove it beats simpler strategies, even when its own numbers are slightly wrong. Problem statement: Third Year, Non Circuit #5, *The Impossible Pit Stop*.

**Team**

| Role code | Role | Person | AI | Machine duties |
| --- | --- | --- | --- | --- |
| BR | Brain & Proof (lead) | Smaran (@Fireball555) · Alienware, Ubuntu | Claude Code (Pro); Antigravity as backup | Runs every big batch on the Alienware |
| SIM | Simulator & Replay | Ashwin (@Iamashwink) · Mac | Antigravity | — |
| DAT | Data & Baselines | Dharshini (@DharshiniShanmugam16) · Asus, Windows | Antigravity | FastF1 downloads |
| UI | Screens & Pitch | Pranesh (@tonorz) · Mac | Antigravity | Records the backup video |

**The demo is three screens, presented live in an online meeting from the Alienware**

1. **Live race.** One race, four identical cars, same weather and safety cars; only the strategy differs. A toggle switches between F1 mode and endurance mode. A feed explains every call, e.g. "Lap 31: Safety car, pitting for HARD + 40 kg fuel saves 9.1 s".
2. **Proof.** Each track raced 1,000 times with random conditions. Key numbers and charts for both modes, plus the fairness test: does it still win when its numbers are off?
3. **Real races.** An animated 20-car race: 19 cars replay their real 2023 laps and ours replaces a real midfield driver. Then real finishing position vs ours. F1 mode only.

**Two race modes (both core)**

|  | F1 mode (default) | Endurance mode |
| --- | --- | --- |
| Rules | 2023 F1: no refuelling, two dry compounds required | Small tank, refuelling at stops |
| Fuel decision | None; fuel only burns off as weight | How much fuel to add at each stop |
| Data | All real | Tyres and pit loss real; tank size and refuel speed assumed (2009-era F1) |
| Screen 1 | Yes | Yes (toggle) |
| Screen 2 | 4 tracks | 2 tracks (Bahrain, Singapore) |
| Screen 3 | Yes | No |

**The four cars**

| Car colour | Strategy | Built by | Knows the future? |
| --- | --- | --- | --- |
| Purple | Pirelli's published pre-race plan, followed blindly | DAT | No |
| Orange | Simple rules (pit at X% wear, inters when wet) | DAT | No |
| Cyan | **Ours**: Monte Carlo rollout, re-thinks every lap | BR | No |
| Grey (dashed) | Oracle: our strategist, but it sees the real future | BR | Yes |

**Locked decisions**

- Data: 2023 season via FastF1. Safety car rates use 2018–2023.
- Tracks: Bahrain (57 laps, high wear), Monza (51, low wear, Alternative Tyre Allocation weekend), Zandvoort (72, rain), Singapore (62, safety cars).
- Lap time = track base + compound offset + tyre wear + fuel weight + wet penalty + noise. One global model, per-track parameters fitted from data.
- Tyre inventory per weekend: sampled from 2023 real usage patterns.
- Ghost cars: no traffic between the four cars. Traffic exists only in the real-race replay.
- Strategist: 200 imagined futures per option, every lap, numpy-vectorised, the same futures for every option.
- **Fairness test:** in some evaluation races the true tyre and pit numbers are drawn from the uncertainty of our fit, while every strategy still plans with the normal numbers.
- Stack: **Python 3.12** (Ubuntu 24.04's default), numpy, pandas, FastF1, Streamlit, Plotly, pytest.

**Out of scope:** two-car teams, a full season, overtaking between the four ghost cars, any frontend other than Streamlit.

## 2. How it fits together

```text
Architecture (text version of the diagram)

FastF1 (2023 laps, tyres, pits, weather; 2018-23 SC data)    Pirelli 2023 race previews
                     \                                        /
        DAT data pipeline: clean, fit, pit loss, SC + rain rates
        writes params (+200 uncertainty samples), Pirelli plans, real-race files
              | true params                         | plans + belief params
              v                                     v
   SIM simulator  --- Observation --->   Strategies (the 4 cars)
   sample_scenario, lap_time (numpy),      DAT baselines: Pirelli plan, Rules
   run_race (4 ghost cars), F1 +          BR brain: Rollout (200 futures), Oracle
   endurance; lap times use TRUE params <--- Decision ---
              |
   +----------+--------------------+---------------------------+
   v                               v                           v
 BR batch evaluation        SIM one race log            SIM real-race replay
 (F1, endurance, fairness)  (one seed, 4 cars)          (19 recorded cars + ours)
   v                               v                           v
 SIM metrics -> summary.json  UI Screen 1: Live race    UI Screen 3: Real races (20 cars)
   v
 UI Screen 2: Proof
```

Data flows one way: real data → parameters → simulator and strategies → three outputs → three screens. The simulator and strategies talk only through `Observation` and `Decision`, which is what keeps the strategist honest about not seeing the future. Lap times always use the true params, while strategies plan with their belief params; in the fairness test the two differ on purpose.

## 3. Contract and handoffs

Every output a role produces has a named consumer, a deadline and a stand-in until it lands. That is what lets four AIs work in parallel. BR commits `pitwall/types.py`, the mocks and working stubs at H0. After that the contract changes only through a PR labelled `contract` that all four approve.

```python
# pitwall/types.py — THE CONTRACT (Python 3.12). Do not edit without a 'contract' PR.
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Protocol
import numpy as np

COMPOUNDS: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")  # index = compound id
DRY = ("SOFT", "MEDIUM", "HARD")
GREEN, VSC, SC = 0, 1, 2   # track status codes
Mode = Literal["f1", "endurance"]

@dataclass(frozen=True)
class CompoundParams:
    offset_s: float            # pace vs fresh MEDIUM (SOFT negative)
    deg_s_per_lap: float       # linear wear, s lost per lap of tyre age
    cliff_lap: int             # tyre age where the cliff starts
    cliff_s_per_lap2: float    # quadratic loss after the cliff
    warmup_s: float            # extra time on the first lap of a set
    wet_penalty_s: tuple[float, float, float]  # penalty at wetness 0.0, 0.5, 1.0 (linear between)

@dataclass(frozen=True)
class TrackParams:
    track: str                 # 'bahrain' | 'monza' | 'zandvoort' | 'singapore' | 'mock'
    laps: int
    base_lap_s: float          # dry, fresh MEDIUM, empty tank
    compounds: dict[str, CompoundParams]
    fuel_start_kg: float       # F1 mode: 110.0 (2023 max race fuel)
    fuel_burn_kg_per_lap: float
    fuel_s_per_kg: float       # fitted; sanity range 0.02-0.04
    pit_loss_s: float          # green-flag pit loss (tyres only)
    pit_loss_sc_s: float       # pit loss under SC/VSC
    sc_lap_factor: float       # SC lap time / green lap time
    vsc_lap_factor: float
    p_sc_per_lap: float
    p_vsc_per_lap: float
    sc_len_laps: tuple[int, int]
    p_rain_race: float
    noise_sd_s: float
    allocation: dict[str, int] # sets per compound at weekend start
    mode: Mode = "f1"
    tank_kg: float = 110.0     # endurance mode: assumed smaller tank
    refuel_kg_per_s: float = 9.0  # endurance mode: assumed, ~2009-era F1 rigs

@dataclass(frozen=True)
class Scenario:
    """One random race world. All four cars race the SAME scenario."""
    track: str
    seed: int
    laps: int
    status: np.ndarray         # (laps,) int8 GREEN/VSC/SC per lap
    wetness: np.ndarray        # (laps,) float 0..1
    noise: np.ndarray          # (laps,) seconds, identical for every car
    forecast: np.ndarray       # (laps, laps): forecast[l, k] = P(rain on lap k) known after lap l
    tags: tuple[str, ...]      # subset of ('dry', 'wet', 'chaotic')

@dataclass(frozen=True)
class TyreSet:
    set_id: int
    compound: str
    age_laps: int              # laps used before the race

@dataclass
class CarState:
    name: str                  # 'pirelli' | 'rules' | 'rollout' | 'oracle'
    lap: int                   # laps completed (0 = on the grid)
    total_time_s: float
    compound: str              # '' before the start-tyre choice
    tyre_age: int
    fuel_kg: float
    inventory: list[TyreSet]   # sets still available (not the fitted one)
    compounds_used: set[str]
    pit_stops: int = 0
    dnf: bool = False

@dataclass(frozen=True)
class Action:
    pit: bool
    set_id: int | None = None  # required when pit=True (lap 0: the start set)
    fuel_kg: float = 0.0       # fuel to add; endurance mode only

STAY = Action(pit=False)

@dataclass(frozen=True)
class Observation:
    """Everything a FAIR strategy may see after lap `lap`. No future truth, no true params."""
    lap: int
    laps_total: int
    status: int                # status of the lap about to be driven
    wetness: float
    rain_forecast: np.ndarray  # (laps_total - lap,) P(rain) per remaining lap

@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str                # one line for the live feed
    expected_s: dict[str, float] = field(default_factory=dict)  # option label -> expected finish time

class Strategy(Protocol):
    name: str
    def reset(self, belief: TrackParams, start: CarState) -> None: ...  # belief = the numbers it PLANS with
    def decide(self, car: CarState, obs: Observation) -> Decision: ...

@dataclass(frozen=True)
class LapRecord:
    car: str; lap: int; lap_time_s: float; total_time_s: float
    compound: str; tyre_age: int; fuel_kg: float; fuel_added_kg: float; pitted: bool
    status: int; wetness: float; reason: str
    expected_json: str         # json.dumps(Decision.expected_s), '' when no decision
```

**Functions (exact names) and who needs them by when**

| Function | Owner | Needed by | Gate | Stand-in until then |
| --- | --- | --- | --- | --- |
| `pitwall.params.load_params(track, mode="f1") -> TrackParams` | DAT | all | H0 | Scaffold version reading `mock.json` |
| `pitwall.params.load_param_samples(track) -> list[TrackParams]` | DAT | BR (fairness test) | H13 | 5 hand-perturbed copies of mock |
| `pitwall.sim.engine.lap_time(cid, age, fuel, wet, status, noise, P)` | SIM | BR rollout, SIM | CP1 | Scaffold: base + linear wear |
| `pitwall.sim.scenario.sample_scenario(P, seed, rain_prob=None, sc_mult=1.0)` | SIM | BR eval, UI Screen 1 | CP1 | Scaffold: all green, dry |
| `pitwall.sim.scenario.sample_futures(belief, obs, n, rng) -> dict[str, ndarray]` | SIM | BR rollout | CP1 | Scaffold: all green, dry |
| `pitwall.sim.inventory.sample_inventory(P, rng) -> list[TyreSet]` | SIM | BR eval, UI | CP1 | Scaffold: fixed 6 sets |
| `pitwall.sim.engine.step(car, action, scn, P_true)` / `observe(car, scn)` | SIM | `run_race`, replay | CP1 | Scaffold versions |
| `pitwall.sim.race.run_race(scn, strategies, P_true, beliefs, inventory) -> (DataFrame, dict)` | SIM | BR eval, UI Screen 1 | CP1 | `results/mock_race_log.parquet` |
| `pitwall.strategy.rules.RulesStrategy` + `rules_config.py` | DAT | BR (numpy twin), everyone | CP1 | Scaffold: pit at half distance |
| `pitwall.strategy.pirelli.PirelliStrategy` | DAT | BR eval | CP1 (mock plan), CP2 (real) | Scaffold: one stop M → H |
| `pitwall.strategy.rollout.RolloutStrategy`, `oracle.Oracle(scn)` | BR | SIM replay, BR eval, UI | CP2 | `RulesStrategy` |
| `pitwall.eval.batch.evaluate(track, mode, n, seed0, test)` | BR | SIM metrics | H13 | `results/mock_eval.parquet` |
| `pitwall.eval.metrics.summarise() -> results/summary.json` | SIM | UI Screen 2, deck | H15 | `results/mock_summary.json` |
| `pitwall.sim.replay.replay(track, driver, strategy)` | SIM | UI Screen 3, deck | H14 | `results/mock_replay.json` |

**File handoffs (all small, all committed)**

| File | Producer | Consumer | Due | Mock until then |
| --- | --- | --- | --- | --- |
| `data/params/mock.json` | BR (scaffold) | all | H0 | — |
| `data/params/{track}.json` (with an `endurance` block) | DAT | all | CP2 | `mock.json` |
| `data/params/{track}_samples.json` (200 draws) | DAT | BR | H13 | 5 copies |
| `data/pirelli/{track}.json` | DAT | DAT's Pirelli strategy | CP2 | `mock.json` plan |
| `data/inventory_stats.json` | DAT | SIM | CP2 | built-in default |
| `data/real/{track}_{laps,status,weather,results}.parquet` | DAT | SIM replay | **H9** | none; SIM builds replay on Bahrain first |
| `results/model_accuracy.json` | DAT | UI, deck | H14 | mock |
| `results/eval_{mode}_{track}.parquet`, `rain_sweep.parquet`, `mismatch_{track}.parquet` | BR | SIM metrics | H14 | `mock_eval.parquet` |
| `results/summary.json` | SIM | UI, deck | H15 | `mock_summary.json` |
| `results/replay_{track}_{driver}.json` + `replay_index.json` | SIM | UI, deck | H14 | `mock_replay.json` |
| `results/demo_{mode}_{track}.parquet` | UI (via `run_race`) | UI | Freeze | — |
| data/real/{track}\_offsets.json | DAT | SIM replay | H12 | offset = driver's median clean lap minus the field median |

**Schemas (UI codes against these from H0)**

```text
race log (run_race DataFrame, parquet): one row per (car, lap) = LapRecord fields

results/eval_*.parquet:  track, mode, test ('main'|'rain_sweep'|'mismatch'), seed, rain_prob,
                         sample_id (-1 unless mismatch), car, finish_s, dnf, pit_stops, tags

results/summary.json:    { "<mode>": { "<track>": {
                             "gain_vs": {"pirelli": [mean, lo95, hi95], "rules": [...]},
                             "win_rate_vs": {"pirelli": 0.0, "rules": 0.0},
                             "oracle_share": 0.0,
                             "by_tag": {"dry": {...}, "wet": {...}, "chaotic": {...}},
                             "n_races": 1000 } },
                           "mismatch": { "<track>": { same keys } },
                           "rain_sweep": [ {"rain_prob": 0.0, "gain_vs_pirelli": 0.0}, ... ] }

results/replay_*.json:   { track, driver, real_grid, real_finish_pos, our_finish_pos, real_time_s, our_time_s,
                           "laps": [ {"lap": 1, "order": ["VER", ..., "OURS"], "elapsed": {"VER": 97.4, ...}} ],
                           "ours":  [ {"lap", "compound", "tyre_age", "pitted", "reason"} ],
                           "real_driver": [ {"lap", "compound", "pitted"} ],
                           "sanity": {"real_strategy_pos": 0, "real_pos": 0} }
```

## 4. Repo structure and ownership

Every file has exactly one owning role. An AI edits only its role's files, so merge conflicts become nearly impossible. Where a folder is shared, ownership is per file.

```text
pitwall/                          # repo root
├── AGENTS.md  CLAUDE.md  GEMINI.md     # AI rules (Section 6)                    BR
├── README.md                     # setup + how to run the 3 screens               UI
├── requirements.txt  .gitignore  .gitattributes                                  BR
├── docs/PLAN.md                  # frozen copy of this document                   BR
├── docs/roles/{BR,SIM,DAT,UI}.md # Sections 7-10, one per role                    BR
├── pitwall/
│   ├── types.py                  # THE CONTRACT                                   BR
│   ├── params.py                 # load_params, load_param_samples                DAT
│   ├── data/                     # fetch, clean, fit, samples, real-race extract  DAT
│   ├── sim/                      # engine, scenario, inventory, race, replay      SIM
│   ├── strategy/rules_config.py  # thresholds shared by both rules versions       DAT
│   ├── strategy/rules.py, pirelli.py, real.py   # baselines + replay's RealStrategy DAT
│   ├── strategy/rollout_core.py, rollout.py, oracle.py                             BR
│   ├── eval/batch.py, eval/fairness.py   # batch runs + fairness test             BR
│   └── eval/metrics.py           # results -> summary.json                        SIM
├── app/                          # Streamlit: Home + 3 pages, style.py            UI
├── data/                         # params, samples, pirelli, real/ (all small)    DAT (mock.json: BR)
├── results/                      # eval_* + mocks: BR | summary, replay_*: SIM | demo_*: UI | model_accuracy: DAT
├── pitch/                        # deck, demo script, Q&A sheet, backup video     UI
├── tests/
│   ├── test_contract.py          # types import, every mock loads                 BR
│   ├── test_data.py, test_baselines.py                                             DAT
│   ├── test_sim.py, test_replay.py, test_metrics.py                                SIM
│   ├── test_rollout.py, test_eval.py                                               BR
│   └── test_app.py               # every page imports and renders on mocks        UI
├── cache/                        # FastF1 cache: NEVER committed
└── .github/workflows/ci.yml      # pytest on every PR                             BR
```

| Role | Person | Owns | Reads but never edits |
| --- | --- | --- | --- |
| BR — Brain & Proof (lead) | Smaran | `types.py`, rollout/oracle files, `eval/batch.py`, `eval/fairness.py`, repo config, docs, CI; merges to `main` | everything else |
| SIM — Simulator & Replay | Ashwin | `pitwall/sim/`, `eval/metrics.py`, `results/summary.json`, `results/replay_*` | `types.py`, `data/`, strategies |
| DAT — Data & Baselines | Dharshini | `pitwall/data/`, `params.py`, `data/`, `rules_config.py`, `rules.py`, `pirelli.py`, `real.py`, `results/model_accuracy.json` | `types.py`, `sim/` |
| UI — Screens & Pitch | Pranesh | `app/`, `pitch/`, `README.md`, `results/demo_*` | everything else |

## 5. GitHub workflow and rules

Nobody pushes to `main`. Everything goes through a short-lived branch and a small pull request (PR) that passes CI, and Smaran merges it within 15 minutes.

**One-time setup (Smaran, H0, about 20 minutes)**

1. Create the repo `pitwall` and add the three teammates as collaborators.
2. Push the H0 scaffold (BR0) and tag it `h0`.
3. Turn on branch protection for `main` (require a PR and green CI). If your plan doesn't offer it for a private repo, enforce it by convention: only Smaran merges.
4. Create one GitHub issue per task ID in Sections 7–10 and assign each to its owner.

**Every member, once**

```bash
# Linux / macOS
git clone https://github.com/<owner>/pitwall.git && cd pitwall
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pytest -q

# Windows (PowerShell)
git clone https://github.com/<owner>/pitwall.git; cd pitwall
py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt; pytest -q
```

`.gitattributes` holds `* text=auto eol=lf`, so Windows and Linux line endings never create fake conflicts.

**The loop for every task (repeat all day)**

```bash
git switch main && git pull                 # start from fresh main
git switch -c sim/lap-time                  # <role code>/<short-task-name>: br/ sim/ dat/ ui/
# ... work with your AI on ONE task ...
pytest -q                                   # all green before committing
git add -p                                  # read every hunk the AI wrote
git commit -m "feat(sim): vectorised lap_time (SIM1)"
git fetch && git rebase origin/main && pytest -q
git push -u origin sim/lap-time
gh pr create --fill                         # or open the PR on github.com
```

**Rules**

| Rule | Why |
| --- | --- |
| A branch lives at most 2 hours; one task ID per branch | Small PRs merge cleanly and review fast |
| A PR touches only your role's files (Section 4) | No conflicts between AIs |
| Under \~400 changed lines, data files excluded | Reviewable in 5 minutes |
| `pytest -q` green locally and in CI before merge | `main` always runs, so the demo always runs |
| Commit format `type(area): what (TaskID)`; types `feat` `fix` `test` `data` `docs` `chore` | History reads as a log of the 24 hours |
| PR description: what changed, how it was tested, a screenshot for UI work | Review without running it |
| Contract change = PR labelled `contract`, approved by all four, merged only at a checkpoint | Everyone's code depends on it |
| Squash-merge; delete the branch after merge | One clean commit per task |
| `git pull --rebase` on `main` at least every hour | Integration breaks show up early |
| Never commit `cache/`, `.venv/`, `.env`, keys, or any file over 5 MB | The FastF1 cache alone is hundreds of MB |
| Never `git push --force` to `main` | One mistake can wipe teammates' work |
| Conflict in a file you don't own: stop and tell the owner | It means your AI edited something it shouldn't have |

**Merge authority.** Smaran merges. If he's busy for more than 15 minutes, any member may merge a green PR that doesn't touch the contract.

**Tags.** `h0`, `cp1`, `cp2`, `freeze`, `v1.0`. The demo runs from a tag, never from a branch.

**CI** (`.github/workflows/ci.yml`): Python 3.12, `pip install -r requirements.txt`, `pytest -q -m "not network and not slow"`, under 3 minutes. Tests that download data carry `@pytest.mark.network`; tests over 10 s carry `@pytest.mark.slow`.

## 6. Rules for every AI, and how to drive it

Every AI follows the same `AGENTS.md`. Claude Code reads `CLAUDE.md` automatically, which points to `AGENTS.md`. Antigravity users paste the kickoff prompt below at the start of every agent conversation, whatever rules file their version picks up.

```markdown
# AGENTS.md — rules for every AI working on PitWall

## Before you write any code
1. Read, in order: AGENTS.md, docs/PLAN.md sections 1-4, docs/roles/<ROLE>.md, pitwall/types.py.
2. Work on ONE task ID (e.g. SIM2) per conversation. Do not start the next task unasked.
3. Any task estimated over 1 hour: reply with a plan first (files, functions, tests). Wait for approval.

## Boundaries
- Edit ONLY the files your role owns (docs/PLAN.md section 4). Read anything.
- NEVER edit pitwall/types.py. If the contract blocks you, stop and propose the exact change in words.
- Need something another role hasn't delivered? Use its stand-in (docs/PLAN.md section 3). Never build their part.
- No new dependencies. If you need one, say so; BR adds it to requirements.txt.
- Do not run git commit, git push or merge. The human commits after reading your diff.

## Code rules
- Python 3.12, type hints everywhere, the dataclasses from pitwall/types.py.
- Units: seconds, laps, kg; wetness 0..1; track names lowercase; mode is 'f1' or 'endurance'.
- Randomness ONLY via np.random.default_rng(seed) passed in. Never `random` or global np.random.
- Anything called inside rollouts must be vectorised numpy over arrays: no Python loop over futures, np.where instead of if on arrays.
- Strategies see ONLY the Observation and the belief params given to reset(). Only Oracle receives the Scenario.
- Lap times are computed with the TRUE params (P_true); strategies plan with their BELIEF params. Never mix them.
- The team runs Linux, macOS and Windows: use pathlib for every path, and guard multiprocessing entry points with if __name__ == "__main__".
- Files under 300 lines. Docstrings state units. No dead code or debug prints left behind.
- Network (FastF1) only inside pitwall/data. Network tests: @pytest.mark.network. Tests over 10 s: @pytest.mark.slow.
- Never invent data. A value not fitted from data gets "source": "assumed" beside it in the JSON.

## Tests
- Every public function gets at least one test in your role's test files.
- Run `pytest -q` yourself and show the output. Never finish with failing tests.

## When you finish
Reply with: (1) what changed, file by file; (2) how you tested it; (3) anything stubbed or TODO;
(4) a commit message `type(area): what (TaskID)`.
```

**Kickoff prompt (paste at the start of every AI conversation)**

```text
You are working on PitWall, role <BR|SIM|DAT|UI>, task <ID>, on branch <branch>.
Read AGENTS.md, docs/PLAN.md sections 1-4, docs/roles/<ROLE>.md and pitwall/types.py before anything else.
Then do task <ID> only, meeting its "Done when" criteria. Plan first if the task is over 1 hour.
Run pytest -q at the end and show me the output.
```

**How each human drives their AI**

- **One task, one fresh conversation.** Long conversations drift and burn usage.
- **Smaran:** save Claude Code for BR's hard tasks (rollout core, Oracle, fairness test). Do lead chores (merging, small fixes) in Antigravity so the Claude Pro limits last the whole night.
- **Antigravity users:** open the repo folder as the workspace; let the agent run `pytest -q` in its terminal; approve its plan before it writes code.
- **Read every diff** (`git add -p`) before committing. You own your PR, not the AI.
- **Three strikes rule.** If the AI fails the same bug three times, stop: `git stash`, split the task smaller, start a fresh conversation, or ask a teammate.
- **Post blockers in the team chat immediately,** with the task ID. Don't wait for the next checkpoint.

## 7. Role BR — Brain & Proof (Smaran, lead)

**Mission:** build the strategist that makes the decisions, prove it with thousands of races on the Alienware, and keep the team integrated. Claude Code does the hard code here; Antigravity handles lead chores so the Claude Pro limits last.

**Owns:** `pitwall/types.py`, `strategy/rollout_core.py`, `strategy/rollout.py`, `strategy/oracle.py`, `eval/batch.py`, `eval/fairness.py`, `results/eval_*`, mocks, repo config, docs, CI, `tests/test_rollout.py`, `tests/test_eval.py`. **Needs:** SIM's `lap_time`, `sample_futures`, `run_race` (CP1); DAT's `rules_config.py` + `RulesStrategy` (CP1), real params (CP2), param samples (H13). **Delivers:** the scaffold to everyone (H0); `RolloutStrategy` + `Oracle` to SIM's replay and UI (CP2); all evaluation files to SIM's metrics (H14).

**How the rollout strategist decides**

After every lap it lists up to 6 legal options: stay out, or pit for the freshest set of each compound (in endurance mode, each combined with a few fuel amounts). For each option it plays out the rest of the race over the same 200 sampled futures, with later decisions following the rules baseline, and picks the lowest mean finish time. This is *policy rollout* (Bertsekas): under its model it is never worse in expectation than the policy it rolls out.

**Tasks**

1. **BR0 Scaffold** (H0; Claude generates it in this chat, Smaran reviews for 20 minutes, pushes, tags `h0`).
   - `types.py` (Section 3); `data/params/mock.json` with plausible Bahrain-like numbers, every one marked `"assumed"`.
   - Working stubs for every function in Section 3 that already return sensible results, so a full stub race runs from minute one.
   - Mock results files in the exact schemas.
   - `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `docs/PLAN.md`, `docs/roles/*.md`, pinned `requirements.txt`, CI, `.gitignore`, `.gitattributes`, `test_contract.py`.
   - Done when: a fresh clone passes `pytest -q` on Linux and Windows, and `python -m pitwall.sim.race --demo` prints a 4-car finish table.
2. **BR1 Rollout core** (4 h). `rollout_core.simulate_rest(belief, state, futures, first_action) -> ndarray (n,)`:
   - State as arrays over n futures: compound id, age, fuel, elapsed time, dry-compounds-used bitmask, availability mask over inventory sets.
   - One `lap_time` call per lap for all n futures. The rules policy is re-implemented as a numpy twin reading the same `rules_config.py`.
   - Endurance aware: fuel arrays; running dry or a disqualification = +1,000 s.
   - Done when: the twin makes the same choice as DAT's `RulesStrategy` on 500 random states, and one decision at n = 200 takes under 50 ms on the Alienware.
3. **BR2 RolloutStrategy** (1.5 h).
   - One `sample_futures` call per decision; every option scored on the same futures.
   - Pruning: wet compounds only if wetness > 0.1 or forecast rain > 0.2 in the next 10 laps; no pit option if tyre\_age < 3 under green.
   - Hysteresis: pit only if it beats STAY by more than 0.5 s.
   - Lap 0 scores every start set. Fills `expected_s` and a reason with ± standard error, e.g. `Lap 23: SC deployed, pit for HARD saves 8.4 s ± 1.9`.
4. **BR3 Oracle** (1 h). Same as BR2 with n = 1: its single future is the true scenario, and its belief is the true params. Label it "knows the future": a strong reference, not a proven optimum.
5. **BR4 No-peeking test** (0.5 h). Change a scenario's arrays after lap L and re-run; every decision up to lap L must be identical.
6. **BR5 Endurance fuel choices** (1.5 h, with SIM5). Fuel options per pit: enough to finish (if it fits the tank), full tank, half tank. Done when: 50 endurance races at Bahrain finish with zero fuel DNFs for the rollout car.
7. **BR6 Batch runner + fairness test** (2.5 h). `batch.evaluate(track, mode, n, seed0, test)`, using `multiprocessing.Pool(nproc − 2)`:
   - `main`: P\_true = belief = the fitted params.
   - `rain_sweep`: same, with `rain_prob` fixed per batch.
   - `mismatch` (`fairness.py`): P\_true = `samples[seed % 200]`; the three fair cars plan with the fitted params; the Oracle gets P\_true.
   - Seeds 0–999 are reserved for evaluation and never used for tuning. Output follows the Section 3 schema.
8. **BR7 Run everything on the Alienware** (H13–H14, about 1 h wall time).

| Run | Tracks | Races | Feeds |
| --- | --- | --- | --- |
| F1 main | Bahrain, Monza, Zandvoort, Singapore | 4 × 1,000 | Screen 2 headline |
| Endurance main | Bahrain, Singapore | 2 × 500 | Screen 2 endurance panel |
| Fairness (mismatch) | Bahrain, Singapore | 2 × 500 | Screen 2 fairness panel |
| Rain sweep | Zandvoort, rain 0–0.5 in steps of 0.1 | 6 × 200 | Screen 2 line chart |
| Replays (SIM's code) | 4 tracks × midfield drivers | \~32 | Screen 3 |

About 7,200 races at roughly 3 s each is about 6 CPU-hours. The Alienware has 22 threads and 30 GB RAM, so `Pool(20)` finishes everything in about 20 minutes. Start by 04:30.

**Lead duties (about 3 h across the night):** merge PRs within 15 minutes, run each checkpoint, approve contract PRs, keep CI green, make the cut-list calls (Section 14).

**Speed budget:** a full race with all 4 cars under 3 s. If missed: n = 100, or re-plan every 2 laps unless an event happens.

**Never:** read `Scenario` outside `Oracle`; use different futures for different options; tune anything on seeds 0–999.

## 8. Role SIM — Simulator & Replay (Ashwin, Antigravity, Mac)

**Mission:** build the race itself (lap times, weather, safety cars, pit stops, both modes), then the 20-car replay of real races, then turn BR's raw results into the numbers on the Proof screen. Every other role runs on your engine, so correctness and speed beat features.

**Owns:** `pitwall/sim/`, `eval/metrics.py`, `results/summary.json`, `results/replay_*`, `tests/test_sim.py`, `tests/test_replay.py`, `tests/test_metrics.py`. **Needs:** the scaffold (H0); DAT's real params (CP2, a file swap); DAT's real-race files (**H9**) and `RealStrategy`; BR's `RolloutStrategy` (CP2) and evaluation files (H14). **Delivers:** the engine functions to BR and UI (**CP1**); the endurance engine (CP2); replays to UI (H14); `summary.json` to UI (H15).

**Timing conventions (put these in the docstrings)**

- `car.lap` = laps completed; array index `i = car.lap` is the lap about to be driven.
- A decision after lap L applies to lap L+1; a pit stop's loss is added to lap L+1.
- `observe` sets `status = scn.status[i]`: a safety car is known the moment it's deployed, which is when real teams call cars in.
- Lap 0 is the start-tyre choice: `decide()` sees `car.lap == 0` and `car.compound == ""`; `Action(pit=True, set_id=...)` means "start on this set" at no time cost. STAY at lap 0 is illegal.
- Lap times always use **P\_true**; each strategy is `reset()` with its **belief** params. In normal runs they are the same object.

**Tasks**

1. **SIM1 Lap time** (1.5 h). `engine.lap_time(cid, age, fuel, wet, status, noise, P)`, with compound parameters precomputed into numpy arrays indexed by compound id.
   - Green lap = base + offset\[c\] + warmup (age == 0) + deg\[c\] × age + cliff\[c\] × max(0, age − cliff\_lap)² + fuel\_s\_per\_kg × fuel + wet\_penalty(c, wet) + noise.
   - SC lap = base × sc\_lap\_factor + 0.2 × noise; VSC the same with vsc\_lap\_factor.
   - Done when: array input equals a loop of scalar calls; time rises with age and fuel; slicks lose more than inters at wetness 1.
2. **SIM2 Scenarios and futures** (2.5 h). `scenario.py`:
   - Safety cars: each green lap starts an SC with `p_sc_per_lap × sc_mult`, else a VSC with `p_vsc_per_lap`; duration uniform in `sc_len_laps`.
   - Rain: with `p_rain_race` (or the override), a uniform start lap; wetness rises 0.15/lap to a 0.4–1.0 peak, holds 5–20 laps, dries 0.08/lap.
   - Noise \~ Normal(0, `noise_sd_s`). Forecast: accurate near-term, blurring towards the base rate over about 15 laps.
   - Tags: `wet` if wetness ever > 0.2; `chaotic` if 2 or more SC/VSC; else `dry`.
   - `sample_futures(belief, obs, n, rng)` runs the same process from `obs` and belief rates only. It never receives the scenario.
   - Done when: same seed gives the same scenario; over 10,000 samples the SC and rain frequencies match params within 10%.
3. **SIM3 Inventory** (0.5 h). `sample_inventory(P, rng)`: from `P.allocation`, keep 1–2 new HARD, 1–2 new MEDIUM, 1 new + 2–3 used SOFT (ages from `data/inventory_stats.json`, built-in default until DAT10), 2 INTERMEDIATE, 1 WET.
4. **SIM4 Step and observe** (1.5 h). Pit: check the set exists; add `pit_loss_sc_s` under SC/VSC, else `pit_loss_s`; fit the set. Then one lap with P\_true; age +1; fuel − burn. F1 mode at the flag: no lap with wetness > 0.2 and fewer than 2 dry compounds = disqualified. Illegal actions raise a clear `ValueError`.
5. **SIM5 Race runner** (1 h). `race.run_race(scn, strategies, P_true, beliefs, inventory)`: ghost cars on one scenario, each strategy reset with `beliefs[name]`; returns the `LapRecord` DataFrame and finish time per car (NaN for DNF). Also `python -m pitwall.sim.race --demo`.
   - **CP1 gate:** Pirelli + Rules on mock params finish within ±10% of laps × base\_lap\_s, and the log loads in UI's Screen 1.
6. **SIM6 Endurance engine** (2 h, before CP2). When `P.mode == "endurance"`:
   - Start with `tank_kg` (DAT sets it to about 55% of race fuel, so at least one refuel is forced).
   - Pit time += max(0, fuel\_kg / `refuel_kg_per_s` − 3 s): the tyre change runs during refuelling.
   - Fuel can't exceed the tank; 0 fuel = DNF. The two-compound rule is off.
   - Same race distance as F1 mode.
7. **SIM7 Real-race replay** (4 h, from H9). `replay.replay(track, driver, strategy)`:
   1. The other 19 cars are recordings: elapsed time per lap from the real `Time` column; retired cars stop at their last lap.
   2. The real scenario comes from data: status per lap from the leader's TrackStatus (4 → SC; 6/7 → VSC). Wetness = the share of running cars on INTER/WET that lap. Noise = 0.
   3. Our car uses the track params plus the replaced driver's pace offset (from DAT12). Lap 1 copies his real lap 1 and real start tyre; the strategy decides from the end of lap 1.
   4. Traffic rule (assumed, marked):
      - Within 1.0 s of the car ahead and under 0.8 s/lap faster → our lap = max(ours, theirs + 0.2).
      - Pass chance per lap = clip((their lap − our lap − 0.3) / 1.0, 0, 0.9).
      - Under SC our elapsed time = car ahead + 0.8 s.
   5. **Sanity check first:** DAT's `RealStrategy(driver)` must finish within ±2 places of reality for most P8–P15 starters. Put this table in the output before claiming results.
   6. Write `results/replay_{track}_{driver}.json` (Section 3 schema) and `replay_index.json` listing every replay. BR runs the full batch on the Alienware.
8. **SIM8 Metrics** (2 h, from H13 on mock eval files, real ones at H14). `metrics.summarise()` writes `results/summary.json` (Section 3 schema):
   - Paired gain per seed vs each baseline, with a 95% bootstrap CI (2,000 resamples).
   - Win rate; oracle share = (mean T\_pirelli − mean T\_ours) / (mean T\_pirelli − mean T\_oracle).
   - Splits by tag and mode; the mismatch block; the rain sweep.
   - DNFs are counted separately and excluded from paired gains.

**Speed rule:** `lap_time` is the hottest function in the project (about 200 × 6 × 60 calls per decision). Pure numpy only; no Python branching on array values.

**Never:** let a strategy touch `Scenario` except through `observe`; use global randomness; read FastF1 directly.

## 9. Role DAT — Data & Baselines (Dharshini, Antigravity, Windows)

**Mission:** turn real F1 data into every number the simulator runs on, build the two baseline cars, and be the team's source of truth for "where does this number come from". Start the downloads in the first 10 minutes: they are the slowest thing in the project.

**Owns:** `pitwall/data/`, `params.py`, `data/`, `strategy/rules_config.py`, `strategy/rules.py`, `strategy/pirelli.py`, `strategy/real.py`, `results/model_accuracy.json`, `tests/test_data.py`, `tests/test_baselines.py`. **Needs:** the scaffold (H0). Nothing else: this role depends on no one. **Delivers:** baselines to BR and SIM (**CP1**); real params, Pirelli plans and inventory stats to everyone (**CP2**); real-race files and `RealStrategy` to SIM (**H9**); param samples to BR (**H13**); accuracy and slide facts to UI (H14).

**FastF1 basics for the AI**

```python
import fastf1
fastf1.Cache.enable_cache("cache")                     # gitignored folder
s = fastf1.get_session(2023, "Bahrain", "R")          # fuzzy names: "Monza", "Zandvoort", "Singapore"
s.load(laps=True, telemetry=False, weather=True, messages=True)
laps = s.laps        # Driver, LapNumber, LapTime, Time, Stint, Compound, TyreLife, FreshTyre,
                     # PitInTime, PitOutTime, TrackStatus, IsAccurate, Position, Team
wx = s.weather_data  # Time, AirTemp, TrackTemp, Humidity, Rainfall, ...
res = s.results      # GridPosition, Position, Status per driver
# LapTime is a Timedelta: .dt.total_seconds()
# TrackStatus = string of codes seen during the lap: '1' green, '2' yellow, '4' SC, '5' red, '6' VSC, '7' VSC ending
```

**Tasks** (in this order)

1. **DAT1 Downloads** (start at H0, runs in the background). `data/fetch.py`: all 2023 races (laps + weather + messages, no telemetry), plus the 2018–2023 races at our 4 tracks. Done when every session loads offline from cache.
2. **DAT2 Rules baseline** (1 h, H0–H1, while downloads run). `rules_config.py` holds every threshold; `RulesStrategy` reads only the Observation and its belief params:
   - Start on a new MEDIUM.
   - Pit when tyre\_age ≥ 0.8 × cliff\_lap, or when the predicted loss vs a fresh set exceeds the pit loss spread over the remaining laps.
   - Next compound: HARD if over 25 laps remain, else MEDIUM, else SOFT; always satisfy the two-compound rule in F1 mode.
   - Wet: wetness ≥ 0.35 → INTERMEDIATE; ≥ 0.75 → WET; back to slicks below 0.25.
   - Endurance mode: refuel to finish if it fits the tank, else full tank.
   - BR's numpy twin must match it, so keep the logic in plain thresholds.
3. **DAT3 Pirelli strategy** (0.5 h). `PirelliStrategy` follows `data/pirelli/{track}.json` lap by lap and ignores safety cars. It switches to inters only at wetness ≥ 0.5 (a late, cautious team), then returns to the plan. Endurance mode: full tank at each planned stop. Uses the mock plan until DAT9.
4. **DAT4 Clean** (1 h). Keep laps with TrackStatus exactly `'1'`, no pit in/out, LapNumber > 1, IsAccurate, dry compound, and under 107% of the race median → `data/clean/laps_2023.parquet`. A test asserts no pit or SC laps remain.
5. **DAT5 Fit + uncertainty samples** (3 h). `data/fit.py`:
   1. Pooled over all 2023 dry races: least squares for `fuel_s_per_kg`, with a fixed offset per driver-race, fuel = 110 kg minus an even burn per lap, compound dummies and compound × tyre-age terms.
   2. Per track, with fuel fixed: `base_lap_s`, compound offsets, `deg_s_per_lap`.
   3. Constraints: deg ≥ 0 and SOFT < MEDIUM < HARD on pace. A track that breaks them, or has under 30 laps on a compound (Monza softs), uses the pooled value scaled by the track's wear ratio, marked `"source": "pooled"`.
   4. Cliffs are rarely seen in real data: `cliff_lap` = 1.1 × the longest real stint on that compound at that track, `cliff_s_per_lap2` = 0.05, both `"assumed"`.
   5. **Samples for the fairness test:** bootstrap by resampling drivers 200 times and refitting, giving `data/params/{track}_samples.json`. The spread of these 200 draws is what "slightly wrong numbers" means. Nothing is invented.
   6. Endurance block per track: `tank_kg` = 0.55 × laps × burn, `refuel_kg_per_s` = 9.0, both `"assumed"`.
   - Done when: `fuel_s_per_kg` is between 0.02 and 0.04; all 4 tracks load in both modes; tests check the ordering.
6. **DAT6 Pit loss and SC pace** (1 h). Per real stop: (in-lap + out-lap) − 2 × that driver's median clean lap nearby. The median per track gives `pit_loss_s`; the same over SC/VSC stops gives `pit_loss_sc_s` (under 5 such stops: 0.55 × `pit_loss_s`, `"assumed"`). `sc_lap_factor`, `vsc_lap_factor` = median SC/VSC lap ÷ median green lap.
7. **DAT7 Safety car rates** (1 h). 2018–2023 at each track: SC deployments (code 4 appears) and VSC (code 6). `p_sc_per_lap` = deployments ÷ race laps; `sc_len_laps` = observed min–max. Zandvoort has only 2021–2023; Singapore wasn't held in 2020–2021.
8. **DAT8 Rain** (1 h). `p_rain_race` = the share of races at that track with any `Rainfall`, blended with a marked prior when samples are few. Wet penalties from inter vs slick laps at Zandvoort 2023; everything unmeasured `"assumed"`.
9. **DAT9 Pirelli plans** (0.5 h, by hand). Read Pirelli's 2023 race-preview press releases for the 4 races → `data/pirelli/{track}.json`. If one can't be found, use the most common strategy among the real top-10 finishers, marked `"typical_2023_top10"`.
10. **DAT10 Inventory stats** (0.5 h). TyreLife at the start of every used-set stint (`FreshTyre == False`), per compound → `data/inventory_stats.json`. Allocation: standard weekend 13 dry sets (2 H, 3 M, 8 S); Monza 2023 Alternative Tyre Allocation 11 sets (3 H, 4 M, 4 S). Verify both against the 2023 Pirelli/FIA documents first.
11. **DAT11 Real-race extract + RealStrategy** (1.5 h, **due H9**). For the 4 races: `data/real/{track}_laps.parquet` (all drivers, raw columns), `_status`, `_weather`, `_results`. `strategy/real.py: RealStrategy(track, driver)` copies a real driver's pit laps and compounds, for SIM's sanity check.
12. **DAT12 Driver offsets + model accuracy** (1.5 h). Per-driver pace offset at each track → `data/real/{track}_offsets.json` (SIM's replay uses it). Then predict every real clean lap from our params plus that offset; MAE and RMSE in seconds → `results/model_accuracy.json`. This is the "accurate to X s" slide.
13. **DAT13 Baseline tuning** (1 h, after CP2). Tune `rules_config.py` on seeds 100000+ only, to make the rules car as strong as possible. A strong baseline makes our win credible. Seeds 0–999 are never touched.
14. **DAT14 Data and honesty slide content** (1.5 h, H14–H16). For UI's deck: a table of every parameter with its source (fitted / pooled / assumed), the accuracy numbers, and the limits.

**Never:** call FastF1 outside `pitwall/data`; commit the cache; write a parameter without its source; tune the baselines to be weaker.

## 10. Role UI — Screens & Pitch (Pranesh, Antigravity, Mac)

**Mission:** make the judges *see* it. Three Streamlit screens that never crash, a deck, a demo script and a backup video. Start at H0 on the mocks, so every screen exists before the real numbers do.

**Owns:** `app/`, `pitch/`, `README.md`, `results/demo_*`, `tests/test_app.py`. **Needs:** mocks (H0); SIM's `run_race` (CP1) for Screen 1; BR's eval files (H14) and SIM's `summary.json` (H15) for Screen 2; SIM's replays (H14) for Screen 3; DAT's slide facts (H16) and Smaran's strategist slide content for the deck. **Delivers:** the demo and the submission package.

**Colour rule:** F1 tyre colours are fixed and judges know them: SOFT red, MEDIUM yellow, HARD white, INTER green, WET blue. Car colours never reuse them. Cars: Pirelli = purple, Rules = orange, **Ours = cyan (thickest line)**, Oracle = grey dashed. Define all colours once in `app/style.py`.

**Tasks**

1. **UI1 Skeleton** (1 h). `app/Home.py` plus `pages/1_Live_Race.py`, `2_Proof.py`, `3_Real_Races.py`. `app/data_access.py` loads the real file when it exists and the mock otherwise, so the app never breaks mid-build.
2. **UI2 Screen 1 — Live race** (4.5 h).
   - Controls: track, **mode toggle (F1 / Endurance)**, seed with a "Surprise me" button, rain chance slider, safety car frequency slider, Run.
   - Run calls `run_race` with a spinner (about 3 s), then animates the finished log. Nothing is computed during playback.
   - Use Plotly animation frames (one per lap, play/pause, speed) so playback is smooth and doesn't rerun Streamlit.
   - Panels:
     - Leaderboard: position, car, gap, tyre with age, stops
     - Gap-to-Pirelli lines with a moving lap marker
     - Tyre strategy strip, one bar per car, coloured by compound
     - Conditions band: wetness and SC/VSC shading
     - Decision feed: our reasons, newest first
     - What-if bars from `expected_json` at the current decision
     - Endurance mode only: a fuel gauge per car, and fuel added shown on each pit marker
   - Done when: Bahrain seed 7 plays end to end in both modes, and an SC or rain event visibly changes our strategy.
3. **UI3 Screen 2 — Proof** (2.5 h).
   - Mode selector.
   - Headline cards: mean gain vs Pirelli ± CI, win rate, % of the Oracle's gain captured, model accuracy (from DAT).
   - Bar chart: mean gain vs each baseline, split dry / wet / chaotic.
   - Histogram: per-race paired gain vs Pirelli, from `eval_*.parquet`.
   - Line: gain vs rain chance.
   - **Fairness panel:** "With its numbers deliberately wrong, ours still gains X s" (the mismatch block).
   - A short "Where it doesn't help" note, filled from the data.
4. **UI4 Screen 3 — Real races, animated** (3 h, reusing UI2's components). Pick track and driver from `replay_index.json`.
   - Animated 20-car position chart and leaderboard: our car cyan, the real driver as a dashed cyan ghost line, everyone else grey.
   - Result card, e.g. "Real: P11 → Ours: P8".
   - The sanity-check table underneath.
5. **UI5 Robustness + demo cache** (1 h). `app/make_demos.py` pre-runs and saves `results/demo_{mode}_{track}.parquet` for seeds chosen to include an SC or rain. The app runs fully offline, every page loads in under 3 s, and if live compute fails, the cached demo plays.
6. **UI6 Deck** (3 h, from CP2). Nine slides:
   1. The problem
   2. Our answer in one line
   3. Real data (DAT14)
   4. How it thinks: the 200-futures picture (content from Smaran)
   5. Results, F1 mode
   6. Endurance mode + fairness test
   7. Real races
   8. Honesty: accuracy, what's assumed, the limits (DAT14)
   9. Demo
7. **UI7 Script, Q&A and backup** (1.5 h, at freeze). We present live in an online meeting, sharing Smaran's screen: the app runs locally on the Alienware, the fastest machine. Prepare a 3-minute demo script with timings, and a screen recording of the whole demo as a backup video, ready to share in the call if the app or network stutters. Hold one full rehearsal on a real call (Google Meet or Zoom) to check that animations stay smooth over screen share, with notifications off and other apps closed. Also prepare a Q&A sheet answering: *Why F1 data for an endurance problem? Where is fuel? Isn't the Oracle cheating? Doesn't it win only because it knows the simulator? Don't the replay cars react? How do you know it isn't overfitted? Why not reinforcement learning? How accurate is the simulator?*

**Never:** compute heavy things on page load; show a number that doesn't come from a results file; use tyre colours for cars.

## 11. Timeline and checkpoints

**Deadline: Saturday 11:00.** H0 is Friday 17:15, when the scaffold is pushed, and we submit at 10:30 to keep 30 minutes of buffer. That's about 17 hours, 3 fewer than first planned. Hour marks used elsewhere in this doc map to the clock like this:

| Mark | H0 | H1 | CP1 (H6) | H9 | CP2 (H12) | H13 | H14 | H15 | Freeze (H16) | Submit (H20) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Clock | 17:15 | 18:00 | 22:30 | 01:00 | 03:30 | 04:30 | 05:30 | 06:30 | 07:30 | 10:30 |

| Phase (clock) | BR (Smaran) | SIM (Ashwin) | DAT (Dharshini) | UI (Pranesh) |
| --- | --- | --- | --- | --- |
| 17:15-18:00 Setup | BR0 push scaffold, tag h0, issues | clone, run tests; SIM1 begins | DAT1 downloads running; DAT2 rules baseline | UI1 app skeleton on mocks |
| 18:00-22:30 Build alone | BR1 rollout core, numpy rules twin, speed test | SIM2 scenarios+futures, SIM3, SIM4, SIM5 run_race | DAT3 Pirelli strategy, DAT4 clean, DAT5 fit + samples | UI2 live race screen on the mock log |
| **CP1 22:30** | one race runs on real engine code; Screen 1 animates it | | | |
| 22:30-03:30 Real data, both modes | BR2 rollout, BR3 oracle, BR4 no-peeking, BR5 endurance fuel | SIM6 endurance engine, SIM7 replay from 01:00 + sanity table | DAT6-DAT10, DAT11 real races by 01:00 | UI2 mode toggle + polish, UI3 proof screen on mocks |
| **CP2 03:30** | real params in; rollout beats rules on 100 seeds; replay sanity | | | |
| 03:30-07:30 Results (staggered sleeps) | BR6 batch + fairness, BR7 all runs on Alienware | SIM7 all drivers, SIM8 metrics | DAT12 offsets + accuracy, DAT13 tuning, DAT14 slide facts | UI4 real races animated, UI5 offline + demo cache, UI6 deck |
| **Freeze 07:30** | tag freeze; bug fixes only | | | |
| 07:30-10:30 Pitch | strategist slide, lead rehearsals | bug fixes, replay table | check every number | UI6 deck, UI7 script, backup video, call rehearsal |
| **Submit 10:30** | tag v1.0 (deadline 11:00) | | | |

At every checkpoint, all four stop for 15 minutes: merge, run the app from `main`, check the gate, and re-plan. A gate that isn't met is fixed before anyone starts the next phase.

## 12. Risks and fallbacks

The three risks most likely to hurt the result are a slow strategist, a replay that doesn't reproduce reality, and Claude usage limits on the critical path. Each has an early test that exposes it before CP2.

| Risk | Early warning | Fallback | Owner |
| --- | --- | --- | --- |
| Strategist too slow | BR1 speed test over 50 ms per decision | n = 100; re-plan every 2 laps unless an event happens | BR |
| Claude Pro limit hit mid-build | Claude Code slows or refuses | Switch BR's task to Antigravity; Claude only for BR1–BR3 and BR6 | BR |
| Replay doesn't match reality | SIM7 sanity check misses by more than 2 places | Fix the driver offset or traffic rule. Still failing at H14: show Screen 3 with the caveat on screen, or compare time only | SIM |
| DAT11 real-race files late | Not merged by H9 | SIM builds the replay on Bahrain only; other tracks follow | DAT |
| FastF1 slow or venue Wi-Fi bad | DAT1 not done by H1.5 | Mock params carry everyone; download on a phone hotspot; extracted files are committed, so it's needed once | DAT |
| Fitted numbers make no sense | DAT5 tests: fuel outside 0.02–0.04, deg < 0, offsets out of order | Pooled values, marked as such | DAT |
| Ours loses dry races to Pirelli | SIM8 split by tag | Expected and fine: show it honestly. Gains come from SC and rain | BR, SIM |
| Ours loses the fairness test | Mismatch gain ≤ 0 | Report it truthfully as a limit; it's still a stronger story than hiding it | BR |
| Endurance numbers questioned | Judge question | Tank and refuel speed are labelled assumed (2009-era F1); tyre and pit numbers are still real | DAT, UI |
| Integration breaks at a checkpoint | CI red; screens fail on real files | Contract + stand-ins + hourly rebase; Smaran fixes merges first | BR |
| Contract needs a change | An AI says the types block it | Contract PR, merged only at a checkpoint, all four approve | BR |
| Demo crashes on stage | Any error at rehearsal | Offline app, cached demo races, backup video, run from the `freeze` tag | UI |
| "This is F1, not endurance" | Judge question | Endurance mode answers it; F1 is the only series with public tyre data | UI |
| Wet-weather model weak | DAT8 has few wet laps | Label assumed values; lead with dry and safety car results | DAT |
| Team exhaustion | Mistakes after H14 | Staggered 90-minute sleeps after CP2: SIM and DAT first, then UI and BR. Nobody merges half-asleep | BR |
| Screen share lags or the call drops | Rehearsal on a real call | Slow the animation speed; share the backup video; Pranesh takes over from his Mac with the same tag checked out | UI |

## 13. Still open before H0

The plan is locked. These answers only fill in details, except the first, which rescales the timeline.

1. **Deadline Saturday 11:00 (done). Still open, submission requirements:** repo link, video, deck format, report? Demo length? Judging criteria? Must the repo be public?
2. Done: Ashwin is SIM (Mac), Dharshini is DAT (Windows), Pranesh is UI (Mac); Smaran leads on the Alienware.
3. Done: two Macs and one Windows laptop. Section 5 covers both; Mac users install Python with \`brew install python@3.12\`.
4. The output of `nproc` and `free -h` on the Alienware: done, 22 threads and 30 GB RAM, so BR7 uses Pool(20).
5. Python 3.12 is assumed for everyone. Confirm teammates can install it.

- [ ] Answers posted
- [ ] BR0 scaffold generated, reviewed and pushed (tag `h0`)
- [ ] Repo created, collaborators added, issues created per task ID
- [ ] Everyone has run `pytest -q` green on a fresh clone
- [ ] DAT1 downloads running

## 14. Review: problem statement, handoffs, workload

After the latest decisions, every requirement of the problem statement is covered. Every screen element traces to a producer and a deadline. The remaining risk is workload, not design.

**Problem statement coverage**

| Problem statement asks | Where we answer it | Strength |
| --- | --- | --- |
| Simulate fuel consumption and tyre performance over time | Lap-time model (SIM1) fitted on 2023 data (DAT5); endurance mode with real fuel decisions (SIM6, BR5) | Strong; tank and refuel speed assumed |
| Pit-stop duration and available tyre options | Pit loss per track (DAT6); real tyre inventory (DAT10, SIM3) | Strong |
| Changing or unpredictable race conditions | SC, VSC, rain, noisy forecast (SIM2) | Strong; wet values partly assumed |
| Recommend or select a strategy during the race | Rollout strategist with explained decisions (BR2) | Strong |
| Reconsider when conditions change | Re-plans every lap; reacts to SC and rain on the same lap | Strong |
| Compare against a simple baseline | Pirelli plan + tuned rules, plus the Oracle as an upper bound | Strong (more than asked) |
| Evaluate across multiple simulated races | 7,200 paired races, confidence intervals, fairness test | Strong |

**Handoff audit: every element on screen has a producer**

| Screen / deliverable element | Source | Producer | Due |
| --- | --- | --- | --- |
| Screen 1 race animation | `run_race` log | SIM5 | CP1 |
| Screen 1 decision feed + what-if bars | `reason`, `expected_json` in the log | BR2 fills, SIM5 records | CP2 |
| Screen 1 fuel gauge (endurance) | `fuel_kg`, `fuel_added_kg` in the log | SIM6, BR5 | CP2 |
| Screen 2 headline cards, bar chart, rain line | `summary.json` | SIM8 from BR7's runs | H15 |
| Screen 2 histogram | `eval_*.parquet` | BR7 | H14 |
| Screen 2 fairness panel | `summary.json` → `mismatch` | SIM8 from BR6/BR7 + DAT5 samples | H15 |
| Screen 2 accuracy card | `model_accuracy.json` | DAT12 | H14 |
| Screen 3 animation + result card | `replay_*.json` | SIM7 (BR7 runs the batch) | H14 |
| Screen 3 sanity table | `sanity` block in `replay_*.json` | SIM7 + DAT11 `RealStrategy` | H14 |
| Deck: data and honesty slides | DAT14 | DAT | H16 |
| Deck: strategist slide | content from Smaran | BR | H16 |
| Backup video | UI7 | UI | Freeze + 1 h |

Gaps found and fixed in this audit: driver pace offsets had no producer (now DAT12 → `data/real/{track}_offsets.json`); `RealStrategy` had no owner (now DAT11); strategies' belief params are now separate from the true params, which the fairness test needs; the lap log gained `fuel_added_kg` and `expected_json` for Screen 1.

**Workload** (task estimates vs about 17.5 usable hours after sleep and checkpoints)

| Role | Task hours | Note |
| --- | --- | --- |
| BR (Smaran) | \~12.5 + 3 lead | Lightest coding load, by design: lead duties and Claude limits |
| SIM | \~15 | SIM7 replay is the riskiest task |
| DAT | \~15.5 | About 2 h of it is background downloading |
| UI | \~16.5 | Heaviest. After BR7 starts (H13), Smaran helps UI with the deck and Screen 3 |

**Remaining honest limits** (say them before a judge does): replay cars don't react to ours; tank size and refuel speed are assumed; wet penalties are partly assumed; the Oracle is a strong reference, not a proven optimum.

**Cut list if behind at CP2** (from the top). Never cut: endurance mode, the Screen 3 animation, the sanity check.

1. Rain sweep chart (keep the dry / wet / chaotic split)
2. Replays beyond 3 drivers per track
3. Singapore in F1 main (3 tracks)
4. DAT13 baseline tuning
5. Fairness test on Bahrain only
