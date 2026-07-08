"""Validator agent.

Deterministically checks the logical Data Vault model in ``VaultAgentState.dv_model`` (and,
if the code generator has already run, the generated artifacts) against the DV2.0 rules in
``vault_agent.rules.dv2_rules``. No LLM is involved, so validation is reproducible and runs
in CI without an API key. It is an independent gate: it re-checks structural invariants the
modeler and generator already enforce, giving defense in depth across agents.

Results land in ``VaultAgentState.validation_report`` as a list of typed
:class:`~vault_agent.state.ValidationIssue` records (``severity`` / ``code`` /
``construct`` / ``message``); ``passed`` is true when there are no error-severity issues.

The gates cover structural invariants (names, keys, parents, required columns), grain and
attribute overlap across constructs, satellite-internal duplicate attributes
(``E_SAT_DUP_ATTR``), effectivity-satellite date count and (start, end) order
(``E_EFFSAT_DATE_ORDER`` / ``W_EFFSAT_DATE_ORDER_UNVERIFIED``), hub hash-key/staging
collisions on a shared source entity (``E_HUB_HK_COLLISION``), duplicate hubs over the same
business key and source (``E_DUP_HUB``), and optional source-schema grounding. Count the
``E_``/``W_`` codes in this module for the authoritative gate count — 28 as of WP7
(backlog-2026-07, adding ``W_MASAT_SHARED_GRAIN``); the code, not this prose, is the
source of truth.
"""
from typing import Any

from vault_agent.agents.base import BaseAgent
from vault_agent.grounding import is_grounded, known_columns
from vault_agent.rules.dv2_rules import (
    REQUIRED_HUB_COLUMNS,
    REQUIRED_LINK_COLUMNS,
    REQUIRED_SAT_COLUMNS,
    SAT_WIDE_ATTRIBUTE_THRESHOLD,
    effectivity_date_pair,
    normalize_identifier,
)
from vault_agent.state import (
    Hub,
    IssueSeverity,
    ValidationIssue,
    ValidationReport,
    VaultAgentState,
)

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


def _issue(
    severity: IssueSeverity, code: str, construct: str, message: str
) -> ValidationIssue:
    return ValidationIssue(severity=severity, code=code, construct=construct, message=message)


class ValidatorAgent(BaseAgent):
    """Validates the Data Vault model and generated artifacts against DV2.0 rules."""

    prompt_path = "validator.md"  # type: ignore[assignment]

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        model = state.dv_model
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
            unknown = [h for h in link.connected_hubs if h not in hub_names]
            if unknown:
                issues.append(
                    _issue(
                        "error", "E_LINK_UNKNOWN_HUB", link.name,
                        f"link references unknown hubs: {unknown}",
                    )
                )
            # A declared driving key must be a subset of the hubs the link connects.
            outside = [h for h in link.driving_key if h not in link.connected_hubs]
            if outside:
                issues.append(
                    _issue(
                        "error", "E_DRIVING_KEY_NOT_IN_LINK", link.name,
                        f"driving key is not a subset of connected_hubs: {outside}",
                    )
                )
            # Mirror the generator gate: a transactional (non-historized) link needs an
            # event timestamp to drive automate_dv.nh_link's src_eff.
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
        issues.extend(self._check_source_grounding(state))
        issues.extend(self._check_artifact_columns(state.artifacts.automatedv_yaml))

        errors = [issue for issue in issues if issue.severity == "error"]
        state.validation_report = ValidationReport(passed=not errors, issues=issues)
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
        grain_groups: dict[tuple[tuple[str, ...], str], list[str]] = {}
        for link in model.links:
            key = (tuple(sorted(link.connected_hubs)), link.link_type)
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

        # E_SAT_ATTR_OVERLAP: an attribute must live in at most one satellite per parent.
        attr_owners: dict[str, dict[str, set[str]]] = {}
        for sat in model.satellites:
            per_parent = attr_owners.setdefault(sat.parent, {})
            for attr in sat.attributes:
                per_parent.setdefault(attr, set()).add(sat.name)
        for parent, attrs in sorted(attr_owners.items()):
            for attr, owners in sorted(attrs.items()):
                if len(owners) > 1:
                    joined = ", ".join(sorted(owners))
                    issues.append(
                        _issue(
                            "error", "E_SAT_ATTR_OVERLAP", parent,
                            f"attribute {attr!r} appears in multiple satellites of "
                            f"{parent!r}: {joined}",
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

        return issues

    @staticmethod
    def _check_source_grounding(state: VaultAgentState) -> list[ValidationIssue]:
        """Phase 1 grounding (ADR-0004): flag keys/attributes absent from the source schema.

        No-ops when no schema is declared, so output is unchanged from today. When a schema
        is present, unknowns are *warnings* (the schema may be partial), never errors."""
        issues: list[ValidationIssue] = []
        if not state.source_schemas:
            return issues
        columns = known_columns(state.source_schemas)
        for hub in state.dv_model.hubs:
            if hub.business_key.strip() and not is_grounded(hub.business_key, columns):
                issues.append(
                    _issue(
                        "warning", "W_BK_NOT_IN_SOURCE", hub.name,
                        f"business key {hub.business_key!r} matches no column in the "
                        f"declared source schema; verify the source or complete the schema",
                    )
                )
        for sat in state.dv_model.satellites:
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
