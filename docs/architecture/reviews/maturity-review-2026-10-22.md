# Maturity review vault-agent — October 2026

Author: Mischa Eismann · Date: 2026-10-22 · Judged on: `main` at `d18b8d7` (2026-10-21), version 0.9.1.
English rendering of the owner's German original (`261022_vault-agent_Reifegradanalyse`, kept outside the
repository). Faithful to its findings and scores; details naming private people, local paths and the
owner's private knowledge base are left out. What happened since is appended at the end.

## Summary

vault-agent is a technically mature prototype at **TRL 6**: demonstrated in a realistic environment, but
never run in a real customer project. For the intended route — accompanied use by the owner as a
consultant — the state carries; for self-service operation at a customer, operations, multi-user
capability and a second real dataset are missing.

The three findings that matter most:

1. **Engineering quality is the strongest part.** All gates green on `main`: 1256 tests passed, 5 skipped,
   93 % line coverage, mypy strict and ruff clean, frontend 19 tests and build green.
2. **The domain evidence rests on one domain.** Nine of the last ten chain runs on AdventureWorks were green;
   the whole vault built on PostgreSQL to 322 of 340 objects. A second, independent dataset and real scaling
   beyond about 30 tables of semantic variety are missing. The owner's own run of 2026-10-22 also found a
   silent generator defect: a multi-active satellite generated as a standard satellite and not idempotent (C11).
3. **Release and repository hygiene lag behind.** 295 commits since the last release 0.9.1 (2026-09-12), the
   README status at WP10, and local workbench runs in the public repository because `workbench/` is not
   ignored.

## Basis and method

The public state of `main` at `d18b8d7`, version 0.9.1. Scale from 1 (idea) to 5 (proven in production at a
customer); the yardstick is the roadmap's goal: productive use in Class-1 projects of large enterprises.

- **Checked directly:** a fresh clone in a Linux sandbox; `ruff check .`, bare `mypy` (as in CI), `pytest` with
  coverage, frontend `tsc`, Vitest and build. Code, ADRs, `docs/log.md`, `docs/index.md`, the reference
  architecture, roadmap, scale findings and `.gitignore` read.
- **Taken from the project log, not re-run:** all live runs with an LLM (chain runs, `scale_100`) and all dbt
  builds on PostgreSQL and Databricks.
- **Checked on the owner's machine on 2026-10-22:** the local working state (one commit ahead of `main`, the log
  entry with candidates C8–C11).

## Maturity per dimension

Threshold 4 = „accompanied pilot at a customer possible". Four of eight dimensions are below it.

| Dimension | Score |
|---|---|
| Code and test quality | 4.5 |
| Functional scope | 4 |
| Architecture and governance | 4 |
| Documentation | 4 |
| Security and compliance | 3.5 |
| Result quality | 3 |
| Operations and deployment | 2.5 |
| Product and market maturity | 2 |

What lies below the threshold is mostly operations, distribution and a second domain proof; real code work is
chiefly C11, the reason result quality drops from 3.5 to 3 after looking at the local state.

## Findings in detail

