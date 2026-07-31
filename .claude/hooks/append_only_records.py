#!/usr/bin/env python3
"""PreToolUse hook: refuse to edit a dated record.

`docs/architecture/` holds ADRs, work-package specs, kick-offs, reviews and spike memos.
Their value depends on showing what was believed when, which is what makes a later correction
legible instead of invisible. `CLAUDE.md` and `.claude/rules/records.md` say so — but
instructions are context, not enforcement, and this is the one convention that can be enforced
mechanically. So it is.

What this blocks: `Edit`, `Write` and `NotebookEdit` on a file that already exists under
`docs/architecture/`. What it deliberately does not block:

* **Creating** a file there — a new ADR or spec is exactly how a decision gets recorded.
* `docs/log.md` — the log is append-only, and appending happens through `Edit`. Its guard is
  `tests/test_log_completeness.py`, which fails if an entry is lost.
* A human with an editor. This constrains agents, not people.
* `Bash` — a determined `sed -i` still gets through. Closing that would mean parsing shell,
  which trades a real cost for a marginal gain against an actor who is not trying to cheat.

Escape hatch, because some edits are legitimate: an ADR moving Proposed → Accepted is a status
change along its intended path. Set `VAULT_AGENT_ALLOW_RECORD_EDIT=1` for that session. It is
deliberately awkward — a deliberate act should feel deliberate.

**Fails open.** Any unexpected input, missing field or internal error exits 0 and lets the
normal permission flow decide. A broken guard must never be the reason work cannot proceed —
the same rule the trace and usage recorders follow in `src/vault_agent/llm.py`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROTECTED_DIR = Path("docs") / "architecture"
OVERRIDE_ENV = "VAULT_AGENT_ALLOW_RECORD_EDIT"
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}

REASON = """\
{path} is a dated record — append-only.

ADRs, specs, kick-offs, reviews and spike memos are not maintained pages: their value is that \
they show what was believed when. Editing one erases the very thing that makes a later \
correction legible.

Instead: append a dated entry to docs/log.md saying what changed and why the earlier text is \
now wrong, or write a new document that states what it supersedes. Adding a NEW file under \
docs/architecture/ is not blocked.

If this genuinely is a status move along an ADR's intended path (Proposed -> Accepted), it \
needs the human's word: re-run with {env}=1 set.

The convention: .claude/rules/records.md · the procedure: .claude/skills/project-docs/SKILL.md\
"""


def _target(tool_name: str, tool_input: dict) -> str | None:
    if tool_name not in EDIT_TOOLS:
        return None
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _is_protected(target: str, cwd: str) -> bool:
    """True when the target is an EXISTING file under docs/architecture/ of this project."""
    path = Path(target)
    if not path.is_absolute():
        path = Path(cwd) / path
    try:
        path = path.resolve()
    except OSError:
        return False
    if not path.is_file():
        return False  # creating a new record is how decisions get written down
    try:
        relative = path.relative_to(Path(cwd).resolve())
    except ValueError:
        return False  # outside the project; not ours to police
    return PROTECTED_DIR in (relative.parent, *relative.parents)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if os.environ.get(OVERRIDE_ENV):
            return 0
        target = _target(payload.get("tool_name", ""), payload.get("tool_input") or {})
        if target is None:
            return 0
        if not _is_protected(target, payload.get("cwd") or os.getcwd()):
            return 0
    except Exception:  # noqa: BLE001 - a broken guard must not block work
        return 0

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON.format(path=target, env=OVERRIDE_ENV),
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
