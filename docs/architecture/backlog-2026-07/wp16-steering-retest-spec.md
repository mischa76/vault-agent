# WP16 — Steering-rule registry, backstop telemetry, and the model-release re-test

Status: Proposed · Size: M · Depends on: WP15 (the `TraceEvent` seam; `backstop` kind is
reserved there). Origin: Karpathy, *LOOPS.md* rule VIII ("Delete the harness") — re-read
the harness against each new model release and delete what the model now does for free;
adaptation review 2026-07-22.

## 1. Problem

Parts of the harness exist because the *current* models failed: the CDK "key column, not
payload" prompt line landed only after LLM steering failed 4/4 even with error feedback,
plus a deterministic backstop (`attributes_without_cdk`); WP9.1 added the FK-demotion
backstop; the eff_sat two-dates line has a generator-side rejection behind it. That is
correct belt-and-braces engineering — but it is model-compensation, and nothing today
can answer "does Sonnet-next still need this?". The steering lines live as an anonymous
`DV_MODELING_RULES: list[str]`, the backstops fire invisibly (`logger.info` at best), and
a model bump (config `heavy_model`/default model change) has no re-test protocol. The
harness grows monotonically — which per LOOPS.md means it has stopped being read.

Scope boundary, stated up front: the **validator gates are the product**, not
model-compensation — an enterprise DV2.0 tool needs deterministic, auditable E_/W_ gates
regardless of model quality. Nothing in this WP proposes deleting a gate. The measurable,
potentially deletable surface is (a) prompt steering lines and (b) deterministic
*pre-gate* backstops that repair LLM output before validation.

## 2. Design

### 2.1 Steering registry (`rules/dv2_rules.py`)

`DV_MODELING_RULES` becomes `list[SteeringRule]` (frozen dataclass, rules stays
pydantic-free): `id` (stable snake_case, e.g. `cdk_not_payload`, `effsat_two_dates`,
`unit_of_work`, `role_qualified_participation`, `masat_source_table`), `text` (today's
strings, byte-identical), `backstop: str | None` (the linked backstop's id where one
exists, e.g. `cdk_not_payload` → `attributes_without_cdk`), `origin` (WP/date, why it
exists). The modeler's `_build_system_prompt` joins `rule.text` — rendered prompt
**byte-identical** to today (pinned). The source_mapper's steering (the FK-anchor and
cross-system-deferral rules in `prompts/source_mapper.md`) stays in its prompt file —
it is mapping heuristics, not DV rules — but is *inventoried in the ledger* (2.5) with
a manual-ablation note; mechanically ablatable rules are the modeler registry only, v1.
Ids unique across the registry (tested).

### 2.2 Ablation seam (`rules/dv2_rules.py` + `agents/dv2_modeler.py`)

`active_modeling_rules() -> list[SteeringRule]` honours a module-level exclusion set
(`set_excluded_rules(ids | None)`, mirroring `set_usage_recorder` — harness-injectable
without threading args through agents). `_build_system_prompt` calls it instead of
reading the constant. Unknown ids raise (attributable, house loader style); empty/None
is byte-identical to today. Production code never sets exclusions — the seam exists for
`eval/ablate.py` only.

### 2.3 Backstop-fire telemetry (via the WP15 trace channel)

Each pre-gate backstop emits a `TraceEvent(kind="backstop")` when — and only when — it
actually repairs something: `attributes_without_cdk` (fired from the modeler when
`deduped != sat.attributes`, carrying satellite name + dropped attrs), the WP9.1
FK-demotion in `source_mapper._post_validate` (concept + demoted candidates), the code
generator's eff_sat `!= 2`-attributes rejection (construct name; the GENERATION_GAP flag
stays — the event adds the *counting* channel, the flag stays the human-review channel).
Emitted through the WP15 recorder seam (no recorder set → no-op, zero behaviour change).
`eval/run.py` counts `backstop` events per repeat into the `metrics` block
(`backstop_fires: {<backstop_id>: n}`).

### 2.4 Ablation runner (`eval/ablate.py`, new)

`python -m eval.ablate --case <name> --drop <rule_id> [--model <id>] [--repeat N]`:
runs the real graph per repeat (MemorySaver + auto-resume, exactly `eval.run`'s
mechanics — reuse `run_case_once`, don't duplicate) once **baseline** and once with the
rule excluded, records for both arms: scores, validation issue codes, backstop fires,
usage. Output: one comparison JSON per invocation under `eval/results/ablation/`
(git-ignored) plus a printed two-column summary. `--model` overrides the modeler tier
for candidate-model probes. WP14.1 crash-safety semantics apply (persist each completed
arm immediately).

### 2.5 Steering ledger + release protocol (`docs/architecture/steering-ledger.md`, new)

One table row per registry id: linked backstop, model last tested, ablation result
(baseline vs. dropped: score delta, backstop fires, new validation errors), verdict
`keep | candidate-delete | deleted (date)`. Protocol, documented in the ledger header:
on any model bump, run the ablation matrix (gated cases × rules with `backstop` set —
the cheap, high-signal subset first); a rule whose ablation shows **zero backstop fires
and no gated-score regression across N ≥ 3 repeats** becomes `candidate-delete` — a
human decides (the registry `origin` says what it cost to learn; deleting prompt text
is cheap to revert, deleting a backstop requires the matching ablation evidence AND
keeping its E_-gate, which catches the failure if the deletion was wrong). Seed the
ledger with the current inventory and today's known evidence (CDK: 4/4 failure on
sonnet-tier, 2026-07-16).

### 2.6 Out of scope

Deleting anything in this WP (it builds the measuring instrument; verdicts are
follow-up, human-decided); ablating validator gates; automating the release protocol
into CI (manual pre-release discipline, like the eval gate).

## 3. Tests (keyless)

Registry: ids unique; rendered modeler system prompt byte-identical to pre-WP16
(pinned string fixture); exclusion drops exactly the named line; unknown id raises
attributably; exclusions cleared → identity. Telemetry (stub recorder): CDK dedup fires
one `backstop` event with the dropped attrs, a clean model fires none; FK-demotion and
eff_sat-rejection likewise; no recorder → no-op. Ablation runner (stubbed
`run_case_once` seam, WP14.1 style): two arms run, JSON shape, immediate persistence on
arm-2 failure. Eval metrics: `backstop_fires` aggregated per repeat.

## 4. Acceptance

1. Byte-identity: no exclusions and no recorder → modeler prompt, pipeline behaviour,
   and all existing fixtures unchanged.
2. A live ablation of `cdk_not_payload` on `health_insurance` (the case that forced the
   rule) reports backstop fires in the dropped arm — demonstrating the instrument
   detects a still-needed rule (expected with current models; if it reports zero fires,
   that is itself the first ledger entry).
3. `steering-ledger.md` exists, seeded with the full inventory and the release protocol.
4. Suite green, ruff clean, mypy strict clean.
