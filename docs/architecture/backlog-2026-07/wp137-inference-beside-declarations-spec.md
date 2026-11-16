---
type: spec
status: not-measured
updated: 2026-11-16
---

# WP137 — Beside declared keys, an inference the declarations already answer is neither made nor offered (C73)

Status: **Approved and in progress** (2026-11-16, on the owner's go of that day: fix C73) · Owner: Mischa
Eismann · Author: Claude. Candidate C73. The candidate named one shape and two options, undecided; this spec
takes the first option (the inference, not the proposer) and says why (§2). **Measuring the candidate's own
case found two further shapes of the same cause; they are built here and marked as going beyond the
candidate's text** (§1 shapes 2 and 3, §2 rules 2 and 3) — the owner may strike either.

## 1 What is wrong — measured at zero cost

WP99 was measured on a catalogue that declares no key (the data copy's own extract), where an inference can
only be compared with nothing. WP136 ran `infer-keys` over the full AdventureWorks catalogue, which declares
its keys, against the same data: 36 inferred foreign keys. Classified against the declarations
(`eval/results/kept-outputs/wp136-20261116/wp136-source-schema-inferred.yml`, read with the house loader):

| | shape | in the file | at the checkpoints of one chain |
|---|---|---|---|
| 1 | the column has a declared single-column foreign key; the inference is another key column that contains its values | 25 | 21 |
| 2 | the pair is a declared foreign key read backwards | 4 | 4 |
| 3 | the column is a component of a declared composite key, and the proposer already reads it one table further to the same target (WP46) | 2 | 2 |
| — | the name rule pairs a column with a key column of its own table | 3 | 0 |
| — | a key the catalogue does not declare | 2 | 2 |

The right-hand column is the real proposer on the five increments of the second chain of 2026-11-15, each
read with the file's inferred keys: 29 inferred licences and proposals over the chain (4, 3, 11, 1, 10), of
which two are keys the catalogue lacks — `WorkOrderRouting.productid` and
`TransactionHistoryArchive.productid`, both to `Product`. The bulk answer declines all 29 and nothing is built
on them; they are what a human reads past to find the one WP136 needs a yes for.

1. **The next-best target.** WP99 rule 4 says a declared pair is never inferred, and the code takes the
   declared pair out of the candidates — after which the next key column that contains every value wins.
   `WorkOrder.ProductID` declares its key to `Product`; `ProductProductPhoto.productid` is unique in the data
   and contains every product, so it is inferred as the target. The proposer skips an inference whose target,
   tied or wider view is the declared pair (WP99 rule 5); the declared pair is no longer among them.
2. **The declaration backwards.** `ProductProductPhoto.ProductID → Product.ProductID` is declared; the photo
   table's column is unique in the data and holds every product, so `Product.productid →
   ProductProductPhoto.productid` satisfies rule 4 and is inferred. Likewise `Address`, `CreditCard` and
   `ProductDescription` towards a table that references them. It states that every parent row has exactly one
   child row — true of this copy, and the same relationship the declaration already carries.
3. **The component the declaration already reads.** `SalesOrderDetail (SpecialOfferID, ProductID) →
   SpecialOfferProduct` is declared; WP46 reads each component one table further and proposes
   `SalesOrderDetail.ProductID → Product` with provenance `declared`. The inference finds the same pair
   directly, and the proposer's comparison knows single-column declarations only: the same key is offered
   twice, once per provenance, under two spellings of the column.

## 2 The rules

1. **The inference: a column with a declared single-column foreign key gets no inferred foreign key.** The
   column, not the pair. Chosen over the candidate's second option (keep the inference, skip it in the
   proposer) because the file is read and edited by a human too, and what stands in it for such a column is
   not a finding about the data but the residue of leaving one candidate out. A declaration that the data
   contradicts is not this command's subject (the profiler's and the warehouse tests' — manual 6.1, 9).
2. **The inference: a pair whose reverse the catalogue declares as a single-column foreign key is not a
   candidate.** `R.c → T.k` is not checked when `T` declares `k → R.c`.
3. **The proposer: the derived key of a composite key's component counts as declared.** The pairs an inferred
   view is compared with (`declared_pairs`) gain `component_keys(fk, declared)` of every declared composite
   key; an inference that duplicates one is skipped as rule 5 of WP99 skips a duplicate of a single-column
   declaration. The inference itself stays in the file — the direct pair is declared nowhere, and it is true.

**Unchanged.** Unique keys; every inference on a column no declared single-column key names; a catalogue
without declared foreign keys — the WP99 guards pin it and stay as they are. Rules 1 and 2 change what
`infer-keys` writes for a catalogue with declared keys; rule 3 changes what the proposer offers from a file
that carries such an inference. No run without inferred keys changes: no byte-identity fixture moves.

## 3 Not built

- **No second skip in the proposer for shapes 1 and 2.** A file written before this change still carries
  them; running the command again removes them. No such file is in use (WP99's is of a catalogue without
  declarations; WP136's is evidence).
- **The name rule within one table** (`EmailAddress.emailaddressid → EmailAddress.businessentityid`,
  `ShoppingCartItem.shoppingcartitemid → ShoppingCartItem.quantity`, `Department.groupname →
  Department.name`): the rule „the key table's name plus `ID`" pairs a column with every key column of that
  table, its own included. It exists without declarations too, none of the three reaches a checkpoint here —
  candidate C75, not decided.
- **C74** (what the tool does where no key evidence exists) is untouched.

## 4 Pre-registration

- **P1** (keyless, SQLite through the real inference): a miniature with declared keys — `Product`,
  `ProductPhoto` (one row per product, declares `ProductID → Product`), `WorkOrder` (declares `ProductID →
  Product`), `Routing` (carries `ProductID`, declares none for it), `SpecialOfferProduct`, `OrderLine`
  (declares the composite key into `SpecialOfferProduct`). `WorkOrder.ProductID` gets no inference (today:
  `→ ProductPhoto.ProductID`), also when the declaration spells the column in another case; `Product.ProductID`
  gets none (today: the same, backwards). **Red before the change.** `Routing.ProductID → Product.ProductID`
  with `ProductPhoto.ProductID` tied, and `OrderLine.ProductID → Product.ProductID`, stay — green before and
  after, the pins of what must not be lost.
- **P2** (keyless, the proposer): on the miniature's tables with their inferences, greenfield, `OrderLine`
  yields one licence for `ProductID`, the declared one (today two). **Red before.** `Routing.ProductID` still
  yields its inferred licence — green before and after.
- **P3** (keyless): `tests/test_wp99_inferred_keys.py` unchanged and green — a catalogue without declared
  foreign keys infers what it inferred.
- **P4** (local PostgreSQL, by hand, read-only): `infer-keys` over the full catalogue against the data copy.
  Predicted from the classification: **7 inferred foreign keys** (36 − 25 − 4), 64 inferred unique keys as
  before; two runs byte-identical.
- **P5** (zero cost, the stored chain): the proposer over the five increments with the new file offers **2
  inferred keys** (29 − 21 − 4 − 2), both in the production step (11 → 2), and the declared counts are
  unchanged (60 licences, 30 proposals).
- **P6** (zero cost): WP136's replay of the second chain with the new file and the one yes writes the fifth
  project byte-identical to the one WP136 built on PostgreSQL — the build of 2026-11-16 then stands for it.

No paid run: nothing here touches a model call.
