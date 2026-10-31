"""Staging-layer generator (the spec §9 follow-up: "generates a runnable project").

Deterministically renders one AutomateDV ``stage`` model per staging source the raw-vault
models reference — computing every hash key / hashdiff the hubs, links, and satellites
consume — plus the dbt project scaffolding (dbt_project.yml, packages.yml, a documented
sources.yml, README.md) that turns the output directory into a buildable dbt project.

No LLM is involved: everything here derives from the typed ``DVModel`` with the same
naming rules the raw-vault generator uses, so staging and raw vault can never disagree
about a column name. The one open decision — which raw relation feeds a staging model —
is taken from the declared source schema (ADR-0004) when a table matches, and otherwise
*inferred* as ``raw_<base>`` and flagged for human review (``FlagKind.SOURCE_BINDING``):
the generator names, it never guesses silently.

Called by the CodeGeneratorAgent after the raw-vault pass; kept in its own module so the
raw-vault renderer stays under its size budget and this layer is testable in isolation.
"""
import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from vault_agent.rules.dv2_rules import (
    AUTOMATE_DV_VERSION,
    DBT_UTILS_VERSION,
    EFFECTIVITY_APPLIED_COLUMN,
    HASHDIFF_SUFFIX,
    INFERRED_SOURCE_NAME,
    LOAD_DATETIME_COLUMN,
    RAW_SOURCE_PREFIX,
    RECORD_SOURCE_COLUMN,
    STAGING_PREFIX,
    RoleParticipant,
    canonical_hub_key_column,
    construct_base_name,
    construct_binds_to_source_table,
    hub_key_columns,
    is_composite_key,
    is_reserved_column,
    normalize_identifier,
    null_safe_type,
    participation_key,
    role_bk_column,
    role_columns_from_foreign_keys,
    role_fk_column,
    role_participant,
    satellite_feed,
    satellite_participation_column,
    source_table_on_multi_source_hub,
    stage_column_name,
)
from vault_agent.rules.platforms import (
    DEFAULT_TARGET_PLATFORM,
    PlatformProfile,
    TargetPlatform,
    platform_profile,
)
from vault_agent.state import (
    BusinessVaultOptions,
    DVModel,
    FlagKind,
    Hub,
    HubSource,
    KeyTranslation,
    PipelineFlag,
    SourceTable,
    StageBinding,
)

# dbt project/profile name used in the generated scaffolding.
PROJECT_NAME = "vault_project"


@dataclass
class _HashDiff:
    """Marker for a hashdiff entry (rendered with ``is_hashdiff: true``)."""

    columns: list[str]


@dataclass
class StagingSpec:
    """Everything one ``stage`` model needs, collected across the constructs it feeds."""

    name: str  # staging model name, e.g. "stg_customer"
    base: str  # construct base, e.g. "customer"
    # Ordered hashed columns: (name, single source column | multi-column list | _HashDiff).
    hashed: list[tuple[str, str | list[str] | _HashDiff]] = field(default_factory=list)
    derived: dict[str, str] = field(default_factory=dict)  # e.g. APPLIED_DTS -> start date
    source_columns: list[str] = field(default_factory=list)  # expected raw columns, ordered
    source_model: str = ""  # the raw relation this staging reads
    bound: bool = False  # True when matched against a declared source table
    # dbt source block this staging reads through (WP7 §7.2). Set only on grounded runs
    # for specs whose declared table carries a physical location (schema/database); the
    # rendered model then uses automate_dv.stage's source() mapping form instead of a
    # bare relation name.
    source_name: str | None = None
    # WP36 (ADR-0013): this link's target keys are reached by joining through other
    # relations — one entry per translated participation (a WP37 relationship link can carry
    # several; 2026-09-13's first dbt build found a single slot silently keeping the last).
    # The stage model then reads the TRANSLATION model (`stage_source`) instead of the raw
    # relation, while `source_model`/`source_name` keep naming the raw relation for
    # sources.yml and the metadata — what the project READS is still that relation.
    translations: list[KeyTranslation] = field(default_factory=list)
    # WP41: parallel to `translations` — the column each one projects the natural key AS. The
    # natural key's own name for an unqualified participation (today's bytes); the role column
    # for a role-qualified one, which two roles of one hub through one table cannot do without.
    # WP93: a list for a composite hub — every key column projected under the hub's own name.
    translation_columns: list[str | list[str]] = field(default_factory=list)
    stage_source: str | None = None
    # WP83: one entry per link participation this stage hashes — (the stage columns the hash
    # is taken over, the relation columns they come from). `build_staging` declares the stage
    # columns as AutomateDV `null_columns: optional` when every relation column is typed
    # integer or character, so a NULL participant becomes the zero key instead of dropping the
    # link row. A translated participation is recorded with the SURROGATE as its relation column
    # (WP93): a NULL surrogate is a NULL participant, zero-keyed when the surrogate's type and the
    # projected key's types are all null-safe (`null_optional_columns`, `zero_key_hubs`).
    # WP86: the third element names the hub the participation hashes into — its zero-key rows.
    null_groups: list[tuple[tuple[str, ...], tuple[str, ...], str]] = field(default_factory=list)
    # WP82: the aliases a human ratified with this stage's binding — a subset of `derived`,
    # recorded apart so the catalogue can carry them (`stage_aliases`) to the next increment.
    ratified_columns: dict[str, str] = field(default_factory=dict)
    # WP95: the link participations this stage hashes, for the rule that reads a role's column
    # from the relation's foreign keys at binding time; and what that rule derived — a subset of
    # `derived` like the ratified aliases, carried the same way.
    participations: list[RoleParticipant] = field(default_factory=list)
    role_columns: dict[str, str] = field(default_factory=dict)

    def add_hashed(self, name: str, value: str | list[str] | _HashDiff) -> None:
        if all(existing != name for existing, _ in self.hashed):
            self.hashed.append((name, value))

    def add_source_column(self, column: str) -> None:
        if column not in self.source_columns:
            self.source_columns.append(column)

    def add_null_group(
        self, stage_columns: list[str], relation_columns: list[str], hub: str
    ) -> None:
        group = (tuple(stage_columns), tuple(relation_columns), hub)
        if group not in self.null_groups:
            self.null_groups.append(group)

    def add_translation(self, translation: KeyTranslation, column: str | list[str]) -> None:
        if (translation, column) not in zip(
            self.translations, self.translation_columns, strict=True
        ):
            self.translations.append(translation)
            self.translation_columns.append(column)

    def projected_apart(self, translation: KeyTranslation, column: str) -> str:
        """WP100: the column ``translation`` projects — ``column`` unless an EARLIER translation
        of this stage already projects that name, then ``<KEY>_VIA_<THROUGH>`` (WP89's form).
        Two hubs keyed alike (`Department.Name`, `Shift.Name`) in one link once rendered
        `r1.NAME as NAME, r2.NAME as NAME`: dbt refused the view, and built, the stage would have
        hashed both hubs from one column. Decided here, BEFORE the hash key, the link key and the
        null group are recorded over it, so the second `NAME` is never confused with the first."""
        taken = {
            normalize_identifier(c)
            for t, cols in zip(self.translations, self.translation_columns, strict=True)
            if t != translation
            for c in _projected(cols)
        }
        if normalize_identifier(column) in taken:
            return _via_column(column, translation.through_table)
        return column

    def translated_groups(self) -> dict[tuple[str, ...], KeyTranslation]:
        """WP93: the null groups whose key arrives through a translation, by stage columns."""
        return {
            tuple(_projected(column)): t
            for t, column in zip(self.translations, self.translation_columns, strict=True)
        }


def _projected(column: str | list[str]) -> list[str]:
    """The column(s) a translation projects: one for a single key, the list for a composite."""
    return list(column) if isinstance(column, list) else [column]


def _via_column(column: str, through_table: str) -> str:
    """``<KEY>_VIA_<THROUGH>``: a translated key projected apart from a same-named column — the
    relation's own (WP89) or an earlier translation's (WP100). The hash value does not depend
    on the column's name."""
    return f"{column}_VIA_{_to_column(through_table)}"


@dataclass
class StagingResult:
    models: dict[str, str]  # staging model name -> rendered SQL
    metadata: dict[str, dict[str, object]]  # staging model name -> stage() metadata
    scaffolding: dict[str, str]  # relative output path -> file content
    flags: list[PipelineFlag]
    # WP86: hub name -> the zero-key stage its source_model list must end with.
    zero_key_hubs: dict[str, str] = field(default_factory=dict)


def _to_column(label: str) -> str:
    return normalize_identifier(label)


# Mirrors of the raw-vault generator's naming (kept trivially simple; both sides derive
# from normalize_identifier + the rules/ constants, so they cannot drift apart).
def _base_name(construct_name: str) -> str:
    # The rule itself lives in rules/ (WP34): the link proposer needs the same answer, and a
    # second copy of it here is how construct↔relation correspondence would silently split.
    return construct_base_name(construct_name)


def _staging_name(construct_name: str) -> str:
    # Normalised through the one identifier helper (WP20 §2.4), the way _sat_staging_model
    # already did — two naming paths that merely happen to agree on well-formed names are a
    # latent split. Byte-identical for every valid construct name (E_BAD_NAME enforces
    # lowercase snake_case, and normalize("account").lower() == "account").
    return STAGING_PREFIX + normalize_identifier(_base_name(construct_name)).lower()


def construct_stage_name(construct_name: str) -> str:
    """The staging model a single-source hub, a link or a satellite with its own ``source_table``
    reads: ``stg_<base>``. The public name of the rule above for readers outside the generators
    (WP80's subject areas); a multi-source hub's feeds use ``multi_source_staging_name``."""
    return _staging_name(construct_name)


def legacy_feeds(
    existing: DVModel | None, carried_bindings: dict[str, str] | None = None
) -> set[tuple[str, str, str]]:
    """The (hub, table, column) feeds that carry an UNSUFFIXED staging name (WP23 §2.6).

    Grandfathering needs exactly one fact: which feed is already materialised as
    ``stg_<entity>``? Only one ever is — the implicit feed of a hub that was SINGLE-source in
    the existing vault. The merger materialises it as (source_entity, business_key), which is
    the shape recorded here.

    A hub that was ALREADY multi-source there is deliberately excluded: its feeds were
    generated with WP10 suffixed names (``stg_<entity>_<source>``) and keeping those is what
    preserves them. Grandfathering them would be wrong twice over — it would rename existing
    models, and every one of them would collapse onto the same unsuffixed name.

    Derived from the existing model rather than stored on the state, so nothing new has to
    survive the checkpointer and a greenfield run has nothing to derive.

    WP101 (C34): a hub that became multi-source on the PREVIOUS step is already multi-source
    here, and the rule above would rename its grandfathered stage on this step — the rename it
    exists to refuse. The carried catalogue (``stage_bindings``, WP77) records what is
    materialised under which name: the feed whose table ``stg_<entity>`` is bound to is the
    grandfathered one. The model alone cannot say it — a greenfield multi-source hub may have a
    feed named like its entity — so without that binding nothing is grandfathered."""
    if existing is None:
        return set()
    legacy = {
        (hub.name, normalize_identifier(hub.source_entity),
         normalize_identifier(hub.business_key))
        for hub in existing.hubs
        if not hub.sources
    }
    for hub in existing.hubs:
        relation = (carried_bindings or {}).get(_staging_name(hub.name))
        if not hub.sources or relation is None:
            continue
        matching = [
            s for s in hub.sources
            if normalize_identifier(s.source_table) == normalize_identifier(relation)
        ]
        if len(matching) == 1:
            legacy.add((hub.name, normalize_identifier(matching[0].source_table),
                        normalize_identifier(matching[0].business_key_column)))
    return legacy


