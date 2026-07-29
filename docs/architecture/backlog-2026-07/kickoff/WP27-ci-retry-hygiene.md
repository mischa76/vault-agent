# Kick-off WP27 — CI parity, retry policy, corrupt-pointer hygiene (review finding 2026-07-29 #5)

You are a senior engineer executing a three-item hygiene batch: CI must enforce the same
type check the DoD claims, the retry loop must listen when the server says how long to wait,
and the one user-editable file on the recovery path must not produce a raw traceback.
Keyless work.

## Read first
1. `CLAUDE.md` (canon) and `docs/architecture/backlog-2026-07/00-overview.md` §Shared
   conventions §6 (the DoD whose type check CI is supposed to be).
2. `docs/architecture/reviews/project-review-2026-07-29.md` finding 5.
3. `docs/architecture/backlog-2026-07/wp27-ci-retry-hygiene-spec.md` — binding spec.
4. `.github/workflows/ci.yml`, `pyproject.toml` `[tool.mypy]` (its comment already records
   why the bare invocation matters).
5. `llm.py` (the retry loop, the injectable `sleep` seam you extend with an injectable RNG,
   and the trace events that must not change), `tests/test_llm.py` (stub client + no-sleep
   pattern).
6. `cli.py` `_read_pending` and its callers — two already guard it, `resume` does not.

## What to build (spec §2, summarised — the spec wins on conflict)
1. CI runs `uv run mypy` (bare), covering `eval/` as the DoD does; install whatever extra
   that needs rather than narrowing the check. Keep the pinned action SHAs.
2. `Retry-After` (or `retry-after-ms`) honoured when the failing `APIStatusError` carries
   it, capped at `_MAX_RETRY_DELAY_SECONDS`; otherwise exponential **plus jitter**, with the
   RNG injectable so tests stay deterministic. **Verify the SDK's exception/header surface
   against the installed version** — the WP8 `t_link` lesson. Log which branch applied and
   for how long; retry policy otherwise unchanged.
3. `_read_pending` raises an attributable `ValueError` (file + problem, the
   `load_source_schemas` style) on invalid JSON or a document without a `thread_id`;
   `resume` catches it, exits 1 with the message and the `--discard`/delete hint. The
   already-guarded callers keep swallowing it.

## Verify
- Spec §3 tests: `retry-after: 30` → the injected sleep sees 30; garbage/missing header →
  the pinned jittered exponential; `retry-after: 3600` → capped; corrupt `pending.json` →
  attributable exit 1, no traceback, while the crash/pruning paths still swallow it.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green — and confirm the workflow
  change itself is green (say so in the commit body; a CI edit nobody ran is not done).

## Out of scope
The retryable status set, `_MAX_RETRIES`, circuit breakers, concurrency limits, and the
streaming transport (WP22 owns `ForcedToolCaller`'s call shape — coordinate/rebase if it
lands first).

## Definition of Done
Spec §4 met; CLAUDE.md milestone paragraph appended; conventional commit(s) referencing this
kick-off and the spec.
