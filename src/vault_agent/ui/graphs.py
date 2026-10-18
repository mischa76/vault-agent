"""Mermaid sources for the workbench's Model perspective (WP66 §2.5).

The output model reuses :func:`vault_agent.report.build_model_mermaid`. The INPUT model — the
declared source schema with its foreign keys — is new here, an ``erDiagram``. Every identifier
is reduced to ``[A-Za-z0-9_]`` before it reaches the diagram source, the report's rule: a
hostile table or column name can never leave the label it is in.
"""
from __future__ import annotations

import re
import sys
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


def area_views(state: Any) -> list[dict[str, Any]]:
    """WP80: the model's subject areas with one scoped Mermaid source each — from the staging
    metadata when the project is generated (the record of what it reads), else recomputed."""
    from vault_agent.report import build_model_mermaid
    from vault_agent.subject_areas import subject_areas

    staging = state.artifacts.automatedv_yaml.get("staging")
    areas = subject_areas(
        state.dv_model, state.source_schemas, carried=state.carried_schemas,
        staging=staging if isinstance(staging, dict) else None,
        existing=state.existing_model, carried_bindings=state.carried_bindings,
    )
    return [
        {
            **area.as_dict(),
            "mermaid": build_model_mermaid(
                state.dv_model, members=area.members(), neighbours=area.neighbours
            ),
        }
        for area in areas
    ]


def node_catalogue() -> list[dict[str, Any]]:
    """The graph's nodes in order with the tool name each agent emits (WP67 §2.1).

    Read from the agents the graph constructs — the ``_TOOL_NAME`` constant of the module the
    agent class lives in — so the frontend derives its status strip from the package's own
    order and names, never from a list of its own. A deterministic node has ``None``.
    """
    from vault_agent.graph import NODES, default_agents

    agents = default_agents()
    return [
        {
            "id": node,
            "tool_name": getattr(sys.modules[type(agents[node]).__module__], "_TOOL_NAME", None),
        }
        for node in NODES
    ]
