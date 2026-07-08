"""ADR Author agent.

Writes the single publication-ready ADR that documents the chosen Data Vault model and
traces every construct back to the requirements that justify it. It is the sole writer of
``VaultAgentState.adrs`` — upstream agents no longer leave draft fragments (L-4).

It is deterministic — it renders ``state.dv_model`` (the source of truth, which already
carries each construct's description and ``requirement_ids``) into the project's ADR
template. No LLM is involved, so the architecture record is reproducible and never subject
to hallucination, matching how DV2.0 rules are kept in pure Python. The finalized ADR has
status ``Proposed``: a human must review and accept it.

Numbering: the generated ADR is a per-run output artifact documenting *one* pipeline run
inside *one* output project, so it is numbered ADR-0001 within that output —
deterministically, never derived from any repository directory. Same state in,
byte-identical ADR out. Repo-level ADR numbering happens only when a human *accepts* the
proposal and moves it into ``docs/architecture/adrs/``; the pipeline never numbers into
the repo sequence.
"""
from datetime import date

from vault_agent.agents.base import BaseAgent
from vault_agent.state import DVModel, FlagKind, VaultAgentState

# The generated ADR is always the first (and only) ADR of its output project.
_OUTPUT_ADR_NUMBER = 1


def _ids(requirement_ids: list[str]) -> str:
    return ", ".join(requirement_ids) if requirement_ids else "—"


class AdrAuthorAgent(BaseAgent):
    """Renders the finalized Data Vault model ADR from state.dv_model."""

    def __init__(self, today: str | None = None, start_number: int | None = None) -> None:
        self._today = today
        # Explicit start_number wins (tests/overrides); the default is the per-output
        # constant 1 — see the module docstring for why the repo's ADR sequence is never
        # consulted.
        self._start_number = start_number

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        if not state.dv_model.hubs:
            state.flag(
                "adr_author",
                "no model to document; run the DV2.0 modeler first",
                severity="error",
                kind=FlagKind.MISSING_INPUT,
            )
            return state

        number = self._start_number if self._start_number is not None else _OUTPUT_ADR_NUMBER
        today = self._today or date.today().isoformat()
        # The adr_author runs after the code generator on the validated path (graph:
        # code_generator → validator → human_checkpoint → adr_author), so every construct
        # the generator had to skip has already raised a GENERATION_GAP flag carrying the
        # construct name as its asset. Matching is on kind/asset only — never message text.
        generation_gaps = sorted(
            {f.asset for f in state.flags if f.kind == FlagKind.GENERATION_GAP and f.asset}
        )
        adr = self._render(
            state.dv_model, state, number=number, today=today, generation_gaps=generation_gaps
        )
        state.adrs = [adr]  # sole writer; overwrites defensively even if anything pre-set it
        state.decisions.append(
            {
                "agent": "adr_author",
                "adr_number": number,
                "adrs_written": 1,
            }
        )
        return state

    @staticmethod
    def _render(
        model: DVModel,
        state: VaultAgentState,
        number: int,
        today: str,
        generation_gaps: list[str],
    ) -> str:
        lines: list[str] = [
            f"# ADR-{number:04d}: Data Vault model derived from requirements",
            "",
            "**Status:** Proposed",
            f"**Date:** {today}",
            "**Decision makers:** Vault-Agent (generated) — pending human review",
            "",
            "## Context",
            "",
            f"This model was derived automatically by the Vault-Agent pipeline from "
            f"{len(state.requirements)} requirement(s) and {len(state.business_keys)} "
            f"business key candidate(s). It records the Data Vault 2.0 structures the "
            f"modeler chose and traces each back to the requirements that justify it.",
            "",
            "## Decision",
            "",
            "Model the following Data Vault 2.0 structures.",
            "",
            f"### Hubs ({len(model.hubs)})",
            "",
        ]
        for hub in model.hubs:
            lines.append(
                f"- **{hub.name}** — business key `{hub.business_key}`. {hub.description} "
                f"_(requirements: {_ids(hub.requirement_ids)})_"
            )

        lines += ["", f"### Links ({len(model.links)})", ""]
        for link in model.links:
            uow = f" Unit of work: {link.unit_of_work}." if link.unit_of_work else ""
            lines.append(
                f"- **{link.name}** — connects {', '.join(link.connected_hubs)}. "
                f"{link.description}{uow} _(requirements: {_ids(link.requirement_ids)})_"
            )

        lines += ["", f"### Satellites ({len(model.satellites)})", ""]
        for sat in model.satellites:
            payload = ", ".join(sat.attributes) if sat.attributes else "—"
            split = f" Split rationale: {sat.split_rationale}." if sat.split_rationale else ""
            lines.append(
                f"- **{sat.name}** — on {sat.parent}; payload: {payload}. "
                f"{sat.description}{split} _(requirements: {_ids(sat.requirement_ids)})_"
            )

        lines += [
            "",
            "## Alternatives considered",
            "",
            "The automated modeler did not record alternative designs. Reviewers should "
            "consider whether any object modelled as a hub is better expressed as a link "
            "(or vice versa), and whether the satellite splits match the true rate of "
            "change of the attributes.",
            "",
            "## Consequences",
            "",
            "- Positive: every construct is traceable to the specific requirements listed "
            "above.",
            "- Neutral: status is Proposed — a human must review and accept this model.",
        ]

        # Only constructs the code generator actually skipped (GENERATION_GAP flags) are
        # caveated; non-standard types that were generated get no caveat — they work.
        if generation_gaps:
            lines.append(
                f"- Caveat: {len(generation_gaps)} construct(s) could not be generated "
                f"and are flagged for human review: {', '.join(generation_gaps)}."
            )

        lines += [
            "",
            "## References",
            "",
            f"- Source requirement document(s): {', '.join(state.input_documents) or '—'}",
            f"- Generated dbt models: {len(state.artifacts.dbt_models)} raw-vault "
            f"model(s) + {len(state.artifacts.staging_models)} staging model(s) "
            "(see `state.artifacts`)",
            "",
        ]
        return "\n".join(lines)
