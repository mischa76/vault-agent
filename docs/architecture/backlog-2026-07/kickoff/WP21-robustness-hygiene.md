# Kick-off WP21 — Robustness + hygiene batch (review findings 2026-07-28 #6/#7a–f)

You are a senior engineer executing a seven-item cleanup batch: one behaviour fix (a bad
input document must flag-and-skip, never crash the run) and six hygiene items. Keyless
work. **STOP precondition: WP17 must be merged** — §2.7 touches the resume flow WP17
reworks.

## Read first
1. `CLAUDE.md` (canon).
2. `docs/architecture/backlog-2026-07/wp21-robustness-hygiene-spec.md` — the binding
   spec; every item has its location there.
3. The touched files: `agents/requirements_parser.py` (`_read_document`), `llm.py`
   (`_record_usage` vs `emit_trace` — copy the latter's guard), `agents/orchestrator.py`
   (`aggregate_review_flags`), `agents/validator.py` (docstring only),
   `agents/code_generator.py` (multi-source satellite branch), `agents/dv2_modeler.py`
   (`_validate_items`), `cli.py` (`--no-write` semantics, post-WP17 state).
4. `tests/test_llm.py` (the raising-trace-recorder test you mirror for usage),
   `tests/test_cli.py` (non-TTY byte-identity guard), `tests/fixtures/report/
   report_fixture.html` (may need a deliberate regeneration if a collapsed source string
   renders in it — check, and say so in the commit if you do).

## What to build (spec §2, summarised — the spec wins on conflict)
1. (6) `_read_document`: wrap the three extractors; any read/extraction error → error
   flag (`MISSING_INPUT`, asset = path, message names the exception) + skip. Broad
   `except Exception` around the pypdf/docx calls is correct here — comment why.
2. (7a) try/except around the usage recorder, warning + `exc_info`, never propagate.
3. (7b) Collapsed review lines: source = the members' single distinct source, else
   `"multiple agents"`.
4. (7c) Validator docstring: drop the stale "30" literal; keep "count the codes".
5. (7d) Multi-source satellite branch emits `_collision_warnings` once per satellite.
6. (7e) `_validate_items` passes a usable `record["name"]` as the flag's `asset`.
7. (7f) `--no-write` = artifacts only, documented; `resume` gains `--write/--no-write`;
   the pause message notes that resuming writes unless `--no-write` is repeated.

## Verify
- Spec §3 tests all green (three corrupt-document cases; raising usage recorder;
  multi-agent collapsed source; single COLUMN_COLLISION on the multi-source path; asset
  on dropped records; `resume --no-write`).
- Renderer parity: md, CLI, and HTML report show the same collapsed source text (the
  three renderers share the WP5 §5.1 API — no per-renderer logic).
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green; report fixture change
  (if any) regenerated deliberately and named in the commit.

## Out of scope
New FlagKind values, happy-path behaviour changes beyond the collapsed source text, and
anything WP17/WP20 own.

## Definition of Done
Spec §4 met with evidence; CLAUDE.md milestone paragraph appended; conventional
commit(s) referencing this kick-off and the spec.
