---
type: spec
status: not-measured
updated: 2026-10-09
---

# WP57 — The retry is a repair, not a new draft: the previous model travels with the issues

Status: **Approved and in progress** (2026-10-09, user: „super, machen wir 1,2 und lassen die 11.
kette drüber rattern“) · Owner: Mischa Eismann · Author: Claude. Touches the modeler's retry
payload, a state field and one steering line (WP16 registry + ledger). A **prompt and payload
change**, re-tested per model release like every steering line; no gate, no backstop.

## 1 Problem, measured

Tenth chain, `20261008T223946700186Z`, step 3 (`docs/log.md` 2026-10-09): attempt 2 had answered
the payload gate — two transaction satellites on `hub_transaction` — with one attribute overlap
left; attempt 3 came back with attempt 1's shape and neither satellite, and the step was red. The
request for attempt 3 named one overlap and two retirements, nothing about the transaction
constructs. The mechanism is in the code: the retry payload carries the requirements, the business
keys, `previous_validation_issues` and `retired_constructs` — **not the previous model**. Every
attempt is a fresh draw from the same inputs; what an attempt got right survives only by chance.
That is the oscillation recorded on every red step since 2026-09-17, and the reason „a step's
colour is whether three attempts suffice“.

## 2 The rule

**On a retry the modeler receives its own previous model and is asked to change exactly what the
issues name.**

1. `VaultAgentState.previous_delta`: the model the modeler emitted in its last attempt — after
   parsing and the memory's drops, **before** the brownfield merge, so in brownfield mode it is the
   delta, never the vault. Set by the modeler on every attempt.
2. The retry payload (when `previous_validation_issues` is sent) carries `previous_model`: the
   previous delta, serialised like the modeler's own output (hubs, links, satellites; defaults and
   nulls omitted).
3. Steering line `repair_not_redraft` (WP16 registry, ledger row): when the input carries
   `previous_model`, it is the modeler's own last attempt; return it as the complete model with
   exactly the changes the issues and their remedies require, keeping every construct no issue
   names — same name, key, parent and attributes. The existing template paragraph on
   `previous_validation_issues` stands; this line makes „preserve what was correct“ operational
   by giving the modeler the thing to preserve.
4. Nothing deterministic enforces the preservation: a modeler that still reshapes is reported by
   the gates as today. The measure is the **carry-over** — the share of the previous attempt's
   constructs (by name) present in the next — readable from consecutive `emit_dv_model` payloads
   in the trace; before WP57 the tenth chain's step 3 carried 0 of 2 transaction satellites from
   attempt 2 into attempt 3.

## 3 Guards before the change

1. A first attempt's payload carries no `previous_model`; after a run `state.previous_delta` equals
   the parsed delta (greenfield: the model itself).
2. With a validation error recorded and a `previous_delta` set, the retry payload carries
   `previous_model` with exactly the delta's constructs; in brownfield mode the existing vault's
   constructs are not in it.
3. The active steering rules contain `repair_not_redraft`, and the rendered system prompt carries
   its text.

## 4 Pre-registration

On the eleventh chain: a retry's model carries over ≥ 90 % of the previous attempt's constructs
by name (the tenth chain's step 3: 0 of 2 on the constructs that mattered); the number of attempts
per step does not rise; no step goes red on a class an earlier attempt had already satisfied.
Cost: ≈ 0.1–0.2 USD more input per retry (the previous model, ≈ 10–40k tokens on Opus at the
cached rate where it hits).

## 5 Not in this WP

A deterministic preservation backstop (restoring constructs the retry dropped without an issue
naming them — a candidate if the steering alone does not hold, like WP44's memory after the
collision remedy's steering did not); the attempt budget.

## 6 Results

*(appended after the change)*
