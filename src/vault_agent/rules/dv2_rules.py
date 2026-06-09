"""Encoded DV2.0/2.1 rules the Modeler and Validator use.

Keep in pure Python so they are unit-testable and not subject to LLM hallucination.
"""

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

# Structural rules the DV2.0 Modeler applies when turning business objects and keys
# into hubs, links, and satellites. Injected into the modeler prompt at runtime so the
# rule set stays a single source of truth (see CLAUDE.md).
DV_MODELING_RULES = [
    "Create exactly one hub per business key — one hub is one concept with one natural key",
    "Hubs hold only the business key plus DV technical columns; never descriptive attributes",
    "Create a link for each relationship between objects; a link connects two or more hubs",
    "Links hold only references to their hubs — no descriptive attributes, no business keys",
    "Put descriptive, changing attributes in satellites; each satellite hangs off one parent",
    "Group attributes that change together (same rate of change or source) into one satellite",
    "Do not model a stand-alone object as a link, and do not model a relationship as a hub",
]

# Physical naming conventions the code generator uses when rendering AutomateDV/dbt
# models. Kept here so naming stays a single source of truth across modeler/generator.
LOAD_DATETIME_COLUMN = "LOAD_DATETIME"
RECORD_SOURCE_COLUMN = "RECORD_SOURCE"
HASHKEY_SUFFIX = "_HK"
HASHDIFF_SUFFIX = "_HASHDIFF"
STAGING_PREFIX = "stg_"

# TODO: populate further from CDVP 2.1 material
