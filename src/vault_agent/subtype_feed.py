"""Translated subtype feeds (WP38): a table keyed on a surrogate feeds satellites on the hub
keyed on the natural key.

`SalesPerson`'s key `BusinessEntityID` is a declared foreign key to `Employee`; the vault keys
`hub_employee` on `NationalIDNumber`. The entity resolver says the sales representative is
the same thing as `hub_employee` but keyed differently, a human ratifies it, and until WP38 the
WP29 prompt section then told the modeler to "model it as its OWN hub" — `hub_sales_representative`,
in every AdventureWorks chain since 2026-08-09. In DV2.0 a role of an employee is satellites on
`hub_employee`. That was unbuildable because a satellite attaches through its parent's key
column, which `SalesPerson` does not carry; WP36 had built the bridge — a join through the
referenced relation — for links only.

**Deterministic, on declared evidence only.** A ratified same-as `concept → hub_X` is a subtype
feed when exactly one declared table `T` carries a single-column foreign key on the concept's
field into a table `hub_X` binds, `T` does not itself carry `hub_X`'s key, and the WP36 rule
(`link_proposal._translation_target`) yields the translation. One rule for links and
satellites, never two. A same-as without that declaration keeps its own hub: a join nobody
declared is a guess.

**Not here:** a table that references `T` (`SalesPersonQuotaHistory → SalesPerson`) needs two
hops and is not joined this way (spec §6).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from vault_agent.link_proposal import _translation_target
from vault_agent.rules.dv2_rules import (
    canonical_hub_key_column,
    hub_binds_to_source_table,
    normalize_identifier,
)
from vault_agent.state import (
    RESOLUTION_SAME_AS,
    DVModel,
    EntityResolution,
    FlagKind,
    KeyTranslation,
    ResolutionProposal,
    SourceTable,
    VaultAgentState,
    split_concept_key,
)

logger = logging.getLogger(__name__)

_RATIFIED = ("accepted", "overridden")


@dataclass(frozen=True)
class SubtypeFeed:
    """A ratified same-as that is a subtype table feeding satellites on an existing hub."""

    concept: str
    hub: str
    table: str
    translation: KeyTranslation


def subtype_feed(
    proposal: ResolutionProposal, model: DVModel, source_schemas: list[SourceTable]
) -> SubtypeFeed | None:
    """The subtype feed a same-as proposal describes, or ``None`` — never a guess.

    Ratification is the caller's question (:func:`ratified_subtype_feeds`); this answers only
    whether the declared schema makes the proposal a translatable subtype of ``model``'s hub."""
    if proposal.resolution != RESOLUTION_SAME_AS or not proposal.same_as:
        return None
    hub = next((h for h in model.hubs if h.name == proposal.same_as), None)
    if hub is None:
        return None
    label, _ = split_concept_key(proposal.concept)
    field = normalize_identifier(label)
    candidates = [
        (table, fk)
        for table in source_schemas
        for fk in table.foreign_keys
        if fk.is_single_column
        and normalize_identifier(fk.columns[0]) == field
        and normalize_identifier(table.table) != normalize_identifier(fk.references_table)
        and hub_binds_to_source_table(hub, fk.references_table)
    ]
    if len({normalize_identifier(table.table) for table, _ in candidates}) != 1:
        return None  # none declared, or several tables: which one is the subtype is not ours
    table, fk = candidates[0]
    natural = normalize_identifier(canonical_hub_key_column(hub))
    if natural in {normalize_identifier(c) for c in table.column_names}:
        return None  # the key is there: an ordinary feed, no translation involved
    declared = {normalize_identifier(t.table): t for t in source_schemas}
    target, translation, _, _ = _translation_target(model, fk, declared)
    if target is None or translation is None or target.name != hub.name:
        return None
    return SubtypeFeed(
        concept=proposal.concept, hub=hub.name, table=table.table, translation=translation
    )


def ratified_subtype_feeds(
    resolutions: EntityResolution, model: DVModel, source_schemas: list[SourceTable]
) -> list[SubtypeFeed]:
    """Every RATIFIED same-as that is a subtype feed — the only ones that may act."""
    feeds = []
    for proposal in resolutions.proposals:
        if proposal.ratification_status not in _RATIFIED:
            continue
        feed = subtype_feed(proposal, model, source_schemas)
        if feed is not None:
            feeds.append(feed)
    return feeds


def apply_subtype_feeds(
    delta: DVModel, existing: DVModel | None, state: VaultAgentState
) -> DVModel:
    """Set the translation on every delta satellite a ratified subtype feed describes.

    A satellite qualifies when its parent is the feed's hub and its ``source_table`` is the
    subtype table (effectivity satellites never: their dates live in a link's relation).
    Applied to the delta before the merge, like the link applier, so the satellite reaches every
    gate on the ordinary path. Recomputed on every modelling attempt — nothing an earlier
    attempt decided survives (the lesson of 2026-09-13's sticky participation)."""
    if existing is None or not state.source_schemas:
        return delta
    model = DVModel(hubs=[*existing.hubs, *delta.hubs])
    feeds = ratified_subtype_feeds(state.resolutions, model, state.source_schemas)
    applied = 0
    for feed in feeds:
        t = feed.translation
        for sat in delta.satellites:
            if (
                sat.parent != feed.hub
                or sat.sat_type == "effectivity"
                or not sat.source_table
                or normalize_identifier(sat.source_table) != normalize_identifier(feed.table)
            ):
                continue
            sat.key_translation = t
            applied += 1
            state.flag(
                "subtype_feed",
                f"satellite {sat.name} on {feed.hub} reads {feed.table}, a subtype keyed on "
                f"{t.referencing_column}: {feed.hub}'s key {t.natural_key_column} is joined in "
                f"through {t.through_table} ({t.referencing_column} → {t.surrogate_column}); "
                f"review the translation model",
                kind=FlagKind.SAT_TRANSLATION,
                asset=sat.name,
            )
    if applied:
        logger.info("subtype feeds: %d satellite translation(s) applied", applied)
    return delta