def legacy_feed_of(hub: Hub, legacy: set[tuple[str, str, str]] | None) -> HubSource | None:
    """WP101: the feed of ``hub`` grandfathered as ``stg_<entity>``, or None. The one answer the
    raw-vault generator and the staging generator both take for an existing satellite."""
    if not legacy:
        return None
    return next((s for s in hub.sources if is_legacy_feed(hub, s, legacy)), None)


def is_legacy_feed(hub: Hub, source: HubSource, legacy: set[tuple[str, str, str]]) -> bool:
    """True when this feed already existed before the extension (WP23 §2.6)."""
    return (
        hub.name,
        normalize_identifier(source.source_table),
        normalize_identifier(source.business_key_column),
    ) in legacy


def multi_source_staging_name(
    hub: Hub, source: HubSource, legacy: set[tuple[str, str, str]] | None = None
) -> str:
    """Per-source staging model for a multi-source hub (WP10): ``stg_<entity>_<source>``.

    Deterministic and traceable — the source suffix is the feeding table's normalised name,
    so a hub fed by ``crm_customer`` + ``victor_partner`` yields ``stg_customer_crm_customer``
    and ``stg_customer_victor_partner``.

    GRANDFATHERING (WP23 §2.6, charter Q2): a feed that already existed before an extension
    keeps its LEGACY name ``stg_<entity>`` — no source suffix. Renaming it would rename a
    materialised dbt model, i.e. drop and rebuild a table that holds history, which is exactly
    the destructive migration this track never performs. Only feeds the extension adds get the
    suffixed WP10 name. ``legacy`` is empty on greenfield runs, so symmetric WP10 naming is
    unchanged there (guarded by the WP10 tests and both demos)."""
    if legacy and is_legacy_feed(hub, source, legacy):
        return _staging_name(hub.name)
    return (
        STAGING_PREFIX
        + _base_name(hub.name)
        + "_"
        + normalize_identifier(source.source_table).lower()
    )


def collect_staging_specs(
    model: DVModel, legacy: set[tuple[str, str, str]] | None = None,
    existing_satellites: frozenset[str] = frozenset(),
) -> dict[str, StagingSpec]:
    """Group the raw-vault constructs by the staging model that feeds them.

    Mirrors the raw-vault generator's guards (unknown hubs/parents are skipped there and
    therefore need no staging here); insertion order is deterministic: hubs, links, then
    the satellites' additions to their parents' staging models."""
    from vault_agent.agents.code_generator import (
        _hub_hashkey,
        _link_hashkey,
        _sat_staging_model,
    )

    specs: dict[str, StagingSpec] = {}
    hub_by_name = {hub.name: hub for hub in model.hubs}

    def spec_for(construct_name: str) -> StagingSpec:
        name = _staging_name(construct_name)
        if name not in specs:
            specs[name] = StagingSpec(name=name, base=_base_name(construct_name))
        return specs[name]

    for hub in model.hubs:
        if hub.sources:
            # WP10 multi-source: one stg_<entity>_<source> per feed, each aliasing its
            # physical key column to the canonical name and hashing X_HK from it — so the
            # same key value hashes identically across sources (the integration property).
            canonical = canonical_hub_key_column(hub)
            for source in hub.sources:
                name = multi_source_staging_name(hub, source, legacy)
                spec = specs.setdefault(name, StagingSpec(name=name, base=_base_name(hub.name)))
                if not (legacy and is_legacy_feed(hub, source, legacy)):
                    spec.source_model = source.source_table
                    spec.bound = True
                # A GRANDFATHERED feed deliberately gets NO binding here (WP23 §2.6): it keeps
                # the one it already had, which bind_sources re-derives exactly as it did for
                # the single-source hub — a declared table when the schema names one, else the
                # inferred raw_<base> (flagged, as before). Binding it verbatim to the feed's
                # source_table would keep the model's NAME while silently repointing it at a
                # different relation: `stg_customer` would stop reading `raw_customer` and
                # start reading `customer`, which either does not exist (the build breaks) or
                # does and is the wrong data. Preserving the name without the binding is not
                # preserving the model.
                src_col = _to_column(source.business_key_column)
                if src_col != canonical:
                    spec.derived[canonical] = src_col  # alias the source column -> canonical
                spec.add_hashed(_hub_hashkey(hub), canonical)
                spec.add_source_column(src_col)
        elif is_composite_key(hub):
            # WP45: the hash is taken over every key column, in order (AutomateDV's list
            # form of hashed_columns); each column passes through.
            spec = spec_for(hub.name)
            cols = hub_key_columns(hub)
            spec.add_hashed(_hub_hashkey(hub), cols)
            for col in cols:
                spec.add_source_column(col)
        else:
            spec = spec_for(hub.name)
            bk_col = _to_column(hub.business_key)
            spec.add_hashed(_hub_hashkey(hub), bk_col)
            spec.add_source_column(bk_col)

    generated_links = []
    for link in model.links:
        if any(ref.hub not in hub_by_name for ref in link.hub_refs):
            continue  # the raw-vault generator skips (and flags) this link
        if link.link_type == "transactional" and link.event_timestamp is None:
            continue  # not generated as t_link either
        generated_links.append(link)
        spec = spec_for(link.name)
        bk_cols = []
        for ref in link.hub_refs:
            # Role-qualify both the FK hash key and its source business-key column so a
            # self-referencing link gets two distinct columns (ADR-0009); unqualified refs
            # keep the bare names, so plain-string links stage byte-identically. The FK
            # hashes from the hub's CANONICAL key column (WP24 §2.1) — anything else
            # cannot join the hub's own hash key when a multi-source hub's feeds agree on
            # a physical name differing from the business-key label.
            hub = hub_by_name[ref.hub]
            if is_composite_key(hub) and ref.role is None and ref.source_key_column is None:
                # WP45: an unqualified participation of a composite hub hashes over the
                # hub's column list, exactly as the hub's own stage does; the link's hash
                # key takes every column. Role and alias shapes are refused by
                # E_HUB_COMPOSITE_UNSUPPORTED before generation.
                cols = hub_key_columns(hub)
                if ref.key_translation is not None:
                    # WP100: each column apart from an earlier translation's, before anything
                    # is recorded over it.
                    cols = [spec.projected_apart(ref.key_translation, c) for c in cols]
                bk_cols.extend(cols)
                spec.add_hashed(role_fk_column(_hub_hashkey(hub), ref.role), cols)
                if ref.key_translation is not None:
                    # WP93: the key arrives through the translation view, every column projected
                    # under the hub's own name (the gate holds them to the hub's). What THIS
                    # relation carries is the surrogate; a NULL surrogate is a NULL participant.
                    t = ref.key_translation
                    surrogate = _to_column(t.referencing_column)
                    spec.add_translation(t, cols)
                    spec.add_source_column(surrogate)
                    spec.add_null_group(cols, [surrogate], hub.name)
                    continue
                for col in cols:
                    spec.add_source_column(col)
                spec.add_null_group(cols, cols, hub.name)
                continue
            bk_col = role_bk_column(canonical_hub_key_column(hub), ref.role)
            if ref.key_translation is not None:
                # WP100: apart from a column an earlier translation of this stage projects
                # (two hubs keyed alike), before the hash key and the link key are recorded.
                bk_col = spec.projected_apart(ref.key_translation, bk_col)
            bk_cols.append(bk_col)
            spec.add_hashed(role_fk_column(_hub_hashkey(hub), ref.role), bk_col)
            if ref.key_translation is None:
                spec.participations.append(role_participant(ref, hub))  # WP95
            # WP34 §3.4: when the relation feeding this link calls the hub's key something
            # else, alias it to the canonical name FIRST — the same mechanism a multi-source
            # hub's feed uses above, and for the same reason: the hash must be taken over the
            # canonical column or the FK cannot join the hub's own hash key. Without the
            # alias the spec would demand a column the relation does not have.
            if ref.key_translation is not None:
                # WP36: the hub's key is not in this relation under any name; it arrives
                # through the translation model (build_staging), which projects it as the
                # canonical column. What THIS relation must carry is the surrogate. WP41: the view
                # projects it as the column hashed here — a role's own column for a role.
                spec.add_translation(ref.key_translation, bk_col)
                surrogate = _to_column(ref.key_translation.referencing_column)
                spec.add_source_column(surrogate)
                spec.add_null_group([bk_col], [surrogate], hub.name)  # WP93: NULL = no participant
                continue
            src_col = _to_column(ref.source_key_column) if ref.source_key_column else bk_col
            if src_col != bk_col:
                spec.derived[bk_col] = src_col
            spec.add_source_column(src_col)
            spec.add_null_group([bk_col], [src_col], hub.name)
        spec.add_hashed(_link_hashkey(link), bk_cols)
        if link.link_type == "transactional":
            for col in link.payload:
                spec.add_source_column(_to_column(col))
            if link.event_timestamp:
                spec.add_source_column(_to_column(link.event_timestamp))

    link_names = {link.name for link in generated_links}
    links_by_name = {link.name: link for link in generated_links}
    for sat in model.satellites:
        if sat.parent not in hub_by_name and sat.parent not in link_names:
            continue  # dangling parent — skipped/flagged by the raw-vault generator
        sat_parent = hub_by_name.get(sat.parent)
        if source_table_on_multi_source_hub(sat, sat_parent):
            continue  # ADR-0011 row 3: the raw-vault generator flags and skips this
            # satellite — emitting its staging here would leave an orphan stg_<sat base>.
        bound_feed = satellite_feed(sat, sat_parent)
        if bound_feed is not None:
            assert sat_parent is not None  # implied by satellite_feed returning a feed
            # ADR-0011: the satellite belongs to ONE feed, so its payload goes to that
            # feed's staging spec and nowhere else. This is the fix the ADR's probe named:
            # under the old split every feed's staging was asked to project the satellite's
            # columns, so the core system's staging demanded the CRM's — which cannot build.
            # No dedicated stg_<sat base> either: the feed's staging already reads the right
            # relation, and a second one would be the WP24 finding-3 orphan all over again.
            target_specs = [specs[multi_source_staging_name(sat_parent, bound_feed, legacy)]]
            for col in [_to_column(attr) for attr in sat.attributes]:
                target_specs[0].add_source_column(col)
            for key in sat.child_dependent_key:
                target_specs[0].add_source_column(_to_column(key))
            target_specs[0].add_hashed(
                _base_name(sat.name).upper() + HASHDIFF_SUFFIX,
                _HashDiff([_to_column(attr) for attr in sat.attributes]),
            )
            continue
        if sat.source_table and sat.sat_type != "effectivity":
            # WP7 §7.1: the satellite's rows live in their own (usually finer-grain) raw
            # relation — a dedicated staging model, bound VERBATIM to the declared
            # source_table (never inferred, never flagged). It still computes the
            # parent's hash key from the parent's business key(s): those columns existing
            # in the finer-grain relation is what makes the rows attachable.
            name = _sat_staging_model(sat)
            spec = specs.setdefault(
                name, StagingSpec(name=name, base=_base_name(sat.name))
            )
            spec.source_model = sat.source_table
            spec.bound = True
            if sat.parent in hub_by_name and is_composite_key(hub_by_name[sat.parent]):
                # WP45: the satellite's own relation must carry every key column (gated by
                # E_SAT_KEY_NOT_IN_SOURCE); the parent key hashes over the list.
                parent_hub = hub_by_name[sat.parent]
                cols = hub_key_columns(parent_hub)
                spec.add_hashed(_hub_hashkey(parent_hub), cols)
                for col in cols:
                    spec.add_source_column(col)
            elif sat.parent in hub_by_name:
                parent_hub = hub_by_name[sat.parent]
                bk_col = canonical_hub_key_column(parent_hub)
                spec.add_hashed(_hub_hashkey(parent_hub), bk_col)
                if sat.key_translation is not None:
                    # WP38: the relation carries the surrogate, not the hub's key; the key
                    # arrives through the translation view `build_staging` renders, exactly as
                    # for a translated link participation (WP36).
                    spec.add_translation(sat.key_translation, bk_col)
                    spec.add_source_column(_to_column(sat.key_translation.referencing_column))
                else:
                    spec.add_source_column(bk_col)
            else:
                parent_link = links_by_name[sat.parent]
                bk_cols = []
                for ref in parent_link.hub_refs:
                    ref_hub = hub_by_name[ref.hub]
                    if is_composite_key(ref_hub) and ref.role is None:
                        # WP45: as in the link's own stage — the list, unaliased.
                        cols = hub_key_columns(ref_hub)
                        bk_cols.extend(cols)
                        for col in cols:
                            spec.add_source_column(col)
                        spec.add_null_group(cols, cols, ref_hub.name)
                        continue
                    bk_col = role_bk_column(canonical_hub_key_column(ref_hub), ref.role)
                    translated = sat.participation_translations.get(
                        participation_key(ref.hub, ref.role)
                    )
                    if translated is not None:
                        bk_col = spec.projected_apart(translated, bk_col)  # WP100, as above
                    bk_cols.append(bk_col)
                    src_col = _to_column(satellite_participation_column(sat, ref, ref_hub))
                    if translated is not None:
                        # WP40: this participation's key arrives through the translation view,
                        # projected as the column hashed here (WP41: a role's own column).
                        spec.add_translation(translated, bk_col)
                    elif src_col != bk_col:
                        # WP41: the relation carries this key under another name.
                        spec.derived[bk_col] = src_col
                    if translated is None:
                        # WP83, as in the link's stage
                        spec.add_null_group([bk_col], [src_col], ref_hub.name)
                    spec.add_source_column(src_col)
                spec.add_hashed(_link_hashkey(parent_link), bk_cols)
            target_specs = [spec]
        else:
            sat_parent_hub = hub_by_name.get(sat.parent)
            if sat_parent_hub is not None and sat_parent_hub.sources:
                if sat.name in existing_satellites:
                    # WP101 (C35): an EXISTING satellite is not split when its hub gained feeds
                    # (WP23 §2.6, the raw-vault generator renders it once against the legacy
                    # stage) — so its payload belongs to the legacy feed's stage alone. Asking
                    # every feed for it made `stg_unit_measure_productvendor` hash a `NAME` that
                    # `ProductVendor` does not have. No identifiable legacy feed: the generator
                    # flags the satellite instead of guessing, and no stage carries its payload.
                    feed = legacy_feed_of(sat_parent_hub, legacy)
                    target_specs = (
                        [specs[multi_source_staging_name(sat_parent_hub, feed, legacy)]]
                        if feed is not None else []
                    )
                else:
                    # WP10: a satellite on a multi-source hub feeds each per-source staging (one
                    # satellite per source is emitted downstream, reading its own staging).
                    target_specs = [
                        specs[multi_source_staging_name(sat_parent_hub, source, legacy)]
                        for source in sat_parent_hub.sources
                    ]
            else:
                target_specs = [spec_for(sat.parent)]
        attr_cols = [_to_column(attr) for attr in sat.attributes]
        for spec in target_specs:
            for col in attr_cols:
                spec.add_source_column(col)
            for key in sat.child_dependent_key:
                spec.add_source_column(_to_column(key))
            if sat.sat_type == "effectivity":
                # Same guard as the raw-vault eff_sat template: needs start+end dates and a
                # link parent. The dedicated src_eff column is DERIVED from the start date so
                # AutomateDV's incremental SQL never projects one column twice (see rules/).
                if sat.parent in link_names and len(attr_cols) >= 2:
                    spec.derived.setdefault(EFFECTIVITY_APPLIED_COLUMN, attr_cols[0])
            else:
                hashdiff_name = _to_column(_base_name(sat.name)) + HASHDIFF_SUFFIX
                spec.add_hashed(hashdiff_name, _HashDiff(columns=attr_cols))

    for spec in specs.values():
        spec.add_source_column(LOAD_DATETIME_COLUMN)
        spec.add_source_column(RECORD_SOURCE_COLUMN)
    return specs


