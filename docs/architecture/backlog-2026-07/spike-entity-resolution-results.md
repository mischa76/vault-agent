# Spike results — entity resolution against an existing vault (brownfield Phase 2)

Status: Complete (2026-07-29) · Charter: `spike-entity-resolution-charter.md` ·
Recommendation: **build it, LLM-first, grounding-gated** (D6, §6) — for Mischa to accept

## 1. What was measured

Two mechanisms on the same golden set (`eval/datasets/brownfield_resolution/`, D1: an
existing bank vault + a DACH contract/CRM source carrying all four trap classes), 5 repeats
each, `claude-sonnet-4-6` per charter §9. Scorers D2 (`eval/scorers.py`, keyless-tested,
they survive this spike).

| | A: deterministic-first | **B: LLM-first** | B, comments stripped | B, names masked |
|---|---|---|---|---|
| **false_merge_rate** (primary) | **1.000** | **1.000** | **1.000** | **1.000** |
| resolution_accuracy | 0.667 | **1.000** | 0.667 | 0.567 |
| new_hub_detection | 1.000 | **1.000** | 1.000 | 0.750 |
| resolution_calibration | 0.054 | 1.000 | 0.270 | 0.383 |
| tokens in/out per run | 606 / 724 | 686 / 986 | 1639 / 1355 | 1698 / 1101 |
| wall per run | 13.1 s | 15.7 s | 20.5 s | 18.5 s |

Zero variance across repeats in every configuration except the masked probe (accuracy
0.500–0.667). One LLM call per run in both variants.

## 2. The answer to the question that mattered

**Both mechanisms produced zero false merges, in every configuration, across 25 runs.**
That is the charter's primary requirement and it is met with room to spare.

More important than the clean number is *how* variant B behaves when the ground is taken
away. Blinded — physical names replaced by `TBL_01`/`COL_01_02`, every comment stripped, so
only types and structure survive — it answers:

```
partner          -> unresolved         conf=0.35
vertragspartner  -> unresolved         conf=0.35
kontakt          -> NEW                conf=0.85
crm_kunde        -> same_as_candidate  conf=0.65
konto            -> hub_account        conf=0.82   (correct)
vertrag          -> NEW                conf=0.90
```

It stops answering exactly where it can no longer know, and says so with a confidence that
*drops to 0.35* while staying high where structure alone still decides. The calibration
margin **rises** under degradation (0.054 → 0.270 → 0.383), which is the opposite of the
failure mode the charter was built to catch: confidence starts doing work precisely when
accuracy stops. This is the honest-degradation property, demonstrated rather than assumed.

## 3. Answers to the charter's §7 questions

