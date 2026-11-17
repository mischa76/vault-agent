---
type: spec
status: not-measured
updated: 2026-11-17
---

# WP141 — The workbench's buttons follow a written rule: four kinds, and what each is for (C45)

Status: **Approved and in progress** (2026-11-17, on the owner's go of that day: all open workbench-usability
candidates, bundled into work packages) · Owner: Mischa Eismann · Author: Claude. Candidate C45; the first of
four packages (WP142: C52 and C51, WP143: C49, WP144: C53 option (a)), first because its rule governs how the
others' controls look.

## 1 What is wrong

Read in the code and on the page (C45, 2026-11-05; unchanged since): `components/ui.tsx` has three button
kinds and their use implies a rule that is written nowhere. The three „attach" controls of the Inputs section
are no `Button` — a hand-written `<label>` with a grey border, one step below the quietest kind — and sink
among the file rows. The per-file and per-run `delete` are bordered grey though they destroy. `danger`
(#e06c5b) and the accent (#d97757) are 7° of hue apart: delete reads as orange too. And the sidebar's „+" is
a second filled button beside every perspective's own.

## 2 The rule

Four kinds, owned by `components/ui.tsx` (`BUTTON_KINDS`); every `Button` carries its kind as `data-kind`.

| kind | look | for |
|---|---|---|
| `primary` | filled accent | the one step that moves the project forward — **at most one per perspective** (run the generator, open the checkpoint, ratify or accept, continue) |
| `add` | accent outline and text | an action that adds something to the project and destroys nothing: attach, read the catalogue, make a profile, infer keys, save settings, record without accepting, parse, create a project |
| `danger` | red outline and text | everything that destroys or abandons, **at every size**: delete a project, a file, a run; discard; cancel |
| `ghost` | grey outline | navigation and toggles |

1. **The attach controls are buttons of kind `add`** — `FileButton`, the same look through the same table, a
   leading „+", the hidden file input and its `aria-label` as before.
2. **Every delete is `danger`**, the small per-file and per-run ones included (`size="sm"`).
3. **`danger` gets a hue of its own.** `--color-bad` becomes #f2647a: 24° from the accent where it was 7°,
   contrast 5.6, 5.1 and 4.6 against the three surfaces it stands on (#e06c5b: 5.3, 4.8, 4.4). The token is
   the error colour everywhere — notes, pills, the failed dot — so they move with it.
4. **The sidebar's „+" is `add`**: creating a project adds; the perspective keeps the one filled button.

**Unchanged.** What every control does, its accessible name and role. The small tool buttons of the diagram
tiles, the log's filters and the model's area chooser are toggles — ghost by the rule, left as they are. The
checkpoint's checkboxes are WP142.

## 3 Not built

No icon set (a „+" is a character). No light theme. No restyling of tabs, pills or inputs.

## 4 Acceptance (Vitest, committed red)

`Buttons.test.tsx`:
- **G1** Project: the three attach controls are kind `add` and still upload through the input found by its
  label; every `delete file`, `delete run` and `delete project` is `danger`; exactly one `primary` („Run the
  generator").
- **G2** Source: read catalogue, make profile, infer keys are `add`.
- **G3** Review: one `primary` at each phase; „Discard the run" `danger`; „Record without accepting" `add`.
- **G4** Run: paused — one `primary` („Open the checkpoint"); running — none, „Cancel the run" `danger`;
  interrupted — „Continue the run" `primary`, „Discard the run" `danger`.
- **G5** the palette: `--color-bad` at least 20° of hue from `--color-accent`, and at least 4.5 : 1 against
  `--color-bg`, `--color-pane` and `--color-pane-2`.
- **G6** every existing Vitest case unchanged and green.

## 5 Pre-registration

- **P1** G1–G5 red before, green after; G6. `tsc`, the build; the Python suite untouched.
- **P2** the Project perspective and a checkpoint in a real browser on stub agents, by screenshot.
- **Not measured:** whether the owner now finds the attach controls at a glance — his to say.
