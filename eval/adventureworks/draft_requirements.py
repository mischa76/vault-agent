"""Draft requirements deterministically from the source catalogue — the C1 experiment's
instrument (2026-10-30, the owner's commission; C1 option 3's machine half, C27 stage 4).

The question C1 asks before any ADR: how does a run on requirements *drafted from the catalogue*
compare with the run on the blinded analyst's documents (`eval/datasets/adventureworks_<area>/
requirements.md`, WP30 §2.4a) — in constructs and review load — and what does a deterministic
derivation make of the associative tables? This module is the derivation. It writes, for every
subject area, a case ``adventureworks_drafted_<area>`` that is the authored case with one file
exchanged: the requirements. Schema and golden are byte-identical copies, so the two arms differ
in exactly the input C1 asks about.

**Rules, stated before the run and never tuned to it.** Everything comes from the extract:
tables, their descriptions, columns with their descriptions, primary keys, Microsoft's ``AK_*``
alternate keys, foreign keys. No sentence here is an analyst's: no clarification, no business
purpose, no scope judgement — the drafted document knows only what the catalogue says.

- A table is a **relationship** when its primary key is covered by two or more foreign keys
  (`BusinessEntityAddress`, `ProductProductPhoto`, `ProductVendor`, …): the document says which
  things it relates and lists its other columns as attributes of the relationship.
- A table is a **subtype** when its primary key is covered by exactly one foreign key
  (`Person` → `BusinessEntity`, `Employee` → `Person`): the document says every X is a Y,
  identified by the same key.
- Every other table is an **entity**, identified by its single-column ``AK_*`` natural key when
  Microsoft declared one that is not the ``rowguid``, else by its primary key — the surrogate,
  which is C1's warning made measurable.
- Columns are named in words (``SalesOrderID`` → *sales order id*), never by their physical
  name, as the analyst's documents never name a column; ``ModifiedDate`` and ``rowguid`` are
  stated once per entity as technical, as the analyst stated them.
- One requirement per described column; the undescribed columns of a table in one requirement;
  one requirement per foreign key.

    python -m eval.adventureworks.draft_requirements   # → eval/datasets/adventureworks_drafted_*
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

from eval.adventureworks.derive import ARM_B_ORDER, AUDIT_COLUMNS, case_dir_name, tables_of

_HEADER = (
    "<!-- Drafted deterministically from the AdventureWorks catalogue (Microsoft, MIT — see\n"
    "NOTICE) by eval.adventureworks.draft_requirements: tables, descriptions, keys and foreign\n"
    "keys as the catalogue states them. No analyst has read or written this. The C1 experiment,\n"
    "2026-10-30. -->\n"
)


def words(name: str) -> str:
    """``SalesOrderHeader`` → *sales order header*; ``BusinessEntityID`` → *business entity id*."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    return spaced.replace("_", " ").lower()


def drafted_case_name(schema: str) -> str:
    return f"adventureworks_drafted_{schema.lower()}"


