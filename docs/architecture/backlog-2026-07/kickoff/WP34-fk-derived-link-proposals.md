# Kick-off WP34 — Links proposed from the source's own foreign keys

You are a senior engineer closing the question three prompt interventions failed to close: arm B
builds 2 cross-domain links where arm A builds 16. Keyless work except the single acceptance run
at the end.

**Read the four measurements before the spec.** The design is not a free choice — the prompt
lever was tried three times, measured each time, and stopped. What makes this WP different is not
a better instruction; it is that the evidence the modeler needed was never in its input.

## Read first
1. `CLAUDE.md` (canon — the invariants on `rules/` helpers, gates vs backstops, and graph order
   all bind here).
2. `docs/log.md`, entries 2026-08-09 (three of them) and 2026-08-10 — the four-run table, the
   WP30.3 post-mortem on why a narrow bar is a bad bar, and the revert.
3. `docs/architecture/steering-ledger.md` — the `preserved_reference_is_a_link` row now reads
   `keep — UNEVIDENCED`. Read *why* it is not `candidate-delete`.
4. `wp34-fk-derived-link-proposals-spec.md` — binding. §2 and §3.4 are the two that matter.
5. `wp29-entity-resolution-spec.md` §2.5 + `agents/entity_resolver.py:487-538` — the
   propose/pause/ratify machinery you extend rather than rebuild.
6. Code: `state.py` (`SourceTable`, `LinkHubRef`, `Hub.sources`), `agents/staging_generator.py`
   (lines 220-247 and 342-384 — the alias problem and the binding fallback),
   `eval/adventureworks/derive.py:73-88` (where the foreign keys are dropped).

## What to build (spec §3 — the spec wins on conflict)
1. `SourceTable.foreign_keys`, optional and inert. **Byte-identity guard committed FIRST.**
2. `derive.py` emits them; re-derive the five AdventureWorks cases deterministically.
3. `link_proposal.py` + a `link_proposer` node: deterministic, keyless, no prompt, no
   `ForcedToolCaller`. Category DERIVED in `rules/`, never claimed.
4. Ratification in the EXISTING `resolution_checkpoint` — one pause, two sections. Preserve its
   purity contract above `interrupt()`.
5. `LinkHubRef.source_key_column` + the staging alias, mirroring `HubSource.business_key_column`.
6. `E_LINK_KEY_NOT_IN_SOURCE`, and the deterministic `source_overrides` binding from §3.5.

## Verify
- Spec §5.2 (byte-identity) and §5.3 (greenfield inertness) **written and run FIRST**, before
  any behaviour change. A guard written afterwards proves only that you wrote it afterwards.
- Never re-derive a canonical staging key at a call site — `canonical_hub_key_column`,
  `normalize_identifier`, `role_bk_column`. This is the one defect class here that produces
  wrong *data*.
- `uv run pytest`, `uv run ruff check`, bare `uv run mypy` green.
- **Do not run the live arm-B repeat until §6's four clauses are written down and agreed.** The
  bar is a conjunction; a link count alone is exactly the bad criterion WP30.3 fell for.

## Out of scope
Composite and self-referencing foreign keys (flag, never guess); links inside one increment;
Business Vault; inference from data rather than declaration; deleting the
`preserved_reference_is_a_link` steering line; **any new decision-persistence file** — that
architecture decision is WP29's and is Mischa's to make.

## Definition of Done
Spec §5 met with evidence, saying plainly which claims are live-verified and which are
keyless-only; a dated `docs/log.md` entry; conventional commits referencing this kick-off and the
spec. If the live run's §6 conjunction fails, **record it as a failure and stop** — do not reach
for a sixth intervention.
