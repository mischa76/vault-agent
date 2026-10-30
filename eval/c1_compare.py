"""The C1 experiment's comparison — written before the result existed (2026-10-30).

Reads the two chain results (arm A, the authored requirements; arm T, the drafted ones), their
per-step result files and the kept step outputs, and computes every prediction of
`docs/architecture/backlog-2026-07/c1-experiment-drafted-requirements.md` §3 from what is on
disk — never from a reading of it. Keyless and pure.

Usage::

    uv run python -m eval.c1_compare --control <arm A result json> \\
        --treatment <arm T result json> --outputs <kept-outputs-root>
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

from eval.adventureworks.draft_requirements import classify
from eval.wp34_check import cross_domain_links
from vault_agent.rules.dv2_rules import (
    canonical_hub_key_column,
    construct_base_name,
    hub_binds_to_source_table,
    normalize_identifier,
)
from vault_agent.state import DVModel

EXTRACT = Path("eval/datasets/adventureworks/schema_extract.json")
SUBTYPES = ("Employee", "Vendor", "Store", "SalesPerson", "Person", "Password")
C1_TABLES = ("BusinessEntityAddress", "ProductProductPhoto")


def _step_files(result_path: Path) -> list[Path]:
    """The per-step result files beside a chain result, in step order."""
    stamp = result_path.name.split("-run")[0]
    files = sorted(result_path.parent.glob(f"{stamp}-step*-run1.json"))
    def index(path: Path) -> int:
        match = re.search(r"-step(\d+)-", path.name)
        return int(match.group(1)) if match else 0
    return sorted(files, key=index)


def _final_model(outputs: Path, case: str, stamp: str) -> DVModel:
    text = (_last_step(outputs, case, stamp) / "metadata" / "dv_model.yml").read_text(
        encoding="utf-8"
    )
    return DVModel.model_validate(yaml.safe_load(text))


def _last_step(outputs: Path, case: str, stamp: str) -> Path:
    steps = sorted(
        (outputs / case / stamp).glob("step*"), key=lambda p: int(p.name[4:].split("_")[0])
    )
    return steps[-1]


def _stage_bindings(outputs: Path, case: str, stamp: str) -> dict[str, str]:
    path = _last_step(outputs, case, stamp) / "metadata" / "source_catalogue.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(doc.get("stage_bindings") or {})


def _mapping_categories(outputs: Path, case: str, stamp: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in (outputs / case / stamp).glob("step*"):
        path = step / "mappings.review.yml"
        if not path.exists():
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for proposal in doc.get("proposals") or []:
            counts[proposal["category"]] = counts.get(proposal["category"], 0) + 1
    return dict(sorted(counts.items()))


def surrogate_keyed_hubs(model: DVModel) -> list[str]:
    """Hubs whose canonical key column, normalised, ends in ``ID`` (prediction P3)."""
    return sorted(
        h.name for h in model.hubs
        if normalize_identifier(canonical_hub_key_column(h)).endswith("ID")
    )


def hubs_binding(model: DVModel, table: str) -> list[str]:
    """Every hub the table feeds — its own, or a multi-source hub it is one source of."""
    return sorted(h.name for h in model.hubs if hub_binds_to_source_table(h, table))


def own_hubs(model: DVModel, table: str) -> list[str]:
    """Hubs whose source entity IS the table — a hub of its own (predictions P1 and P2), as
    against a multi-source hub the table merely feeds (`Employee` → `hub_business_entity`)."""
    wanted = normalize_identifier(table)
    return sorted(
        h.name for h in model.hubs
        if h.source_entity and normalize_identifier(h.source_entity) == wanted
    )


def constructs_for(model: DVModel, bindings: dict[str, str], table: str) -> dict[str, list[str]]:
    """What a run built for one source table: hubs that bind it, links and satellites whose
    staging binds it (by the travelling catalogue's stage bindings), by name."""
    bound = {
        stage for stage, relation in bindings.items()
        if normalize_identifier(relation) == normalize_identifier(table)
    }

    def reads(name: str) -> bool:
        base = normalize_identifier(construct_base_name(name)).lower()
        return any(
            normalize_identifier(stage[4:]).lower() == base
            for stage in bound if stage.startswith("stg_")
        )
    return {
        "hubs": hubs_binding(model, table),
        "links": sorted(lk.name for lk in model.links if reads(lk.name)),
        "satellites": sorted(s.name for s in model.satellites if reads(s.name)),
    }


def arm(result_path: Path, outputs: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    metrics = result.get("metrics", result)
    case = result.get("case", result_path.parent.name)
    stamp = result_path.name.split("-run")[0]
    steps = metrics["chain_steps"]
    step_scores = [
        json.loads(p.read_text(encoding="utf-8")).get("scores", {})
        for p in _step_files(result_path)
    ]
    model = _final_model(outputs, case, stamp)
    bindings = _stage_bindings(outputs, case, stamp)
    extract = json.loads(EXTRACT.read_text(encoding="utf-8"))
    relationships = [t["name"] for t in extract["tables"] if classify(t)[0] == "relationship"]
    return {
        "case": case, "stamp": stamp,
        "constructs": steps[-1]["constructs"],
        "constructs_per_step": [s["constructs"] for s in steps],
        "decisions_per_step": [s["review_decisions"] for s in steps],
        "decisions": metrics["review_decisions"],
        "review_items": metrics["review_items_total"],
        "scores_per_step": step_scores,
        "wall_clock_seconds": metrics["wall_clock_seconds"],
        "usage": metrics["usage"],
        "cross_domain_links": len(cross_domain_links(steps)),
        "subtype_own_hubs": {t: own_hubs(model, t) for t in SUBTYPES},
        "subtype_fed_hubs": {t: hubs_binding(model, t) for t in SUBTYPES},
        "relationship_hubs": {t: own_hubs(model, t) for t in relationships if own_hubs(model, t)},
        "relationship_links": {
            t: constructs_for(model, bindings, t)["links"] for t in relationships
        },
        "surrogate_keyed": surrogate_keyed_hubs(model),
        "hub_keys": {
            h.name: canonical_hub_key_column(h) for h in sorted(model.hubs, key=lambda h: h.name)
        },
        "c1_tables": {t: constructs_for(model, bindings, t) for t in C1_TABLES},
        "mapping_categories": _mapping_categories(outputs, case, stamp),
        "link_proposals": metrics.get("link_proposals", {}),
    }


def _gate(scores: list[dict[str, Any]], name: str) -> list[float | None]:
    return [s.get(name) for s in scores]


def report(a: dict[str, Any], t: dict[str, Any]) -> str:
    lines = [
        f"| | arm A (authored) `{a['stamp']}` | arm T (drafted) `{t['stamp']}` |", "|---|---|---|"
    ]

    def row(label: str, va: Any, vt: Any) -> None:
        lines.append(f"| {label} | {va} | {vt} |")

    def shape(c: dict[str, int]) -> str:
        return f"{c['hubs']} / {c['links']} / {c['satellites']}"

    def present(d: dict[str, list[str]]) -> Any:
        return {k: v for k, v in d.items() if v} or "none"

    row("step-5 hubs / links / satellites", shape(a["constructs"]), shape(t["constructs"]))
    for key in ("hubs", "links", "satellites"):
        row(f"{key} per step", [c[key] for c in a["constructs_per_step"]],
            [c[key] for c in t["constructs_per_step"]])
    row("review decisions per step", a["decisions_per_step"], t["decisions_per_step"])
    row("review decisions, sum", a["decisions"], t["decisions"])
    row("review items, sum", a["review_items"], t["review_items"])
    for gate in ("validation_gate", "existing_construct_preservation", "project_self_contained",
                 "pipeline_health", "mapping_coverage"):
        row(gate + " per step", _gate(a["scores_per_step"], gate),
            _gate(t["scores_per_step"], gate))
    row("wall-clock (min)", round(a["wall_clock_seconds"] / 60, 1),
        round(t["wall_clock_seconds"] / 60, 1))
    row("usage", a["usage"], t["usage"])
    row("cross-domain links", a["cross_domain_links"], t["cross_domain_links"])
    row("P1 own hubs of the subtypes", present(a["subtype_own_hubs"]),
        present(t["subtype_own_hubs"]))
    row("P1 hubs the subtypes feed", present(a["subtype_fed_hubs"]),
        present(t["subtype_fed_hubs"]))
    row("P2 relationship tables with an own hub", a["relationship_hubs"] or "none",
        t["relationship_hubs"] or "none")
    row("P2 relationship tables read by a link",
        sum(1 for v in a["relationship_links"].values() if v),
        sum(1 for v in t["relationship_links"].values() if v))
    row("P3 hubs keyed on an …ID column", f"{len(a['surrogate_keyed'])} of {len(a['hub_keys'])}",
        f"{len(t['surrogate_keyed'])} of {len(t['hub_keys'])}")
    row("mapping categories", a["mapping_categories"], t["mapping_categories"])
    row("link proposals", a["link_proposals"], t["link_proposals"])
    for table in C1_TABLES:
        row(f"C1: {table}", a["c1_tables"][table], t["c1_tables"][table])
    lines.append("")
    for label, data in (("arm A", a), ("arm T", t)):
        lines.append(f"Hubs keyed on an …ID column, {label}: " + ", ".join(data["surrogate_keyed"]))
        lines.append(f"Hub keys, {label}: " + json.dumps(data["hub_keys"]))
        lines.append(f"Relationship tables read by a link, {label}: " + json.dumps(
            {k: v for k, v in data["relationship_links"].items() if v}
        ))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--treatment", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    args = parser.parse_args(argv)
    print(report(arm(args.control, args.outputs), arm(args.treatment, args.outputs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