# WP83: the declared types `COALESCE(col, '-2')` accepts on every platform — integers and
# character strings. A date, a boolean, a UUID would fail at build, so they keep today's
# behaviour; so does an untyped column.
def _null_safe_type(declared: str) -> bool:
    return null_safe_type(declared)  # the rule lives in rules/ since WP94 (the gate reads it too)


def _group_types(
    spec: StagingSpec,
    stage_columns: tuple[str, ...],
    relation_columns: tuple[str, ...],
    types: dict[str, str],
    declared: dict[str, SourceTable] | None,
) -> list[str] | None:
    """WP83/WP93: the declared types a null group's zero key must be safe for — the relation
    columns' own; for a translated group (WP93) the surrogate's AND the projected key columns'
    in the through relation, since the stage column that is replaced is the projected one.
    ``None`` when a type is unknown or not null-safe: no null handling, today's behaviour."""
    own = [types.get(normalize_identifier(c), "") for c in relation_columns]
    if not all(_null_safe_type(t) for t in own):
        return None
    translation = spec.translated_groups().get(tuple(stage_columns))
    if translation is None:
        return own
    through = (declared or {}).get(normalize_identifier(translation.through_table))
    if through is None:
        return None
    through_types = {normalize_identifier(c.name): c.type for c in through.column_refs}
    projected = [through_types.get(normalize_identifier(c), "") for c in translation.natural_keys]
    return projected if all(_null_safe_type(t) for t in projected) else None


def null_optional_columns(
    spec: StagingSpec,
    relation: SourceTable | None,
    declared: dict[str, SourceTable] | None = None,
) -> list[str]:
    """WP83: the stage columns to declare as AutomateDV ``null_columns: optional`` — every
    participation whose relation columns are all typed integer or character in the bound
    relation (a translated one: its surrogate and its projected key, WP93). An inferred stage or
    an unknown relation: none (today's behaviour)."""
    if not spec.bound or relation is None or not spec.null_groups:
        return []
    types = {normalize_identifier(c.name): c.type for c in relation.column_refs}
    columns: list[str] = []
    for stage_columns, relation_columns, _hub in spec.null_groups:
        if _group_types(spec, stage_columns, relation_columns, types, declared) is not None:
            columns.extend(c for c in stage_columns if c not in columns)
    return columns


_INTEGER_TYPES = frozenset({"int", "integer", "bigint", "smallint", "tinyint"})


def zero_key_hubs(
    model: DVModel, specs: dict[str, StagingSpec], declared: dict[str, SourceTable]
) -> dict[str, list[tuple[str, str]]]:
    """WP86: every hub a zero-keyed participation (WP83's rule) hashes into, with the hub's own
    stage key columns and each one's abstract type — ``bigint`` for an integer-typed relation
    column, else ``varchar`` — taken from the participation's relation columns, position by
    position. A participation whose column count differs from the hub key's is not used."""
    hubs = {hub.name: hub for hub in model.hubs}
    out: dict[str, list[tuple[str, str]]] = {}
    for spec in specs.values():
        relation = declared.get(normalize_identifier(spec.source_model)) if spec.bound else None
        if relation is None:
            continue
        types = {normalize_identifier(c.name): c.type for c in relation.column_refs}
        for stage_columns, relation_columns, hub_name in spec.null_groups:
            hub = hubs.get(hub_name)
            if hub is None or hub_name in out:
                continue
            # WP93: a translated group's row is typed by the projected key's columns.
            declared_types = _group_types(spec, stage_columns, relation_columns, types, declared)
            if declared_types is None:
                continue
            key_columns = hub_stage_key_columns(hub)
            if len(key_columns) != len(declared_types):
                continue
            out[hub_name] = [
                (col, "bigint" if re.split(r"[\s(]", t.strip().lower(), maxsplit=1)[0]
                 in _INTEGER_TYPES else "varchar")
                for col, t in zip(key_columns, declared_types, strict=True)
            ]
    return out


def hub_stage_key_columns(hub: Hub) -> list[str]:
    """The columns a hub's own stage hashes its key over — the order the hash takes them."""
    if hub.sources:
        return [canonical_hub_key_column(hub)]
    if is_composite_key(hub):
        return list(hub_key_columns(hub))
    return [_to_column(hub.business_key)]


def zero_key_model_name(hub: Hub) -> str:
    return f"zero_keys_{_base_name(hub.name)}"


def zero_key_stage_name(hub: Hub) -> str:
    return f"stg_{_base_name(hub.name)}_zero_keys"


