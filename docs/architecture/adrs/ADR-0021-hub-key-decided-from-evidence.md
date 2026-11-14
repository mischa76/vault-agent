---
type: adr
status: keyless-only
updated: 2026-11-14
---

# ADR-0021: A hub's key is decided from evidence before the modeler, not chosen by it

**Status:** Accepted (2026-11-14, Mischa Eismann — on the owner's go on the proposal as presented: the rule, the
gate, the question at the first checkpoint with the natural key as its default, the translation over a declared key
as a disclosure, and a unique name valid as a key where requirement and catalogue agree)
**Date:** 2026-11-14
**Decision makers:** Mischa Eismann

## Context

Candidate C63 (`backlog-2026-11-candidates.md`, 2026-11-14): on the 5.5 models the modeler keys hubs on the source's
generated primary key although the requirement names the natural key and the key agent ranks it first —
`hub_product` on `ProductID` against `REQ-001` and a candidate score of 0.95 for `ProductNumber`, in its first
attempt; 29 of 40 hubs of the twenty-third chain on an `…ID` column. A hub on a system surrogate loads correctly from
one source and cannot integrate a second one by key, which is what a business key is for (Linstedt/Olschimke;
`dv2-rules-cheatsheet.md`, business key criteria).

The cause is a division of labour, not a defect of one line. The key agent proposes and ranks; the modeler is told to
*prefer* the higher-scored candidate; one steering line demands the parent's key column in a satellite's own relation;
the translation ADR-0013 built for exactly this case works after the modeler and is unknown to it. The modeler
therefore weighs a preference against a rule it can check, and decides for the rule. The same model with the same
rules decided the other way on another document (the drafted arm, 2026-10-30) — the outcome is discretion.

Nothing behind the modeler notices: no gate reads the candidates or the catalogue's keys, the hub's key is not a
decision at either checkpoint, and sign-off shows the mapping of the surrogate as an exact name match of high
confidence. ADR-0013 had rejected keying hubs on the surrogate by name and named this very risk as a caveat (its
effectiveness „depends on the modeler continuing to choose natural keys").

Two constraints shape the answer. The decision must not depend on a model generation. And it must not be bought with
review load: a reviewer who answers ninety decisions accepts defaults, so a default must never be the surrogate, and
a question must be asked only where the evidence disagrees.

## Decision

1. **The key of a hub is decided per source table by a rule in `rules/`, before the modeler runs**, from two pieces
   of evidence: the key agent's ranked candidates (what the requirements say) and the catalogue's declared keys (what
   the source guarantees). A table's *natural keys* are its declared single-column unique keys — the primary key
   included — that are not technical: not a GUID, not generated, not a reference to another table's technical key,
   not nullable.
   - No natural key declared: the rule decides nothing. The modeler chooses as before, and a hub of this run that
     lands on a technical primary key is disclosed as such.
   - The requirements' first choice is a declared natural key: that key, without a question (*agreed*).
   - The primary key is itself a natural key and the requirements' first choice is no other declared natural key:
     the primary key, without a question (*natural primary key*).
   - Otherwise — the primary key is technical, a natural key is declared, and the requirements' first choice is not
     one — the case is *contested*: a question at the resolution checkpoint.
   - A table an existing hub is built from keeps that hub's key (records are never re-keyed, WP23).
2. **The modeler receives the decided keys as given**, not as a ranking, and is told that a relation carrying only a
   reference to the hub's table attaches by the generated translation (ADR-0013). Both through the steering registry.
3. **A gate refuses a hub of this run whose key differs from the decided one** (`E_HUB_KEY_NOT_AS_DECIDED`), with a
   remedy the re-model loop follows. A gate, not a backstop: re-keying a hub changes what its satellites and links
   must carry, which is the modeler's to redo.
4. **The contested question is asked once per table, before modelling, and its default is the declared natural key.**
   The bulk answer takes the default. Keying a hub on the technical primary key where a natural key is declared is
   possible only as a named answer with a reason, and the reason is recorded in the proposed ADR. Friction sits on the
   deviation, not on the norm.
5. **A unique name counts** as a natural key where it is declared unique; that it can be renamed is a property of
   natural keys the reviewer sees in the disclosure, not a reason to fall back to the surrogate.

## Alternatives considered

- **Strengthen the prompt** (tell the modeler that a surrogate is never a key). Cheapest, and the mechanism that
  failed: a preference weighed by a model. It would have to be re-proven per model release, and it leaves the
  conflicting satellite line in place. Kept only as the instruction that accompanies the given key.
- **A backstop that re-keys the hub after the modeler.** Deterministic, but a re-keyed hub leaves the old key's
  natural key duplicated in a satellite and the surrogate unread; repairing that is modelling. Rejected for the gate.
- **Ask a human about every hub's key.** Honest and unusable: forty questions per chain on top of the existing
  decisions, answered by default. The rule asks about six on AdventureWorks (estimated from the twenty-third chain:
  address type, contact type, state or province, sales territory, credit card, ship method).
- **Decide from the catalogue alone** (always the first declared unique key). Deterministic, and wrong where the
  requirements argue otherwise — a card number is unique and is not what the business wants hashed into a key.
  Rejected for the two-evidence rule; the catalogue's key is the *default* of the question, not the answer.
- **Accept the surrogate and integrate in the Business Vault** (same-as links). A legitimate pattern where no
  natural key exists, and what a hub on a technical key amounts to; as a default it gives up the raw vault's
  integration by key and contradicts ADR-0013.

## Consequences

- (+) The key no longer depends on the document's wording or the model generation; the rule and the gate are product
  and are not ablated.
- (+) ADR-0013's translation gets its cases back — it had been built for hubs on natural keys and had none on 5.5.
- (−) More translations per run. A translation was one decision per key (WP116); over a declared foreign key it
  becomes a disclosure (note appended to ADR-0013, WP128), or the natural key would cost about 55 decisions per chain
  (the C1 finding, 2026-10-31).
- (−) The 5.5 review record's decision counts were measured on surrogate-keyed hubs; the record starts a new
  generation with the first chain under this ADR.
- (−) A staging join per referencing relation: the referenced table must be loaded with it, an unmatched reference
  fails the build (ADR-0013's tests). Late-arriving parents and delta deliveries on translation views are not
  measured.
- (neutral) Where the catalogue declares no keys the rule is inert and the run behaves as before; a landing zone
  without constraints gets nothing from this ADR until inferred keys (ADR-0018) are admitted as evidence.
- (neutral) Whether a primary key is generated is not in the catalogue today; until the reader delivers it (WP127)
  the rule reads the type: an integer or GUID primary key is taken as technical, a character one as a code — never
  the column's name.
- (neutral) Existing vaults keep their keys. The shipped AdventureWorks demo is regenerated.

## References

- C63: `docs/architecture/backlog-2026-11-candidates.md`; the log entry of 2026-11-14
- ADR-0013 (surrogate→natural-key translation) and its note of 2026-11-14; ADR-0007 (automation scope);
  ADR-0018 (inferred keys); ADR-0019 (the drafted arm that kept the natural keys)
- Spec: `docs/architecture/backlog-2026-07/wp125-hub-key-decision-spec.md`
- Invariants: a gate refuses, a backstop repairs; branch on typed fields; helpers in `rules/` (CLAUDE.md)
