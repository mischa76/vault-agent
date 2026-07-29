# Backlog 2026-07 — fully specified work packages

Status: Proposed · Author: Mischa Eismann + Claude (project review 2026-07-06/07)

This package turns every open point from `docs/architecture/reviews/project-review-2026-07-06.md` (and the deferrals
recorded in CLAUDE.md) into implementation-ready specs. Each work package (WP) has a spec in
this directory and a self-contained kick-off prompt in `kickoff/` that a developer agent
(e.g. Claude Opus 4.8 via Claude Code) can execute without further briefing.

## Work packages and recommended order

| WP | Spec | What | Size | Depends on |
|----|------|------|------|------------|
| WP4 | `wp4-typed-validation-issue-spec.md` | `ValidationIssue` pydantic model replaces issue dicts | S | — |
| WP1 | `wp1-validator-gates-spec.md` | 4 new validator gates (eff-sat date order, dup attr, hub-HK collision, dup hub) | S/M | WP4 |
| WP2 | `wp2-adr-author-spec.md` | ADR author: correct caveat, per-output numbering, drop repo-path coupling | S | — |
| WP3 | `wp3-llm-cost-spec.md` | Prompt caching, errors-only retry feedback, input-size guard | S | — |
| WP5 | `wp5-hygiene-spec.md` | Renderer merge, dead code/deps removal, logging + `--debug`, checkpoint pruning, doc fixes | M | — |
| WP6 | `wp6-eval-harness-spec.md` | Eval harness: golden datasets, deterministic scorers, optional LangSmith layer | M/L | WP4 |
| WP7 | `wp7-staging-refinements-spec.md` | ma_sat staging grain, bound `source()` refs, seed column types | M | — |
| WP8 | `wp8-multi-role-links-spec.md` | Role-qualified link hub references (self-referencing links) — includes draft ADR-0009 | L | WP1, WP7 |
| WP9 | `wp9-mapping-spec.md` | Business↔source mapping (LLM-first, ratification file, category gate) — spike-validated | L | WP7, WP6, ADR-0008 Accepted |
| WP10 | `wp10-multi-source-hub-spec.md` | Multi-source hub: business-key harmonisation across sources | M/L | WP9 |

Rationale for the order: WP4 changes the shape WP1's new gates emit and WP6's scorers
consume — do it first. WP1/WP2/WP3/WP5 are independent of each other. WP8 is the most
invasive model change; land it last, on top of the hardened validator and staging layers.

## Parallel execution plan (waves)

Parallelism is limited by *file overlap* more than by logical dependencies: WP4 touches
`state.py`/`validator.py`/`orchestrator.py`/`dv2_modeler.py` (overlaps almost everything),
WP5 is a cross-cutting sweep, WP8 touches the whole link pipeline. The conflict-free
schedule, one agent per WP, one git worktree/branch per agent:

| Wave | Parallel WPs | Why this is safe |
|------|--------------|------------------|
| 1 | **WP4 + WP2** | WP2 (`adr_author.py` + own tests) is fully disjoint from WP4 |
| 2 | **WP1 + WP3 + WP6** | after WP4 merges they are near-disjoint: validator/rules vs. llm/parser/modeler vs. additive `eval/` |
| 3 | **WP7 + WP5** | WP7 needs WP1's final validator; WP5 sweeps the then-quiet cross-cutting files (coordinate `langsmith_*` with WP6) |
| 4 | **WP8 alone** | invasive; ADR-0009 gate; needs WP1 + WP7 |

Merge discipline (the actual success condition): every agent works on its own branch,
rebases onto main before review; merges are **serial**, full test suite as the gate — never
merge two WPs simultaneously. Known trivial conflicts: every WP appends a CLAUDE.md
milestone paragraph (resolve append-order at merge), and the kick-offs' STOP preconditions
(WP1/WP6 require WP4 merged) must be honoured by the wave scheduler, not the agents.

## Explicitly NOT in this package (needs a design spike / ADR first)

- **Business↔source mapping (Phase 2, ADR-0008): RESOLVED 2026-07-13.** The spike ran
  2026-07-12 (`spike-mapping-charter.md` → `spike-mapping-results.md`; finding: LLM-first
  mapping at 0.984 accuracy / 1.000 gap recall beat deterministic-first (0.65) at lower
  token cost). All maintainer decisions are taken (decision record in the results memo),
  ADR-0008 is **Accepted**, and the work is specced as **WP9** (mapping, single-source
  binding) + **WP10** (multi-source hub) with kick-offs. Only DDL/`information_schema`
  introspection and same-as links remain future work beyond WP10.
