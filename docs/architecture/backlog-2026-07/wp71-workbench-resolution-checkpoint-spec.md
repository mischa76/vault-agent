---
type: spec
status: not-measured
updated: 2026-10-13
---

# WP71 — Workbench: the resolution checkpoint, shown and answered as the CLI does

Status: **Approved and in progress** (2026-10-13, the owner's go for WP71, after the demo
rehearsal's finding of the same day) · Owner: Mischa Eismann · Author: Claude. Closes the gap
`docs/log.md` 2026-10-13 „Finding — the workbench is blind to the resolution checkpoint“
records. No agent, gate or prompt changes; the CLI's predicate and appliers are reused, never
re-implemented; the suite stays keyless.

## 1 The finding, in one paragraph

A grounded run pauses twice: at the WP29/WP34 resolution checkpoint before the modeler
(entity resolutions, link proposals, key licenses) and at sign-off. `ResolutionCheckpointAgent`
interrupts with `checkpoint: "resolution"`; the CLI tells the pauses apart with
`_paused_at_resolution(state)` and its interactive loop answers both in one session. The
workbench showed the sign-off queue at both pauses, listed nothing of what the first one asks,
ratified every proposal through a blanket accept, and dropped the owners typed there.

## 2 The rules

1. **The checkpoint says which it is.** `GET …/checkpoint` carries `phase`: `resolution` or
   `signoff`, from `cli._paused_at_resolution` — the CLI's predicate, not a second one.
2. **At the resolution phase the answer carries what the CLI shows:** `links` — every pending
   proposal from `pending_link_decisions` with its `key` (`proposal_key`), `kind` (`link`,
   `relationship`, `license`), `target` (`_link_target`), `note` (`_link_category_note`) and
   `evidence`; `resolutions` — every pending proposal from `pending_resolution_decisions`
   with `concept`, `label`, `entity`, `claim`, `category`, `confidence`, `evidence`, and the
   four answers the CLI takes (a construct name, `NEW`, `same_as_candidate`, `unresolved`).
   The queue's `items` stay for the disclosures; the frontend hides the owner fields there.
3. **`POST …/checkpoint` takes `links: {key: true|false}`** beside `resolutions`, hands both
   to `_build_decision(..., links=)`, and records `--link key` / `--no-link key` in the CLI
   equivalent. Everything left unanswered is ratified by `accept`, exactly as `--accept`.
4. **`run.json` records which pause a decision answered:** `checkpoints: [{phase, command}]`,
   one entry per resume, beside the unchanged `cli_equivalents`.
5. **The frontend loops as the CLI does.** After a decision the run may pause again; the Run
   tab shows it, the Review tab opens the next phase. The Review tab at `resolution` shows the
   licenses and proposals with build/decline (default build, as the CLI's prompt), the
   resolutions with an answer field, no owner fields, and a line that says sign-off follows
   the modeler. The walk script (`frontend/e2e/walk.mjs`) answers pauses until `finished`.

## 3 Guards before the change

1. On stub agents whose link proposer leaves a `KeyLicense` pending and whose resolution
   checkpoint is the real `ResolutionCheckpointAgent`: the run pauses with `phase`
   `resolution`; `links` names the license's key with kind `license` and a target; `items`
   carries no `contract_owner` decision that the frontend would offer an owner for — or if it
   does, `phase` says not to.
2. `POST {links: {key: false}, accept: true}` resumes; the recorded command ends with
   `--no-link <key> --accept`; the run pauses again with `phase` `signoff`; `run.json`'s
   `checkpoints` lists `resolution` then, after the owner accept, `signoff`, and the run
   finishes.
3. On the plain stub (no proposals) the phase is `signoff` and nothing else changes (the WP66
   guards hold unchanged).

## 4 Pre-registration

The demo rehearsal repeated: the walk on `adventureworks_person` with its schema against
`vault-agent ui` with a real key (≈ 1 USD): the first pause shows `resolution` with 13
licenses, the walk accepts them, the second pause shows `signoff` with 13 owner decisions, the
walk fills and accepts, the run finishes; `run.json` carries two `checkpoints` entries.

## 5 Not in this WP

Editing a license's translation; the `mappings` overrides (`--map`); the chat console
explaining a license (`explain` could, later).

## 6 Results

*(appended after the change)*

**2026-10-13 — built, keyless and rehearsed with a real key.** Guards `e1e7f6c` (red), the
change `6b073c2`, the console and docs `28e184c`, the rest in the commit carrying this line.
Four guards on the stub agents with a pending `KeyLicense` and the real
`ResolutionCheckpointAgent`: phase `resolution` with the license (kind, target, note,
evidence), `--no-link <key> --accept` recorded, the second pause `signoff`, `checkpoints`
`[resolution, signoff]`, the plain stub unchanged; the console names the phase and the license.
Frontend: the Review tab's resolution view (build/decline per proposal, build the default, no
owner fields), the Run tab's phase labels, 15 Vitest tests. **§4, the rehearsal:**
`adventureworks_person` with its schema through `vault-agent ui` (Sonnet 5.5 / Opus 5.5):
pause 1 at 137 s — „Resolution checkpoint — before the modeler“, 13 proposals (all key
licenses, WP41), 0 resolutions, ratified as proposed; the modeler took three attempts; pause 2
at 266 s — „Sign-off checkpoint“, 16 decisions (13 owners, 3 code-generator flags), 2
disclosures, owners filled, accepted; finished at 269 s; 21 calls, 0.94 USD; `run.json`
`checkpoints` `[resolution, signoff]`, the first command `resume --out … --accept`, the second
with the 13 `--owner` flags. 7 hubs / 2 links / 16 satellites; both diagrams rendered (the
input `erDiagram` 5 s after the output one — the walk's screenshot had caught it mid-render).
**Not measured:** declining a license in a real run; an entity resolution at this pause (a
brownfield case — none in the rehearsal).
