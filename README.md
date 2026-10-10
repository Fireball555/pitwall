# PitWall

**Team Chumma Oru Commit** · CommitCon hackathon

Ram Smaran H (lead), Ashwin, Dharshini, Pranesh.

## Problem statement

Third Year, Non Circuit #5: **The Impossible Pit Stop (Race Strategist)**. Simulate fuel consumption and tyre performance, account for pit-stop time and tyre options, introduce changing race conditions, recommend and reconsider a strategy during the race, and compare it against a simple baseline across many simulated races.

## Our solution

PitWall simulates a race lap by lap: tyre wear, fuel weight, pit stops, rain and safety cars. Tyre wear, fuel effect and pit-stop loss are fitted from real F1 races (2022 and 2023 pooled; Zandvoort 2022 only, and Singapore in effect 2023 only because its wet 2022 laps are filtered out); safety-car and rain rates from 2018–2023 (3 to 6 races per track).

Our strategist re-plans **every lap**:
- It lists the options: stay out, or pit for each available tyre (plus how much fuel in endurance mode).
- It plays out the rest of the race 100 times for each option. These imagined futures use only what a real team could know: track history and a forecast.
- In each imagined future, later pit calls follow one of 9 simple plans (the basic rules, a longer-stint version, run to the flag, or 1- and 2-stop plans); each option is scored with the plan that suits it best.
- It picks the option with the best average finish (Monte Carlo policy rollout, Bertsekas).
- **You can watch it think.** At every PitWall pit call the app pauses and shows the imagined futures behind each option ("Explain calls"), then carries on.

To prove it works, four identical cars race identical conditions; only the strategy differs:

