# Spike charter — entity resolution against an existing vault (brownfield Phase 2)

Status: Proposed · Type: timeboxed design spike (NOT a work package) ·
Timebox: 2–3 agent-days · Decision maker: Mischa Eismann ·
Output feeds: a Phase-2 WP spec + the same-as decision the roadmap has deferred twice ·
Source: incremental-extension charter §3.5 / §4 (Phase 2), with the mapping spike
(`spike-mapping-charter.md` → `spike-mapping-results.md`) as the explicit template

## 1. Goal

Answer, with **measured evidence**, whether the agent can propose — reliably enough to be
worth building — the answer to the one genuinely new question brownfield mode asks:

> The new source describes a "Partner". Is that the existing `hub_customer`, or a new hub?

This is the WP9 mapping problem one level up: concept↔**concept** instead of
concept↔column. The whole WP9 apparatus is expected to transfer (evidence trail,
deterministic confidence categories, honest `unresolved`, HITL ratification,
post-validation that never invents a construct), and the spike's job is to find out where
that expectation breaks.

**Phase 1 already works without this.** `--existing` extends a vault today, provided the
human answers the resolution question themselves — by naming the existing construct in the
requirements, or by correcting the delta. Phase 2 only automates the *proposal*. That makes
"do not build it" a cheap and acceptable outcome, and the spike must be run in a way that
can actually reach that conclusion.

## 2. The asymmetry that shapes everything else

WP9's mapping spike optimised for accuracy: a wrong `concept → TABLE.COLUMN` proposal is a
bad suggestion a human corrects at the checkpoint. **Entity resolution is not symmetric in
that way.**

- A **false merge** — declaring the new source's "Kontakt" to be the existing
  `hub_customer` when it is a different concept — feeds foreign business keys into a hub
  that holds live history. It is the destructive migration the entire brownfield charter
  (§2) exists to refuse, arrived at through the front door.
- A **false split** — proposing a new hub where the existing one was meant — costs a
  redundant hub the human deletes at the checkpoint. Recoverable and visible.

So the spike's primary metric is **not** accuracy. It is:

> **false-merge rate must be 0**, and `unresolved` must be strongly preferred over a
> confident wrong merge.

A mechanism at 95% accuracy with one false merge is a **worse** result than one at 80%
accuracy with none. The memo must report both numbers separately and must not average them
into a single score. If no mechanism reaches zero false merges on the trap set, the honest
outcome is "propose nothing; keep the human answering", and §8 says so.

## 3. Non-goals

- No changes to `src/vault_agent/` (prototype code lives under `spike/`, deleted at the
  end; only docs and eval assets survive — the mapping spike's rule, which held).
- No Phase 3 work: foreign-vault introspection stays deferred (its own charter).
- No change to the merge/gate machinery WP23 shipped. Resolution feeds the modeler's
  NAMING; `merge_models` already folds a delta that re-uses an existing name, and the
  `E_EXISTING_*` gates already refuse anything non-additive. That integration point is
  fixed, not spike territory.
- No new trust model — ratification stays the ADR-0006 checkpoint.

## 4. Deliverables

| # | Deliverable | Form |
|---|-------------|------|
| D1 | Golden entity-resolution set with the four trap classes (§5) | `eval/datasets/<case>/golden_resolution.yml` |
| D2 | Deterministic scorers: `resolution_accuracy`, **`false_merge_rate`**, `new_hub_detection`, `resolution_calibration` — keyless-tested. These SURVIVE the spike (eval assets, WP6 patterns) | `eval/scorers.py` additions |
| D3 | Two candidate-mechanism prototypes (§6) | `spike/` throwaway code |
| D4 | Measured comparison: the four scores + token cost + latency, ≥ 5 repeats per variant per case | results JSON + table in the memo |
| D5 | Decision memo answering §7 | `spike-entity-resolution-results.md` |
| D6 | Either a draft Phase-2 WP spec, **or** a written recommendation not to build it | backlog format |

## 5. Golden set — dataset design (D1)

Built on the existing `bank_extension` case (a vault + a new source already exist there),
extended with a second, harder case if the first proves too easy. Each entry is
`new-source concept → {existing construct | NEW | same_as_candidate}` with a rationale
line, so a failure can be read without re-deriving the intent.

Four trap classes, each present by construction and named in the file:

1. **Synonym hub (must resolve).** The new source calls it `PARTNER`; the vault has
   `hub_customer` keyed on the national customer ID; the new source's key column carries
   the same identifiers. Correct answer: the existing hub.
2. **False friend (must NOT merge).** The new source has `KONTAKT` — a contact *person* at
   a corporate customer, keyed on its own contact ID. Name and domain both smell like the
   customer hub. Correct answer: NEW hub. This is the trap the primary metric is about.
3. **Legitimate new hub despite a similar name (must NOT merge).** `VERTRAGSPARTNER`
   (contract counterparty) next to an existing `hub_partner`: adjacent vocabulary, genuinely
   different concept and key. Correct answer: NEW hub.
4. **Same-as candidate (must be FLAGGED, never merged).** Two keys asserted equivalent but
   *different*: the vault's `hub_customer` on `national_customer_id`, the new source keyed
   on `crm_guid`, with a cross-reference table asserting the correspondence. Charter §3.5
   makes this an expected OUTPUT: **two hubs plus a flagged same-as candidate for human
   ratification — never a silent merge.** A mechanism that merges here scores a false merge.

Anonymised throughout (ATLAS convention), DACH-flavoured naming as in `messy_insurance`, so
the traps are the kind a real project produces rather than synthetic riddles.

## 6. Experiment protocol (D3/D4)

Both variants receive identical inputs: the existing model's construct inventory (names,
business keys, source entities — what `render_extension_prompt_section` already builds), the
new source's declared schema, and the requirement text. Both emit the same typed result:
per new concept a `(resolution, confidence, category, evidence: list[str])` where
`resolution ∈ {existing construct name, NEW, same_as_candidate, unresolved}`.

