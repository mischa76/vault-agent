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

Since WP117 (ADR-0019, 2026-10-31) the rules live in ``vault_agent.draft_requirements`` and this
module delegates to them; the documents' leading comment is the product's typed header.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from eval.adventureworks.derive import (
    ARM_B_ORDER,
    AUDIT_COLUMNS,
    build_source_schema,
    case_dir_name,
    tables_of,
)
from vault_agent.draft_requirements import draft_document
from vault_agent.draft_requirements import words as _words
from vault_agent.state import SourceTable


def words(name: str) -> str:
    """``SalesOrderHeader`` → *sales order header*; the product's rule (WP117)."""
    return _words(name)


def drafted_case_name(schema: str) -> str:
    return f"adventureworks_drafted_{schema.lower()}"


def classify(table: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """``("relationship" | "subtype" | "entity", the foreign keys covering the primary key)`` —
    on the extract's dicts, for `eval.c1_compare`; the product classifies the house format."""
    pk = set(table["primary_key"])
    covering = [fk for fk in table["foreign_keys"] if set(fk["columns"]) & pk]
    covered = set().union(*(set(fk["columns"]) for fk in covering)) if covering else set()
    if pk and pk <= covered:
        return ("subtype" if len(covering) == 1 else "relationship"), covering
    return "entity", covering


DRAFT_SOURCE = "eval.adventureworks.derive (schema_extract.json)"
DRAFT_DATE = "2026-10-30"  # the C1 experiment's date, so the documents regenerate byte-identically


def draft(extract: dict[str, Any], schema: str) -> str:
    """The drafted document of one subject area — since WP117 (ADR-0019) the product's
    `draft_document` on the house-format tables the derivation builds, so the eval's six
    documents are the product's output and regenerate from it."""
    tables = [
        SourceTable.model_validate(t)
        for t in build_source_schema(extract, schema)["source_schemas"]
    ]
    return draft_document(
        tables, schema, source=DRAFT_SOURCE, date=DRAFT_DATE, technical=AUDIT_COLUMNS,
    )


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
