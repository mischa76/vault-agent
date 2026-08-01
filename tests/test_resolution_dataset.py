"""WP29.1 — the `brownfield_resolution` case as an instrument (kick-off items 1 and 3).

Two properties, and the order matters. First that stripping the trap annotations out of
`source_schema.yml` changed nothing the pipeline can see — measured rather than argued, because
"YAML comments are dropped" is the sort of claim that is true until someone moves a line. Then
that the file no longer states its own answers, which is what makes blinded authoring possible
at all (WP30 §2.4a).

The parsed snapshot was captured from the ANNOTATED file, before the strip, and is the guard:
it fails if the cleaning touched a table, a column, a type or a column comment.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vault_agent.existing_model import load_existing_model
from vault_agent.source_schema import load_source_schemas

CASE = Path("eval/datasets/brownfield_resolution")
SCHEMA = CASE / "source_schema.yml"
SNAPSHOT = Path("tests/fixtures/resolution/source_schema_parsed.json")

# Tokens that would tell a reader the answer. `hub_customer`/`hub_account` are the existing
# vault's construct names: a schema that names them has stopped being a source description.
TELLS = (
    "TRAP", "CONTROL", "hub_customer", "hub_account", "same-as candidate", "false friend",
    # Not answers, but they tell the author what game is being played — that there IS an
    # existing vault to resolve against, and that correct answers exist somewhere. The first
    # blinded author read exactly this and reported it (docs/log.md, 2026-08-01); the second
    # read a milder version I had introduced while cleaning the file, and reported that too.
    "entity-resolution", "entity resolution", "existing bank vault", "spike",
    "trap-annotations", "golden_resolution",
)


def _parsed() -> list[dict[str, object]]:
    return [
        {
            "table": t.table,
            "columns": [
                {"name": c.name, "type": c.type, "comment": c.comment} for c in t.column_refs
            ],
        }
        for t in load_source_schemas(SCHEMA)
    ]


def test_stripping_the_annotations_changed_nothing_the_pipeline_reads() -> None:
    """Byte-equivalent INPUT before and after the strip — the WP29.1 kick-off's item 1 pin.

    The annotations were YAML comments, which `yaml.safe_load` discards, so no past score was
    ever affected by them. That is measured here rather than asserted: the snapshot was taken
    from the annotated file, and any drift in a table, column, type or column comment fails."""
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert _parsed() == expected


def test_the_schema_no_longer_states_its_own_answers() -> None:
    """A blinded author reads the RAW file, not the parsed one.

    This is the property the strip exists for. The pipeline never saw the annotations; the
    requirements author could not avoid them, which is how the contamination surfaced
    (docs/log.md, 2026-08-01)."""
    raw = SCHEMA.read_text(encoding="utf-8")
    found = [tell for tell in TELLS if tell in raw]
    assert not found, f"source_schema.yml still states its answers: {found}"


def test_the_annotations_survive_beside_the_case() -> None:
    """Stripped, not destroyed: the reasoning is a record and stays readable."""
    notes = CASE / "trap-annotations.md"
    assert notes.is_file(), "the trap reasoning must be preserved, not deleted"
    text = notes.read_text(encoding="utf-8")
    assert "TRAP 1" in text and "TRAP 5" in text


@pytest.mark.parametrize(
    ("loader", "path", "check"),
    [
        (load_existing_model, CASE / "existing_vault.yml",
         lambda m: sorted(h.name for h in m.hubs) == ["hub_account", "hub_customer"]),
        (load_source_schemas, SCHEMA, lambda t: len(t) == 8),
    ],
)
def test_the_case_loads_through_the_production_loaders(
    loader: object, path: Path, check: object
) -> None:
    """Wiring failures must be attributable to the wiring, not to the fixtures (item 3)."""
    assert check(loader(path))  # type: ignore[operator]
