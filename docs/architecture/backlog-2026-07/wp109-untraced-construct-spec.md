---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP109 — `W_UNTRACED_CONSTRUCT`: a construct of this run that cites no requirement (C6)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog) · Owner: Mischa Eismann ·
Author: Claude. C6 recorded 2026-10-21: the modeler is told to cite `requirement_ids` for every construct and no gate
checks it.

## 1 What the evidence says before the change

Every persisted model in `eval/results` (15 files) and the demo's five recorded runs: **no** construct of a run lacks
`requirement_ids` except the links the ratified-proposal applier builds (WP34 — twenty-third chain step 4: 3; arm A
steps 4 and 5: 4 and 4; arm T: 3 and 3; the demo's Purchasing and Sales runs: 2 and 4). The 5.5 modeler cites;
the applier's links are built from the catalogue and have nothing to cite. The gate therefore fires nowhere today;
it is a guard for the next model release, for a hand-edited `dv_model.yml` and for a modeler that stops citing —
the three cases a traceability warning exists for. Built small and measured honestly as zero.

## 2 The rules

1. **The gate.** For every hub, link and satellite of this run (not in `existing_model`) whose `requirement_ids` is
   empty: `W_UNTRACED_CONSTRUCT`, a warning naming the construct and the count of parsed requirements it could have
   cited. A warning: it is a disclosure in the review (WP43 roles — validation warnings answer nothing), it never fails
   the run, and the eval's `validation_gate` counts it only where a case sets `max_validation_warnings`.
2. **Typed exemptions, by rule not by text.** A link the ratified-proposal applier built — recognised by the same
   naming the applier uses (`link_proposal.ratified_link_names`: the near hub by `hub_binds_to_source_table`, the name
   by `_link_name`, and `_relationship_link_name` for ratified relationship tables), never by its description. Key
   licenses (WP40/41) repair modeler-built constructs that carry their citations, so nothing to exempt; a satellite
   the payload gate (`E_HUB_PAYLOAD_UNREAD`) made the modeler add has no typed marker and is warned when uncited —
   the modeler cites the hub's requirement in every kept chain, and if it stops, the warning is right.
3. **Nothing to trace to, nothing to warn.** With no parsed requirements (`state.requirements` empty — a keyless
   fixture, a model built by a script) the gate is silent: a citation needs something to cite. Said here so nobody
   reads vacuity into it.

## 3 Not this WP

A gate that the cited ids *exist* among the parsed requirements (a wrong id is a different class, unseen so far). A
`requirement_ids` field on the proposals' links. Traceability the other way (a requirement no construct covers).

## 4 Acceptance (keyless)

`tests/test_wp109_untraced_construct.py`, committed red (two of five; three pins green): uncited hub, link and
satellite each warned by name, severity warning, the report passing; a cited model silent; no requirements → silent;
an existing vault's constructs silent; a link `apply_ratified_link_proposals` built exempt, the same link by hand
warned. The console catalogue's guard (WP68) pins the code's one-line meaning and chapter 8's row.

## 5 Pre-registration (keyless)

- **P1** The demo's five recorded runs (`state.json`: requirements, proposals, existing vault) replayed through the
  validator: `W_UNTRACED_CONSTRUCT` **0** on each (the 2 and 4 applier links exempt); every other issue code's count
  equal to the recorded `validation_report`.
- **P2** The twenty-third chain's five steps replayed with the gate armed by a placeholder requirement (the step
  results persist neither requirements nor proposals, so the exemption cannot be exercised there): exactly the
  applier's links named — 0, 0, 0, 3, 0 — and no other construct.
- **P3** Suite green with the WP68 catalogue guard; ruff; bare mypy; README's „36 `E_` gates" untouched (a `W_`).

## 6 Measured

Appended after the run.
