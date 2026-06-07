"""Encoded DV2.0/2.1 rules the Modeler and Validator use.

Keep in pure Python so they are unit-testable and not subject to LLM hallucination.
"""

REQUIRED_HUB_COLUMNS = {"hash_key", "business_key", "load_date_time", "record_source"}
REQUIRED_LINK_COLUMNS = {"hash_key", "load_date_time", "record_source"}
REQUIRED_SAT_COLUMNS = {"hash_key", "load_date_time", "record_source", "hash_diff"}

# TODO: populate from CDVP 2.1 material
