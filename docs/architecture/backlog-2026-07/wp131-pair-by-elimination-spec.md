---
type: spec
status: not-measured
updated: 2026-11-15
---

# WP131 — A hub taken twice by one link: the participation no role names reads the key the roles leave (C67)

Status: **Approved and in progress** (2026-11-15, on the owner's go of that day: fix C67 and C68, then run the
demo's chain again) · Owner: Mischa Eismann · Author: Claude. Candidate C67.

## 1 What is wrong

`link_proposal._pair_participations` (WP41 §2) decides which ratified key each participation of one hub reads. For
a link that takes a hub more than once it pairs a participation only when its role names the key's column
(`component` → `ComponentID`); a participation without a role beside another of the same hub is skipped — „two
keys into one hub are a question only a role can answer". The demo's chain (2026-11-15) built the bill of
materials as `hub_product` unqualified (the assembly) plus `hub_product:component`. Both foreign keys of
`BillOfMaterials` (`ProductAssemblyID`, `ComponentID` → `Product.ProductID`) were ratified. The component got its
translation, the assembly none: `stg_product_assembly_component` hashed a `PRODUCTNUMBER` its relation does not
carry, PostgreSQL refused the stage, the link and its two satellites were skipped (1 error, 3 skips of 537).

The question is answered once the roles have taken theirs: one participation and one key are left.

## 2 The rule

After the role-named pairs, the participation without a role reads the remaining key when **all** of these hold:

1. exactly one participation of the hub carries no role;
2. exactly one ratified key into the hub is left unpaired;
3. the relation is declared and carries the hub's key under no name of its own, and does not declare that column
   as its key into the hub (WP89's `declares_key`);
4. every role-named participation is settled — paired here, or already repaired, or its role column is in the
   relation.

Anything less certain pairs nothing, as before. The pair is treated like any other: a translation is flagged for
review (`LINK_TRANSLATION`), an alias is logged, and a satellite on the link reading the relation gets the same
pair (`participation_translations` / `participation_aliases`).

## 3 Not done

- No gate that asks the modeler for a role. With rule 2 the shape is repaired; what rule 2 leaves open (two keys
  left, a role without its key) is refused by WP132's column check, which names the missing column.
- The translation view's header repeats one sentence per join without naming the referencing column
  (`'BillOfMaterials' references 'Product.ProductID' …` twice) — cosmetic, left.
- The view is named `…_via_product_and_product`; the joined list is the name's rule (WP102) and was not changed.

## 4 Pre-registration

- **P1** guards (`tests/test_wp131_pair_by_elimination.py`) red first — seven of nine; the two that pin what stays
  (the relation carries the hub's key; two keys left) green by design — then green.
- **P2** suite with no key reachable, ruff, bare mypy; WP41's, WP89's and WP93–WP95's guards unchanged.
- **P3** zero-cost replay of the demo's five stored runs (stored delta → licences → merge → generator → validator →
  re-bind): on the unchanged code the replay reproduces the stored model and staging metadata exactly; on the fixed
  code nothing but the bill of materials' stage differs.
- **P4** keyless build of the replayed fifth project on PostgreSQL: no error, no skip.
- **P5** live: the demo's next chain builds the link (recorded in `docs/log.md`).

## 5 Measured (2026-11-15)

- **P1 ✔.** Seven of nine red at `0ee6123`, nine green after.
- **Supersedes WP41 §2 rule 3** („an unqualified participation beside others of the same hub: never paired")
  for the case of §2 above, and WP41 §5's note that such a link keeps a stage that cannot build. Not seen when
  this spec was written: WP41's own guard pinned the rule and failed on the fix. It is flipped in the fix
  commit, deliberately (`tests/test_wp41_role_columns_guard.py`, renamed, reason in its docstring).
- **P2 ✔.** Numbers in `docs/log.md`.
- **P3 ✔.** Unchanged code: five of five steps „model as stored", no stage changed. Fixed code: steps 3–5 differ in
  `stg_product_assembly_component` alone — two joins through `Product`, `PRODUCTASSEMBLYID` → `PRODUCTNUMBER` and
  `COMPONENTID` → `COMPONENT_PRODUCTNUMBER` — and one more `LINK_TRANSLATION` flag in step 3.
- **P4 ✔ keyless build.** PASS=539, ERROR=0, SKIP=0 of 539 (two tests more than the 537: the second join's).
  `link_product_assembly_component` holds 2 484 rows = the distinct (assembly, component, unit) of
  `BillOfMaterials`' 2 679; every row's assembly key and component key joins `hub_product` (2 484 and 2 484). The
  second build found the satellite re-inserting — WP133.
- **P5** in `docs/log.md` with the chain.
- **P5 ✔ live** (2026-11-15, the demo's second chain, run `20261115T111823849877Z`; `docs/log.md`, „The demo's
  second chain …"). The modeler built `link_product_assembly_component` as `hub_product` without a role plus
  `hub_product:component`; the unqualified participation carries the translation over `ProductAssemblyID`, the
  component the one over `ComponentID`, the stage is bound to `BillOfMaterials`. Built on PostgreSQL with the fifth
  project (PASS=575 of 575): 2 484 link rows = the distinct (assembly, component, unit) of the table's 2 679; every
  assembly key and every component key joins `hub_product`. One chain, one case.
