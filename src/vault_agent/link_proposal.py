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
    construct_base_from_table,
    construct_base_name,
    construct_binds_to_source_table,
    hub_binds_to_source_table,
    normalize_identifier,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    ForeignKeyRef,
    Hub,
    KeyLicense,
    KeyTranslation,
    Link,
    LinkHubRef,
    LinkProposal,
    LinkProposals,
    LinkSkip,
    LinkSkipReason,
    Participation,
    RelationshipLinkProposal,
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
        hub for hub in matches if hub_binds_to_source_table(hub, fk.references_table)
    ]
    if len(by_table) == 1:
        return by_table[0], None, ""
    names = ", ".join(sorted(hub.name for hub in matches))
    return None, "ambiguous_hub", (
        f"{len(matches)} hubs are keyed on {fk.references_columns[0]!r} ({names}) and the "
        f"referenced table {fk.references_table!r} does not single one out"
    )


def _onward_key(fk: ForeignKeyRef, declared: dict[str, SourceTable]) -> ForeignKeyRef | None:
    """WP39: ``A.c → B.k`` read as ``A.c → C.x`` when ``B`` declares exactly one single-column
    foreign key on ``k`` itself (``B.k → C.x``). Every value of ``A.c`` is a value of ``B.k``,
    and every value of ``B.k`` a value of ``C.x`` — the same key, one table further. ``None``
    when ``B`` is not declared here or does not carry exactly one such key."""
    middle = declared.get(normalize_identifier(fk.references_table))
    if middle is None:
        return None
    key = normalize_identifier(fk.references_columns[0])
    onward = [
        g for g in middle.foreign_keys
        if g.is_single_column
        and normalize_identifier(g.columns[0]) == key
        and normalize_identifier(g.references_table) != normalize_identifier(middle.table)
    ]
    if len(onward) != 1:
        return None
    return ForeignKeyRef(
        columns=list(fk.columns),
        references_table=onward[0].references_table,
        references_columns=list(onward[0].references_columns),
        references_schema=onward[0].references_schema,
    )


def _translation_target(
    existing: DVModel,
    fk: ForeignKeyRef,
    declared: dict[str, SourceTable],
    *,
    hop: bool = True,
) -> tuple[Hub | None, KeyTranslation | None, LinkSkipReason | None, str]:
    """WP36 (ADR-0013): when no hub is keyed on the referenced column, is there exactly one
    hub built FROM the referenced relation, keyed on another column? Then the FK references a
    surrogate and the hub the natural key, and the bridge is a join through that relation.

    Deterministic, three conditions (spec §2): one hub binds the referenced table by name
    (the prefix-exact helper — ``hub_product`` binds ``Product``, ``hub_product_category`` does
    not); its canonical key differs from the referenced column; and if the referenced table is
    declared in THIS increment it must carry both columns — otherwise the hub's own provenance
    stands for the natural key being there (it was modelled from that relation on that key).

    Returns ``(None, None, None, "")`` when the shape is simply not this one, so the caller
    keeps its ordinary ``no_hub_for_key`` skip; a typed ``translation_key_missing`` when the
    shape holds but the declared relation lacks a column."""
    bound = [
        hub for hub in existing.hubs if hub_binds_to_source_table(hub, fk.references_table)
    ]
    if not bound and hop:
        # WP39: no hub is built from the referenced table, so the nearest hub may be one table
        # further — `SalesOrderHeader.SalesPersonID → SalesPerson.BusinessEntityID → Employee`,
        # `hub_employee` keyed on NationalIDNumber. One hop only, and only here: a hub bound to
        # the referenced table is always found first, and WP34's key match runs before any
        # translation is tried, so the nearest hub decides every shape it decided before.
        onward = _onward_key(fk, declared)
        if onward is not None:
            return _translation_target(existing, onward, declared, hop=False)
    if len(bound) != 1:
        return None, None, None, ""
    hub = bound[0]
    natural = canonical_hub_key_column(hub)
    surrogate = fk.references_columns[0]
    if normalize_identifier(natural) == normalize_identifier(surrogate):
        return None, None, None, ""  # cannot happen after _target_hub declined, kept explicit
    relation = declared.get(normalize_identifier(fk.references_table))
    if relation is not None:
        present = {normalize_identifier(c) for c in relation.column_names}
        missing = [
            c for c in (surrogate, natural) if normalize_identifier(c) not in present
        ]
        if missing:
            return None, None, "translation_key_missing", (
                f"{fk.references_table!r} is declared without {', '.join(repr(m) for m in missing)}"
                f" — translating {fk.columns[0]!r} to {hub.name}'s key {natural!r} would join on "
                f"a column that is not there"
            )
    return hub, KeyTranslation(
        referencing_column=fk.columns[0],
        through_table=fk.references_table,
        through_schema=fk.references_schema,
        surrogate_column=surrogate,
        natural_key_column=natural,
    ), None, ""