- **Variant A — deterministic-first.** Key-overlap is the strong signal here and it is
  computable: normalised business-key match, key-format/value-overlap from profiling, name
  similarity. Only ambiguous concepts go to one forced-tool-call LLM pass with the shortlist.
  Hypothesis: near-perfect on traps 1 and 4 (they are key-level facts), weak on 2/3 where the
  distinction is semantic.
- **Variant B — LLM-first.** One forced-tool-call pass over inventory + schema + comments,
  then deterministic post-validation (a named construct must exist; a claimed key overlap
  must hold against the declared schema — violations become `unresolved`, never silent).
  Hypothesis: better on the semantic traps, and the false-merge risk lives here.

Protocol: ≥ 5 repeats per variant per case; record all four scores plus tokens and wall time
per run; results JSON in the `eval/results/` shape. Then:

- **Degraded-mode probe.** Re-run the winner with comments stripped and with an
  opacity-masked schema (the WP9 §10.7 transform already exists and is reusable). The
  question is not whether accuracy drops — it will — but whether the mechanism degrades
  *honestly*: more `unresolved`, not more confident merges. Rising false merges under
  degradation disqualifies a mechanism outright.
- **Trap autopsy.** Per trap class, which variant fails how, and whether the failure is
  visible in the evidence trail a human would read at ratification.

## 7. Questions the memo (D5) must answer

1. Does either mechanism reach **zero false merges** across ≥ 5 repeats on all four traps?
   If not, does the evidence trail at least make the wrong merge *reviewable* — and is that
   enough, given the human is reviewing a vault they cannot easily un-corrupt?
2. Which mechanism, at what accuracy and cost? Is the LLM's contribution above the
   deterministic key-overlap baseline worth its spend — measured, not assumed? (The mapping
   spike found LLM-first won at *lower* input cost; do not assume that transfers.)
3. Is confidence calibrated enough, or does this need WP9's category approach
   (exact-key > key-overlap > semantic) instead of a number?
4. Same-as: is `same_as_candidate` reliably distinguishable from "the same hub" and from
   "unrelated"? This is the first time the deferred same-as concept is measured rather than
   discussed — the memo should say whether it is ready for a model field or still premature.
5. Integration shape: does the proposal belong in the modeler's prompt (steering the delta
   to re-use a name) or as a separate pre-modeling agent with its own ratification file?
   Argue from the measurement, including what a human actually has to see to ratify.
6. HITL: what does the reviewer need in front of them — the existing construct, the new
   concept, the key evidence, and what happens if they say no? Sketch it against real
   proposal counts from the runs.

## 8. Exit criteria

The spike ends when D1–D6 exist or the timebox expires, whichever comes first.

**Honest-failure outcomes, all valid and all cheap because Phase 1 stands alone:**

- *"No mechanism reaches zero false merges."* → Recommend not building the assist. Phase 1
  keeps working with the human answering; the memo records the trap that broke it so the
  question is not re-opened from scratch.
- *"The deterministic key-overlap baseline is as good as the LLM."* → Recommend a
  deterministic-only proposal (cheap, calibrated, no prompt to maintain), which is a smaller
  WP than Phase 2 was scoped as.
- *"It works, but only with declared keys and comments."* → Recommend it as a
  grounding-gated assist, inert otherwise — the ADR-0004 pattern this repo already uses.

A result that cannot distinguish these is not a result; the memo says what is missing.

## 9. Constraints

- Repo conventions bind (CLAUDE.md); scorers/datasets follow the WP6 patterns exactly.
- All LLM calls through `ForcedToolCaller`; **measure on Sonnet-tier before reaching for
  Opus** (the mapping spike's rule, and it held).
- Anonymised dataset content only.
- The test suite, ruff and mypy stay green; prototype code lives outside `src/` and the
  mypy scope, and is deleted at the end.
- Read the traces rather than re-running to diagnose (the 2026-07-28 method note, which
  paid off twice during WP23).

## 10. References

- `incremental-extension-charter.md` §3.5 (the task), §4 (phasing, the trap list this
  charter expands), §2 (extensions vs migrations — why a false merge is the cardinal sin)
- `spike-mapping-charter.md` / `spike-mapping-results.md` — the protocol template and the
  precedent that a spike's scorers survive while its prototypes do not
- ADR-0008 (assist-level mapping, evidence trail, degraded mode), ADR-0006 (ratification is
  the checkpoint), ADR-0007 (the agent proposes, a human ratifies)
- WP23 (`wp23-incremental-extension-spec.md`) — the merge and gate machinery this feeds,
  and `render_extension_prompt_section`, which already builds the inventory a resolver needs
