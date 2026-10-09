"""Our strategist (cyan) and the Oracle (grey). Owner: Smaran (BR).

Idea (Monte Carlo policy rollout): after every lap, list the sensible options (stay out, or pit
for each compound, plus fuel amounts in endurance mode). For each option, play out the rest of
the race in 100 imagined futures, with later decisions following a simple base policy, and pick
the option with the best average finish.

The base policy is not one fixed rule but a small family of them (BASES): the simple rules with
different stint lengths and compound preferences. Each option is scored with whichever base
policy does best on average for it (a "superheuristic", Bertsekas). Rollout is guaranteed to do
at least as well as its base policies in expectation, so a richer family = a stronger strategist. Every option is scored on the SAME futures, so differences
come from the decision, not from luck. Everything is vectorised: all options x all futures run
as one numpy batch.
"""
from __future__ import annotations

import numpy as np

from pitwall.core import (COMPOUNDS, DRY_IDS, GREEN, INTER, SC, STAY, STATUS_NAMES, VSC, WET, Action,
                          CarState, Decision, Observation, TrackParams)
from pitwall.engine.lap import lap_time
from pitwall.engine.race import REFUEL_OVERLAP_S
from pitwall.engine.scenario import Scenario, sample_futures
from pitwall.strategy.rules import RULES

PENALTY = 1000.0  # seconds added for a DNF or a disqualification in an imagined future

# Base policies for the imagined futures, as (wear, preferred dry compound or -1 for the rules' choice):
#   wear > 0: pit when tyre age reaches wear x the compound's cliff lap (0.8 = the simple rules)
#   wear < 0: plan -wear more stops, splitting the remaining laps into equal stints
# (0.8, -1) is exactly the simple rules.
# 8 policies: the simple rules, a longer-stint variant, and 1- or 2-stop equal-stint plans.
BASES: list[tuple[float, int]] = [(0.8, -1), (1.0, -1), (-1, -1), (-1, 1), (-1, 2), (-2, -1), (-2, 0), (-2, 2)]


def _family(cid: np.ndarray) -> np.ndarray:
    return (cid >= INTER).astype(int)  # 0 = dry, 1 = wet tyres


def simulate(P: TrackParams, car: CarState, obs: Observation, actions: list[Action],
             fut: dict[str, np.ndarray], bases: list[tuple[float, int]] | None = None) -> np.ndarray:
    """Finish time of the rest of the race for every (action, base policy, future).
    Returns shape (len(actions), len(bases), n)."""
    bases = bases or [(RULES["wear_frac"], -1)]
    K, H, (n, R) = len(actions), len(bases), fut["status"].shape
    B = K * H * n
    status, wet, noise = (np.tile(fut[k], (K * H, 1)) for k in ("status", "wetness", "noise"))
    wear_frac = np.tile(np.repeat([b[0] for b in bases], n), K).astype(float)
    # equal-stint plans: stint length = (laps left + current tyre age) / (stops + 1)
    stops = np.maximum(-wear_frac, 0)
    stint = np.where(wear_frac < 0, np.ceil((R + car.age) / (stops + 1)), 0.0)
    pref = np.tile(np.repeat([b[1] for b in bases], n), K)
    inv = car.inventory
    m = len(inv)
    set_cid = np.array([s.cid for s in inv], dtype=int) if m else np.zeros(0, int)
    set_age = np.array([s.age for s in inv], dtype=float) if m else np.zeros(0)
    set_dry = set_cid < INTER
    avail = np.ones((B, m), dtype=bool)
    cid = np.full(B, max(car.cid, 0), dtype=int)
    age = np.full(B, float(car.age))
    fuel = np.full(B, float(car.fuel))
    total = np.zeros(B)
    used = np.zeros((B, 3), dtype=bool)
    for c in car.used_dry:
        used[:, c] = True
    race_wet = np.full(B, obs.race_was_wet)
    dead = np.zeros(B, dtype=bool)
    rows = np.arange(B)
    endurance = P.mode == "endurance"

    first_pit = np.repeat([a.pit for a in actions], H * n)
    ids = [s.set_id for s in inv]
    first_choice = np.repeat([ids.index(a.set_id) if a.pit else -1 for a in actions], H * n)
    first_fuel = np.repeat([a.fuel_add for a in actions], H * n).astype(float)

    for k in range(R):
        left = R - k
        if k == 0:
            pit, choice, fuel_add = first_pit, first_choice, first_fuel
        else:
            pit, choice, fuel_add = _rules_policy(P, wet[:, k - 1], cid, age, fuel, used, race_wet, avail,
                                                  set_cid, set_age, set_dry, left, wear_frac, pref, stint)
        has = pit & (choice >= 0)
        safe_choice = np.where(has, choice, 0)
        loss = np.zeros(B)
        if obs.lap + k > 0:
            loss = np.where(has, np.where(np.isin(status[:, k], (SC, VSC)), P.pit_loss_sc, P.pit_loss), 0.0)
        if endurance:
            added = np.where(has, np.clip(fuel_add, 0.0, P.tank - fuel), 0.0)
            fuel = fuel + added
            if obs.lap + k > 0:
                loss = loss + np.where(has, np.maximum(0.0, added / P.refuel_rate - REFUEL_OVERLAP_S), 0.0)
        if m:
            new_cid = set_cid[safe_choice]
            cid = np.where(has, new_cid, cid)
            age = np.where(has, set_age[safe_choice], age)
            avail[rows[has], choice[has]] = False
            dry_has = has & (new_cid < INTER)
            used[rows[dry_has], new_cid[dry_has]] = True
        lt = lap_time(P, cid, age, fuel, wet[:, k], status[:, k], noise[:, k])
        total += lt + loss
        age += 1
        fuel -= P.fuel_burn
        if endurance:
            dead |= fuel < -1e-9
        race_wet |= wet[:, k] > 0.2
    total += np.where(dead, PENALTY, 0.0)
    if not endurance:
        total += np.where(~race_wet & (used.sum(1) < 2), PENALTY, 0.0)
    return total.reshape(K, H, n)


