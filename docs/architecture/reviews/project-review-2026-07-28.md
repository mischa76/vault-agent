# Project Review vault-agent — as of 2026-07-28

Scope: full project review over the current codebase (src/vault_agent, eval/, tests, CLI,
docs), 95 commits after the previous review (`project-review-2026-07-06.md`, baseline
`fdb2c70`). Method: code reading with findings verified against the named files/lines;
pytest/ruff/mypy were NOT re-run for this review (the CLAUDE.md milestone records 465
green as of 2026-07-28 — re-verify in the WSL environment before acting on this document).

Status of the previous review: all ten optimisation points (P1–P10 of 2026-07-06) are
demonstrably implemented and verified — typed flags, hardened LLM call path, staging
generator, the four validator gates, exact-asset HITL pruning, ADR-author remediation,
prompt caching, typed ValidationIssue, the hygiene batch, and the eval harness (which grew
far past the original ask: scale generator, ablation runner, trace capture, crash-safe
persistence). That document is now historical.

## Overall assessment

The discipline observed in July has held through a period of rapid feature growth
(WP7–WP16, mapping, multi-source hubs, traces, steering registry, output-budget
hardening). The conventions still hold under inspection: graph.py is pure wiring, rules
live in rules/, every LLM call goes through the single hardened `ForcedToolCaller`,
deterministic and LLM concerns stay separated per agent, consumers branch on typed
kinds/codes — never message text — and the review/render knowledge has exactly one owner.
Notably, the project's own failure analysis is now productised (traces, backstop
telemetry, steering ledger), which is rare at any maturity level.

No finding in this review is of the structural-debt class the 2026-07-06 review opened
with. The themes are instead: (1) the CLI never received the crash-safety the eval harness
got in WP14.1 — a mid-pipeline failure still loses paid-for work; (2) the eval gate
mechanism can silently pass on absence of evidence in ways the WP14/2026-07-28 fixes did
not fully close; (3) LLM-derived construct names are trusted at the filesystem boundary,
inconsistently with the report's "every state string is hostile" posture; (4) one agent
(data_contract) still lacks the truncation-split the other three list-shaped agents share.

## Strengths

The output-budget hardening is exemplary engineering-from-measurement: budgets are set
from replayed traces, the sub-linear growth numbers are recorded next to the constant they
justify (`dv2_modeler.py:40-47`), and what is NOT proven (scale_100 end-to-end) is stated
in bold before anyone can over-read it. The WP16 steering registry answers a question most
LLM products cannot even ask ("does the next model still need this prompt line?") with a
measurement, and the live ablation of `cdk_not_payload` showed the telemetry catching a
regression the scores hid. Escaping in report.py is thorough (verified: every LLM-derived
string passes `_esc`, Mermaid labels included). The scorer-universe/vacuity/link-grain
fixes each came with the honest generalisation ("third instance of the same class") written
down rather than rediscovered.

## Weaknesses and risks (prioritised, with locations)

**1. The CLI has no crash-recovery path — a failed run loses everything paid for.**
When any node raises after expensive LLM work (a truncation past `MAX_SPLIT_DEPTH`, a
non-retryable 4xx mid-pipeline, a decode error — see finding 6), `_run_pipeline` propagates
(`cli.py:711-718`), `write_outputs` never runs, no `pending.json` is written, and `resume`
refuses (`cli.py:777-780`: it requires `pending.json`). The state IS in
`checkpoints.sqlite` — every completed node checkpointed — but no CLI surface can reach it:
the thread_id is printed nowhere and `_paused_state` is only wired to the interactive
resume. Consequence: a scale_100-style run that dies at the source_mapper discards a
validated model plus ~$5 of tokens, exactly the class WP14.1 fixed for eval. Bonus defect:
the orphaned thread is never pruned (WP5 §5.5 deletes only *finalised* threads), so crashed
runs regrow `checkpoints.sqlite` unboundedly.

**2. Eval gates can silently pass on absence of evidence — two remaining holes.**
(a) `failed_gates` checks `name in stats` (`eval/run.py:215-221`): a gated scorer that
never produced a score is skipped without a word. A typo'd scorer name in `min_scores`, or
a committed case whose `golden_mapping.yml` is missing (`materialize_case` returns `None`
→ `_score_run` skips the mapping scorers), disables the gate and exits 0. scale_30 gates
`mapping_coverage` — delete its golden mapping and the batch goes green.
(b) The vacuity contract is enforced only for `construct_f1`/`driving_key_accuracy`
(`eval/datasets.py:180-193`). The mapping family is unprotected: `mapping_coverage` with
zero mappable golden entries returns a gateable 1.0 ("no mappable golden entries",
`eval/scorers.py:407-411`), and the loader cannot check it because the golden mapping
lives in a file it never opens. The vacuous-marking convention is also inconsistent —
only `construct_f1`/`driving_key_accuracy` emit the `"vacuous"` details prefix that
`vacuous_scorers` and the console marker key on; `confidence_calibration` even scores its
nothing-to-check case 0.0 (`eval/scorers.py:480-481`), the opposite convention. This is
the fourth instance of the recorded "gate/score on absence of evidence" class.

**3. data_contract is the last list-shaped agent without the truncation-split.**
The enricher chunks by a fixed `_FIELDS_PER_CALL = 40` and its own margin arithmetic is
thin: ~200 output tokens/field worst case × 40 = ~8,000 of the 8,192 budget
(`data_contract.py:46-51`). A denser-than-assumed chunk truncates → `LLMCallError`
propagates → the whole run dies (finding 1 amplifies the cost). The 2026-07-28 milestone
itself argues fixed thresholds are the wrong proxy; the shared
`llm.call_with_truncation_split` fits here directly (unit = field chunk, merge =
`_merge_enrichment`, which already exists).

