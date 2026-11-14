---
type: spec
status: not-measured
updated: 2026-11-14
---

# WP125 — A hub's key is decided from evidence before the modeler: the rule, the given key, the gate, the question (C63, ADR-0021)

Status: **Approved and in progress** (2026-11-14, on the owner's go on the proposal as presented) · Owner: Mischa
Eismann · Author: Claude. Candidate C63, ADR-0021.

## 1 What is wrong

C63: the modeler keys hubs on the source's generated primary key against the requirement and the ranked candidates
(`hub_product` on `ProductID`, first attempt, 2026-10-31; 29 of 40 hubs on an `…ID` column), and nothing behind it
objects. The key is a preference in a prompt; the conflicting steering line and the unmentioned translation make the
surrogate the consistent answer from where the modeler stands.

## 2 The rules

1. **`rules/key_decision.py` — `decide_keys(state)`**, pure, no model call, recomputed wherever it is read (the
   checkpoint, the modeler, the validator), so no node is added and the graph order is untouched. Input: the
   increment's `source_schemas` (declared `primary_key`, `unique_keys`, `foreign_keys`, column types, nullability),
   `business_keys`, `existing_model`, and the human's answers (`state.key_answers`).
   - **Technical column:** its type is a GUID (`uniqueidentifier`, `uuid`); or it is a single-column foreign key onto
     a technical column of another table (a subtype's primary key); or its type is an integer or a serial. Until the
     catalogue says whether a column is generated (WP127) the type decides; the name never does.
   - **Natural column:** not technical and of a character type. A column whose type the catalogue does not declare,
     or declares as anything else (a date, a decimal, a `hierarchyid`), is evidence for neither.
   - **Natural keys of a table:** the declared single-column unique keys, a single-column primary key included,
     whose column is natural and not declared nullable; the primary key first, then in declaration order. A table
     whose single-column primary key is neither technical nor natural gets no decision.
   - **The requirements' candidates of a table:** the key agent's candidates whose field is a column of the table and
     whose entity is the table's name (separator- and case-insensitive), or whose field is a column of no other
     declared table. The first choice is the highest score.
   - **Decision per table with a declared primary key and at least one natural key:** `existing` (a hub of the
     existing vault is built from the table: its key); `human` (an answer names the columns); `agreed` (the first
     choice is a natural key); `natural_primary_key` (the primary key is natural and the first choice is no other
     natural key); otherwise **contested** — pending, with a default: the best-scored candidate among the natural
     keys, else the first natural key. The bulk answer records the default (`catalogue_default`).
   - A table without a declared primary key or without a natural key gets no decision.
2. **The modeler** receives `decided_keys` in its payload (table, key columns, basis) when there are any — absent
   otherwise, so an ungrounded run's payload is byte-identical — and two registered steering lines: the decided key is
   given; a relation that carries only a reference to the hub's table attaches by translation and the hub is never
   re-keyed to make it fit. The fixture `modeler_rules_pre_wp16.txt` is regenerated, the pre-WP16 block a prefix.
3. **`E_HUB_KEY_NOT_AS_DECIDED`** (validator): a hub of this run whose `source_entity` is a decided table and whose
   key columns differ from the decision; a multi-source hub is judged on its feed from that table. A remedy names the
   decided key, says where the old key goes (an attribute of a satellite on the hub's own table) and that referencing
   relations stay as they are. Hubs of the existing vault are not judged.
4. **`W_HUB_ON_TECHNICAL_KEY`** (validator, a disclosure): a hub of this run keyed on its table's technical primary
   key — because no natural key is declared, or because a human chose it, whose reason the message carries.
5. **The question.** The resolution checkpoint pauses while a contested key is pending and lists it with its
   evidence. `resume --key "Table=Column[+Column]"` answers one; `--key-reason "Table=text"` is required when the
   answer is the technical primary key although a natural key is declared, and when it names columns the catalogue
   does not declare unique; `--accept` takes the default for what is still pending. An answer is checked before
   anything resumes (WP73's rule): an unknown table, a column the table does not declare, a missing reason are
   refused with exit 2 and nothing is applied. The interactive prompt asks the same question with the same default.
   The workbench's API takes the same fields (the parity guard of WP82); its form is WP126.
6. **The record.** The proposed ADR lists the decided keys with their basis and a human's reason.

## 3 Not done

The workbench's form (WP126). The catalogue's generated-column property (WP127). The translation's role (WP128).
Inferred keys as evidence (ADR-0018): a catalogue without declared keys gets no decision. Composite natural keys are
never chosen by the rule; a human may name them. No re-keying of an existing hub. No `run --key`: the answer belongs
to the pause that asks.

## 4 Pre-registration

- **P1** guards (`tests/test_wp125_key_decision.py`) red first, then green.
- **P2** suite, ruff, bare mypy green with no key reachable. Changed deliberately: the steering fixture; the gate
  count in the README and the manual's chapter 8 (C44's guard); whatever byte-identity baseline carries the modeler's
  rules block. No raw-vault, staging or contract artefact of an ungrounded or key-less baseline changes.
- **P3 — the replay.** The modeler's stored first attempt on the twenty-third chain's production step
  (`tests/fixtures/wp125/chain23_step3_attempt1.json`: the candidates it was given, the hubs it emitted) against
  `eval/datasets/adventureworks_production/source_schema.yml`: the gate refuses `hub_product` (decided
  `ProductNumber`, *agreed*) and the five hubs whose `Name` led the candidates — category, subcategory, model,
  location, scrap reason — six refusals, each with a remedy naming the decided key; `hub_unit_measure`,
  `hub_culture`, `hub_document` and the hubs without a natural key pass.
- **P4 — the count.** Over the five AdventureWorks steps with the twenty-third chain's candidates: the contested
  tables are at most eight (estimated six: address type, contact type, state or province, sales territory, credit
  card, ship method). Read from the stored trace, no model call.
- **P5** an ungrounded run and a grounded run whose catalogue declares no unique keys: no decision, no pause, the
  modeler's payload byte-identical to today's.
- **Not in this WP:** a paid chain. It follows WP128, pre-registered on its own.
