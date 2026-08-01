<!--
STATUS: DRAFT, NOT USABLE AS A MEASUREMENT INPUT — 2026-08-01.

Authored by a blinded agent that was given only this case's source_schema.yml. The blinding
did not hold, through no fault of the author: that schema file states the expected answers in
its YAML comments ("TRAP 1 - synonym hub. This IS the existing hub_customer", "CONTROL", and
for vic_migration_altbestand a full sentence saying the only correct answer is `unresolved`).
The author reported this unprompted and says it treated those comments as off-limits, writing
only from table names, column names, types and the German COLUMN comments. That may well be
true, and it is exactly the kind of claim blinding exists so that nobody has to trust.

Before this file is used: strip the trap annotations out of source_schema.yml (they duplicate
golden_resolution.yml's own `rationale` fields), then re-author against the clean file. Keep
this draft only as the record of why. See docs/log.md, 2026-08-01.
-->

# Business Requirements: Contract Management and CRM

**Area:** Contract administration, contract counterparties and CRM customer records
**Prepared by:** Business Analysis
**Status:** Draft for review
**Scope:** The operational contract-management system (tables prefixed `vic_`) together with its CRM module (tables prefixed `crm_`), as it is to be delivered to the warehouse.

---

## 1. Purpose and business context

We are a Swiss retail bank. This document covers a source system that administers **contracts** and the **parties involved in them**, plus a **CRM module** in which client-facing staff maintain their own view of the customer.

The system is a long-lived application with a legacy data dictionary. Its column names are terse and its German comments are in places more informative than the names themselves; both have been used as the basis for this document. Where the source says nothing, this document says so rather than filling the gap by assumption.

The business need is straightforward to state and hard to satisfy today: we want to be able to report **who our partners are, which contracts exist, who the counterparties to those contracts are, which accounts we carry, and how the CRM view of a customer relates to the record held under the national customer ID**. Today each of these questions is answered in a different screen of the application, and none of them can be answered together.

This document describes **what the business needs to know**. It does not propose how the warehouse should be structured.

---

## 2. Business entities in scope

| Concept | Source table | What it is in business terms |
|---|---|---|
| Partner | `vic_partner` | A party carried under the national customer ID issued by the core banking system |
| Contact person | `vic_kontakt` | A named individual acting for a corporate customer |
| Contract partner | `vic_vertragspartner` | A counterparty to a contract, held under its own key |
| Contract | `vic_vertrag` | An individual contract with a start date and a counterparty |
| Account | `vic_konto` | An account, identified by its account number, with an account kind |
| CRM customer | `crm_kunde` | The customer record as maintained inside the CRM module |
| CRM assignment | `crm_xref_partner` | The mapping maintained by the migration between a CRM record and a national customer ID |
| Legacy holding | `vic_migration_altbestand` | A record taken over from a predecessor system on a given date |

---

## 3. Partner

- **REQ-001** The business must maintain a register of **partners** as held in this system.
- **REQ-002** Each partner is identified by the **national customer ID** (`partn_nr`), which the source states is **issued by the core banking system**. This system therefore does not mint the identifier; it carries an identifier that originates elsewhere in the bank.
- **REQ-003** Because the identifier originates in the core banking system, the business expects the same identifier to denote the same party wherever it appears in the bank. Reporting must be able to use it as the point of reference for a partner. **Confirmation required** from the core banking system owners that the ID is stable over the life of a party and never re-issued to a different party.
- **REQ-004** The business must record the partner's **name** (`partn_name`). The source calls this the "name of the partner" without distinguishing an individual from an organisation, and it is a single field — there is no separate first name, family name or legal-form component.
- **REQ-005** The business must record **customer since** (`partn_seit`), the date from which the party has been a customer. This is the only tenure information in the area and the business needs it for cohort analysis: how many partners joined in a given year, and how long a partner has been with us at the time of any contract.
- **REQ-006** The business must be able to answer: how many partners do we carry, when did they join, and how has the partner population grown per year.
- **REQ-007** **Clarification needed:** the record carries no party-type indicator, no status, no closure date and no address. The business cannot tell from this system whether a partner is an individual or a company, nor whether the relationship is still open. If those facts are required for reporting they must be sourced elsewhere; they are not available here.

---

## 4. Contact persons at corporate customers

- **REQ-010** The business must record the **contact persons** it deals with at corporate customers.
- **REQ-011** A contact person is identified by a **technical key** (`kontakt_id`). The source describes it explicitly as technical. It carries no meaning for the business, but it is the only identifier the contact person has — the same individual cannot be recognised across two records by anything else the source provides.
- **REQ-012** The business must record the contact person's **name** (`kontakt_name`).
- **REQ-013** The business must record the contact person's **function in the company** (`kontakt_funktion`), which the source illustrates with "Geschäftsführer" (managing director). This is a free-text role description, not a code from a maintained list.
- **REQ-014** Every contact person is attached to a **corporate customer** by the national customer ID (`partn_nr`), described in the source as a foreign key to `vic_partner.partn_nr` — "the corporate customer at which this person works".
- **REQ-015** The business must be able to answer: **who is our contact at this corporate customer, and in what function?** and, in the other direction, at which corporate customer does a given contact person work.
- **REQ-016** A corporate customer may have **several** contact persons. Reporting must not assume there is exactly one.
- **REQ-017** The contact person carries **no contact details of their own** — no email address, no telephone number, no address. If the business wants to reach a contact person from warehouse output, that information must come from another system.
- **REQ-018** People change jobs and change function. The source holds only the current assignment, with no validity dates and no status. **If the business needs to know who the contact at a corporate customer was at a given point in the past, that history must be built and kept by the warehouse** — the operational system does not supply it.
- **REQ-019** **Clarification needed:** the source does not state whether a contact person may be recorded for a partner that is not a company, nor whether the same individual working for two corporate customers appears as one record or two. The technical key suggests the latter, but this must be confirmed.

---

## 5. Contract partners

- **REQ-020** The business must maintain a register of **contract partners** — the counterparties that appear in our contracts.
- **REQ-021** A contract partner is identified by its **contract-partner key** (`vp_nummer`). The source states expressly that this key is **not identical to the customer number**. Reporting must therefore treat it as an identifier in its own right and must not join it to the national customer ID.
- **REQ-022** The business must record the contract partner's **designation** (`vp_bezeichnung`). The source illustrates this with "eine Rückversicherung" (a reinsurer), which indicates that contract partners include institutional counterparties rather than only our own retail clients.
- **REQ-023** The business must record the contract partner's **role in the contract** (`vp_rolle`). Note that the role is recorded **on the contract partner, not on the contract**: as the source presents it, a contract partner carries one role, and a counterparty acting in two roles would need two records. **Clarification needed** — this is a material modelling question and the business must confirm the intended behaviour.
- **REQ-024** The business must be able to answer: which counterparties do we hold contracts with, in which roles, and how many contracts does each of them carry.
- **REQ-025** The contract-partner record carries **no date fields at all** — no registration date, no validity period, no status. The business cannot tell from this system when a counterparty relationship began or whether it is still active.

---

## 6. Contracts

- **REQ-030** The business must record every **contract** administered in this system, identified by its **contract number** (`vertrag_nr`).
- **REQ-031** The business must record the **contract start date** (`vertrag_beginn`). This is the only date on the contract: there is **no end date, no termination date, no renewal date and no status**.
- **REQ-032** Because no end date exists, the business cannot determine an active contract portfolio from this system alone. Reporting can state how many contracts started in a period; it cannot state how many are in force at a point in time. **This is a significant gap and must be raised with the system owners.**
- **REQ-033** Every contract is linked to a **contract partner** (`vp_nummer`), described in the source as a foreign key to `vic_vertragspartner.vp_nummer`.
- **REQ-034** The business must be able to answer: how many contracts start per month and per year; which contracts belong to a given counterparty; what the age distribution of the contract book is.
- **REQ-035** The contract carries **no link to a partner and no link to an account**. As delivered, a contract is connected to its counterparty and to nothing else. The business needs the connection between a contract and the customer it serves; **this connection cannot be made from the data in this source system** and its absence must be resolved before contract-level customer reporting is possible.
- **REQ-036** The contract carries no product, no amount, no premium and no currency. Any financial reporting on contracts must be sourced elsewhere.

---

## 7. Accounts

- **REQ-040** The business must record **accounts**, identified by the **account number** (`konto_nr`).
- **REQ-041** The business must record the **account kind** (`konto_art`) — the classification of the account. The source provides the field but no list of permitted values. **Clarification needed:** the full set of account kinds and their business meaning, so that reporting can present them in business language rather than as raw codes.
- **REQ-042** The business must be able to count and segment accounts by account kind.
- **REQ-043** The account record carries **no owner, no partner reference, no opening date, no closing date, no balance and no currency**. As delivered by this system, an account is an account number and a kind, and nothing more.
- **REQ-044** The business fully expects to report accounts **per customer** — "which accounts does this partner hold?" is a basic question. That question **cannot be answered from this source system**, because it holds no relationship between an account and any party. The owning relationship must be obtained from another system, and until it is, account reporting is limited to counts by kind.

---

## 8. The CRM customer record

The CRM module holds its own record of the customer, maintained by client-facing staff, with its own key and its own content.

### The CRM record

- **REQ-050** The business must record the **CRM customer record** as maintained in the CRM module.
- **REQ-051** The CRM record is identified by a **CRM-internal GUID** (`crm_guid`), described in the source as the **primary key within the CRM**. It is a system-generated identifier belonging to the CRM module.
- **REQ-052** The business must record the **display name used in the CRM** (`crm_anzeigename`). This is the name as client-facing staff see and maintain it; the source does not state that it is subject to any naming rule.
- **REQ-053** The business must record the **marketing segment** (`segment`). Segment is a primary reporting dimension: the business must be able to count, filter and compare across segments.
- **REQ-054** **Clarification needed:** the permitted values of the marketing segment, who maintains them, and how often they change. A segment that is re-defined silently changes the meaning of every comparison over time.
- **REQ-055** The CRM record carries **no dates** — no creation date, no last-changed timestamp, no segment-assigned date. Segment membership does move, and the business needs to be able to report on the segment a customer was in at the time of a past activity. **That history does not exist in the source and would have to be built by the warehouse.**

### The assignment maintained by the migration

- **REQ-060** The business must record the **assignment between a CRM record and a national customer ID**, held in `crm_xref_partner`.
- **REQ-061** The assignment consists of the **CRM GUID** (`crm_guid`, a foreign key to `crm_kunde.crm_guid`) and a **number that the source describes as corresponding to the national customer ID** (`partn_nr`). The source describes the table itself as an **assignment table maintained by the migration**.
- **REQ-062** The business must be able to report the CRM content — display name and marketing segment — **alongside** the record held under the national customer ID, using this assignment.
- **REQ-063** Because the assignment is described as *maintained by the migration* rather than by the operational process, its completeness and its currency are open questions. The business needs to know:
  - how many CRM records have **no** assignment,
  - how many national customer IDs appear in the assignment with **no** corresponding partner record,
  - whether one CRM record can be assigned to more than one national customer ID, or one national customer ID to more than one CRM record,
  - who maintains the assignment now that the migration is complete, and under what process a new CRM record acquires one.
- **REQ-064** These figures must be **reported as a standing data-quality measure**, not established once. An assignment table that is not kept current degrades quietly, and every report that depends on it degrades with it.
- **REQ-065** Where a CRM record cannot be assigned, reporting must **show it as unassigned** rather than dropping it. A customer count that silently omits unassigned CRM records is wrong in a way nobody notices.
- **REQ-066** The assignment table carries no dates and no status, so it is not possible to tell when an assignment was made or whether it has since been superseded.

---

## 9. Legacy holdings taken over from the predecessor system

- **REQ-070** The business must record the **holdings taken over from the predecessor system**, held in `vic_migration_altbestand`.
- **REQ-071** Each record is identified by a **number from the legacy system** (`alt_nr`). The source describes this number as being **in the same format as the customer number**.
- **REQ-072** The business must record the **designation in the legacy system** (`alt_bezeichnung`) and the **date of takeover** (`uebernahme_datum`).
- **REQ-073** The business must be able to report how many records were taken over and when — the takeover volume by date is the basic measure of the migration itself.
- **REQ-074** **Clarification needed, and this is the most important open point in this document.** The source tells us only that `alt_nr` has the *same format* as the customer number. It does not say what these numbers refer to, whether they are drawn from the same numbering series, or whether a given `alt_nr` and a given `partn_nr` with equal values denote the same party. There is **no assignment table for this data as there is for the CRM records** (REQ-060).
- **REQ-075** Until the system owners state the answer to REQ-074 in writing, this data must be **reported strictly on its own terms**, as legacy holdings identified by their legacy number. It must **not** be joined to, counted with, or presented as the partner population. Matching on format similarity alone would put wrong parties in front of the business, and a wrong join here would be invisible in the output.
- **REQ-076** The business needs a stated answer, not an inference: **do these numbers identify the same parties as the national customer IDs, a different population, or an overlapping one?** The system owners and the migration team are the source of that answer.

---

## 10. Cross-cutting requirements

### Bringing the parts together

- **REQ-080** The business needs a **single view of a party** in this source system: the partner record, its contact persons, and — where an assignment exists — the CRM display name and marketing segment.
- **REQ-081** Reporting must correctly reflect that the relationships involved are **one-to-many**: a corporate customer has several contact persons, a contract partner carries several contracts. Any report that assumes one of each will be wrong.
- **REQ-082** The business must be able to state, for each identifier in this area, **what it identifies and what it may be joined to**. Four different identifiers appear across the eight tables — the national customer ID, the technical contact key, the contract-partner key, the CRM GUID — plus the account number, the contract number and the legacy number. They are not interchangeable, and the source says as much in one case explicitly (REQ-021).
- **REQ-083** Where two records cannot be related from the data in this system, warehouse output must **leave the relationship absent and visible as absent**, rather than closing it by name similarity or by matching values that merely look alike. Anything asserted beyond what the source states must be traceable to a documented business decision.

### Change over time

- **REQ-090** The source provides **no change-tracking mechanism anywhere in this area**: no last-changed timestamp, no version, no validity dates, no status and no deletion marker on any of the eight tables. The three dates that exist (`partn_seit`, `vertrag_beginn`, `uebernahme_datum`) are business event dates, not change signals.
- **REQ-091** The operational system therefore holds the **current state only**, and every change overwrites what was there before, invisibly.
- **REQ-092** The business requires the warehouse to **preserve the history of change** for at least the following, all of which do change and all of which matter analytically:
  - a partner's name,
  - a contact person's name, function and the corporate customer they work for,
  - a contract partner's designation and role,
  - a CRM display name and marketing segment,
  - an account's kind,
  - the assignment between a CRM record and a national customer ID.
- **REQ-093** Because there is no change signal in the source, change detection must be performed by **comparing successive deliveries** in the warehouse. The business needs to understand the consequence: change is detected to the granularity of the delivery cycle, and two changes between deliveries are seen as one. **Clarification needed:** the delivery frequency of each table.
- **REQ-094** **Clarification needed:** if a record is removed operationally it simply disappears from the delivery. The business must state whether removals need to be detected and retained, and for which tables.

### Data quality

- **REQ-100** The business needs standing visibility of **broken references**: contact persons whose national customer ID has no partner record; contracts whose contract-partner key has no contract-partner record; CRM assignments whose GUID has no CRM record.
- **REQ-101** The business needs visibility of **duplicates** — in particular the same organisation or individual carried more than once. Nothing in the source prevents this, and it directly affects every count the business will publish.
- **REQ-102** The business needs visibility of **records with no relationship at all**: partners with no contact person, contract partners with no contract, CRM records with no assignment (REQ-063), and accounts, which today have no relationship available to them at all (REQ-043).
- **REQ-103** Free-text fields — the contact function, the contract-partner designation, the CRM display name, the legacy designation — will contain spelling variants, abbreviations and inconsistent casing. Reporting that groups on them needs that stated up front; the source enforces no vocabulary on any of them.
- **REQ-104** The account kind and the marketing segment must resolve to **named, documented values**. A code that cannot be resolved is a data-quality defect and must be reported rather than passed through.

### Confidentiality and access

- **REQ-110** This area holds **client-identifying banking data**: named parties, their tenure as customers, account numbers, contract numbers and marketing segments. It is subject to the bank's client-confidentiality and data-protection obligations.
- **REQ-111** Access to party-level detail must be restricted to roles with a legitimate business need. Aggregated reporting — counts by segment, by account kind, by contract start year — should be available more widely.
- **REQ-112** The **marketing segment** governs how a customer may be approached commercially. It must be carried correctly through to any downstream use, and any extract that leaves the warehouse must respect it.
- **REQ-113** The business must be able to state, for a given party, what this area holds about them.

---

## 11. Assumptions, exclusions and open points

**Assumptions**

- The national customer ID is stable over the life of a party and is never re-issued (to be confirmed, REQ-003).
- The `vic_` and `crm_` table groups are delivered from one system as one package, and their deliveries are consistent with each other at the point of extraction. If the CRM module is extracted on a different cycle from the contract system, the assignment table can be out of step with both and this must be known.
- The foreign keys described in the column comments are enforced by the application. The source comments assert them; the schema does not state that any constraint exists.

**Out of scope for this area** — needed for full reporting but sourced elsewhere:

- The core banking system's own party master data — party type, status, addresses, closure
- Account ownership, balances, currency, opening and closing dates
- Contract financials: product, premium, sum insured, amounts, currency
- Contract termination and renewal events
- Contact details of contact persons (email, telephone, address)
- The predecessor system itself and its documentation

**Open points requiring business clarification**

1. Does the contract partner's role belong on the contract partner or on the contract (REQ-023)?
2. How can a contract be related to the customer it serves, given that no such link exists here (REQ-035)?
3. Where does account ownership come from (REQ-044)?
4. What are the permitted values of the account kind (REQ-041) and of the marketing segment (REQ-054)?
5. Who maintains the CRM assignment table now, and how complete is it (REQ-063)?
6. What do the legacy numbers in `vic_migration_altbestand` identify, and how do they relate — if at all — to the national customer ID (REQ-074)? A written answer from the migration team is required before this data is joined to anything.
7. How is a contract's end or termination to be determined (REQ-032)?
8. What is the delivery frequency of each table, and must deletions be detected (REQ-093, REQ-094)?