def render_zero_key_model(
    hub: Hub, columns: list[tuple[str, str]], profile: PlatformProfile, type_stage: str
) -> str:
    """WP86: the hub's two zero-key rows — every key column `-1` (required, missing) and `-2`
    (optional, not applicable) — at AutomateDV's ghost-record date, from the system. Each key is
    cast to the type the hub's own stage (``type_stage``) has in the warehouse, read at run time
    through the adapter: the declared source types are only the fallback, because a warehouse may
    type a column otherwise (the first build found `ShoppingCartID` declared `nvarchar`, loaded
    `bigint` — a hub cannot union text with bigint)."""
    def cast(value: str, col: str, kind: str) -> str:
        return f"CAST('{value}' AS {{{{ types.get('{col}', '{profile.seed_type(kind)}') }}}})"

    def row(value: str) -> str:
        keys = ", ".join(f"{cast(value, col, kind)} AS {col}" for col, kind in columns)
        return (
            f"SELECT {keys}, CAST('1900-01-01' AS {profile.seed_type('timestamp')}) AS "
            f"{LOAD_DATETIME_COLUMN}, CAST('SYSTEM' AS {profile.seed_type('varchar')}) AS "
            f"{RECORD_SOURCE_COLUMN}"
        )

    return (
        f"-- Generated zero-key rows for {hub.name} (WP86): a link whose participant is missing\n"
        "-- carries the zero key; these rows give it a hub row to join.\n"
        # dbt cannot see a ref() inside `if execute`; the hint declares the dependency.
        f"-- depends_on: {{{{ ref('{type_stage}') }}}}\n"
        "{{ config(materialized='view') }}\n"
        "{%- set types = {} -%}\n"
        "{%- if execute -%}\n"
        f"{{%- for c in adapter.get_columns_in_relation(ref('{type_stage}')) -%}}\n"
        "{%- do types.update({c.name | upper: c.data_type}) -%}\n"
        "{%- endfor -%}\n"
        "{%- endif %}\n"
        f"{row('-1')}\nUNION ALL\n{row('-2')}\n"
    )


def stage_key_columns(spec: StagingSpec) -> list[str]:
    """The raw columns a stage's KEYS read from its relation: every hash key's source column(s)
    and every derived column's source (WP73). A hashdiff's attributes are not keys — a missing
    attribute is a partial schema and stays `W_ATTR_NOT_IN_SOURCE`'s warning; a missing key
    column is a wrong binding. Normalised, ordered, deduplicated."""
    seen: list[str] = []
    for _name, value in spec.hashed:
        if isinstance(value, _HashDiff):
            continue
        columns = value if isinstance(value, list) else [value]
        for column in columns:
            key = normalize_identifier(column)
            if key not in seen:
                seen.append(key)
    for source in spec.derived.values():
        key = normalize_identifier(source)
        if key not in seen:
            seen.append(key)
    return seen


def missing_stage_columns(spec: StagingSpec, table: SourceTable) -> list[str]:
    """The key columns a stage hashes or derives that ``table`` does not declare (WP73). A
    hash may read a DERIVED column (a role alias such as ``ORGANISATION_BUSINESSENTITYID``,
    WP41) — AutomateDV derives before it hashes — so derived names count as available; the
    derived columns' own sources must be declared."""
    available = {normalize_identifier(c) for c in table.column_names}
    available |= {normalize_identifier(name) for name in spec.derived}
    return [c for c in stage_key_columns(spec) if c not in available]


def apply_stage_aliases(
    spec: StagingSpec, columns: dict[str, str], *, ratified: bool = True
) -> None:
    """WP82: a human's aliases ``{STAGE_COLUMN: relation_column}`` on one stage — each becomes a
    derived column (WP41's mechanism: AutomateDV derives before it hashes, so the hash reads the
    alias), the null groups and the expected columns name the relation's column instead, and the
    aliases are recorded for the metadata and the catalogue. WP95 applies the rule-derived role
    columns through the same path (``ratified=False``: recorded as ``role_columns``)."""
    if not columns:
        return
    alias = {normalize_identifier(k): v for k, v in columns.items()}
    # WP95: a stage column that already read an alias the relation lacks (the modeler's
    # `StoreID`) reads the relation's column now; the old name leaves the expected columns.
    previous = {
        normalize_identifier(spec.derived[k]): v
        for k, v in columns.items() if k in spec.derived
    }
    alias = {**previous, **alias}
    # AutomateDV renders every derived column in ONE select over the source (read in
    # `macros/staging/derive_columns.sql`, 0.11.4: `<source> AS <derived>` per entry, all from
    # `source_data`), so a derived column cannot read another. A WP41 role column that read the
    # aliased stage column (`STORE_BUSINESSENTITYID: STOREID`) must read the relation's column
    # directly once the alias says where STOREID comes from.
    for derived_name, source in list(spec.derived.items()):
        if normalize_identifier(source) in alias:
            spec.derived[derived_name] = alias[normalize_identifier(source)]
    for stage_column, relation_column in columns.items():
        spec.derived[stage_column] = relation_column
        if ratified:
            spec.ratified_columns[stage_column] = relation_column
        else:
            spec.role_columns[stage_column] = relation_column
    spec.null_groups = [
        (stage_columns, tuple(alias.get(normalize_identifier(c), c) for c in relation_columns), hub)
        for stage_columns, relation_columns, hub in spec.null_groups
    ]
    expected: list[str] = []
    for column in spec.source_columns:
        renamed = alias.get(normalize_identifier(column), column)
        if renamed not in expected:
            expected.append(renamed)
    spec.source_columns = expected


def bind_sources(
    specs: dict[str, StagingSpec],
    source_schemas: list[SourceTable],
    source_overrides: dict[str, str] | None = None,
    binding_reasons: dict[str, str] | None = None,
    carried_bindings: dict[str, str] | None = None,
    ratified: dict[str, str] | None = None,
    carried_aliases: dict[str, dict[str, str]] | None = None,
) -> list[PipelineFlag]:
    """Bind each staging model to its raw relation; flag every *inferred* binding.

    A declared source table matches by normalised name against the construct base or its
    ``raw_<base>`` form; the table name is then used verbatim (source dialect, ADR-0004).
    Without a match the binding is inferred as ``raw_<base>`` and flagged for review.

    ``source_overrides`` (WP9 §6) maps a normalised construct base to the source table a
    ratified/proposed business↔source mapping resolved it to; an override binds the spec
    verbatim and raises no flag (the mapping *is* the human-reviewable evidence).

    ``carried_bindings`` (WP77) maps a stage model's name to the relation an earlier increment
    bound it to; it is applied after this run's overrides and before the name match, only when
    the relation is declared here (increment or catalogue) and carries every column the stage
    hashes — and raises no flag: it was reviewed when it was made."""
    overrides = source_overrides or {}
    carried = carried_bindings or {}
    decided = ratified or {}  # WP82: by stage name, before every rule
    aliases = carried_aliases or {}
    # WP47: why a binding is inferred, from the same resolution the overrides come from
    # (``link_proposal.link_binding_reasons``); a base with no entry is ``none``.
    reasons = binding_reasons or {}
    flags: list[PipelineFlag] = []
    declared_tables = {normalize_identifier(t.table): t for t in source_schemas}

    def _rejected(spec: StagingSpec, table_name: str) -> bool:
        """WP73: a declared relation must carry every column the stage hashes or derives. A
        translated stage joins through another relation and is judged by its own gates."""
        table = declared_tables.get(normalize_identifier(table_name))
        if table is None or spec.translations:
            return False
        # WP95: a role's column the relation carries under its foreign key's name is derived
        # first, so the relation is judged with it — the alias a human typed before.
        apply_stage_aliases(
            spec, role_columns_from_foreign_keys(spec.participations, table, spec.derived),
            ratified=False,
        )
        missing = missing_stage_columns(spec, table)
        if not missing:
            return False
        flags.append(
            PipelineFlag(
                agent="code_generator",
                message=(
                    f"staging model {spec.name!r} was bound to {table_name!r}, which declares "
                    f"none of {', '.join(missing)} that the stage hashes or derives; the binding "
                    f"is refused and the stage reads {RAW_SOURCE_PREFIX + spec.base!r} until a "
                    f"human maps the relation"
                ),
                kind=FlagKind.BINDING_REJECTED,
                asset=spec.name,
                reason=table_name,
            )
        )
        return True

    for spec in specs.values():
        if spec.bound:
            # Declared on the construct itself (Satellite.source_table, WP7 §7.1):
            # bound verbatim at collection time — no inference, no flag.
            continue
        inferred = RAW_SOURCE_PREFIX + spec.base
        # WP82: a binding a human ratified at sign-off is a decision and comes first — over the
        # name rule, the offer, the evidence tier and a ratified proposal alike. Its aliases are
        # already derived (build_staging), so the WP73 check judges the relation with them.
        decided_relation = decided.get(spec.name)
        if decided_relation:
            if _rejected(spec, decided_relation):
                spec.source_model = inferred
            else:
                spec.source_model = decided_relation
                spec.bound = True
            continue
        override = overrides.get(normalize_identifier(spec.base))
        if override and not _rejected(spec, override):
            spec.source_model = override
            spec.bound = True
            continue
        if override:
            spec.source_model = inferred  # the override was refused above, with its flag
            continue
        kept = carried.get(spec.name)
        if kept and normalize_identifier(kept) in declared_tables:
            # WP82: the aliases that travelled with the binding, applied before the check — the
            # carried relation would otherwise be refused for the very column the alias supplied.
            apply_stage_aliases(spec, aliases.get(spec.name) or {})
            if _rejected(spec, kept):
                spec.source_model = inferred
                continue
            table_name = declared_tables[normalize_identifier(kept)].table
            spec.source_model = table_name
            spec.bound = True
            continue
        for table in source_schemas:
            if construct_binds_to_source_table(spec.base, table.table):
                if _rejected(spec, table.table):
                    spec.source_model = inferred
                    break
                spec.source_model = table.table
                spec.bound = True
                break
        else:
            spec.source_model = inferred
            flags.append(
                PipelineFlag(
                    agent="code_generator",
                    message=(
                        f"staging model {spec.name!r} assumes raw source "
                        f"{spec.source_model!r} (no declared source table matched); "
                        f"provide it as a seed/table of that name or correct the binding"
                    ),
                    kind=FlagKind.SOURCE_BINDING,
                    asset=spec.name,
                    reason=reasons.get(normalize_identifier(spec.base), "none"),
                )
            )
    return flags


# WP76: the `inferred` block's schema — dbt renders a source's `schema` with Jinja (dbt-core
# 1.11 `SchemaYamlRenderer.should_render_keypath` exempts only description/loaded_at_query for
# sources), so the block follows the profile's target schema, where seeds land too.
TARGET_SCHEMA_JINJA = "{{ target.schema }}"


@dataclass
class SourceBlock:
    """One dbt ``source:`` block in the generated sources.yml (grounded runs, WP7 §7.2)."""

    name: str  # dbt source name: "raw", then "raw_2", ... in first-appearance order
    database: str | None
    schema_name: str | None
    specs: list[StagingSpec] = field(default_factory=list)


