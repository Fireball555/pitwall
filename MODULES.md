# What each part does, and what to improve next

The whole project works end to end. Run `pytest` and `python -m pitwall.server` after every change.

```
frontend/ (React)  ->  pitwall/server.py (FastAPI)  ->  engine/  strategy/  eval/  data/
```

---

## Engine: `pitwall/engine/`

**Does:** lap times (tyre wear, cliff, warm-up, fuel weight, wet penalty), random safety cars and rain, the forecast, the strategist's imagined futures, tyre stock per car, pit stops, endurance refuelling, a full 4-car race, and the 20-car real-race replay with a sanity check.

**See it:** `python -m pitwall.engine.race` and `python -m pitwall.engine.replay bahrain`. In the app: *Live race* and *Real races*.

**Improve:**
1. Replay accuracy: tune the traffic rule in `replay.py` until most drivers' real strategies land within ±1 place.
2. Under SC/VSC, tyres age about half as fast (in `race.py` and in the futures).
3. Rain realism: slow drying, inters best at medium wetness. Check against Zandvoort 2023.
4. Keep a full race under 3 s.

**Don't break:** `lap_time(P, cid, age, fuel, wet, status, noise)` on numpy arrays; `sample_scenario`, `sample_futures`, `run_race`, `replay_with_sanity`; the replay JSON keys; `tests/test_engine.py`.

---

## Data: `pitwall/data/`, `data/`

**Does:** loads track numbers from `data/tracks/*.json` (placeholders until the build runs); downloads 2023 races with FastF1 and fits tyre wear, fuel effect, pit loss, noise and safety-car factor; writes 200 uncertainty samples for the fairness test; fits safety-car and rain rates from 2018–2023; makes a synthetic race for offline use.

**See it:** `python -m pitwall.data.build --track bahrain --synthetic` (offline).

**Improve:**
1. Real numbers: `python -m pitwall.data.build --all`. Check fuel effect 0.02–0.04 s/kg, wear positive, SOFT < MEDIUM < HARD in lap time, pit loss 20–30 s.
2. Fill `data/pirelli.json` with Pirelli's 2023 race-preview strategies and name the sources.
3. Check tyre `allocation` against the 2023 rules (Monza used the Alternative Tyre Allocation).
4. `pitwall/data/accuracy.py`: predict every real clean lap and save `data/accuracy.json` as `{"mae_s", "rmse_s"}`. The Proof tab shows it automatically.
5. The SOFT wear fit comes out too low on synthetic data; improve `fit.py`.

**Don't break:** the track JSON format (a value is a number or `{"value", "source"}`); `load_track`, `load_param_samples`, `load_pirelli_plan`; the real-race parquet columns in `realrace.py`; `tests/test_data.py`.

---

## Strategy and evaluation: `pitwall/strategy/`, `pitwall/eval/`

**Does:** the Pirelli-plan car, the simple-rules car, our rollout strategist (200 futures per option, every lap, vectorised, with explained decisions) and the Oracle; batch evaluation (main, endurance, fairness, rain sweep) on all CPU cores; bootstrap confidence intervals.

**See it:** `python -m pitwall.eval.batch --track bahrain --n 100`. In the app: *Proof*.

**Improve:**
1. After the real numbers land: `python -m pitwall.eval.batch --all --n 1000` (about 15 minutes on 20 cores), then commit `results/`.
2. Strategy quality: try 300 futures, tune the 0.5 s hysteresis, make the futures' later decisions use safety cars. Tune only on seeds ≥ 100000.
3. Endurance: smarter fuel amounts (short-fill before an expected safety car).
4. Run `python -m pitwall.engine.replay <track>` for every track and commit `results/replay_*.json`.

**Don't break:** the strategy interface (`reset(belief, car)`, `decide(car, obs) -> Decision`) and `make_cars`; the `results/` file names and columns; `tests/test_strategy.py` (including the no-peeking test) and `tests/test_eval.py`.

---

## Web app: `pitwall/server.py`, `frontend/`

**Does:** FastAPI serves a JSON API and the built React app. Three tabs:
- *Live race*: controls, timing tower that follows the lap slider, gap chart with safety-car and rain bands, tyre strategy strip, decision feed with what-if bars.
- *Proof*: headline numbers, histogram, results by race type, fairness test, rain line.
- *Real races*: 20-car positions with our strategist in one seat, and the sanity check.

**See it:** `python -m pitwall.server`. For live frontend editing: `python -m pitwall.server --no-browser`, then `cd frontend && npm run dev`.

**Improve:**
1. Endurance mode: a fuel chart per car.
2. Proof: a short "how we test" box and an F1 vs endurance comparison.
3. Real races: our pit stops as markers on the position chart, and a table across all replayed drivers.
4. Keep the README true as the numbers change.
5. After the 09:30 freeze: deck, demo script, backup video (`pitch/`).

**Don't break:** the `/api/*` JSON keys the frontend reads; `tests/test_api.py`; no heavy computation on page load; car colours never use tyre colours; rebuild `frontend/dist` after frontend changes.
