# ADR-0018: Keys inferred from data — their own class in the house format, and how far an inference may act

**Status:** Accepted (2026-10-30 — the owner accepted Option B; draft by Claude the same day, on the owner's go
for C27 stage 3; built as WP99 on the recommendation)
**Date:** 2026-10-30
**Decision makers:** Mischa Eismann

## Context

The deterministic link proposer (WP34, WP36–WP40, WP46) reads **declared** foreign keys only, and says so in
its own words: *„it proposes only from a DECLARATION"*; `ForeignKeyRef` is *„transcribed from the source
catalogue, never inferred by this pipeline and never derived from data"*. The spec's third tier,
`key_name_only` — a column that merely shares a hub key's name — was rejected with numbers: against step 4's
30-hub vault, AdventureWorks Sales matched 13 hubs by key name and 7 of those only because they were keyed
`Name` (WP34 §3.2). That rejection stands.

What the field brings is catalogues without declarations: a `pg_dump` of data without its DDL (the house's own
AdventureWorks copy: 68 tables, 0 keys, WP96 P5), SAP's dictionary where the foreign keys are relationships
and not constraints (C27 tier C), staging areas and lakes where nothing was ever declared. For such a source the
proposer is blind, and the owner's build needed hand-made views for the link stages no rule could bind
(C18, reason `none`). The stage 2 profiler (WP98) now reads rows; the statistics that make a key visible —
uniqueness, and inclusion (*every value of A occurs in B*) — are one anti-join away.

Backlog C27 stage 3 asks for exactly that, with three conditions: *an inference, not a declaration; its own
class („inferred key"); ratified at the checkpoint, never binding on its own (WP34's inertness stays)*. It also
notes that stages 3 and 4 *„need the ADR together with C1"*. This ADR takes the part that does not depend on
C1: C1 asks whether a vault may take the source's shape without a requirements document; this ADR asks what an
inferred key *is* and what it may *do*. Both answers below hold under either outcome of C1 — a source-driven
mode would read the same class, and a requirements-driven run uses it exactly as decided here.

## Decision (proposed)

**Option B — an inferred key is its own class in the house format, produced by a command, consumed by the
proposer as a proposal nobody accepts by default.**

1. **Its own class, beside the declaration, never inside it.** `SourceTable.inferred_keys` (`InferredKeys`:
   `unique: [InferredUniqueKey]`, `foreign: [InferredForeignKey]`), absent by default. An `InferredForeignKey`
   has the shape of a `ForeignKeyRef` **plus its evidence** — the non-null referencing rows (every one found),
   the distinct referencing values, the referenced column's distinct values, the candidate tier that paired
   them, and the wider domains that also contain every value. `foreign_keys`, `primary_key` and `unique_keys`
   stay what they are: the catalogue's words. A reader of the file can always tell the two apart.
2. **Produced by an explicit command, from data, deterministically.** `vault-agent infer-keys --source-schema
   FILE --out FILE` reads the declared schema file, connects as `profile` does (ADR-0008 #4's explicitly
   invoked, read-only, scoped step; the row boundary of `deployment-residency.md`, addendum 2026-10-30), and
   writes the file back with inferences attached. A column is an inferred unique key when over more than one
   row `count(distinct c) = count(c) = count(*)`. A pair (R.c → T.k) is an inferred foreign key when T.k is a
   declared or inferred single-column unique key, the two columns share a type family, the pair is a
   *candidate*, and the anti-join finds no non-null value of R.c absent from T.k. Candidates come in two tiers
   the operator chooses: **`name`** (default) — R.c and T.k spell the same compact name, R.c ends in T.k's
   name (`ShipToAddressID` → `AddressID`), or R.c is T's name plus `ID` (`SalesPersonID` → `SalesPerson`'s key);
   **`type`** — every type-compatible pair, which is complete and noisy (a two-valued status column is
   included in every integer key) and is therefore never the default. Where several unique columns contain
   every value of R.c, the one with the fewest distinct values is the inference and the others are recorded
   as `wider` — `Employee.BusinessEntityID` is a `Person` before it is a `BusinessEntity`. A pair the catalogue
   already declares is never inferred. Nothing here reads WP34's rejected tier back in: a name coincidence
   is a *candidate*, and only the data makes it an inference.
3. **Consumed by the proposer as a proposal with `provenance: inferred`.** The per-key path (target hub, else
   translation, else licence, else a typed skip) runs on inferred keys exactly as on declared ones, after
   them, and every proposal or licence it yields carries `provenance` and evidence lines that state the
   numbers and the absence of a declaration. Nothing else reads the class: not the modeler's prompt, not the
   travelling catalogue, not the satellite-grain gate (`E_SAT_GRAIN_NOT_UNIQUE` reads declarations; an inferred
   unique key lifting a refusal would be an inference acting on its own).