def group_sources(
    specs: dict[str, StagingSpec], source_schemas: list[SourceTable]
) -> list[SourceBlock]:
    """Assign bound staging specs to dbt source blocks (grounded runs only, WP7 §7.2).

    A spec joins a block when its bound relation matches a declared table that carries a
    physical location (``schema_name`` and/or ``database``) — only then is a ``source()``
    reference *better* than the bare relation name (a dbt source without a ``schema``
    property defaults its schema to the source's name, which would silently break the
    verified bare-name/seed pattern; unknowns stay bare and documented, never guessed).
    One block per distinct (database, schema) pair, deterministic: blocks appear in
    staging-spec insertion order, named ``raw``, ``raw_2``, ... Ungrounded runs
    (``source_schemas`` empty) return no blocks — output stays byte-identical."""
    if not source_schemas:
        return []
    declared: dict[str, SourceTable] = {}
    for table in source_schemas:
        declared.setdefault(normalize_identifier(table.table), table)
    blocks: dict[tuple[str | None, str | None], SourceBlock] = {}
    for spec in specs.values():
        if not spec.bound:
            continue
        match = declared.get(normalize_identifier(spec.source_model))
        if match is None or (match.schema_name is None and match.database is None):
            continue
        key = (match.database, match.schema_name)
        block = blocks.get(key)
        if block is None:
            name = "raw" if not blocks else f"raw_{len(blocks) + 1}"
            block = SourceBlock(name=name, database=match.database,
                                schema_name=match.schema_name)
            blocks[key] = block
        block.specs.append(spec)
        spec.source_name = block.name
    return list(blocks.values())


def _reserved_alias(column: str) -> str:
    """WP79's alias for a reserved column, else the column — what the stage hashes by."""
    return stage_column_name(column) if is_reserved_column(column) else column


def _reserved_rewrite(
    spec: StagingSpec, profile: PlatformProfile, relation_columns: list[str] | None = None
) -> tuple[dict[str, str | dict[str, Any]], list[tuple[str, str | list[str] | _HashDiff]]]:
    """WP79: the derived and hashed columns as the stage must declare them when a source column
    is a reserved word. Every reserved column the spec references — hashed, a derived column's
    source, or passed through — gets a derived alias ``<NAME>_: {source_column: <physical>,
    escape: true}`` (AutomateDV then escapes the column wherever it prints it, in the relation's
    spelling), hashed references name the alias (AutomateDV hashes after deriving), and a derived
    column whose source is reserved takes the mapping form. ``relation_columns`` are the bound
    relation's declared columns: `include_source_columns=true` makes AutomateDV select EVERY
    column of the relation, so a reserved name the spec never references still breaks the view
    (the twenty-first chain's `stg_sales_territory` hashed `TERRITORYID` only and failed on
    `group`). Specs without reserved columns come back unchanged — byte-identical output."""
    def alias(column: str) -> str:
        return stage_column_name(column)

    referenced: list[str] = []
    for _, value in spec.hashed:
        cols = value.columns if isinstance(value, _HashDiff) else (
            value if isinstance(value, list) else [value]
        )
        referenced.extend(cols)
    referenced.extend(spec.derived.values())
    referenced.extend(spec.source_columns)
    referenced.extend(normalize_identifier(c) for c in (relation_columns or []))
    reserved = [c for c in dict.fromkeys(referenced) if is_reserved_column(c)]
    if not reserved:
        return dict(spec.derived), list(spec.hashed)
    derived: dict[str, str | dict[str, Any]] = {}
    for name, source in spec.derived.items():
        if is_reserved_column(source):
            derived[name] = {"source_column": profile.physical_name(source), "escape": True}
        else:
            derived[name] = source
    for column in reserved:
        derived.setdefault(
            alias(column), {"source_column": profile.physical_name(column), "escape": True}
        )

    def fix(column: str) -> str:
        return alias(column) if is_reserved_column(column) else column

    hashed: list[tuple[str, str | list[str] | _HashDiff]] = []
    for name, value in spec.hashed:
        if isinstance(value, _HashDiff):
            hashed.append((name, _HashDiff([fix(c) for c in value.columns])))
        elif isinstance(value, list):
            hashed.append((name, [fix(c) for c in value]))
        else:
            hashed.append((name, fix(value)))
    return derived, hashed


def render_stage_model(
    spec: StagingSpec, profile: PlatformProfile | None = None,
    relation_columns: list[str] | None = None,
    null_columns: list[str] | None = None,
) -> str:
    """Render one AutomateDV ``stage`` model (the pattern verified by demo/bank_postgres).
    ``profile`` (WP79) supplies the physical spelling of an escaped reserved column; the
    default platform's when omitted; ``relation_columns`` the bound relation's declared columns."""
    profile = profile or platform_profile(DEFAULT_TARGET_PLATFORM)
    derived, hashed = _reserved_rewrite(spec, profile, relation_columns)
    binding = "declared source schema" if spec.bound else "inferred — see review queue"
    lines = [
        f"-- Generated AutomateDV staging model for the raw-vault constructs on "
        f"'{spec.base}'.",
        "-- Computes the hash keys / hashdiffs the raw-vault models reference and passes",
        f"-- the source columns through (source binding: {binding}).",
        "{{ config(materialized='view') }}",
        "{%- set yaml_metadata -%}",
    ]
    if spec.stage_source:
        # WP36: read the translation model, which already joined the natural key in.
        lines.append(f"source_model: '{spec.stage_source}'")
    elif spec.source_name:
        # source() mapping form (AutomateDV stage: `source_name: table_name`), bound to
        # the matching block in the generated sources.yml (WP7 §7.2, grounded runs).
        lines.append("source_model:")
        lines.append(f"  {spec.source_name}: '{spec.source_model}'")
    else:
        lines.append(f"source_model: '{spec.source_model}'")
    if derived:
        lines.append("derived_columns:")
        for name, source_col in derived.items():
            if isinstance(source_col, dict):
                # WP79: AutomateDV's escaping form — the physical spelling, quoted everywhere.
                lines.append(f"  {name}:")
                lines.append(f"    source_column: '{source_col['source_column']}'")
                lines.append("    escape: true")
            else:
                lines.append(f"  {name}: '{source_col}'")
    if null_columns:
        # WP83: a missing link participant becomes AutomateDV's optional zero key ('-2')
        # before hashing; the original stays as <COL>_ORIGINAL.
        lines.append("null_columns:")
        lines.append("  optional:")
        lines.extend(f"    - '{_reserved_alias(col)}'" for col in null_columns)
    lines.append("hashed_columns:")
    for name, value in hashed:
        if isinstance(value, str):
            lines.append(f"  {name}: '{value}'")
        elif isinstance(value, _HashDiff):
            lines.append(f"  {name}:")
            lines.append("    is_hashdiff: true")
            lines.append("    columns:")
            lines.extend(f"      - '{col}'" for col in value.columns)
        else:
            lines.append(f"  {name}:")
            lines.extend(f"    - '{col}'" for col in value)
    derived_arg = "metadata_dict['derived_columns']" if derived else "none"
    lines.extend(
        [
            "{%- endset -%}",
            "{% set metadata_dict = fromyaml(yaml_metadata) %}",
            "",
            "{{ automate_dv.stage(include_source_columns=true,",
            "                     source_model=metadata_dict['source_model'],",
            f"                     derived_columns={derived_arg},",
            *(
                ["                     null_columns=metadata_dict['null_columns'],"]
                if null_columns else []
            ),
            "                     hashed_columns=metadata_dict['hashed_columns'],",
            "                     ranked_columns=none) }}",
        ]
    )
    return "\n".join(lines) + "\n"


def _stage_metadata(
    spec: StagingSpec, profile: PlatformProfile | None = None,
    relation_columns: list[str] | None = None,
    null_columns: list[str] | None = None,
) -> dict[str, object]:
    profile = profile or platform_profile(DEFAULT_TARGET_PLATFORM)
    derived_columns, hashed_columns = _reserved_rewrite(spec, profile, relation_columns)  # WP79
    hashed: dict[str, object] = {}
    for name, value in hashed_columns:
        if isinstance(value, _HashDiff):
            hashed[name] = {"is_hashdiff": True, "columns": list(value.columns)}
        elif isinstance(value, list):
            hashed[name] = list(value)
        else:
            hashed[name] = value
    meta: dict[str, object] = {
        "source_model": (
            {spec.source_name: spec.source_model} if spec.source_name
            else spec.source_model
        ),
        "source_binding": "declared" if spec.bound else "inferred",
        "hashed_columns": hashed,
        "expected_source_columns": list(spec.source_columns),
    }
    if derived_columns:
        meta["derived_columns"] = dict(derived_columns)
    if spec.ratified_columns:
        meta["ratified_columns"] = dict(spec.ratified_columns)  # WP82
    if spec.role_columns:
        meta["role_columns"] = dict(spec.role_columns)  # WP95: derived by rule, not typed
    if null_columns:
        meta["null_columns"] = {"optional": [_reserved_alias(c) for c in null_columns]}
    if spec.translations and spec.stage_source:
        # WP36: the joins a reader of automatedv.yml must see without opening the SQL.
        meta["key_translation"] = {
            "model": spec.stage_source,
            "joins": [
                {
                    "through_table": t.through_table,
                    "on": f"{_to_column(t.referencing_column)} = "
                          f"{_to_column(t.surrogate_column)}",
                    "projects": column,
                }
                for t, column in zip(spec.translations, spec.translation_columns, strict=True)
            ],
        }
    return meta


def _relation_ref(source_model: str, source_name: str | None) -> str:
    """How generated SQL names a raw relation: the same two forms automate_dv.stage uses."""
    if source_name:
        return f"{{{{ source('{source_name}', '{source_model}') }}}}"
    return f"{{{{ ref('{source_model}') }}}}"


def _relation_test_ref(source_model: str, source_name: str | None) -> str:
    """How a schema.yml test names a relation: the Jinja expression WITHOUT braces.

    ``to: {{ ref('x') }}`` is a YAML flow mapping with an unhashable key — dbt refused to
    parse every project that carried a translated link until the first build ran
    (2026-09-13). dbt's own form for ``relationships.to`` is ``ref('x')`` / ``source(...)``."""
    if source_name:
        return f"source('{source_name}', '{source_model}')"
    return f"ref('{source_model}')"


