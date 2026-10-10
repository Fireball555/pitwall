# Demo run sheet (about 5 minutes)

Start the app before the call: `python -m pitwall.server`, then open http://127.0.0.1:8000 full screen. Keep "Explain calls" on.

## 1. Live race (2 min)

**"Bahrain · rain arrives"** is selected on load. Let the start lights run.

- **Say first:** "Four identical cars, same weather, same safety cars. Only the strategist differs. Purple is ours, PitWall. On F1 timing screens purple means fastest."
- **When rain arrives (around lap 13):** PitWall pauses on its pit call and shows its imagined futures. Say: "Each dot is one imagined rest-of-the-race. It tested every choice on the same 100 futures and picked the one that finishes first on average." Then click *Continue race*.
- **Point at the delta plate (top right of the map):** PitWall vs the Pirelli plan in seconds.
- **To finish:** drag the timeline to the end. The verdict reads: PitWall beat the Pirelli plan by about 37 s.

## 2. Different inputs (1 min, or whenever a judge asks)

- **During any race:** press **Rain**, **Heavy rain**, **Safety car** or **Dry**. It starts from the next lap and all four strategists react.
- **Custom race ▾:** any track, F1 or endurance rules, weather, safety cars or race number.
- **If a random race loses, say so:** "It loses some races; across 1000 races it wins on average." Then go to Proof.

## 3. Proof (1 min)

- **Scoreboard:** PitWall beats the fixed plan at all four tracks.
- **Say plainly:** the edge comes mostly from rain. In dry races it is small, about 1 s.
- **Rain line:** more rain, bigger advantage.
- **Fairness test:** it still wins when its tyre numbers are wrong.

## 4. Real races (1 min)

- **Bahrain 2023, ALB:** the real starting grid. Press **Lights out**, let it run a few laps, then *Skip to the flag*.
- **The reveal:** PitWall finishes P4. Albon's real stops in our simulator finish P8, and Albon really finished P10.
- **Say:** "We compare against his real stops in the same simulator, so the model's own errors cancel."

## If something breaks

- **Server not reachable:** restart `python -m pitwall.server`.
- **A screen looks stuck:** reload the page; every race is reproducible.
- **Hard questions:** see `docs/PANEL_QA.md`.
