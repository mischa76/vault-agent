---
type: spec
status: not-measured
updated: 2026-11-16
---

# WP138 — The inclusion check within one table compared each row with itself (C75, diagnosis corrected)

Status: **Approved and in progress** (2026-11-16, on the owner's go of that day: fix C75) · Owner: Mischa
Eismann · Author: Claude. Candidate C75. **The candidate blamed the name rule and said the data holds each of
the three inclusions. Neither is so** (§1): the data holds none of them, and the name rule only chose which
pairs were handed to a check that, within one table, does not check inclusion. What is built is the check.
None of the candidate's three options is taken.

## 1 What is wrong — read from the statement and the data copy

C75 (2026-11-16, WP137) listed three inferred foreign keys that reference a column of their own table and
called them true of the data and no keys. WP99's measurement of 2026-10-30 had called the same three
„coincidences“ — inclusions that hold by chance. Both were written from the command's output; nobody had
looked at the rows.

`key_inference._inclusion_holds` builds the anti-join from the two column objects:
`NOT EXISTS (… WHERE key == referencing)`. Across two tables SQLAlchemy puts the key's table into the
subquery and correlates the referencing one — the statement of the spec's rule 4. **Within one table both
columns belong to the same table object, and the subquery is rendered over that table with no reference to
the outer row** (SQLAlchemy 2.1.6, compiled for PostgreSQL):

```sql
SELECT count(*) FROM "HumanResources"."Department"
WHERE "HumanResources"."Department".groupname IS NOT NULL AND NOT (EXISTS (
  SELECT * FROM "HumanResources"."Department"
  WHERE "HumanResources"."Department".name = "HumanResources"."Department".groupname))
```

The subquery asks whether *any* row carries the same value in both columns. If one does, no row counts as a
violation and the pair „holds“; if none does, every non-null row is a violation. Measured on the data copy
(read-only):

| pair | violations as sent | true anti-join | rows with both columns equal |
|---|---|---|---|
| `Department.groupname` in `Department.name` | 0 | 11 of 16 | 2 |
| `EmailAddress.emailaddressid` in `EmailAddress.businessentityid` | 0 | 805 of 19 972 | 291 |
| `ShoppingCartItem.shoppingcartitemid` in `ShoppingCartItem.quantity` | 0 | 2 of 3 | 1 |

„Inventory Management“ is a department group and no department's name; cart item 2 is no quantity. All three
are false inferences, written with counts that read as evidence. **The error runs the other way too:** a real
reference into the own table — a parent column of a hierarchy, where no row is its own parent — has no row
with both columns equal and was never inferred.

At the checkpoints of the second chain of 2026-11-15 two of the three become a `link_proposal_skipped` flag
(`Department.groupname`: three hubs are keyed on a name; `ShoppingCartItem.shoppingcartitemid`: no hub is
keyed on a quantity) — review entries about a key that does not exist.

## 2 The rule

**Within one table the key's side of the anti-join is an alias of the table.** `_inclusion_holds` takes the
key column from `key.table.alias()` when the key's table is the referencing column's table; the statement is
then rule 4's for that pair too. The statement for two tables is not touched — it is the one measured since
WP99.

**Unchanged.** Which pairs are candidates (the name rule and the type tier as they are); every pair across
two tables; unique keys; WP137's rules. WP99's first guard pins `EmailAddress.EmailAddressID →
EmailAddress.BusinessEntityID` on its miniature, where every row carries the same value in both columns — the
inclusion truly holds there, and the pin stays as it is.

## 3 Not built

- **No change to the name rule.** With the check corrected, a pair within one table is inferred where the
  data holds it and nowhere else; the candidate's options (no candidate within one table; the table-name rule
  onto the primary key only) would now remove only true inclusions — among them the hierarchy the check could
  not see before. Whether a column named after its own table should be a candidate against another key
  column of that table has no measured case left.
- **No correction inside the earlier records** (WP99's log entry, WP137's spec and log entry, C75): they are
  dated records; this spec, the log entry of this WP and a backlog entry say what was wrong in them.

## 4 Pre-registration

- **P1** (keyless, SQLite through the real inference), a miniature without declarations. `Item(ItemID,
  Quantity)` with rows (2, 3), (4, 4), (5, 7): today `ItemID → Item.Quantity` is inferred (the row 4 = 4);
  it must not be. `Category(CategoryID, ParentCategoryID)` with a root and three children, no row its own
  parent: today nothing is inferred; `ParentCategoryID → Category.CategoryID` must be, with 3 rows, 2
  distinct, 4 referenced. `Node(NodeID, ParentNodeID)` with a root that is its own parent and one parent that
  does not exist: today inferred; must not be. **Red before the change, all three.** A pair across two tables
  (`Line.ProductID → Product.ProductID`) is inferred before and after — the pin.
- **P2** (keyless): `tests/test_wp99_inferred_keys.py` and `tests/test_wp137_inference_beside_declarations.py`
  unchanged and green.
- **P3** (local PostgreSQL, by hand, read-only): `infer-keys` over the full catalogue against the data copy
  writes **4 inferred foreign keys** (7 − 3): the two keys to `Product` the catalogue lacks and the two
  components of `SalesOrderDetail`'s composite key, each equal to its earlier entry; the same 64 unique keys;
  two runs byte-identical. A reference into the own table that the old statement could not see would show
  here as a fifth; none is expected — the catalogue's tables carry no parent column with a name path.
- **P4** (zero cost, the stored chain): the proposer over the five increments with the new file offers the
  same 2 inferred licences and 60 and 30 declared; the `link_proposal_skipped` flags on the three columns go
  from 2 to 0.
- **P5** (zero cost): WP136's replay with the new file writes the fifth project byte-identical to the one
  built on PostgreSQL on 2026-11-16.

No paid run: nothing here touches a model call.
