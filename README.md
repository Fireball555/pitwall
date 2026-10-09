# PitWall

**Team Chumma Oru Commit** · CommitCon hackathon

Ram Smaran H (lead), Ashwin, Dharshini, Pranesh.

## Problem statement

Third Year, Non Circuit #5: **The Impossible Pit Stop (Race Strategist)**. Simulate fuel consumption and tyre performance, account for pit-stop time and tyre options, introduce changing race conditions, recommend and reconsider a strategy during the race, and compare it against a simple baseline across many simulated races.

## Our solution

PitWall simulates a race lap by lap: tyre wear, fuel weight, pit stops, rain and safety cars. Tyre wear, fuel effect and pit-stop loss are fitted from real 2022–2023 F1 races; safety-car and rain rates from 2018–2023.

Our strategist re-plans **every lap**:
- It lists the options: stay out, or pit for each available tyre (plus how much fuel in endurance mode).
- It plays out the rest of the race 100 times for each option. These imagined futures use only what a real team could know: track history and a forecast.
- In each imagined future, later pit calls follow one of 8 simple plans (the basic rules, or 1- and 2-stop plans); each option is scored with the plan that suits it best.
- It picks the option with the best average finish (Monte Carlo policy rollout, Bertsekas).

To prove it works, four identical cars race identical conditions; only the strategy differs:

| Car | Strategy |
| --- | --- |
| Purple | A fixed pre-race plan, followed blindly (Bahrain: Pirelli's 2023 preview; other tracks: assumed one-stop, see `data/pirelli.json`) |
| Orange | Simple rules (pit when tyres are worn, inters when wet) |
| **Cyan** | **Ours (PitWall)** |
| Grey | Oracle: knows the real future, as an upper reference |

There are two modes:
- **F1:** real 2023 rules, no refuelling.
- **Endurance:** a small tank, so the strategist also decides how much fuel to take on.

We test across 1000 random races per track, including a **fairness test** where the true numbers are secretly different from what the strategists believe. We also replay **real 2023 races** (Bahrain, Monza, Singapore) with our strategist replacing one driver.

## Technologies

- **Backend:** Python 3.12, numpy, pandas, FastF1, FastAPI, uvicorn, pytest.
- **Frontend:** React 18 built with Vite, Recharts for charts, Barlow fonts.

The Python server runs the simulator and also serves the built React app, so the demo is one command. The built app (`frontend/dist`) is included, so Node is only needed to change the frontend.

```
browser (React)  --/api/race, /api/proof, /api/replay-->  FastAPI (pitwall/server.py)
                                                           |-- engine/    lap model, safety cars, rain, pit stops
                                                           |-- strategy/  Pirelli plan, rules, our rollout, Oracle
                                                           |-- eval/      many-race test, confidence intervals
                                                           '-- data/      real F1 numbers (FastF1)
```

## How to run

```bash
# Mac / Linux
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                   # all tests
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
- In the replay, the recorded cars can't react to ours, and the traffic rule is a simplification. Our simulator is 2–4 places optimistic, so we compare PitWall with the driver's real pit stops run through the same simulator. Zandvoort 2023 is not replayed: its red flag isn't modelled.
- The Oracle is a strong reference, not a proven optimum.
