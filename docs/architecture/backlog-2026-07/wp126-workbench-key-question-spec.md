---
type: spec
status: keyless-only
updated: 2026-11-14
---

# WP126 — The workbench asks the contested hub keys at the resolution checkpoint (C63, ADR-0021)

Status: **Built** (2026-11-14, on the owner's go on the proposal as presented) · Owner: Mischa Eismann · Author:
Claude. Candidate C63; WP125 built the rule, the API's fields and the CLI's question.

## 1 What is missing

Since WP125 a run pauses at the resolution checkpoint for a contested hub key and the API shows and takes it
(`keys`). The Review page did not: a run paused for a key alone showed an empty checkpoint, and its one button took
the default without the reviewer having seen the question.

## 2 The rules

1. At the resolution phase the page lists every contested key in its own section: the table, a selection whose first
   and pre-selected option is the declared natural key, the other declared natural keys, the technical primary key
   named as such, and the evidence lines the CLI prints. The header counts the hub keys beside the proposals and
   resolutions.
2. Only a named answer is sent (`keys: {Table: {columns, reason}}`); a key left at its default sends nothing — the
   pipeline takes the declared natural key for whatever is unanswered (WP125).
3. Selecting the technical primary key opens a reason field; the button that continues the run is disabled, and the
   field says why, until a reason is given. No path on the page keys a hub on the technical key without one.
4. A composite key is answered in the terminal (`resume --key "Table=A+B"`); the page says so.
5. Nothing at sign-off: the key is decided before the modeler.

## 3 Measured (2026-11-14, keyless)

- Three Vitest guards (`frontend/src/Review.test.tsx`, „contested hub keys (WP126)"). **Written with the change,
  not before it**; shown red against the previous page afterwards — two of the three fail there (the third pins
  that sign-off shows no key section, which holds either way). `npm run check`, `npm test` (43 passed),
  `npm run build` green.
- **In a real browser against the real API, stub agents, no model call:** a run paused for `AddressType` alone; the
  page showed „1 hub keys", `Name` pre-selected and the three evidence lines; with `AddressTypeID` selected the
  button was disabled until the reason was typed; the answer reached the pipeline as
  `resume … --key AddressType=AddressTypeID --key-reason 'AddressType=the name is renamed yearly' --accept` (the
  run's recorded CLI equivalent) and the run went on to sign-off with no key pending.
- **Not measured:** the page on a run of the real agents; several contested keys at once in the browser (the unit
  guards and the API take a map); a small viewport.
