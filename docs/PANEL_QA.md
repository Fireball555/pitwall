# Hard questions, and our answers

Before the demo we put PitWall in front of a mock judging panel: an F1 race strategist, an operations-research researcher, a statistician, a software engineer, a UX designer and a hackathon judge. Each read every file and tried to break the project. These are their questions and our honest answers. **Fixed** means we changed the project because of the question. **Limit** means we know, and say so.

Short answers for the stage are in bold. The longer explanation is underneath.

## The idea

**Q1. In one sentence, what does PitWall do?**
**Every lap, it plays out the rest of the race 100 times for each option (stay out, or pit for each tyre) and picks the option that finishes first on average.** That is Monte Carlo policy rollout (Bertsekas). The imagined futures use only what a team could know: the track's history, the weather radar and the current state of the car.

**Q2. Why not just optimise the pit stops before the race?**
**Because the race changes.** A fixed plan can't react to a safety car or rain. Our results show exactly that: in dry races the fixed plan is almost as good (+0.7 s at Bahrain), in wet races PitWall gains 16–35 s.

**Q3. Why is this better than the simple rules a team might use?**
Rules like "pit when the tyre is 80% worn" ignore what happens next. PitWall scores each choice by its consequences. Against the simple rules it is +13 to +15 s at three tracks and wins 88–99% of races. At Monza it ties (see Q18).

**Q4. What is the "Hindsight" car?**
**The same method given the real future: weather, safety cars, lap noise.** It shows how much of the remaining gap is uncertainty. It is not a perfect optimum. It still decides one lap at a time, so in some races it finishes behind a fixed plan. *Limit:* an exact optimum (dynamic programming over the known future) is the next step.

## Strategy (asked by the F1 strategist)

**Q5. Safety car on laps 13–16, you're on 12-lap softs. Do you box?**
**Only if the imagined futures say the cheaper stop is worth it, and you can watch it weigh that on screen.** In our data a stop under the safety car at Bahrain costs 19.6 s instead of 24.4 s (measured from real 2022–23 stops), which is a small saving, so it often stays out. *Limit:* at Zandvoort and Singapore the safety-car measurement was unreliable, so we assume 0.55 × the normal loss. In chaotic Bahrain races our gain over the fixed plan is about zero. Safety cars are not where our advantage comes from; rain is.

**Q6. Undercut, overcut, track position?**
**Not modelled in the 4-car race. The cars are "ghosts" racing the clock, so we isolate the value of strategy itself.** The real-race replay does have traffic: a car within 1 s that isn't much faster gets stuck. *Limit:* an undercut duel against a rival is the obvious next feature.

**Q7. Where do the tyre numbers come from?**
Tyre wear, compound pace and fuel effect come from one least-squares fit with a pace offset per driver, using every clean racing lap of the 2022 and 2023 races (FastF1). The compound order is enforced: a softer tyre is never slower and never wears slower. *Limit:* the "cliff" (where wear suddenly accelerates) and the warm-up lap are assumed, not fitted.

**Q8. Do you chase the weather?**
Sometimes. Each imagined future picks its own rain peak, so in very heavy rain PitWall can switch inters → wets just before the rain eases. *Limit:* we documented it rather than tune it the night before.

**Q9. Did PitWall ever pit twice in a row for nothing?**
**It did, and we fixed it.** Two bugs in its imagined futures caused it. None of its 8 follow-up plans meant "no more stops", so staying out was always charged a later stop. And the stint length after "pit now" counted the age of the tyre coming off. *Fixed:* we added a "run to the flag" plan and corrected the stint length. On 96 held-out races the fix gained +3.6 s at Singapore and +8 s in wet Bahrain races. It was neutral at Bahrain, Monza and Zandvoort in the dry.

**Q10. Are the baselines straw men?**
We tried hard to avoid that.
- The fixed plan is Pirelli's published 2023 plan at Bahrain. It never fits slicks on a wet track: *fixed*, after we caught it doing exactly that.
- In the dry it is close to PitWall, which is honest.
- *Limit:* both baselines react to rain later than the model's ideal switching point, and neither sees the rain radar. Part of the wet-race gain is information, not cleverness.

**Q11. What about the two-compound rule, tyre allocation, fuel?**
- **Two-compound rule:** enforced in dry races. A car that breaks it is disqualified in the simulator, and our tests check every car in every race.
- **Tyre sets:** fixed per car (a realistic 2023 race allocation).
- **Endurance mode:** a small tank, so every stop also decides how much fuel to take. No car may overfill. A fixed plan can run dry in a chaotic wet race (Monza, endurance, wet, lots of safety cars, race 13: the Pirelli plan stops on lap 28). The app then shows it as out of the race, and a test checks that.

## Method (asked by the OR researcher)

**Q12. Is rollout guaranteed to beat its base policies?**
In expectation, yes: rollout improves on the plans it imagines with (Bertsekas). We score each option with the best of 9 plans on the same futures, so it is at least as good as the best of them in the model. That is why PitWall beats the simple rules, which are one of those plans.

**Q13. Why 100 futures? Isn't that noisy?**
**Every option is scored on the same 100 futures (common random numbers), so the noise largely cancels when we compare options.** It also only pits when the gain is above 0.5 s. 100 futures × 4 options × 9 plans run as one numpy batch, a few seconds for a whole race on a laptop.

**Q14. Can it cheat by peeking at the future?**
**No, and a test proves it.** We change everything after lap 25 and check that no decision up to lap 25 changes. The "Rain now" button is also a true surprise: the radar only shows it from the lap you press, and a second test checks that.

