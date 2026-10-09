You are working on PitWall, role SIM, task <ID>, on branch <branch>.
Read AGENTS.md, docs/PLAN.md sections 1-4, docs/roles/SIM.md and pitwall/types.py before anything else.
Then do task <ID> only, meeting its "Done when" criteria. Plan first if the task is over 1 hour.
Run pytest -q at the end and show me the output.

---

## 8. Role SIM — Simulator & Replay (Ashwin, Antigravity, Mac)

**Mission:** build the race itself (lap times, weather, safety cars, pit stops, both modes), then the 20-car replay of real races, then turn BR's raw results into the numbers on the Proof screen. Every other role runs on your engine, so correctness and speed beat features.

**Owns:** `pitwall/sim/`, `eval/metrics.py`, `results/summary.json`, `results/replay_*`, `tests/test_sim.py`, `tests/test_replay.py`, `tests/test_metrics.py`. **Needs:** the scaffold (H0); DAT's real params (CP2, a file swap); DAT's real-race files (**H9**) and `RealStrategy`; BR's `RolloutStrategy` (CP2) and evaluation files (H14). **Delivers:** the engine functions to BR and UI (**CP1**); the endurance engine (CP2); replays to UI (H14); `summary.json` to UI (H15).

**Timing conventions (put these in the docstrings)**

- `car.lap` = laps completed; array index `i = car.lap` is the lap about to be driven.
- A decision after lap L applies to lap L+1; a pit stop's loss is added to lap L+1.
- `observe` sets `status = scn.status[i]`: a safety car is known the moment it's deployed, which is when real teams call cars in.
- Lap 0 is the start-tyre choice: `decide()` sees `car.lap == 0` and `car.compound == ""`; `Action(pit=True, set_id=...)` means "start on this set" at no time cost. STAY at lap 0 is illegal.
- Lap times always use **P_true**; each strategy is `reset()` with its **belief** params. In normal runs they are the same object.

**Tasks**

1. **SIM1 Lap time** (1.5 h). `engine.lap_time(cid, age, fuel, wet, status, noise, P)`, with compound parameters precomputed into numpy arrays indexed by compound id.
   - Green lap = base + offset[c] + warmup (age == 0) + deg[c] × age + cliff[c] × max(0, age − cliff_lap)² + fuel_s_per_kg × fuel + wet_penalty(c, wet) + noise.
   - SC lap = base × sc_lap_factor + 0.2 × noise; VSC the same with vsc_lap_factor.
   - Done when: array input equals a loop of scalar calls; time rises with age and fuel; slicks lose more than inters at wetness 1.
2. **SIM2 Scenarios and futures** (2.5 h). `scenario.py`:
   - Safety cars: each green lap starts an SC with `p_sc_per_lap × sc_mult`, else a VSC with `p_vsc_per_lap`; duration uniform in `sc_len_laps`.
   - Rain: with `p_rain_race` (or the override), a uniform start lap; wetness rises 0.15/lap to a 0.4–1.0 peak, holds 5–20 laps, dries 0.08/lap.
   - Noise ~ Normal(0, `noise_sd_s`). Forecast: accurate near-term, blurring towards the base rate over about 15 laps.
   - Tags: `wet` if wetness ever > 0.2; `chaotic` if 2 or more SC/VSC; else `dry`.
   - `sample_futures(belief, obs, n, rng)` runs the same process from `obs` and belief rates only. It never receives the scenario.
   - Done when: same seed gives the same scenario; over 10,000 samples the SC and rain frequencies match params within 10%.
3. **SIM3 Inventory** (0.5 h). `sample_inventory(P, rng)`: from `P.allocation`, keep 1–2 new HARD, 1–2 new MEDIUM, 1 new + 2–3 used SOFT (ages from `data/inventory_stats.json`, built-in default until DAT10), 2 INTERMEDIATE, 1 WET.
4. **SIM4 Step and observe** (1.5 h). Pit: check the set exists; add `pit_loss_sc_s` under SC/VSC, else `pit_loss_s`; fit the set. Then one lap with P_true; age +1; fuel − burn. F1 mode at the flag: no lap with wetness > 0.2 and fewer than 2 dry compounds = disqualified. Illegal actions raise a clear `ValueError`.
5. **SIM5 Race runner** (1 h). `race.run_race(scn, strategies, P_true, beliefs, inventory)`: ghost cars on one scenario, each strategy reset with `beliefs[name]`; returns the `LapRecord` DataFrame and finish time per car (NaN for DNF). Also `python -m pitwall.sim.race --demo`.
   - **CP1 gate:** Pirelli + Rules on mock params finish within ±10% of laps × base_lap_s, and the log loads in UI's Screen 1.
6. **SIM6 Endurance engine** (2 h, before CP2). When `P.mode == "endurance"`:
   - Start with `tank_kg` (DAT sets it to about 55% of race fuel, so at least one refuel is forced).
   - Pit time += max(0, fuel_kg / `refuel_kg_per_s` − 3 s): the tyre change runs during refuelling.
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
   - Win rate; oracle share = (mean T_pirelli − mean T_ours) / (mean T_pirelli − mean T_oracle).
   - Splits by tag and mode; the mismatch block; the rain sweep.
   - DNFs are counted separately and excluded from paired gains.

**Speed rule:** `lap_time` is the hottest function in the project (about 200 × 6 × 60 calls per decision). Pure numpy only; no Python branching on array values.

**Never:** let a strategy touch `Scenario` except through `observe`; use global randomness; read FastF1 directly.
