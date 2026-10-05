---
type: spec
status: not-measured
updated: 2026-10-05
---

# WP47 — A typed reason on every inferred binding, and a chain variant that sees the whole catalogue

Status: **Approved and in progress** (2026-10-05, user: „alright, so machen wir es: typisierte
Begründung gefolgt von Option 2 als Eval-Variante und Vergleich") · Owner: Mischa Eismann ·
Author: Claude. Touches `bind_sources` (WP7), `link_source_overrides` (WP34 §3.5, WP42), the WP43
role table, the eval's chain runner (WP30 §2.7) and its metrics. No prompt change; no model
call; the existing chain case is untouched.

## 1 Problem, measured

The October chains carry 154–191 `source_binding` disclosures of 218–230; arm A carries 7 of 21
(`docs/log.md` 2026-10-05, „Arm A run"). The difference is the chain design: each step receives
only its own domain's schema, so the stages of earlier domains are rebuilt without a declared
relation, inferred as `raw_<base>`, and flagged again — 1, 17, 25, 50, 94 across the five steps
of 2026-09-17 (WP43 §5). That is a cost of the increment's *presentation*, not of the increment.
And the flag says nothing about *why*: a relation nobody declared, several relations that
offer the link's participations, or a stage the link shares with a hub are three different
findings, the middle one a decision, and the queue cannot tell them apart.

## 2 The rule

### 2.1 Every inferred binding carries a typed reason

`PipelineFlag.reason: str | None` (a code, part of the flag's identity). For
`FlagKind.SOURCE_BINDING` the vocabulary is `SourceBindingReason`:

| reason | meaning | role (WP43) |
|---|---|---|
| `none` | no declared relation is named like the construct, and no offer binds it | disclosure |
| `ambiguous` | two or more declared relations offer the link's participations (WP42: binds nothing) | **decision** |
| `shared` | the link's stage base is a hub's; the stage is not the link's to repoint (WP42) | disclosure |

The reasons come from the same resolution the overrides come from: `link_binding_reasons(state)`
beside `link_source_overrides(state)` in `link_proposal.py`, keyed like the overrides (the
normalised construct base), returning `shared` for a base a hub owns and otherwise the
resolution's `grund` where it is not `offer` or `name`. `build_staging` takes
`binding_reasons` and `bind_sources` stamps the reason on the flag; a spec with no entry is
`none`. The role table gains one typed override, `(SOURCE_BINDING, "ambiguous") → decision`;
every other reason keeps the kind's role. `eval/run.py` adds `flag_reasons` (`{kind: {reason:
n}}`) to the per-run and per-step metrics.

### 2.2 A chain variant with the cumulative catalogue

`ChainSpec.cumulative_schema: bool = False`. When true, step N receives the declared schemas of
steps 1 … N−1 beside its own (`EvalCase.extra_source_schemas`, merged by `run_case_once`, first
declaration of a table wins). A new case, `adventureworks_incremental_cumulative`, is the
existing chain with the flag set — same steps, same gates. The existing case stays as it is:
WP30 §2.7's measurement is not changed, it gets a sibling, and the comparison is the point.

What the variant simulates: a customer's brownfield run, where the catalogue of the vault
already built is available to every increment — the earlier domains' tables and foreign keys.
What it changes in the measurement: the proposer sees the earlier domains' keys into the
current domain's tables too, so more licences and translations are possible; the stages of
earlier constructs bind to declared relations instead of `raw_<base>`.

## 3 Guards before the change

1. `bind_sources` stamps `reason` on every `source_binding` flag: `none` by default, the
   given reason for a base in `binding_reasons`; a bound spec raises none.
2. `link_binding_reasons`: `shared` for a link whose base a hub owns, `ambiguous` when two
   declared relations offer its participations, `none` when none does, and nothing for a link
   bound by name or by one offer.
3. `flag_role`: a `source_binding` flag with reason `ambiguous` is a decision; with `none` or
   `shared` a disclosure; the role table's existing guard still covers every kind.
4. `run_metrics` carries `flag_reasons`; the additivity key set grows by exactly that key;
   `PipelineFlag.identity()` distinguishes reasons (no dedup across reasons).
5. `ChainSpec.cumulative_schema` loads; `run_chain_once` hands step N the schemas of steps
   1 … N−1 as `extra_source_schemas` when set and nothing when not; `run_case_once` merges them,
   first declaration winning; the new dataset loads with its gates.

## 4 Pre-registration

**The comparison.** One repeat of `adventureworks_incremental_cumulative` against the chain of
2026-10-05 (`20261004T140130528908Z`, 353 items / 135 decisions / 218 disclosures,
`source_binding` 154, 22 cross-domain links, all gates green). Expected ≈ 6.5–7 USD, ≈ 45 min
(more declared tables per step: more proposer work, same number of model calls).

- **P1 — bindings.** `source_binding` over the chain falls from 154 to **under 40**; what remains
  is reason `none` on relations the catalogue really does not declare, `shared`, and
  `ambiguous`. `review_disclosures` falls from 218 to **under 110**.
- **P2 — decisions.** `review_decisions` within **110–175**: owners 68 unchanged; translations
  may rise (the proposer sees the earlier domains' keys: more licences), and the `ambiguous`
  bindings now count as decisions (predicted ≤ 15).
- **P3 — the model.** `validation_gate` 1.0 in every step unless a class not seen appears; WP34
  §6's link, invention and join clauses hold; cross-domain links ≥ 22 (more keys visible, not
  fewer). `existing_construct_preservation` 1.0 — additivity does not depend on the catalogue.
- **P4 — the reason split on the *existing* chain's shape**: of the 154 of 2026-10-05, replayed
  through the new resolution on the persisted step models, `ambiguous` is a minority (≤ 20),
  `shared` small (≤ 10), `none` the rest — the part the cumulative catalogue removes.
- **P5 — unchanged elsewhere.** The existing chain case and arm A produce byte-identical
  staging and flags except for the new `reason` field (the keyless suites and the greenfield
  manifest hold).

## 5 Not in this WP

- The acknowledgement ledger (WP43 §5 route a): still the WP29 persistence decision.
- Making the cumulative variant the default chain: a WP30 §2.7 decision for the owner, after
  the comparison.

## 6 Results

*(appended after the change and after the comparison run)*
