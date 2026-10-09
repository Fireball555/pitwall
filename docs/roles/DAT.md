You are working on PitWall, role DAT, task <ID>, on branch <branch>.
Read AGENTS.md, docs/PLAN.md sections 1-4, docs/roles/DAT.md and pitwall/types.py before anything else.
Then do task <ID> only, meeting its "Done when" criteria. Plan first if the task is over 1 hour.
Run pytest -q at the end and show me the output.

---

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
   - Pit when tyre_age ≥ 0.8 × cliff_lap, or when the predicted loss vs a fresh set exceeds the pit loss spread over the remaining laps.
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
