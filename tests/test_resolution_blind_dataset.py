"""WP29 §4 acceptance #3 — the blinded twin differs in EXACTLY the column comments.

A blinded case that also moved a table, renamed a column or changed a type would silently
measure a different landscape, and the accuracy drop it produced would mean nothing. So the
blinding is a mechanical derivation, re-run here and compared, rather than a hand-edited file.

The same guard pattern WP29.1 used for stripping the trap annotations: pin what the pipeline
reads, not what the file looks like.
"""
from __future__ import annotations

import re
from pathlib import Path

from vault_agent.source_schema import load_source_schemas

CLEAN = Path("eval/datasets/brownfield_resolution/source_schema.yml")
BLIND = Path("eval/datasets/brownfield_resolution_blind/source_schema.yml")


def _structure(path: Path) -> list[tuple[str, tuple[tuple[str, str | None], ...]]]:
    """Tables, columns and types in order — everything except the comments."""
    return [
        (t.table, tuple((c.name, c.type) for c in t.column_refs))
        for t in load_source_schemas(path)
    ]


def _comments(path: Path) -> list[str | None]:
    return [c.comment for t in load_source_schemas(path) for c in t.column_refs]


def test_the_blinded_twin_has_the_same_structure() -> None:
    """Same tables, same columns, same types, same order — or the probe is not a twin."""
    assert _structure(BLIND) == _structure(CLEAN)


def test_the_blinded_twin_has_no_comments_and_the_clean_one_does() -> None:
    """The blinding, stated as the property it is: the data dictionary is gone."""
    assert all(c is None for c in _comments(BLIND))
    assert any(c for c in _comments(CLEAN)), "the clean case must carry the evidence"


def test_the_derivation_is_reproducible_from_the_clean_case() -> None:
    """Re-derive and compare. A hand-edit to the blinded file fails here.

    This is what makes the twin auditable: the blinding is one rule — drop every ``comment:``
    — applied mechanically, not a judgement someone made line by line."""
    rederived = [
        re.sub(r',\s*comment:\s*".*?"\}', "}", line)
        for line in CLEAN.read_text(encoding="utf-8").splitlines()
        if not line.startswith("#") and line.strip() != "source_schemas:"
    ]
    on_disk = [
        line
        for line in BLIND.read_text(encoding="utf-8").splitlines()
        if not line.startswith("#") and line.strip() != "source_schemas:"
    ]
    assert on_disk == rederived


def test_the_golden_is_the_same_ground_truth() -> None:
    """Blinding removes the mechanism's EVIDENCE, never the correct answer.

    The expected answers are identical to the clean case's, which is the whole point: the drop
    in `resolution_accuracy` between the two is the measurement. A blinded golden with softened
    expectations would measure nothing."""
    clean = (CLEAN.parent / "golden_resolution.yml").read_text(encoding="utf-8")
    blind = (BLIND.parent / "golden_resolution.yml").read_text(encoding="utf-8")
    assert clean == blind


def test_the_blinded_schema_does_not_state_what_it_is_for() -> None:
    """The third time this leaked, and the first time a test catches it.

    A blinded requirements author reads this raw file. Twice before, the leak came from the
    person doing the blinding rather than from the fixture: the clean case's schema named which
    table WAS the customer (2026-08-01), and this file's first header named the expected
    `unresolved` fallback outright. Both were reported by the authoring agent, not by a check.

    The tells are checked in the RAW text because that is what an author sees; the pipeline
    never reads comments at all."""
    from tests.test_resolution_dataset import TELLS

    raw = BLIND.read_text(encoding="utf-8")
    found = [tell for tell in (*TELLS, "blinded", "degradation", "false_merge")
             if tell.lower() in raw.lower()]
    assert not found, f"the blinded schema tells its reader what to answer: {found}"
