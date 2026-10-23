---
type: record
status: agreed
updated: 2026-10-23
---

# What 1.0 waits for — the criteria, replacing „the first live Databricks build"

Status: **Agreed** (2026-10-23, the owner's go to record the criteria and cut 0.11.0) · Owner: Mischa Eismann ·
Author: Claude. Supersedes the rule in the CHANGELOG header since 0.9.0 (2026-09-12): „versions stay below 1.0 until
the first live Databricks build". That build happened on 2026-10-16/17 (WP72), and the week after it the owner's own
hands-on build found three classes of wrong data in the generated vault (C11–C13) and this week's corrections (WP86,
WP89, WP90) changed the generated output for unchanged inputs three times — exactly what SemVer's 0.x permits and 1.x
does not. A platform build measured breadth; the maturity review of 2026-10-22 (`reviews/maturity-review-2026-10-22.md`,
TRL 6) measures depth. 1.0 is the second.

## The criteria (all of them; each one is checked by a recorded measurement, not a judgement)

1. **A second real domain**, not AdventureWorks and from the target market (bank or insurance), modelled from
   requirements written independently of the schema, built and idempotent on PostgreSQL (backlog C17).
2. **Two consecutive minor releases without a „Fixed: wrong data" entry** — no correction that changes the rows of a
   generated vault for unchanged inputs. A gate that refuses more is not such a correction; a generator that hashes
   another column is.
3. **AdventureWorks builds without a hand-made view**: every link stage bound by rule or at sign-off (C18's second
   half, C4/WP82), measured on the five-domain chain and on the owner's build.
4. **ADR-0015 decided and its consequences done** — the single-user tool deliberately, or authentication and a shared
   checkpointer; either way recorded and built, not assumed.
5. **One evaluator walk-through by someone who is neither the owner nor the agent**, following the written guide,
   with its result in the log (the maturity review's open item).

## Not criteria

Snowflake or Fabric builds (platform breadth, 1.x), bridges and marts (ADR-0016's later increments), semantic scale
above ~30 tables (`scale-test-findings.md`; measured when the second domain gives it a real landscape), PyPI.

## How it is applied

The CHANGELOG header points here. A release note that claims a criterion met names the log entry that measured it.
Until all five are met, releases are `0.<minor>.<patch>`; an output-changing correction is a minor, never hidden in
a patch.
