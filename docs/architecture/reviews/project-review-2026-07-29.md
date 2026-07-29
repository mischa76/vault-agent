# Project Review vault-agent — as of 2026-07-29

Scope: full project review over the current codebase (src/vault_agent, eval/, tests, CLI,
docs, CI), 9 commits after the previous review (`project-review-2026-07-28.md`, baseline
`86e474c`): the WP17–WP21 batch plus ADR-0010, the brownfield charter, and the WP22/WP23
specs. Method: code reading, plus **executable probes for every correctness claim** — the
two composition defects below (findings 2 and 3) and the exit-code behaviour (finding 1)
were reproduced against the real code, not inferred. `uv run pytest -q` (509 passed),
`uv run ruff check .` and `uv run mypy` (37 files) were re-run green in the WSL
environment before writing this.

Status of the previous review: all seven findings (WP17–WP21) are implemented and
verified. Note for the reader: WP17–WP21 were implemented by the assistant in the same
session that produced this review, so those parts are a self-review — findings 1 and 5c
below are defects that batch did not create but also did not catch, and finding 2 sits in
code it touched (WP20 §2.4) without being caused by it.

## Overall assessment

The pipeline's failure surface is now genuinely good on the axes that were measured: a
crashed run keeps its work (WP17), no list-shaped agent can die of output density (WP19),
no LLM-derived name reaches the filesystem unchecked (WP20), no unreadable document ends a
run (WP21), and no eval gate can pass on absence of evidence (WP18). ADR-0010 continues the
project's strongest habit — deciding from replayed measurements rather than architecture
taste — and the brownfield charter opens the first genuinely new product surface since WP9.

This review's theme is different from the last two, and it is worth naming precisely: the
remaining defects are no longer in the individual features but **between** them. WP7
(satellite `source_table`), WP8 (role-qualified links) and WP10 (multi-source hubs) are each
correct and each tested; two of their pairwise combinations produce silently wrong output
and are covered by no test and no gate. The second theme is that the pipeline has no
first-class *failure* outcome: a model that never validates ends the run with exit code 0
and no ADR while its own review queue says "requires sign-off".

## Strengths

The WP17 crash path is the right shape: the rescue is guarded step by step and the original
exception always wins, which is the hard part of recovery code and the part most projects
get wrong. WP18's `VACUOUS_PREFIX` finally makes one convention greppable instead of four
conventions plus a comment. The steering registry, trace capture and backstop telemetry
keep paying off — ADR-0010's numbers came out of transcripts already on disk, at zero API
cost, exactly as the 2026-07-28 method note demanded. `report.py`'s hostile-string posture
is now matched by the write path (WP20 §2.3), closing a real asymmetry.

## Weaknesses and risks (prioritised, with locations)

**1. A model that never validates ends the run "successfully" — and the checkpoint that
should catch it is unreachable.**
`route_after_validation` (`graph.py:69-76`) routes to `END` once
`modeling_attempts >= MAX_MODELING_ATTEMPTS`, bypassing `human_checkpoint` and `adr_author`.
But `HumanReviewQueue.requires_signoff` (`orchestrator.py:90-96`) treats a validation error
as blocking, and ADR-0006 plus `docs/architecture/1-architecture-overview.md:44` both state
that a validation error surviving the re-model budget is exactly what makes the checkpoint
block. That branch can never fire from the graph: `passed` is false precisely when an error
issue exists, and such a state never reaches the node. Reproduced end-to-end with a stubbed
graph whose validator always fails: the CLI prints *"Human-in-the-loop checkpoint — requires
sign-off (1 item)"*, writes `review-queue.md` with **Status: requires sign-off**, writes no
ADR, writes no `pending.json` — and **exits 0**. So: a script cannot distinguish a failed run
from a good one; the queue points at a checkpoint that does not exist; `resume` says "No
unfinished run found"; and `docs/operations/06-running.md:59` ("Three failed attempts end the
run as failed") is not true of the exit code. Design question the fix must answer, not dodge:
does an unvalidatable model deserve a human decision (route it into the checkpoint, per
ADR-0006) or only a non-zero exit?

**2. A link or satellite attached to a multi-source hub hashes a DIFFERENT column than the
hub does — silent join failure.**
`rules.canonical_hub_key_column()` exists as the single source of truth for a hub's staging
key column, and WP10 uses it in exactly two places (`staging_generator.py:144`,
`code_generator.py:141`). Everything else that hashes a hub's key still calls
`_to_column(hub.business_key)` directly: link participations
(`staging_generator.py:175`), a `source_table` satellite on a hub parent (`:205`), and on a
link parent (`:213`). When a multi-source hub's feeds *agree* on a physical column name that
differs from the business-key label, canonical is that source column while the link stages
the business-key label. Probed:

```
stg_customer_crm_customer:  CUSTOMER_HK <- CUSTOMER_KEY      # the hub
stg_account_customer:       CUSTOMER_HK <- CUSTOMER_ID       # the link's FK
```

Same target column, different hash input: the link's FK can never match the hub's hash key.
Every existing test and the WP10 Postgres verification use the *disagreeing* case, where
canonical happens to equal `normalize(business_key)` — so the bug is invisible to the whole
suite. This is the worst defect class for a Data Vault tool (wrong data, no error), and it is
a single-source-of-truth violation of a helper written for exactly this purpose.

