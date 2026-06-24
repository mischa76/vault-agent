"""Declared source-schema loader (source-schema-input spec, Phase 1).

The *producer* half of ADR-0004 grounding: read a declared YAML/JSON file describing the
source tables and their columns into ``list[SourceTable]``, which the CLI sets on
``state.source_schemas`` so the already-built grounding (validator warnings, prompt
steering, per-table contracts) activates.

Loading is I/O and validation; matching lives in ``grounding.py``. Kept deterministic and
key-free. Inert by construction: an empty/``null`` document yields ``[]`` (no schema), so a
run with no declared schema behaves exactly as before."""
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from vault_agent.state import SourceTable


def load_source_schemas(path: Path) -> list[SourceTable]:
    """Load a declared source schema (YAML or JSON) into ``list[SourceTable]``.

    Accepts either a top-level ``source_schemas:`` key mapping to a list, or a bare
    top-level list of the same ``{table, columns}`` objects. Column names are stored as
    written (grounding normalises both sides).

    Raises ``FileNotFoundError`` if the file is missing, and a clear, attributable
    ``ValueError`` (naming the file and the problem) on a malformed document or entry so
    the CLI can surface it as a clean exit rather than silently dropping a bad schema. An
    empty or ``null`` document yields ``[]`` (treated as "no schema": inert)."""
    raw = path.read_text(encoding="utf-8")
    try:
        document: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML/JSON ({exc})") from exc

    if document is None:
        return []

    if isinstance(document, dict):
        if "source_schemas" not in document:
            raise ValueError(
                f"{path}: mapping has no 'source_schemas' key (expected "
                "'source_schemas:' or a bare list of {table, columns} entries)"
            )
        entries = document["source_schemas"]
        if entries is None:
            return []
    else:
        entries = document

    if not isinstance(entries, list):
        raise ValueError(
            f"{path}: 'source_schemas' must be a list of {{table, columns}} entries, "
            f"got {type(entries).__name__}"
        )

    schemas: list[SourceTable] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"{path}: entry #{index + 1} must be a mapping with 'table' and "
                f"'columns', got {type(entry).__name__}"
            )
        try:
            schemas.append(SourceTable.model_validate(entry))
        except ValidationError as exc:
            raise ValueError(f"{path}: entry #{index + 1} is invalid: {exc}") from exc
    return schemas