4. **Never binding on its own.** `--accept` — the bulk key the CLI, the workbench and the eval harness's
   unattended resume use — ratifies every *declared* proposal still pending and **declines** every inferred
   one (`overridden`, on the record as offered and not built). An inferred proposal is built only when a human
   names it: `resume --link Table.Column`, or the interactive prompt, whose default for an inferred proposal
   is *no*. The same holds for an inferred licence. A chain measured unattended therefore builds nothing from
   an inference, and says so in its `link_proposals` metrics by provenance.

## Alternatives considered

- **Option A — write inferred keys into `foreign_keys` and `unique_keys`.** One class, no new types, the
  proposer unchanged. Rejected: it makes the catalogue lie (`ForeignKeyRef`'s own contract says „never
  inferred"), the reviewer cannot tell a declaration from a guess, and `--accept` would build inferred links
  unattended — the WP30.3 noise with a data-shaped excuse.
- **Option C — a separate inference file (`--inferred-keys FILE`).** The declared schema stays pure. Rejected
  for plumbing, not principle: a third input must travel with the catalogue, be carried between increments,
  reach the workbench's request models and the eval's dataset format; the class separation Option B keeps
  inside one file buys the same legibility for none of that.
- **Option D — infer at run time inside the pipeline.** Rejected by ADR-0008 #4 and by WP96's invariant that
  no agent holds a database connection; the inference is a command, like the profile.
- **Composite keys and inclusion over column sets.** Deferred: pairs only. A composite inclusion projects onto
  its components (the WP46 reading), so single-column inferences already serve the composite case partly;
  inferring the composite itself is combinatorial and waits for a case that needs it.

## Decision (2026-10-30)

The owner accepted **Option B** on 2026-10-30, after WP99 was built and measured on it (`docs/log.md`, 2026-10-30:
on the key-less AdventureWorks data copy 79 of 89 declared single-column keys hit exactly, 5 more with the true
target in the recorded wider list, 0 wrong targets). An inferred key is its own class beside the declarations
(`SourceTable.inferred_keys`), produced by `vault-agent infer-keys`, proposed by the proposer with
`provenance: inferred` and resolved through a tied or wider key column an existing hub binds, declined by
`--accept` and built only by an explicit `--link` or a *yes* at the prompt. One refinement from the measurement
is part of what was accepted: one inference per referencing column, equal domains recorded as `tied` and broken
by a stated preference, the strictly larger ones as `wider` — the first run's „ties: all of them" produced 39
false positives, 30 of them one 1:1 group emitted per member. C1 stays its own ADR; the type tier and the
gates' reading of inferred unique keys stay later, measured increments.

## Consequences

- **Positive.** A key-less source (the data copy, a dump, a lake) gets the proposer back, with the human in
  the same seat as for declared keys and a stricter default. The AdventureWorks data copy is a measurement
  instrument with ground truth: its catalogue declares nothing, the extract declares 89 single-column keys,
  so recall and precision of each tier are numbers, not claims (WP99 P5).
- **Negative.** Two more commands read rows (`profile`, `infer-keys`); the residency note already carries the
  boundary. The `type` tier is expensive (every type-compatible pair is an anti-join) and noisy by design; the
  manual must say when to use it. An inferred key that is wrong and *accepted* by a human is wrong data — the
  evidence lines and the `wider` list are what the human decides on, and they must stay in front of the
  decision in every surface (CLI prompt, workbench, review queue).
- **Neutral.** C1 is untouched and keeps its own ADR; a source-driven mode would consume this class. The
  satellite-grain gate and the binder's offer tier (C18's second half) could read inferred unique keys later
  — each would be an inference acting on its own and needs its own measured WP. `candidate: type` and the
  `wider` list exist so that a later ranking or pruning rule has the numbers it needs without re-reading data.

## References

- Backlog C27 (`docs/architecture/backlog-2026-10-candidates-3.md`), C18 (`…-candidates-2.md`), C1
  (`…-candidates.md`).
- WP34 §3.2 (the rejected `key_name_only` tier), WP36–WP40, WP46 — `docs/architecture/backlog-2026-07/`.
- ADR-0008 #4 and its note of 2026-10-30; ADR-0017; `deployment-residency.md` addendum 2026-10-30; WP98.
- The proposer: `src/vault_agent/link_proposal.py`; the applier of decisions:
  `src/vault_agent/agents/orchestrator.py` (`apply_link_decision`); the eval's unattended resume:
  `eval/run.py` (`AUTO_RESUME_DECISION`).
