---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP116 — A translation is ratified once per key: the per-construct translation flags become disclosures under one decision per translated key (C42)

Status: **Approved and in progress** (2026-10-31, the owner's choice of the first of three ways after the C1
finding) · Owner: Mischa Eismann · Author: Claude. Opened by the finding of 2026-10-31 (`docs/log.md`, „the C1
experiment's 55 extra review decisions are translation decisions"); C42 in candidates part 3.

## 1 What is wrong

ADR-0013 §3 made every translated link „its own review class", WP38 did the same for a translated satellite feed, and
WP43 kept both **individual and decisions** („translations — not in a group, ADR-0013 §3 — stay individual"). Each
`link_translation` and `sat_translation` flag is one decision at sign-off: *review the translation model*. But the
translation they report has already been decided: the gates `E_LINK_TRANSLATION_UNRATIFIED` and
`E_SAT_TRANSLATION_UNRATIFIED` refuse any translation that no ratified link proposal, key licence or subtype feed
produced, so every flag that reaches the sign-off stands under a ratification given at the resolution checkpoint.
What the reviewer is then asked, construct by construct, is the same question: *is `hub_product` keyed on
`ProductNumber`, and is the join through `Product` the way to reach it?* On the C1 experiment's drafted arm that
question was asked 60 times for 21 relations — `Product` alone eight times on the production step, six links and two
satellites, every one `ProductID → ProductNumber` — and the 60 were the whole of the arm's „60 % more review". The
authored arm carried 4; without this class the arms tie (87 against 86).

## 2 The rules

1. **One key, one decision.** The unit a human ratifies is the *translated key*: the hub, the relation the join goes
   through and the natural key it projects — `translation_key(t, hub)` in `rules/dv2_rules.py`, the one helper, built
   from the typed `KeyTranslation` and the hub's name (never from a message). At sign-off the review queue carries
   **one decision per key** that this run's constructs translate to: a `review_flag` item whose asset is the key,
   whose summary says how many constructs join through which relation to read which key, and whose detail lists
   them. The per-construct `link_translation` and `sat_translation` flags **become disclosures** under it, grouped
   by the key (`translation:<key>`), collapsing above `AGGREGATE_THRESHOLD` to one line that names the key — the
   WP5 aggregation WP43 withheld from them, now keyed so nothing of a different key folds together.
2. **The flag carries its key, typed.** Every site that raises one of the two kinds — the proposer's translated
   proposal, a relationship table's translated participation, a link and a satellite repaired under a key licence
   (WP40), a subtype feed's satellite (WP38) — passes `reason=translation_key(t, hub)`; `VaultAgentState.flag`
   gains the `reason` keyword `PipelineFlag` already has (WP47's typed reason). The role follows the typed fields:
   a translation flag **with** a key is a disclosure; one **without** (a flag an older state persisted, or a
   caller that forgot) stays a decision — the conservative default WP43 chose, so a key the code did not name is
   never hidden. The per-key decisions are synthesised from the flags' keys in `assemble_review_queue`, in first
   appearance order; a run without translations has none, byte-identically.
3. **The gates are untouched.** What makes the flags disclosures is that the two gates already refuse an
   unratified translation; nothing about ratification moves. The decision at sign-off is the confirmation of the
   generated translation model, once per key, which is what a reviewer reads once.
4. **The record is re-read, not re-seeded.** `review_decisions` of a future chain counts per key. Of the recorded
   chains only the second 5.5 generation's two carry translation decisions (the seven before WP79 never did, WP104's
   split); the rule is a deterministic transformation of their kept queues — decisions minus translation flags plus
   distinct keys per step — so their samples are re-read under it (the measured values kept in the comment, the
   method named), and the generation stays one: a new generation would throw away the two samples for a change
   that can be computed. The 4.8 record is untouched.
5. **Records.** A dated note appended to ADR-0013 (§3's „its own review class" holds for the *disclosure*, not for a
   decision per construct) and to WP43's spec (the amendment of 2026-10-03 is superseded for the translation kinds);
   manual 7's two „never aggregated" sentences, the flag catalogue's two entries, the methodology cheatsheet where it
   lists the kinds.

## 3 Acceptance (keyless)

`tests/test_wp116_translation_per_key.py`, red before the change: the helper's format; the WP36 ratified state's
flag carrying the key as reason and the queue holding one per-key decision for it; a constructed state with five
translation flags over two keys yielding two decisions and five disclosures, the larger group collapsing to a line
that names the key; a translation flag without a reason still a decision (WP43's mixed state unchanged, its guard
untouched); every raise site of the two kinds in `src/` passing `reason=` (a source guard, the invariant „the code
owns every count"); the Markdown layout showing the per-key decision with its constructs; the record's two samples
re-read. Every byte-identity fixture unchanged (no fixture carries a translation flag).

## 4 Pre-registration

- **P1 — keyless.** Guards green; fixtures byte-identical; suite, ruff, bare mypy, tsc, vitest green.
- **P2 — the kept queues, re-counted under the rule** (decisions − translation flags + distinct keys per step, keys
  as (hub, through relation) read from the queue text — a re-assembly is not possible, the eval keeps no state):
  the drafted arm **146 → 119** (keys 6, 4, 10, 3, 10), the twenty-second (authored control) **91 → 90**
  (step 5: 4 flags, 3 keys), the twenty-third **95 → 94** (likewise). Falsified by any other number from the same
  files; the per-step figures are recorded either way.
- **P3 — the gap the finding named closes.** Under the rule the two arms of the C1 experiment stand 90 against 119:
  the draft's remaining surplus is 29 decisions, all of them per-key translation confirmations the authored arm did
  not need because its prose kept the surrogates. That number, not 60 %, is the review cost of the draft's keys.

## 5 Not in scope

Moving the decision to the resolution checkpoint (the licence is already ratified there; the per-key sign-off
confirmation is kept on purpose, it is where the generated model exists); any change to the translation models or
the gates; the drafted-requirements command (ADR-0019 is judged after this on corrected numbers); re-reading the 4.8
record or the first 5.5 generation (no translation decisions there).

## 6 Measured (2026-10-31, keyless)

- **P1 ✔.** Eight guards red before the change (`826d58e`, red at import), green after; suite 1567 passed, 5 skipped;
  ruff; bare mypy; no fixture changed (none carries a translation flag). Two guards updated deliberately: WP104's
  record guard (the twenty-second's sample 91 → 90) and nothing else — WP43's mixed state keeps its key-less
  translation flag a decision, as rule 2 says.
- **P2 ✔ with one number corrected.** Re-counted from the kept queues under the stated method (decisions − translation
  flags + distinct keys per step, a key = hub and relation joined through): the twenty-second **91 → 90** and the
  twenty-third **95 → 94** as predicted (step 5: 4 flags on `hub_currency_rate`, `hub_customer`, `hub_sales_order`);
  the drafted arm **146 → 118**, not 119 — the pre-registration's per-step keys (6, 4, 10, 3, 10) came from a looser
  shape that counted a satellite's and a link's flag for one key twice on two steps and merged two keys on another;
  under the method as written the keys are 4, 2, 8, 6, 12 = 32. The per-step decisions of the drafted arm under the
  rule: 19, 10, 35, 15, 39.
- **P3 ✔.** The C1 arms under the rule: **90 against 118**, a surplus of 28 — all of it per-key confirmations of the
  natural keys the authored arm's prose did not keep. That is the draft's review cost: 28 decisions on five steps,
  not „60 % more review".

Open after WP116: the per-key decision has no answer slot of its own (it is confirmed by `--accept` like any
decision); a `--confirm-translation KEY` would be WP82-parity work if a reviewer ever needs to decline one.