- **Contradiction reconciliation (reality-test #1).** Requires prompt-design
  experimentation with live LLM runs (and ideally WP6's eval harness to measure it). Not
  deterministically speccable today.
- **Typed source-schema quality gates (reality-test #4)** — blocked on the same Phase-2
  schema model as ADR-0008.
- **Business Vault assist, information-layer scaffolding, UI** — per ADR-0007 scope
  boundaries and CLAUDE.md ("no UI until the pipeline is stable on 2+ demos").

## Shared conventions (binding for every WP)

1. **Repo canon first.** Read `CLAUDE.md` fully before coding: technology lock, code
   conventions, "What NOT to do", current milestone. It overrides anything else.
2. **Rules live in `src/vault_agent/rules/dv2_rules.py`**, never in prompts or agents.
   New thresholds/tokens/constants go there with a comment citing the DV2.0 rationale.
3. **Typed flags.** Agent findings go through `state.flag(...)` (`PipelineFlag`); consumers
   branch on `kind`/`asset`, never on message text. New kinds are added to `FlagKind` and,
   if aggregatable, to `orchestrator.REVIEW_FLAG_GROUPS` + `_GROUP_LABELS`.
4. **Determinism.** Everything except the four LLM extractors must be unit-testable without
   an API key. LLM calls go exclusively through `vault_agent.llm.ForcedToolCaller`.
5. **Never silently guess.** Unknowns are named and flagged for human review.
6. **Definition of Done (every WP):**
   - `uv run pytest -q` green (all existing + new tests), no test deleted without
     replacement;
   - `uv run ruff check .` clean; `uv run mypy src/vault_agent` strict clean;
   - the bank demo guardrail tests (`tests/test_demo_bank_postgres.py`) still pass and the
     regenerated demo models stay byte-identical unless the spec says otherwise;
   - CLAUDE.md "Current milestone" gets a dated paragraph describing what landed;
   - docs that the change invalidates are updated in the same commit.
7. **Commit style:** conventional commits, one WP = one commit (or a small series), spec
   referenced in the body.

## How to run a developer agent on a WP

Give the agent the matching `kickoff/WPn-*.md` file as its task prompt, with the repo as
working directory. The kick-off tells it what to read, what to build, and how to verify.
Review its output against the spec's acceptance criteria before merging.

## Addendum 2026-07-18 — UI track (post-review additions)

Two WPs added after the original package, from the UI-track decision 2026-07-17
(see `../roadmap-2026-07-productization.md` for the full sequence incl. the
scale-test / residency / competitive-brief charters):

| WP | Spec | What | Size | Depends on |
|----|------|------|------|------------|
| WP11 | `wp11-html-run-report-spec.md` | Static HTML run report (model graph, review queue, mappings) — UI stage 1 | M | — |
| WP12 | `wp12-interactive-resume-spec.md` | Interactive checkpoint prompt in the CLI — UI stage 1.5 | S/M | — |
| WP13 | `wp13-scale-hardness-spec.md` | Scale hardness test: landscape generator, eval cases, usage capture (Charter A) | M | WP6 |
| WP14 | `wp14-scale-mapping-coverage-spec.md` | Column-based mapping coverage for scale cases (eval-only; before the scale_100 live step) | S | WP13 |
| WP14.1 | kickoff-only (`kickoff/WP14.1-eval-run-persistence.md`, spec = findings Candidate #3) | Crash-safe per-repeat result persistence in eval.run | S | WP13 |

Both are bound by the CLI-first invariant (WP11 §1): pure console operation stays a
complete mode; nothing may become web- or prompt-only. Kick-offs: `kickoff/WP11-html-run-report.md`,
`kickoff/WP12-interactive-resume.md`.

## Addendum 2026-07-28 — review batch (project review 2026-07-28)

Five WPs from `../reviews/project-review-2026-07-28.md` (findings 1–7). Shared
conventions above apply unchanged.

| WP | Spec | What | Size | Depends on |
|----|------|------|------|------------|
| WP17 | `wp17-cli-crash-recovery-spec.md` | CLI crash recovery: crashed `pending.json` phase, artifacts-so-far, resumable crashed threads, orphan pruning (finding 1) | M | — |
| WP18 | `wp18-eval-gate-integrity-spec.md` | Eval gate integrity: loud missing-scorer gates, one vacuity convention, runtime vacuous-gate rejection (finding 2; eval/ only) | S | — |
| WP19 | `wp19-contract-truncation-split-spec.md` | data_contract onto `call_with_truncation_split` (finding 3) | S | — |
| WP20 | `wp20-name-gates-spec.md` | `E_BAD_NAME` gate + steering line, `write_outputs` refuse-guard, staging-name unification, normalised `E_SAT_ATTR_OVERLAP` (findings 4+5) | S | — |
| WP21 | `wp21-robustness-hygiene-spec.md` | Flag-and-skip unreadable documents + hygiene batch 7a–f (findings 6+7) | S/M | WP17 |

Waves (file-overlap driven, one branch per WP, serial merges as above): **wave 1 =
WP18 + WP19 + WP20 in parallel** (eval/ vs. data_contract vs. validator/rules/generators
— WP20's small `write_outputs` guard is the only cli.py touch and merges before WP17
reworks that file); **wave 2 = WP17 alone** (invasive cli.py rework); **wave 3 = WP21**
(cross-cutting sweep; STOP precondition WP17 merged). Recommended order rationale: the
review pairs WP17+WP18 as highest impact — the safety net (pipeline) and the quality
gates (eval) both have holes exactly where one would fall; WP19 and WP21 §2.1 remove the
two remaining ways a run dies avoidably, which also makes future scale_100 attempts
cheaper.

## Addendum 2026-07-29 — scaling decision + brownfield track

From ADR-0010 (Accepted 2026-07-29: streaming before staged modelling) and the
incremental-extension charter (Accepted; §5 decisions 2026-07-29):

| WP | Spec | What | Size | Depends on |
|----|------|------|------|------------|
| WP22 | `wp22-streaming-spec.md` | Streaming in `ForcedToolCaller`; modeler budget past the 16384 transport stopgap | S/M | ADR-0010 |
| WP23 | `wp23-incremental-extension-spec.md` | Brownfield mode Phase 1: `--existing`, dv_model.yml round-trip, merge + additive `E_EXISTING_*` gates, grandfathering, diff artifact, delta-ADR | L | — |

WP22 and WP23 are file-disjoint (llm.py/dv2_modeler constant vs. the extension surface)
and can run in parallel; merge serially as usual. WP22 unblocks the scale_100/300 live
measurements; WP23 Phase 2 (LLM entity resolution) follows as its own spike per the
charter, after Phase 1 lands.

## Addendum 2026-07-29 — review batch (project review 2026-07-29)

Four WPs from `../reviews/project-review-2026-07-29.md` (findings 1–5). Shared conventions
above apply unchanged. Note the theme: after WP17–WP21 the individual features are sound —
these findings sit **between** features (WP7 × WP10), and in what the pipeline reports
about itself when things go wrong.

| WP | Spec | What | Size | Depends on |
|----|------|------|------|------------|
| WP24 | `wp24-multi-source-composition-spec.md` | Every hub-key hash through `canonical_hub_key_column`; reject the WP7+WP10 satellite combination; the WP7×WP8×WP10 composition matrix (findings 2+3) | S/M | — |
| WP25 | `wp25-failed-run-outcome-spec.md` | A failed run is first-class: route the exhausted re-model loop into the checkpoint (ADR-0006), exit code 3, ADR caveat when accepted over errors (finding 1) | M | — |
| WP26 | `wp26-adr-completeness-spec.md` | ADR renders driving keys, multi-source feeds, satellite types, ratified mappings; determinism claim made true (finding 4) | S | — |
| WP27 | `wp27-ci-retry-hygiene-spec.md` | CI runs the canonical `uv run mypy`; `Retry-After` + jitter; attributable error on a corrupt `pending.json` (finding 5) | S | — |

Waves (file-overlap driven): **wave 1 = WP24 alone** — it is the only finding producing
wrong *data*, it must precede any further multi-source work (WP23's merge path inherits the
same hashing helper), and it touches the generators the others do not. **Wave 2 = WP25 +
WP26 + WP27 in parallel** (graph/cli vs. adr_author vs. ci/llm/`_read_pending`); the one
overlap to watch is WP25's ADR caveat vs. WP26's renderer — merge WP26 first and let WP25
rebase onto it. Cross-batch: **WP26 must land before WP23's delta-ADR** (§2.8), and WP27
must rebase onto WP22 if streaming lands first (both edit `ForcedToolCaller.call`).
