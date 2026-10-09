# AGENTS.md — rules for every AI working on PitWall

## Before you write any code
1. Read, in order: AGENTS.md, docs/PLAN.md sections 1-4, docs/roles/<ROLE>.md, pitwall/types.py.
2. Work on ONE task ID (e.g. SIM2) per conversation. Do not start the next task unasked.
3. Any task estimated over 1 hour: reply with a plan first (files, functions, tests). Wait for approval.

## Boundaries
- Edit ONLY the files your role owns (docs/PLAN.md section 4). Read anything.
- NEVER edit pitwall/types.py. If the contract blocks you, stop and propose the exact change in words.
- Need something another role hasn't delivered? Use its stand-in (docs/PLAN.md section 3). Never build their part.
- No new dependencies. If you need one, say so; BR adds it to requirements.txt.
- Do not run git commit, git push or merge. The human commits after reading your diff.

## Code rules
- Python 3.12, type hints everywhere, the dataclasses from pitwall/types.py.
- Units: seconds, laps, kg; wetness 0..1; track names lowercase; mode is 'f1' or 'endurance'.
- Randomness ONLY via np.random.default_rng(seed) passed in. Never `random` or global np.random.
- Anything called inside rollouts must be vectorised numpy over arrays: no Python loop over futures, np.where instead of if on arrays.
- Strategies see ONLY the Observation and the belief params given to reset(). Only Oracle receives the Scenario.
- Lap times are computed with the TRUE params (P_true); strategies plan with their BELIEF params. Never mix them.
- The team runs Linux, macOS and Windows: use pathlib for every path, and guard multiprocessing entry points with if __name__ == "__main__".
- Files under 300 lines. Docstrings state units. No dead code or debug prints left behind.
- Network (FastF1) only inside pitwall/data. Network tests: @pytest.mark.network. Tests over 10 s: @pytest.mark.slow.
- Never invent data. A value not fitted from data gets "source": "assumed" beside it in the JSON.

## Tests
- Every public function gets at least one test in your role's test files.
- Run `pytest -q` yourself and show the output. Never finish with failing tests.

## When you finish
Reply with: (1) what changed, file by file; (2) how you tested it; (3) anything stubbed or TODO;
(4) a commit message `type(area): what (TaskID)`.
