# ADR-0016: Business Vault PIT and bridge generation — on AutomateDV's deprecated macros, in our own SQL, or later

**Status:** Proposed (draft by Claude, 2026-10-23 — the decision is the owner's)
**Date:** 2026-10-23
**Decision makers:** Mischa Eismann

## Context

ADR-0007's layer table puts „Business Vault — PIT / Bridge" on the **Generate** side and names PIT/Bridge generation
as the next step of its roadmap gradient; backlog C22 (`backlog-2026-10-candidates-3.md`) shapes the work package:
an as-of-dates model, a PIT per hub with two or more satellites — deterministic from the model — and bridges along
link paths, which need a path choice from the requirements, ratified by a human. The owner said „go" on 2026-10-23.

Two facts stand in the way, both read in the installed AutomateDV 0.11.4 the same day (`docs/log.md`, 2026-10-23,
the correction entry) and measured in `backlog-2026-07/spike-pit-trial-results.md`:

1. **AutomateDV deprecates `pit()` and `bridge()`** since 0.11.0: „not currently fit-for-purpose and need significant
   usability and performance improvements, as well as a design overhaul. Improved implementations will be released
   in a future version." No date. The macros still run and warn on every build.
2. **The project's stack rule** (CLAUDE.md, „Don't bypass AutomateDV by writing dbt models from scratch") exists so
   that the generated vault stays AutomateDV's — the macros carry the hashing, the incremental semantics and the
   platform dispatch the project is verified against. PIT and bridge are the first constructs where the package's
   own implementation is the thing its authors advise against.

The trial on the owner's vault (`hub_sales_order`, 4 satellites, 31 465 keys, 11 as-of dates): both the macro and a
plain-SQL PIT produce the same 346 115 rows with the same load dates; they differ only in the ghost key, where the
macro writes 32 ASCII zeros into a `bytea` column whose real values are 16-byte MD5s — a value no convention of this
vault knows. The macro's second („incremental") run recomputed the whole PIT and was slower than its first; the
plain-SQL table rebuilds whole by construction. Multi-active satellites, several load dates, Databricks and bridges
were not measured.

## Options

**A — Generate on the deprecated macros.** The generator emits `automate_dv.pit(...)` / `bridge(...)` models with
the `pit_incremental` / `bridge_incremental` materialisations, exactly as the trial's variant A.
*For:* smallest change; stays inside the stack rule to the letter; AutomateDV's own platform dispatch.
*Against:* every build warns; the ghost key is wrong for this vault; the authors name performance as a known
problem; the next AutomateDV release may change or remove the macros, and the generated projects of every customer
would carry that risk; `src_extra_columns` is ignored, so a PIT cannot carry a business key column without a join.

**B — Generate PIT and bridge SQL ourselves, as a scoped exception to the stack rule.** The generator renders the
PIT (and later the bridge) as plain dbt models — the trial's variant B — with the vault's own conventions: the ghost
entry points at WP86's zero-key hub row and, when AutomateDV ghost records are enabled in the satellites, at that
record; the as-of spine is a generated model over `dbt_utils.date_spine`; the materialisation is the project's
(`table`, or an incremental by as-of window written and tested by us). The exception is recorded here, limited to
the Business Vault constructs AutomateDV has deprecated, and revisited when AutomateDV ships its redesign.
*For:* no deprecation warning; a ghost key that means something in this vault; SQL the owner can read and defend;
the generator already owns every input (hub, satellites, their load-date columns, the stages).
*Against:* maintenance and platform dispatch are ours (PostgreSQL first, Databricks to be verified as WP72 did);
one more place where the output is not AutomateDV's; an incremental PIT is real work, not a flag.

**C — Wait for AutomateDV's redesign.** Generate nothing; C22 stays open.
*For:* no work on a moving target. *Against:* no date exists; the roadmap's next step stays blocked; the owner's
positioning (ADR-0015) names PIT/Bridge among the honest limits today.

## Decision (proposed)

**Option B**, with these bounds:

- PIT first, bridge second. A PIT is proposed for every hub with two or more satellites, deterministic from the
  model, and listed at sign-off as a disclosure; a bridge needs a path, proposed from the requirements and ratified
  as a decision (ADR-0007's human ratification of Business Vault logic is kept — the agent assists, it does not
  decide the paths).
- The first increment is a `table` PIT with an as-of spine the operator bounds (`start`, `end`, grain) in the
  project settings; an incremental PIT is a later work package with its own pre-registration, because the trial
  showed no measured incremental benefit to copy.
- Ghost handling is decided before the spec: either the PIT's ghost key is WP86's `-2` hub key (consistent with the
  links), or satellites get AutomateDV ghost records (`enable_ghost_records`) and the PIT points at them — read
  `binary_ghost` for PostgreSQL and Databricks first; the trial found the macro's own value unusable.
- The exception to the stack rule is this ADR and nothing wider: hubs, links, satellites and stages stay AutomateDV's.
- Re-evaluate when AutomateDV publishes the redesigned macros: if they are fit, a later ADR may retire ours.

## Consequences

- A new generator module for Business Vault output, with byte-identity fixtures and a keyless `dbt build` on
  PostgreSQL before any live run; Databricks verified separately, as WP72 did for the raw vault.
- `docs/operations/09-warehouse.md` gains a Business Vault section; ADR-0007's layer table is not edited (records are
  append-only) — this ADR is the dated record that PIT/Bridge generation starts.
- The honest limit in the README and the wiki page („Business Vault (PIT/Bridge) … noch nicht generiert") changes only
  when the first PIT has built on the owner's vault, not when this ADR is accepted.

## What this ADR does not decide

Which hubs get a PIT in a given project (every eligible hub by default, the operator deselects); the bridge path
language; whether marts follow (ADR-0007 keeps them human-ratified).
