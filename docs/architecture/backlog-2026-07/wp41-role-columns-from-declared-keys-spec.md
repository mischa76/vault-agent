---
type: spec
status: not-measured
updated: 2026-09-15
---

# WP41 — Role columns from declared keys, and key licenses in greenfield

Status: **Approved and in progress** (2026-09-15, user: „mach 2, Rollenspalten aus deklarierten
Fremdschlüsseln"; ratification path chosen the same day: „Lizenzen auch in Greenfield" over
„nur Erweiterungsläufe" and „deterministisch, ohne Checkpoint") · Owner: Mischa Eismann ·
Author: Claude. Depends on WP8/ADR-0009 (roles), WP34 (proposer, checkpoint), WP36/ADR-0013
(translation), WP40 (key licenses), and `E_LINK_KEY_WRONG_COLUMN` of 2026-09-15.

## 1 Problem, measured

A role-qualified participation stages its key from `ROLE_<key>` (`role_bk_column`, ADR-0009), a
column no real catalogue carries: the source names the role in its own column
(`ProductAssemblyID`, `ComponentID`) and declares it as a foreign key. WP40 repairs only
unqualified, single participations, and only in extension runs. Inventory over every persisted
step of the five `adventureworks_incremental` chains (new links, relation bound by name and
declared with foreign keys):

| link | step | chains | shape |
|---|---|---|---|
| `link_business_entity_contact` | 1, person (greenfield) | 2 | `hub_business_entity:organisation`, `hub_person:contact` — both role columns absent |
| | | 1 | `…:organisation` absent, `hub_person` unqualified hashed from the organisation column |
| | | 2 | both unqualified, `hub_person` hashed from the organisation column |
| `link_bill_of_materials` | 3, production | 2 | `hub_product:assembly`, `hub_product:component` — both absent |
| | | 3 | `hub_product` unqualified, `hub_product:component` — both absent |

Every one of these stages demands a column its relation does not have, or hashes the wrong one.
The only gates are `W_ROLE_BK_NOT_IN_SOURCE` (a warning), `E_SAT_KEY_NOT_IN_SOURCE` on a satellite
read from the same relation (the red person gate of `20260915T013719090467Z`), and since this
morning `E_LINK_KEY_WRONG_COLUMN`. All other role-qualified links in the corpus read inferred
`raw_*` relations — no declared keys, out of scope.

Two further facts the build has to respect. In greenfield nothing licenses anything: the proposer
is inert without an existing vault (`is_grounded_extension`), and the modeler calls every applier
only in brownfield mode. And a translation view projects the natural key under its own name
(`r.PRODUCTNUMBER as PRODUCTNUMBER`), so two roles of one hub through one table would project one
column twice, and neither under the name the stage hashes.

## 2 The rule

**Licenses in every grounded run.** The link proposer runs when a schema is declared, with or
without an existing vault. In greenfield it proposes against an empty vault, which yields exactly
WP40's key licenses — every declared single-column foreign key into another table of the increment
— and nothing else: no link proposals, no relationship proposals, and no skips or skip flags (a key
into an undeclared table has no vault to link to). The resolution checkpoint pauses on them as it
does in extension runs; one `Table.Column` decision each, `--accept` for all. The modeler applies
`apply_key_licenses` in greenfield too, against an empty existing vault. The resolver and every
other applier stay extension-only. A greenfield schema without declared foreign keys is unchanged
and never pauses.

**Pairing — per relation and hub, never per key alone.** After the modeler, for each relation `S`
and hub `H`, the resolved grants into `H` (ratified licenses and WP34/WP36 proposals, as in WP40)
give a set of columns `C`, each with its resolution: translation, alias, or same name. For each
link the modeler built that reads `S`, with participations `P` of `H`:

