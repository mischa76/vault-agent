# Kick-off WP25 — A failed run is a first-class outcome (review finding 2026-07-29 #1)

You are a senior engineer closing the last place where the product's own self-assessment and
its externally visible behaviour contradict each other: a model that never validates ends
the run with **exit code 0**, no ADR, and a `review-queue.md` that says "requires sign-off"
while no checkpoint exists. Keyless work (stub graph + CliRunner).

## Read first
1. `CLAUDE.md` (canon).
2. `docs/architecture/reviews/project-review-2026-07-29.md` finding 1 (with the reproduced
   CLI output).
3. `docs/architecture/backlog-2026-07/wp25-failed-run-outcome-spec.md` — binding spec.
4. `docs/architecture/adrs/ADR-0006-human-in-the-loop-review-queue.md` and
   `docs/architecture/1-architecture-overview.md` §Human-in-the-loop — both describe the
   behaviour you are making real; if your routing decision refines them, update them.
5. `graph.py` (`route_after_validation`), `agents/orchestrator.py`
   (`HumanReviewQueue.requires_signoff`), `cli.py` (`run`/`resume` exit paths, post-WP17),
   `agents/adr_author.py` (the caveat you extend), `tests/test_graph.py`
   (`test_persistent_failure_stops_at_retry_cap` — it encodes today's contract and must be
   updated deliberately).

## What to build (spec §2, summarised — the spec wins on conflict)
1. Route the exhausted re-model loop to `human_checkpoint` (NOT the source mapper — say why
   in the code: mapping a model that may be discarded burns tokens), so the existing
   blocking-signoff branch finally fires and the run pauses with the errors in the queue.
2. Exit code **3** from `run`/`resume` whenever the run ends with
   `validation_report.passed` false — including after a human accepts. Pause stays 0. One
   plain line explaining what the artifacts are (diagnosis, not deployment).
3. `adr_author`: when the accepted model failed validation, a prominent caveat listing the
   surviving error codes/constructs (matched on `severity`, never message text).
4. Docs: exit-code table (`06-running.md` §6.6), troubleshooting chapter, ADR-0006 /
   architecture overview if the routing decision refines them.

## Verify
- Spec §3 tests: the graph reaches the checkpoint and interrupts; the modeler still runs
  exactly `MAX_MODELING_ATTEMPTS` times; CLI exits 3 with a resumable pending; `--accept`
  finalises with the caveat and still exits 3; `--discard` unchanged; a passing run's
  artifacts and exit code byte-identical; the source mapper does not run on the failed path.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.

## Out of scope
`MAX_MODELING_ATTEMPTS`, partial-model repair, what the validator considers an error, and
anything WP24 owns (it may land first and touch the validator — rebase, do not fight it).

## Definition of Done
Spec §4 met with evidence (paste the new exit codes for both paths); CLAUDE.md milestone
paragraph appended — and be explicit that the previously-unreachable `requires_signoff`
branch is now live; conventional commit(s) referencing this kick-off and the spec.
