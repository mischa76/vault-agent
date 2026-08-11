"""Validator agent.

Deterministically checks the logical Data Vault model in ``VaultAgentState.dv_model`` (and,
if the code generator has already run, the generated artifacts) against the DV2.0 rules in
``vault_agent.rules.dv2_rules``. No LLM is involved, so validation is reproducible and runs
in CI without an API key. It is an independent gate: it re-checks structural invariants the
modeler and generator already enforce, giving defense in depth across agents.

Results land in ``VaultAgentState.validation_report`` as a list of typed
:class:`~vault_agent.state.ValidationIssue` records (``severity`` / ``code`` /
``construct`` / ``message``); ``passed`` is true when there are no error-severity issues.

The gates cover structural invariants (names — uniqueness and well-formedness
(``E_BAD_NAME``, WP20) — keys, parents, required columns), grain and
attribute overlap across constructs (matched on the *normalised* attribute, so two casing
variants of one column across two satellites of a parent are the same duplicate),
satellite-internal duplicate attributes
(``E_SAT_DUP_ATTR``), effectivity-satellite date count and (start, end) order
(``E_EFFSAT_DATE_ORDER`` / ``W_EFFSAT_DATE_ORDER_UNVERIFIED``), hub hash-key/staging
collisions on a shared source entity (``E_HUB_HK_COLLISION``), duplicate hubs over the same
business key and source (``E_DUP_HUB``), role-qualified link participations
(``E_LINK_DUP_ROLE`` and the grounded ``W_ROLE_BK_NOT_IN_SOURCE``, ADR-0009/WP8), and
optional source-schema grounding. For the gate count, count the ``E_``/``W_`` codes in this
module: the code is the source of truth, and a literal here only ever goes stale (it said
"30 as of WP8" while the module had 32).
"""
import logging
from typing import Any

from vault_agent.agents.base import BaseAgent
from vault_agent.grounding import is_grounded, known_columns
from vault_agent.rules.dv2_rules import (
    CONSTRUCT_NAME_PATTERN,
    REQUIRED_HUB_COLUMNS,
    REQUIRED_LINK_COLUMNS,
    REQUIRED_SAT_COLUMNS,
    SAT_WIDE_ATTRIBUTE_THRESHOLD,
    construct_binds_to_source_table,
    effectivity_date_pair,
    is_valid_construct_name,
    normalize_identifier,
    role_bk_column,
    satellite_payload_relations,
    source_table_on_multi_source_hub,
)
from vault_agent.state import (
    Hub,
    IssueSeverity,
    Link,
    ValidationIssue,
    ValidationReport,
    VaultAgentState,
)

logger = logging.getLogger(__name__)

# Maps the logical DV column names in the rules to the AutomateDV metadata keys the code
# generator emits, so the required-column rules can be checked against the artifacts.
_LOGICAL_TO_META = {
    "hash_key": "src_pk",
    "business_key": "src_nk",
    "load_date_time": "src_ldts",
    "record_source": "src_source",
    "hash_diff": "src_hashdiff",
}
_REQUIRED_COLUMNS = {
    ("hubs", "hub"): REQUIRED_HUB_COLUMNS,
    ("links", "link"): REQUIRED_LINK_COLUMNS,
    ("satellites", "satellite"): REQUIRED_SAT_COLUMNS,
}


def _link_grain(link: Link) -> tuple[tuple[str, str], ...]:
    """A link's grain: the sorted multiset of (hub, role) participations (ADR-0009).

    The same shape ``W_LINK_REDUNDANT_GRAIN`` groups on — a role-qualified self-reference is
    a different grain from a plain link over the same hub. Used by ``E_EXISTING_GRAIN_CHANGED``
    (WP23) to decide whether an existing link still hashes the same way."""
    return tuple(sorted((ref.hub, ref.role or "") for ref in link.hub_refs))


def _shares_payload_namespace(
    owners: set[str], relations: dict[str, frozenset[str]]
) -> bool:
    """Do any two of these satellites draw payload from the same relation? (ADR-0012)

    The severity switch for ``E_SAT_ATTR_OVERLAP``: intersecting relation sets mean one
    relation's column would be historised twice, which is the error the gate exists for;
    disjoint sets mean same-named columns of different relations, which only warns.

    An EMPTY set means "unknown" (an unresolvable parent) and is treated as sharing with
    everything — an unknown relation must never *lower* a severity. Without that, an empty set
    would intersect nothing and quietly downgrade the gate."""
    seen: set[str] = set()
    for name in sorted(owners):
        own = relations.get(name) or frozenset()
        if not own:
            return True
        if own & seen:
            return True
        seen |= own
    return False


