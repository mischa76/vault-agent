# Kick-off WP29 — Entity resolution against an existing vault (brownfield Phase 2)

You are a senior engineer building the assist the entity-resolution spike measured and
recommended: proposing, for each concept a new source introduces, whether it IS a construct
the vault already has. Keyless work except the acceptance runs at the end.

**Read the spike memo before the spec.** The design is not a free choice — it is what the
measurement supports, and two of its conditions exist because a plausible alternative was
measured and failed.

## Read first
1. `CLAUDE.md` (canon; the WP23/WP28 paragraphs describe the machinery this feeds).
2. `docs/architecture/backlog-2026-07/spike-entity-resolution-results.md` — especially §2
   (honest degradation, the property that made this buildable), §3 (the six answers) and
   §4 (what the spike does NOT establish).
3. `spike-entity-resolution-charter.md` §2 — the asymmetry. A false merge is not a bad
   suggestion; it is foreign keys in a table holding history.
4. `wp29-entity-resolution-spec.md` — binding.
5. Code: `agents/source_mapper.py` (the closest sibling — WP9's assist, ratification file,
   post-validation), `existing_model.py` (`render_extension_prompt_section`),
   `agents/orchestrator.py` (review queue), `graph.py`.
6. `eval/resolution.py` + the four scorers + `eval/datasets/brownfield_resolution/`.

## What to build (spec §2 — the spec wins on conflict)
1. `agents/entity_resolver.py`: one forced-tool pass, Sonnet-tier, pre-modeling, inert
   without BOTH an existing model and a declared schema.
2. Promote the resolution types into `state.py`; same-as becomes a first-class output.
3. Derive the confidence category in `rules/` — never trust the model's own.
4. Keep the post-validation safety property (never invent a construct).
5. `resolutions.review.yml` + `resume --resolve`; two new flag kinds in the review queue.

## Verify
- Spec §3 green; inertness guard written and run FIRST.
- **Acceptance #2 first, before building the rest**: run trap 5 (`undecidable`) against the
  prototype design. It is UNMEASURED — added after the spike's prototype was deleted. If the
  mechanism merges or guesses instead of declining, STOP and report; the recommendation
  itself is then in question.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.

## Out of scope
Phase 3 introspection, same-as link generation, any change to WP23's merge/gate machinery.

## Definition of Done
Spec §4 met with evidence (paste the live scores); CLAUDE.md milestone paragraph, honest
about anything unmeasured; conventional commits referencing this kick-off, the spec and the
spike memo.