def _project_homonyms_apart(spec: StagingSpec, relation_columns: list[str]) -> None:
    """WP89: a translated key projected under a name the relation already carries would put the
    column into the view twice (`select t.*, r.ACCOUNTNUMBER as ACCOUNTNUMBER` over
    `SalesOrderHeader`, whose own `AccountNumber` is a financial account). Such a key is projected
    as ``<KEY>_VIA_<THROUGH>`` and every hash key taken over it follows; the relation's own column
    stays what it is, payload included. The hash value does not depend on the column's name."""
    present = {normalize_identifier(c) for c in relation_columns}
    for i, (t, columns) in enumerate(
        zip(spec.translations, spec.translation_columns, strict=True)
    ):
        renamed_all = list(_projected(columns))
        for k, column in enumerate(_projected(columns)):
            if normalize_identifier(column) not in present:
                continue
            renamed = _via_column(column, t.through_table)
            renamed_all[k] = renamed
            for j, (name, value) in enumerate(spec.hashed):
                if isinstance(value, str) and value == column:
                    spec.hashed[j] = (name, renamed)
                elif isinstance(value, list) and column in value:
                    spec.hashed[j] = (name, [renamed if v == column else v for v in value])
            spec.null_groups = [
                (tuple(renamed if c == column else c for c in stage), rel, hub)
                for stage, rel, hub in spec.null_groups
            ]
        spec.translation_columns[i] = (
            renamed_all if isinstance(columns, list) else renamed_all[0]
        )


def translation_model_name(spec: StagingSpec, limit: int | None = None) -> str:
    """``stg_<link>_via_<table>``; several translations join their tables with ``_and_``.

    WP102 (C36): when that name would exceed the platform's identifier ``limit`` — arm T's fifth
    project joined five tables into 103 characters, PostgreSQL ends at 63 — it becomes
    ``stg_<link>_via_<n>_<digest>``: the count of joined relations and six hex digits of a
    SHA-256 over the joined list, deterministic and distinct per list. The joined relations stay
    readable in the view's header, its schema.yml and the stage's ``key_translation`` metadata.
    A name that fits is unchanged, so every existing output is byte-identical."""
    assert spec.translations
    via = "_and_".join(
        normalize_identifier(construct_base_name(t.through_table)).lower()
        for t in spec.translations
    )
    full = f"{spec.name}_via_{via}"
    if limit is None or len(full) <= limit:
        return full
    digest = hashlib.sha256(via.encode("utf-8")).hexdigest()[:6]
    return f"{spec.name}_via_{len(spec.translations)}_{digest}"


def render_translation_model(
    spec: StagingSpec, throughs: list[StagingSpec | None], name: str | None = None
) -> tuple[str, str]:
    """The WP36 translation model and its schema.yml: one LEFT JOIN per translated
    participation, through the referenced relation, so the hub's natural key is available to
    the link's stage model. ``throughs`` is parallel to ``spec.translations``: the spec that
    already stages the referenced relation (the hub's), or ``None`` when nothing stages it.

    LEFT, not INNER: every row of the referencing relation survives, and an unmatched
    surrogate shows as a NULL natural key — which the ``not_null`` test refuses at build time.
    Data-time facts (unmatched surrogates, duplicate matches) are gated by dbt tests, because
    no model-time gate can see rows; nothing is repaired silently (ADR-0013 consequences)."""
    assert spec.translations and len(throughs) == len(spec.translations)
    name = name or translation_model_name(spec)  # WP102: the caller knows the platform's limit
    t_ref = _relation_ref(spec.source_model, spec.source_name)
    single = len(spec.translations) == 1
    joins: list[tuple[str, KeyTranslation, str, str]] = []  # alias, translation, ref, test ref
    for i, (t, through) in enumerate(zip(spec.translations, throughs, strict=True), start=1):
        alias = "r" if single else f"r{i}"
        if through is not None:
            r_ref = _relation_ref(through.source_model, through.source_name)
            r_test = _relation_test_ref(through.source_model, through.source_name)
        else:
            r_ref = _relation_ref(t.through_table, None)
            r_test = _relation_test_ref(t.through_table, None)
        joins.append((alias, t, r_ref, r_test))
    # WP41: parallel to the translations — a role-qualified participation's key is projected as
    # its own role column, so two roles of one hub through one table stay two columns.
    assert len(spec.translation_columns) == len(spec.translations)
    aliases = [
        column
        for columns in spec.translation_columns
        for column in _projected(columns)
    ]
    # WP100: a view projecting one name twice is refused by dbt and by the warehouse — and
    # accepted, it would hash two hubs from one column. Reaching this is a generator defect.
    assert len(set(aliases)) == len(aliases), f"{name} projects a column twice: {aliases}"
    projected = ", ".join(
        f"{alias}.{_to_column(natural)} as {column}"
        for (alias, t, _, _), columns in zip(joins, spec.translation_columns, strict=True)
        for natural, column in zip(t.natural_keys, _projected(columns), strict=True)
    )
    sql_lines = [
        "-- Generated by vault-agent (WP36, ADR-0013): surrogate→natural-key translation for",
        f"-- the link staged by '{spec.name}'.",
    ]
    for _, t, _, _ in joins:
        sql_lines.append(
            f"-- '{spec.source_model}' references '{t.through_table}.{t.surrogate_column}', a "
            f"surrogate; the hub is keyed on '{t.natural_key_label}', the natural key."
        )
    sql_lines += [
        "-- This view joins the natural key(s) in so the stage model can hash the link from",
        "-- them. LEFT JOIN: every source row survives; an unmatched surrogate becomes a NULL",
        f"-- natural key, which {name}.yml's not_null test refuses at build time. The",
        "-- translation is visible here, never hidden in a mapping.",
        "{{ config(materialized='view') }}",
        "",
        f"select t.*, {projected}",
        f"from {t_ref} t",
    ]
    sql_lines += [
        f"left join {r_ref} {alias} on t.{_to_column(t.referencing_column)} = "
        f"{alias}.{_to_column(t.surrogate_column)}"
        for alias, t, r_ref, _ in joins
    ]
    description = "; ".join(
        f"{spec.source_model} joined to {t.through_table} on "
        f"{_to_column(t.referencing_column)} = {_to_column(t.surrogate_column)}, projecting "
        f"{', '.join(_to_column(c) for c in t.natural_keys)}"
        for _, t, _, _ in joins
    )
    test_lines = [
        "# Generated by vault-agent (WP36): the data-time gates of a surrogate→natural-key",
        "# translation. An unmatched surrogate or a dangling reference fails `dbt build` here,",
        "# before the link hashes a NULL key.",
        "version: 2",
        "",
        "models:",
        f"  - name: {name}",
        f"    description: \"{description} for the link's hash (ADR-0013).\"",
        "    columns:",
    ]
    for (_, t, _, r_test), columns in zip(joins, spec.translation_columns, strict=True):
        # WP93: a NULL surrogate is a NULL participant, not a dangling reference — the key may
        # be NULL exactly where the surrogate is; `relationships` ignores NULL by itself.
        for column in _projected(columns):
            test_lines += [
                f"      - name: {column}",
                "        tests:",
                "          - not_null:",
                "              config:",
                f"                where: \"{_to_column(t.referencing_column)} is not null\"",
            ]
        test_lines += [
            f"      - name: {_to_column(t.referencing_column)}",
            "        tests:",
            "          - relationships:",
            f"              to: {r_test}",
            f"              field: {_to_column(t.surrogate_column)}",
        ]
    return "\n".join(sql_lines) + "\n", "\n".join(test_lines) + "\n"


# Contract data_type -> ABSTRACT seed column type (WP7 §7.3), spelled the Postgres way
# because that output is the pinned baseline; `rules/platforms.py` translates it into the
# target platform's physical type (WP35). JSON Schema base types only; "string" is
# refined by a `format` semantic (date / date-time) below.
# Unmapped types (unknown/object/array/null) are OMITTED — dbt seed inference, as before;
# absence of knowledge stays visible, never papered over with a guess.
_SEED_TYPE_BY_JSON_TYPE = {
    "string": "varchar",
    "integer": "bigint",
    "number": "numeric",
    "boolean": "boolean",
}


def _seed_type(contract_field: dict[str, Any]) -> str | None:
    """Map one contract field to a seed column type, or None to omit (never guess)."""
    constraints = contract_field.get("constraints") or {}
    data_type: Any = constraints.get("data_type", "unknown")
    if isinstance(data_type, list):
        # Unions take the non-null member; anything ambiguous is omitted.
        non_null = [t for t in data_type if t != "null"]
        if len(non_null) != 1:
            return None
        data_type = non_null[0]
    if data_type == "string":
        fmt = next(
            (
                s.get("value")
                for s in contract_field.get("semantics", [])
                if isinstance(s, dict) and s.get("kind") == "format"
            ),
            None,
        )
        if fmt == "date":
            return "date"
        if fmt == "date-time":
            return "timestamp"
    return _SEED_TYPE_BY_JSON_TYPE.get(str(data_type))


def _collect_seed_column_types(
    specs: dict[str, StagingSpec],
    contracts: list[dict[str, Any]],
    profile: PlatformProfile,
) -> dict[str, dict[str, str]]:
    """Seed column types per staging source, from the drafted data contracts (WP7 §7.3).

    A staging spec picks up the contract whose ``name`` matches its ``source_model``
    (normalised) — on grounded runs the contracts are per source table, so the names
    line up; ungrounded entity contracts match nothing and change nothing. Column names
    are normalised to the UPPER_SNAKE seed headers; ``LOAD_DATETIME`` / ``RECORD_SOURCE``
    are always typed timestamp / varchar (every raw relation carries them). Every type
    goes through ``profile.seed_type`` — the contract's abstract type becomes the target
    platform's physical one (WP35), never a spelling one warehouse happens to accept."""
    by_name: dict[str, dict[str, Any]] = {}
    for contract in contracts:
        name = contract.get("name")
        if isinstance(name, str):
            by_name.setdefault(normalize_identifier(name), contract)
    column_types: dict[str, dict[str, str]] = {}
    for spec in specs.values():
        matched = by_name.get(normalize_identifier(spec.source_model))
        if matched is None:
            continue  # no contract match -> no column_types (dbt inference, as today)
        columns: dict[str, str] = {}
        raw_fields = matched.get("schema", [])
        if not isinstance(raw_fields, list):
            raw_fields = []
        for contract_field in raw_fields:
            if not isinstance(contract_field, dict):
                continue
            label = contract_field.get("name")
            if not isinstance(label, str):
                continue
            seed_type = _seed_type(contract_field)
            if seed_type is not None:
                columns[_to_column(label)] = profile.seed_type(seed_type)
        columns[LOAD_DATETIME_COLUMN] = profile.seed_type("timestamp")
        columns[RECORD_SOURCE_COLUMN] = profile.seed_type("varchar")
        column_types[spec.source_model] = columns
    return column_types