def resolve_fk_target(
    model: DVModel, fk: ForeignKeyRef, declared: dict[str, SourceTable]
) -> tuple[Hub | None, KeyTranslation | None, LinkSkipReason | None, str]:
    """One foreign key against one model: the hub it points at, with translation if needed.

    The single resolution the proposer (against the existing vault) and the relationship
    applier (against the merged model, WP37) both use — two call sites, one rule, per the
    invariant that a seam matched by two different identity rules is the defect site."""
    hub, reason, message = _target_hub(model, fk)
    if hub is not None:
        return hub, None, None, ""
    # The key column declined — none keyed so, or several. Either way, if exactly ONE hub is
    # built from the REFERENCED table and keyed on another column, the foreign key means that
    # hub through a translation (ADR-0013 §1): the declaration names the table, and several
    # hubs sharing a key NAME (BusinessEntityID on Person, Employee, Store …) say nothing about
    # Vendor. Measured necessary on 2026-09-12: ProductVendor.BusinessEntityID → Vendor was
    # "ambiguous" against the vault while hub_vendor sat right there, keyed on AccountNumber.
    t_hub, translation, t_reason, t_message = _translation_target(model, fk, declared)
    if t_hub is not None:
        return t_hub, translation, None, ""
    if t_reason is not None:
        return None, None, t_reason, t_message
    return None, None, reason, message


def _participation(
    fk: ForeignKeyRef, hub: Hub | None, translation: KeyTranslation | None
) -> Participation:
    p = Participation(
        referencing_column=fk.columns[0],
        references_table=fk.references_table,
        references_column=fk.references_columns[0],
        references_schema=fk.references_schema,
    )
    if hub is None:
        return p
    canonical = canonical_hub_key_column(hub)
    p.target_hub = hub.name
    p.target_business_key = canonical
    if translation is not None:
        p.key_translation = translation
    elif normalize_identifier(fk.columns[0]) != normalize_identifier(canonical):
        p.source_key_column = fk.columns[0]
    return p