def _issue(
    severity: IssueSeverity, code: str, construct: str, message: str
) -> ValidationIssue:
    return ValidationIssue(severity=severity, code=code, construct=construct, message=message)


class ValidatorAgent(BaseAgent):
    """Validates the Data Vault model and generated artifacts against DV2.0 rules."""

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        model = state.dv_model
        logger.info(
            "validating model: %d hub(s), %d link(s), %d satellite(s)",
            len(model.hubs),
            len(model.links),
            len(model.satellites),
        )
        issues: list[ValidationIssue] = []

        hub_names = {hub.name for hub in model.hubs}
        link_names = {link.name for link in model.links}
        links_by_name = {link.name: link for link in model.links}

        if not model.hubs:
            issues.append(
                _issue("error", "E_NO_HUBS", "dv_model", "model has no hubs; nothing to validate")
            )

        all_names = (
            [hub.name for hub in model.hubs]
            + [link.name for link in model.links]
            + [sat.name for sat in model.satellites]
        )
        for name in sorted({n for n in all_names if all_names.count(n) > 1}):
            issues.append(
                _issue("error", "E_DUP_NAME", name, f"construct name {name!r} is not unique")
            )

        # E_BAD_NAME: a construct name becomes a dbt model name AND a file on disk, so it must
        # be well-formed before anything is generated (the re-model loop gets the feedback,
        # mirroring how E_SAT_DUP_ATTR pre-empts the build error). write_outputs re-checks the
        # filename components as defense in depth; this gate is what keeps that unreachable.
        for name in all_names:
            if is_valid_construct_name(name):
                continue
            offending = sorted({c for c in name if not (c.islower() or c.isdigit() or c == "_")})
            rendered = ", ".join(repr(c) for c in offending) if offending else "the name shape"
            issues.append(
                _issue(
                    "error", "E_BAD_NAME", name,
                    f"construct name {name!r} is not well-formed ({rendered}); expected "
                    f"hub_/link_/sat_ followed by lowercase snake_case, i.e. "
                    f"{CONSTRUCT_NAME_PATTERN}",
                )
            )

        for hub in model.hubs:
            if not hub.business_key.strip():
                issues.append(
                    _issue("error", "E_HUB_NO_BK", hub.name, "hub has no business key")
                )
            if not any(sat.parent == hub.name for sat in model.satellites):
                issues.append(
                    _issue(
                        "warning", "W_HUB_NO_SAT", hub.name,
                        "hub has no satellite; no descriptive data is captured for it",
                    )
                )

        for link in model.links:
            if len(link.connected_hubs) < 2:
                issues.append(
                    _issue(
                        "error", "E_LINK_TOO_FEW_HUBS", link.name,
                        f"link connects {len(link.connected_hubs)} hub(s); needs >= 2",
                    )
                )
            unknown = sorted({ref.hub for ref in link.hub_refs if ref.hub not in hub_names})
            if unknown:
                issues.append(
                    _issue(
                        "error", "E_LINK_UNKNOWN_HUB", link.name,
                        f"link references unknown hubs: {unknown}",
                    )
                )
            # E_LINK_DUP_ROLE: two participations with the same (hub, role) are the exact
            # duplicate roles exist to disambiguate (ADR-0009) — one hub twice with no role,
            # or twice under the same role, would collapse to one FK column. Role-qualify
            # (or drop) the repeat.
            seen_refs: set[tuple[str, str | None]] = set()
            for ref in link.hub_refs:
                key = (ref.hub, ref.role)
                if key in seen_refs:
                    label = ref.hub if ref.role is None else f"{ref.hub} (role {ref.role})"
                    issues.append(
                        _issue(
                            "error", "E_LINK_DUP_ROLE", link.name,
                            f"hub participation {label} appears twice with the same role; "
                            f"qualify each repeated participation with a distinct role",
                        )
                    )
                seen_refs.add(key)
            # A declared driving key must name connected participations (by hub, or
            # "hub:role" for a role-qualified one — ADR-0009).
            connected_keys = {(ref.hub, ref.role) for ref in link.hub_refs}
            outside = []
            for entry in link.driving_key:
                dk_hub, sep, dk_role = entry.partition(":")
                if (dk_hub, dk_role if sep else None) not in connected_keys:
                    outside.append(entry)
            if outside:
                issues.append(
                    _issue(
                        "error", "E_DRIVING_KEY_NOT_IN_LINK", link.name,
                        f"driving key is not a subset of connected participations: {outside}",
                    )
                )
            # Mirror the generator gate: a transactional (non-historized) link needs an
            # event timestamp to drive automate_dv.t_link's src_eff.
            if link.link_type == "transactional" and not (link.event_timestamp or "").strip():
                issues.append(
                    _issue(
                        "error", "E_TXNLINK_NO_TIMESTAMP", link.name,
                        "transactional link has no event_timestamp",
                    )
                )

        valid_parents = hub_names | link_names
        for sat in model.satellites:
            if sat.parent not in valid_parents:
                issues.append(
                    _issue(
                        "error", "E_SAT_UNKNOWN_PARENT", sat.name,
                        f"satellite parent {sat.parent!r} is not a known hub or link",
                    )
                )
            if not sat.attributes:
                issues.append(
                    _issue(
                        "error", "E_SAT_NO_PAYLOAD", sat.name,
                        "satellite has no attributes (empty payload)",
                    )
                )
            # A very wide satellite is a smell (mixed rates of change / sources / PII) — flag
            # for human review, never fail. Effectivity sats carry two dates and never trip it.
            if len(sat.attributes) > SAT_WIDE_ATTRIBUTE_THRESHOLD:
                issues.append(
                    _issue(
                        "warning", "W_SAT_WIDE", sat.name,
                        f"satellite has {len(sat.attributes)} attributes "
                        f"(> {SAT_WIDE_ATTRIBUTE_THRESHOLD}); consider splitting by rate of "
                        f"change, source, or data classification",
                    )
                )
            # E_SAT_DUP_ATTR: two attributes (or an attribute and a child-dependent-key
            # label) that normalise to the same identifier become a duplicate staging/payload
            # column — the generated SQL cannot build. Attributes and child_dependent_key are
            # one namespace: both end up as columns of the same satellite. Covers exact
            # duplicates and lossy-normalisation ones ("customer-id" vs "customer id").
            by_column: dict[str, list[str]] = {}
            for label in sat.attributes + sat.child_dependent_key:
                by_column.setdefault(normalize_identifier(label), []).append(label)
            for column, labels in sorted(by_column.items()):
                if len(labels) > 1:
                    joined = ", ".join(repr(label) for label in labels)
                    issues.append(
                        _issue(
                            "error", "E_SAT_DUP_ATTR", sat.name,
                            f"attributes {joined} all map to the same column {column}; "
                            f"the generated satellite would carry a duplicate payload "
                            f"column and cannot build",
                        )
                    )
            # Mirror the generator gate: a multi-active satellite needs a child dependent
            # key to distinguish concurrently-active rows (automate_dv.ma_sat's src_cdk).
            if sat.sat_type == "multi_active" and not sat.child_dependent_key:
                issues.append(
                    _issue(
                        "error", "E_MASAT_NO_CDK", sat.name,
                        "multi-active satellite has no child_dependent_key",
                    )
                )
            # W_MASAT_SHARED_GRAIN (WP7 §7.1): multi-active rows usually live in their
            # own source relation at finer grain than the parent's; without a declared
            # source_table the satellite silently shares the parent's staging model,
            # which assumes equal grain. Warning, not error — the shared relation may
            # genuinely carry the multi-active rows.
            if sat.sat_type == "multi_active" and not sat.source_table:
                issues.append(
                    _issue(
                        "warning", "W_MASAT_SHARED_GRAIN", sat.name,
                        "multi-active rows usually come from their own source relation; "
                        "sharing the parent's staging assumes equal grain — declare "
                        "source_table or confirm the shared source",
                    )
                )
            # Heuristic: a *standard* satellite hanging off a link whose payload is a from/to
            # date pair is likely a mis-modelled effectivity satellite (it should be
            # sat_type=effectivity with the link's driving key, not a plain sat carrying the
            # dates). Warning, not error — a legitimate sat may carry two dates.
            if sat.sat_type == "standard" and sat.parent in link_names:
                date_pair = effectivity_date_pair(sat.attributes)
                if date_pair is not None:
                    from_attr, to_attr = date_pair
                    issues.append(
                        _issue(
                            "warning", "W_SAT_MAYBE_EFFECTIVITY", sat.name,
                            f"standard satellite on link {sat.parent!r} carries a from/to "
                            f"date pair ({from_attr!r}, {to_attr!r}); model it as an "
                            f"effectivity satellite (sat_type=effectivity) with the link's "
                            f"driving key?",
                        )
                    )
            # Mirror + extend the generator gates for effectivity satellites: parent must be
            # a link, exactly two ordered date attributes, and the link must declare a
            # driving key so relationships can be end-dated per driving key.
            if sat.sat_type == "effectivity":
                if len(sat.attributes) != 2:
                    issues.append(
                        _issue(
                            "error", "E_EFFSAT_DATES", sat.name,
                            "effectivity satellite must carry exactly two date attributes "
                            f"(start, end) in order; has {len(sat.attributes)}",
                        )
                    )
                else:
                    # The generator takes attributes[0] as the start and attributes[1] as
                    # the end date positionally — a reversed pair renders a silently
                    # inverted effectivity satellite. effectivity_date_pair() is the single
                    # source of truth for from/to token classification: a recognisably
                    # reversed pair is an error; unrecognisable tokens only warn (a
                    # heuristic non-match must never hard-fail a legitimate model, same
                    # reasoning as W_SAT_MAYBE_EFFECTIVITY).
                    start_attr, end_attr = sat.attributes[0], sat.attributes[1]
                    date_pair = effectivity_date_pair(sat.attributes)
                    if date_pair == (end_attr, start_attr):
                        issues.append(
                            _issue(
                                "error", "E_EFFSAT_DATE_ORDER", sat.name,
                                f"effectivity date attributes are reversed: "
                                f"{start_attr!r} is the end date and {end_attr!r} the "
                                f"start date; required order is (start, end), i.e. "
                                f"({end_attr!r}, {start_attr!r})",
                            )
                        )
                    elif date_pair is None:
                        issues.append(
                            _issue(
                                "warning", "W_EFFSAT_DATE_ORDER_UNVERIFIED", sat.name,
                                f"cannot verify that the effectivity date attributes "
                                f"({start_attr!r}, {end_attr!r}) are in (start, end) "
                                f"order; confirm {start_attr!r} is the start and "
                                f"{end_attr!r} the end of the active period",
                            )
                        )
                if sat.parent in link_names:
                    if not links_by_name[sat.parent].driving_key:
                        issues.append(
                            _issue(
                                "error", "E_EFFSAT_NO_DRIVING_KEY", sat.name,
                                f"parent link {sat.parent!r} declares no driving key",
                            )
                        )
                elif sat.parent in hub_names:
                    issues.append(
                        _issue(
                            "error", "E_EFFSAT_PARENT_NOT_LINK", sat.name,
                            f"effectivity satellite parent {sat.parent!r} is a hub, not a link",
                        )
                    )

        issues.extend(self._check_cross_construct(state))
        issues.extend(self._check_additive_extension(state))
        issues.extend(self._check_source_grounding(state))
        issues.extend(self._check_artifact_columns(state.artifacts.automatedv_yaml))

        errors = [issue for issue in issues if issue.severity == "error"]
        state.validation_report = ValidationReport(passed=not errors, issues=issues)
        logger.info(
            "validation %s: %d error(s), %d warning(s)",
            "failed" if errors else "passed",
            len(errors),
            len(issues) - len(errors),
        )
        state.decisions.append(
            {
                "agent": "validator",
                "passed": not errors,
                "errors": len(errors),
                "warnings": len(issues) - len(errors),
            }
        )
        return state

    @staticmethod
    def _check_cross_construct(state: VaultAgentState) -> list[ValidationIssue]:
        """Checks that span several constructs: grain, attribute overlap, key collision."""
        model = state.dv_model
        issues: list[ValidationIssue] = []

        # W_LINK_REDUNDANT_GRAIN: two links over the same hub set with the same type likely
        # model one Unit of Work twice (or are a grain error). Order-independent on hubs.
        grain_groups: dict[tuple[tuple[tuple[str, str | None], ...], str], list[str]] = {}
        for link in model.links:
            # Grain = the multiset of (hub, role) participations (ADR-0009): a
            # role-qualified self-referencing link has a different grain from a plain link
            # over the same hub, and must not be flagged as its redundant twin.
            grain = tuple(sorted((ref.hub, ref.role or "") for ref in link.hub_refs))
            key = (grain, link.link_type)
            grain_groups.setdefault(key, []).append(link.name)
        for _key, names in sorted(grain_groups.items()):
            if len(names) > 1:
                joined = ", ".join(sorted(names))
                issues.append(
                    _issue(
                        "warning", "W_LINK_REDUNDANT_GRAIN", joined,
                        f"links {joined} connect the same hubs with the same link_type; "
                        f"likely the same unit of work modeled twice or a grain error",
                    )
                )

        # E_SAT_ATTR_OVERLAP: an attribute must live in at most one satellite per parent —
        # but only within ONE payload namespace (ADR-0012). Keyed on the NORMALISED attribute
        # (WP20 §2.5), like the within-satellite E_SAT_DUP_ATTR: what would collide is the
        # generated column, so "Customer ID" in one satellite and "customer_id" in another is
        # the same duplicate. The original labels are reported — they are what a human has to
        # reconcile. Two satellites fed by DIFFERENT relations (WP7 source_table: Microsoft's
        # ProductCostHistory and ProductListPriceHistory both hang off Product) each project
        # their own same-named column from their own staging model; nothing collides, so that
        # is W_SAT_ATTR_OVERLAP_CROSS_SOURCE — reported, because two records of one measure at
        # different grain is still a smell a reviewer should see.
        parent_by_name: dict[str, Hub | Link] = {
            **{hub.name: hub for hub in model.hubs},
            **{link.name: link for link in model.links},
        }
        relations = {
            sat.name: satellite_payload_relations(sat, parent_by_name.get(sat.parent))
            for sat in model.satellites
        }
        attr_owners: dict[str, dict[str, dict[str, set[str]]]] = {}
        for sat in model.satellites:
            per_parent = attr_owners.setdefault(sat.parent, {})
            for attr in sat.attributes:
                per_parent.setdefault(normalize_identifier(attr), {}).setdefault(
                    attr, set()
                ).add(sat.name)
        for parent, attrs in sorted(attr_owners.items()):
            for _norm, labels in sorted(attrs.items()):
                owners = {name for names in labels.values() for name in names}
                if len(owners) > 1:
                    joined = ", ".join(sorted(owners))
                    rendered = " / ".join(repr(label) for label in sorted(labels))
                    if _shares_payload_namespace(owners, relations):
                        issues.append(
                            _issue(
                                "error", "E_SAT_ATTR_OVERLAP", parent,
                                f"attribute {rendered} appears in multiple satellites of "
                                f"{parent!r}: {joined}",
                            )
                        )
                    else:
                        named = ", ".join(
                            f"{name} <- {'/'.join(sorted(relations[name]))}"
                            for name in sorted(owners)
                        )
                        issues.append(
                            _issue(
                                "warning", "W_SAT_ATTR_OVERLAP_CROSS_SOURCE", parent,
                                f"attribute {rendered} appears in several satellites of "
                                f"{parent!r} fed by different source relations ({named}); "
                                f"same-named columns of different relations are different "
                                f"attributes, but check they are not one measure historised "
                                f"twice",
                            )
                        )

        # W_BK_COLLISION_RISK: the same business-key field used by hubs over different source
        # entities may denote different real-world objects (may need a collision code).
        bk_sources: dict[str, set[str]] = {}
        bk_hub_names: dict[str, list[str]] = {}
        for hub in model.hubs:
            bk_sources.setdefault(hub.business_key, set()).add(hub.source_entity)
            bk_hub_names.setdefault(hub.business_key, []).append(hub.name)
        for business_key, sources in sorted(bk_sources.items()):
            if business_key.strip() and len(sources) > 1:
                joined = ", ".join(sorted(bk_hub_names[business_key]))
                issues.append(
                    _issue(
                        "warning", "W_BK_COLLISION_RISK", joined,
                        f"hubs {joined} share business key {business_key!r} across different "
                        f"source entities {sorted(sources)}; confirm whether a collision "
                        f"code is needed",
                    )
                )

        # E_HUB_HK_COLLISION: the hub hash key and staging model derive from source_entity
        # (normalize(source_entity) + "_HK"), so hubs sharing a source entity but keyed
        # differently collide on the same X_HK column and staging model — the staging
        # generator's per-name dedup then silently binds one hub's HK to the other's
        # business key. Groups whose members all share one normalised business key are the
        # same-concept case and belong to E_DUP_HUB instead (gate 3/4 interplay).
        hubs_by_source: dict[str, list[Hub]] = {}
        for hub in model.hubs:
            hubs_by_source.setdefault(normalize_identifier(hub.source_entity), []).append(hub)
        for source_norm, hubs in sorted(hubs_by_source.items()):
            if len(hubs) < 2:
                continue
            bks = {normalize_identifier(hub.business_key) for hub in hubs}
            if len(bks) > 1:
                joined = ", ".join(sorted(hub.name for hub in hubs))
                issues.append(
                    _issue(
                        "error", "E_HUB_HK_COLLISION", joined,
                        f"hubs {joined} share source entity "
                        f"{hubs[0].source_entity!r} but have different business keys; "
                        f"they would derive the same {source_norm}_HK hash-key column "
                        f"and staging model, silently binding one hub's hash key to "
                        f"the other's business key",
                    )
                )

        # E_DUP_HUB: the same business key on the same source entity modelled as >= 2 hubs
        # is the same business concept twice ("one hub per business key",
        # DV_MODELING_RULES[0]). Complements W_BK_COLLISION_RISK, which covers the same BK
        # across *different* source entities. Empty BKs are already E_HUB_NO_BK.
        hubs_by_concept: dict[tuple[str, str], list[str]] = {}
        for hub in model.hubs:
            if not hub.business_key.strip():
                continue
            concept = (
                normalize_identifier(hub.business_key),
                normalize_identifier(hub.source_entity),
            )
            hubs_by_concept.setdefault(concept, []).append(hub.name)
        for (bk_norm, _source_norm), names in sorted(hubs_by_concept.items()):
            if len(names) > 1:
                joined = ", ".join(sorted(names))
                issues.append(
                    _issue(
                        "error", "E_DUP_HUB", joined,
                        f"hubs {joined} model the same business concept (business key "
                        f"{bk_norm} on the same source entity) more than once; create "
                        f"exactly one hub per business key",
                    )
                )

        # E_HUB_DUP_FEED (WP10): a multi-source hub must not name the same (table, column)
        # feed twice — a copy-paste / ratification slip, not two distinct sources.
        for hub in model.hubs:
            seen: set[tuple[str, str]] = set()
            for source in hub.sources:
                feed = (
                    normalize_identifier(source.source_table),
                    normalize_identifier(source.business_key_column),
                )
                if feed in seen:
                    issues.append(
                        _issue(
                            "error", "E_HUB_DUP_FEED", hub.name,
                            f"hub {hub.name!r} declares the source feed "
                            f"{source.source_table}.{source.business_key_column} more than "
                            f"once; each HubSource must be a distinct (table, column)",
                        )
                    )
                seen.add(feed)

        # E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB — NARROWED by ADR-0011. A satellite whose
        # source_table NAMES one of the hub's feeds is now the canonical one-per-source shape
        # and is generated; only a table that is not a feed at all remains an error, because a
        # finer-grain relation under one feed cannot say which feed it belongs to. Gating here
        # tells the human before generation and feeds the re-model loop (the E_SAT_DUP_ATTR
        # pattern). The condition lives in rules/ so all three sites agree on what is skipped.
        hub_by_name = {hub.name: hub for hub in model.hubs}
        for sat in model.satellites:
            parent_hub = hub_by_name.get(sat.parent)
            if source_table_on_multi_source_hub(sat, parent_hub):
                assert parent_hub is not None  # implied by the predicate
                feeds = ", ".join(source.source_table for source in parent_hub.sources)
                issues.append(
                    _issue(
                        "error", "E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB", sat.name,
                        f"satellite {sat.name!r} declares source_table "
                        f"{sat.source_table!r}, which is not one of the feeds of its "
                        f"multi-source parent {sat.parent!r}. Available feeds: {feeds}. Name "
                        f"one of them to bind this satellite to that source system, or drop "
                        f"source_table so it splits across all feeds. A finer-grain relation "
                        f"under a single feed is not expressible today (ADR-0011)",
                    )
                )

        return issues

    @staticmethod
    def _check_additive_extension(state: VaultAgentState) -> list[ValidationIssue]:
        """Additivity gates for brownfield mode (WP23 §2.5, charter §3.3).

        Inert unless ``state.existing_model`` is set, so greenfield output is unchanged.
        These compare the MERGED model back to the vault it extends and enforce the one
        promise the whole track makes: an extension run never changes what already exists.

        They are invariants over the merger's output, not a check on the LLM — the merger
        already refuses non-additive deltas. That is the point: these are the guarantee, the
        steering is only the shortcut. A merger bug, or any future re-model mode, hits them
        instead of silently reshaping a live vault.

        On growth vs shrink (charter Q3): BOTH count as a reshape of an existing satellite.
        Adding an attribute to a satellite that already has history means backfilling a
        column for every past row — a migration, not an extension. New attributes belong in
        a NEW satellite on the same parent, which is what the modeler is steered to emit."""
        prior = state.existing_model
        if prior is None:
            return []
        issues: list[ValidationIssue] = []
        merged = state.dv_model

        hubs = {hub.name: hub for hub in merged.hubs}
        links = {link.name: link for link in merged.links}
        sats = {sat.name: sat for sat in merged.satellites}

        for construct_name, kind in [
            *[(hub.name, "hub") for hub in prior.hubs],
            *[(link.name, "link") for link in prior.links],
            *[(sat.name, "satellite") for sat in prior.satellites],
        ]:
            if construct_name not in {**hubs, **links, **sats}:
                issues.append(
                    _issue(
                        "error", "E_EXISTING_REMOVED", construct_name,
                        f"existing {kind} {construct_name!r} is absent from the extended "
                        f"model; an extension run must never drop what the vault already "
                        f"contains",
                    )
                )

        for hub in prior.hubs:
            current = hubs.get(hub.name)
            if current is None:
                continue  # already reported as removed
            if normalize_identifier(current.business_key) != normalize_identifier(
                hub.business_key
            ) or normalize_identifier(current.source_entity) != normalize_identifier(
                hub.source_entity
            ):
                issues.append(
                    _issue(
                        "error", "E_EXISTING_BK_CHANGED", hub.name,
                        f"existing hub {hub.name!r} changed identity: business key "
                        f"{hub.business_key!r}/{hub.source_entity!r} became "
                        f"{current.business_key!r}/{current.source_entity!r}. The key is what "
                        f"every stored hash was derived from — changing it is a migration",
                    )
                )
            gained = len(current.sources) - len(hub.sources)
            if gained > 0:
                issues.append(
                    _issue(
                        "warning", "W_EXISTING_EXTENDED", hub.name,
                        f"existing hub {hub.name!r} gained {gained} source feed(s): "
                        f"{', '.join(s.source_table for s in current.sources[len(hub.sources):])}",
                    )
                )

        for link in prior.links:
            current_link = links.get(link.name)
            if current_link is None:
                continue
            if _link_grain(current_link) != _link_grain(link) or set(
                current_link.driving_key
            ) != set(link.driving_key):
                issues.append(
                    _issue(
                        "error", "E_EXISTING_GRAIN_CHANGED", link.name,
                        f"existing link {link.name!r} changed grain or driving key; its "
                        f"participations define the hash key of every stored row",
                    )
                )

        for sat in prior.satellites:
            current_sat = sats.get(sat.name)
            if current_sat is None:
                continue
            reshaped = (
                current_sat.parent != sat.parent
                or current_sat.sat_type != sat.sat_type
                or current_sat.source_table != sat.source_table
                or {normalize_identifier(a) for a in current_sat.child_dependent_key}
                != {normalize_identifier(a) for a in sat.child_dependent_key}
                or {normalize_identifier(a) for a in current_sat.attributes}
                != {normalize_identifier(a) for a in sat.attributes}
            )
            if reshaped:
                issues.append(
                    _issue(
                        "error", "E_EXISTING_SAT_RESHAPED", sat.name,
                        f"existing satellite {sat.name!r} was reshaped (parent, type, child "
                        f"dependent key, source table or attribute set). Growth counts too: "
                        f"a new attribute on a satellite with history is a backfill. Put new "
                        f"attributes in a NEW satellite on {sat.parent!r}",
                    )
                )

        # Advisory inventory of every legitimate extension — the review queue's extension
        # category (charter Q5: validation warnings already flow into the queue, so no new
        # ReviewKind is needed). Hubs that gained feeds are reported above.
        prior_names = (
            {hub.name for hub in prior.hubs}
            | {link.name for link in prior.links}
            | {sat.name for sat in prior.satellites}
        )
        for name, kind, parent in [
            *[(hub.name, "hub", "") for hub in merged.hubs],
            *[(link.name, "link", "") for link in merged.links],
            *[(sat.name, "satellite", sat.parent) for sat in merged.satellites],
        ]:
            if name in prior_names:
                continue
            attached = f" on {parent}" if parent and parent in prior_names else ""
            issues.append(
                _issue(
                    "warning", "W_EXISTING_EXTENDED", name,
                    f"new {kind} {name!r}{attached} added by this extension run",
                )
            )

        return issues

    @staticmethod
    def _check_source_grounding(state: VaultAgentState) -> list[ValidationIssue]:
        """Phase 1 grounding (ADR-0004): flag keys/attributes absent from the source schema.

        No-ops when no schema is declared, so output is unchanged from today. When a schema
        is present, unknowns are *warnings* (the schema may be partial), never errors.

        WP23: on an extension run, constructs that ALREADY EXIST are skipped. The declared
        schema describes the source system this increment integrates — the CRM — while the
        existing constructs were grounded against the core system's schema when they were
        created. Re-checking them against a schema that was never meant to describe them
        produces one warning per pre-existing attribute, which is pure noise and drowns the
        warnings that are about this run. Found by the live bank_extension run: it is what
        pushed the case over its warning tolerance."""
        issues: list[ValidationIssue] = []
        if not state.source_schemas:
            return issues
        pre_existing = (
            {hub.name for hub in state.existing_model.hubs}
            | {link.name for link in state.existing_model.links}
            | {sat.name for sat in state.existing_model.satellites}
            if state.existing_model is not None
            else set()
        )
        columns = known_columns(state.source_schemas)
        hub_by_name = {hub.name: hub for hub in state.dv_model.hubs}
        for hub in state.dv_model.hubs:
            if hub.name in pre_existing:
                continue
            if hub.business_key.strip() and not is_grounded(hub.business_key, columns):
                issues.append(
                    _issue(
                        "warning", "W_BK_NOT_IN_SOURCE", hub.name,
                        f"business key {hub.business_key!r} matches no column in the "
                        f"declared source schema; verify the source or complete the schema",
                    )
                )
            # WP10: each multi-source feed's physical key column should exist in the schema.
            for source in hub.sources:
                if not is_grounded(source.business_key_column, columns):
                    issues.append(
                        _issue(
                            "warning", "W_HUBSOURCE_BK_NOT_IN_SOURCE", hub.name,
                            f"multi-source feed {source.source_table}."
                            f"{source.business_key_column} matches no column in the declared "
                            f"source schema; verify the source or complete the schema",
                        )
                    )
        # W_ROLE_BK_NOT_IN_SOURCE (ADR-0009): a role-qualified participation expects a
        # role-prefixed business-key column in the source (COUNTERPARTY_ACCOUNT_NUMBER); a
        # self-referencing raw table carries the two participations as two columns. Warning,
        # mirroring W_BK_NOT_IN_SOURCE — the schema may be partial. Unqualified refs are
        # already covered by the hub loop above.
        for link in state.dv_model.links:
            if link.name in pre_existing:
                continue
            for ref in link.hub_refs:
                if ref.role is None:
                    continue
                ref_hub = hub_by_name.get(ref.hub)
                if ref_hub is None or not ref_hub.business_key.strip():
                    continue
                expected = role_bk_column(
                    normalize_identifier(ref_hub.business_key), ref.role
                )
                if expected not in columns:
                    issues.append(
                        _issue(
                            "warning", "W_ROLE_BK_NOT_IN_SOURCE", link.name,
                            f"role-qualified participation {ref.hub} (role {ref.role!r}) "
                            f"expects a source column {expected!r}, which matches no column "
                            f"in the declared source schema; verify the source or complete "
                            f"the schema",
                        )
                    )
        # E_LINK_KEY_NOT_IN_SOURCE (WP34 §3.6): an ALIASED link participation names a
        # physical column that must exist, and this is an ERROR where its neighbours are
        # warnings. The difference is deliberate and narrow. A missing business key may mean
        # a partial schema; an alias is an explicit claim that *this relation calls the hub's
        # key THIS*, and staging turns it into a rename. Wrong, it either fails the build or —
        # worse — hashes a same-named column meaning something else into a link that joins
        # live history. `source_key_column` is set only by a ratified FK-derived proposal, so
        # by construction the column was declared; if it is not, something is broken rather
        # than merely incomplete. Checked against the relation the link's staging actually
        # binds to where the schema names one, and against the whole schema where it does not
        # — as precise as the available information allows, never stricter.
        for link in state.dv_model.links:
            if link.name in pre_existing:
                continue
            bound = [
                table
                for table in state.source_schemas
                if construct_binds_to_source_table(link.name, table.table)
            ]
            in_scope = (
                {normalize_identifier(c) for t in bound for c in t.column_names}
                if bound
                else columns
            )
            where = bound[0].table if bound else "the declared source schema"
            for ref in link.hub_refs:
                if ref.source_key_column is None:
                    continue
                if normalize_identifier(ref.source_key_column) not in in_scope:
                    issues.append(
                        _issue(
                            "error", "E_LINK_KEY_NOT_IN_SOURCE", link.name,
                            f"participation {ref.hub} aliases "
                            f"{ref.source_key_column!r} to the hub's key column, but "
                            f"{where} declares no such column; staging would rename a "
                            f"column that is not there",
                        )
                    )
        for sat in state.dv_model.satellites:
            if sat.name in pre_existing:
                continue
            for attr in sat.attributes:
                if not is_grounded(attr, columns):
                    issues.append(
                        _issue(
                            "warning", "W_ATTR_NOT_IN_SOURCE", sat.name,
                            f"attribute {attr!r} matches no column in the declared source "
                            f"schema; verify the source or complete the schema",
                        )
                    )
        return issues

    @staticmethod
    def _check_artifact_columns(metadata: dict[str, Any]) -> list[ValidationIssue]:
        """Check each generated construct carries every DV-required column (if generated)."""
        issues: list[ValidationIssue] = []
        for (section, kind), required in _REQUIRED_COLUMNS.items():
            for name, meta in metadata.get(section, {}).items():
                effective = required
                # Effectivity satellites are date-driven and carry no hash_diff/payload.
                if section == "satellites" and "src_start_date" in meta:
                    effective = required - {"hash_diff"}
                for logical in effective:
                    key = _LOGICAL_TO_META[logical]
                    if not meta.get(key):
                        issues.append(
                            _issue(
                                "error", "E_MISSING_COLUMN", name,
                                f"generated {kind} is missing required column "
                                f"{logical!r} (metadata key {key!r})",
                            )
                        )
        return issues
