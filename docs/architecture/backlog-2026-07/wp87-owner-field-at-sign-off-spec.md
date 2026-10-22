---
type: spec
status: not-measured
updated: 2026-10-23
---

# WP87 — The owner field at sign-off: a bare email is accepted and stored as name and address; what is wrong is said at the field (C9)

Status: **Approved and in progress** (2026-10-23, owner: „zieh C9 und C5 vor") · Owner: Mischa Eismann · Author:
Claude. Backlog C9, from the owner's run of 2026-10-21.

## 1 What is wrong

The owner typed a bare email (`john.doe@acme.com`) into every contract's owner field. The workbench disabled
„Accept" because it requires a `<` — and said why only in the button's tooltip; the owner pressed „Record without
accepting", which finished the run as nothing blocked. The CLI's `_parse_owner` stores a bare email as the *name*
with `email: null` — 13 contracts ended like that (log, 2026-10-21/22).

## 2 The rules

1. **One parser, CLI and workbench** (`cli._parse_owner`): `Name <email>` as today; a bare address
   (`local@domain`, no `<…>`) is the email, and its local part is the name (`john.doe@acme.com` → name `john.doe`,
   email `john.doe@acme.com`); anything else without `<…>` stays a name without email, as today.
2. **The workbench accepts what the parser accepts** as a filled owner: `Name <email>` or a bare address. An owner
   that is neither shows a message *under the field* — „Name <email> or an email address" — not only a tooltip.
3. „Record without accepting" says on the button what it does when nothing blocks: the run finishes.

## 3 Acceptance (keyless)

`tests/test_wp87_owner_parse.py` (the parser, both shapes and the unchanged ones) and
`frontend/src/Review.test.tsx` (accept enabled with a bare address; the inline message for an invalid entry).