def _rules_policy(P, w, cid, age, fuel, used, race_wet, avail, set_cid, set_age, set_dry, left,
                  wear_frac=None, pref=None, stint=None):
    """numpy twin of RulesStrategy.decide, for many futures at once. wear_frac and pref (per row)
    turn it into the family of base policies; the defaults are exactly the simple rules."""
    B = len(cid)
    is_wet_tyre = cid >= INTER
    full_wet = w >= RULES["wet_at"]
    inter = (w >= RULES["inter_at"]) & ~full_wet
    weather = (full_wet & (cid != WET)) | (inter & ~is_wet_tyre) | (is_wet_tyre & (w < RULES["slick_at"]))
    wf = RULES["wear_frac"] if wear_frac is None else wear_frac
    limit = wf * P.cliff_lap[cid]
    if stint is not None:
        limit = np.where(stint > 0, stint, limit)
    worn = ~is_wet_tyre & (age >= limit) & (left > 5)
    n_used = used.sum(1)
    other_dry = (avail & set_dry[None, :] & ~used[:, np.minimum(set_cid, 2)]).any(1) if len(set_cid) else np.zeros(B, bool)
    two = ~race_wet & (n_used < 2) & (left <= RULES["two_compound_by"]) & ~is_wet_tyre & other_dry
    fuel_low = np.zeros(B, bool)
    if P.mode == "endurance":
        fuel_low = fuel < P.fuel_burn * RULES["fuel_margin_laps"]
    pit = (weather | fuel_low | (~weather & (worn | two))) & (left > 1)

    # dry compound choice: order by laps left, unused compounds first while the 2-compound rule is open
    if left > RULES["hard_if_left"]:
        rank = np.array([2, 1, 0])
    elif left > RULES["medium_if_left"]:
        rank = np.array([2, 0, 1])
    else:
        rank = np.array([0, 1, 2])
    score = np.tile(rank.astype(float), (B, 1)) + np.where((n_used < 2)[:, None] & used, 10.0, 0.0)
    if pref is not None:
        score -= np.where(np.arange(3)[None, :] == pref[:, None], 5.0, 0.0)  # preferred compound first
    if len(set_cid):
        has_c = np.stack([(avail & (set_cid == c)[None, :]).any(1) for c in DRY_IDS], axis=1)
        score += np.where(has_c, 0.0, 100.0)
    dry_target = np.argmin(score, axis=1)
    target = np.where(full_wet, WET, np.where(inter, INTER, dry_target))
    target = np.where(weather, target, np.where(worn | two, dry_target, cid))

    if len(set_cid):
        fam_match = _family(set_cid)[None, :] == _family(target)[:, None]
        pen = np.where(set_cid[None, :] == target[:, None], 0.0, np.where(fam_match, 500.0, 1e5))
        cost = pen + set_age[None, :] + np.where(avail, 0.0, 1e6)
        choice = np.argmin(cost, axis=1)
        choice = np.where(cost[np.arange(B), choice] >= 1e5, -1, choice)
    else:
        choice = np.full(B, -1)
    fuel_add = np.zeros(B)
    if P.mode == "endurance":
        fuel_add = np.clip(np.minimum(P.tank - fuel, left * P.fuel_burn + 0.5 - fuel), 0.0, None)
    return pit, choice, fuel_add