| Dimension | Strengths (evidence) | Gaps |
|---|---|---|
| Functional scope | 13 graph nodes from requirement to dbt project; brownfield increments; mapping with ratification; HITL with resume; workbench (ADR-0014) with a CLI equivalent per action | Business Vault PIT/Bridge open — per the reference architecture the only gap of class „Generate"; marts deliberately last; no source-driven mode without a requirements document (candidate C1); 8 of 340 stages remain „inferred" and do not build; workbench without deleting and project settings |
| Result quality | 21 chain runs recorded, nine of the last ten green (red: the 19th); review load 83–88 decisions since the 14th run; whole vault 322/340 on PostgreSQL, hubs equal to their sources; the owner's own run of 2026-10-22 (person + HumanResources, built by hand) held every pre-registered number | One real domain (AdventureWorks); `scale_300` never run; above 30 tables the synthetic generator measures repetition, not semantics (candidate #5); C11: a feed-bound multi-active satellite silently generated as a standard satellite, no gate reports it, the re-run adds 26 rows |
| Code and test quality | 1256 tests green, 93 % coverage, mypy strict, ruff clean; tests red before the fix; pre-registered runs | `ui/console.py` 70 %, `ui/app.py` 79 %; the WP78 defect (relative path) passed because no test went through the API; `cli.py` 1858 lines |
| Architecture and governance | 14 ADRs; rules in code, not in prompts; 35 deterministic `E_` gates; CLI-first invariant kept; code generation through AutomateDV | ADR-0004, -0005 and -0007 still „Proposed" in file and index although built |
| Operations and deployment | Windows installer (WSL2); Bedrock and Vertex routes wired; release workflow with definition of done | Workbench local only (127.0.0.1), no auth, no multi-user; SQLite checkpointer; no PyPI; no on-prem LLM; no Snowflake or Fabric dialect |
| Security and compliance | Secret scanning, push protection, CodeQL, Dependabot, Actions pinned by SHA, `SECURITY.md`; traces excluded by `.gitignore` | `workbench/` not ignored: `workbench/myproject` and `workbench-demo$/…` (a typo in the folder name) are committed publicly; a run on real requirements lands in the repo with the next `git add .` |
| Documentation | Operations manual in 14 chapters; project log with 277 entries and evidence; steering ledger | README status ends at WP10 („Polish — next"), names 33 instead of 35 gates and Databricks as „keyless-only" although built there; reference architecture last derived 2026-08-14 (still says „no data profiling"); the owner's project page outdated |
| Product and market maturity | Competitive brief exists; cost per chain known (4.2–4.9 USD, 21–24 min) | One maintainer, no external user yet: a first walk-through guide and `docs/evaluator-guide.md` exist, no result recorded anywhere; no pilot; 295 commits unreleased since 0.9.1 |

## Recommendations

Hygiene first, then the second proof — features after that.

**Now (small, one commit each)**
- Take `workbench/` and `workbench-demo$/` out of the repository and into `.gitignore`; point the quick start and
  the demo guide at a root outside the repository.
- Cut release 0.10.0: 295 commits, WP11–WP80, sit under `[Unreleased]`.
- Clean up documentation drift: README status block, gate count (35), Databricks state; re-derive the reference
  architecture. ADR-0004, -0005, -0007: decide acceptance and record it by log entry plus index — the ADR files
  stay unchanged (`docs/architecture/` is append-only). Update the owner's project page.

**Next (spread the evidence)**
- Run a second real domain that is not AdventureWorks — ideally a banking- or insurance-like landscape.
- Fix C11: guard first, then dispatch on `sat_type` in the ADR-0011 branch — a silently wrong satellite weighs
  heavier for Class 1 than a missing one. Then close the eight „inferred" stages: the only generator-side reason
  the whole vault does not build.
- Workbench tests through the API (the WP78 class); raise the coverage of `ui/console.py`.

**Before a pilot at a customer**
- Decide the positioning: the consultant's local single-user tool, or a team tool with auth and a shared
  checkpointer.
- Snowflake dialect, because Snowflake is a strategic target and only PostgreSQL and Databricks are verified
  today.
- Decide the ADR for the source-driven mode (C1) — brownfield customers often come without a requirements
  document.

---

## Follow-up (added 2026-10-23)

Recorded in `docs/log.md` (2026-10-22) and backlog `backlog-2026-10-candidates-2.md` (C14–C21 from this review):

- **Done:** `workbench/` ignored, the committed runs untracked, the owner's AdventureWorks build shipped as the
  curated demo `demo/workbench-adventureworks/` (C14); documentation drift corrected, ADR-0004/-0005/-0007
  accepted in the index (C16); release **0.10.0** published (C15).
- **Fixed beyond the review:** C11 (WP84), and two further data defects the owner's build found — nullable link
  participants (C12, WP83 phase 1) and satellite grain (C13, WP85, gate `E_SAT_GRAIN_NOT_UNIQUE`, 36 gates). The
  owner's vault rebuilt: 180 of 180 incremental models idempotent.
- **Correction to the review's premise:** PIT/Bridge is indeed ADR-0007's „Generate" class — candidate C22.
- **Open:** a second domain (C17), the inferred link stages (C18), workbench API tests (C19), positioning (C20),
  Snowflake (C21), C1.