**3. WP7 + WP10 compose into a dbt project that cannot build, with zero flags.**
A satellite declaring `source_table` on a multi-source hub takes the `source_table` branch in
`collect_staging_specs` (`staging_generator.py:191`) — one staging model carrying the
hashdiff — while `code_generator.py:455-478` ignores `source_table` on the multi-source path
and emits one satellite per source reading `stg_<entity>_<source>`. Probed output: two models
`sat_customer_details_{crm_customer,victor_partner}` referencing
`CUSTOMER_DETAILS_HASHDIFF`, which is computed only in the orphaned `stg_customer_details`
that nothing references. `dbt build` fails on a missing column; `state.flags` is empty. The
generator already flags the *other* unsupported multi-source combination (a non-standard
satellite type, `code_generator.py:461`) — this one was simply not considered. Same class as
WP8's `t_link` and WP9 §10.8's duplicate `sources.yml`: an untested feature combination,
found by composing rather than by using.

**4. The ADR omits the decisions the pipeline is proudest of, and one CLAUDE.md claim about
it is false.**
`adr_author._render` renders hubs (name, business key, description), links (participations
incl. ADR-0009 roles, unit of work) and satellites (parent, payload, split rationale). It
does **not** render: `Link.driving_key` — although CLAUDE.md states "State carries
Link.driving_key … for the ADR trail, which the adr_author surfaces when present" (grep:
`driving_key` does not occur in `adr_author.py`); `Hub.sources`, so a hub integrating two
source systems reads identically to a single-source hub, i.e. the WP10 integration decision
is invisible in the architecture record; `Satellite.sat_type`/`child_dependent_key`; and the
ratified business↔source mappings (WP9), which exist only in `mappings.review.yml`.
Separately, the module docstring promises "Same state in, byte-identical ADR out" while
`date.today()` (`adr_author.py:63`) makes that false across midnight — the injectable
`today` parameter is the fix's shape, the claim needs to match it.

**5. Hygiene (each small, none urgent).**
(a) **CI type-checks less than the DoD.** `.github/workflows/ci.yml:22` runs `uv run mypy
src`, and `pyproject.toml:70`'s own comment says an explicit path overrides
`files = ["src/vault_agent", "eval"]` — so `eval/` (2,000+ lines, WP6/13/14/16/18) is
strict-checked locally and not in CI.
(b) **The retry policy ignores the server's own advice.** `ForcedToolCaller` retries
429/5xx three times at a fixed 2/4/8s (`llm.py:246-248`) without reading `Retry-After` and
without jitter. A rate-limited enterprise key returning `Retry-After: 30` fails the whole
call in 14 seconds; concurrent runs retry in lockstep. Post-WP17 the run is at least
resumable, which lowers the severity but not the waste.
(c) **`resume` still has one unguarded read.** `cli._read_pending` does a bare
`json.loads` and `resume` calls it outside any try (`cli.py:1131`), so a truncated or
hand-edited `pending.json` — now a file users are told about and may edit — surfaces as a
raw `JSONDecodeError` traceback instead of an attributable message. `_report_crashed` and
`_prune_orphan_threads` already guard the same call.

## Open points / deliberately deferred (recorded elsewhere, unchanged)

scale_100 has never completed end-to-end; ADR-0010 decided streaming first (WP22) and
defers staged modelling. Brownfield/incremental extension is chartered and specced (WP23),
Phase 2 (LLM entity resolution) is its own future spike. Hubs and satellites remain
name-keyed in the eval scorers (README caveat). Business Vault assist, mart scaffolding,
DDL/`information_schema` introspection, same-as links, mid-run regeneration of a
newly-multi-source hub, and UI stage 2 remain deferred as documented. WP15's "a resume
appends to the same transcript" stays structurally unverifiable while every post-checkpoint
node is deterministic.

## Optimisation potential (prioritised)

| P | Measure | Effort | Impact |
|---|---|---|---|
| 1 | Route every hub-key hash through `canonical_hub_key_column`; reject the WP7+WP10 satellite combination with a flag + gate instead of emitting unbuildable SQL; add the composition matrix to the tests | S/M | **High — silent wrong data today** |
| 2 | Make a failed run a first-class outcome: decide checkpoint-vs-exit per ADR-0006, exit non-zero when a run ends unfinalized, align the docs | M | High — the product currently reports success on failure |
| 3 | ADR completeness: driving keys, multi-source feeds, satellite types/CDK, ratified mappings; make the determinism claim true | S | Medium — the ADR is the human-facing deliverable |
| 4 | Hygiene: CI runs the canonical `uv run mypy`; honour `Retry-After` + jitter; attributable error on a corrupt `pending.json` | S | Low-medium — trust in the gates and the recovery path |

## Recommended order

P1 first and alone: it is the only finding that produces wrong *data* rather than a wrong
*message*, and it is cheap. P2 next — it is the last place where the product's own
self-assessment (the review queue) and its externally visible behaviour (exit code,
artifacts) contradict each other, which matters more the moment anyone automates around the
CLI. P3 should land **before** WP23's delta-ADR, since both edit `adr_author._render` and
the extension case is easier to express on a complete renderer than on a partial one. P4
alongside whatever touches those files next. None of this blocks WP22 (streaming) or WP23
(brownfield Phase 1); P1 in particular should land before any further multi-source work,
because WP23's merge path will inherit the same hashing helper.
