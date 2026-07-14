"""Opacity-masked degradation probe (WP9 §10.7) — closes the ADR-0008 precondition-(c) gap.

The mapping spike found that stripping comments/types did NOT degrade the LLM mapper on the
`messy_insurance` case, because its physical names (`PARTN_NR`, `VTG_NR`, …) are recognisable
DACH-insurance abbreviations the model knows (spike-mapping-results.md thin-evidence #1). To
actually stress ADR-0008 precondition (c) — "output quality is capped by input quality" — this
probe **masks** every physical column name to a meaningless `COL_0001…`, strips comments and
example values (keeping only type + distribution statistics), and re-runs the *production*
mapper against a correspondingly re-keyed golden set.

The acceptance property (WP9 §10.7): with the names/documentation gone the mapper must
**degrade honestly** — accuracy drops, more concepts land in `unresolved`, categories shift
away from `comment_grounded`, and it does NOT confidently hallucinate (no high-confidence wrong
proposals) — rather than inventing mappings.

The masking transform (:func:`mask_case`) is deterministic and keyless (unit-tested); only the
live probe (:func:`run_probe`) needs an API key.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter

from eval.datasets import DATASETS_ROOT
from eval.mapping import (
    AmbiguousEntry,
    ConceptRef,
    FalseFriend,
    GoldenCandidate,
    GoldenMapping,
    GoldenMappingEntry,
    concepts_for_prototype,
    load_golden_mapping,
)
from eval.scorers import score_mapping
from vault_agent.profiling import load_profiling
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import (
    ColumnProfile,
    DVModel,
    Hub,
    Satellite,
    SourceColumn,
    SourceTable,
    VaultAgentState,
)

MaskedInputs = tuple[list[SourceTable], GoldenMapping, dict[str, dict[str, ColumnProfile]]]


def mask_case(
    schema: list[SourceTable],
    golden: GoldenMapping,
    profiling: dict[str, dict[str, ColumnProfile]],
    *,
    mask_tables: bool = False,
) -> MaskedInputs:
    """Mask every physical column name to ``COL_NNNN`` consistently across schema, golden, and
    profiling; strip comments + example values; keep types + distribution statistics.
    ``mask_tables`` additionally renames tables to ``TBL_NN`` — maximal opacity, removing the
    last name signal so only types + distributions + the concept list remain.

    Deterministic: columns are numbered in schema order, so the same (table, column) always
    masks to the same name. The golden mapping is re-keyed to the masked names so the
    concept→column *relationship* is retained while its lexical signal is destroyed."""
    rename: dict[tuple[str, str], str] = {}
    table_rename: dict[str, str] = {}

    def masked(table: str, column: str) -> str:
        key = (normalize_identifier(table), normalize_identifier(column))
        if key not in rename:
            rename[key] = f"COL_{len(rename) + 1:04d}"
        return rename[key]

    def masked_table(table: str) -> str:
        if not mask_tables:
            return table
        key = normalize_identifier(table)
        if key not in table_rename:
            table_rename[key] = f"TBL_{len(table_rename) + 1:02d}"
        return table_rename[key]

    # Number every schema column first so golden/profiling reuse the same masked names.
    masked_schema: list[SourceTable] = []
    for table in schema:
        cols: list[str | SourceColumn] = [
            SourceColumn(name=masked(table.table, col.name), type=col.type)  # comment dropped
            for col in table.column_refs
        ]
        masked_schema.append(
            SourceTable(
                table=masked_table(table.table),
                columns=cols,
                schema=table.schema_name,
                database=table.database,
            )
        )

    masked_golden = GoldenMapping(
        mappings=[
            GoldenMappingEntry(
                concept=m.concept, entity=m.entity, source_table=masked_table(m.source_table),
                source_column=masked(m.source_table, m.source_column), kind=m.kind,
            )
            for m in golden.mappings
        ],
        ambiguous=[
            AmbiguousEntry(
                concept=a.concept, entity=a.entity, kind=a.kind,
                candidates=[
                    GoldenCandidate(table=masked_table(c.table), column=masked(c.table, c.column))
                    for c in a.candidates
                ],
            )
            for a in golden.ambiguous
        ],
        gaps=list(golden.gaps),  # gaps have no source column — unchanged
        false_friends=[
            FalseFriend(table=masked_table(f.table), column=masked(f.table, f.column), note="")
            for f in golden.false_friends
        ],
    )

    masked_profiling: dict[str, dict[str, ColumnProfile]] = {}
    for table_name, columns in profiling.items():
        masked_profiling[masked_table(table_name)] = {
            masked(table_name, name): ColumnProfile(
                name=masked(table_name, name),
                uniqueness_ratio=p.uniqueness_ratio,
                null_ratio=p.null_ratio,
                distinct_count=p.distinct_count,
                example_values=[],  # values leak semantics (an AHV number, a partner id)
            )
            for name, p in columns.items()
        }
    return masked_schema, masked_golden, masked_profiling


def _model_from_concepts(concepts: list[ConceptRef]) -> DVModel:
    """Encode the golden concept list as model constructs so the mapper's concept work-list
    surfaces them (business_key -> a hub, attribute -> a satellite attribute)."""
    hubs: list[Hub] = []
    attrs: dict[str, list[str]] = {}
    for ref in concepts:
        if ref.kind == "business_key":
            hubs.append(Hub(name=f"hub_{ref.entity}_{len(hubs)}", business_key=ref.concept,
                            source_entity=ref.entity or "x", description="d"))
        else:
            attrs.setdefault(ref.entity or "x", []).append(ref.concept)
    sats = [
        Satellite(name=f"sat_{entity}", parent=f"hub_{entity}", attributes=labels, description="d")
        for entity, labels in attrs.items()
    ]
    return DVModel(hubs=hubs, satellites=sats)


async def run_probe(case: str, repeats: int, mask_tables: bool = False) -> int:
    """Run the masked probe ``repeats`` times; print the honest-degradation verdict."""
    from vault_agent.agents.source_mapper import SourceMapperAgent

    root = DATASETS_ROOT / case
    schema = load_source_schemas(root / "source_schema_enriched.yml")
    golden = load_golden_mapping(root / "golden_mapping.yml")
    profiling = load_profiling(root / "profiling.yml")
    masked_schema, masked_golden, masked_profiling = mask_case(
        schema, golden, profiling, mask_tables=mask_tables
    )
    concepts = concepts_for_prototype(masked_golden)

    scope = "columns + TABLES masked (maximal opacity)" if mask_tables else "columns masked"
    print(f"opacity probe on {case!r}: {len(concepts)} concepts, {scope} to COL_NNNN/TBL_NN, "
          f"comments + example values stripped (types + profiling kept)\n")
    honest = True
    for i in range(repeats):
        state = VaultAgentState(
            dv_model=_model_from_concepts(concepts),
            source_schemas=masked_schema,
            profiling=masked_profiling,
        )
        state = await SourceMapperAgent().run(state)
        scores = {r.name: r.score for r in score_mapping(state.mappings, masked_golden)}
        cats = Counter(p.category for p in state.mappings.proposals)
        # Honest degradation: no CONFIDENT hallucination. A wrong proposal is one whose (table,
        # column) is not the golden pair; count those with confidence > 0.7.
        acceptable = {
            normalize_identifier(m.concept): (normalize_identifier(m.source_table),
                                              normalize_identifier(m.source_column))
            for m in masked_golden.mappings
        }
        confident_wrong = [
            p for p in state.mappings.proposals
            if p.confidence > 0.7
            and acceptable.get(normalize_identifier(p.concept))
            != (normalize_identifier(p.table), normalize_identifier(p.column))
        ]
        print(f"run {i + 1}/{repeats}: accuracy={scores['mapping_accuracy']:.3f} "
              f"gap={scores['gap_detection']:.3f} proposals={len(state.mappings.proposals)} "
              f"unresolved={len(state.mappings.unresolved)} "
              f"confident_wrong={len(confident_wrong)} categories={dict(cats)}")
        if confident_wrong:
            honest = False
    print(
        "\nVERDICT: "
        + ("PASS — degraded honestly (no confident hallucination)." if honest
           else "FAIL — produced high-confidence wrong proposals.")
    )
    return 0 if honest else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.opacity_probe")
    parser.add_argument("--case", default="messy_insurance")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--mask-tables", action="store_true",
                        help="also mask table names (maximal opacity — no name signal at all)")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv()
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("opacity probe needs ANTHROPIC_API_KEY (real LLM calls).", file=sys.stderr)
        return 2
    return asyncio.run(run_probe(args.case, args.repeat, args.mask_tables))


if __name__ == "__main__":
    raise SystemExit(main())
