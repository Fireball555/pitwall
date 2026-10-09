"""BR0: one GitHub issue per task ID in docs/roles/*.md, via `gh issue create`.

Parses lines starting with a task ID (e.g. "1. **BR1 Rollout core** (4 h)." or "2. **SIM1 Lap time** (1.5 h).")
in each docs/roles/<ROLE>.md file. Title = "<ID> <short name>"; body = that task's bullet text
from PLAN.md; label = role (lowercase). Assignees: BR -> Fireball555, SIM -> Iamashwink,
DAT -> DharshiniShanmugam16, UI -> tonorz. An assignee only works once that person has accepted
the repo invite; on failure the issue is still created (unassigned) and the failure is reported.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLES_DIR = ROOT / "docs" / "roles"

ASSIGNEES = {
    "BR": "Fireball555",
    "SIM": "Iamashwink",
    "DAT": "DharshiniShanmugam16",
    "UI": "tonorz",
}

TASK_RE = re.compile(r"^\d+\.\s+\*\*([A-Z]{2,4}\d+)\s+([^*]+?)\*\*\s*(\([^)]*\))?\.")


def parse_tasks(role: str) -> list[tuple[str, str, str]]:
    path = ROLES_DIR / f"{role}.md"
    text = path.read_text()
    lines = text.splitlines()

    tasks: list[tuple[str, str, str]] = []
    current: tuple[str, str, list[str]] | None = None

    for line in lines:
        m = TASK_RE.match(line.strip())
        if m:
            if current:
                task_id, name, body_lines = current
                tasks.append((task_id, name.strip(), "\n".join(body_lines).strip()))
            task_id, name = m.group(1), m.group(2)
            current = (task_id, name, [line])
        elif current and (line.startswith("   ") or line.strip() == "" or line.startswith("|")):
            current[2].append(line)
        elif current and re.match(r"^\d+\.\s+\*\*", line.strip()):
            pass  # handled above
        elif current and line.strip().startswith("**"):
            # a new section (e.g. "**Lead duties") ends the task list
            task_id, name, body_lines = current
            tasks.append((task_id, name.strip(), "\n".join(body_lines).strip()))
            current = None

    if current:
        task_id, name, body_lines = current
        tasks.append((task_id, name.strip(), "\n".join(body_lines).strip()))

    return tasks


def ensure_label(label: str) -> None:
    subprocess.run(["gh", "label", "create", label, "--force"], capture_output=True, text=True)


def create_issue(task_id: str, name: str, body: str, role: str) -> tuple[bool, str]:
    label = role.lower()
    title = f"{task_id} {name}"
    assignee = ASSIGNEES[role]

    cmd = ["gh", "issue", "create", "--title", title, "--body", body, "--label", label, "--assignee", assignee]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, result.stdout.strip()

    # Retry unassigned: the assignee may not have accepted the repo invite yet.
    cmd_unassigned = ["gh", "issue", "create", "--title", title, "--body", body, "--label", label]
    result2 = subprocess.run(cmd_unassigned, capture_output=True, text=True)
    if result2.returncode == 0:
        return False, f"{result2.stdout.strip()} (created unassigned: {result.stderr.strip()})"
    return False, f"FAILED: {result2.stderr.strip()}"


def main() -> None:
    ensure_label("contract")
    for label in ("br", "sim", "dat", "ui"):
        ensure_label(label)

    created, assigned_ok, failures = 0, 0, []
    for role in ("BR", "SIM", "DAT", "UI"):
        for task_id, name, body in parse_tasks(role):
            ok, info = create_issue(task_id, name, body, role)
            created += 1
            if ok:
                assigned_ok += 1
                print(f"ok   {task_id} {name} -> {info}")
            else:
                failures.append((task_id, name, info))
                print(f"WARN {task_id} {name}: {info}")

    print(f"\n{created} issues created, {assigned_ok} assigned successfully, {len(failures)} assignment failures.")
    if failures:
        print("Assignment failures:")
        for task_id, name, info in failures:
            print(f"  {task_id} {name}: {info}")


if __name__ == "__main__":
    main()
