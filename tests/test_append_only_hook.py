"""The append-only rule is the one convention that can be enforced rather than asked for.

`.claude/hooks/append_only_records.py` runs as a `PreToolUse` hook and denies `Edit`/`Write` on
an existing file under `docs/architecture/`. These tests pin the four decisions that matter and,
just as importantly, that it **fails open**: a guard that blocks work when it breaks is worse
than no guard.

The hook is invoked as a subprocess with the real stdin contract, not imported — what CI must
protect is the behaviour Claude Code actually gets.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".claude" / "hooks" / "append_only_records.py"


def _run(payload: object, env_extra: dict[str, str] | None = None) -> dict:
    """Run the hook; return its parsed decision, or {} when it stays silent (= allow)."""
    import os

    env = {k: v for k, v in os.environ.items() if k != "VAULT_AGENT_ALLOW_RECORD_EDIT"}
    env.update(env_extra or {})
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"the hook must always exit 0: {result.stderr}"
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _payload(tool: str, path: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": path},
        "cwd": str(REPO_ROOT),
    }


def _denied(decision: dict) -> bool:
    return decision.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def test_editing_an_existing_adr_is_denied() -> None:
    adr = REPO_ROOT / "docs/architecture/adrs/ADR-0001-llm-choice.md"
    assert adr.is_file(), "fixture assumption: this ADR exists"

    decision = _run(_payload("Edit", str(adr)))

    assert _denied(decision)
    reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
    assert "append-only" in reason
    assert "docs/log.md" in reason, "the denial must name the alternative, not just refuse"
    assert "VAULT_AGENT_ALLOW_RECORD_EDIT" in reason, "and the deliberate way through"


def test_creating_a_new_record_is_allowed() -> None:
    """Writing a NEW ADR is how a decision gets recorded — never blocked."""
    target = REPO_ROOT / "docs/architecture/adrs/ADR-9999-does-not-exist-yet.md"
    assert not target.exists()

    assert _run(_payload("Write", str(target))) == {}


def test_the_log_stays_appendable() -> None:
    """docs/log.md is append-only, and appending goes through Edit. Its guard is a test."""
    assert _run(_payload("Edit", str(REPO_ROOT / "docs/log.md"))) == {}


def test_ordinary_code_is_untouched() -> None:
    assert _run(_payload("Edit", str(REPO_ROOT / "src/vault_agent/graph.py"))) == {}
    assert _run(_payload("Edit", "docs/index.md")) == {}, "relative paths resolve against cwd"


def test_the_escape_hatch_opens() -> None:
    adr = REPO_ROOT / "docs/architecture/adrs/ADR-0001-llm-choice.md"

    decision = _run(_payload("Edit", str(adr)), {"VAULT_AGENT_ALLOW_RECORD_EDIT": "1"})

    assert decision == {}, "a deliberate, human-set override must get through"


def test_a_read_is_never_blocked() -> None:
    payload = {"tool_name": "Read", "tool_input": {"file_path": "docs/architecture/0-vision.md"}}
    assert _run({**payload, "cwd": str(REPO_ROOT)}) == {}


def test_it_fails_open_on_garbage() -> None:
    """A broken guard must not be the reason work cannot proceed."""
    assert _run("not json at all") == {}
    assert _run({"tool_name": "Edit"}) == {}  # no tool_input
    assert _run({"tool_input": {"file_path": "x"}}) == {}  # no tool_name
    assert _run({}) == {}
