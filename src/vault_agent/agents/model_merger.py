"""Deterministic merge of an extension delta into an existing vault (WP23 §2.4).

Brownfield mode's modeler emits only a DELTA against the vault named by ``--existing``
(charter Q1): new constructs, plus an existing hub re-stated by name carrying additional
``sources`` entries (the S1 "a second system now feeds this hub" case). This module folds
that delta onto the existing model and produces the model everything downstream sees —
code generation, validation, mapping, the ADR.

Three properties the rest of the WP rests on, so they are stated here rather than implied:

* **The existing model is never mutated.** It stays the comparison baseline the
  ``E_EXISTING_*`` gates and the diff artifact measure against, so the merge returns a new
  ``DVModel`` and deep-copies anything it carries over.
* **Merging is additive only.** A delta that re-states an existing link or satellite, or an
  existing hub with a different business key, is not a merge case — it is a migration, which
  this track never performs (charter §2). Such a delta is flagged
  ``FlagKind.EXTENSION_CONFLICT`` (error) and the conflicting part is DROPPED, so the merged
  model still satisfies the additivity gates and the human sees exactly one story: the flag.
* **Order is deterministic.** Existing constructs keep their order; new ones append in delta
  order. That is what lets an unchanged construct render byte-identically, which is what
  makes "regenerate the whole project" data-safe (charter §3.2).

No LLM, no state mutation beyond the flags it raises.
"""
import logging

from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import DVModel, FlagKind, Hub, HubSource, Link, Satellite, VaultAgentState

logger = logging.getLogger(__name__)

_AGENT = "model_merger"


def merge_models(existing: DVModel, delta: DVModel, state: VaultAgentState) -> DVModel:
    """Fold ``delta`` onto ``existing`` additively; return the merged model.

    Flags (never raises) on anything the delta asks for that is not an extension."""
    merged = DVModel(
        hubs=[hub.model_copy(deep=True) for hub in existing.hubs],
        links=[link.model_copy(deep=True) for link in existing.links],
        satellites=[sat.model_copy(deep=True) for sat in existing.satellites],
    )
    hub_index = {hub.name: hub for hub in merged.hubs}

    for hub in delta.hubs:
        prior = hub_index.get(hub.name)
        if prior is None:
            merged.hubs.append(hub.model_copy(deep=True))
            hub_index[hub.name] = merged.hubs[-1]
            continue
        _extend_hub(prior, hub, state)

    for link in delta.links:
        _append_or_conflict(merged.links, link, state, kind="link")

    for sat in delta.satellites:
        _append_or_conflict(merged.satellites, sat, state, kind="satellite")

    logger.info(
        "merged extension delta: %d hub(s), %d link(s), %d satellite(s) total",
        len(merged.hubs), len(merged.links), len(merged.satellites),
    )
    return merged


def _extend_hub(prior: Hub, delta_hub: Hub, state: VaultAgentState) -> None:
    """Apply the ONE legal hub extension — additional source feeds — in place on ``prior``.

    Any other difference is a migration the agent does not perform: the business key and
    source entity of an existing hub are its identity, and changing either would re-hash
    every row downstream. Flagged and ignored, so the merged model keeps the existing hub
    exactly as it was and ``E_EXISTING_BK_CHANGED`` has nothing to fire on."""
    if normalize_identifier(delta_hub.business_key) != normalize_identifier(prior.business_key):
        state.flag(
            _AGENT,
            f"the delta re-states existing hub {prior.name!r} with business key "
            f"{delta_hub.business_key!r} instead of {prior.business_key!r}; an existing hub's "
            f"key is immutable (changing it re-hashes every row), so the existing key is "
            f"kept and this change is flagged for human review, never applied",
            severity="error",
            kind=FlagKind.EXTENSION_CONFLICT,
            asset=prior.name,
        )
    if normalize_identifier(delta_hub.source_entity) != normalize_identifier(
        prior.source_entity
    ):
        state.flag(
            _AGENT,
            f"the delta re-states existing hub {prior.name!r} with source entity "
            f"{delta_hub.source_entity!r} instead of {prior.source_entity!r}; kept as it was",
            severity="error",
            kind=FlagKind.EXTENSION_CONFLICT,
            asset=prior.name,
        )

    # New feeds are the point of the S1 scenario. Dedup per E_HUB_DUP_FEED semantics: a feed
    # already present (same normalised table+column) is not an addition, it is the delta
    # restating context.
    known = {_feed_key(source) for source in prior.sources}
    if not prior.sources and delta_hub.sources:
        # The existing hub was single-source and is becoming multi-source. Its original feed
        # is implicit (Hub.sources empty = "one source, named by the staging binding"), so it
        # has to be materialised or the merge would silently drop the legacy feed. The
        # grandfathering rules (§2.6) recognise it as legacy by its presence in the existing
        # model, and rules.canonical_hub_key_column then sees both feeds.
        legacy = HubSource(
            source_table=prior.source_entity, business_key_column=prior.business_key
        )
        prior.sources.append(legacy)
        known.add(_feed_key(legacy))

    for source in delta_hub.sources:
        if _feed_key(source) in known:
            continue
        prior.sources.append(source.model_copy(deep=True))
        known.add(_feed_key(source))


def _append_or_conflict[C: (Link, Satellite)](
    target: list[C], construct: C, state: VaultAgentState, *, kind: str
) -> None:
    """Append a net-new link/satellite, or flag a re-statement of an existing one.

    Links and satellites are never extended in place (charter §2 / spec §2.4): a link's grain
    and a satellite's payload shape are its identity, and re-shaping either is a migration.
    Additional attributes for an existing concern belong in a NEW satellite on the same
    parent (charter Q3) — that is what the modeler is steered to emit."""
    if any(existing.name == construct.name for existing in target):
        state.flag(
            _AGENT,
            f"the delta re-states existing {kind} {construct.name!r}; {kind}s are never "
            f"extended in place — additional attributes belong in a NEW satellite on the "
            f"same parent. The existing {kind} is kept unchanged and this is flagged for "
            f"human review",
            severity="error",
            kind=FlagKind.EXTENSION_CONFLICT,
            asset=construct.name,
        )
        return
    target.append(construct.model_copy(deep=True))


def _feed_key(source: HubSource) -> tuple[str, str]:
    return (
        normalize_identifier(source.source_table),
        normalize_identifier(source.business_key_column),
    )
