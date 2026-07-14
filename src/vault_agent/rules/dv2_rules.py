"""Encoded DV2.0/2.1 rules the Modeler and Validator use.

Keep in pure Python so they are unit-testable and not subject to LLM hallucination.
"""
import re
from typing import Any


def normalize_identifier(label: str) -> str:
    """Normalise a business label into a SQL identifier (UPPER_SNAKE).

    Single source of truth for identifier normalisation: the code generator renders columns
    with it, and source-schema grounding (ADR-0004) matches proposed keys/attributes to real
    columns with it, so ``"national customer ID"`` grounds against a ``NATIONAL_CUSTOMER_ID``
    column."""
    return re.sub(r"[^0-9a-zA-Z]+", "_", label).strip("_").upper()


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

# Structural rules the DV2.0 Modeler applies when turning business objects and keys
# into hubs, links, and satellites. Injected into the modeler prompt at runtime so the
# rule set stays a single source of truth (see CLAUDE.md).
DV_MODELING_RULES = [
    "Create exactly one hub per business key — one hub is one concept with one natural key",
    "Hubs hold only the business key plus DV technical columns; never descriptive attributes",
    "Create a link for each relationship between objects; a link connects two or more hubs",
    "Links hold only references to their hubs — no descriptive attributes, no business keys",
    "Put descriptive, changing attributes in satellites; each satellite hangs off one parent",
    f"Split satellites along these axes — {', '.join(SATELLITE_SPLIT_AXES)}; one satellite "
    f"holds attributes that belong together on all of them, split where they diverge",
    "Do not model a stand-alone object as a link, and do not model a relationship as a hub",
    "A link represents exactly one Unit of Work — the business keys of one atomic business "
    "event; never split one event across links nor merge unrelated relationships into one link",
    "Degenerate attributes of the relationship itself (e.g. an order-line sequence number) may "
    "sit on the link; descriptive attributes that change over time go in a satellite on the link",
    "When an effectivity satellite tracks a relationship's active period, declare the link's "
    "driving key — the hub reference(s) that stay fixed while the others rotate over time",
    "An effectivity satellite carries exactly two date attributes, in (start, end) order: "
    "the active-from date first, the active-to date second",
    "When a satellite's rows live in their own source relation at finer grain than the "
    "parent's — typical for a multi-active satellite — declare the satellite's "
    "source_table (the raw relation feeding it); the parent's business-key column must "
    "exist in that relation so the rows attach to the parent",
    "When the same business-key value from different sources can mean different objects, add a "
    "collision code (source differentiation) rather than silently merging them into one hub",
    "When one hub participates twice in a relationship (e.g. a transfer's payer and "
    "counterparty are both accounts), qualify each participation with a role — "
    "connected_hubs entry {hub: hub_account, role: counterparty} — instead of dropping or "
    "duplicating the hub; role-qualify the driving key as \"hub_account:counterparty\" when it "
    "names a role",
]

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
