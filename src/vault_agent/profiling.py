"""Declared profiling-evidence loader (WP9 §3.2 / ADR-0008 #4).

The *producer* half of ADR-0008's profiling premise: read a pre-step YAML/JSON file of
per-column statistics into ``dict[str, dict[str, ColumnProfile]]`` (table -> column ->
profile), which the CLI sets on ``state.profiling`` for the business↔source mapper.

Profiling is deliberately a **file** — produced ahead of time from a sanitised extract or a
metadata export — never produced by the pipeline logging into a live source (ADR-0008 #4).

Loading is I/O + validation only; kept deterministic and key-free, in the
:func:`vault_agent.source_schema.load_source_schemas` style: a malformed document raises a
clear, attributable ``ValueError`` naming the file and the problem. An empty/``null``
document yields ``{}`` (no profiling: inert), so a run without the flag behaves as before."""
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from vault_agent.state import ColumnProfile


def load_profiling(path: Path) -> dict[str, dict[str, ColumnProfile]]:
    """Load a profiling file (YAML or JSON) into ``{table: {column: ColumnProfile}}``.

    Accepts a top-level ``tables:`` key mapping to a list (or a bare list) of
    ``{table, columns: [{name, uniqueness_ratio, null_ratio, distinct_count,
    example_values}]}`` entries; any extra per-table keys (e.g. ``row_count``) are ignored.

    Raises ``FileNotFoundError`` if missing, and a clear, attributable ``ValueError`` on a
    malformed document or entry. An empty/``null`` document yields ``{}`` (inert)."""
    raw = path.read_text(encoding="utf-8")
    try:
        document: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML/JSON ({exc})") from exc

    if document is None:
        return {}

    if isinstance(document, dict):
        if "tables" not in document:
            raise ValueError(
                f"{path}: mapping has no 'tables' key (expected 'tables:' or a bare list "
                "of {table, columns} entries)"
            )
        entries = document["tables"]
        if entries is None:
            return {}
    else:
        entries = document

    if not isinstance(entries, list):
        raise ValueError(
            f"{path}: 'tables' must be a list of {{table, columns}} entries, "
            f"got {type(entries).__name__}"
        )

    profiling: dict[str, dict[str, ColumnProfile]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or "table" not in entry:
            raise ValueError(
                f"{path}: entry #{index + 1} must be a mapping with a 'table' key, "
                f"got {type(entry).__name__}"
            )
        table = str(entry["table"])
        columns: dict[str, ColumnProfile] = {}
        for col in entry.get("columns", []) or []:
            if not isinstance(col, dict) or "name" not in col:
                raise ValueError(
                    f"{path}: table {table!r} has a column entry without a 'name' key"
                )
            try:
                profile = ColumnProfile.model_validate(col)
            except ValidationError as exc:
                raise ValueError(
                    f"{path}: table {table!r} column {col.get('name')!r} is invalid: {exc}"
                ) from exc
            columns[profile.name] = profile
        profiling[table] = columns
    return profiling