**1. Zero false merges?** Yes, 25/25 runs. The evidence trail is also genuinely reviewable —
B cites the fact it decided on ("`vp_nummer` is explicitly noted as *nicht identisch mit der
Kundennummer*"), not a restatement of its conclusion. A reviewer can check each claim against
the schema without re-deriving the judgement.

**2. Which mechanism, at what cost?** B, at +13% input and +36% output tokens over A —
roughly a tenth of a cent per run at this size. A's accuracy of 0.667 is *not* evidence that
deterministic-first is unworkable: A failed on `partner` and `konto` because its
cross-reference heuristic fired on any small table whose comment mentions an existing key,
which caught the real xref table *and* the customer table itself. That is a prototype flaw I
could tune. The reason not to is different and worth stating plainly: **B needed no tuning at
all**, and every heuristic A would need is a rule someone has to maintain against source
systems nobody has seen yet. Note that A's flaw failed *safe* — it over-produced same-as
candidates rather than merging — which is a property a deterministic layer would keep.

**3. Is confidence calibrated?** Yes, on this set, and better than WP9's mapping confidence
was. But see §4: a category (`exact_key` > `key_overlap` > `comment_grounded` > `semantic`)
should still be derived deterministically from the evidence, as WP9 §7 settled, because the
number is self-reported and the category is not. B reported `semantic` for everything,
including the exact-key cases — the model does not classify its own evidence reliably even
when the evidence itself is right.

**4. Same-as: distinguishable?** Yes, and this is the spike's most useful secondary finding.
B identified the same-as candidate in 5/5 clean runs and **still identified it when blinded**
(conf 0.65), separating "asserted equivalent on a different key" from both "the same hub" and
"unrelated". The twice-deferred same-as concept is ready to become a model field.

**5. Integration shape.** A separate pre-modeling step with its own ratification, not a
modeler prompt section. Three reasons from the measurement: the resolution must be ratified
*before* the delta is modelled (once the modeler has named a construct, WP23's `merge_models`
folds it by name and the decision is already made); the evidence trail is what a human
ratifies and it does not survive being compressed into a steering line; and the blinded probe
shows the mechanism needs to be able to return `unresolved`, which a prompt section cannot
express — the modeler would have to guess anyway.

**6. HITL.** Per proposal the reviewer needs: the new concept and its key, the proposed
existing construct, the evidence lines, and the consequence of accepting (keys from this
source enter that hub). Six proposals is a comfortable CLI list; a real landscape produces
tens, so this belongs in the ratification-file pattern WP9 already established
(`mappings.review.yml` → `resolutions.review.yml`), with `--resolve "concept=hub_name"` as
the single-item shortcut.

## 4. What this spike does NOT establish

Stated plainly, because the numbers are clean enough to be over-read:

- **One case, six concepts.** The mapping spike measured 30+ concepts on a deliberately
  cryptic real-shaped schema. This set is small; 1.000 on six concepts is a strong signal,
  not a proof. Before this ships, the golden set should grow — ideally on
  `messy_insurance`'s VICTOR schema, which already exists and is nastier.
- **The golden set and the prompt were written in the same session, by me.** That is a real
  confound: the traps may be ones the prompt implicitly anticipates. The blinded probe
  mitigates it (the prompt cannot lean on names it cannot see) but does not remove it. An
  independently-authored trap — ideally one Mischa writes from a real project — would.
- ~~**Zero false merges on four traps is not zero false merges.** The mechanism was never
  offered the hardest case.~~ **Addressed the same day — see §6a.** The trap now exists and
  the mechanism declines on it 5/5. The criticism stands for everything else in this list.
- **Sonnet-tier sufficed**, and no Opus comparison was run. That is per charter §9 and not a
  gap, but it means "Opus would do better" is unmeasured.

## 5. Cost

25 LLM calls total, one per run, ~$0.30 for the whole spike including the degraded probes.
The mechanism is cheap enough that cost is not an argument in either direction.

## 6. Recommendation (D6)

**Build it: LLM-first, one forced-tool call, deterministic post-validation, grounding-gated
and inert without a declared schema** — the ADR-0004/WP9 pattern this repo already uses. As a
pre-modeling step with its own ratification file, not a modeler prompt section (§3.5).

Four conditions I would put on the WP rather than leave to the implementer:

1. **The category is derived, not reported.** `exact_key` when the concept's key normalises
   to the existing business key; `key_overlap` when a cross-reference asserts it;
   `comment_grounded` when the deciding evidence is a documented comment; `semantic`
   otherwise. B's self-reported category was wrong on every exact-key case even where its
   answer was right.
2. **Post-validation keeps the WP9 safety property**, which this prototype already
   implements: a resolution naming a construct that does not exist becomes `unresolved` with
   the violation in the evidence — never a silent drop, never an invented hub.
3. **Same-as becomes a first-class output**, per charter §3.5: two hubs plus a flagged
   candidate. The spike shows it is reliably distinguishable, so the deferral can end.
4. **Grow the golden set first** (§4). The WP should not be scoped on six concepts.

If any of that looks like more than the problem is worth, the honest alternative remains
available and cheap: Phase 1 works today with the human answering, and this spike's cost was
one afternoon and thirty cents.

## 6a. Addendum (2026-07-29, same day): the undecidable trap, measured

§4 said the mechanism "was never offered the hardest case". That trap now exists
(`altbestand`: a legacy migration register whose key is documented as having the *same
format* as the national customer ID, with no cross-reference table and nothing that
establishes whether the populations overlap — the only correct answer is `unresolved`), and
it has been measured. 5 repeats clean, 5 blinded.

| | clean | blinded |
|---|---|---|
| false_merge_rate | **1.000** | **1.000** |
| resolution_accuracy | 1.000 | 0.486 |
| **trap 5 answer** | **`unresolved` 5/5** (conf 0.30–0.80) | `NEW` 5/5 (conf 0.88) |

**Clean: it declines, and says why.** Its evidence names the exact reason — *"format
resembles a customer number but is not confirmed to be one … no explicit cross-reference is
provided … merging risks injecting legacy keys into live history … a data lineage review or
explicit key mapping is required"*. That is the behaviour the whole charter was written
around, on the one trap designed to defeat it. WP29's acceptance #2 is met.

**A methodological confound, found and controlled.** The first probe of this trap used a
prompt carrying a sentence I had added — *"a key that merely LOOKS like an existing key is
not evidence…"* — which describes trap 5 almost verbatim. That is teaching to the test, and
exactly the confound §4 warned about. Re-measured with that sentence removed (the prompt the
spike actually ran): **identical result, `unresolved` 5/5.** The confound was real and did
not carry the result; recorded because the check is the point, not the outcome.

**Blinded, trap 5 flips to `NEW` at confidence 0.88 — and the honest reading is that the
blinded probe cannot test this trap.** Trap 5's entire difficulty lives in the comment
("Format wie die Kundennummer"); strip it and the table becomes an ordinary unrelated
relation, for which `NEW` is a reasonable inference from what remains visible. So the score
on that concept should be excluded rather than read as a failure. What DOES survive as a
genuine weakness: the confidence is **0.88 on an answer the golden calls wrong**, where the
other blinded concepts correctly dropped to 0.35. Blinded, the mechanism is not uniformly
honest — it is honest where it can *see* that it lacks evidence, and confident where the
evidence for its own uncertainty was what got removed. That is a limit of confidence as a
signal, not of this mechanism, and WP29 should not lean on the number alone.

Direction matters here: the wrong answer was `NEW`, not a merge. `false_merge_rate` held at
1.000 in all 10 runs. The failure mode costs a redundant hub someone deletes, which is the
charter's tolerable side of the asymmetry — but a reviewer is less likely to scrutinise it at
0.88 confidence, and the memo would rather say that than round it off.

## 7. Surviving assets

- `eval/datasets/brownfield_resolution/` — golden set with the four traps (D1)
- `eval/resolution.py` + four scorers in `eval/scorers.py`, 15 keyless tests (D2)
- `eval/results/spike_resolution/*.json` — the raw runs behind §1 (D4)
- `spike/resolve.py` — **throwaway**, deleted with this commit per charter §3