**4. LLM-derived construct names are trusted at the filesystem and dbt boundary.**
No gate validates name well-formedness. `write_outputs` does
`models_dir / f"{name}.sql"` with `name` from `dv_model` constructs and
`contracts_dir / f"{asset}.contract.yml"` with the asset name (`cli.py:99-138`); a name
containing a path separator or `..` writes outside the output directory, and a name with
spaces/uppercase produces dbt models that cannot be referenced. report.py treats every
state string as hostile; `write_outputs` and the generators do not. Related inconsistency:
a `source_table` satellite's staging name normalises the base
(`code_generator._sat_staging_model`) while every other staging name uses the raw base
(`staging_generator._staging_name`) — two naming paths that agree only for well-formed
names. Fix in one place: an `E_BAD_NAME` validator gate (`^(hub|link|sat)_[a-z0-9_]+$` or
similar) blocks before generation, mirroring how E_SAT_DUP_ATTR pre-empts the build error.

**5. E_SAT_ATTR_OVERLAP matches raw strings, not normalised identifiers.**
`validator.py:367-371` keys the cross-satellite overlap check on the raw attribute label,
while E_SAT_DUP_ATTR (within one satellite) normalises. "Customer ID" in sat A and
"customer_id" in sat B of the same parent — the same generated column twice on one parent —
passes the gate. One-line fix plus a test; keep reporting the original labels.

**6. One unreadable document kills a run instead of being flagged.**
`_read_document` flags-and-skips unknown extensions, but `read_text(encoding="utf-8")`
(UnicodeDecodeError on a Latin-1 file), a corrupt PDF (pypdf raises), or a broken .docx
propagate uncaught (`requirements_parser.py:271-277`) — ending a possibly multi-document
run at its first step, against the module's own flag-and-skip contract. Wrap the three
extractors; flag `MISSING_INPUT`-style and continue.

**7. Hygiene batch (each small, none urgent).**
(a) `ForcedToolCaller._record_usage`'s docstring promises a recorder error "never
disturbs the call path", but unlike `emit_trace` there is no try/except
(`llm.py:334-348`) — a raising usage recorder kills the call after a successful, billed
response. (b) `aggregate_review_flags` hardcodes `source="data_contract"` on every
collapsed line (`orchestrator.py:197`) — wrong attribution for the source-binding
(code_generator) and mapping (source_mapper) groups. (c) The validator docstring says
"30 as of WP8"; the module has 32 codes (WP10 added E_HUB_DUP_FEED and
W_HUBSOURCE_BK_NOT_IN_SOURCE) — drop the number or keep it right. (d) The WP10
multi-source satellite path skips `_collision_warnings` (`code_generator.py:452-477`
`continue`s before `_render_satellite`, where the check lives). (e)
`dv2_modeler._validate_items` drops invalid records with no `asset` attribution — the one
DROPPED_RECORD flag a reviewer cannot trace to a construct. (f) `run --no-write` on a
paused run still writes `pending.json` and prints resume instructions whose resume WILL
write to disk — decide and document which semantics `--no-write` has across the pause.

## Open points / deliberately deferred (unchanged, recorded elsewhere)

scale_100 has never completed end-to-end; the modeler sits at 91% of the non-streaming
16384 ceiling, so 300 tables needs streaming in ForcedToolCaller or staged modelling —
the next structural WP, already specced in prose. Hubs/satellites remain name-keyed in
eval (README caveat). Business Vault assist, mart scaffolding, DDL/DB introspection,
same-as links, mid-run regeneration of a newly-multi-source hub, and the UI stage 2 remain
deferred as documented.

## Optimisation potential (prioritised)

| P | Measure | Effort | Impact |
|---|---|---|---|
| 1 | CLI crash recovery: on any pipeline exception write `pending.json` (+ artifacts-so-far where safe) with the thread_id, teach `resume` to continue a crashed thread; prune orphaned threads | M | High — stops losing paid LLM work; parity with WP14.1 |
| 2 | Gate integrity: `failed_gates` fails loudly on a gated scorer absent from stats; extend the vacuity contract (details prefix + gate rejection) to the mapping scorer family; unify the vacuous convention (`confidence_calibration`) | S | High — the gates are the product's own quality claim |
| 3 | data_contract on `call_with_truncation_split` (split the field chunk on `truncated`) | S | Medium — removes the last hard-truncation death |
| 4 | `E_BAD_NAME` validator gate for construct-name format; sanitise/refuse odd names in `write_outputs` as defense in depth | S | Medium — closes the filesystem trust gap |
| 5 | Normalise E_SAT_ATTR_OVERLAP matching | S | Low-medium — real correctness hole, rare trigger |
| 6 | Wrap document extraction errors as flags (flag-and-skip) | S | Medium — robustness of the very first step |
| 7 | Hygiene batch (7a–7f) | S | Low — consistency and trust in the telemetry |

## Recommended order

P1 and P2 first, as a pair: both are "the safety net has a hole exactly where you'd fall"
findings — P1 for the pipeline, P2 for the quality gates that everything else (ablation
verdicts, release protocol, scale findings) leans on. Then P3+P6 (the two remaining ways a
run dies avoidably), then P4/P5 as the next validator batch, and the hygiene items
alongside whatever WP touches those files next. None of this blocks the declared next
structural work (streaming/staged modelling for 300 tables); P1 in particular makes those
expensive scale runs cheaper to attempt.
