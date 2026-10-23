---
type: spec
status: not-measured
updated: 2026-10-23
---

# WP89 — Homonym keys: a ratified foreign key's translation wins over a same-named column that means something else (C26)

Status: **Approved and in progress** (2026-10-23, the owner's yes to the third — C26 as a work package, before C22) · Owner:
Mischa Eismann · Author: Claude. Found by WP86's measurement (`docs/log.md`, 2026-10-23, P3).

## 1 What is wrong, in one paragraph

`SalesOrderHeader` declares `CustomerID → Customer.CustomerID` and also carries `AccountNumber` — a financial
account (`10-4020-000676`). `hub_customer` is keyed on `Customer.AccountNumber` (`AW00000001`). The ratified key
license resolves to the right translation (`CustomerID` through `Customer` to `AccountNumber`), but
`link_proposal._pair_participations` drops it whenever the relation carries a column named like the hub's key:
„a same-named key column beside a surrogate reference may be a legitimate copy" (WP41 §2 rule 1: „repaired only by
an alias, never a translation"). The stage then hashes the homonym, and **all 31 465 rows of
`link_sales_order_customer` point at no customer** — in the owner's `aw`, in WP86's measurement, and in today's paid
chain (`link_sales_order`). The hub-satellite repair has the same exception (`key in present`).

## 2 The rules (this reverses WP41 §2 rule 1's last clause; WP41's record stays as written)

1. **An unqualified participation of hub `H` in a link reading relation `S`**: when exactly one ratified key from
   `S` into `H` resolves to a translation, the translation is set **even if `S` carries a column named like `H`'s
   key**, as long as `S` does not declare that column as a key into `H` itself. The declaration is the authority:
   if the same-named column is a copy, the translation yields the same value; if it is a homonym, only the
   translation is right. The link satellite's participation follows (it uses the same pairing).
2. **A satellite on `H` read from `S`**: the same — the translation is set although `S` carries the same-named
   column.
3. **Unchanged:** a relation that declares the same-named column as a key into `H` (nothing to repair); a role
   participation whose role column exists; two or more keys into `H` from `S` (not decidable from the catalogue).
4. **The flag says it.** The `LINK_TRANSLATION`/`SAT_TRANSLATION` flag names the same-named column that was not
   read, so the reviewer sees the homonym.
5. **Not in this WP:** a participation with no ratified key (no grant, no repair). A gate for that case would need
   evidence beyond the name; left to C26's later half if the shape recurs.

## 3 Acceptance (keyless)

`tests/test_wp89_homonym_keys.py`: the link participation, the link satellite's participation and a hub satellite
read the translation; the flag names the column not read; a relation declaring the same-named column as a key into
the hub is untouched. The rest of the suite unchanged (checked before the change: no test pins the WP41 clause).

## 4 Pre-registration (keyless `dbt build` on PostgreSQL)

The owner's Sales run regenerated as for the third `aw` rebuild (`docs/log.md`, 2026-10-23), with
`apply_key_licenses` re-applied to the stored model, built twice into a fresh schema `aw_wp89`:

- **P1** `link_sales_order_customer` 31 465 rows, **every** `CUSTOMER_HK` joined to `hub_customer` (was 0).
- **P2** a translation model `stg_sales_order_customer_via_customer` (or the name staging gives it) exists and
  passes its tests.
- **P3** every other link's row count equals `aw`'s, every other link column's join count unchanged.
- **P4** PASS for every model (406 plus the translation model and its tests), second build 180+ incremental
  models `INSERT 0 0`.
- **P5** the paid chain's last step (`workbench/chain-20261023/…/20261022T234439976097Z`) regenerated keylessly:
  `link_sales_order`'s `hub_customer` participation carries the translation.

Not predicted: wall time; which other links, if any, the rule also changes (each one is listed in the log).