| Car | Strategy |
| --- | --- |
| **Purple circle** | **Ours (PitWall).** On F1 timing screens purple means fastest, so nothing else is purple. |
| Teal diamond | A fixed pre-race plan, followed blindly (Bahrain: Pirelli's 2023 preview; other tracks: assumed one-stop, see `data/pirelli.json`) |
| Pink triangle | Simple rules (pit when tyres are worn, inters when wet) |
| Grey hollow diamond | Hindsight: PitWall's own method, but given the real future (a reference, not a perfect optimum) |

There are two modes:
- **F1:** real 2023 rules, no refuelling.
- **Endurance:** a small tank, so the strategist also decides how much fuel to take on.

We test across 1000 random races per track, including a **fairness test** where the true numbers are secretly different from what the strategists believe. We also replay **real 2023 races** (Bahrain, Monza, Singapore) with our strategist replacing one driver.

## Technologies

- **Backend:** Python 3.12, numpy, pandas, FastF1, FastAPI, uvicorn, pytest.
- **Frontend:** React 18 built with Vite, Recharts for charts, Archivo and Chivo Mono fonts.

The Python server runs the simulator and also serves the built React app, so the demo is one command. The built app (`frontend/dist`) is included, so Node is only needed to change the frontend.

```
browser (React)  --/api/race, /api/proof, /api/replay-->  FastAPI (pitwall/server.py)
                                                           |-- engine/    lap model, safety cars, rain, pit stops
                                                           |-- strategy/  Pirelli plan, rules, our rollout, Hindsight
                                                           |-- eval/      many-race test, confidence intervals
                                                           '-- data/      real F1 numbers (FastF1)
```

## How to run

```bash
# Mac / Linux
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                   # fast tests (about 20 s)
pytest -m slow                           # extensive sweep: every track, rule set, weather, forced event and replay
python -m pitwall.engine.race            # one demo race in the terminal
python -m pitwall.server                 # the app: opens http://127.0.0.1:8000

# Windows (PowerShell)
py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
python -m pitwall.server
```

Changing the frontend (needs Node 18+):

```bash
cd frontend && npm install
npm run dev        # live-reload on http://localhost:5173, talks to the server on :8000
npm run build      # rebuilds frontend/dist, which the Python server serves
```

Other commands:
- **Real F1 data**, needs internet the first time: `python -m pitwall.data.build --all`
- **Full evaluation** (1000 races per track, all CPU cores): `python -m pitwall.eval.batch --all --n 1000`, then `python -m pitwall.eval.metrics`
- **Replay real races** for midfield drivers: `python -m pitwall.engine.replay bahrain` (also `monza`, `singapore`)
- **Model accuracy on an unseen race:** `python -m pitwall.data.accuracy`
- **Rewrite the Results section below from `results/`:** `python -m pitwall.eval.report`
- **Click through the whole app in a browser** (needs `pip install playwright`): `python tests/e2e_ui.py`
- **Hard questions a judge might ask, with our answers:** `docs/PANEL_QA.md`

## Trying different inputs

In the app's **Live race** tab, pick the track, F1 or endurance mode, the race seed, the rain chance and the safety-car frequency, then press **Run race**. Each race runs live in a few seconds. The same inputs work from the browser or the terminal:

```
http://127.0.0.1:8000/api/race?track=zandvoort&mode=endurance&seed=42&rain=0.8&sc=2
```

| Endpoint | What it returns |
| --- | --- |
| `/api/meta` | tracks, cars, and where each track's numbers come from |
| `/api/race?track&mode&seed&rain&sc&n` | one race, lap by lap, with every strategist decision |
| `/api/proof?track&mode` | the many-race results (after `pitwall.eval.batch`) |
| `/api/replay?track&driver` | our strategist inside a real 2023 race |

## Results

<!-- results:start -->
1000 random races per track (F1 rules), 500 for endurance and the fairness test. All four cars race the same weather, safety cars and lap noise. "Gain" is how many seconds earlier PitWall finished. The 95% interval is a bootstrap over simulated races: it covers simulation noise only, assuming our fitted tyre, rain and safety-car numbers are right. Full numbers: `results/summary.json`, or the app's **Proof** tab. This section is written by `python -m pitwall.eval.report`.

| Track (F1) | Gain vs pre-race plan | Won | Gain vs simple rules | Won |
| --- | --- | --- | --- | --- |
| Bahrain | +0.8 s (+0.5 to +1.2) | 56% | +14.7 s (+14.3 to +15.0) | 99% |
| Monza | +1.1 s (+0.8 to +1.5) | 65% | −0.1 s (−0.3 to +0.1) | 20% |
| Zandvoort | +9.5 s (+7.8 to +11.5) | 51% | +13.5 s (+12.7 to +14.3) | 92% |
| Singapore | +13.5 s (+12.3 to +14.6) | 86% | +12.9 s (+12.0 to +13.8) | 88% |

What this shows, honestly:
- **The advantage comes mostly from changing conditions.** In wet races PitWall gains +15.8 to +35.0 s on the pre-race plan; in dry races +0.7 s at Bahrain, +0.8 s at Monza, +8.1 s at Singapore, +0.5 s at Zandvoort. Wet races supply 48% of the Bahrain gain, 21% of the Monza gain, 51% of the Singapore gain, 89% of the Zandvoort gain.
- **More rain, bigger advantage** (Zandvoort, same 200 races at each rain chance): +0.5 s with no rain, +10.7 s at a 50% rain chance.
- **Monza vs the simple rules:** −0.1 s (−0.3 to +0.1) on average, but the simple rules finish ahead in 80% of races. Monza's three dry tyres come out identical (our soft-never-slower constraint merges them), so there is little to optimise.
- **Fairness test** (true tyre wear, compound pace and pit loss secretly different from what every strategist believes; rain and safety-car rates unchanged): +0.8 s at Bahrain, +12.2 s at Singapore.
- **Endurance mode** (fuel calls too): +3.8 s at Bahrain, +32.7 s at Singapore vs the pre-race plan. Part of the Singapore number is the fixed plans' late fuel stop.
- The pre-race plan never fits slicks on a wet track, but it does not see the rain radar PitWall uses, so part of the wet gain is information, not cleverness.
- At Singapore the assumed pre-race plan and the simple rules often make the same stops, so both baselines score alike.

**Real 2023 races.** PitWall replaced one midfield driver; we compare it with that driver's real pit stops run through the same simulator (the fair comparison: same model for both).

| Race | Driver | Real finish | Real stops in our sim | PitWall |
| --- | --- | --- | --- | --- |
| Bahrain | ALB | P10 | P8 | **P4** |
| Bahrain | BOT | P8 | P8 | **P4** |
| Bahrain | STR | P6 | P6 | **P4** |
| Monza | ALO | P9 | P7 | **P6** |
| Monza | BOT | P10 | P10 | **P10** |
| Monza | HAM | P6 | P6 | **P6** |
| Singapore | ALB | P11 | P6 | **P4** |
| Singapore | GAS | P6 | P6 | **P6** |
| Singapore | HUL | P13 | P9 | **P8** |

The tyre numbers were fitted on these same races, so the replays are a demonstration, not proof of a real-world gain. Our simulator runs the real strategies faster than they really went, so we only compare PitWall with the real stops inside the same simulator.

**Lap-time model on a race it has never seen** (fit on 2022, predict 2023, `python -m pitwall.data.accuracy`): Bahrain 0.45 s per lap (skill +0.76), Monza 0.44 s per lap (skill −0.03), Zandvoort 0.52 s per lap (skill +0.51), Singapore 2.06 s per lap (skill −3.22). Skill compares with a flat line: Bahrain is genuinely predictive; Monza and Zandvoort predict the average well but not the shape within a stint; Singapore does not transfer from 2022 (a wet race) to 2023, so its numbers rest on the 2023 race alone.
<!-- results:end -->

## External resources

- [React](https://react.dev), [Vite](https://vitejs.dev), [Recharts](https://recharts.org), [FastAPI](https://fastapi.tiangolo.com) and the [Barlow](https://fonts.google.com/specimen/Barlow) fonts (all open source).
- [FastF1](https://github.com/theOehrly/Fast-F1) (MIT licence): access to Formula 1 timing data. We use 2023 race laps, tyres, pit stops, track status and weather, plus 2018–2023 track status for safety-car rates. The data is used non-commercially, for this hackathon only.
- [Pirelli 2023 Bahrain GP preview](https://press.pirelli.com/2023-bahrain-grand-prix---saturday/), for the Bahrain pre-race plan.
- Policy rollout (Bertsekas), the decision method our strategist is based on.

## Use of AI tools

- The code was written mostly by AI assistants: **Claude** (Anthropic: Claude Code and claude.ai) and **Antigravity** (Google).
- The team made the decisions: problem choice, approach, which data to use, the fairness tests.
- The team reviewed and tested the code and can explain it.
- The plan and the first working version were produced with Claude.

## Honest limits

- Every number in `data/tracks/*.json` says where it came from. Not fitted from data: tyre cliff and warm-up, wet-weather penalties, Singapore's soft tyre (too few laps), Monza's fuel effect, and some safety-car pit losses (too few stops).
- At Monza the data can't tell the three dry tyres apart, so they behave the same.
- The pre-race plans for Monza, Zandvoort and Singapore are assumed, not Pirelli's published 2023 plans.
- In endurance mode, tank size and refuel speed are assumed (2009-era F1).
- In the replay, the recorded cars can't react to ours, and the traffic rule is a simplification. Our simulator runs the real strategies faster than they really went (0–5 places), so we only compare PitWall with the driver's real pit stops run through the same simulator. Zandvoort 2023 is not replayed: its red flag isn't modelled.
- Hindsight ("oracle" in the code and results) is a reference, not an optimum: it uses PitWall's lap-by-lap method with the real future, and in some races it finishes behind a fixed plan.
- No track position: cars don't block each other in the 4-car race (only the real-race replay has traffic), so undercuts and overcuts aren't modelled.
- The 95% intervals cover simulation noise only. Rain and safety-car rates come from 3–6 races per track, so the true rates (and so the size of the wet-race gain) are uncertain.
- Safety-car pit loss is measured at Bahrain and Monza and assumed (0.55 × green) at Zandvoort and Singapore, where the measurement was unreliable.