def _relationship_candidate(
    existing: DVModel, table: SourceTable, declared: dict[str, SourceTable]
) -> RelationshipLinkProposal | None:
    """WP37 §2: a table with two or more single-column keys, at least one of which resolves
    against the existing vault now; keys into THIS increment's tables stay pending for the
    applier. Purely intra-increment tables are the modeler's own business and yield nothing."""
    keys = [fk for fk in table.foreign_keys if fk.is_single_column]
    if len(keys) < 2:
        return None
    participations: list[Participation] = []
    resolved_now = 0
    for fk in keys:
        hub, translation, reason, _ = resolve_fk_target(existing, fk, declared)
        if hub is not None:
            resolved_now += 1
        elif not (
            normalize_identifier(fk.references_table) in declared
            and not any(hub_binds_to_source_table(h, fk.references_table) for h in existing.hubs)
        ):
            # Points outside this increment at nothing this vault can name (no hub, or several
            # hubs and no tie-break): never completable, so no candidate. A key into THIS
            # increment's own, not-yet-hubbed table is PENDING whatever the key-name match said.
            return None
        participations.append(_participation(fk, hub, translation))
    if resolved_now == 0:
        return None
    return RelationshipLinkProposal(
        source_table=table.table,
        participations=participations,
        evidence=[
            f"{table.table} declares {len(keys)} single-column foreign keys and is therefore a "
            f"relationship between the tables they reference, not a business object of its own",
        ] + [
            (
                f"{table.table}.{p.referencing_column} → {p.references_table}."
                f"{p.references_column}: "
                + (f"{p.target_hub} (existing)" if p.resolved
                   else "no hub yet — this increment's table, resolved after the modeler")
            )
            for p in participations
        ] + [
            "applies only if the modeler builds no hub for the table itself; a hub there means "
            "the ordinary per-key links apply instead"
        ],
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
    relationships: list[RelationshipLinkProposal] = []
    licenses: list[KeyLicense] = []
    declared: dict[str, SourceTable] = {}
    for table in source_schemas:
        declared.setdefault(normalize_identifier(table.table), table)

    for table in source_schemas:
        candidate = _relationship_candidate(existing, table, declared)
        if candidate is not None:
            relationships.append(candidate)
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
                # WP36: the vault may be keyed on the natural key while the source references
                # the surrogate — one join away, not unreachable. Tried only after the plain
                # match declined, so every WP34 shape is decided exactly as before.
                t_hub, translation, t_reason, t_message = _translation_target(
                    existing, fk, declared
                )
                if t_hub is not None and translation is not None:
                    hopped = normalize_identifier(translation.through_table) != (
                        normalize_identifier(fk.references_table)
                    )
                    proposals.append(
                        LinkProposal(
                            source_table=table.table,
                            source_column=fk.columns[0],
                            target_hub=t_hub.name,
                            target_business_key=translation.natural_key_column,
                            category="declared_fk_translated",
                            translation=translation,
                            evidence=[
                                f"{table.table}.{fk.columns[0]} references "
                                f"{fk.references_table}.{fk.references_columns[0]} (declared "
                                f"foreign key in the source catalogue)",
                            ]
                            + (
                                [
                                    f"{fk.references_table}.{fk.references_columns[0]} is itself "
                                    f"a declared foreign key to {translation.through_table}."
                                    f"{translation.surrogate_column}, and no hub is built from "
                                    f"{fk.references_table} — the same key one table further "
                                    f"(WP39)"
                                ]
                                if hopped
                                else []
                            )
                            + [
                                f"{t_hub.name} is built from {translation.through_table} and "
                                f"keyed on {translation.natural_key_column}, not on "
                                f"{translation.surrogate_column}",
                                f"staging must join {table.table} to {translation.through_table} "
                                f"on {translation.surrogate_column} and hash the link from "
                                f"{translation.natural_key_column} — a translation, not an alias",
                            ],
                        )
                    )
                    continue
                if t_reason is not None:
                    reason_code, reason = t_reason, t_message
            if hub is None:
                assert reason_code is not None  # a decline always carries its code
                if reason_code in ("no_hub_for_key", "ambiguous_hub") and _licensable(
                    existing, table, fk, declared
                ):
                    # WP40: the referenced table is this increment's own and has no hub yet —
                    # the hub, if the modeler builds one, is known only after modelling.
                    licenses.append(_license(table, fk))
                    continue
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

    return (
        LinkProposals(
            proposals=proposals, skipped=skipped, relationships=relationships, licenses=licenses
        ),
        skipped,
    )


def _licensable(
    existing: DVModel, table: SourceTable, fk: ForeignKeyRef, declared: dict[str, SourceTable]
) -> bool:
    """WP40: a single-column key into a DIFFERENT table declared in this increment, which no
    hub of the existing vault binds."""
    referenced = normalize_identifier(fk.references_table)
    return (
        referenced in declared
        and referenced != normalize_identifier(table.table)
        and not any(hub_binds_to_source_table(h, fk.references_table) for h in existing.hubs)
    )


def _license(table: SourceTable, fk: ForeignKeyRef) -> KeyLicense:
    return KeyLicense(
        source_table=table.table,
        source_column=fk.columns[0],
        references_table=fk.references_table,
        references_column=fk.references_columns[0],
        references_schema=fk.references_schema,
        evidence=[
            f"{table.table}.{fk.columns[0]} references {fk.references_table}."
            f"{fk.references_columns[0]} (declared foreign key in the source catalogue)",
            f"{fk.references_table} is declared in this increment and has no hub yet; the hub, "
            f"if the modeler builds one, is resolved after modelling",
            f"licenses a translation or alias for links and satellites the modeler builds from "
            f"{table.table}; builds nothing itself (WP40)",
        ],
    )


def proposal_key(proposal: LinkProposal | RelationshipLinkProposal | KeyLicense) -> str:
    """The stable handle a human uses to answer one proposal: ``Customer.PersonID``, or
    ``ProductVendor.*`` for a relationship table (WP37 — one decision per table).

    The same string the skip flags use as their ``asset``, so everything a reviewer sees
    about one foreign key is keyed identically — and it is a typed handle, not a rendered
    sentence, because consumers must never parse a message."""
    if isinstance(proposal, RelationshipLinkProposal):
        return f"{proposal.source_table}.*"
    return f"{proposal.source_table}.{proposal.source_column}"


def pending_link_decisions(
    link_proposals: LinkProposals,
) -> list[LinkProposal | RelationshipLinkProposal | KeyLicense]:
    """Proposals a human must answer before modelling. Pure, and safe above ``interrupt()``.

    Every proposal is pending until answered: unlike a resolution, there is no class of link
    proposal that needs no decision. A link is only ever built because someone said yes.
    Relationship-table proposals (WP37) are listed after the per-key ones."""
    pending: list[LinkProposal | RelationshipLinkProposal | KeyLicense] = [
        p for p in link_proposals.proposals if p.ratification_status == "proposed"
    ]
    pending.extend(p for p in link_proposals.relationships if p.ratification_status == "proposed")
    # WP40: key licenses last — they build nothing, they license repairs.
    pending.extend(p for p in link_proposals.licenses if p.ratification_status == "proposed")
    return pending


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
                for name, hub in hubs.items()
                if name.startswith("hub_") and hub_binds_to_source_table(hub, proposal.source_table)
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

        if proposal.translation is not None:
            # WP36: its own review class — the reviewer must see that this link is a join
            # through another relation, not a renamed column (ADR-0013 §3).
            state.flag(
                "link_proposer",
                f"link to {proposal.target_hub} from {proposal.source_table} requires "
                f"surrogate→natural-key translation through "
                f"{proposal.translation.through_table} "
                f"({proposal.translation.surrogate_column} → "
                f"{proposal.translation.natural_key_column}); review the translation model",
                kind=FlagKind.LINK_TRANSLATION,
                asset=f"{proposal.source_table}.{proposal.source_column}",
            )
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
                        # WP36: a translation instead of an alias; the two exclude each other.
                        key_translation=proposal.translation,
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

    # WP37: relationship tables. Resolved against the MERGED model, because the pending
    # participations reference this increment's own tables, which have hubs only now.
    declared = {normalize_identifier(t.table): t for t in state.source_schemas}
    merged = DVModel(hubs=list(hubs.values()), links=[*existing.links, *delta.links])
    for rel in state.link_proposals.ratified_relationships():
        if any(hub_binds_to_source_table(hub, rel.source_table) for hub in hubs.values()):
            logger.info(
                "relationship proposal for %s not applied: the table got a hub of its own, the "
                "per-key links cover it", rel.source_table,
            )
            continue
        fk_by_column = {
            normalize_identifier(fk.columns[0]): fk
            for t in state.source_schemas if t.table == rel.source_table
            for fk in t.foreign_keys if fk.is_single_column
        }
        # A pending participation is resolved against THIS attempt's merged model, every
        # time. The first build resolved it once and kept the answer, so when attempt 2 of a
        # re-model loop dropped the hub attempt 1 had resolved to, the link was still built
        # to it (`E_LINK_UNKNOWN_HUB`) and attempt 3 re-created the hub to satisfy the link
        # (2026-09-13, run 20260913T153801752650Z). The resolution IS written back — the
        # gate `E_LINK_TRANSLATION_UNRATIFIED` reads the participations as the provenance of
        # every translation — but marked as the applier's, so the next attempt redoes it.
        # A participation the PROPOSER resolved is permanent: its hub is in the existing
        # vault, and existing hubs are immutable.
        unresolved: list[str] = []
        participations: list[Participation] = []
        for p in rel.participations:
            if p.resolved and not p.resolved_by_applier:
                participations.append(p)
                continue
            fk = fk_by_column.get(normalize_identifier(p.referencing_column))
            hub, translation = (None, None)
            if fk is not None:
                hub, translation, _, _ = resolve_fk_target(merged, fk, declared)
            if hub is None:
                p.target_hub = p.target_business_key = None
                p.source_key_column = p.key_translation = None
                p.resolved_by_applier = False
                unresolved.append(p.referencing_column)
                continue
            fresh = _participation(fk, hub, translation)  # type: ignore[arg-type]
            p.target_hub, p.target_business_key = fresh.target_hub, fresh.target_business_key
            p.source_key_column, p.key_translation = fresh.source_key_column, fresh.key_translation
            p.resolved_by_applier = True
            participations.append(p)
        targets = [p.target_hub for p in participations if p.target_hub]
        if unresolved or len(set(targets)) != len(rel.participations) or len(targets) < 2:
            why = (
                f"unresolved participation(s) {', '.join(unresolved)}" if unresolved
                else "two participations resolve to the same hub"
            )
            state.flag(
                "link_proposer",
                f"ratified relationship link for {rel.source_table} not built: {why} — a "
                f"link with a missing or merged participation has a different grain",
                kind=FlagKind.LINK_RELATIONSHIP_INCOMPLETE,
                asset=f"{rel.source_table}.*",
            )
            continue
        grain = frozenset(targets)
        if grain in grains:
            logger.info("relationship link for %s already built", rel.source_table)
            continue
        for p in participations:
            if p.key_translation is not None:
                state.flag(
                    "link_proposer",
                    f"link for {rel.source_table} requires surrogate→natural-key translation "
                    f"through {p.key_translation.through_table} for {p.target_hub}; review the "
                    f"translation model",
                    kind=FlagKind.LINK_TRANSLATION,
                    asset=f"{rel.source_table}.{p.referencing_column}",
                )
        delta.links.append(
            Link(
                name=_relationship_link_name(rel.source_table),
                connected_hubs=[
                    LinkHubRef(
                        hub=p.target_hub or "",
                        source_key_column=p.source_key_column,
                        key_translation=p.key_translation,
                    )
                    for p in participations
                ],
                description=(
                    f"Relationship table {rel.source_table}: its declared foreign keys "
                    f"relate {', '.join(targets)}; ratified from the source catalogue (WP37)."
                ),
            )
        )
        grains.add(grain)
        added += 1
    return delta


def apply_key_licenses(
    delta: DVModel, existing: DVModel, state: VaultAgentState
) -> DVModel:
    """WP40: repair the staging of constructs the modeler built from a licensed table.

    Grants come from ratified key licenses — resolved here against the merged model, every
    attempt — and from ratified WP34/WP36 link proposals that carry an alias or a translation
    (the modeler may have built their link itself, which made the link applier skip them as
    covered). A grant repairs, and never creates:

    1. a link whose staging reads the table — by construct name, or for a link proposal through
       the override the mapper applies — on its single unqualified participation of the hub,
       when that participation has neither alias nor translation and the table lacks the key;
    2. a satellite on the hub read from the table (translation only);
    3. a satellite on a link with that hub read from the table (translation only, per
       participation)."""
    licenses = state.link_proposals.ratified_licenses()
    link_grants = [
        p for p in state.link_proposals.ratified()
        if p.translation is not None or p.needs_alias
    ]
    if not licenses and not link_grants:
        return delta
    declared = {normalize_identifier(t.table): t for t in state.source_schemas}
    merged = DVModel(hubs=[*existing.hubs, *delta.hubs])
    hubs = {hub.name: hub for hub in merged.hubs}
    grants: list[tuple[str, Hub, KeyTranslation | None, str | None, bool]] = []
    for lic in licenses:
        lic.target_hub = lic.key_translation = lic.source_key_column = None
        lic.resolved_by_applier = False
        fk = ForeignKeyRef(
            columns=[lic.source_column],
            references_table=lic.references_table,
            references_columns=[lic.references_column],
            references_schema=lic.references_schema,
        )
        hub, translation, _, _ = resolve_fk_target(merged, fk, declared)
        if hub is None:
            continue
        alias = (
            lic.source_column
            if translation is None
            and normalize_identifier(lic.source_column)
            != normalize_identifier(canonical_hub_key_column(hub))
            else None
        )
        lic.target_hub, lic.key_translation, lic.source_key_column = hub.name, translation, alias
        lic.resolved_by_applier = True
        if translation is not None or alias is not None:
            grants.append((lic.source_table, hub, translation, alias, False))
    for proposal in link_grants:
        target = hubs.get(proposal.target_hub)
        if target is not None:
            grants.append((
                proposal.source_table, target, proposal.translation,
                proposal.source_column if proposal.needs_alias else None, True,
            ))

    links_by_name = {link.name: link for link in [*existing.links, *delta.links]}
    for table, hub, translation, alias, by_override in grants:
        relation = declared.get(normalize_identifier(table))
        present = (
            {normalize_identifier(c) for c in relation.column_names}
            if relation is not None else None
        )
        key = normalize_identifier(canonical_hub_key_column(hub))
        if present is not None and key in present:
            continue  # the table carries the hub's key itself: nothing to repair
        for link in delta.links:
            reads = construct_binds_to_source_table(link.name, table) or (
                by_override and any(
                    ref.hub != hub.name and ref.hub in hubs
                    and hub_binds_to_source_table(hubs[ref.hub], table)
                    for ref in link.hub_refs
                )
            )
            refs = [ref for ref in link.hub_refs if ref.hub == hub.name]
            if not reads or len(refs) != 1 or refs[0].role is not None:
                continue
            ref = refs[0]
            if ref.key_translation is not None or ref.source_key_column is not None:
                continue
            if translation is not None:
                ref.key_translation = translation
                state.flag(
                    "link_proposer",
                    f"link {link.name}, built by the modeler from {table}, requires "
                    f"surrogate→natural-key translation through {translation.through_table} for "
                    f"{hub.name} ({translation.referencing_column} → "
                    f"{translation.natural_key_column}); repaired under a ratified key; review "
                    f"the translation model",
                    kind=FlagKind.LINK_TRANSLATION,
                    asset=f"{table}.{translation.referencing_column}",
                )
            else:
                ref.source_key_column = alias
                logger.info("link %s: %s aliased to %s's key under a ratified key",
                            link.name, alias, hub.name)
        if translation is None:
            continue
        for sat in delta.satellites:
            if (
                not sat.source_table or sat.sat_type == "effectivity"
                or normalize_identifier(sat.source_table) != normalize_identifier(table)
            ):
                continue
            if sat.parent == hub.name:
                if sat.key_translation is not None:
                    continue
                sat.key_translation = translation
            else:
                parent = links_by_name.get(sat.parent)
                if parent is None:
                    continue
                refs = [ref for ref in parent.hub_refs if ref.hub == hub.name]
                if len(refs) != 1 or refs[0].role is not None:
                    continue
                if hub.name in sat.participation_translations:
                    continue
                sat.participation_translations[hub.name] = translation
            state.flag(
                "link_proposer",
                f"satellite {sat.name} reads {table}, which carries "
                f"{translation.referencing_column} but not {hub.name}'s key "
                f"{translation.natural_key_column}: joined in through "
                f"{translation.through_table} under a ratified key; review the translation model",
                kind=FlagKind.SAT_TRANSLATION,
                asset=sat.name,
            )
    return delta


def _relationship_link_name(table: str) -> str:
    """``ProductVendor`` -> ``link_product_vendor``: the relationship table names its link."""
    return "link_" + construct_base_from_table(table)


def link_source_overrides(state: VaultAgentState) -> dict[str, str]:
    """Staging bindings an FK-derived link already knows (§3.5).

    A link's staging relation is otherwise INFERRED as ``raw_<base>`` and flagged, because no
    declared table is named like a link. The proposal knows it: the referencing table. Keyed
    the way ``source_mapper.source_overrides`` keys its own entries, so the existing
    ``bind_sources`` override path consumes them unchanged and raises no flag."""
    overrides: dict[str, str] = {}
    for rel in state.link_proposals.ratified_relationships():
        name = _relationship_link_name(rel.source_table)
        if any(link.name == name for link in state.dv_model.links):
            overrides[normalize_identifier(construct_base_name(name))] = rel.source_table
    for proposal in state.link_proposals.ratified():
        for link in state.dv_model.links:
            if any(
                hub_binds_to_source_table(hub, proposal.source_table)
                for ref in link.hub_refs
                for hub in state.dv_model.hubs
                if hub.name == ref.hub
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
