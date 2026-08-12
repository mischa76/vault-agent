"""Links proposed from the new source's own declared foreign keys (WP34).

Deterministic, keyless, zero model calls. This module exists because three prompt
interventions failed to make the modeler relate a new increment to a prior vault
(WP30.1-30.3, ~$46), and because the reason turned out to be partly structural: the foreign
keys stating those relations were dropped by the schema derivation before any agent could
see them. A declared foreign key whose referenced column is an existing hub's business key
*is* a link, and saying so needs no reasoning at all.

**What this module does NOT do.** It does not write links. It proposes them, and a human
ratifies at the WP29 checkpoint before anything reaches the model — the same treatment entity
resolution gets, for the same reason: a link writes join keys into tables holding history, so
being wrong is not a bad suggestion, it is bad data.

**The spec's third category is deliberately not implemented.** §3.2 illustrates a
``key_name_only`` tier for hubs matched by column-name coincidence with no declared foreign
key behind them. The conditions in that same section admit only declared foreign keys, and
implementing the looser tier would rebuild exactly the noise WP30.3 measured and was reverted
for: against step 4's 30-hub vault, AdventureWorks Sales matches 13 hubs by business-key
column and 7 of those only because they are keyed on ``Name``. Two tiers, both evidenced by a
declaration; the third is recorded as rejected rather than silently absent.
"""
import logging

from vault_agent.agents.base import BaseAgent
from vault_agent.rules.dv2_rules import (
    canonical_hub_key_column,
    construct_base_name,
    construct_binds_to_source_table,
    normalize_identifier,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    ForeignKeyRef,
    Hub,
    Link,
    LinkHubRef,
    LinkProposal,
    LinkProposals,
    LinkSkip,
    LinkSkipReason,
    SourceTable,
    VaultAgentState,
)

logger = logging.getLogger(__name__)


def _target_hub(
    existing: DVModel, fk: ForeignKeyRef
) -> tuple[Hub | None, LinkSkipReason | None, str]:
    """The existing hub an FK points at, or ``(None, reason_code, message)`` — never a guess.

    Matched on the hub's CANONICAL key column, through the helper: that column is what the
    join is actually made of, so anything else can be right about the concept and wrong about
    the data. Where several hubs share the key, the referenced TABLE breaks the tie; where it
    cannot, this returns nothing rather than picking one.

    The CODE is returned beside the sentence because the two declines are different findings:
    ``no_hub_for_key`` says the vault is keyed differently from how the source references it,
    ``ambiguous_hub`` says the vault is keyed the same way twice. Counting them together
    hides which one a landscape actually suffers from.
    """
    referenced = normalize_identifier(fk.references_columns[0])
    matches = [
        hub
        for hub in existing.hubs
        if normalize_identifier(canonical_hub_key_column(hub)) == referenced
    ]
    if not matches:
        return None, "no_hub_for_key", (
            f"no existing hub is keyed on {fk.references_columns[0]!r}"
        )
    if len(matches) == 1:
        return matches[0], None, ""

    by_table = [
        hub for hub in matches if construct_binds_to_source_table(hub.name, fk.references_table)
    ]
    if len(by_table) == 1:
        return by_table[0], None, ""
    names = ", ".join(sorted(hub.name for hub in matches))
    return None, "ambiguous_hub", (
        f"{len(matches)} hubs are keyed on {fk.references_columns[0]!r} ({names}) and the "
        f"referenced table {fk.references_table!r} does not single one out"
    )


