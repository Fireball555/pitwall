# PitWall

A race strategist that decides every lap whether to pit, which tyre to fit and (in endurance mode)
how much fuel to add — calibrated on real 2023 F1 data, and evaluated against simpler strategies.

## Team

TODO (UI8, Pranesh): team name and members with roles.

## Problem statement

TODO (UI8, Pranesh): Third Year, Non Circuit #5, The Impossible Pit Stop.

## Solution

TODO (UI8, Pranesh): the solution in brief.

## Technologies and tools

TODO (UI8, Pranesh): Python 3.12, numpy, pandas, FastF1, Streamlit, Plotly.

## How to run

```bash
# Linux / macOS
git clone https://github.com/Fireball555/pitwall.git && cd pitwall
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pytest -q
python tools/task.py role SIM            # your role: BR | SIM | DAT | UI
```

```powershell
# Windows (PowerShell)
git clone https://github.com/Fireball555/pitwall.git; cd pitwall
py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt; pytest -q
python tools/task.py role DAT
```

Run the demo race:

```bash
python -m pitwall.sim.race --demo
```

## External resources

TODO (UI8, Pranesh / DAT supplies the data-source list): FastF1, Formula 1 2023 timing data via FastF1,
Pirelli 2023 race-preview press releases.

## Use of AI tools

TODO (UI8, Pranesh / Smaran supplies the wording): Claude Code and Antigravity wrote most code under
human direction; humans reviewed, tested and can explain it.