def classify(table: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """``("relationship" | "subtype" | "entity", the foreign keys covering the primary key)``."""
    pk = set(table["primary_key"])
    covering = [fk for fk in table["foreign_keys"] if set(fk["columns"]) & pk]
    covered = set().union(*(set(fk["columns"]) for fk in covering)) if covering else set()
    if pk and pk <= covered:
        return ("subtype" if len(covering) == 1 else "relationship"), covering
    return "entity", covering


def natural_key(table: dict[str, Any]) -> list[str] | None:
    """Microsoft's own ``AK_*`` key that is not the technical GUID — the first declared."""
    for key in table["alternate_keys"]:
        if not key.get("technical_guid"):
            return list(key["columns"])
    return None


class _Draft:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.n = 0

    def req(self, text: str) -> None:
        self.n += 1
        self.lines.append(f"- **REQ-{self.n:03d}** {text}")

    def text(self, line: str = "") -> None:
        self.lines.append(line)


def _key_phrase(columns: list[str]) -> str:
    if len(columns) == 1:
        return f"its **{words(columns[0])}**"
    return "the combination of " + ", ".join(f"**{words(c)}**" for c in columns)


def draft(extract: dict[str, Any], schema: str) -> str:
    tables = tables_of(extract, schema)
    d = _Draft()
    d.text(_HEADER)
    d.text(f"# Requirements drafted from the source catalogue: {words(schema)}")
    d.text()
    d.text(f"**Area:** {schema}  ")
    d.text("**Prepared by:** nobody — drafted from the catalogue  ")
    d.text("**Status:** Draft, unreviewed")
    d.text()
    d.text("## 1. Purpose")
    d.text()
    d.text(
        f"The business needs to analyse what the {words(schema)} area of the operational system "
        "records. This document lists what that area records, as the system's own catalogue "
        "describes it: its tables, what identifies each, what each records, and how they refer "
        "to one another. It states nothing the catalogue does not."
    )
    d.text()
    d.text("## 2. Business entities in scope")
    d.text()
    d.text("| Concept | What the catalogue says it is |")
    d.text("|---|---|")
    for table in tables:
        kind, _ = classify(table)
        label = {
            "relationship": " (a relationship)", "subtype": " (a kind of another concept)",
        }.get(kind, "")
        what = table["description"] or "(no description in the catalogue)"
        d.text(f"| {words(table['name']).capitalize()}{label} | {what} |")
    d.text()
    for index, table in enumerate(tables, start=3):
        kind, covering = classify(table)
        name = words(table["name"])
        d.text(f"## {index}. {name.capitalize()}")
        d.text()
        if table["description"]:
            d.text(table["description"])
            d.text()
        described = [c for c in table["columns"] if c["name"] not in AUDIT_COLUMNS]
        key_columns = set(table["primary_key"])
        fk_columns = {c for fk in table["foreign_keys"] for c in fk["columns"]}
        if kind == "relationship":
            parties = ", ".join(f"**{words(fk['references_table'])}**" for fk in covering)
            d.req(f"The business must record which {parties} are related, as a **{name}**.")
            d.req(f"Each {name} is identified by {_key_phrase(table['primary_key'])}.")
        elif kind == "subtype":
            parent = words(covering[0]["references_table"])
            same = (
                f"the same **{words(table['primary_key'][0])}**" if len(table["primary_key"]) == 1
                else "the same " + _key_phrase(table["primary_key"])
            )
            d.req(f"The business must record every **{name}**. Every {name} is a **{parent}** and "
                  f"is identified by {same}.")
        else:
            d.req(f"The business must record every **{name}**.")
            key = natural_key(table) or table["primary_key"]
            if key:
                d.req(f"Each {name} is identified by {_key_phrase(key)}.")
        identifying = set(key_columns)
        if kind == "entity":
            identifying |= set(natural_key(table) or [])
        attributes = [
            c for c in described if c["name"] not in identifying and c["name"] not in fk_columns
        ]
        for column in attributes:
            if column.get("description"):
                d.req(f"The business must record the **{words(column['name'])}** of each {name}: "
                      f"{column['description']}")
        undescribed = [words(c["name"]) for c in attributes if not c.get("description")]
        if undescribed:
            listed = ", ".join(f"**{u}**" for u in undescribed)
            d.req(f"The business must also record, for each {name}: {listed}.")
        for fk in table["foreign_keys"]:
            if kind != "entity" and fk in covering:
                continue
            via = ", ".join(words(c) for c in fk["columns"])
            d.req(f"Each {name} refers to one **{words(fk['references_table'])}** (by its {via}).")
        if any(c["name"] in AUDIT_COLUMNS for c in table["columns"]):
            guid = any(c["name"] == "rowguid" for c in table["columns"])
            d.req(
                f"Each {name} carries a last-changed timestamp"
                + (" and a technical row identifier, which is not a business key" if guid else "")
                + "."
            )
        d.text()
    return "\n".join(d.lines).rstrip() + "\n"


def write_cases(extract: dict[str, Any], out_root: Path) -> dict[str, dict[str, int]]:
    """One drafted case per subject area beside the authored one, and the drafted chain."""
    summary: dict[str, dict[str, int]] = {}
    for schema in ARM_B_ORDER:
        source = out_root / case_dir_name(schema)
        target = out_root / drafted_case_name(schema)
        target.mkdir(parents=True, exist_ok=True)
        for asset in ("source_schema.yml", "golden_mapping.yml"):
            shutil.copyfile(source / asset, target / asset)
        text = draft(extract, schema)
        (target / "requirements.md").write_text(text, encoding="utf-8")
        dataset = (source / "dataset.yml").read_text(encoding="utf-8")
        dataset = (
            "# The C1 experiment (2026-10-30): the authored case with ONE file exchanged — the\n"
            "# requirements are drafted deterministically from the catalogue by\n"
            "# eval.adventureworks.draft_requirements. Schema and golden are byte-identical\n"
            "# copies.\n"
            + dataset.replace(
                f"name: {case_dir_name(schema)}", f"name: {drafted_case_name(schema)}"
            )
        )
        (target / "dataset.yml").write_text(dataset, encoding="utf-8")
        kinds = [classify(t)[0] for t in tables_of(extract, schema)]
        summary[schema] = {
            "tables": len(kinds), "entities": kinds.count("entity"),
            "subtypes": kinds.count("subtype"), "relationships": kinds.count("relationship"),
            "requirements": text.count("- **REQ-"), "lines": text.count("\n"),
        }
    chain_source = out_root / "adventureworks_incremental" / "dataset.yml"
    chain = chain_source.read_text(encoding="utf-8")
    chain = chain.replace(
        "name: adventureworks_incremental", "name: adventureworks_drafted_incremental"
    )
    for schema in ARM_B_ORDER:
        chain = chain.replace(f"- {case_dir_name(schema)}\n", f"- {drafted_case_name(schema)}\n")
    chain_dir = out_root / "adventureworks_drafted_incremental"
    chain_dir.mkdir(parents=True, exist_ok=True)
    (chain_dir / "dataset.yml").write_text(
        "# The C1 experiment (2026-10-30): the arm-B chain on DRAFTED requirements — every step\n"
        "# the authored step with its requirements exchanged. Not a normal chain: it never enters\n"
        "# the review record of eval.wp34_check.\n" + chain, encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extract", type=Path,
        default=Path("eval/datasets/adventureworks/schema_extract.json"),
    )
    parser.add_argument("--out", type=Path, default=Path("eval/datasets"))
    args = parser.parse_args()
    extract = json.loads(args.extract.read_text(encoding="utf-8"))
    summary = write_cases(extract, args.out)
    print(f"{'subject area':16} {'tables':>7} {'entities':>9} {'subtypes':>9} {'relations':>10} "
          f"{'reqs':>6} {'lines':>6}")
    for schema, c in summary.items():
        print(f"{schema:16} {c['tables']:>7} {c['entities']:>9} {c['subtypes']:>9} "
              f"{c['relationships']:>10} {c['requirements']:>6} {c['lines']:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
