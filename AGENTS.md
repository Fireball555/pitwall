# Rules for every AI working on PitWall

1. Read `MODULES.md` first to find which files do what.
2. Change only the files the task needs. Never rename a function or argument listed under "Don't break" in `MODULES.md`; other modules call them.
3. `pitwall/core.py` holds the shared types. Change it only if the task truly needs it, and say why.
4. Keep everything working: run `pytest` before you finish, show the output, and fix failures.
5. Anything the strategist calls inside its imagined futures must stay vectorised numpy (no Python loops over futures).
6. Randomness only through `np.random.default_rng(seed)`. Same seed, same result.
7. Strategies may only see the `Observation` and their belief params. Only the Oracle sees the real future.
8. Never invent data. A number that isn't fitted from real data is marked `"source": "assumed"` or "placeholder".
9. Python 3.12. Use `pathlib` for paths, and guard multiprocessing with `if __name__ == "__main__":`.
10. Frontend: after changing `frontend/src`, run `npm run build` in `frontend/` so `frontend/dist` (which the server serves) stays current. The server must never run heavy computation on page load. Car colours must never use tyre colours.
11. Don't run `git commit`, `push` or `merge`. The human ships.
12. When you finish, list what changed (file by file), how you tested it, and anything left undone.
