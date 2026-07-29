# WP27 — CI parity, retry policy, corrupt-pointer hygiene

Status: Proposed · Size: S · Depends on: — · Source: project review 2026-07-29, finding 5

## 1. Problems

**(a) CI type-checks less than the Definition of Done.** `.github/workflows/ci.yml:22` runs
`uv run mypy src`; `pyproject.toml:70` sets `files = ["src/vault_agent", "eval"]` and its own
comment records that an explicit path *overrides* that list. So `eval/` — 2,000+ lines
carrying the quality gates everything else leans on (WP6/13/14/16/18) — is strict-checked on
the maintainer's machine and not in CI. A green CI is currently a weaker statement than the
DoD it is supposed to enforce.

**(b) The retry policy ignores the server's own advice.** `ForcedToolCaller` retries
408/429/5xx three times at a fixed 2/4/8 s (`llm.py:246-248`), never reading `Retry-After`
and without jitter. A rate-limited enterprise key answering `Retry-After: 30` fails the call
after ~14 s of waiting that was guaranteed to be too short; parallel runs (eval `--repeat`,
ablation arms) retry in lockstep and re-collide. WP17 makes the resulting failure resumable,
which lowers the cost but not the waste.

**(c) One unguarded read on the recovery path.** `cli._read_pending` does a bare
`json.loads`, and `resume` calls it outside any try (`cli.py:1131`). `pending.json` is now a
documented file users are pointed at (WP17), so a truncated or hand-edited pointer surfaces
as a raw `JSONDecodeError` traceback — while `_report_crashed` and `_prune_orphan_threads`
already guard the same call.

## 2. Target design [ENFORCE]

### 2.1 CI runs the canonical gate

`ci.yml` runs `uv run mypy` (no path), matching the DoD and `pyproject`'s `files`. Verify
the run is green in CI-like conditions before merging — if `eval/` needs the `eval` extra to
type-check, install it in the workflow rather than narrowing the check back. While in the
file: keep the pinned action SHAs, and state in a comment WHY the invocation is bare.

### 2.2 Retry-After and jitter

In `ForcedToolCaller.call`'s retry loop:

- If the failing `APIStatusError` carries a `retry-after` (or `retry-after-ms`) response
  header, wait that long instead of the exponential value, capped at a constant
  (`_MAX_RETRY_DELAY_SECONDS`, suggested 60) so a hostile/absurd header cannot hang a run.
  Read the header defensively — a stub client in tests has no headers, and the SDK's
  exception surface must be **verified against the installed version, not assumed** (the
  WP8 `t_link` lesson).
- Otherwise keep the exponential base delay, plus **full jitter** (`delay * random()` or
  `delay/2 + random()*delay/2` — pick one and say why). Randomness must be injectable
  alongside the existing `sleep` seam so tests stay deterministic; the module-level default
  is the real RNG.
- Log at INFO which one applied and for how long — a run that waits 30 s must say so.

The retry *policy* stays otherwise unchanged: same status set, same `_MAX_RETRIES`, same
non-retryable propagation, same trace events.

### 2.3 A corrupt pointer is an attributable message

`_read_pending` raises a `ValueError` naming the file and the problem (house loader style,
as in `source_schema.load_source_schemas`) on unreadable/invalid JSON, or on a document that
is not a mapping with a `thread_id`. `resume` catches it and exits 1 with that message plus
the `--discard`/manual-deletion hint; the already-guarded callers keep swallowing it.

## 3. Tests

1. (a) is a CI-config change: assert nothing in pytest, but state in the commit body that
   the workflow was run/validated. Optionally a test asserting the workflow file contains
   the bare invocation — cheap drift protection for exactly the class of defect this is.
2. Retry-After honoured: stub client raising a 429 whose response carries `retry-after: 30`
   → the injected sleep sees 30 (capped value if over the cap), not 2.
3. Missing/garbage header → exponential path, and with the RNG stubbed the delay is exactly
   the pinned jittered value; the jitter never exceeds the base delay.
4. Cap: `retry-after: 3600` waits `_MAX_RETRY_DELAY_SECONDS`.
5. Corrupt `pending.json` → `resume` exits 1 with the attributable message and no traceback;
   the crash path and the orphan pruning still swallow it (existing behaviour pinned).

## 4. Acceptance criteria

1. CI's type check is the DoD's type check (same command, same file set).
2. No fixed-delay retry ignores a server-supplied `Retry-After`; every wait is logged and
   bounded; tests stay deterministic (injected sleep + RNG).
3. No user-editable file on the recovery path can produce a raw traceback.
4. Standard DoD.

## 5. Out of scope

Changing the retryable status set or `_MAX_RETRIES`, adding a circuit breaker, request-level
concurrency limits, and any streaming change (WP22 owns the transport).
