---
type: spec
status: not-measured
updated: 2026-10-09
---

# WP56 — A relation-less satellite whose attributes name exactly one declared table reads that table

Status: **Approved and in progress** (2026-10-09, user: „Dann bauen wir doch zunächst die
Relationsableitung und lassen im Anschluss die zehnte Kette laufen“) · Owner: Mischa Eismann ·
Author: Claude. Touches the modeler's parser (`_parse`, the WP55 collapse and the hub-parent path)
and `rules/`. A **backstop** with telemetry, like WP55; no prompt change, no model call.

## 1 Problem, measured

Ninth chain, `20261008T005807208141Z`, step 1 attempt 1 (`docs/log.md` 2026-10-08): WP55
collapsed two one-hub links on `hub_person`, but their satellites declared no `source_table`, so
the rule's conservative half dropped them — `sat_email_address_detail` (EmailAddress,
ModifiedDate) and `sat_credential_status` (ModifiedDate). The payload came back only because an
unrelated gate forced attempt 2. The conservative half was right not to **guess**: a satellite
moved to `hub_person` without a relation would read `Person`, which carries no e-mail column. But
one of the two was not a guess: `EmailAddress` is a column of exactly one declared table of the
increment. A relation that the attributes determine is not inferred from words; it is read from
the schema.

## 2 The rule

**A satellite without a `source_table` whose attributes are all columns of exactly one declared
table of this increment reads that table.**

1. `rules.infer_satellite_relation(satellite, tables) -> str | None`: the declared table (name
   as declared) such that every attribute of the satellite — and its `child_dependent_key`, if
   any — is one of its columns, compared through `normalize_identifier`; `None` when no table or
   more than one qualifies, or the satellite has no attributes. `ModifiedDate` alone qualifies
   every table and so infers nothing — `sat_credential_status` stays dropped, as it should: the
   modeler itself said it deliberately carried nothing but a timestamp.
2. In the WP55 collapse: a relation-less satellite on a one-hub link gets the inferred relation
   and moves to the hub; with no inference it is dropped as before. The `link_collapsed` flag
   says the relation was inferred.
3. On a **hub** parent: a relation-less satellite whose inferred relation exists and is **not**
   the hub's own (its `source_entity`, or any of its `sources`) gets that `source_table`. The
   same table as the hub's stays implicit — so every existing model and fixture renders
   byte-identically — and a satellite on a link is not touched (its relation is the link's
   offer, WP42). Effectivity satellites are excluded (their `source_table` is ignored anyway).
4. Each inference is a `relation_inferred` flag on the satellite (new
   `FlagKind.RELATION_INFERRED`, a **disclosure**: the schema, not a guess, named the table) and
   one `satellite_relation_inferred` backstop event with the satellite, the table and the path
   (`collapse` or `hub`). The key gates judge the satellite afresh on its relation, as always.

## 3 Guards before the change

1. `infer_satellite_relation` on the person step's declared tables: (EmailAddress, ModifiedDate)
   → `EmailAddress`; (ModifiedDate) → None; (EmailAddress, PasswordHash) → None; a CDK is counted.
2. The ninth chain's step-1 attempt-1 records: `sat_email_address_detail` moves to `hub_person`
   with `source_table = EmailAddress` (`link_collapsed` and `relation_inferred`, no
   `dropped_record`); `sat_credential_status` is dropped as before; the backstop event names the
   satellite, the table and `collapse`.
3. A relation-less satellite on `hub_person` with attributes (EmailAddress, ModifiedDate) gets
   `source_table = EmailAddress` and a `relation_inferred` flag; one with (FirstName, LastName)
   stays without a `source_table` and raises nothing; one on a link is untouched.
4. `relation_inferred` is a disclosure.

## 4 Pre-registration

On the tenth chain: a relation-less satellite whose attributes determine a table carries that
table in the same attempt's model — no `dropped_record` for it on a collapsed link, no stage
that selects columns its relation does not have. Where the attributes determine nothing (a lone
timestamp), the drop stands and the disclosure says so. Untestable if no relation-less satellite
occurs.

## 5 Not in this WP

Inferring a relation from fewer than all attributes (a partial match is a guess); satellites on
links; the grain of the moved satellite (WP55 §5).

## 6 Results

*(appended after the change)*

**2026-10-09 — built, keyless.** Commits `b4a40b4` (guards, failing on import) and `58f4fad` (the
change). `rules.infer_satellite_relation`, `FlagKind.RELATION_INFERRED` (disclosure, group
`relation-inferred`), the parser's two paths with the `satellite_relation_inferred` backstop
event. Guards 1–4 pass on the ninth chain's step-1 attempt-1 records: `sat_email_address_detail`
moves to `hub_person` reading `EmailAddress`, `sat_credential_status` (a lone `ModifiedDate`) is
dropped as before; on a hub only a foreign relation is set. Guard 1's dependent-child-key argument
corrected to the field's list type. 1160 tests, ruff, mypy. §4 is **not yet measured live**.

**2026-10-09 — tenth live chain** (`20261008T223946700186Z`): no relation-less satellite whose attributes determined
a table occurred (the one relation-less satellite, step 3 attempt 3's `sat_transaction_detail` on
a link, is out of scope — §2.3 leaves link satellites untouched). §4 untestable, not failed.

**2026-10-09 — eleventh live chain** (`20261009T124133681291Z`): one relation-less satellite on a collapsed one-hub
link, carrying a lone `ModifiedDate` — no table determined, dropped as §2.1 says. Untestable on the
positive case; the negative case behaved.
