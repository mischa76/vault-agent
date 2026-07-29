# Kick-off WP28 — Satellite feed binding on multi-source hubs (ADR-0011, Accepted 2026-07-29)

You are a senior data engineer implementing ADR-0011: a satellite whose `source_table`
names one of its multi-source hub's feeds is generated once and bound to that feed —
the DV2.0-canonical one-satellite-per-source shape the pipeline currently rejects.
Keyless work except the live acceptance run at the end (needs an API key; report it
separately if you cannot run it).

## Read first
1. `CLAUDE.md` (canon; the WP23/WP24 milestone paragraphs describe the two systems you
   are changing and the live findings that motivated the ADR).
2. `docs/architecture/adrs/ADR-0011-satellite-source-binding-on-multi-source-hubs.md` —
   the decision, incl. the SHARPENED acceptance signal (step 5): the primary signal is
   the gate no longer firing on the REQ-107 shape; `validation_gate` is confounded by
   `E_HUB_HK_COLLISION` and does not decide.
3. `docs/architecture/backlog-2026-07/wp28-satellite-feed-binding-spec.md` — the binding
   spec.
4. Code: `rules/dv2_rules.py` (`source_table_on_multi_source_hub`, the WP16 registry),
   `agents/code_generator.py` (multi-source satellite path), `agents/staging_generator.py`
   (`collect_staging_specs` — the `source_table` branch vs. the per-source fan-out),
   `agents/validator.py` (the gate), WP23's grandfathering/`legacy_feeds` helpers.
5. Tests: `test_feature_composition.py` (the matrix you move), `test_steering.py` +
   `tests/fixtures/steering/modeler_rules_pre_wp16.txt` (deliberate fixture change, WP20
   precedent), the WP10/staging/demo byte-identity guards.

## What to build (spec §2, summarised — the spec wins on conflict)
1. Narrow the shared predicate: error only when `source_table` names NO feed of the
   parent (normalised match; the grandfathered legacy feed matches — pin it, don't
   assume it).
2. Code generator: feed-bound sat rendered once, bound via the same staging naming the
   hub uses for that feed (incl. legacy name); no per-source suffix, no flag.
3. Staging generator: the sat's columns/hashdiff go to the named feed's spec ONLY; no
   orphan `stg_<sat base>`; other feeds untouched.
4. Narrowed gate message lists the available feeds; update gate catalogue, WP24 spec
   (dated note), operations §6.7, and the `bank_extension` limitation note in the same
   commit.
5. Delete the `no_source_table_on_multi_source_hub` steering rule; fixture regenerated
   (pre-WP16 prefix asserted), ledger row moved to deleted-with-evidence.
6. Move the composition-matrix cells; the one-hash-input-set-per-target-column invariant
   must hold over the new cells.

## Verify
- Spec §3 list green; all byte-identity guards untouched (single-source, WP10 greenfield
  split, both demos).
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.
- Live (if key available): `bank_extension` ≥ 3 repeats — primary signal per ADR step 5;
  report `validation_gate` and `existing_construct_preservation` alongside. State
  plainly in the final report if this step is still open.

## Out of scope
ADR-0011 row 3 semantics (finer-grain relation under one feed), hub-key canonicalisation
policy, mapper changes, `E_HUB_HK_COLLISION` on hub_campaign/hub_employee (independent
modelling smell — do not chase it here).

## Definition of Done
Spec §4 met with evidence; CLAUDE.md milestone paragraph appended (honest about the live
step); conventional commits referencing this kick-off, the spec, and ADR-0011.
