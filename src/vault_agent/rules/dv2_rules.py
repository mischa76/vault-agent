"""Encoded DV2.0/2.1 rules the Modeler and Validator use.

Keep in pure Python so they are unit-testable and not subject to LLM hallucination.
"""
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


def normalize_identifier(label: str) -> str:
    """Normalise a business label into a SQL identifier (UPPER_SNAKE).

    Single source of truth for identifier normalisation: the code generator renders columns
    with it, and source-schema grounding (ADR-0004) matches proposed keys/attributes to real
    columns with it, so ``"national customer ID"`` grounds against a ``NATIONAL_CUSTOMER_ID``
    column."""
    return re.sub(r"[^0-9a-zA-Z]+", "_", label).strip("_").upper()


def construct_base_from_table(table: str) -> str:
    """A source table's name as a construct base: ``ProductVendor`` -> ``product_vendor``.

    Construct names are lowercase snake_case (``CONSTRUCT_NAME_PATTERN``); source tables are
    often CamelCase, and ``normalize_identifier`` alone would fold ``ProductVendor`` to
    ``productvendor`` (WP37 named its first link that way). CamelCase boundaries become
    underscores first — ``SalesOrderDetail`` -> ``sales_order_detail``, ``HTMLParser`` ->
    ``html_parser`` — then the ordinary normalisation applies. One place, because a link named
    from a table and a hub named by the modeler must fold to the same base or the binder
    (``construct_binds_to_source_table``) cannot see that they are the same table."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", table)
    return normalize_identifier(spaced).lower()


# Well-formed construct names (WP20 §2.1). A construct name is not decoration: it becomes a
# dbt model name, a file on disk (``<name>.sql``), and the stem of the staging model feeding
# it. DV2.0 convention prefixes the construct kind (hub_/link_/sat_ — the prefix the
# generators strip to derive the staging base), and dbt/warehouse portability wants plain
# lowercase snake_case: a space or a dot breaks the dbt ``ref()``, a path separator or ``..``
# would write outside the output directory. Single source of truth for the pattern; the
# validator gates on it (E_BAD_NAME) so the modeler's re-model loop can fix it, and
# ``cli.write_outputs`` re-checks the filename components as defense in depth.
CONSTRUCT_NAME_PATTERN = r"^(hub|link|sat)_[a-z0-9][a-z0-9_]*$"
_CONSTRUCT_NAME_RE = re.compile(CONSTRUCT_NAME_PATTERN)


def is_valid_construct_name(name: str) -> bool:
    """True when ``name`` is a well-formed hub/link/satellite name (see the pattern above)."""
    return bool(_CONSTRUCT_NAME_RE.match(name))


REQUIRED_HUB_COLUMNS = {"hash_key", "business_key", "load_date_time", "record_source"}
REQUIRED_LINK_COLUMNS = {"hash_key", "load_date_time", "record_source"}
REQUIRED_SAT_COLUMNS = {"hash_key", "load_date_time", "record_source", "hash_diff"}

# Heuristics a candidate must satisfy to qualify as a Data Vault business key.
# Single source of truth: agents inject these into their prompt rather than
# hard-coding DV2.0 rules in the prompt text (see CLAUDE.md).
BUSINESS_KEY_CRITERIA = [
    "Stable over time — the natural identifier does not change for a given object",
    "Unique within the business object's universe (it isolates exactly one instance)",
    "Recognised and used by the business, preferred over a surrogate or system-generated key",
    "Not nullable — every instance of the object carries a value",
]

# The axes attributes are grouped by (and split across) satellites. One satellite holds
# attributes that belong together on ALL axes; split where they diverge. Canon: Linstedt &
# Olschimke, satellite splitting.
SATELLITE_SPLIT_AXES = [
    "rate of change",
    "source system",
    "data classification (e.g. PII / sensitivity)",
    "data type",
]

# Heuristic threshold: a satellite with more attributes than this is *flagged* (W_SAT_WIDE)
# for possible splitting — a smell that prompts human review, never a hard failure.
SAT_WIDE_ATTRIBUTE_THRESHOLD = 30

# Hint tokens marking the two ends of an active-period (from/to) date pair. Single source of
# truth for the validator's W_SAT_MAYBE_EFFECTIVITY heuristic, which spots a *standard*
# satellite on a link that carries such a pair (it should likely be an effectivity satellite).
# Matched against normalize_identifier(attr): a single-word token matches one of the
# underscore-separated stems (so "FROM" matches "EFFECTIVE_FROM"); a multi-word token matches
# as a contiguous substring.
EFFECTIVITY_FROM_TOKENS = {"FROM", "START", "BEGIN", "VALID_FROM", "EFFECTIVE_FROM"}
EFFECTIVITY_TO_TOKENS = {"TO", "END", "VALID_TO", "EFFECTIVE_TO"}


def _matches_tokens(attr: str, tokens: set[str]) -> bool:
    """True if ``attr`` (normalised) matches one of ``tokens`` by stem or substring."""
    norm = normalize_identifier(attr)
    if norm in tokens or set(norm.split("_")) & tokens:
        return True
    return any("_" in token and token in norm for token in tokens)


def effectivity_date_pair(attributes: list[str]) -> tuple[str, str] | None:
    """Return the ``(from, to)`` attributes if these look like one active-period date pair.

    A pair is exactly one "from"-token match and one "to"-token match across ``attributes``
    (see :data:`EFFECTIVITY_FROM_TOKENS` / :data:`EFFECTIVITY_TO_TOKENS`); anything else
    (zero, or ambiguous multiples) returns ``None``. Heuristic by design: a *non-match* only
    ever warns (W_SAT_MAYBE_EFFECTIVITY, W_EFFSAT_DATE_ORDER_UNVERIFIED) — but a positive,
    recognisably *reversed* match is safe to fail on (E_EFFSAT_DATE_ORDER)."""
    from_matches = [a for a in attributes if _matches_tokens(a, EFFECTIVITY_FROM_TOKENS)]
    to_matches = [a for a in attributes if _matches_tokens(a, EFFECTIVITY_TO_TOKENS)]
    if len(from_matches) == 1 and len(to_matches) == 1:
        return from_matches[0], to_matches[0]
    return None

@dataclass(frozen=True)
class SteeringRule:
    """One prompt-steering line the modeler is given, with its provenance (WP16 §2.1).

    Parts of the harness exist because *current* models failed — the CDK line landed only
    after LLM steering failed 4/4, the effectivity two-dates line has a generator-side
    rejection behind it. That is correct belt-and-braces engineering, but it is
    model-compensation, and an anonymous ``list[str]`` cannot answer "does the next model
    still need this?". Naming each line makes it ablatable (:func:`active_modeling_rules`)
    and countable against its ``backstop``.

    - ``id``: stable snake_case handle (``eval.ablate --drop <id>``, ledger row key)
    - ``text``: the prompt line itself, byte-identical to what shipped before WP16
    - ``backstop``: the deterministic pre-gate repair that catches this failure when the
      steering does not — the thing whose fire count says whether the rule is still earning
      its place. ``None`` where steering stands alone.
    - ``origin``: WP/date and what it cost to learn (read before deleting anything)

    Validator gates are deliberately NOT in scope here: they are the product (auditable,
    deterministic E_/W_ codes an enterprise DV2.0 tool owes its users), not
    model-compensation. Only prompt lines and pre-gate backstops are measurable-and-deletable.
    """

    id: str
    text: str
    backstop: str | None = None
    origin: str = ""


# Structural rules the DV2.0 Modeler applies when turning business objects and keys
# into hubs, links, and satellites. Injected into the modeler prompt at runtime so the
# rule set stays a single source of truth (see CLAUDE.md).
DV_MODELING_RULES = [
    SteeringRule(
        id="one_hub_per_key",
        text="Create exactly one hub per business key — one hub is one concept with one "
        "natural key",
        origin="canon (Linstedt/Olschimke); gated by E_DUP_HUB (WP1, 2026-07-08)",
    ),
    SteeringRule(
        id="hub_no_attributes",
        text="Hubs hold only the business key plus DV technical columns; never descriptive "
        "attributes",
        origin="canon (Linstedt/Olschimke)",
    ),
    SteeringRule(
        id="link_per_relationship",
        text="Create a link for each relationship between objects; a link connects two or "
        "more hubs",
        origin="canon (Linstedt/Olschimke)",
    ),
    SteeringRule(
        id="link_no_attributes",
        text="Links hold only references to their hubs — no descriptive attributes, no "
        "business keys",
        origin="canon (Linstedt/Olschimke)",
    ),
    SteeringRule(
        id="attributes_in_satellites",
        text="Put descriptive, changing attributes in satellites; each satellite hangs off "
        "one parent",
        origin="canon (Linstedt/Olschimke)",
    ),
    SteeringRule(
        id="satellite_split_axes",
        text=f"Split satellites along these axes — {', '.join(SATELLITE_SPLIT_AXES)}; one "
        f"satellite holds attributes that belong together on all of them, split where they "
        f"diverge",
        origin="canon (satellite splitting); W_SAT_WIDE flags the smell",
    ),
    SteeringRule(
        id="no_object_link_confusion",
        text="Do not model a stand-alone object as a link, and do not model a relationship "
        "as a hub",
        origin="canon (Linstedt/Olschimke)",
    ),
    SteeringRule(
        id="unit_of_work",
        text="A link represents exactly one Unit of Work — the business keys of one atomic "
        "business event; never split one event across links nor merge unrelated "
        "relationships into one link",
        origin="dv2-modeling-rules-spec (2026-06-13); W_LINK_REDUNDANT_GRAIN",
    ),
    SteeringRule(
        id="degenerate_attributes",
        text="Degenerate attributes of the relationship itself (e.g. an order-line sequence "
        "number) may sit on the link; descriptive attributes that change over time go in a "
        "satellite on the link",
        origin="dv2-modeling-rules-spec (2026-06-13)",
    ),
    SteeringRule(
        id="effsat_driving_key",
        text="When an effectivity satellite tracks a relationship's active period, declare "
        "the link's driving key — the hub reference(s) that stay fixed while the others "
        "rotate over time",
        origin="review-2026-06 remediation; gated by E_EFFSAT_NO_DRIVING_KEY",
    ),
    SteeringRule(
        id="effsat_two_dates",
        text="An effectivity satellite carries exactly two date attributes, in (start, end) "
        "order: the active-from date first, the active-to date second",
        backstop="effsat_two_attributes",
        origin="WP1 (2026-07-08): the generator reads attributes[0]/[1] positionally and "
        "silently dropped payload beyond the first two",
    ),
    SteeringRule(
        id="masat_source_table",
        text="When a satellite's rows live in their own source relation at finer grain than "
        "the parent's — typical for a multi-active satellite — declare the satellite's "
        "source_table (the raw relation feeding it); the parent's business-key column must "
        "exist in that relation so the rows attach to the parent",
        origin="WP7 §7.1 (2026-07-08); W_MASAT_SHARED_GRAIN warns when absent",
    ),
    SteeringRule(
        id="cdk_not_payload",
        text="A multi-active satellite's child_dependent_key (the sub-sequence key that "
        "distinguishes its concurrent rows, e.g. address_type) is a key column, not payload "
        "— never also list it among the satellite's attributes, or the generated satellite "
        "carries a duplicate column and cannot build",
        backstop="attributes_without_cdk",
        origin="2026-07-16: health_insurance failed validation 4/4 (E_SAT_DUP_ATTR) with "
        "error feedback alone — steering AND the deterministic backstop were needed",
    ),
    SteeringRule(
        id="bk_collision_code",
        text="When the same business-key value from different sources can mean different "
        "objects, add a collision code (source differentiation) rather than silently merging "
        "them into one hub",
        origin="canon (business-key collision); W_BK_COLLISION_RISK",
    ),
    SteeringRule(
        id="role_qualified_participation",
        text="When one hub participates twice in a relationship (e.g. a transfer's payer and "
        "counterparty are both accounts), qualify each participation with a role — "
        "connected_hubs entry {hub: hub_account, role: counterparty} — instead of dropping or "
        "duplicating the hub; role-qualify the driving key as \"hub_account:counterparty\" "
        "when it names a role",
        origin="WP8 / ADR-0009 (2026-07-08); E_LINK_DUP_ROLE",
    ),
    SteeringRule(
        id="construct_naming",
        text="Name every construct hub_/link_/sat_ followed by lowercase snake_case (e.g. "
        "hub_customer, link_account_customer, sat_customer_details) — nothing else; the name "
        "becomes a dbt model name and a file on disk",
        origin="review 2026-07-28 finding 4 / WP20: gated by E_BAD_NAME — steering keeps a "
        "deterministic formality from burning a modeling retry",
    ),
    SteeringRule(
        id="attribute_one_satellite",
        text="Within one source relation, an attribute belongs to exactly one satellite of a "
        "parent — split payload between satellites, never repeat a column in two of them; "
        "technical audit columns such as a last-modified timestamp are the usual trap, so put "
        "such a column in at most one satellite rather than in each",
        origin="WP31 / ADR-0012 (2026-07-30): AdventureWorks Sales duplicated ModifiedDate "
        "across two satellites of one relation — E_SAT_ATTR_OVERLAP is right there and stays "
        "an error, so steering keeps a real defect from burning the re-model budget",
    ),
    SteeringRule(
        id="repair_not_redraft",
        text=(
            "If the input contains `previous_model`, it is your own previous attempt: return it "
            "as the complete model with exactly the changes `previous_validation_issues` and their "
            "remedies require, and keep every construct no issue names — same name, same key, same "
            "parent, same attributes. Do not reshape what passed."
        ),
        backstop=None,
        origin=(
            "WP57, 2026-10-09: the tenth chain's step 3 fixed the payload gate in attempt 2 and "
            "lost the fix in attempt 3 — the retry carried no previous model, every attempt was a "
            "new draft. Measured as carry-over of constructs between attempts (trace)."
        ),
    ),
    SteeringRule(
        id="preserved_reference_is_a_link",
        text="A reference the requirements say is maintained elsewhere and must be PRESERVED "
        "so the areas can be joined later is a relationship, not a new concept: model it as a "
        "link to the existing hub named in the vault inventory, and never create a local hub "
        "for a concept the vault already holds",
        origin="WP30.1 (2026-08-09): measured, arm B built 0 of 37 links spanning two domains "
        "and invented hub_sales_representative where hub_employee stood in the inventory — with "
        "the foreign key in the schema, the requirement explicit (\"these references must be "
        "preserved so the sales information can later be joined to those areas\") and a "
        "ratified resolver merge all present. Resolution answers \"is this concept the existing "
        "one\"; nothing asked whether the RELATIONSHIP should span domains",
    ),
]

# Ablation seam (WP16 §2.2). Module-level, mirroring llm.set_usage_recorder: the harness
# injects an exclusion set without threading arguments through the agents. PRODUCTION CODE
# NEVER SETS THIS — it exists for eval/ablate.py, which measures whether a steering line is
# still doing work against the current model.
_excluded_rule_ids: frozenset[str] = frozenset()


def set_excluded_rules(rule_ids: Iterable[str] | None) -> None:
    """Exclude the named steering rules from the modeler prompt (or clear with ``None``).

    Raises ``ValueError`` on an unknown id — a silently ignored typo would report a rule as
    "safe to delete" while it was still in the prompt, the one failure mode that must not be
    quiet. Empty/``None`` restores the byte-identical shipped prompt."""
    global _excluded_rule_ids
    if not rule_ids:
        _excluded_rule_ids = frozenset()
        return
    requested = frozenset(rule_ids)
    known = {rule.id for rule in DV_MODELING_RULES}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError(
            f"unknown steering rule id(s): {', '.join(unknown)}; "
            f"known ids: {', '.join(sorted(known))}"
        )
    _excluded_rule_ids = requested


def excluded_rules() -> frozenset[str]:
    """The currently excluded steering-rule ids (empty in every production run)."""
    return _excluded_rule_ids


def active_modeling_rules() -> list[SteeringRule]:
    """The steering rules the modeler prompt is built from, honouring the ablation seam."""
    return [rule for rule in DV_MODELING_RULES if rule.id not in _excluded_rule_ids]

def attributes_without_cdk(
    attributes: list[str], child_dependent_key: list[str]
) -> list[str]:
    """Drop payload attributes that duplicate a ``child_dependent_key`` column.

    A satellite's attributes and its child_dependent_key share ONE column namespace (both
    become columns of the generated satellite; the CDK is emitted as ``src_cdk``, the
    attributes as ``src_payload``). A multi-active CDK (e.g. ``address_type``) also listed
    among the attributes would emit that column twice — the duplicate the warehouse rejects
    and ``E_SAT_DUP_ATTR`` blocks. Removing the redundant payload copy is meaning-preserving:
    the CDK column stays (via the key), only its duplicate attribute entry goes. Genuine
    attribute-vs-attribute duplicates are NOT touched here — the validator still flags those.
    Order-preserving; matches by ``normalize_identifier`` so casing/spacing variants collide."""
    cdk_norms = {normalize_identifier(key) for key in child_dependent_key}
    return [attr for attr in attributes if normalize_identifier(attr) not in cdk_norms]


def _role_prefix(column: str, role: str | None) -> str:
    """Prefix ``column`` with a normalised role; ``role`` None returns it unchanged."""
    if role is None:
        return column
    return f"{normalize_identifier(role)}_{column}"


def role_fk_column(hub_hashkey: str, role: str | None) -> str:
    """Role-qualify a hub's FK hash-key column for a link participation (ADR-0009).

    ``role_fk_column("ACCOUNT_HK", "counterparty") == "COUNTERPARTY_ACCOUNT_HK"``;
    an unqualified ref (``role=None``) returns the hash key unchanged, so plain-string
    links render byte-identically. Single source of truth for role FK naming — the code
    generator, staging generator, and validator all call it (never prefix ad hoc)."""
    return _role_prefix(hub_hashkey, role)


def role_bk_column(bk_column: str, role: str | None) -> str:
    """Role-qualify a business-key *source* column in staging for a role ref (ADR-0009).

    ``role_bk_column("ACCOUNT_NUMBER", "counterparty") == "COUNTERPARTY_ACCOUNT_NUMBER"``;
    None returns it unchanged. A self-referencing raw table necessarily carries the two
    participations as two columns — the role prefix is the documented expectation (an
    unmatched grounded column surfaces as W_ROLE_BK_NOT_IN_SOURCE, never a silent guess)."""
    return _role_prefix(bk_column, role)


def participation_key(hub: str, role: str | None) -> str:
    """How one link participation is named where a string has to identify it (ADR-0009).

    The hub name, or ``hub:role`` — the form ``LinkHubRef.__str__`` renders and ``driving_key``
    entries use. WP41 keys a link satellite's per-participation repairs by it, so an unqualified
    participation keeps the bare hub name WP40 keyed it by."""
    return hub if role is None else f"{hub}:{role}"


def role_names_column(role: str, column: str) -> bool:
    """Does a participation's role name this source column? (WP41)

    A catalogue does not carry ``COMPONENT_PRODUCTNUMBER``; it carries ``ComponentID`` and declares
    it as a foreign key. The role names the column when, separator-insensitive, it is contained in
    the column's name: ``component`` in ``ComponentID``, ``assembly`` in ``ProductAssemblyID``,
    ``bill_to`` in ``BillToAddressID``. Containment, not similarity — and a caller must require
    the match to be unique in both directions, because a role that names two columns, or a column
    two roles name, says nothing about which key is meant."""
    wanted = _separator_insensitive(role)
    return bool(wanted) and wanted in _separator_insensitive(column)


def canonical_hub_key_column(hub: Any) -> str:
    """The canonical staging column name a hub's key hashes from (WP10 §2.2, one source).

    Policy (decided 2026-07-13): a **business term** (normalised from ``hub.business_key``,
    e.g. ``CUSTOMER_ID``) ONLY when the feeding sources disagree on the physical key column;
    otherwise the source's own column name (no gratuitous rename — WP9 §6). With no declared
    ``sources`` this is today's single-source behaviour (``normalize_identifier(business_key)``),
    keeping single-source hubs byte-identical. Takes ``Any`` to avoid importing the state
    model here (rules stays dependency-free)."""
    sources = getattr(hub, "sources", None) or []
    if not sources:
        return normalize_identifier(hub.business_key)
    columns = {normalize_identifier(s.business_key_column) for s in sources}
    if len(columns) == 1:
        return next(iter(columns))  # sources agree — keep the source name
    return normalize_identifier(hub.business_key)  # disagree — harmonise to the business term


def is_composite_key(hub: Any) -> bool:
    """WP45: two or more declared key columns make the key composite; one is no composite."""
    return len(getattr(hub, "business_key_columns", None) or []) >= 2


def hub_key_columns(hub: Any) -> list[str]:
    """The staging column(s) a hub's hash key is computed from, in hashing order (WP45).

    The normalised ``business_key_columns`` for a composite key; otherwise exactly
    ``[canonical_hub_key_column(hub)]``, so every single-key path is unchanged. The staging
    generator, the hub renderer and the key gates all read this — never the label."""
    if is_composite_key(hub):
        return [normalize_identifier(c) for c in hub.business_key_columns]
    return [canonical_hub_key_column(hub)]


def satellite_participation_column(satellite: Any, ref: Any, hub: Any) -> str:
    """The source column a link satellite's stage reads one participation's key from (WP40/41).

    The translation's referencing column when the key is joined in through a view; the alias
    when the satellite's relation carries the key under another name; otherwise the
    participation's own column (``role_bk_column`` over the hub's canonical key). One answer for
    the staging generator and ``E_SAT_KEY_NOT_IN_SOURCE``, which must never disagree about it."""
    key = participation_key(ref.hub, ref.role)
    translation = satellite.participation_translations.get(key)
    if translation is not None:
        return str(translation.referencing_column)
    alias = satellite.participation_aliases.get(key)
    if alias is not None:
        return str(alias)
    return role_bk_column(canonical_hub_key_column(hub), ref.role)


def satellite_payload_relations(satellite: Any, parent: Any) -> frozenset[str]:
    """The source relation(s) a satellite's payload columns come from (ADR-0012).

    The single point that decides whether two satellites of one parent share a payload
    NAMESPACE, which is what separates a real duplicated column from two same-named columns of
    two different relations. Normalised names throughout; ``Any``-typed like its neighbours so
    ``rules/`` stays free of the state models.

    * declares ``source_table`` -> that table. An effectivity satellite is excluded (it stages
      with its parent link and ignores ``source_table`` — WP7 §7.1), the same one-line guard
      ``satellite_feed`` makes.
    * no ``source_table``, hub parent without ``sources`` -> the hub's ``source_entity``.
    * no ``source_table``, hub parent WITH ``sources`` (WP10) -> every feed, because the
      satellite splits across them. So a split satellite and a WP28 feed-bound satellite on the
      same hub intersect on that feed and stay one namespace, with no branch of their own.
    * no ``source_table``, link parent -> a ``link:<name>`` MARKER, not a relation: a link's
      staging is derived from its participations and has no single source table. It only ever
      needs to compare equal to itself.
    * unresolvable parent -> the EMPTY set, which callers must read as "unknown", never as
      "shares nothing" (an unknown relation must not lower a severity). A missing parent is
      ``E_SAT_UNKNOWN_PARENT``'s complaint, not this helper's."""
    if satellite.source_table and satellite.sat_type != "effectivity":
        return frozenset({normalize_identifier(satellite.source_table)})
    if parent is None:
        return frozenset()
    sources = getattr(parent, "sources", None) or []
    if sources:
        return frozenset(normalize_identifier(s.source_table) for s in sources)
    source_entity = getattr(parent, "source_entity", None)
    if source_entity:
        return frozenset({normalize_identifier(source_entity)})
    # A link parent has no source_entity: its staging comes from its participations.
    return frozenset({f"link:{normalize_identifier(parent.name)}"})


def satellite_feed(satellite: Any, parent_hub: Any) -> Any | None:
    """The multi-source hub feed a satellite's ``source_table`` names, or None (ADR-0011).

    "Names a feed" is a normalised table-name match against the hub's ``sources``. It
    therefore also matches the MATERIALISED LEGACY FEED of a grandfathered hub: when a
    single-source hub gains a feed, WP23's merger writes its original feed out explicitly
    (``source_entity``/``business_key``), so the brownfield case — the one that motivated
    ADR-0011 — needs no special case here. That is asserted by a test rather than assumed.

    Returns None when there is no multi-source parent, no ``source_table``, the satellite is
    an effectivity satellite (``source_table`` is ignored for those — they stage with their
    parent link), or the named table is not a feed at all. Takes/returns ``Any`` to keep
    rules/ free of the state models."""
    if parent_hub is None or not satellite.source_table:
        return None
    if satellite.sat_type == "effectivity":
        return None
    named = normalize_identifier(satellite.source_table)
    for source in getattr(parent_hub, "sources", None) or []:
        if normalize_identifier(source.source_table) == named:
            return source
    return None


def source_table_on_multi_source_hub(satellite: Any, parent_hub: Any) -> bool:
    """Is this satellite's ``source_table`` unusable on its multi-source parent? (ADR-0011)

    The single point the validator, code generator and staging generator ask, so they can
    never disagree about what is generated (WP24 §2.2). ADR-0011 NARROWED it — the name is
    unchanged, the meaning is not:

    * ``source_table`` naming one of the hub's feeds → **False**. The satellite binds to that
      feed and is generated once. This is the DV2.0-canonical one-satellite-per-source shape,
      and rejecting it was WP24's over-reach: measured, the alternative it steered to (no
      ``source_table``, so a split across feeds) demands the named feed's columns from EVERY
      feed's staging, which does not build either.
    * ``source_table`` naming anything else → **True**, still an error. A finer-grain relation
      *under* one feed would have to say which feed it belongs to, and the model cannot
      express that; inventing the binding is not something this project does.

    Effectivity satellites and single-source parents are excluded, as before."""
    if parent_hub is None or not satellite.source_table:
        return False
    if satellite.sat_type == "effectivity":
        return False
    if not getattr(parent_hub, "sources", None):
        return False
    return satellite_feed(satellite, parent_hub) is None


# Physical naming conventions the code generator uses when rendering AutomateDV/dbt
# models. Kept here so naming stays a single source of truth across modeler/generator.
LOAD_DATETIME_COLUMN = "LOAD_DATETIME"
RECORD_SOURCE_COLUMN = "RECORD_SOURCE"
HASHKEY_SUFFIX = "_HK"
HASHDIFF_SUFFIX = "_HASHDIFF"
STAGING_PREFIX = "stg_"
# Dedicated effectivity-tracking column for an effectivity satellite's AutomateDV `src_eff`.
# It MUST be distinct from src_start_date / src_end_date / src_ldts: AutomateDV's incremental
# eff_sat SQL projects src_eff separately, so reusing the start-date column makes Postgres
# reject the query with "column ... specified more than once". The staging for an eff_sat
# parent supplies this column carrying the same value as the start date, so end-dating closes
# a superseded record to the business effective date of its successor (not a load timestamp).
EFFECTIVITY_APPLIED_COLUMN = "APPLIED_DTS"
# Prefix for an *inferred* raw source relation when no declared source table matches a
# staging model (e.g. stg_customer -> raw_customer). An inferred binding is always flagged
# for human review (FlagKind.SOURCE_BINDING) — the generator names, it never guesses silently.
RAW_SOURCE_PREFIX = "raw_"
# AutomateDV package pin for the generated packages.yml — the version the Postgres
# end-to-end PoC (demo/bank_postgres) is verified against. Bump deliberately, re-verifying the demo.
AUTOMATE_DV_VERSION = "0.11.4"

# Vos revisions (NBK over hash, insert-only over persisted end-dating, ELM relationship-hubs,
# foreign-key links, PSA, PIT/Bridge) are deliberately out of scope here — they are ADR-gated
# alternatives, never silent defaults, tracked in docs/methodology/dsaf-mapping.md.


def construct_base_name(construct_name: str) -> str:
    """``hub_customer`` -> ``customer``: a construct's name without its DV type prefix.

    Promoted here from ``staging_generator._base_name`` (WP34) because a second consumer
    appeared — the link proposer has to answer "which hub represents this source table?" and
    must get the SAME answer staging binding gets. Two naming paths that merely happen to
    agree on well-formed names are a latent split, which is the reasoning ``_staging_name``
    already records for itself."""
    for prefix in ("hub_", "link_", "sat_"):
        if construct_name.startswith(prefix):
            return construct_name[len(prefix):]
    return construct_name


def _separator_insensitive(name: str) -> str:
    """An identifier reduced to the form ``snake_case`` and ``CamelCase`` share.

    ``normalize_identifier`` turns runs of non-alphanumerics into ``_`` and upper-cases, which
    leaves ``sales_order_header`` as ``SALES_ORDER_HEADER`` and ``SalesOrderHeader`` as
    ``SALESORDERHEADER``. Dropping the separators is what makes those the same name. Private
    on purpose: this is a comparison key for binding, never something to render or store."""
    return normalize_identifier(name).replace("_", "")


def construct_binds_to_source_table(construct_name: str, table_name: str) -> bool:
    """True when a construct's base names this declared source table.

    The ONE rule for construct↔relation correspondence, lifted verbatim from
    ``staging_generator.bind_sources``: the base matches the table directly, or its
    ``raw_<base>`` form does. The proposer needs the near side of an FK-derived link — the
    hub built for the referencing table — and deriving that independently is exactly the
    class of duplication that once staged a hash from the wrong relation (WP24).

    **Separator-insensitive since 2026-08-12, and that was a defect, not a preference.**
    Construct names are lowercase snake_case by ``CONSTRUCT_NAME_PATTERN``; a CamelCase source
    table normalises with no separators at all. So ``SALES_ORDER_HEADER`` was compared against
    ``SALESORDERHEADER`` and no multi-word CamelCase table could ever bind — 34 of 47 hubs on
    AdventureWorks, which is every enterprise landscape shaped like it. Measured consequences:
    5 of 7 ratified link proposals dropped for want of a near hub (exactly the two single-word
    tables, ``Employee`` and ``Customer``, survived), and 242 ``SOURCE_BINDING`` flags binding
    staging to ``raw_*`` relations that do not exist. The two spellings are one identifier.

    The comparison stays EXACT modulo the separator convention — deliberately not fuzzy
    matching. It is a widening: every pair that bound before still binds (pinned in
    ``tests/test_construct_binding_guard.py``), and it is unambiguous only while declared table
    names stay distinct once separators are ignored, which the same guard asserts against the
    corpus rather than assuming."""
    base = construct_base_name(construct_name)
    candidates = {
        _separator_insensitive(base),
        _separator_insensitive(RAW_SOURCE_PREFIX + base),
    }
    return _separator_insensitive(table_name) in candidates


def link_relation_offer(
    relation: Any, model: Any, resolve: Any, expand: Any | None = None
) -> dict[str, int]:
    """Which hubs a relation offers, and how often (WP42 §2).

    A relation offers every hub built FROM it (``hub_binds_to_source_table`` — by name or by
    provenance) plus every hub its single-column foreign keys resolve to, counted with
    multiplicity: ``BillOfMaterials`` declares two keys into ``Product`` and therefore offers
    ``hub_product`` twice, which is exactly what a bill-of-materials link takes.

    ``resolve`` is the caller's FK resolution (``link_proposal.resolve_fk_target`` bound to the
    model and the declared tables) — passed in so ``rules/`` stays free of that module."""
    angebot: dict[str, int] = {}
    for fk in getattr(relation, "foreign_keys", None) or []:
        if getattr(fk, "is_single_column", False):
            keys = [fk]
        elif expand is not None:
            # WP46: a composite key offers what its components resolve to one table further
            # (``link_proposal.component_keys``); without an expansion it offers nothing, as before.
            keys = list(expand(fk))
        else:
            continue
        for key in keys:
            hub = resolve(key)
            if hub is not None:
                angebot[hub.name] = angebot.get(hub.name, 0) + 1
    for hub in getattr(model, "hubs", None) or []:
        if hub_binds_to_source_table(hub, relation.table):
            angebot[hub.name] = max(angebot.get(hub.name, 0), 1)
    return angebot


def resolve_link_relation(
    link: Any, model: Any, schemas: Any, resolve: Any, expand: Any | None = None
) -> tuple[Any, str]:
    """The declared relation a link reads — ``(relation, grund)``; relation is None when unknown.

    Two tiers, and deliberately no third (WP42 §2):

    * **name** — exactly one declared table the link's construct name binds. Unchanged, tried
      first, so every binding that held before holds now.
    * **offer** — otherwise exactly one declared relation whose offer covers the link's
      participations as a multiset. Two or more fitting relations bind NOTHING: over six chains
      24 links fit more than one relation, always the same shapes (``Customer`` beside
      ``SalesOrderHeader``, ``BillOfMaterials`` beside ``Product``), and picking one would be a
      guess with wrong data as the failure mode.

    A satellite's ``source_table`` is not a tier: measured over the same corpus it resolves 1 of
    those 24 and contradicts a unique offer match once (``link_transaction_product``).

    ``grund`` is a code, never a sentence: ``name``, ``offer``, ``ambiguous``, ``none``."""
    benannt = [t for t in schemas if construct_binds_to_source_table(link.name, t.table)]
    if len(benannt) == 1:
        return benannt[0], "name"
    gewollt: dict[str, int] = {}
    for ref in link.hub_refs:
        gewollt[ref.hub] = gewollt.get(ref.hub, 0) + 1
    passend = []
    for relation in schemas:
        angebot = link_relation_offer(
            relation, model, lambda fk, _relation=relation: resolve(_relation, fk), expand
        )
        if angebot and all(angebot.get(hub, 0) >= n for hub, n in gewollt.items()):
            passend.append(relation)
    if len(passend) == 1:
        return passend[0], "offer"
    return None, ("ambiguous" if passend else "none")


def hub_binds_to_source_table(hub: Any, table_name: str) -> bool:
    """True when a hub is built FROM this declared source table — by name or by provenance.

    Name first: ``construct_binds_to_source_table`` on the hub's name, the same rule staging
    binds by. Then provenance: the hub's ``source_entity`` (the relation the modeler named it
    from), and each ``sources[].source_table`` of a multi-source hub (WP10), compared through
    the same separator-insensitive key. Names and provenance disagree exactly where a hub is
    named after the CONCEPT and the table after the RECORD — ``hub_purchase_order`` from
    ``PurchaseOrderHeader``, ``hub_sales_representative`` from ``SalesPerson`` — which is what
    the modeler did on 2026-09-12 and what name-only binding could not see: it skipped ratified
    links "for want of a hub" and took a hubbed header table for hub-less (WP37 §3.1).

    ``Any``-typed like its neighbours so ``rules/`` stays free of the state models."""
    if construct_binds_to_source_table(hub.name, table_name):
        return True
    wanted = _separator_insensitive(table_name)
    provenance = [
        source.source_table for source in (getattr(hub, "sources", None) or [])
    ] + [getattr(hub, "source_entity", None) or ""]
    return any(_separator_insensitive(rel) == wanted for rel in provenance if rel)


def resolution_category(
    concept_key: str, resolution: str, hubs: Any, source_tables: Any, evidence: Any
) -> str:
    """The DERIVED confidence tier of an entity resolution (WP29 §2.3, ADR-free rule).

    Deliberately not the resolver's own claim. The Phase 2 spike measured the model reporting
    ``semantic`` for every case, INCLUDING the exact-key ones where its answer was right — so
    a self-reported category cannot carry a reviewer's attention, and this computes it from
    what is actually on the table:

    * ``exact_key`` — the concept's key normalises to the resolved hub's business key. The
      strongest fact available and the one a reviewer can check in one glance.
    * ``key_overlap`` — a cross-reference relation carries both keys. This is the same-as
      shape: asserted equivalence, not identity.
    * ``comment_grounded`` — a declared column comment names the hub's business key. Weaker
      than a key match and stronger than a guess, mirroring WP9 §7's middle tier.
    * ``semantic`` — everything else, i.e. the model reasoned it out. Not a failure grade;
      it is the tier that says "a human should look".

    Takes ``Any`` for the state models to keep rules/ dependency-free, as the neighbouring
    helpers do."""
    key = normalize_identifier(concept_key)
    target = next((h for h in hubs if h.name == resolution), None)
    if target is not None and normalize_identifier(target.business_key) == key:
        return "exact_key"

    hub_keys = {normalize_identifier(h.business_key): h.name for h in hubs}
    for table in source_tables:
        columns = {normalize_identifier(c.name) for c in table.column_refs}
        if key in columns and columns & set(hub_keys):
            return "key_overlap"

    for table in source_tables:
        for column in table.column_refs:
            if normalize_identifier(column.name) != key or not column.comment:
                continue
            if any(hub_key in normalize_identifier(column.comment) for hub_key in hub_keys):
                return "comment_grounded"

    joined = normalize_identifier(" ".join(str(item) for item in (evidence or [])))
    if any(hub_key and hub_key in joined for hub_key in hub_keys):
        return "comment_grounded"
    return "semantic"



@dataclass(frozen=True)
class HubCollisionRemedy:
    """What the re-model loop should do about two hubs built from one source entity.

    ``keep`` / ``drop`` name the hubs; ``inherited`` says the pair is in the existing vault,
    where no delta can remove it; ``text`` is the sentence sent to the modeler."""

    keep: str | None
    drop: list[str]
    inherited: bool
    text: str


def _entity_matches(candidate_entity: str, hub: Any) -> bool:
    """`vendor` names `Vendor`; `purchase order` names `PurchaseOrderHeader` (prefix)."""
    cand = normalize_identifier(candidate_entity).replace("_", "")
    for label in (hub.source_entity, construct_base_name(hub.name)):
        ent = normalize_identifier(label).replace("_", "")
        if cand and ent and (cand == ent or ent.startswith(cand) or cand.startswith(ent)):
            return True
    return False


def _references(key: str, other: Any) -> bool:
    """`BusinessEntityID` references `hub_business_entity`: the other hub's key AND named
    after its entity. A generic key shared by name alone (`Name`) references nothing."""
    if normalize_identifier(key) != normalize_identifier(other.business_key):
        return False
    bare = normalize_identifier(key).replace("_", "")
    for label in (other.source_entity, construct_base_name(other.name)):
        ent = normalize_identifier(label).replace("_", "")
        if ent and bare in (ent, ent + "ID", ent + "KEY", ent + "CODE", ent + "NUMBER"):
            return True
    return False


_SQL_JSON_TYPES: dict[str, str] = {
    **{t: "integer" for t in ("int", "bigint", "smallint", "tinyint")},
    "bit": "boolean",
    **{t: "number" for t in ("decimal", "numeric", "money", "smallmoney", "float", "real")},
    **{t: "string" for t in (
        "char", "nchar", "varchar", "nvarchar", "text", "ntext", "uniqueidentifier", "xml",
        "date", "time", "datetime", "datetime2", "smalldatetime", "datetimeoffset", "binary",
        "varbinary", "image", "hierarchyid", "geography", "geometry",
    )},
}


def json_type_for_sql(declared: str) -> str | None:
    """The JSON Schema type a declared SQL Server base type denotes, or None (WP63).

    A length or precision suffix is ignored (``nvarchar(50)``, ``decimal(8,2)``); a user-defined
    type (AdventureWorks' ``Name``, ``Flag``, ``Phone``) or an empty declaration is None — the
    model may answer for those, the code must not guess. A declared fact is the code's to hold:
    the contract agent used to ask the model for a type it already had (2026-10-09)."""
    base = declared.split("(", 1)[0].strip().lower()
    return _SQL_JSON_TYPES.get(base) if base else None


def unread_payload(hub: Any, table: Any, model: Any, tables: Any = ()) -> list[str]:
    """The declared columns of ``table`` that nothing in ``model`` reads (WP54).

    The table's columns in declared order, minus the hub's key columns (``hub_key_columns``),
    minus every column of a declared foreign key of the table, minus every column a declared
    foreign key of any table in ``tables`` REFERENCES on it (an identifier other tables point
    at — a surrogate such as ``SalesOrderID`` beside the natural key the hub is on — is not
    payload), minus every attribute of a satellite that reads the table — a satellite reads it
    when ``satellite_payload_relations`` of the satellite and its parent names the table,
    whatever the parent (a link satellite counts). Normalised comparison; ``Any``-typed like
    its neighbours."""
    wanted = normalize_identifier(table.table)
    parents = {h.name: h for h in model.hubs} | {lk.name: lk for lk in model.links}
    read: set[str] = set()
    for sat in model.satellites:
        if wanted in satellite_payload_relations(sat, parents.get(sat.parent)):
            read |= {normalize_identifier(a) for a in sat.attributes}
    keys = {normalize_identifier(c) for c in hub_key_columns(hub)}
    for fk in getattr(table, "foreign_keys", None) or []:
        keys |= {normalize_identifier(c) for c in fk.columns}
    for other in tables:
        for fk in getattr(other, "foreign_keys", None) or []:
            if normalize_identifier(fk.references_table) == wanted:
                keys |= {normalize_identifier(c) for c in fk.references_columns}
    return [
        c for c in table.column_names
        if normalize_identifier(c) not in keys and normalize_identifier(c) not in read
    ]


def infer_satellite_relation(satellite: Any, tables: Any) -> str | None:
    """The one declared table that carries every attribute (and every dependent child key) of
    a satellite without a ``source_table`` — its relation, read from the schema (WP56).

    None when no table or more than one qualifies, or when there is nothing to match: a lone
    ``ModifiedDate`` qualifies every table and infers nothing. Returns the table's name as
    declared. ``Any``-typed like its neighbours."""
    wanted = {normalize_identifier(a) for a in satellite.attributes}
    cdk = getattr(satellite, "child_dependent_key", None) or []
    wanted |= {normalize_identifier(c) for c in cdk}
    if not wanted:
        return None
    matches = [
        t.table for t in tables
        if wanted <= {normalize_identifier(c) for c in t.column_names}
    ]
    return matches[0] if len(matches) == 1 else None


def satellite_reads_table(model: Any, table_name: str) -> bool:
    """Does any satellite of ``model`` read ``table_name`` (WP54)? Same reading rule as
    ``unread_payload``: the satellite's payload relations, whatever its parent."""
    wanted = normalize_identifier(table_name)
    parents = {h.name: h for h in model.hubs} | {lk.name: lk for lk in model.links}
    return any(
        wanted in satellite_payload_relations(sat, parents.get(sat.parent))
        for sat in model.satellites
    )


@dataclass(frozen=True)
class HubPayloadRemedy:
    """What the re-model loop should do with a hub whose table no satellite reads (WP54): the
    parent to hang the payload on and the sentence sent to the modeler."""

    parent: str
    columns: list[str]
    text: str


def hub_payload_remedy(hub: Any, table: Any, model: Any, columns: list[str]) -> HubPayloadRemedy:
    """Name the parent for the lost payload: the hub — or, for a relationship table (two or more
    declared foreign keys), the link of this model that reads it, if one does."""
    parent = hub.name
    fks = getattr(table, "foreign_keys", None) or []
    if len(fks) >= 2:
        for link in model.links:
            if construct_binds_to_source_table(link.name, table.table):
                parent = link.name
                break
    listed = ", ".join(columns)
    text = (
        f"{table.table} declares {listed}, which no satellite of this model reads — the vault "
        f"would drop them; add a satellite on {parent} read from {table.table} carrying them "
        f"(or hang them on another parent whose key {table.table} carries)"
    )
    return HubPayloadRemedy(parent=parent, columns=list(columns), text=text)


@dataclass(frozen=True)
class SatelliteKeyRemedy:
    """What the re-model loop should do with a satellite whose relation lacks its parent's key
    (WP46): the parents whose key the relation DOES carry, and the sentence sent to the modeler."""

    candidates: list[str]
    text: str


def satellite_key_remedy(
    satellite: Any, relation_columns: set[str], model: Any, missing: list[str],
) -> SatelliteKeyRemedy:
    """Name the parents the relation can feed, deterministically, else say „drop it".

    A hub qualifies when every column of its key (``hub_key_columns``) is declared on the
    relation; a link when every participation's column is — unqualified participations only,
    on the hubs' canonical columns, because a role, alias or translation is exactly what the
    relation would have needed and does not have. The current parent is never a candidate.
    The remedy also says that an unchanged copy of the satellite will be dropped (WP44 memory),
    so the modeler knows the choice is re-parent, re-source, or lose the payload."""
    present = {normalize_identifier(c) for c in relation_columns}
    candidates: list[str] = []
    for hub in model.hubs:
        if hub.name != satellite.parent and all(c in present for c in hub_key_columns(hub)):
            candidates.append(hub.name)
    hubs = {hub.name: hub for hub in model.hubs}
    for link in model.links:
        if link.name == satellite.parent:
            continue
        refs = link.hub_refs
        if not refs or any(
            ref.hub not in hubs or ref.role is not None or ref.key_translation is not None
            or ref.source_key_column is not None
            for ref in refs
        ):
            continue
        if all(
            c in present for ref in refs for c in hub_key_columns(hubs[ref.hub])
        ):
            candidates.append(link.name)
    where = ", ".join(sorted(candidates))
    lost = ", ".join(missing)
    if candidates:
        text = (
            f"re-parent {satellite.name} to a parent whose key {satellite.source_table} carries "
            f"— {where} — or read it from a relation that carries {lost}; an unchanged copy "
            f"(same parent, same relation) is dropped and its payload becomes a review decision"
        )
    else:
        text = (
            f"no hub or link of this model is keyed on columns {satellite.source_table} carries; "
            f"read {satellite.name} from a relation that carries {lost}, or drop it — an "
            f"unchanged copy (same parent, same relation) is dropped and its payload becomes a "
            f"review decision"
        )
    return SatelliteKeyRemedy(candidates=sorted(candidates), text=text)


@dataclass(frozen=True)
class SatelliteAttributeRemedy:
    """Which satellite keeps an attribute two satellites of one parent carry (WP48)."""

    keep: str | None
    drop: list[str]
    inherited: bool
    text: str


def satellite_attribute_remedy(
    satellites: list[Any], attribute: str, existing: Any | None,
) -> SatelliteAttributeRemedy:
    """Decide which satellite keeps a duplicated attribute, deterministically, and say why.

    The E_SAT_ATTR_OVERLAP diagnosis alone went unrepaired for three attempts on 2026-10-05
    (`MaritalStatus` on two satellites of `hub_employee`) and poisoned every later step of the
    chain. The rule, in order: (1) every owner is in the existing vault — INHERITED, nothing
    this increment emits can remove it, retire nothing; (2) exactly one owner is existing — it
    keeps the attribute, an existing satellite is immutable; (3) among new owners the first by
    name keeps it, and the text says the choice was arbitrary. A declared relation breaks no
    tie: the error fires only when all owners draw from one relation (ADR-0012)."""
    names = sorted(sat.name for sat in satellites)
    existing_names = {s.name for s in existing.satellites} if existing is not None else set()
    inherited = [n for n in names if n in existing_names]
    if names and len(inherited) == len(names):
        return SatelliteAttributeRemedy(
            keep=None, drop=[], inherited=True,
            text=(
                f"{attribute!r} is carried by {', '.join(names)}, all in the existing vault; "
                f"nothing this increment emits can remove it — do not re-emit either "
                f"satellite; the duplicate is a review item for the vault's owner"
            ),
        )
    if len(inherited) == 1:
        keep = inherited[0]
        drop = [n for n in names if n != keep]
        return SatelliteAttributeRemedy(
            keep=keep, drop=drop, inherited=False,
            text=(
                f"keep {attribute!r} on {keep}, which is in the existing vault (an existing "
                f"satellite is immutable); drop it from {', '.join(drop)}"
            ),
        )
    keep = names[0] if names else None
    drop = [n for n in names if n != keep]
    return SatelliteAttributeRemedy(
        keep=keep, drop=drop, inherited=False,
        text=(
            f"keep {attribute!r} on {keep} and drop it from {', '.join(drop)} — an attribute "
            f"lives in one satellite per parent; the choice of {keep} is arbitrary (first by "
            f"name) and a human may move it at the checkpoint; a re-emitted copy is dropped"
        ),
    )


@dataclass(frozen=True)
class SecondHubRemedy:
    """A hub that is the second hub of one entity (WP50): keyed on another hub's surrogate, in a
    vault that has that hub. ``parent`` is the hub to use instead, ``through`` the hub's own
    table (the translation's middle), ``text`` the sentence sent to the modeler."""

    second: str
    parent: str
    through: str
    text: str


def second_hub_remedy(
    hub: Any, model: Any, ratified_target: str, ratified_through: str,
) -> SecondHubRemedy | None:
    """Is ``hub`` the second hub of one entity? Decided on a RATIFIED key, never on a hunch (WP50).

    The evidence is the checkpoint's: a ratified key of the relation the link reads — the very
    column the gate names as the hub's declared key, a key into ``ratified_through`` — resolves
    (translated, WP36/WP39) to ``ratified_target``, another hub. When ``hub`` is built from
    ``ratified_through`` and ``ratified_target`` is another hub of the model, the modeler has
    built, under its own key, the hub the human already resolved that key to:
    `hub_sales_person` on `SalesPerson` beside `hub_employee`, `Store.SalesPersonID → SalesPerson
    → Employee` ratified. One entity, one hub (CLAUDE.md); WP38 hangs `SalesPerson`'s satellites on
    `hub_employee` as a subtype feed. A subtype hub nobody ratified away (`hub_store` on
    `Store.BusinessEntityID → BusinessEntity`) is not touched: no ratified key says so."""
    if ratified_target == hub.name or not hub_binds_to_source_table(hub, ratified_through):
        return None
    parent = next((h for h in model.hubs if h.name == ratified_target), None)
    if parent is None:
        return None
    sats = [s.name for s in getattr(model, "satellites", []) if s.parent == hub.name]
    hung = (
        f"; hang {', '.join(sats)} on {parent.name}, read from {ratified_through} (a subtype feed)"
        if sats else ""
    )
    return SecondHubRemedy(
        second=hub.name, parent=parent.name, through=ratified_through,
        text=(
            f"{hub.name} is {ratified_through} keyed on the surrogate the ratified key resolves "
            f"through to {parent.name} — the same entity, which the vault has; take the "
            f"participation from {parent.name} through {ratified_through} (the ratified "
            f"translation){hung}; do not build {hub.name} — a re-emitted copy under any name is "
            f"dropped"
        ),
    )


def hub_collision_remedy(
    hubs: list[Any],
    business_keys: list[Any],
    existing: Any | None,
    model_hubs: list[Any] | None = None,
) -> HubCollisionRemedy:
    """Decide which of the colliding hubs stays, deterministically, and say why.

    Three paid chain steps on 2026-09-13 exhausted the re-model loop on
    ``E_HUB_HK_COLLISION`` with the diagnosis alone as feedback: the modeler had hubbed both
    business-key candidates the identifier offered for one table (`Vendor`: `AccountNumber`
    0.95 and `BusinessEntityID` ~0.8) and, told only that they collide, kept both. The rule,
    in order:

    1. A pair that is entirely in the existing vault is INHERITED — nothing this increment
       emits can remove it, so the remedy is "do not re-emit either" and the pair stays a
       review item for the vault's owner.
    2. An existing hub always stays: its key is immutable (changing it re-hashes every row),
       so the new hub is the one to drop.
    3. Among new hubs, the one keyed on the business-key candidate the identifier ranked
       HIGHEST for that entity stays; a hub whose key is no candidate at all loses to one
       whose key is (the replay's `hub_department_group` on `GroupName`).
    4. Without a ranking, a hub keyed on another hub's key AND named after that hub's entity
       (``BusinessEntityID`` is ``hub_business_entity``'s) is a reference, not an identity:
       it is the one to drop. A generic key shared by name alone (``Name``) is no reference —
       the first replay said "Name on Department references hub_shift", which is nonsense.
    5. Otherwise the first by name stays, and the text says the choice was arbitrary.

    Whatever is dropped, the relationship its key expressed is a link to the hub keyed on
    that key, which the model may already contain."""
    by_name = {hub.name: hub for hub in hubs}
    existing_names = {h.name for h in existing.hubs} if existing is not None else set()
    names = sorted(by_name)
    inherited = [n for n in names if n in existing_names]
    others = [o for o in (model_hubs or []) if o.name not in by_name]

    def _referenced_hub(name: str) -> str | None:
        for other in others:
            if _references(by_name[name].business_key, other):
                return str(other.name)
        return None

    def _link_hint(dropped: list[str]) -> str:
        hints = []
        for name in dropped:
            target = _referenced_hub(name)
            if target:
                hints.append(
                    f"{by_name[name].business_key} on {by_name[name].source_entity} is a "
                    f"reference to {target}; model that relationship as a link to "
                    f"{target}, not as a second hub"
                )
        if hints:
            return "; " + "; ".join(hints)
        return (
            "; if the dropped hub's key references another concept, that relationship is a "
            "link to the hub keyed on it, not a second hub"
        )

    if len(inherited) == len(names):
        return HubCollisionRemedy(
            keep=None, drop=[], inherited=True,
            text=(
                f"{', '.join(names)} are all in the existing vault; nothing this increment "
                f"emits can remove them — do not re-emit either hub; the duplicate is a "
                f"review item for the vault's owner"
            ),
        )
    if inherited:
        keep = inherited[0]
        drop = [n for n in names if n not in existing_names]
        return HubCollisionRemedy(
            keep=keep, drop=drop, inherited=False,
            text=(
                f"drop {', '.join(drop)}; keep {keep}, which is in the existing vault keyed on "
                f"{by_name[keep].business_key} (an existing hub's key is immutable)"
                + _link_hint(drop)
            ),
        )
    scores: dict[str, float] = {}
    for cand in business_keys:
        for name in names:
            hub = by_name[name]
            if _entity_matches(cand.entity, hub) and (
                normalize_identifier(hub.business_key) == normalize_identifier(cand.field)
            ):
                scores[name] = max(scores.get(name, float("-inf")), cand.score)
    if scores and (len(scores) < len(names) or len(set(scores.values())) > 1):
        keep = max(scores, key=lambda n: (scores[n], n))
        drop = [n for n in names if n != keep]
        ranked = ", ".join(
            f"{by_name[n].business_key} {scores[n]:.2f}"
            for n in sorted(scores, key=lambda n: scores[n], reverse=True)
        )
        unranked = [by_name[n].business_key for n in drop if n not in scores]
        why = (
            f"the business-key identifier ranked {by_name[keep].source_entity}'s candidates "
            f"{ranked}"
            + (f" and never proposed {', '.join(unranked)} as a key" if unranked else "")
            + ", and one entity is one hub on its highest-ranked key"
        )
        return HubCollisionRemedy(
            keep=keep, drop=drop, inherited=False,
            text=f"drop {', '.join(drop)}; keep {keep} — {why}" + _link_hint(drop),
        )
    referencing = [n for n in names if _referenced_hub(n)]
    if referencing and len(referencing) < len(names):
        keep = next(n for n in names if n not in referencing)
        return HubCollisionRemedy(
            keep=keep, drop=referencing, inherited=False,
            text=(
                f"drop {', '.join(referencing)}; keep {keep} — a hub keyed on another hub's "
                f"key is a reference, not an identity" + _link_hint(referencing)
            ),
        )
    keep, drop = names[0], names[1:]
    return HubCollisionRemedy(
        keep=keep, drop=drop, inherited=False,
        text=(
            f"drop {', '.join(drop)}; keep {keep} — one source entity is one hub; the choice "
            f"between these keys is arbitrary here (no ranked candidate, no reference), so "
            f"keep the first and express the other key as a link if it references a concept"
            + _link_hint(drop)
        ),
    )
