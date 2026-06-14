"""Orchestrator agent (ADR-0002, ADR-0006).

Two deterministic responsibilities, no LLM:

1. **Planning entry node.** Runs first in the graph (``START -> orchestrator -> …``). It
   validates the run's inputs and records a typed :class:`~vault_agent.state.ExecutionPlan`
   on the state, so the trace shows the planned stages, declared inputs, and whether
   source-schema grounding is active.

2. **Human-in-the-loop checkpoint.** :func:`assemble_review_queue` derives a categorized
   :class:`HumanReviewQueue` from a finished run — the validation issues, contracts still
   awaiting an owner, and the agents' review flags. Per ADR-0006 this deterministic queue is
   surfaced to the human (CLI / file) and, when it blocks sign-off, the
   :class:`HumanCheckpointAgent` pauses the graph on a live LangGraph ``interrupt()`` until a
   human resumes with their decision. Keeping the queue a pure, separately-tested function
   means the interrupt node just assembles it and delivers an already-defined payload.

Being deterministic, the whole agent is unit-tested without an API key.
"""
from typing import Any, Literal

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from vault_agent.agents.base import BaseAgent
from vault_agent.models.contract import ContractOwner
from vault_agent.state import ExecutionPlan, VaultAgentState

# Review flags whose owner concern is already represented structurally as a
# ``contract_owner`` item — filtered out of the advisory flags to avoid double-listing.
_OWNER_FLAG_MARKER = "placeholder owner"

ReviewKind = Literal[
    "contract_owner", "validation_error", "validation_warning", "review_flag"
]


class ReviewItem(BaseModel):
    """One thing a human must look at before the model/contracts are considered agreed."""

    kind: ReviewKind
    summary: str
    detail: str = ""
    source: str = ""  # the agent / construct the item originates from


class HumanReviewQueue(BaseModel):
    """The categorized checkpoint payload derived from a finished run."""

    items: list[ReviewItem] = Field(default_factory=list)

    @property
    def requires_signoff(self) -> bool:
        """True when something blocks agreement: a hard validation error or an unassigned
        contract owner. Warnings and advisory flags inform review but do not block."""
        return any(
            item.kind in ("validation_error", "contract_owner") for item in self.items
        )

    def by_kind(self) -> dict[str, list[ReviewItem]]:
        grouped: dict[str, list[ReviewItem]] = {}
        for item in self.items:
            grouped.setdefault(item.kind, []).append(item)
        return grouped


def assemble_review_queue(state: VaultAgentState) -> HumanReviewQueue:
    """Build the human-review checkpoint from a finished run's state (deterministic)."""
    items: list[ReviewItem] = []

    # Validation issues — severity maps to a blocking error vs an advisory warning.
    for issue in state.validation_report.issues:
        severity = str(issue.get("severity", ""))
        kind: ReviewKind = (
            "validation_error" if severity == "error" else "validation_warning"
        )
        code = str(issue.get("code", "")) or "issue"
        construct = str(issue.get("construct", "")) or "model"
        items.append(
            ReviewItem(
                kind=kind,
                summary=f"{code} on {construct}",
                detail=str(issue.get("message", "")),
                source="validator",
            )
        )

    # Contracts still carrying the placeholder owner — a required human assignment.
    for contract in state.artifacts.contracts:
        owner = contract.get("owner") or {}
        if owner.get("name") == ContractOwner.PLACEHOLDER_NAME:
            name = str(contract.get("name", "<unnamed>"))
            items.append(
                ReviewItem(
                    kind="contract_owner",
                    summary=f"Assign an owner for contract {name!r}",
                    detail="The agent never invents an owner; assign one before agreeing "
                    "the contract.",
                    source="data_contract",
                )
            )

    # Remaining advisory flags. The owner concern is already a structured contract_owner
    # item above, so drop those flag lines to avoid listing the same thing twice.
    for err in state.errors:
        if _OWNER_FLAG_MARKER in err:
            continue
        items.append(ReviewItem(kind="review_flag", summary=err, source="pipeline"))

    return HumanReviewQueue(items=items)


_KIND_HEADINGS: dict[str, str] = {
    "validation_error": "Validation errors (block agreement)",
    "contract_owner": "Contract owners to assign (block agreement)",
    "validation_warning": "Validation warnings (advisory)",
    "review_flag": "Review flags (advisory)",
}
# Stable presentation order: blocking concerns first, advisory last.
_KIND_ORDER = (
    "validation_error",
    "contract_owner",
    "validation_warning",
    "review_flag",
)