1. **One unqualified participation** (WP40's case, now per group): if `S` declares `H`'s key on the
   hashed column itself, nothing; else if `C` has exactly one entry, its translation or alias is
   set. A same-named key column that `S` does not declare as `H`'s is repaired only by an alias,
   never a translation — the `E_LINK_KEY_WRONG_COLUMN` signature, whose refusal becomes a repair
   once the key is ratified. Two or more columns: nothing (WP40 took the first grant; that was a
   guess).
2. **A role-qualified participation**: paired with a column `c` when `P` is that one participation
   and `C` has exactly one entry, or when its role names `c` — the role, separator-insensitive, is
   contained in the column name (`component` → `ComponentID`, `assembly` → `ProductAssemblyID`,
   `bill_to` → `BillToAddressID`) — and that match is unique in both directions. A same-name
   resolution becomes an alias too: `ORGANISATION_BUSINESSENTITYID` is derived from
   `BusinessEntityID`.
3. **An unqualified participation beside others of the same hub**: never paired. Which key it means
   is not in the catalogue.

The naming test lives in `rules/` (`role_names_column`), beside `role_bk_column`.

**Staging.** A role-qualified translation projects the natural key under the column the stage
hashes (`r1.PRODUCTNUMBER as ASSEMBLY_PRODUCTNUMBER`); its `not_null` test names that column. An
unqualified translation projects exactly as today (byte-identity).

**Link satellites.** A satellite on a link, read from its own `source_table`, stages every
participation key. `Satellite.participation_translations` is keyed by participation (`hub`, or
`hub:role` — `LinkHubRef`'s own string form, as `driving_key` uses it; unqualified keys unchanged),
and a new `Satellite.participation_aliases` carries the alias repair. Both are applier-owned and
stripped from the modeler's schema.

**Gates follow.** `E_SAT_KEY_NOT_IN_SOURCE` reads a participation's alias or translation;
`E_SAT_TRANSLATION_UNRATIFIED` matches translations by participation; `W_ROLE_BK_NOT_IN_SOURCE`
stays silent on a repaired participation. A repair never creates a link, hub or satellite.

## 3 Guards before the change

`tests/test_wp41_role_columns_guard.py`, committed first, on a greenfield contact miniature and a
production bill-of-materials miniature, through the real proposer, modeler (stub), generator and
validator. Pins FLIPPED by WP41: (1) greenfield with declared keys proposes no license; (2) the
contact link's stage demands `ORGANISATION_BUSINESSENTITYID` and `CONTACT_BUSINESSENTITYID`, and
its satellite is refused by `E_SAT_KEY_NOT_IN_SOURCE`; (3) the unqualified person is refused by
`E_LINK_KEY_WRONG_COLUMN`; (4) the bill-of-materials stage demands `ASSEMBLY_PRODUCTNUMBER` and
`COMPONENT_PRODUCTNUMBER`. Never flipped: (5) an unqualified participation beside a role of the same
hub stays unrepaired; (6) with every license declined, greenfield artifacts are byte-identical to
the same schema without foreign keys; (7) nothing is built the modeler did not build.

## 4 Acceptance

Keyless: the flips and counter-cases; a greenfield schema without foreign keys never pauses; the
pairing rule's three cases, including a role that names two columns (unpaired); gates silent on
repaired constructs; the modeler never sees `participation_aliases`. Replay, zero cost: step 1 and
step 3 of every persisted chain, before and after — role and wrong-column participations repaired,
`E_LINK_KEY_WRONG_COLUMN`, `E_SAT_KEY_NOT_IN_SOURCE` and `W_ROLE_BK_NOT_IN_SOURCE` counts. Postgres:
the demo gains a contact table with an organisation role (same-name alias) and a person keyed under
another name, and a bill of materials with two roles of one hub through one translation; `dbt build`
green, every link row joining the right entities. Live: the user's call, pre-registered after the
replay.

## 5 Not in this WP, and what it costs

Out: links read from undeclared relations; composite keys; a hub satellite with an alias (still
translation only); an unqualified participation beside a role of the same hub (3 of 5
`link_bill_of_materials`, which keep a stage that cannot build — no gate refuses it). **Costs, by
design:** every grounded greenfield run with declared foreign keys pauses at the checkpoint (the
person schema: 13 licenses), and each repair raises its own review item. **Arm A**
(`adventureworks_full`, one greenfield pass) now receives licenses too: an arm-A result from before
WP41 and one after measure different pipelines, and a comparison has to say so.
