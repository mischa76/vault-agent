# Kick-off WP30 — An independent semantic axis, and the domain-partitioning experiment

You are building the first eval instrument in this project that somebody else designed, and
then using it to test a claim the architecture currently asserts without evidence: that
modelling domain by domain into a growing vault beats one big pass. Eval-only — **no
`src/vault_agent/` change is in scope.**

**Read the finding before the spec.** This WP exists because the measuring instrument was
caught being wrong, twice in one day, and the second time by the project owner asking the
obvious question I had not asked.

## Read first
1. `CLAUDE.md` (canon).
2. `docs/architecture/scale-test-findings.md` — **Candidate #5 first**. It is a *withdrawn*
   product finding, replaced by a finding about the generator. Read how it was withdrawn, not
   just what it concluded: the standing rule at the end of that entry is the reason this WP
   exists.
3. `docs/architecture/backlog-2026-07/incremental-extension-charter.md` §1 and ADR-0010
   Option C — the claim under test. Note that ADR-0010 explicitly recorded Option C so the
   staged-modelling discussion "does not resurface as its accidental substitute". That is a
   warning this WP must respect: do not let it drift into making one big pass work.
4. `wp30-adventureworks-semantic-axis-spec.md` — binding, **including the two acceptance
   amendments (2026-07-29)**: §2.4a blinded requirements authoring (author them in a separate
   session that sees only the one subject area's schema; record how in the case file) and
   §2.7 the arm-B chaining machinery (chained case in the runner, output→input threading,
   mid-chain auto-accept semantics stated in the writeup, per-step preservation scoring) —
   §2.7 is the real implementation effort of this WP, plan it first, not last.
5. `spike-entity-resolution-results.md` §4 — the author-bias confound, in the memo's own words.
6. Code: `eval/datasets.py` (`EvalCase`, `materialize_case`, the loader's refusals),
   `eval/run.py`, `eval/scorers.py` (WP14 column mode, WP18 vacuity), `existing_model.py`.

## What to build (spec §2 — the spec wins on conflict)
1. Derive `source_schema.yml` per subject area from the AdventureWorks OLTP DDL —
   deterministically, from a checked-in extract, types included. **No comments** (§2.3).
2. One requirements document per subject area, written *from the schema*. Never the other way
   round.
3. Five greenfield cases, plus arm A (`adventureworks_full`) and arm B
   (`adventureworks_incremental`, chained through `existing:`).
4. Golden *mappings* only — business key → real `TABLE.COLUMN`, read out of the DDL. No golden
   DV model (§2.5).
5. `NOTICE` with the Microsoft copyright and MIT text beside the derived assets.

## Three things that are easy to get wrong here
- **Do not redraw the schema boundaries.** They are the instrument. An awkward boundary is a
  finding, not a defect to tidy away. The moment you adjust them, this WP measures our opinion
  again and its whole point is gone.
- **Do not author column comments** to make the mapper look better, and do not write
  requirements that quietly encode the DV model you expect. Both re-import the confound.
- **Write arm B's order down before running it**, derived from the FK graph. An order chosen
  after seeing a result is not evidence.

## Verify
- Spec §3 green; `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.
- Run the five per-case runs FIRST — cheap and informative — before the two arms.
- Set the §6 cost ceiling before the first live run and stop at it.
- Findings quote the trace (`tool_name`, `attempt`), per the WP15 §2.4 protocol.

## The outcome you must be willing to report
The hypothesis is that arm B wins. **If it does not** — if one pass gives comparable review load
and validation at lower cost — that is the result, and it goes in the spec's §7 as it came out.
Do not re-run until it comes out the preferred way; do not bury the losing arm. The charter's
claim is load-bearing for the whole brownfield track, which is exactly why it deserves a real
test rather than a supportive one.

## Out of scope
Any `src/` change; authoring comments; a hand-authored golden model; loading AdventureWorks
data or building it on PostgreSQL; WP29 entity resolution (identify the `Person` overlap,
measure it later); retiring or relabelling `scale_100`/`scale_300`.
