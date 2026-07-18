# Kick-off WP11 — Static HTML run report

You are a senior Python engineer working on **vault-agent** (this repository). Your task
is exactly one work package: a self-contained, deterministic `report.html` per run,
emitted by `write_outputs` — UI-track stage 1. A small commit series is fine (module +
tests, then CLI wiring).

## Read first, in this order
1. `CLAUDE.md` — repo canon; especially the WP5 §5.1 paragraph (single owner of the
   review-queue presentation knowledge) and the WP8/WP10 milestone paragraphs (role-
   qualified links, multi-source hubs — both must show correctly in the graph).
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD, and
   the 2026-07-18 addendum (CLI-first invariant).
3. `docs/architecture/backlog-2026-07/wp11-html-run-report-spec.md` — your spec,
   including the §1 invariant and the §3 rendering decision (already made — do not
   relitigate; Mermaid text + pinned CDN + fallback).
4. `src/vault_agent/agents/orchestrator.py` — `assemble_review_queue`, `KIND_HEADINGS`,
   `KIND_ORDER`, `aggregate_review_flags`, `render_review_queue_md`: you are writing the
   **third renderer**; import this API, never duplicate it.
5. `src/vault_agent/state.py` — `DVModel`, `Hub` (incl. `sources`), `Link` (use
   `hub_refs` and `resolve_driving_refs()`, never raw `connected_hubs`), `Satellite`
   (`sat_type`, `source_table`), `ValidationIssue`, `PipelineFlag`;
   `src/vault_agent/rules/dv2_rules.py` — `normalize_identifier` (node IDs — no new
   normalisation logic); `src/vault_agent/models/contract.py` —
   `ContractOwner.PLACEHOLDER_NAME`.
6. `src/vault_agent/cli.py` — `write_outputs`, `_print_summary`/`_print_checkpoint`
   (the summary lines you extend), and `tests/test_cli.py` (the WP5 renderer-parity test
   pattern you extend to the report) + `tests/test_staging_regression.py` (the pinned-
   fixture pattern for the idempotency test).
7. Current Mermaid docs for the pinned-major CDN include + init API — verify against the
   live docs, not memory (the WP8 t_link lesson).

## Task
New deterministic module `src/vault_agent/report.py` (`build_report(state)`,
`build_model_mermaid(model)`), wired into `write_outputs` (`report.html` at the output
root, counts + summary line) — content sections, graph semantics (roles, driving keys as
thick edges, multi-source cylinders, sat_type classes), escaping and determinism rules
exactly per spec §4–§5.

## Constraints
- No new runtime dependency; stdlib templating only (jinja2 was removed in WP5 — do not
  reintroduce). No timestamps or environment info — byte-identical output for identical
  state.
- Every LLM-derived string passes `html.escape` (and Mermaid label escaping). Treat all
  state strings as hostile.
- The report is additive: every other written file stays byte-identical; existing
  guardrail and baseline tests must pass unchanged.
- `graph.py` untouched; no business logic in the report module — presentation only.

## Definition of Done
Spec acceptance criteria 1–5 verified (2 needs the messy_insurance artifacts; if you
cannot run live LLM calls, build the report from the checked-in eval fixtures and note
it) · all new tests keyless · `uv run pytest -q` / `ruff` / `uv run mypy src/vault_agent`
strict green · note in your handover that a manual browser check (online + CDN-blocked)
is required before release · CLAUDE.md milestone paragraph · conventional commits
referencing the spec.
