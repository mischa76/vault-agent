---
type: spec
status: not-measured
updated: 2026-11-17
---

# WP142 — The checkpoint's decision controls: two named answers side by side, and a resolution answer one can read (C52, C51)

Status: **Approved and in progress** (2026-11-17, on the owner's go of that day: all open workbench-usability
candidates) · Owner: Mischa Eismann · Author: Claude. Candidates C52 and C51 — one question, as both say: a
small set of decision controls for the checkpoint. Second of four packages (WP141 before, WP143 and WP144 after).

## 1 What is wrong

- **C52.** A link proposal, a key licence, an inferred key and a bridge path are each a checkbox with one
  word beside it, and the word is the current answer: „decline" beside an empty box reads as „tick to
  decline". Found by the owner on the bridges (2026-11-07); WP140 added a third use of the pattern.
- **C51.** An entity resolution is answered in a free-text field with a suggestion list. Keeping the
  proposal is the empty field and stands in no list; another existing hub is a name to type; the three
  listed values (`NEW`, `same_as_candidate`, `unresolved`) are the CLI's tokens in two spellings. The API
  says what was proposed only as a sentence (`claim`), and does not say which hubs exist.

## 2 The rules

1. **A yes/no decision is a segmented control** — `Choice` in `components/ui.tsx`, a radio group of two
   named answers, both always visible, the chosen one filled, the default first: `[ Build | Decline ]` for a
   link or a relationship table, `[ Allow | Decline ]` for a key licence, `[ Decline | Allow ]` for an
   inferred key, `[ Decline | Build ]` for a bridge path. C52's first option, the one it prefers. What is
   sent is what was sent: an answer for a control someone used, nothing for one left alone.
2. **A resolution is answered from a list in plain words**, the proposal first and preselected:
   „Keep the proposal — is `<hub>`" (or „— same as `<hub>`, keyed differently"), „New hub", „Leave
   unresolved", and under „Another existing hub" every hub of the vault being extended. The machine value
   is what is sent and what the run's CLI equivalent shows (`--resolve`); the page does not show it.
3. **The API says what the page needs as fields:** a pending resolution carries `proposed` (the construct,
   or `same_as_candidate`) and `same_as`; the checkpoint carries `hubs`, the hubs of the existing vault —
   the only constructs the applier takes as an answer (`_apply_resolution_decision`).

**Not offered in the list:** `same_as_candidate` as an answer of its own. Where the proposal is a same-as,
keeping it is that answer; chosen against a merge proposal it would assert an equivalence to no named
construct (the applier keeps `same_as` as it was, empty). The CLI still takes it.

**No default by confidence** (the owner's question in C51): keeping the proposal is the agent's answer
already; a default that moved with the confidence would be a second decision rule in the page (ADR-0014).
No hint below a threshold either — a threshold would be a number nobody has set.

**Unchanged.** The decision the API takes, the bulk answer, every other field of the perspective.

## 3 Not built

- **The section „Unresolved concepts (entity resolution)"** is left as it is, and is not what its title
  says: its entries are the multi-source *mapping* concepts (`cli._multi_source_unresolved`), and its field
  sends an entity-resolution answer for a concept that is no resolution proposal — which the applier drops
  without a word. Read in the code while specifying this, not measured by a run. Giving a field that
  does nothing a better control would be polish on a dead end: candidate C78.
- The contested hub keys (WP126) and the stage bindings (WP82) keep their controls.
- The bridge paths get the segmented control here, one per path; WP144 groups them.

## 4 Acceptance (committed red)

- **G1** (Vitest) a declared licence is a radio group „decision for `<key>`" with „Allow" chosen; choosing
  „Decline" sends `links: {key: false}`; no checkbox with a state word is left for it.
- **G2** (Vitest) an inferred key's group has „Decline" chosen and first; left alone nothing is sent for it;
  „Allow" sends `true` — WP140's two cases, on the new control.
- **G3** (Vitest) a bridge path's group has „Decline" chosen; „Build" sends `bridges: {path: true}`.
- **G4** (Vitest) a merge proposal's select shows „Keep the proposal — is hub_business_entity" selected and
  offers „New hub", „Leave unresolved" and the other hubs; left alone no resolution is sent; „New hub"
  sends `NEW`; another hub sends its name. A same-as proposal's first entry names the candidate.
- **G5** (Python) the pending resolutions carry `proposed` and `same_as`; the hubs of the existing vault are
  listed, none without one.
- **G6** every other Vitest case and the Python suite unchanged and green.

## 5 Pre-registration

- **P1** G1–G5 red before, green after; G6; `tsc`, the build, ruff, bare mypy, UI coverage.
- **P2** a resolution checkpoint with a licence and an inferred key in a real browser on stub agents, by
  screenshot. A checkpoint with a pending entity resolution or a bridge needs an existing vault and a
  model — shown in the browser only if a stub state can carry them; otherwise Vitest only, and said so.

## 6 Measured (2026-11-17)

- **P1 held, with one case that was never red.** Four Vitest cases red at `ecfb0be` (three rewritten
  deliberately onto the new control, the resolution list), green with the change; the fifth new case — what
  is sent for a resolution left alone or answered — passed before as well and is a pin, as the commit said.
  Two Python guards red by import, green. Vitest 54, suite 1867 passed / 3 skipped with no key reachable,
  `tsc`, the build, ruff, bare mypy; `vault_agent.ui` coverage 95 %.
- **P2 done, all of it.** A stub state could carry an existing vault, two pending resolutions and a model
  whose links cite one requirement (`serve_stub2.py`, `canned.py` in the evidence folder; orchestrator, link
  proposer and both checkpoints real, no model call). In a real Chromium: no checkbox left on the resolution
  checkpoint; the declared licences `Allow ✓ / Decline`, the inferred key `Decline ✓ / Allow`; the merge
  proposal's list „Keep the proposal — is hub_business_entity" selected, then „New hub", „Leave unresolved",
  `hub_person`, `hub_vendor`; the same-as proposal's first entry naming `hub_person`. One inferred key
  allowed and one resolution answered with another hub: the run recorded `resume … --resolve
  contact::contactid=hub_vendor --link Routing.ProductID --accept`. At sign-off five bridge paths, each
  `Decline ✓ / Build`.
- **Changed after the first screenshot:** the answer not chosen was drawn in the faintest text colour and
  read as disabled; it is the dim one now.
- **Not measured.** A real extension run with a real resolver's proposals on the page.
