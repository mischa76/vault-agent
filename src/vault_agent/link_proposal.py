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

from vault_agent.rules.dv2_rules import (
    canonical_hub_key_column,
    construct_binds_to_source_table,
    normalize_identifier,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    ForeignKeyRef,
    Hub,
    LinkProposal,
    LinkProposals,
    SourceTable,
    VaultAgentState,
)

logger = logging.getLogger(__name__)


def _target_hub(existing: DVModel, fk: ForeignKeyRef) -> tuple[Hub | None, str]:
    """The existing hub an FK points at, or ``(None, reason)`` — never a guess.

    Matched on the hub's CANONICAL key column, through the helper: that column is what the
    join is actually made of, so anything else can be right about the concept and wrong about
    the data. Where several hubs share the key, the referenced TABLE breaks the tie; where it
    cannot, this returns nothing rather than picking one.
    """
    referenced = normalize_identifier(fk.references_columns[0])
    matches = [
        hub
        for hub in existing.hubs
        if normalize_identifier(canonical_hub_key_column(hub)) == referenced
    ]
    if not matches:
        return None, f"no existing hub is keyed on {fk.references_columns[0]!r}"
    if len(matches) == 1:
        return matches[0], ""

    by_table = [
        hub for hub in matches if construct_binds_to_source_table(hub.name, fk.references_table)
    ]
    if len(by_table) == 1:
        return by_table[0], ""
    names = ", ".join(sorted(hub.name for hub in matches))
    return None, (
        f"{len(matches)} hubs are keyed on {fk.references_columns[0]!r} ({names}) and the "
        f"referenced table {fk.references_table!r} does not single one out"
    )


def propose_links(
    existing: DVModel, source_schemas: list[SourceTable]
) -> tuple[LinkProposals, list[tuple[str, str]]]:
    """Propose one link per declared foreign key that points at an existing hub.

    Returns the proposals and a list of ``(asset, reason)`` skips the caller flags. A skip is
    honest output, not a defect: a composite key or an ambiguous target is a question this
    pass is not entitled to answer.
    """
    proposals: list[LinkProposal] = []
    skipped: list[tuple[str, str]] = []

    for table in source_schemas:
        for fk in table.foreign_keys:
            asset = f"{table.table}.{','.join(fk.columns)}"
            if not fk.is_single_column:
                # §3.2 condition 2. Which column pairs with which hub key is a modelling
                # decision, and a composite link built from the wrong pairing is wrong data.
                skipped.append(
                    (asset, f"composite foreign key ({len(fk.columns)} columns) — not guessed at")
                )
                continue

            hub, reason = _target_hub(existing, fk)
            if hub is None:
                skipped.append((asset, reason))
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

    return LinkProposals(proposals=proposals), skipped


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
    for asset, reason in skipped:
        state.flag(
            "link_proposer",
            f"no link proposed for {asset}: {reason}",
            kind=FlagKind.LINK_PROPOSAL_SKIPPED,
            asset=asset,
        )
    logger.info(
        "link proposer: %d proposal(s) from declared foreign keys, %d skipped",
        len(proposals.proposals),
        len(skipped),
    )
    return state
