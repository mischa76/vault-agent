"""The docs retrofit moved a chronicle, it did not summarise one.

On 2026-07-31 the ~47 chronological paragraphs of ``CLAUDE.md``'s "Current milestone" section
were moved to ``docs/log.md`` (see ``docs/methodology/llm-wiki-mapping.md`` for why). The value
of that section is the retrospective corrections and measurement findings it carries — the part
no spec document repeats — so the move has to be provable, not asserted.

The fixture holds one sha256 per pre-retrofit paragraph, taken at commit 699ec62. This test
asserts every one of them still appears in ``docs/log.md`` byte-for-byte. It deliberately does
NOT read git: a shallow CI checkout would not have the commit, and the fixture makes the guard
self-contained in the style of ``tests/fixtures/steering/modeler_rules_pre_wp16.txt``.

``docs/log.md`` is append-only, so this test only ever gets stricter: new entries are free,
losing an old one fails.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "docs" / "log.md"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "log" / "pre_retrofit_paragraphs.sha256"


def _expected() -> list[tuple[str, str]]:
    """(sha256, human-readable head) for every pre-retrofit paragraph."""
    rows: list[tuple[str, str]] = []
    for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, _, head = line.partition("  ")
        rows.append((digest, head))
    return rows


def _log_blocks() -> set[str]:
    """sha256 of every blank-line-delimited block of the log.

    Hashed after ``rstrip()``, matching how the fixture was taken: trailing whitespace is not
    content. Every other character is — a reworded sentence fails this test.
    """
    text = LOG_PATH.read_text(encoding="utf-8")
    blocks = (b.rstrip() for b in re.split(r"\n\s*\n", text) if b.strip())
    return {hashlib.sha256(b.encode("utf-8")).hexdigest() for b in blocks}


def test_every_pre_retrofit_paragraph_survives_in_the_log() -> None:
    expected = _expected()
    assert len(expected) == 63, "the fixture itself was modified"

    present = _log_blocks()
    missing = [head for digest, head in expected if digest not in present]

    assert not missing, (
        f"{len(missing)} of {len(expected)} pre-retrofit CLAUDE.md paragraph(s) are no longer "
        f"in docs/log.md byte-for-byte. The log is append-only — an entry may be added after "
        f"one, never edited. Missing:\n  " + "\n  ".join(missing)
    )


def test_log_entries_are_greppable_by_date() -> None:
    """The one convention the log promises its readers: `grep '^## \\[' docs/log.md`."""
    text = LOG_PATH.read_text(encoding="utf-8")
    headings = re.findall(r"^## \[(\d{4}-\d{2}-\d{2})\] (.+)$", text, re.M)

    assert len(headings) >= 63, f"expected one heading per entry, found {len(headings)}"
    dates = [d for d, _ in headings]
    assert dates == sorted(dates), "log entries are chronological; the newest goes at the bottom"
    assert all(title.strip() for _, title in headings), "every entry needs a title"
