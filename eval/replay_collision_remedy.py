"""Replay the recorded first modelling attempts of a chain through today's validator and print
the remedy each `E_HUB_HK_COLLISION` would now carry (2026-09-13). Keyless and pure.

The trace holds the modeler's raw output per call (``payload``) and its input
(``user_content``: requirements and business-key candidates); a step's existing vault is the
previous step's persisted model when the run wrote one (``--resume-chain`` era) and absent
otherwise, in which case inherited pairs cannot be told from new ones and the replay says so.

Usage::

    uv run python -m eval.replay_collision_remedy \\
        eval/results/adventureworks_incremental/<stamp>-run1.trace.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.model_merger import merge_models
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.existing_model import load_existing_model
from vault_agent.state import BusinessKeyCandidate, VaultAgentState


def _first_attempts(trace: Path) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """(timestamp, input payload, output payload) of every attempt-1 modeler call."""
    out = []
    for line in trace.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("tool_name") != "emit_dv_model" or record.get("kind") != "llm_call":
            continue
        try:
            sent = json.loads(record["user_content"])
        except (TypeError, ValueError):
            continue
        if "previous_validation_issues" in sent or not isinstance(record.get("payload"), dict):
            continue
        out.append((record["ts"], sent, record["payload"]))
    return out


async def replay(trace: Path) -> int:
    stamp = trace.name.split("-run1")[0]
    attempts = _first_attempts(trace)
    previous_models = sorted(trace.parent.glob(f"{stamp}-step*-run1.dv_model.yml"))
    by_step = {int(p.name.split("-step")[1].split("-")[0]): p for p in previous_models}
    collisions = 0
    for index, (ts, sent, raw) in enumerate(attempts, start=1):
        state = VaultAgentState(business_keys=[
            BusinessKeyCandidate.model_validate(b) for b in sent.get("business_keys", [])
        ])
        delta = Dv2ModelerAgent()._validate_model(raw, state)
        existing = load_existing_model(by_step[index - 1]) if index - 1 in by_step else None
        state.existing_model = existing
        state.dv_model = merge_models(existing, delta, state) if existing else delta
        report = (await ValidatorAgent().run(state)).validation_report
        issues = [i for i in report.issues if i.code == "E_HUB_HK_COLLISION"]
        vault = "existing vault from persisted step model" if existing else "no persisted vault"
        print(f"step {index} ({ts[11:19]}, {vault}): {len(issues)} collision(s)")
        for issue in issues:
            collisions += 1
            print(f"  {issue.construct}\n    remedy: {issue.remedy}")
    return collisions


def main(argv: list[str] | None = None) -> int:
    import asyncio

    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    n = asyncio.run(replay(Path(args[0])))
    print(f"{n} collision(s) replayed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
