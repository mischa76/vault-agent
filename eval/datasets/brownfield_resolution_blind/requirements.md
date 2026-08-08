# Business Requirements: Partners, Contracts and Accounts

**Area:** Partner, contract and account master data
**Prepared by:** Business Analysis
**Status:** Draft for review — contains a substantial number of open points
**Scope:** The operational system area that records the parties the bank deals with, the contracts held with them, the accounts carried in the system, the CRM view of the customer, and a holding of records taken over from a predecessor system.

---

## 1. Purpose and business context

We are a Swiss retail bank. Our reporting depends on knowing *which parties* we have a relationship with, *which contracts* those relationships are expressed in, and *which accounts* exist. Client advisors, product management, finance and regulatory reporting all need to reach the same answer to "who is this customer and what do they hold with us?".

The operational area described here is the system of record for partner, contract and account data, and it is accompanied by a customer view maintained in the CRM application and a set of records carried over from a predecessor system during a migration.

This document describes **what the business needs to know**. It does not propose how the warehouse should be structured.

### 1.1 Basis of this document, and the limits that follow from it

This document was written from a **structural extract only**: the delivered source description lists eight tables with their column names and data types, and **nothing else**. Specifically, the extract contains:

- no column descriptions or data dictionary,
- no primary key, foreign key, uniqueness or nullability declarations,
- no code lists or value domains for any coded column,
- no cardinalities, no row counts, no sample data,
- no statement of which system each table originates from,
- no audit, validity, status or deletion columns of any kind.

Every column name in the extract is a **German-flavoured abbreviation**. Where this document says what a name "reads as", that is a *translation of the name*, not a documented meaning. A column called `vertrag_beginn` reads as a contract start date; the source does not confirm that this is what it contains, nor whose contract, nor what "begin" means operationally (signature, effect, booking, or migration).

Consequently a significant part of this document is written as **open questions rather than requirements**. That is deliberate. Where the extract does not support a statement, this document does not make one. The open points in §12 are the most actionable part of this draft: they are the questions the business and the operational system owners must answer before the warehouse design can be settled, and they should be read as work items, not as caveats.

---

## 2. Business entities in scope

The area covers eight delivered tables. The middle column states only what the table and column names read as; the right-hand column states what the extract does **not** establish.

| Table | What the name reads as | Not established by the extract |
|---|---|---|
| `vic_partner` | A register of partners, with a name and a "since" date | What a partner is: a person, an organisation, either, or a role. Whether the partner number is unique or stable |
| `vic_kontakt` | Named contacts, each with a function, carrying a partner number | Whether a contact is a person, a communication event, or a contact channel. What the partner number on it refers to |
| `vic_vertragspartner` | Contract partners, with a designation and a role | Whether these are the same population as `vic_partner`, a subset, an overlap, or an unrelated register |
| `vic_vertrag` | Contracts, with a start date and a contract-partner number | What kind of contract; which party the number identifies; whether a contract has exactly one such party |
| `vic_konto` | Accounts, with an account kind | Who owns an account, which contract it belongs to, or what the kinds are. The table carries no reference to any other table |
| `crm_kunde` | Customers as held in CRM, with a display name and a segment | What a CRM customer corresponds to elsewhere; what the segment values are |
| `crm_xref_partner` | A pair of identifiers, a CRM identifier and a partner number | Which direction the mapping runs, whether it is complete, unique, current, or authoritative |
| `vic_migration_altbestand` | Records taken over from a predecessor system, with a designation and a takeover date | What kind of object was taken over, and what key space its number belongs to |

**The extract contains no monetary amount, quantity, rate, balance, status or currency column anywhere.** No financial or exposure reporting can be sourced from this area as delivered (§11, REQ-208).

---

## 3. Partners (`vic_partner`)

The partner register is the largest identity-bearing object in the extract and is the natural candidate for the backbone of the area. What it actually registers is not documented.

