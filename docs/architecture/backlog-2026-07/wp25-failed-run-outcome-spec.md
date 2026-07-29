# WP25 — A failed run is a first-class outcome

Status: Proposed · Size: M · Depends on: — (touches `graph.py` routing + `cli.py` exit
codes; coordinate with WP17's crash paths, already merged) · Source: project review
2026-07-29, finding 1

## 1. Problem

A model that never validates ends the run as a *success*. `route_after_validation`
(`graph.py:69-76`) routes to `END` once `modeling_attempts >= MAX_MODELING_ATTEMPTS`,
skipping `human_checkpoint` and `adr_author`. Reproduced with a stubbed always-failing
validator: the CLI prints "Human-in-the-loop checkpoint — requires sign-off (1 item)",
writes `review-queue.md` with **Status: requires sign-off**, writes no ADR, writes no
`pending.json` — and **exits 0**.

Three consequences, each independently wrong:

1. **Automation cannot tell.** Exit 0 is the documented code for "finalized — or paused"
   (`docs/operations/06-running.md:136`). Any script, cron, or CI wrapper treats a failed
   model as a good one.
2. **The blocking-checkpoint branch is unreachable.** `HumanReviewQueue.requires_signoff`
   (`orchestrator.py:90-96`) counts a validation error as blocking, and ADR-0006 plus
   `docs/architecture/1-architecture-overview.md:44` describe exactly this case ("a
   validation error remains after the re-model budget is exhausted"). Since `passed` is
   false precisely when an error issue exists, that state can never reach the node. The
   product documents a human gate it never opens.
3. **The queue points at nothing.** `review-queue.md` tells the human to sign off; there is
   no checkpoint thread, so `resume` answers "No unfinished run found".

## 2. Target design [ENFORCE]

### 2.1 Decide the semantics first (this is the WP's actual content)

ADR-0006 already answers it: an unvalidatable model is precisely the case a human gate
exists for. **Route the exhausted re-model loop into `human_checkpoint`** instead of `END`,
so the run pauses with the blocking errors in the queue and the human decides — accept the
model as-is (with the errors recorded, §2.3) or abandon it (`resume --discard`, WP17). This
makes the existing `requires_signoff` branch live rather than deleting it, and it makes
`review-queue.md` honest.

Graph change is one edge target in `route_after_validation`: on `passed == False` at the
cap, return `HUMAN_CHECKPOINT_NODE` (NOT `SOURCE_MAPPER_NODE` — mapping a model that does
not validate wastes tokens on a model that may be discarded; state that reasoning in the
code, since the "passed" path deliberately goes through the mapper first).

### 2.2 Exit codes tell the truth

`run` and `resume` exit **non-zero** when the run ends with `validation_report.passed`
false — including after a human accepts at the checkpoint, because the artifacts on disk
still carry known errors. Proposal: exit code **3** for "completed but the model did not
validate", keeping 1 for a pipeline failure and 2 for CLI usage (Click convention). A
pause stays 0 (it is a normal outcome, unchanged). Update the exit-code table in
`docs/operations/06-running.md` §6.6 and the troubleshooting chapter.

Also print, on that path, what it means in one line: the model did not validate after N
attempts, the errors are in the review queue and `report.html`, and the artifacts are for
diagnosis — not for deployment.

### 2.3 The ADR records that it was accepted over errors

When the human accepts a model whose validation failed, `adr_author` renders the ADR as
usual plus a **prominent** caveat listing the surviving error codes/constructs (derived
from `state.validation_report.issues`, matching on `severity`, never message text) and
stating that the model was accepted at the checkpoint despite them. An ADR that documents a
known-broken model without saying so would be worse than no ADR. (If WP26 has landed,
extend its structure; if not, this is a self-contained addition to `_render`.)

### 2.4 What must not change

The pass path (validator → source_mapper → checkpoint → ADR) byte-for-byte; the pause
semantics and `pending.json` shape (WP17); `MAX_MODELING_ATTEMPTS` and the retry feedback
(WP3 §2). The re-model loop itself is untouched — only what happens when it gives up.

## 3. Tests

1. Stubbed always-failing validator through the real graph: the run reaches
   `human_checkpoint`, `requires_signoff` is true, the graph interrupts (not `END`), and
   the modeler still ran exactly `MAX_MODELING_ATTEMPTS` times (the existing bound test
   must keep passing, adjusted for the new terminal node).
2. CLI: the same run exits 3, prints the one-line explanation, and leaves a resumable
   `pending.json` (`phase: paused`).
3. `resume --accept` on it finalises, writes the ADR **with** the error caveat, and still
   exits 3 (accepted ≠ validated).
4. `resume --discard` on it removes thread + pending (WP17 path, unchanged).
5. Regression: a passing run exits 0 and its artifacts/ADR are byte-identical to today.
6. The source mapper does NOT run on the failed path (no wasted LLM call) — assert via the
   decisions log with a stubbed mapper.

## 4. Acceptance criteria

1. No run can end with `passed == False` and exit code 0.
2. The review queue never points at a checkpoint that does not exist.
3. ADR-0006 and `1-architecture-overview.md` describe what the code does (update the ADR
   with a dated note if the routing decision refines it).
4. Standard DoD; `docs/operations/06-running.md` §6.6 and chapter 12 updated.

## 5. Out of scope

Changing `MAX_MODELING_ATTEMPTS`, adding a partial-model repair path, and any change to
what the validator considers an error.
