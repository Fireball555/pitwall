You are working on PitWall, role BR, task <ID>, on branch <branch>.
Read AGENTS.md, docs/PLAN.md sections 1-4, docs/roles/BR.md and pitwall/types.py before anything else.
Then do task <ID> only, meeting its "Done when" criteria. Plan first if the task is over 1 hour.
Run pytest -q at the end and show me the output.

---

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
   - Pruning: wet compounds only if wetness > 0.1 or forecast rain > 0.2 in the next 10 laps; no pit option if tyre_age < 3 under green.
   - Hysteresis: pit only if it beats STAY by more than 0.5 s.
   - Lap 0 scores every start set. Fills `expected_s` and a reason with ± standard error, e.g. `Lap 23: SC deployed, pit for HARD saves 8.4 s ± 1.9`.
4. **BR3 Oracle** (1 h). Same as BR2 with n = 1: its single future is the true scenario, and its belief is the true params. Label it "knows the future": a strong reference, not a proven optimum.
5. **BR4 No-peeking test** (0.5 h). Change a scenario's arrays after lap L and re-run; every decision up to lap L must be identical.
6. **BR5 Endurance fuel choices** (1.5 h, with SIM5). Fuel options per pit: enough to finish (if it fits the tank), full tank, half tank. Done when: 50 endurance races at Bahrain finish with zero fuel DNFs for the rollout car.
7. **BR6 Batch runner + fairness test** (2.5 h). `batch.evaluate(track, mode, n, seed0, test)`, using `multiprocessing.Pool(nproc − 2)`:
   - `main`: P_true = belief = the fitted params.
   - `rain_sweep`: same, with `rain_prob` fixed per batch.
   - `mismatch` (`fairness.py`): P_true = `samples[seed % 200]`; the three fair cars plan with the fitted params; the Oracle gets P_true.
   - Seeds 0–999 are reserved for evaluation and never used for tuning. Output follows the Section 3 schema.
8. **BR7 Run everything on the Alienware** (H13–H14, about 1 h wall time).

| Run | Tracks | Races | Feeds |
| --- | --- | --- | --- |
| F1 main | Bahrain, Monza, Zandvoort, Singapore | 4 × 1,000 | Screen 2 headline |
| Endurance main | Bahrain, Singapore | 2 × 500 | Screen 2 endurance panel |
| Fairness (mismatch) | Bahrain, Singapore | 2 × 500 | Screen 2 fairness panel |
| Rain sweep | Zandvoort, rain 0–0.5 in steps of 0.1 | 6 × 200 | Screen 2 line chart |
| Replays (SIM's code) | 4 tracks × midfield drivers | ~32 | Screen 3 |

About 7,200 races at roughly 3 s each is about 6 CPU-hours. The Alienware has 22 threads and 30 GB RAM, so `Pool(20)` finishes everything in about 20 minutes. Start by 04:30.

**Lead duties (about 3 h across the night):** merge PRs within 15 minutes, run each checkpoint, approve contract PRs, keep CI green, make the cut-list calls (Section 14).

**Speed budget:** a full race with all 4 cars under 3 s. If missed: n = 100, or re-plan every 2 laps unless an event happens.

**Never:** read `Scenario` outside `Oracle`; use different futures for different options; tune anything on seeds 0–999.