def propose_links(
    existing: DVModel, source_schemas: list[SourceTable]
) -> tuple[LinkProposals, list[LinkSkip]]:
    """Propose one link per declared foreign key that points at an existing hub.

    Returns the proposals and the typed skips the caller flags. A skip is honest output, not a
    defect: a composite key or an ambiguous target is a question this pass is not entitled to
    answer. The skips come back in the ``LinkProposals`` too — this second return value stays
    because the caller raises one flag per skip and would otherwise re-walk the list.
    """
    proposals: list[LinkProposal] = []
    skipped: list[LinkSkip] = []

    for table in source_schemas:
        for fk in table.foreign_keys:
            asset = f"{table.table}.{','.join(fk.columns)}"
            if not fk.is_single_column:
                # §3.2 condition 2. Which column pairs with which hub key is a modelling
                # decision, and a composite link built from the wrong pairing is wrong data.
                skipped.append(
                    LinkSkip(
                        asset=asset,
                        reason="composite_key",
                        message=(
                            f"composite foreign key ({len(fk.columns)} columns) — not guessed at"
                        ),
                    )
                )
                continue

            hub, reason_code, reason = _target_hub(existing, fk)
            if hub is None:
                assert reason_code is not None  # a decline always carries its code
                skipped.append(LinkSkip(asset=asset, reason=reason_code, message=reason))
                continue

            canonical = canonical_hub_key_column(hub)
            same_name = normalize_identifier(fk.columns[0]) == normalize_identifier(canonical)
            proposals.append(
                LinkProposal(
                    source_table=table.table,
                    source_column=fk.columns[0],
                    target_hub=hub.name,
                    target_business_key=canonical,
                    category=(
                        "declared_fk_same_name" if same_name else "declared_fk_renamed"
                    ),
                    evidence=[
                        f"{table.table}.{fk.columns[0]} references "
                        f"{fk.references_table}.{fk.references_columns[0]} (declared foreign "
                        f"key in the source catalogue)",
                        f"{hub.name} is keyed on {canonical}",
                    ]
                    + (
                        []
                        if same_name
                        else [
                            f"staging must alias {fk.columns[0]} to {canonical} before "
                            f"hashing — the names differ"
                        ]
                    ),
                )
            )

    return LinkProposals(proposals=proposals, skipped=skipped), skipped


def proposal_key(proposal: LinkProposal) -> str:
    """The stable handle a human uses to answer one proposal: ``Customer.PersonID``.

    The same string the skip flags use as their ``asset``, so everything a reviewer sees
    about one foreign key is keyed identically — and it is a typed handle, not a rendered
    sentence, because consumers must never parse a message."""
    return f"{proposal.source_table}.{proposal.source_column}"


def pending_link_decisions(link_proposals: LinkProposals) -> list[LinkProposal]:
    """Proposals a human must answer before modelling. Pure, and safe above ``interrupt()``.

    Every proposal is pending until answered: unlike a resolution, there is no class of link
    proposal that needs no decision. A link is only ever built because someone said yes."""
    return [p for p in link_proposals.proposals if p.ratification_status == "proposed"]


def _link_name(near: str, target: str) -> str:
    """``hub_customer`` + ``hub_person`` -> ``link_customer_person`` (E_BAD_NAME-shaped)."""
    return "link_" + "_".join(
        normalize_identifier(construct_base_name(name)).lower() for name in (near, target)
    )


def _grain(link: Link) -> frozenset[str]:
    """A link's identity for duplicate detection: the SET of hubs it connects.

    Names are the modeler's choice and the eval conventions already say so — score structure,
    not free-form names. A link the modeler happened to build under a different name is the
    same link, and proposing it again would be a duplicate, not a contribution."""
    return frozenset(ref.hub for ref in link.hub_refs)


