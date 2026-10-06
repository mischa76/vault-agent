---
type: spec
status: not-measured
updated: 2026-10-06
---

# WP51 — A dropped hub's payload moves to its kept twin

Status: **Approved and in progress** (2026-10-06, user: „ok, bau das Umhängen der Payload an den
Zwilling") · Owner: Mischa Eismann · Author: Claude. Extends the repair memory (WP44, WP49, WP50)
at the point WP44 §5 deferred: „one case is not a rule". No prompt change; no model call.

## 1 Problem, measured

Fifth chain, `20261006T032619166848Z`, step 2 (`docs/log.md` 2026-10-06): attempt 3 re-emitted two
retired hubs; the memory dropped them with three links and four satellites, seven `retired_orphan`
decisions — and the step was green. But `hub_candidate_business_entity`, the twin the collision
remedy had **kept**, ended without a satellite, because the candidate's payload (`Resume`,
`ModifiedDate`) sat on the dropped `hub_job_candidate` and went to a decision item instead of
moving to the hub that stands for the same entity. The invention clause of WP34 §6 counted it. On
2026-10-04 (WP44 §5) the same shape had appeared once; this is the second case.

A retired hub and its kept twin are, by the remedy's own finding, one entity on one source
relation under two keys. A satellite of the dropped hub describes that entity; its home is the
twin. A link that named the dropped hub expresses a relationship of that entity; its participation
is the twin's — unless the twin already takes part, in which case the link joined the entity to
itself and is no relationship at all.

## 2 The rule

**When the memory drops a hub that has a kept twin, the hub's dependents move to the twin.**

1. The retirement knows the twin. `ValidationIssue.retires_into` carries the hub the remedy kept —
   `HubCollisionRemedy.keep` for a collision, `SecondHubRemedy.parent` for a second hub (WP50) —
   and the validator records it as `RetiredConstruct.kept_twin`.
2. `drop_retired`, when it drops a hub (by name or shape) whose `kept_twin` is a hub of the model
   and not itself retired: every satellite parented on the dropped hub is re-parented to the twin;
   every link naming the dropped hub has that participation re-pointed to the twin (role, alias and
   translation kept) — unless the twin already takes part in the link, which is then dropped as
   today (an entity's link to itself). Each move is a `retired_reparented` flag, a **disclosure**
   under WP43: the payload kept its meaning and found its home deterministically. Without a twin,
   or with the twin absent or retired, everything is dropped as today, a decision.
3. The key gates judge the result as they judge any satellite: a re-parented satellite whose own
   relation does not carry the twin's key (`sat_employee_pay_rate` from `EmployeePayHistory`, the
   twin `hub_employee` on `NationalIDNumber`) is repaired by the licence machinery when a licence
   exists (WP40, as it is for any satellite on `hub_employee` from that table), else refused by
   `E_SAT_KEY_NOT_IN_SOURCE` with WP46's remedy — the move is right, the key is the gate's business.

## 3 Guards before the change

1. The validator records `kept_twin` from a collision remedy's `keep` and from WP50's parent.
2. On the fifth chain's step-2 attempt-1 shape (fixture cut from llm_call 30): with both
   retirements carrying their twins, the re-emitted model keeps `hub_employee` and
   `hub_candidate_business_entity`, loses the two retired hubs, re-parents
   `sat_job_candidate_details` to `hub_candidate_business_entity` and `sat_employee_pay_rate` to
   `hub_employee`, re-points `link_employee_assignment`'s first participation to `hub_employee`,
   drops `link_candidate_employee` (the twin already takes part) as an orphan, and its satellites
   with it; the flags are three `retired_reparented`, one `retired_orphan` for the self-link, two
   `retired_reemitted`; the backstop event lists what moved.
3. Validated afterwards (no schema): no `E_HUB_HK_COLLISION`; the kept twin has its satellite.
4. Without a twin on the retirement the behaviour is WP44's: everything dropped, orphans.

## 4 Pre-registration

Replayed on step 2 of the fifth chain: the kept twin keeps `Resume`, the invention clause counts
2 zero-satellite hubs (`hub_product_description`, `hub_shopping_cart`) — met; orphan decisions in
that step fall from seven to one. On the next chain: the memory's enforcement no longer costs the
kept hub its payload; `retired_orphan` decisions appear only for self-links and satellites of
dropped links.

## 5 Not in this WP

Carrying retirements across chain steps; re-parenting across *different* entities (never — the
twin relation is the only one the rule reads).

## 6 Results

*(appended after the change)*

**2026-10-06 — built, keyless.** Commits `ce0c16b` (guards, failing) and `d7bb1d1` (the change).
`ValidationIssue.retires_into`, `RetiredConstruct.kept_twin` (recorded for collisions and WP50
second hubs), `drop_retired` re-parenting satellites and re-pointing link participations to the
twin, `retired_reparented` as a disclosure. Guards 1–4 pass on the fifth chain's step-2 attempt-1
shape: two satellites move, one link re-points, the self-link is dropped, the twin keeps `Resume`,
no collision afterwards. 1133 tests, ruff, mypy. §4's chain half is **not yet measured live**.
