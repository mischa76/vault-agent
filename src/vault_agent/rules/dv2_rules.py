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