def render_review_queue_md(queue: HumanReviewQueue) -> str:
    """Render the queue as a Markdown checkpoint document (one artifact per run)."""
    lines = ["# Human-in-the-loop checkpoint", ""]
    if not queue.items:
        lines.append("No items require human review. ✅")
        return "\n".join(lines) + "\n"

    verdict = "requires sign-off" if queue.requires_signoff else "advisory only"
    lines.append(f"**Status:** {verdict} — {len(queue.items)} item(s).")
    lines.append("")
    grouped = queue.by_kind()
    for kind in _KIND_ORDER:
        group = grouped.get(kind)
        if not group:
            continue
        lines.append(f"## {_KIND_HEADINGS[kind]}")
        lines.append("")
        for item in group:
            line = f"- **{item.summary}**"
            if item.detail:
                line += f" — {item.detail}"
            if item.source:
                line += f" _({item.source})_"
            lines.append(line)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


class OrchestratorAgent(BaseAgent):
    """Deterministic planning entry node; also owns the review-queue helpers above."""

    prompt_path = "orchestrator.md"  # type: ignore[assignment]

    def __init__(self, planned_stages: list[str] | None = None) -> None:
        # The downstream stages this run will execute, injected by the graph so the plan
        # tracks the real pipeline without this module importing graph (no import cycle).
        self._planned_stages = planned_stages or []

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        notes: list[str] = []
        if not state.input_documents:
            notes.append(
                "no input documents declared; downstream parsing will produce nothing"
            )
            state.errors.append("orchestrator: no input documents declared")

        plan = ExecutionPlan(
            stages=list(self._planned_stages),
            input_documents=len(state.input_documents),
            grounded=bool(state.source_schemas),
            notes=notes,
        )
        state.plan = plan
        state.decisions.append(
            {
                "agent": "orchestrator",
                "stages": len(plan.stages),
                "inputs": plan.input_documents,
                "grounded": plan.grounded,
            }
        )
        return state


def apply_human_decision(state: VaultAgentState, decision: Any) -> list[str]:
    """Apply a human's sign-off decision to the state, returning the assets re-owned.

    ``decision`` is whatever the resume supplied, expected as
    ``{"owners": {asset: {"name": ..., "email": ...}}, "accept": bool}``. Owners are written
    onto the matching contracts, and the now-resolved placeholder-owner review flags are
    pruned so a regenerated review queue no longer lists them. Deterministic and pure (no
    interrupt), so it is unit-tested directly."""
    owners = decision.get("owners", {}) if isinstance(decision, dict) else {}
    assigned: list[str] = []
    for contract in state.artifacts.contracts:
        name = contract.get("name")
        proposed = owners.get(name) if isinstance(owners, dict) else None
        if name and isinstance(proposed, dict) and proposed.get("name"):
            contract["owner"] = {
                "name": proposed["name"],
                "email": proposed.get("email"),
            }
            assigned.append(str(name))

    if assigned:
        state.errors = [
            err
            for err in state.errors
            if not (_OWNER_FLAG_MARKER in err and any(a in err for a in assigned))
        ]
    return assigned


class HumanCheckpointAgent(BaseAgent):
    """Human-in-the-loop gate (ADR-0006). On the validated path it assembles the review
    queue and, when something blocks agreement, pauses the graph with LangGraph's
    ``interrupt()`` until a human resumes with their decision. When nothing blocks it passes
    straight through. Requires the graph to be compiled with a checkpointer."""

    prompt_path = "orchestrator.md"  # type: ignore[assignment]

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        queue = assemble_review_queue(state)
        if not queue.requires_signoff:
            state.decisions.append(
                {"agent": "human_checkpoint", "interrupted": False, "assigned": []}
            )
            return state

        # interrupt() must come before any state mutation: on resume the node re-executes
        # from the top, so anything above this line would run twice.
        decision = interrupt(
            {
                "review_queue": queue.model_dump(),
                "instructions": (
                    "Assign owners for the listed contracts and/or accept to proceed; "
                    "resume with vault-agent resume."
                ),
            }
        )
        assigned = apply_human_decision(state, decision)
        state.decisions.append(
            {
                "agent": "human_checkpoint",
                "interrupted": True,
                "assigned": assigned,
                "accepted": bool(decision.get("accept"))
                if isinstance(decision, dict)
                else False,
            }
        )
        return state
