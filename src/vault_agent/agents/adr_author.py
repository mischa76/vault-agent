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
deterministically, never derived from any repository directory. Repo-level ADR numbering
happens only when a human *accepts* the proposal and moves it into
``docs/architecture/adrs/``; the pipeline never numbers into the repo sequence.

Determinism (WP26 §2.3), stated precisely because the previous wording was not true: the
ADR is byte-identical for a given state **and date**. The date is the single input that
does not come from state — ``today`` is injectable and defaults to the clock, which is
correct for a dated decision record but means two runs of identical state on either side
of midnight differ in exactly that line. Nothing else here reads a clock, an environment,
or a filesystem.

What the ADR renders, and what it deliberately does not (WP26 §4.1 — every typed field
that changes how the vault *behaves* is either visible or listed here):

* Rendered: hub business key + multi-source feeds and their canonical staging key column
  (WP10); link participations with ADR-0009 roles, unit of work, driving key (WP8), and
  the transactional link's payload/event timestamp (which selects ``automate_dv.t_link``);
  satellite parent, payload, non-standard type + child dependent key, ``source_table``
  (WP7), split rationale; the ratified business↔source mappings (WP9); requirement traces.
* Deliberately omitted: ``Hub.source_entity`` (a modelling input the validator's collision
  gates read — it does not change generated SQL); a proposal's ``confidence``/``evidence``
  (the ratification trail belongs to ``mappings.review.yml``, which the reviewer has open
  next to this); and the data contracts (their own artifact, per WP26 §5).
"""
import logging
from datetime import date

from vault_agent.agents.base import BaseAgent
from vault_agent.rules.dv2_rules import canonical_hub_key_column
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    Link,
    LinkHubRef,
    ProposedMapping,
    Satellite,
    VaultAgentState,
)

logger = logging.getLogger(__name__)

# The generated ADR is always the first (and only) ADR of its output project.
_OUTPUT_ADR_NUMBER = 1

# A standard satellite says nothing about its type — silence means standard, so only the
# types that change what AutomateDV macro is rendered get a label.
_SAT_TYPE_LABELS = {
    "multi_active": "Multi-active satellite",
    "effectivity": "Effectivity satellite",
}


def _ids(requirement_ids: list[str]) -> str:
    return ", ".join(requirement_ids) if requirement_ids else "—"


def _ref(ref: LinkHubRef) -> str:
    """One participation as ``hub_account`` / ``hub_account (counterparty)`` (ADR-0009).

    The single formatting point, so the driving key reads exactly like the participation
    list it names — a reader comparing the two lines must not have to translate."""
    return ref.hub if ref.role is None else f"{ref.hub} ({ref.role})"


# Construct renderers are module-level and one-line-per-construct on purpose: WP23's
# delta-ADR renders a *subset* of the same constructs, so it can reuse these rather than
# fork the formatting (§2.4 keeps the untouched lines' wording stable).
def _hub_line(hub: Hub) -> str:
    integration = ""
    if hub.sources:
        feeds = ", ".join(
            f"{source.source_table}.{source.business_key_column}" for source in hub.sources
        )
        # The canonical name comes from rules/ (WP10 §2.2, WP24) — never re-derived here,
        # or the ADR would document a column the staging models do not build.
        integration = (
            f" Integrated from {len(hub.sources)} source(s): {feeds}; "
            f"canonical staging key column `{canonical_hub_key_column(hub)}`."
        )
    return (
        f"- **{hub.name}** — business key `{hub.business_key}`. {hub.description}"
        f"{integration} _(requirements: {_ids(hub.requirement_ids)})_"
    )


def _link_line(link: Link) -> str:
    uow = f" Unit of work: {link.unit_of_work}." if link.unit_of_work else ""
    connected = ", ".join(_ref(ref) for ref in link.hub_refs)
    # Unresolvable driving-key entries simply do not appear — the validator's
    # E_DRIVING_KEY_NOT_IN_LINK owns that complaint, the ADR does not duplicate it.
    driving_refs = link.resolve_driving_refs()
    driving = ""
    if driving_refs:
        driving = f" Driving key: {', '.join(_ref(ref) for ref in driving_refs)}."
    transactional = ""
    if link.link_type == "transactional":
        payload = ", ".join(link.payload) if link.payload else "—"
        event = link.event_timestamp or "—"
        transactional = (
            f" Transactional link (non-historized): payload {payload}; "
            f"event timestamp {event}."
        )
    return (
        f"- **{link.name}** — connects {connected}. {link.description}"
        f"{transactional}{uow}{driving} _(requirements: {_ids(link.requirement_ids)})_"
    )


def _sat_line(sat: Satellite) -> str:
    payload = ", ".join(sat.attributes) if sat.attributes else "—"
    kind = ""
    label = _SAT_TYPE_LABELS.get(sat.sat_type)
    if label:
        cdk = ", ".join(sat.child_dependent_key)
        kind = f" {label}" + (f", child dependent key: {cdk}." if cdk else ".")
    source = f" Source table: {sat.source_table}." if sat.source_table else ""
    split = f" Split rationale: {sat.split_rationale}." if sat.split_rationale else ""
    return (
        f"- **{sat.name}** — on {sat.parent}; payload: {payload}. "
        f"{sat.description}{kind}{source}{split} _(requirements: {_ids(sat.requirement_ids)})_"
    )


def _mappings_section(mappings: ProposedMapping) -> list[str]:
    """The WP9 business↔source mappings, or nothing at all when the mapper was inert.

    An ungrounded run produces no proposals, no gaps and no unresolved concepts, and then
    this section is absent entirely — so an ungrounded ADR stays byte-identical to the
    pre-WP26 one (§2.2, pinned by test). A gap is first-class output, not a non-answer, so
    a run that produced only gaps still gets the section."""
    if not (mappings.proposals or mappings.gaps or mappings.unresolved):
        return []
    lines = [
        "",
        f"### Source mappings ({len(mappings.proposals)})",
        "",
        "Where each modelled concept's values come from (ADR-0008). The category is the "
        "deterministic confidence tier; `accepted` / `overridden` mark a human decision, "
        "`proposed` still awaits one.",
        "",
    ]
    for proposal in mappings.proposals:
        lines.append(
            f"- `{proposal.concept}` → `{proposal.table}`.`{proposal.column}` — "
            f"{proposal.category}, {proposal.ratification_status}"
        )
    if mappings.gaps:
        lines += [
            "",
            f"No in-scope source — Business Vault / marts ({len(mappings.gaps)}): "
            f"{', '.join(mappings.gaps)}.",
        ]
    if mappings.unresolved:
        lines += [
            "",
            f"Unresolved — the mapper could not decide ({len(mappings.unresolved)}): "
            f"{', '.join(mappings.unresolved)}.",
        ]
    return lines


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

        logger.info(
            "rendering model ADR: %d hub(s), %d link(s), %d satellite(s)",
            len(state.dv_model.hubs),
            len(state.dv_model.links),
            len(state.dv_model.satellites),
        )
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
        lines += [_hub_line(hub) for hub in model.hubs]

        lines += ["", f"### Links ({len(model.links)})", ""]
        lines += [_link_line(link) for link in model.links]

        lines += ["", f"### Satellites ({len(model.satellites)})", ""]
        lines += [_sat_line(sat) for sat in model.satellites]

        lines += _mappings_section(state.mappings)

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
