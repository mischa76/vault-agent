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

# TODO: populate further from CDVP 2.1 material
