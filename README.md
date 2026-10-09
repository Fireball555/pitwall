# PitWall

**Team Chumma Oru Commit** · CommitCon hackathon

| Member | Module |
| --- | --- |
| Ram Smaran H | Strategy and evaluation (`pitwall/strategy`, `pitwall/eval`), team lead |
| Ashwin | Race engine and real-race replay (`pitwall/engine`) |
| Dharshini | Real F1 data (`pitwall/data`, `data/`) |
| Pranesh | Web app, README and presentation (`frontend/`, `pitwall/server.py`) |

## Problem statement

Third Year, Non Circuit #5: **The Impossible Pit Stop (Race Strategist)**. Simulate fuel consumption and tyre performance, account for pit-stop time and tyre options, introduce changing race conditions, recommend and reconsider a strategy during the race, and compare it against a simple baseline across many simulated races.

## Our solution

PitWall simulates a race lap by lap: tyre wear, fuel weight, pit stops, rain and safety cars. The numbers are fitted from real 2023 F1 data.

Our strategist re-plans **every lap**:
- It lists the options: stay out, or pit for each available tyre (plus how much fuel in endurance mode).
- It plays out the rest of the race 200 times for each option. These imagined futures use only what a real team could know: track history and a forecast.
- It picks the option with the best average finish (Monte Carlo policy rollout).

To prove it works, four identical cars race identical conditions; only the strategy differs:

| Car | Strategy |
| --- | --- |
| Purple | Pirelli's published pre-race plan, followed blindly |
| Orange | Simple rules (pit when tyres are worn, inters when wet) |
| **Cyan** | **Ours (PitWall)** |
| Grey | Oracle: knows the real future, as an upper reference |

There are two modes:
- **F1:** real 2023 rules, no refuelling.
- **Endurance:** a small tank, so the strategist also decides how much fuel to take on.

We test across thousands of random races per track, including a **fairness test** where the true numbers are secretly different from what the strategists believe. We also replay **real 2023 races** with our strategist replacing one driver.

## Technologies

- **Backend:** Python 3.12, numpy, pandas, FastF1, FastAPI, uvicorn, pytest.
- **Frontend:** React 18 built with Vite, Recharts for charts, Barlow fonts.

The Python server runs the simulator and also serves the built React app, so the demo is one command. The built app (`frontend/dist`) is committed, so Node is only needed to change the frontend.

```
browser (React)  --/api/race, /api/proof, /api/replay-->  FastAPI (pitwall/server.py)
                                                           |-- engine/    lap model, safety cars, rain, pit stops
                                                           |-- strategy/  Pirelli plan, rules, our rollout, Oracle
                                                           |-- eval/      many-race test, confidence intervals
                                                           '-- data/      real 2023 F1 numbers (FastF1)
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
- **Full evaluation**, takes about 15 minutes on 20 cores: `python -m pitwall.eval.batch --all --n 1000`
- **Real 2023 data**, needs internet the first time: `python -m pitwall.data.build --all`
- **Replay real races** for midfield drivers: `python -m pitwall.engine.replay bahrain`

## Trying different inputs

In the app's **Live race** tab, pick the track, F1 or endurance mode, the race seed, the rain chance and the safety-car frequency, then press **Run race**. Each race runs live in 1–3 seconds. The same inputs work from the browser or the terminal:

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
- Pirelli 2023 race-preview press releases, for the "Pirelli plan" baseline.
- Policy rollout (Bertsekas), the decision method our strategist is based on.

## Use of AI tools

- The code was written mostly by AI assistants: **Claude** (Anthropic: Claude Code and claude.ai) and **Antigravity** (Google).
- The team made the decisions: problem choice, approach, which data to use, the fairness tests.
- The team reviewed and tested the code, and each member can explain their own module.
- The plan, the first working version and the task split were produced with Claude.

## Honest limits

- Until `pitwall.data.build` has been run, the track numbers are **placeholders** (marked in each `data/tracks/*.json`, and the app shows a banner).
- In endurance mode, tank size and refuel speed are assumed (2009-era F1).
- In the replay, the recorded cars can't react to ours, and the traffic rule is a simplification.
- The Oracle is a strong reference, not a proven optimum.
