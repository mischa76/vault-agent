"""Mermaid sources for the workbench's Model perspective (WP66 §2.5).

The output model reuses :func:`vault_agent.report.build_model_mermaid`. The INPUT model — the
declared source schema with its foreign keys — is new here, an ``erDiagram``. Every identifier
is reduced to ``[A-Za-z0-9_]`` before it reaches the diagram source, the report's rule: a
hostile table or column name can never leave the label it is in.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

_IDENT = re.compile(r"[^A-Za-z0-9_]+")


def _ident(value: object) -> str:
    cleaned = _IDENT.sub("_", str(value)).strip("_")
    return cleaned or "unnamed"


def build_source_mermaid(tables: Iterable[Any]) -> str:
    """The declared source schema as a Mermaid ``erDiagram`` (tables, typed columns, FKs)."""
    lines = ["erDiagram"]
    tables = list(tables)
    for table in tables:
        lines.append(f"  {_ident(table.table)} {{")
        for column in table.column_refs:
            lines.append(f"    {_ident(column.type or 'unknown')} {_ident(column.name)}")
        lines.append("  }")
    for table in tables:
        for fk in getattr(table, "foreign_keys", None) or []:
            label = _ident(",".join(fk.columns))
            lines.append(
                f"  {_ident(table.table)} }}o--|| {_ident(fk.references_table)} : {label}"
            )
    return "\n".join(lines) + "\n"
