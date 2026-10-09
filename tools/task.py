"""PitWall task helper: the ONLY git commands a teammate needs.

    python tools/task.py role SIM          # once: who am I (BR | SIM | DAT | UI)
    python tools/task.py start rain-model  # before a task: fresh main -> new branch sim/rain-model
    python tools/task.py ship "better rain model"     # after the AI is done: test, commit, (push, PR, merge)
    python tools/task.py check             # at checkpoints: update main, run all tests + demo race
    python tools/task.py status            # what changed, and is it all mine?

Works on Linux, macOS and Windows. Needs git and the GitHub CLI (gh) logged in.
Ships with a merge commit (never squash), so every real commit stays in the history (Rulebook section 5).
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLE_FILE = ROOT / ".pitwall_role"
ROLES = ("BR", "SIM", "DAT", "UI")
TEST_CMD = [sys.executable, "-m", "pytest", "-q", "-m", "not network and not slow"]

# Who may edit what (MODULES.md). BR may edit anything, but gets a warning outside its own files.
OWNERS: dict[str, list[str]] = {
    "BR": ["pitwall/strategy/*", "pitwall/eval/*", "pitwall/core.py", "pitwall/__init__.py",
           "tests/test_strategy.py", "tests/test_eval.py", "tests/conftest.py",
           "results/eval_*", "results/mismatch_*", "results/rain_sweep_*", "results/summary.json",
           "tools/*", "AGENTS.md", "MODULES.md", "requirements.txt", ".gitignore", "pytest.ini"],
    "SIM": ["pitwall/engine/*", "tests/test_engine.py", "results/replay_*"],
    "DAT": ["pitwall/data/*", "data/*", "tests/test_data.py"],
    "UI": ["frontend/*", "pitwall/server.py", "pitch/*", "README.md", "tests/test_api.py"],
}
NOT_DAT: list[str] = []


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print("  $", " ".join(cmd))
    res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=capture)
    if check and res.returncode != 0:
        if capture:
            print(res.stdout, res.stderr)
        die(f"command failed: {' '.join(cmd)}")
    return res


def out(cmd: list[str]) -> str:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True).stdout.strip()


def die(msg: str) -> None:
    print(f"\nSTOP: {msg}\nIf you are unsure what to do, post this message in the team chat.")
    sys.exit(1)


def role() -> str:
    if not ROLE_FILE.exists():
        die("role not set. Run: python tools/task.py role <BR|SIM|DAT|UI>")
    return ROLE_FILE.read_text().strip()


def has_origin() -> bool:
    return "origin" in out(["git", "remote"]).split()


def branch() -> str:
    return out(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def owned(path: str, r: str) -> bool:
    if r == "DAT" and path in NOT_DAT:
        return False
    return any(fnmatch.fnmatch(path, pat) for pat in OWNERS[r])


def changed_files() -> list[str]:
    files = set(out(["git", "diff", "--name-only", "HEAD"]).splitlines())
    files |= set(out(["git", "ls-files", "--others", "--exclude-standard"]).splitlines())
    if has_origin():
        files |= set(out(["git", "diff", "--name-only", "origin/main...HEAD"]).splitlines())
    return sorted(f for f in files if f)


def ownership_problems(r: str) -> list[str]:
    return [f for f in changed_files() if not owned(f, r)]


def cmd_role(args: list[str]) -> None:
    if not args or args[0].upper() not in ROLES:
        die("usage: python tools/task.py role <BR|SIM|DAT|UI>")
    ROLE_FILE.write_text(args[0].upper())
    print(f"Role saved: {args[0].upper()}")


def cmd_start(args: list[str]) -> None:
    r = role()
    if not args:
        die("usage: python tools/task.py start <short-name>, e.g. start rain-model")
    task = args[0].lower().replace(" ", "-")
    if out(["git", "status", "--porcelain"]):
        die("you have unsaved changes. Finish them with 'ship' first, or ask the team.")
    run(["git", "switch", "main"])
    if has_origin():
        run(["git", "pull", "--ff-only"])
    name = f"{r.lower()}/{task}"
    exists = run(["git", "rev-parse", "--verify", name], check=False, capture=True).returncode == 0
    run(["git", "switch", name] if exists else ["git", "switch", "-c", name])
    print(f"\nReady. Now tell your AI:\n  Read AGENTS.md and MODULES.md (section {r}), then: <what you want improved>")
    print(f"When it is done and its tests pass, run:\n  python tools/task.py ship \"<what you did>\"")


def cmd_ship(args: list[str]) -> None:
    r = role()
    b = branch()
    if b == "main":
        die("you are on main. Start first: python tools/task.py start <short-name>")
    task = b.split("/")[-1]
    print("\n1/5 Running tests")
    if subprocess.run(TEST_CMD, cwd=ROOT).returncode != 0:
        die("tests fail. Ask your AI to fix them, then ship again.")
    problems = ownership_problems(r)  # checked after tests, so files the tests create are covered too
    if problems and r != "BR":
        die("these files are not yours (MODULES.md). Undo them or ask the owner:\n  " + "\n  ".join(problems))
    if problems:
        print("WARNING (lead): touching files owned by others:\n  " + "\n  ".join(problems))
    print("\n2/5 Committing")
    if out(["git", "status", "--porcelain"]):
        msg = " ".join(args) or input("One line: what did you do? ").strip() or "work in progress"
        run(["git", "add", "-A"])
        run(["git", "commit", "-m", f"feat({r.lower()}): {msg} ({task})"])
    if not has_origin():
        print("No GitHub remote yet: committed locally only.")
        return
    print("\n3/5 Bringing in teammates' latest work")
    run(["git", "fetch", "origin"])
    if run(["git", "merge", "--no-edit", "origin/main"], check=False).returncode != 0:
        run(["git", "merge", "--abort"], check=False)
        die("your work conflicts with main. Do not force anything; ask Smaran.")
    if subprocess.run(TEST_CMD, cwd=ROOT).returncode != 0:
        die("tests fail after merging main. Ask your AI to fix them, then ship again.")
    print("\n4/5 Pushing and opening the pull request")
    run(["git", "push", "-u", "origin", b])
    if run(["gh", "pr", "view", b], check=False, capture=True).returncode != 0:
        run(["gh", "pr", "create", "--base", "main", "--head", b, "--fill"])
    print("\n5/5 Waiting for GitHub's tests, then merging (merge commit)")
    for _ in range(8):  # checks can take a minute to appear
        time.sleep(15)
        if run(["gh", "pr", "checks", b, "--watch"], check=False).returncode == 0:
            break
    else:
        die("GitHub's tests failed or never started. Open the PR page, read the error, fix, ship again.")
    run(["gh", "pr", "merge", b, "--merge"])
    run(["git", "switch", "main"])
    run(["git", "pull", "--ff-only"])
    print(f"\nShipped {task}. Next: python tools/task.py start <next-thing>")


def cmd_check(_: list[str]) -> None:
    if out(["git", "status", "--porcelain"]):
        die("unsaved changes. Ship them first.")
    run(["git", "switch", "main"])
    if has_origin():
        run(["git", "pull", "--ff-only"])
    ok = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT).returncode == 0
    ok &= subprocess.run([sys.executable, "-m", "pitwall.engine.race"], cwd=ROOT).returncode == 0
    print("\nCHECKPOINT OK" if ok else "\nCHECKPOINT FAILED: post the error in the team chat")


def cmd_status(_: list[str]) -> None:
    r = role()
    print(f"Role: {r}   Branch: {branch()}")
    files = changed_files()
    print("Changed files:", *(f"  {'ok ' if owned(f, r) else 'NOT YOURS '}{f}" for f in files), sep="\n")


COMMANDS = {"role": cmd_role, "start": cmd_start, "ship": cmd_ship, "check": cmd_check, "status": cmd_status}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