class RolloutStrategy:
    name = "rollout"

    def __init__(self, n: int = 100, seed: int = 0, hysteresis: float = 0.5):
        self.n, self.seed, self.hysteresis = n, seed, hysteresis

    def reset(self, belief: TrackParams, car: CarState) -> None:
        self.P = belief
        self.rng = np.random.default_rng(self.seed)

    def futures(self, obs: Observation) -> dict[str, np.ndarray]:
        return sample_futures(self.P, obs.lap, obs.status, obs.wetness, obs.rain_forecast, self.n, self.rng)

    def options(self, car: CarState, obs: Observation) -> list[tuple[str, Action]]:
        P, left = self.P, obs.laps - obs.lap
        soon_wet = obs.wetness > 0.1 or (len(obs.rain_forecast) and obs.rain_forecast[:10].max() > 0.2)
        if obs.lap == 0:
            cids = list(DRY_IDS) + ([INTER, WET] if soon_wet else [])
        elif left <= 1:
            return [("stay out", STAY)]
        else:
            quiet = (car.age < 3 and obs.status == GREEN and not soon_wet and car.cid in DRY_IDS
                     and not (P.mode == "endurance" and car.fuel < 3 * P.fuel_burn))
            cids = [] if quiet else list(DRY_IDS) + ([INTER, WET] if soon_wet or car.cid >= INTER else [])
        opts = [] if obs.lap == 0 else [("stay out", STAY)]
        for c in cids:
            sets = [s for s in car.inventory if s.cid == c]
            if not sets:
                continue
            s = min(sets, key=lambda t: t.age)
            if P.mode == "endurance" and obs.lap > 0:
                room = P.tank - car.fuel
                finish = max(0.0, left * P.fuel_burn + 0.5 - car.fuel)
                amounts = {"to finish": finish} if finish <= room else {}
                amounts.update({"full tank": room, "half tank": room / 2})
                for lab, amt in amounts.items():
                    opts.append((f"pit {COMPOUNDS[c]} + {amt:.0f} kg ({lab})", Action(True, s.set_id, amt)))
            else:
                opts.append((f"start {COMPOUNDS[c]}" if obs.lap == 0 else f"pit {COMPOUNDS[c]}", Action(True, s.set_id)))
        return opts

    def decide(self, car: CarState, obs: Observation) -> Decision:
        opts = self.options(car, obs)
        if len(opts) == 1:
            return Decision(opts[0][1])
        all_times = simulate(self.P, car, obs, [a for _, a in opts], self.futures(obs), BASES)  # (K, H, n)
        h_best = all_times.mean(2).argmin(1)              # best base policy for each option
        times = all_times[np.arange(len(opts)), h_best]   # (K, n)
        means = times.mean(1)
        best = int(np.argmin(means))
        options = {lab: float(v) for (lab, _), v in zip(opts, means)}
        if obs.lap == 0:
            return Decision(opts[best][1], f"Start on {opts[best][0].split()[1]} (best of {len(opts)} options)", options)
        stay = 0  # index of "stay out"
        gain = means[stay] - means[best]
        if best == stay or gain < self.hysteresis:
            return Decision(STAY, "", options)
        diff = times[stay] - times[best]
        se = diff.std(ddof=1) / np.sqrt(len(diff)) if len(diff) > 1 else 0.0
        why = f"{STATUS_NAMES[obs.status]} now, " if obs.status != GREEN else ""
        if obs.wetness > 0.2:
            why += f"track wetness {obs.wetness:.2f}, "
        return Decision(opts[best][1], f"Lap {obs.lap}: {why}{opts[best][0]} saves {gain:.1f} s ± {se:.1f} vs staying out", options)


class Oracle(RolloutStrategy):
    """Knows the real future (cheats on purpose): an upper reference for how good a decision could be."""
    name = "oracle"

    def __init__(self, scn: Scenario):
        super().__init__(n=1, seed=0, hysteresis=0.0)
        self.scn = scn

    def futures(self, obs: Observation) -> dict[str, np.ndarray]:
        s = self.scn
        return {"status": s.status[None, obs.lap:], "wetness": s.wetness[None, obs.lap:], "noise": s.noise[None, obs.lap:]}

