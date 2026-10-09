You are working on PitWall, role UI, task <ID>, on branch <branch>.
Read AGENTS.md, docs/PLAN.md sections 1-4, docs/roles/UI.md and pitwall/types.py before anything else.
Then do task <ID> only, meeting its "Done when" criteria. Plan first if the task is over 1 hour.
Run pytest -q at the end and show me the output.

---

## 10. Role UI — Screens & Pitch (Pranesh, Antigravity, Mac)

**Mission:** make the judges *see* it. Three Streamlit screens that never crash, a deck, a demo script and a backup video. Start at H0 on the mocks, so every screen exists before the real numbers do.

**Owns:** `app/`, `pitch/`, `README.md`, `results/demo_*`, `tests/test_app.py`. **Needs:** mocks (H0); SIM's `run_race` (CP1) for Screen 1; BR's eval files (H14) and SIM's `summary.json` (H15) for Screen 2; SIM's replays (H14) for Screen 3; DAT's slide facts (H16) and Smaran's strategist slide content for the deck. **Delivers:** the demo and the submission package.

**Colour rule:** F1 tyre colours are fixed and judges know them: SOFT red, MEDIUM yellow, HARD white, INTER green, WET blue. Car colours never reuse them. Cars: Pirelli = purple, Rules = orange, **Ours = cyan (thickest line)**, Oracle = grey dashed. Define all colours once in `app/style.py`.

**Tasks**

1. **UI1 Skeleton** (1 h). `app/Home.py` plus `pages/1_Live_Race.py`, `2_Proof.py`, `3_Real_Races.py`. `app/data_access.py` loads the real file when it exists and the mock otherwise, so the app never breaks mid-build.
2. **UI2 Screen 1 — Live race** (4.5 h).
   - Controls: track, **mode toggle (F1 / Endurance)**, seed with a "Surprise me" button, rain chance slider, safety car frequency slider, Run. Judges may ask for different inputs (Rule 9.5), so every control must work and no combination may crash.
   - Run calls `run_race` with a spinner (about 3 s), then animates the finished log. Nothing is computed during playback.
   - Use Plotly animation frames (one per lap, play/pause, speed) so playback is smooth over screen share and doesn't rerun Streamlit.
   - Panels:
     - Leaderboard: position, car, gap, tyre with age, stops
     - Gap-to-Pirelli lines with a moving lap marker
     - Tyre strategy strip, one bar per car, coloured by compound
     - Conditions band: wetness and SC/VSC shading
     - Decision feed: our reasons, newest first
     - What-if bars from `expected_json` at the current decision
     - Endurance mode only: a fuel gauge per car, and fuel added on each pit marker
   - Done when: Bahrain seed 7 plays end to end in both modes, and an SC or rain event visibly changes our strategy.
3. **UI3 Screen 2 — Proof** (2.5 h).
   - Mode selector.
   - Headline cards: mean gain vs Pirelli ± CI, win rate, % of the Oracle's gain captured, model accuracy.
   - Bar chart: mean gain vs each baseline, split dry / wet / chaotic.
   - Histogram: per-race paired gain vs Pirelli, from `eval_*.parquet`.
   - Line: gain vs rain chance.
   - Fairness panel: "With its numbers deliberately wrong, ours still gains X s".
   - A short "Where it doesn't help" note, filled from the data.
4. **UI4 Screen 3 — Real races, animated** (3 h, reusing UI2's components). Pick track and driver from `replay_index.json`. Show an animated 20-car position chart and leaderboard (ours cyan, the real driver as a dashed cyan ghost, everyone else grey), a result card such as "Real: P11 → Ours: P8", and the sanity-check table underneath.
5. **UI5 Robustness + demo cache** (1 h). `app/make_demos.py` pre-runs and saves `results/demo_{mode}_{track}.parquet` for seeds with an SC or rain. The app runs fully offline, every page loads in under 3 s, and if live compute fails the cached demo plays.
6. **UI8 README** (1 h, merged by 09:30). Everything Rule 8 requires:
   - team name (Chumma Oru Commit) and members with roles
   - problem statement (Third Year, Non Circuit #5, The Impossible Pit Stop)
   - solution in brief
   - technologies (Python 3.12, numpy, pandas, FastF1, Streamlit, Plotly)
   - how to run the 3 screens
   - external resources (FastF1, Formula 1 2023 timing data via FastF1, Pirelli 2023 race-preview press releases)
   - **AI use disclosure**: Claude Code and Antigravity wrote most code under human direction; humans reviewed, tested and can explain it
   - DAT supplies the data-source list; Smaran supplies the AI disclosure wording.
7. **UI6 Deck** (3 h, after the freeze). Ten slides that cover everything judges must hear (Rule 9.4):
   1. The problem
   2. Our answer in one line
   3. Real data and where every number comes from
   4. How it thinks: the 200-futures picture
   5. **Major design decisions:** F1 data, two modes, ghost cars, rollout instead of reinforcement learning
   6. Results, F1 mode
   7. Endurance mode + fairness test
   8. Real races
   9. **Challenges we hit**, and how we solved them (collect these at each team call)
   10. **Requirements checklist** + honest limits, then the live demo
8. **UI7 Script, Q&A and backup** (1.5 h, after the freeze). We present live in an online meeting, sharing Smaran's screen; the app runs locally on the Alienware.
   - A 3-minute demo script with timings.
   - A screen recording of the submitted app as a backup video. It's a fallback only: the live app is required (Rule 9.6).
   - One full rehearsal on a real call, notifications off.
   - A Q&A sheet answering: *Why F1 data for an endurance problem? Where is fuel? Isn't the Oracle cheating? Doesn't it win only because it knows the simulator? Don't the replay cars react? How do you know it isn't overfitted? Why not reinforcement learning? How accurate is the simulator? What did the AI write and what did you decide?*

**Never:** compute heavy things on page load; show a number that doesn't come from a results file; use tyre colours for cars.