def apply_ratified_link_proposals(
    delta: DVModel, existing: DVModel, state: VaultAgentState
) -> DVModel:
    """Add a link per RATIFIED proposal to the modeler's delta, before it is merged.

    Deliberately applied to the delta rather than to the merged model: the link then goes
    through ``merge_models`` and every validator gate on the ordinary path, with no
    privileged route into the model (§3.6). An unratified proposal is never applied — that is
    the whole safety property, and it is why this reads ``ratified()`` and not ``proposals``.

    Silent about nothing: a proposal whose near side was never modelled, or whose link the
    modeler already built, is logged and flagged rather than dropped."""
    ratified = state.link_proposals.ratified()
    if not ratified:
        return delta

    hubs = {hub.name: hub for hub in [*existing.hubs, *delta.hubs]}
    grains = {_grain(link) for link in [*existing.links, *delta.links]}
    added = 0

    for proposal in ratified:
        near = next(
            (
                name
                for name in hubs
                if name.startswith("hub_")
                and construct_binds_to_source_table(name, proposal.source_table)
            ),
            None,
        )
        if near is None:
            state.flag(
                "link_proposer",
                f"ratified link to {proposal.target_hub} not applied: no hub was modelled "
                f"for {proposal.source_table}",
                kind=FlagKind.LINK_PROPOSAL_SKIPPED,
                asset=f"{proposal.source_table}.{proposal.source_column}",
            )
            continue
        if proposal.target_hub not in hubs:
            state.flag(
                "link_proposer",
                f"ratified link not applied: {proposal.target_hub} is not in the model",
                kind=FlagKind.LINK_PROPOSAL_SKIPPED,
                asset=f"{proposal.source_table}.{proposal.source_column}",
            )
            continue

        grain = frozenset({near, proposal.target_hub})
        if grain in grains or len(grain) < 2:
            # The modeler built it, or the FK points a table at its own hub. Neither is a
            # defect and neither needs a second link.
            logger.info(
                "link proposal for %s already covered by an existing link", proposal.source_table
            )
            continue

        delta.links.append(
            Link(
                name=_link_name(near, proposal.target_hub),
                connected_hubs=[
                    LinkHubRef(hub=near),
                    LinkHubRef(
                        hub=proposal.target_hub,
                        # §3.4: only when the names differ. An alias that restates the
                        # canonical name would be noise the gate then has to check.
                        source_key_column=(
                            proposal.source_column if proposal.needs_alias else None
                        ),
                    ),
                ],
                description=(
                    f"Declared foreign key {proposal.source_table}."
                    f"{proposal.source_column} references {proposal.target_business_key}; "
                    f"ratified from the source catalogue (WP34)."
                ),
            )
        )
        grains.add(grain)
        added += 1

    logger.info("applied %d ratified link proposal(s) to the delta", added)
    return delta


def link_source_overrides(state: VaultAgentState) -> dict[str, str]:
    """Staging bindings an FK-derived link already knows (§3.5).

    A link's staging relation is otherwise INFERRED as ``raw_<base>`` and flagged, because no
    declared table is named like a link. The proposal knows it: the referencing table. Keyed
    the way ``source_mapper.source_overrides`` keys its own entries, so the existing
    ``bind_sources`` override path consumes them unchanged and raises no flag."""
    overrides: dict[str, str] = {}
    for proposal in state.link_proposals.ratified():
        for link in state.dv_model.links:
            if any(
                construct_binds_to_source_table(ref.hub, proposal.source_table)
                for ref in link.hub_refs
            ) and any(ref.hub == proposal.target_hub for ref in link.hub_refs):
                overrides[normalize_identifier(construct_base_name(link.name))] = (
                    proposal.source_table
                )
    return overrides


def is_grounded_extension(state: VaultAgentState) -> bool:
    """The gate WP29 uses, applied here: an existing model AND a declared schema.

    Without both there is nothing to propose against, and keeping the condition identical to
    the resolver's is what makes greenfield and ungrounded runs provably inert."""
    return state.existing_model is not None and bool(state.source_schemas)


def collect_link_proposals(state: VaultAgentState) -> VaultAgentState:
    """The ``link_proposer`` node's whole body: propose, flag the skips, record nothing else.

    Pure and idempotent by construction — it reads state and replaces
    ``state.link_proposals`` wholesale — because the checkpoint that follows re-executes its
    own node on resume and the two must not drift.
    """
    if not is_grounded_extension(state):
        return state
    assert state.existing_model is not None  # implied by is_grounded_extension

    proposals, skipped = propose_links(state.existing_model, state.source_schemas)
    state.link_proposals = proposals
    for skip in skipped:
        state.flag(
            "link_proposer",
            f"no link proposed for {skip.asset}: {skip.message}",
            kind=FlagKind.LINK_PROPOSAL_SKIPPED,
            asset=skip.asset,
        )
    logger.info(
        "link proposer: %d proposal(s) from declared foreign keys, %d skipped",
        len(proposals.proposals),
        len(skipped),
    )
    return state


class LinkProposerAgent(BaseAgent):
    """The ``link_proposer`` node: deterministic, keyless, no prompt (agent conventions).

    It owns exactly one state field, ``link_proposals``, and raises typed flags for the
    foreign keys it declines to answer for. Everything it does is a pure function of state,
    which is what lets the checkpoint that follows re-execute safely on resume."""

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        return collect_link_proposals(state)
