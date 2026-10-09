# PitWall

A race strategist that decides every lap whether to pit, which tyre to fit and (in endurance mode)
how much fuel to add — calibrated on real 2023 F1 data, and evaluated against simpler strategies.

## Setup

```bash
# Linux / macOS
git clone https://github.com/Fireball555/pitwall.git && cd pitwall
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pytest -q
```

```powershell
# Windows (PowerShell)
git clone https://github.com/Fireball555/pitwall.git; cd pitwall
py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt; pytest -q
```

## Run the demo race

```bash
python -m pitwall.sim.race --demo
```
