"""Encoded DV2.0/2.1 rules the Modeler and Validator use.

Keep in pure Python so they are unit-testable and not subject to LLM hallucination.
"""
import re


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
    "When the same business-key value from different sources can mean different objects, add a "
    "collision code (source differentiation) rather than silently merging them into one hub",
]

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

# Vos revisions (NBK over hash, insert-only over persisted end-dating, ELM relationship-hubs,
# foreign-key links, PSA, PIT/Bridge) are deliberately out of scope here — they are ADR-gated
# alternatives, never silent defaults, tracked in docs/methodology/dsaf-mapping.md.