def _render_dbt_project(
    seed_column_types: dict[str, dict[str, str]],
    business_vault: BusinessVaultOptions | None = None,
) -> str:
    pit = business_vault is not None and business_vault.pit
    business_block = (
        "    # WP91 (ADR-0016): point-in-time tables, rebuilt whole over the as-of spine.\n"
        "    business_vault:\n"
        "      +materialized: table\n"
    ) if pit else ""
    vars_block = (
        "\nvars:\n"
        "  # WP91: every standard satellite carries AutomateDV's ghost record, the row a PIT's\n"
        "  # ghost entry points at (binary_ghost / date_ghost — the same values the PIT writes).\n"
        "  enable_ghost_records: true\n"
    ) if pit else ""
    return f"""# Generated by vault-agent — dbt project scaffolding for the generated Data Vault.
# Define a matching connection profile named '{PROJECT_NAME}' in profiles.yml
# (see README.md); then: dbt deps && dbt build.
name: '{PROJECT_NAME}'
version: '1.0.0'
config-version: 2

profile: '{PROJECT_NAME}'

model-paths: ["models"]
seed-paths: ["seeds"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
macro-paths: ["macros"]

target-path: "target"
clean-targets:
  - "target"
  - "dbt_packages"

models:
  {PROJECT_NAME}:
    staging:
      # Thin view layer (hash keys / hashdiffs); no need to persist it.
      +materialized: view
    raw_vault:
      # The generated models already carry config(materialized='incremental');
      # this is a belt-and-braces default.
      +materialized: incremental
{business_block}{vars_block}
seeds:
  {PROJECT_NAME}:
    # Keep seed column headers UNQUOTED so UPPER_SNAKE identifiers fold consistently
    # with the (also unquoted) identifiers AutomateDV emits (verified on Postgres —
    # see demo/bank_postgres in the vault-agent repo).
    +quote_columns: false
""" + _render_seed_column_types(seed_column_types)


def _render_seed_column_types(seed_column_types: dict[str, dict[str, str]]) -> str:
    """The per-seed ``+column_types`` blocks (WP7 §7.3); empty when no contract matched,
    keeping ungrounded/contract-less output byte-identical."""
    if not seed_column_types:
        return ""
    lines = [
        "    # Column types pinned from the drafted data contracts (never inferred);",
        "    # columns with an undetermined contract type are omitted and left to dbt's",
        "    # seed inference, so a gap stays visible instead of being guessed at.",
    ]
    for seed_name, columns in seed_column_types.items():
        lines.append(f"    {seed_name}:")
        lines.append("      +column_types:")
        for column, seed_type in columns.items():
            lines.append(f"        {column}: {seed_type}")
    return "\n".join(lines) + "\n"


def _render_packages(business_vault: BusinessVaultOptions | None = None) -> str:
    utils = (
        "  # WP91: the as-of spine is dbt_utils.date_spine (the version AutomateDV resolves).\n"
        "  - package: dbt-labs/dbt_utils\n"
        f"    version: {DBT_UTILS_VERSION}\n"
    ) if business_vault is not None and business_vault.pit else ""
    return f"""# Generated by vault-agent. AutomateDV (Datavault-UK) — the OSS dbt package whose
# hub/link/sat/eff_sat/stage macros the generated models call. Pinned to the version
# the generator's output is verified against; bump deliberately.
packages:
  - package: Datavault-UK/automate_dv
    version: {AUTOMATE_DV_VERSION}
""" + utils


def _merge_source_tables(
    specs: Iterable[StagingSpec],
) -> list[tuple[str, list[str], bool]]:
    """Collapse staging specs that read the SAME raw relation into one source entry.

    Several staging models can legitimately bind to one physical table — e.g. a hub's
    staging plus a satellite whose ``source_table`` names the hub's own relation, or a
    hub and a standard satellite the modeller named off the same base. A dbt
    ``sources.yml`` (and the documented interface it renders) must list each table
    exactly ONCE: dbt raises a compilation error on two source tables with the same name.
    Returns ``(source_model, expected columns unioned in first-appearance order,
    all_bound)`` per distinct relation, in first-appearance order — so the output stays
    byte-identical when every spec already has a distinct ``source_model``."""
    merged: dict[str, list[str]] = {}
    bound: dict[str, bool] = {}
    order: list[str] = []
    for spec in specs:
        if spec.source_model not in merged:
            merged[spec.source_model] = []
            bound[spec.source_model] = True
            order.append(spec.source_model)
        cols = merged[spec.source_model]
        for col in spec.source_columns:
            if col not in cols:
                cols.append(col)
        bound[spec.source_model] = bound[spec.source_model] and spec.bound
    return [(name, merged[name], bound[name]) for name in order]


def _render_sources_yml(
    specs: dict[str, StagingSpec], blocks: list[SourceBlock]
) -> str:
    if blocks:
        # Grounded run with declared physical locations (WP7 §7.2): REAL source blocks —
        # the staging models listed under them reference their table via source().
        lines = [
            "# Generated by vault-agent — dbt sources for the declared raw inputs "
            "(ADR-0004).",
            "#",
            "# Grounded run: staging models whose declared source table carries a "
            "physical",
            "# location (schema/database) reference it through automate_dv.stage's "
            "source()",
            "# mapping form (`source_model: {<source name>: <table>}`), bound to the "
            "blocks",
            "# below. Relations in the trailing comment are still referenced by BARE "
            "name",
            "# (a seed, model, or table in the target schema).",
            "version: 2",
            "",
            "sources:",
        ]
        in_blocks = {spec.name for block in blocks for spec in block.specs}
        for block in blocks:
            lines.append(f"  - name: {block.name}")
            if block.name == INFERRED_SOURCE_NAME:
                lines.append(
                    "    # WP76: relations no declared table matched (see the SOURCE_BINDING /"
                )
                lines.append(
                    "    # BINDING_REJECTED review items). Declared here so the project parses;"
                )
                lines.append(
                    "    # provide each as a table or view of that name in the target schema."
                )
            if block.database is not None:
                lines.append(f"    database: {block.database}")
            if block.schema_name is not None:
                schema = block.schema_name
                if "{{" in schema:
                    schema = f'"{schema}"'  # Jinja is a YAML flow mapping unless quoted
                lines.append(f"    schema: {schema}")
            lines.append("    tables:")
            for source_model, source_columns, _ in _merge_source_tables(block.specs):
                lines.append(f"      - name: {source_model}")
                cols = ", ".join(source_columns)
                lines.append(f"        # expected columns: {cols}")
        bare = [spec for spec in specs.values() if spec.name not in in_blocks]
        if bare:
            lines.append("")
            lines.append(
                "# Referenced by BARE relation name (no declared physical location):"
            )
            for spec in bare:
                note = "" if spec.bound else " — inferred binding, review"
                lines.append(f"#   - {spec.source_model} (feeds {spec.name}){note}")
        return "\n".join(lines) + "\n"

    lines = [
        "# Generated by vault-agent — the raw inputs the staging layer expects.",
        "#",
        "# The stg_* models reference their raw input by BARE relation name (a seed, model,",
        "# or table in the target schema named like `source_model` below). This file",
        "# DOCUMENTS that interface. To bind to an external schema instead, set database/",
        "# schema here and switch the staging model's source_model to a source() mapping",
        "# (automate_dv.stage accepts `source_model: {source_name: table_name}`).",
        "version: 2",
        "",
        "sources:",
        "  - name: raw",
        "    # database: <set me>",
        "    # schema: <set me>",
        "    tables:",
    ]
    for source_model, source_columns, all_bound in _merge_source_tables(specs.values()):
        lines.append(f"      - name: {source_model}")
        cols = ", ".join(source_columns)
        lines.append(f"        # expected columns: {cols}")
        if not all_bound:
            lines.append(
                "        # NOTE: inferred binding (no declared source table matched) — review"
            )
    return "\n".join(lines) + "\n"


def _render_platform_section(profile: PlatformProfile) -> str:
    """The README's target-platform section (WP35) — present only when the run chose a
    platform other than the default. The default's README is the pinned baseline and says
    'any AutomateDV-supported warehouse', which stays true; a chosen platform is a decision
    the operator should see named, with the adapter and profile shape it implies."""
    if profile.name == DEFAULT_TARGET_PLATFORM:
        return ""
    return f"""
## Target platform: {profile.name}

This project was generated for **{profile.name}** (`--target-platform {profile.name}`):
the seed column types in `dbt_project.yml` use its native types. The models themselves
are platform-neutral — AutomateDV dispatches per adapter. Install `{profile.dbt_adapter}`
and give the `{PROJECT_NAME}` profile a target of `type: {profile.profile_type}` with
{profile.profile_hint}.
"""


def _render_readme(specs: dict[str, StagingSpec], profile: PlatformProfile) -> str:
    inputs = "\n".join(
        f"- `{spec.source_model}` → feeds `{spec.name}` "
        f"(expected columns: {', '.join(spec.source_columns)})"
        for spec in specs.values()
    )
    return f"""# Generated Data Vault project (vault-agent)

A runnable dbt project: `models/staging/` computes the hash keys / hashdiffs via
AutomateDV's `stage` macro, `models/raw_vault/` holds the generated hubs, links, and
satellites. Review `review-queue.md` and `contracts/` before agreeing the model.

## Provide the raw inputs

Each staging model reads one raw relation by name — provide it either as a dbt seed
(`seeds/<name>.csv`, headers exactly as listed) or as a table/view in the target schema:

{inputs}

Every raw relation must also carry `{LOAD_DATETIME_COLUMN}` and `{RECORD_SOURCE_COLUMN}`.

## Run it

1. Define a `{PROJECT_NAME}` profile in `profiles.yml` (any AutomateDV-supported warehouse).
2. `dbt deps`
3. `dbt seed` (if using seeds), then `dbt build`.
""" + _render_platform_section(profile)


