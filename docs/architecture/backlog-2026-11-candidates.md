---
type: backlog
status: proposed
updated: 2026-11-05
---

# Backlog candidates of November 2026

Status: **Proposed, not prioritised** (2026-11-05) · Owner: Mischa Eismann · Author: Claude.
Continues `backlog-2026-10-candidates-3.md` (C22–C44, all closed per its status note of 2026-11-05), append-only.
„C" stands for *candidate*: a finding or idea, not yet a work package.

## C45 — The workbench has three button kinds and no rule for when to use which; the „attach" controls do not read as buttons (owner, 2026-11-05)

**Observed by the owner** in the Project perspective, section Inputs: the three controls „attach requirements",
„attach schema", „attach profiling" are not recognisable at a glance as buttons; they disappear among the file rows
above them (mono file names, grey pills, the small bordered `delete` per file). Asked whether a concept governs when
a button looks like „Run the generator" (filled orange), like „delete project" (orange-red text and border) or like
the attach controls (grey border, white text).

**Read in the code (`frontend/src`, 2026-11-05, `1314107`):** `components/ui.tsx` `Button` has three kinds —
`primary` (`bg-accent text-bg`, filled, `--color-accent` #d97757), `danger` (`border-bad text-bad`, `--color-bad`
#e06c5b), `ghost` (`border-line text-ink`, the default text colour). Usage implies a rule — primary for the one action a
perspective exists for (Run the generator), danger for anything that destroys, ghost for the rest — but **it is
written down nowhere** (not in `docs/operations/14-workbench.md`, no ADR, no comment). The attach controls are not
`Button` at all: a hand-written `<label>` around a hidden file input (`perspectives/Project.tsx`, the Inputs
section), `border-line text-sm`, without `font-medium` — visually one step below ghost, and of the same family as
the per-file `delete` buttons and the pills, which is why they sink. Two more things seen on the way: `danger` and
`accent` differ little in hue (#e06c5b vs #d97757), so the owner reads delete as orange too; and the per-file and
per-run `delete` are bordered grey, not `danger`.

**Shape of a WP:** (1) write the rule — one short paragraph in the workbench chapter: primary at most once per
perspective, the step that moves the project forward; danger for every destructive action, at every size; a
secondary kind for actions that add something (attach, parse, record); ghost for navigation and toggles; (2) give
the attach controls that secondary look — e.g. accent outline or `accent-soft` fill, with an icon or „+" — through
`Button` (it needs an `as="label"` or a file-input variant so the hidden input keeps working); (3) decide whether
`danger` gets a hue clearly apart from the accent; (4) the per-file/per-run `delete` follow the rule. Guard first:
the existing `Project.test.tsx` queries by role and name (`getByRole("button", …)`); the attach controls are found
by `aria-label` on the input, which must survive the change.
