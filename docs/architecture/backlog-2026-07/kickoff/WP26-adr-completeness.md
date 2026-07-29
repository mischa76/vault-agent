# Kick-off WP26 — ADR completeness and determinism (review finding 2026-07-29 #4)

You are a senior engineer making the pipeline's human-facing architecture record actually
record the architecture. The ADR currently omits driving keys, multi-source hub feeds,
satellite types, and the ratified source mappings — and CLAUDE.md claims the driving key is
rendered when it is not. Deterministic work: the ADR author is and stays LLM-free.

**Ordering note: land this BEFORE WP23's delta-ADR** — both edit `adr_author._render`, and
the "Extends" framing is far easier to write on a complete renderer.

## Read first
1. `CLAUDE.md` (canon — including the WP2 ADR paragraph and the driving-key claim you are
   making true or correcting).
2. `docs/architecture/reviews/project-review-2026-07-29.md` finding 4.
3. `docs/architecture/backlog-2026-07/wp26-adr-completeness-spec.md` — binding spec.
4. `agents/adr_author.py` in full; `state.py` (`Hub.sources`, `Link.driving_key` +
   `resolve_driving_refs`, `Satellite.sat_type`/`child_dependent_key`/`source_table`,
   `ProposedMapping`); `rules/dv2_rules.py` (`canonical_hub_key_column` — use it, never
   re-derive the canonical name).
5. `tests/test_agents/test_adr_author.py` — the byte-identity pins you extend.
6. `docs/architecture/backlog-2026-07/wp23-incremental-extension-spec.md` §2.8, so your
   structure does not fight the delta-ADR that follows.

## What to build (spec §2, summarised — the spec wins on conflict)
1. Hub lines carry `sources` (feeds + canonical staging key column); link lines carry the
   driving key rendered through `resolve_driving_refs()` (role-qualified like the
   participation list); satellite lines carry non-standard `sat_type`, the CDK, and
   `source_table`.
2. A conditional **Source mappings** section from `state.mappings` (proposals with category
   + ratification status, gaps, unresolved) — absent entirely when the mapper was inert, so
   an ungrounded ADR stays byte-identical.
3. Determinism: decide whether the claim gets precise ("for a given state and date") or the
   date stops coming from the clock, then make docstring, CLAUDE.md and the tests agree.

## Verify
- Spec §3 tests: each new field renders; a model without them is byte-identical to today
  (fixture); ungrounded run has no mappings section; role-qualified driving key matches the
  participation rendering; determinism test extended.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.

## Out of scope
Any LLM involvement, repo-level ADR numbering, the brownfield "Extends" section (WP23), and
rendering the data contracts.

## Definition of Done
Spec §4 met; the CLAUDE.md driving-key claim is true (or corrected) in the same commit;
CLAUDE.md milestone paragraph appended; conventional commit(s) referencing this kick-off and
the spec.