def build_staging(
    model: DVModel,
    source_schemas: list[SourceTable],
    contracts: list[dict[str, Any]] | None = None,
    source_overrides: dict[str, str] | None = None,
    existing: DVModel | None = None,
    target_platform: TargetPlatform = DEFAULT_TARGET_PLATFORM,
    binding_reasons: dict[str, str] | None = None,
    carried: list[SourceTable] | None = None,
    carried_bindings: dict[str, str] | None = None,
    business_vault: BusinessVaultOptions | None = None,
    ratified_bindings: dict[str, StageBinding] | None = None,
    carried_aliases: dict[str, dict[str, str]] | None = None,
) -> StagingResult:
    """The full staging pass: specs -> bindings -> rendered models + scaffolding.

    ``ratified_bindings`` (WP82) are the stages a human bound at sign-off, by stage name — the
    relation and its aliases; ``carried_aliases`` the aliases earlier increments ratified, applied
    with ``carried_bindings``. Both empty on every run no human bound a stage in.

    ``business_vault`` (WP91) adds to the scaffolding what a PIT needs — AutomateDV ghost records,
    the `business_vault` model block, `dbt_utils` — and nothing when it is off or ``None``.

    ``contracts`` (``state.artifacts.contracts``, drafted by the data-contract agent —
    which runs BEFORE the code generator in the graph) pins seed column types for
    staging sources whose contract matches by name (WP7 §7.3).

    ``source_overrides`` (WP9 §6) binds specs to the source tables a ratified/proposed
    business↔source mapping resolved them to (the source_mapper's re-bind); ``None`` /
    empty leaves the WP7 inference untouched, so unmapped runs stay byte-identical.

    ``existing`` (WP23 §2.6) is the vault being extended: feeds it already carried keep
    their legacy staging names instead of gaining a WP10 source suffix. ``None`` =
    greenfield, where nothing is grandfathered and naming is symmetric.

    ``target_platform`` (WP35) selects the seed-type dialect and the README's profile
    hint; the rendered models are identical across platforms. The default is the
    byte-identity baseline."""
    legacy = legacy_feeds(existing, carried_bindings)  # WP101: the carried catalogue too
    specs = collect_staging_specs(
        model, legacy,
        frozenset(s.name for s in existing.satellites) if existing is not None else frozenset(),
    )
    # WP82: a human's aliases are part of the stage before anything judges its binding.
    for stage_name, binding in (ratified_bindings or {}).items():
        if stage_name in specs:
            apply_stage_aliases(specs[stage_name], binding.columns)
    # WP74: an existing construct's stage binds against the catalogue earlier increments
    # carried in (schema, database, full columns), the increment's own tables first. The
    # carried tables reach nothing else — the contract agent, the proposer and the modeler
    # still see `source_schemas` alone.
    seen_tables = {(t.schema_name, normalize_identifier(t.table)) for t in source_schemas}
    binding_schemas = list(source_schemas) + [
        t for t in (carried or [])
        if (t.schema_name, normalize_identifier(t.table)) not in seen_tables
    ]
    # WP77: the bindings earlier increments made travel with the catalogue, kept unless this
    # run's own resolution binds the stage (the offer tier and the proposals see only the
    # increment's tables, so a link bound by offer in step 3 would otherwise infer in step 4).
    flags = bind_sources(
        specs, binding_schemas, source_overrides, binding_reasons, carried_bindings,
        ratified={name: b.relation for name, b in (ratified_bindings or {}).items()},
        carried_aliases=carried_aliases,
    )
    # Grounded runs only (ungrounded: no blocks, no source_name — byte-identical output).
    blocks = group_sources(specs, binding_schemas)
    if blocks:
        # WP76: a project that addresses its declared inputs through source() declares its
        # INFERRED relations the same way, under one block in the target schema — AutomateDV
        # turns a bare name into a ref(), and one unresolvable ref() made the nineteenth
        # chain's fifth project unparseable. Without a block (seed world) the bare name stays
        # the verified pattern. The flags still say what a human must provide.
        inferred = SourceBlock(name=INFERRED_SOURCE_NAME, database=None,
                               schema_name=TARGET_SCHEMA_JINJA)
        for spec in specs.values():
            if not spec.bound:
                spec.source_name = INFERRED_SOURCE_NAME
                inferred.specs.append(spec)
        if inferred.specs:
            blocks.append(inferred)
    profile = platform_profile(target_platform)
    seed_column_types = _collect_seed_column_types(specs, contracts or [], profile)
    # WP36: one translation model per link whose target key is a join away. Rendered
    # BEFORE the stage models so each such stage reads its translation model; the referenced
    # relation's binding is taken from the spec that already stages it (the hub's), so the
    # two can never disagree about where that relation lives.
    translations: dict[str, str] = {}
    translation_tests: dict[str, str] = {}
    by_relation = {
        normalize_identifier(s.source_model): s for s in specs.values() if s.bound
    }
    # WP79: the bound relation's declared columns, so a reserved name the spec never references
    # is escaped too (AutomateDV selects every column of the relation).
    declared_columns = {
        normalize_identifier(t.table): list(t.column_names) for t in binding_schemas
    }
    for spec in specs.values():
        if not spec.translations:
            continue
        if spec.bound:
            _project_homonyms_apart(
                spec, declared_columns.get(normalize_identifier(spec.source_model), [])
            )
        throughs = [
            by_relation.get(normalize_identifier(t.through_table)) for t in spec.translations
        ]
        name = translation_model_name(spec, profile.max_identifier_length)  # WP102
        sql, tests = render_translation_model(spec, throughs, name)
        translations[name] = sql
        translation_tests[f"models/staging/{name}.yml"] = tests
        spec.stage_source = name

    def relation_columns(spec: StagingSpec) -> list[str] | None:
        return declared_columns.get(normalize_identifier(spec.source_model)) if spec.bound else None

    # WP83: the bound relation itself, for the declared types the zero-key rule reads.
    declared_tables = {normalize_identifier(t.table): t for t in binding_schemas}

    def null_columns(spec: StagingSpec) -> list[str]:
        return null_optional_columns(
            spec, declared_tables.get(normalize_identifier(spec.source_model)), declared_tables
        )

    models = {
        name: render_stage_model(spec, profile, relation_columns(spec), null_columns(spec))
        for name, spec in specs.items()
    }
    models.update(translations)
    metadata = {
        name: _stage_metadata(spec, profile, relation_columns(spec), null_columns(spec))
        for name, spec in specs.items()
    }
    # WP86: a zero-key view and stage per hub a zero-keyed participation reaches.
    zero_hubs: dict[str, str] = {}
    hubs_by_name = {hub.name: hub for hub in model.hubs}
    for hub_name, columns in zero_key_hubs(model, specs, declared_tables).items():
        hub = hubs_by_name[hub_name]
        from vault_agent.agents.code_generator import _hub_hashkey

        view = zero_key_model_name(hub)
        stage = StagingSpec(name=zero_key_stage_name(hub), base=_base_name(hub.name),
                            source_model=view)
        key_columns = [col for col, _ in columns]
        stage.add_hashed(_hub_hashkey(hub), key_columns if len(key_columns) > 1 else key_columns[0])
        for col in key_columns:
            stage.add_source_column(col)
        stage.add_source_column(LOAD_DATETIME_COLUMN)
        stage.add_source_column(RECORD_SOURCE_COLUMN)
        type_stage = (
            multi_source_staging_name(hub, hub.sources[0], legacy) if hub.sources
            else _staging_name(hub.name)
        )
        models[view] = render_zero_key_model(hub, columns, profile, type_stage)
        models[stage.name] = render_stage_model(stage, profile).replace(
            "(source binding: inferred — see review queue)",
            f"(source binding: generated — {view}, WP86)",
        )
        stage_meta = _stage_metadata(stage, profile)
        stage_meta["source_binding"] = "generated"
        metadata[stage.name] = stage_meta
        zero_hubs[hub_name] = stage.name
    # WP102 (C36): a relation name over the platform's limit is refused by the warehouse; a
    # translation name was shortened above, any other long name is the construct's own and is
    # flagged, never truncated — a truncated name is a different model than every reference.
    for long_name in sorted(n for n in models if len(n) > profile.max_identifier_length):
        flags.append(PipelineFlag(
            agent="code_generator",
            message=(
                f"staging model {long_name!r} is {len(long_name)} characters long; "
                f"{profile.name} identifiers end at {profile.max_identifier_length}, so the "
                f"warehouse will refuse the relation — the construct it stages needs a shorter "
                f"name"
            ),
            kind=FlagKind.GENERATION_GAP,
            asset=long_name,
        ))
    scaffolding = {
        "dbt_project.yml": _render_dbt_project(seed_column_types, business_vault),
        "packages.yml": _render_packages(business_vault),
        "models/staging/sources.yml": _render_sources_yml(specs, blocks),
        "README.md": _render_readme(specs, profile),
        **translation_tests,
    }
    return StagingResult(
        models=models, metadata=metadata, scaffolding=scaffolding, flags=flags,
        zero_key_hubs=zero_hubs,
    )


def unresolved_raw_vault_refs(models: dict[str, str], staging: dict[str, str]) -> list[str]:
    """WP101 (C34): the raw-vault models whose ``source_model`` — a bare name or a list — or
    whose ``ref()`` names no rendered staging or raw-vault model. Arm A's fifth project carried
    `sat_unit_measure_details` reading `stg_unit_measure`, which that step no longer rendered;
    `project_self_contained` had looked at the staging layer only. Pure; names out, sorted."""
    known = set(models) | set(staging)
    unresolved: list[str] = []
    for name, sql in models.items():
        named: list[str] = []
        setting = re.search(r'set source_model = (\[[^\]]*\]|"[^"]+")', sql)
        if setting:
            named += re.findall(r'"(\w+)"', setting.group(1))
        named += re.findall(r"ref\('(\w+)'\)", sql)
        if any(ref not in known for ref in named):
            unresolved.append(name)
    return sorted(unresolved)


def unresolved_stage_refs(models: dict[str, str], sources_yml: str) -> list[str]:
    """The staging models whose relation dbt cannot resolve at parse time (WP74 §2.5, corrected
    2026-10-17): a ``source()`` mapping whose block or table the generated ``sources.yml`` does
    not declare, or a bare name that is not another staging model — an inferred ``raw_*``
    relation included. The nineteenth chain's fifth project failed `dbt parse` on
    `ref('raw_sales_order')`: AutomateDV's stage macro turns a bare name into a `ref()`, so an
    inferred relation is not "a table in the target schema" to dbt but a missing node, and one
    is enough to make the whole project unparseable. Since WP76 a grounded project declares its
    inferred relations under the ``inferred`` block, so they resolve here — resolution is a
    parse-time fact; ``stage_refs_inferred`` still counts what a human must provide. Pure: a
    rendered project in, names out, sorted."""
    import yaml as _yaml

    parsed = _yaml.safe_load(sources_yml) or {}
    blocks: dict[str, set[str]] = {}
    for block in parsed.get("sources") or []:
        blocks[str(block.get("name"))] = {
            normalize_identifier(str(t.get("name"))) for t in (block.get("tables") or [])
        }
    unresolved: list[str] = []
    for name, sql in models.items():
        bad = False
        mapping = re.search(r"source_model:\s*\n\s+(\w+): '([^']+)'", sql)
        if mapping:
            block, table = mapping.group(1), normalize_identifier(mapping.group(2))
            bad = table not in blocks.get(block, set())
        else:
            bare = re.search(r"source_model:\s*'?([\w.]+)'?", sql)
            if bare and bare.group(1) not in models:
                bad = True
        # A translation view (WP36) joins relations with Jinja refs of its own: every ref() must
        # be a staging model, every source() a declared block and table — the nineteenth
        # chain's fifth project failed its parse on such a `ref('raw_document_product')`.
        for ref in re.findall(r"ref\('(\w+)'\)", sql):
            if ref not in models:
                bad = True
        for block, table in re.findall(r"source\('(\w+)',\s*'([^']+)'\)", sql):
            if normalize_identifier(table) not in blocks.get(block, set()):
                bad = True
        if bad:
            unresolved.append(name)
    return sorted(unresolved)