- **REQ-001** The business requires a register of the **parties it has a relationship with**, each carrying a stable identifier that can be quoted across departments. `vic_partner` is the candidate for that register.
- **REQ-002** The business requires that this identifier (`partn_nr`) be **unique within the register and never re-used** for a different party. **The extract declares no key and no uniqueness constraint**; this must be confirmed with the operational system owners before the number is relied on as an identifier.
- **REQ-003** The business requires the **partner's name** (`partn_name`) for display in reporting and in client-facing output.
- **REQ-004** **Clarification needed:** the extract holds a single name column. It is not stated whether this is a natural person's name, a legal entity name, a formatted display name, or a mixture; nor whether it is structured (surname, given name) or free text. Reporting rules for sorting, matching and salutation depend on the answer.
- **REQ-005** **Clarification needed:** the register does not record what **kind** of party each row is. There is no person/organisation indicator, no partner type, no status and no segment. If the business needs to count or filter partners by kind or by status — and retail banking reporting normally does — that information is **not available from this table** and must be sourced elsewhere or added.
- **REQ-006** The business requires the date recorded in `partn_seit` ("partner since") in order to report on **relationship tenure** — for example, how many partners were taken on in each year.
- **REQ-007** **Clarification needed:** what event `partn_seit` records. Candidate readings include the start of the business relationship, the date of the first contract, the date the record was created in this system, and the date the record was loaded during a migration. These give materially different tenure figures. Until this is answered, tenure reporting cannot be signed off.
- **REQ-008** The business requires visibility of partners with a **missing or implausible** `partn_seit` (absent, or earlier than the bank's own founding, or in the future), as these distort every tenure analysis.
- **REQ-009** The extract provides **no end date, no closure date and no active flag** for a partner. The business must be able to distinguish live relationships from ended ones; as delivered, this area **cannot** support that distinction. Whether ended relationships are deleted, retained, or never occur must be established (§11, REQ-203).

---

## 4. Contacts (`vic_kontakt`)

- **REQ-020** The business requires a record of the **named contacts** it deals with, so that an advisor can see who to approach and in what capacity.
- **REQ-021** The business requires the contact's identifier (`kontakt_id`), name (`kontakt_name`) and function (`kontakt_funktion`).
- **REQ-022** The business requires **reporting by function** — for example, listing all contacts holding a particular function. This depends on `kontakt_funktion` being drawn from a controlled list.
- **REQ-023** **Clarification needed:** whether `kontakt_funktion` is a coded value from a maintained list or free text entered by users. The extract gives it as a character column with no code list attached. If it is free text, function-based reporting will require cleansing and the requirement above cannot be met as stated.
- **REQ-024** **Clarification needed — significant.** `vic_kontakt` carries a column named `partn_nr`, the same name as the identifier column of `vic_partner`. **The extract does not state whether the two columns draw on the same key space, or what the relationship between a contact and a partner is.** This document deliberately does **not** assume that they match, and equally does **not** assume that they do not. The business must confirm:
  - whether every value of `vic_kontakt.partn_nr` occurs in `vic_partner.partn_nr`,
  - whether a contact belongs to exactly one partner, to several, or to none,
  - whether the contact is a person acting *for* the partner, a person who *is* the partner, or something else entirely.
  Until this is answered, **no reporting that joins contacts to partners may be built**, and no count of "contacts per customer" can be produced.
- **REQ-025** **Clarification needed:** whether a contact is a *person* at all. The name of the table and the presence of a name and a function are consistent with a person, but they are also consistent with a contact *role*, a contact *point*, or a logged *interaction*. The business needs the operational owners to state which.
- **REQ-026** The extract records **no contact channel**: no telephone number, no email address, no postal address anywhere in the area. If the business needs to reach a contact, or to report on reachability, that data must come from another source.
- **REQ-027** The extract records **no validity period** for a contact and no indication of whether a function has changed. Contact functions change as people move roles; if the business needs to know who held a function at a past date, that history must be built and kept by the warehouse (§11, REQ-200).

---

## 5. Contract partners (`vic_vertragspartner`)

- **REQ-040** The business requires a record of the **parties that appear on contracts**, each with an identifier (`vp_nummer`), a designation (`vp_bezeichnung`) and a role (`vp_rolle`).
- **REQ-041** The business requires **reporting by role** — for example, distinguishing a principal party from a co-liable party, a guarantor, or a representative — because the role determines liability, mailing and regulatory treatment.
- **REQ-042** **Clarification needed:** the permitted values of `vp_rolle` and their business meaning. No code list is delivered. Role-based reporting cannot be specified, let alone validated, without it.
- **REQ-043** **Clarification needed:** what a role is a role *in*. A role may qualify the party's relationship to a specific contract, to the bank in general, or to another party. The extract attaches the role to the contract-partner row itself, not to a contract, but does not say what that means. If one party can hold different roles on different contracts, the structure delivered may not be able to express that, and reporting will be wrong in a way that is invisible.
- **REQ-044** **Clarification needed — significant.** `vic_vertragspartner` and `vic_partner` both read as registers of parties, and both carry an identifier, a name-like column and a further attribute. **The extract does not state whether they describe the same population.** Possible readings include: the same parties under two numbering schemes; contract partners as a subset of partners; two overlapping registers maintained independently; two unrelated registers. This document takes **no position**. The business must establish:
  - whether `vp_nummer` and `partn_nr` are drawn from the same key space,
  - whether a party can appear in both registers, and if so how the two rows are tied together,
  - which register, if either, is authoritative for a party's name.
  Any consolidated customer count produced before this is answered is unreliable — it will either double-count or under-count, and the extract gives no way to tell which.
- **REQ-045** The business requires visibility of **contract partners with no designation** and of designations that differ from the corresponding name held elsewhere, once REQ-044 has been answered and a correspondence exists to compare against.

---

## 6. Contracts (`vic_vertrag`)

- **REQ-060** The business requires a register of **contracts**, each identified by a contract number (`vertrag_nr`), so that the bank can count and list its contractual relationships.
- **REQ-061** The business requires the contract's start date (`vertrag_beginn`) in order to report **new business by period** — contracts started per month, per quarter and per year — which is a standing management figure.
- **REQ-062** **Clarification needed:** what `vertrag_beginn` records — signature, entry into force, first booking, or load date. New-business reporting is only defensible once this is fixed.
- **REQ-063** **Clarification needed:** what kind of contract this table holds. There is **no product, type, category, status, term, end date, amount or currency column**. As delivered, the business can count contracts and date them, and can do nothing else with them. Product-level, term-level and volume-level reporting are **not supported by this extract** and would require either further columns from the source or a further source.
- **REQ-064** The business requires the ability to report contracts **per party**. `vic_vertrag` carries a column named `vp_nummer`, the same name as the identifier column of `vic_vertragspartner`.
- **REQ-065** **Clarification needed — significant.** As with REQ-024, **the extract does not state that these two same-named columns refer to the same thing**, and this document does not assume it either way. The business must confirm whether every `vic_vertrag.vp_nummer` occurs in `vic_vertragspartner.vp_nummer`, and in particular:
  - whether a contract has exactly **one** party. A single party column on the contract would express only one; retail banking contracts routinely have several (joint accounts, co-borrowers, guarantors). If several parties per contract are possible, the extract as delivered **cannot represent them**, and either the source carries the relationship somewhere not delivered, or contracts are being silently reduced to one party.
  - whether the same party may hold many contracts (expected, but not stated).
- **REQ-066** The business requires visibility of **contracts whose party reference is missing or does not resolve**, since an unattributable contract cannot be reported to a client advisor or included in a client view.
- **REQ-067** The extract holds **no contract end, termination or status**. The business cannot distinguish live from terminated contracts from this area. Whether terminated contracts remain in the table, are deleted, or are moved elsewhere must be established (§11, REQ-203).

---

## 7. Accounts (`vic_konto`)

- **REQ-080** The business requires a register of **accounts**, each identified by an account number (`konto_nr`) and classified by an account kind (`konto_art`).
- **REQ-081** The business requires the ability to **count accounts by kind** — the most basic portfolio figure the bank produces.
- **REQ-082** **Clarification needed:** the permitted values of `konto_art` and their meaning. No code list is delivered. The business needs the list, its stability over time, and confirmation of whether values are ever re-coded — a re-coding silently rewrites historical portfolio splits.
- **REQ-083** **Significant gap.** `vic_konto` carries **no reference to any other table in the extract** — no partner, no contract-partner, no contract, no customer. As delivered, **an account cannot be attributed to anybody**. This means the extract cannot answer:
  - which accounts a given customer holds,
  - how many accounts a customer has,
  - which contract an account belongs to,
  - the total number of accounts per segment, region or advisor.
  These are core business questions, so the business must establish where the ownership relationship lives: in a column not included in this extract, in a separate table not delivered, encoded inside the account number itself, or nowhere.
- **REQ-084** **Clarification needed:** whether `konto_nr` carries structure (for example an embedded partner or branch number, as many banking account numbers do). If it does, that structure is undocumented and **must not** be decoded by the warehouse on the strength of appearance alone; the business must state the rule or state that there is none.
- **REQ-085** The extract holds **no balance, currency, opening date, closing date or status** for an account. No balance, volume or account-lifecycle reporting can be sourced here.

---

## 8. Customers as held in CRM (`crm_kunde`)

- **REQ-100** The business requires the **customer view maintained in the CRM application**, identified by `crm_guid`, with a display name (`crm_anzeigename`) and a segment (`segment`).
- **REQ-101** The business requires **segment-based reporting** — customer counts and, ultimately, portfolio figures per segment — because segment drives service model, pricing and campaign eligibility.
- **REQ-102** **Clarification needed:** the permitted values of `segment`, their definitions, who maintains them, and how often a customer moves between them. No code list is delivered.
- **REQ-103** **Clarification needed:** whether `crm_guid` is a technical replication identifier or a business identifier that people quote. The distinction matters: a technical identifier that can be regenerated must not be used as the anchor for a customer's history.
- **REQ-104** **Clarification needed:** what a CRM customer *is* relative to the other registers in this area. The extract offers no definition and no statement of overlap. This document does **not** assume that a CRM customer corresponds to a partner, to a contract partner, to both, or to neither. See §9.
- **REQ-105** The extract records **no relationship owner or responsible advisor**, no CRM status, and no creation date. Advisor-level and CRM-lifecycle reporting are not supported here.
- **REQ-106** Segment changes over time and is analytically load-bearing: reporting "customers by segment" for a past period requires knowing the segment as it stood then. The source supplies only the **current** value, so retention of segment history is a **warehouse requirement**, not something the operational system provides.

---

## 9. The CRM-to-partner cross-reference (`crm_xref_partner`)

- **REQ-120** The business requires the ability to bring the CRM customer view and the partner register together, so that a customer discussed in CRM and a party held in the core system can be recognised as the same relationship where they are one. `crm_xref_partner`, holding a `crm_guid` and a `partn_nr`, is the delivered candidate for that.
- **REQ-121** **Clarification needed — significant.** The extract delivers this table as two character columns and nothing else. **It does not state** that these columns refer to the same things as the same-named columns in `crm_kunde` and `vic_partner`, and this document does not assume it. The business must establish, before any consolidated customer view is built:
  - whether the values genuinely resolve to `crm_kunde` and to `vic_partner` respectively,
  - the **cardinality**: is it one-to-one, or may one CRM customer map to several partners, or one partner to several CRM customers? Each case produces a different, and differently wrong, customer count if assumed incorrectly.
  - whether the mapping is **complete** — are there CRM customers with no partner, and partners with no CRM customer? Both are plausible and both need reporting.
  - whether the mapping is **current and maintained**, or a one-off artefact of a past load.
  - **who owns it** and what happens to it when a customer or partner is merged, split or closed.
- **REQ-122** The business requires visibility of **unmatched records on both sides** of this mapping, and of any values in the cross-reference that resolve to nothing, as these represent customers who will be missing from, or duplicated in, every consolidated report.
- **REQ-123** The cross-reference carries **no validity date, no source, no confidence and no match method**. If a mapping is later found to be wrong, nothing in the delivered structure records when it was believed to be right. The business must state whether the correctness of the mapping needs to be auditable; if it does, that provenance must be added.
- **REQ-124** This document makes **no statement** about whether identities can be resolved across the registers by comparing names (`partn_name`, `vp_bezeichnung`, `crm_anzeigename`, `alt_bezeichnung`). Name-based matching is a business decision with false-positive consequences — merging two real customers is worse than leaving them apart — and it must be specified and approved by the business, not adopted by default.

---

## 10. Records taken over from the predecessor system (`vic_migration_altbestand`)

- **REQ-140** The business requires visibility of the records **taken over from the predecessor system** during migration, each with a number (`alt_nr`), a designation (`alt_bezeichnung`) and a takeover date (`uebernahme_datum`).
- **REQ-141** The business requires this holding in order to **reconcile the migration**: to state how many records were taken over, when, and whether each one is represented in the current system.
- **REQ-142** **Clarification needed — significant.** The extract does **not** state what kind of object `alt_nr` identifies. It reads as "old number", and the surrounding tables offer several candidates — partners, contract partners, contracts, accounts — as well as the possibility that it is a key space of its own belonging to the predecessor system and corresponding to nothing here. **This document takes no position on which**, because guessing wrong would attach migrated records to the wrong entity and the error would be invisible in the result. The business must state:
  - what the predecessor system numbered with these values,
  - whether `alt_nr` can be resolved to any current identifier, and by what rule,
  - whether the resolution is one-to-one, or whether one legacy record became several current ones (or the reverse).
- **REQ-143** **Clarification needed:** what `uebernahme_datum` dates. It reads as a takeover date, but whether it is the date the record was loaded into the current system, the date the underlying business relationship transferred, or a contractual takeover date is not stated. Migration-completeness reporting depends on this.
- **REQ-144** **Clarification needed:** whether this table is **static history** (a frozen record of a completed migration) or **still growing** (records still arriving from a system being decommissioned in tranches). The loading strategy and the reconciliation reporting differ sharply between the two.
- **REQ-145** The business requires that migrated records be **identifiable as migrated** in reporting, so that figures affected by the migration cut-over can be explained. As delivered, that is only possible for objects whose relationship to this table has been established under REQ-142.
- **REQ-146** The extract holds **no status, no migration outcome and no error indication**. Whether a takeover succeeded, was partial, or was later reversed cannot be reported from this area.

---

## 11. Cross-cutting requirements

### Identity and linkage

- **REQ-190** The business requires a **single view of a customer**: for one relationship, the party as registered, the contracts held, the accounts held, the contacts associated with it, its CRM segment, and whether it originated in the predecessor system.
- **REQ-191** **This view cannot be assembled from the extract as delivered.** Of the joins it would need, every single one is undeclared: contact to partner (REQ-024), contract-partner to partner (REQ-044), contract to contract-partner (REQ-065), CRM customer to partner (REQ-121), legacy record to anything (REQ-142), and account to anything at all (REQ-083, for which the extract offers no candidate column whatsoever). Answering these is the **precondition** for the central deliverable of this area, and should be the first item on the business analysis agenda.
- **REQ-192** The business requires an explicit, written statement — from the operational system owners, not inferred — of **which register is authoritative** for a party's identity and for a party's name, given that three tables carry a name-like column (`partn_name`, `vp_bezeichnung`, `crm_anzeigename`) and a fourth carries a designation (`alt_bezeichnung`).
- **REQ-193** Where the same column *name* appears in more than one table (`partn_nr` in three tables, `vp_nummer` in two, `crm_guid` in two), the business requires **confirmation, per pair, that the values share a key space and a meaning**. A shared name is a naming convention, not evidence. This document therefore treats each such pair as unresolved, and the warehouse must do the same until the confirmation exists.
- **REQ-194** Where a linkage cannot be confirmed, the business requires that the warehouse **leave it unbuilt and say so**, rather than build a plausible join. A missing relationship is visible and can be fixed; a wrongly asserted one produces confident numbers that are wrong, and nothing downstream will flag it.

### Change over time

- **REQ-200** **The extract contains no audit columns at all** — no created timestamp, no last-modified timestamp, no version, no validity period, on any of the eight tables. The three date columns present (`partn_seit`, `vertrag_beginn`, `uebernahme_datum`) read as business dates, not as change markers.
- **REQ-201** The business therefore has **no change signal** from this source. It cannot be determined from the delivered structure whether a row has been updated, when, or by what.
- **REQ-202** The business nonetheless requires history for the attributes that demonstrably move — a partner's name, a contact's function, a contract partner's role, a CRM segment, an account kind. **Preserving that history is a warehouse requirement**, and the means of detecting change must be agreed with the operational system owners (full comparison of each delivery, a change feed, or an additional column) because the source as described supplies none.
- **REQ-203** The extract provides **no deletion marker and no status flag anywhere**. If a partner, contract, account or mapping is removed operationally it simply disappears from the delivery. The business must state, per table, whether disappearances need to be detected and retained; for contracts and partners this is likely to be a regulatory requirement rather than a preference.
- **REQ-204** The business requires confirmation of the **delivery frequency and mode** of this extract (full snapshot or delta), since with no change columns the reconstruction of history depends entirely on it.

### Data quality

- **REQ-205** The business requires visibility of **records with a missing identifier or a missing name**, in every one of the eight tables.
- **REQ-206** The business requires visibility of **references that do not resolve**, for each linkage once that linkage has been confirmed under REQ-193 — and, until it is confirmed, a count of how many values would fail to resolve if it were, as evidence for the confirmation discussion itself.
- **REQ-207** The business requires visibility of **duplicate parties** — the same real customer registered more than once, whether within one register or across two. Nothing in the delivered structure prevents this, and it directly affects customer counts, exposure aggregation and regulatory client identification.
- **REQ-208** The business notes that **no column in this area carries an amount, balance, rate, quantity or currency**, and that all non-date columns are character-typed. Every financial figure the bank reports must therefore come from outside this area, and this area's role is limited to identity, relationship and counting.
- **REQ-209** Coded columns (`kontakt_funktion`, `vp_rolle`, `konto_art`, `segment`) require **maintained code lists with business descriptions**. Reporting must present the meaning, not the raw code. Until the lists are delivered, the completeness of these columns cannot be validated and their values must be treated as opaque.

### Privacy, regulation and access

- **REQ-210** This area holds **data about identifiable parties**, including names and, in the case of contacts, named individuals with a stated function. It must be treated as personal data unless the business establishes that every party is a legal entity — which the extract does not establish.
- **REQ-211** Access to party-level detail must be restricted to roles with a legitimate business need. Aggregated reporting (counts by segment, by account kind, by contract start year) may be available more widely.
- **REQ-212** The bank is subject to client-identification and record-keeping obligations. The business must state which of the retention and history requirements in REQ-202 and REQ-203 are **regulatory** rather than analytical, since that determines whether they are negotiable.
- **REQ-213** Because the linkage between the registers is unconfirmed (REQ-191), the bank currently **cannot demonstrate a complete view of a single client** across this area. This is a stated business gap and should be escalated as such rather than absorbed into the warehouse design.

---

## 12. Assumptions, exclusions and open points

**Assumptions** — each requires confirmation, and none of them is relied on in the requirements above

- The extract is a faithful and complete list of the columns available in these tables, i.e. no columns were dropped in preparing it. If columns were dropped, several of the gaps recorded here (notably the account's ownership reference, REQ-083) may not be real gaps.
- The eight tables belong to a single delivery from an operational landscape. The `vic_` and `crm_` name prefixes are a visible naming pattern, but **the extract does not state that they correspond to different systems**, and this document does not assume that they do.
- German-language column abbreviations are read here at face value as German words. This is a reading of a name and carries no authority.

**Out of scope for this area** — needed for full reporting, and not sourceable from this extract

- Balances, volumes, exposures, revenues and any monetary figure (REQ-208)
- Product and contract type definitions, terms, conditions and pricing (REQ-063)
- Account ownership, account balances and account lifecycle (REQ-083, REQ-085)
- Addresses, telephone numbers, email addresses and any contact channel (REQ-026)
- Advisor, branch, organisational unit and responsibility (REQ-105)
- Party lifecycle: closure, dormancy, status, and any active flag (REQ-009, REQ-067)
- KYC, risk classification, PEP status and any compliance attribute

**Open points requiring business clarification** — in priority order

1. Do `vic_kontakt.partn_nr` and `vic_partner.partn_nr` share a key space, and what is a contact's relationship to a partner? (REQ-024)
2. Do `vic_partner` and `vic_vertragspartner` describe the same population, and can a party appear in both? (REQ-044)
3. Do `vic_vertrag.vp_nummer` and `vic_vertragspartner.vp_nummer` share a key space, and can a contract have more than one party? (REQ-065)
4. What does `crm_xref_partner` map, in which direction, at what cardinality, and is it complete and maintained? (REQ-121)
5. What object does `alt_nr` identify, and can it be resolved to any current identifier? (REQ-142)
6. Where does account ownership live — the extract offers no candidate column at all? (REQ-083)
7. Which register is authoritative for a party's identity and name? (REQ-192)
8. Is `partn_nr` unique and never re-used? Are the other identifiers? (REQ-002)
9. What event does `partn_seit` record? (REQ-007)
10. What event does `vertrag_beginn` record? (REQ-062)
11. What event does `uebernahme_datum` record? (REQ-143)
12. What kind of contract does `vic_vertrag` hold, and where do product and status live? (REQ-063)
13. What are the permitted values and meanings of `vp_rolle`? What is the role a role *in*? (REQ-042, REQ-043)
14. What are the permitted values and meanings of `konto_art`? (REQ-082)
15. What are the permitted values and meanings of `segment`, and how often do customers move? (REQ-102)
16. Is `kontakt_funktion` coded or free text? (REQ-023)
17. Is a contact a person, a role, a contact point, or an interaction? (REQ-025)
18. Is `crm_guid` a technical or a business identifier? (REQ-103)
19. Does `konto_nr` carry decodable internal structure, and if so what is the documented rule? (REQ-084)
20. How is change detected, given that the source carries no audit or validity columns? (REQ-202, REQ-204)
21. Must deletions be detected and retained, and for which tables is that a regulatory obligation? (REQ-203, REQ-212)
22. Is `vic_migration_altbestand` static or still growing? (REQ-144)
23. Is name-based matching across the registers permitted, and under what rule and whose approval? (REQ-124)
24. Is every party a legal entity, or does this area hold personal data about natural persons? (REQ-210)

**Note on the state of this draft.** The unusual weight of open points is a finding, not an omission. The source system ships **no data dictionary**, and the delivered extract carries names and types only. The requirements that can be stated with confidence are those about *what the business needs*; almost everything about *what the source actually contains* is unconfirmed. This draft should not be signed off, and no warehouse linkage should be constructed, until at least open points 1 to 7 have been answered in writing by the operational system owners.