## Statistics (asked by the statistician)

**Q15. Is +0.8 s at Bahrain real or luck?**
**It is real inside the model: 1000 paired races, 95% interval +0.5 to +1.2 s.** "Paired" means all four cars race identical weather, safety cars and lap noise, so luck cancels.
*Limit:* that interval covers simulation noise only. It assumes our fitted numbers are right.

**Q16. How accurate is the simulator on a race it has never seen?**
**We fitted on 2022 and predicted every 2023 lap.**

| Track | Error per lap | Notes |
| --- | --- | --- |
| Bahrain | 0.45 s | Genuinely predictive: 76% better than a flat line |
| Monza | 0.44 s | Predicts the average, not the shape within a stint |
| Zandvoort | 0.52 s | Predicts the average, not the shape within a stint |
| Singapore | 2.06 s | The 2022 race was wet, so it doesn't transfer |

Singapore's numbers therefore rest on the 2023 race alone. Run `python -m pitwall.data.accuracy`. The result is shown on the Proof screen.

**Q17. Where does the gain actually come from?**
**Mostly rain.** Wet races supply 89% of the Zandvoort gain, 51% at Singapore and 48% at Bahrain. We say this up front.
*Limit:* rain probabilities come from only 3–6 races per track. Zandvoort is 1 wet race in 3, so the true wet-race share is uncertain.

**Q18. Monza: you "tie" the simple rules, but they finish ahead in 80% of races?**
Yes. They are slightly ahead most of the time by tiny margins, and PitWall wins big occasionally, so the average is −0.1 s (−0.3 to +0.1).
*Limit:* Monza's three tyres come out identical because our soft-never-slower constraint merges noisy fits. So "nothing to optimise" is partly our assumption.

**Q19. The rain sweep rises smoothly. Isn't that built in?**
Partly. The same 200 races are used at each rain chance, so the wet races at 20% are a subset of those at 40%. That makes the comparison fair (paired), and it also makes the curve smooth. With no rain PitWall is only 0.5 s ahead of the fixed plan.

**Q20. Do the real-race replays prove a real-world gain?**
**No, and we don't claim it.** The tyre numbers were fitted on those same races, and our simulator runs the real strategies faster than they really went. So we compare PitWall only with the driver's real pit stops run through the same simulator. Across 9 drivers that gives 2–4 places better at Bahrain, 0–2 at Singapore and 0–1 at Monza, and never worse. It is a demonstration that the pipeline works on real data.

**Q21. What does the fairness test change?**
Tyre wear, compound pace and pit loss are drawn from the uncertainty of our own fit (bootstrap over drivers). PitWall still gains +0.8 s at Bahrain and +12.2 s at Singapore.
*Limit:* rain and safety-car rates are not perturbed.

## Engineering (asked by the software engineer)

**Q22. Is it reproducible?**
**Yes. Same inputs give the same race on any computer:** every random number comes from one seeded generator, and a test checks it. The six demo races were chosen this way and verified on the final code.

**Q23. How is it tested?**
Three layers:
1. **Fast unit and API tests (25, about 20 s)**, run by GitHub CI on every pull request. They cover the engine, strategies, data, evaluation and API, including the no-peeking test.
2. **An extensive sweep (`pytest -m slow`).** It runs every track × both rule sets × dry / usual / wet weather, plus forced rain, dry and safety cars, every replay, a car running out of fuel, and bad inputs (32 checks, about a minute). Each race is checked against the rules:
   - time always increases and no lap time is absurd
   - fresh tyres after every stop
   - the two-compound rule holds
   - no car runs out of fuel or overfills
   - replays keep a consistent running order
3. **A browser click-through (`tests/e2e_ui.py`)** that presses every control on all three screens at two screen sizes and fails on any browser error.

**Q24. Why FastAPI + React instead of one tool?**
The simulator is numpy and fast. The app needs smooth animation at 60 fps (cars moving on a real track outline, start lights, the futures view). The server also serves the built React app, so the demo is one command: `python -m pitwall.server`.

**Q25. How fast is it?**
A full race with all four strategists takes a few seconds (it re-plans every lap). The 1000-race evaluation of all 4 tracks takes about 15 minutes on 20 CPU cores.

## The demo (asked by the UX designer and the hackathon judge)

**Q26. What should I look at first?**
- **Live race:** the purple PitWall card and the delta at the top ("PitWall vs Pirelli plan"). Purple means PitWall and only PitWall, as on F1 timing screens, where purple is the fastest sector.
- **Real races:** the purple row in the timing tower against the dashed "for real" ghost row.

**Q27. Can I change the inputs?**
Yes:
- **Before a race:** any track, F1 or endurance rules, dry / usual / wet weather, few or many safety cars, any race number.
- **During a race:** press Rain, Heavy rain, Dry or Safety car, and all four strategists react from the next lap. Each can be used once per race, so laps you have already watched never change.

**Q28. What happens inside its head?**
**Turn on "Explain calls".** At each PitWall pit call the race pauses and shows every imagined finish time for each option, the averages, and the winner.

## Questions we couldn't fully answer (next steps)

These are the panel's interesting ideas we didn't have time for:
- **An undercut duel** against one rival car, scoring "finish ahead of him" instead of "finish fast", with traffic in the imagined futures.
- **A true optimum for Hindsight**, by dynamic programming over the known future.
- **Fit the cliff and warm-up**, and age tyres slower under a safety car.
- **Tie the rain peak in the imagined futures to the trend on the radar**, to stop chasing the weather.
- **A "best fixed plan" baseline** optimised on the same model, to measure the pure value of re-planning.
