# Business Requirements: Contract Management and Customer Records

**Area:** Contract management system (tables prefixed `vic_`) and its CRM module (tables prefixed `crm_`)
**Prepared by:** Business Analysis
**Status:** Draft for review
**Scope:** The operational system area that records partners, contact persons, contract partners, CRM customer records, accounts, contracts, and the holdings taken over from a predecessor system.

---

## 1. Purpose and business context

We are a retail bank. A contract-management system, together with its CRM module, is being brought into the warehouse. The system holds registers of parties, a register of accounts, a register of contracts, an assignment table maintained by a migration, and a record of the holdings carried over from a predecessor system.

The business needs this content reported: who is recorded in each register, what each record says, how long parties have been customers, how contracts and holdings develop over time, and where the data is incomplete.

This document describes **what the business needs to know**, and it deliberately describes each register **as the source presents it**. Where the source does not settle a question — in particular questions about what an identifier means outside its own table — the question is written down here as an open point rather than answered. The source data dictionary is terse, and several of its columns are described only by a short comment; those comments are reproduced faithfully below and nothing is inferred beyond them.

This document does not propose how the warehouse should be structured.

---

## 2. Business entities in scope

The extract covers the following, in the order the source lists them:

| Source table | What the source says it is |
|---|---|
| `vic_partner` | A partner, identified by a national customer ID issued by the core banking system |
| `vic_kontakt` | A contact person, identified by a technical key, with a function and a partner reference |
| `vic_vertragspartner` | A contract partner, identified by a contract-partner key that the source states is *not* identical to the customer number |
| `crm_kunde` | A CRM record, identified by a CRM-internal GUID that is the CRM's own primary key |
| `crm_xref_partner` | An assignment row linking a CRM GUID to a value described as the national customer number, maintained by the migration |
| `vic_konto` | An account, identified by an account number, with an account kind |
| `vic_vertrag` | A contract, identified by a contract number, with a start date and a contract-partner reference |
| `vic_migration_altbestand` | A record from the predecessor system, with a legacy number, a designation and a takeover date |

Each of these is described in its own section below. No section assumes anything about another.

---

## 3. Partner (`vic_partner`)

- **REQ-001** The business must maintain a register of **partners** as held in the contract-management system.
- **REQ-002** Each partner is identified by a **national customer number** (`partn_nr`). The source states that this number is **issued by the core banking system**, not by the contract-management system. The contract-management system therefore carries an identifier it does not own.
- **REQ-003** Because the identifier is issued elsewhere, the business must confirm with the owners of the core banking system: whether the number is unique across the whole bank, whether it is stable for the life of the party, and whether a number can ever be re-used for a different party. None of this is stated in this source.
- **REQ-004** The business must record the **partner name** (`partn_name`). The source holds it as a single free-text field. There is no separation into first and last name, no legal-form field, and no salutation.
- **REQ-005** The business must record **customer since** (`partn_seit`), a date. The business needs this for tenure reporting — for example, how many partners have been customers for more than ten years.
- **REQ-006** The partner record carries **nothing else**: no party type, no status, no address, no contact channel, no segment, no advisor, no organisational unit.

**Clarification needed:** the source does not state which population the partner register covers — all parties known to the bank, or only those that the contract-management system needs. The business must state the expected record count and the criterion for a party appearing here at all.

**Clarification needed:** the register does not distinguish natural persons from legal entities. The business must state whether that distinction is required for reporting and, if so, where it is to be obtained.

---

## 4. Contact person (`vic_kontakt`)

- **REQ-010** The business must maintain a register of **contact persons** — named individuals recorded in the contract-management system.
- **REQ-011** Each contact person is identified by `kontakt_id`, which the source explicitly describes as a **technical key**. The business must state whether this key is stable across reloads of the source system, and what — if anything — serves as a business identifier for a contact person. A technical key that is regenerated on reload cannot carry history.
- **REQ-012** The business must record the **contact person's name** (`kontakt_name`), again a single free-text field.
- **REQ-013** The business must record the person's **function in the company** (`kontakt_funktion`). The source gives "Geschäftsführer" (managing director) as an example. No list of admissible functions is supplied; the field appears to be free text.
- **REQ-014** Function is a reporting dimension — the business wants to select contacts by the role they hold. This requires a stated set of admissible values (REQ-103).
- **REQ-015** Each contact person record carries a `partn_nr`. The source describes this column as a **foreign key to `vic_partner.partn_nr`**, identifying "der Firmenkunde, bei dem diese Person arbeitet" — the **corporate customer at which this person works**. This is the only relationship the source states for this table.
- **REQ-016** The record structure carries **exactly one** partner reference per contact person. The business must state whether one person can be a contact at more than one partner and, if so, how that is to be represented — the source as delivered cannot express it.
- **REQ-017** The relationship carries **no validity dates**: nothing records when a person started or stopped being the contact for that partner. Contact roles change as people change jobs; the source shows only the current assignment.

**Clarification needed:** the referenced party is described in the comment as a *corporate customer*, but the partner register itself (section 3) records no indication of whether a partner is a company or an individual. The business must state how a corporate customer is recognised, and whether every partner referenced from this table is expected to be one.

---

## 5. Contract partner (`vic_vertragspartner`)

- **REQ-020** The business must maintain a register of **contract partners** as held in the contract-management system.
- **REQ-021** Each contract partner is identified by `vp_nummer`, described by the source as the "Schlüssel des Vertragspartners". The source adds explicitly that this key is **not identical to the customer number**. The business should read that as a statement about the *key*; the source makes no statement about the parties themselves (see REQ-082).
- **REQ-022** The business must record the **designation of the contract partner** (`vp_bezeichnung`), a free-text field. The example given by the source is "eine Rückversicherung" — a reinsurer.
- **REQ-023** The business must record the **role in the contract** (`vp_rolle`). No list of admissible roles is supplied.
- **REQ-024** The role is held **on the contract partner record**, not on a relationship between a contract and a partner. As delivered, a contract partner therefore carries one role, the same one in every contract it appears in. The business must state whether a party can hold different roles in different contracts and, if so, where that would be recorded — the source as delivered cannot express it.
- **REQ-025** The example in the source suggests counterparties to a contract rather than the bank's own customers, but the source supplies no type field and no enumeration of the population. **Clarification needed:** what kinds of party appear in this register, and how many records it holds.
- **REQ-026** The record carries no dates, no status and no address.

---

## 6. CRM record (`crm_kunde`)

- **REQ-030** The business must maintain the register of **records held in the CRM module**.
- **REQ-031** Each record is identified by `crm_guid`, described by the source as a **CRM-internal GUID** and as the **primary key in the CRM**. It is the only identifier the CRM record carries.
- **REQ-032** Because the source describes the GUID as CRM-internal, the business must state whether it is acceptable as a warehouse-visible identifier for the record, or whether a different, business-meaningful identifier is expected to be supplied for CRM records.
- **REQ-033** The business must record the **display name** (`crm_anzeigename`). The source describes it as the name shown *in the CRM*; it is not stated to be a legal or registered name, and it may be maintained for presentation rather than for identification.
- **REQ-034** The business must record the **marketing segment** (`segment`). This is a primary reporting dimension for marketing: counts and campaign selection by segment. No list of admissible segments is supplied.
- **REQ-035** The CRM record carries nothing else — no date of creation, no status, no owner, no contact channel.

**Clarification needed:** the source records the current segment only. Segment changes are analytically meaningful (a record moving between segments is a business event), and no history exists. The business must state whether segment history is required (REQ-091).

---

## 7. Migration assignment table (`crm_xref_partner`)

- **REQ-040** The source supplies an **assignment table** with two columns and nothing else. The source describes `crm_guid` as a **foreign key to `crm_kunde.crm_guid`**, and describes `partn_nr` as a value that **corresponds to the national customer number**, in an assignment table **maintained by the migration**.
- **REQ-041** The business must state whether this assignment is **authoritative** — that is, whether the warehouse may rely on it — or whether it is a working artefact of the migration project with a defined end of life.
- **REQ-042** The business must state the **cardinality** of the assignment. Neither column is stated to be unique. It is not settled by the source whether one CRM record may be assigned to several customer numbers, or one customer number to several CRM records.
- **REQ-043** The table carries **no supporting metadata**: no load date, no validity period, no status, no confidence, no indication of who or what created a row, and no record of the basis on which the assignment was made (manual, deterministic rule, probabilistic match). **Clarification needed** on all of these before the assignment is used for anything.
- **REQ-044** The business needs **coverage reporting on both sides**: CRM records that appear in no assignment row, and national customer numbers that appear in no assignment row. Both unmatched populations are business-relevant and must be visible, not silently dropped.
- **REQ-045** The business must state what is expected to happen to this table after the migration ends: whether new assignments continue to be created, by whom, and under what rule.

---

## 8. Account (`vic_konto`)

- **REQ-050** The business must maintain a register of **accounts** as held in the contract-management system.
- **REQ-051** Each account is identified by its **account number** (`konto_nr`).
- **REQ-052** The business must record the **account kind** (`konto_art`). No list of admissible kinds is supplied; the business must supply one (REQ-103), since counting accounts by kind is the primary reporting need this table can serve.
- **REQ-053** The account record carries **no reference to any other record in this extract** — no party, no contract, no product. As delivered, the source does not state who holds an account or what it belongs to.
- **REQ-054** Reporting on **account ownership** is a stated business need and **cannot be served from this extract as delivered**. The business must state where the account-to-party relationship is held and arrange for it to be supplied, either as an extended extract from this system or from another source.
- **REQ-055** The account record carries no opening date, no closing date, no status, no currency and no balance. Account reporting from this source is therefore limited to enumeration and classification by kind. Balance and turnover reporting is out of scope for this area.

---

## 9. Contract (`vic_vertrag`)

- **REQ-060** The business must maintain a register of **contracts** as held in the contract-management system.
- **REQ-061** Each contract is identified by its **contract number** (`vertrag_nr`).
- **REQ-062** The business must record the **contract start date** (`vertrag_beginn`). The business needs new-business reporting from it: contracts started per month, per quarter, per year.
- **REQ-063** Each contract carries a `vp_nummer`, described by the source as a **foreign key to `vic_vertragspartner.vp_nummer`**. This is the only relationship the source states for this table.
- **REQ-064** The structure carries **exactly one** contract-partner reference per contract. Contracts commonly involve several parties in different roles. The business must state whether that is the case here and, if so, where the further parties are recorded — the source as delivered cannot express more than one.
- **REQ-065** The contract record carries **no end date, no term, no status and no termination reason**. The business cannot determine from this source whether a contract is still in force. This must be resolved before any active-portfolio reporting is promised.
- **REQ-066** The contract record carries no product, no amount, no premium and no currency. Contract reporting from this source is limited to counts and start dates.
- **REQ-067** The contract record carries **no reference to an account and no reference to a partner**. The business must state whether contracts relate to accounts or to partners and, if so, where that relationship is held.

---

## 10. Legacy holdings taken over by the migration (`vic_migration_altbestand`)

- **REQ-070** The business must retain the record of the **holdings taken over from the predecessor system**.
- **REQ-071** Each row carries `alt_nr`, described by the source as a **number from the legacy system** whose **format is like the customer number**. The source states a resemblance of *format*. It does not state that the values are drawn from the same set of values, and it does not state what the number identifies.
- **REQ-072** The business must record the **designation in the legacy system** (`alt_bezeichnung`), a free-text field.
- **REQ-073** The business must record the **takeover date** (`uebernahme_datum`). The business needs migration progress reporting from it: how many records were taken over, and when.
- **REQ-074** **Clarification needed — this is the most important open question about this table:** the source does not state **what a row represents**. A designation and a legacy number are compatible with a party, with a contract, with a holding, or with a portfolio position. The business must state what was taken over before the content can be reported meaningfully.
- **REQ-075** The row carries **no reference to what the legacy record became** after the takeover — no target identifier, no status, no indication of whether the takeover succeeded. The business must state whether the outcome of a takeover has to be traceable and, if so, where that information is held.

---

## 11. Cross-cutting requirements

### Questions the business wants answered

- **REQ-080** From the relationships the source states, the business expects the warehouse to answer at least: how many partners exist and how long they have been customers; which contact persons are recorded for a given partner and in what function; how many contracts started in a period, and which contract partner and role each carries; how many accounts of each kind exist; how many CRM records exist per marketing segment; and how the takeover of legacy holdings progressed over time.
- **REQ-081** Questions that **span two registers** — for example a single view of one party across the registers described in sections 3 to 7, or attributing a contract to a customer — depend on the identifier decisions in REQ-082 to REQ-086. They cannot be committed to until those are answered.

### Identifiers and their meaning

- **REQ-082** The extract carries seven identifiers: `partn_nr`, `kontakt_id`, `vp_nummer`, `crm_guid`, `konto_nr`, `vertrag_nr` and `alt_nr`. For **each** of them the business must state: which system issues it, over which population it is unique, whether it is stable over the life of the thing it identifies, and whether values are ever re-used.
- **REQ-083** The source states relationships between tables in exactly three places, and in no others:
  1. `vic_kontakt.partn_nr` is described as a foreign key to `vic_partner.partn_nr` (REQ-015);
  2. `vic_vertrag.vp_nummer` is described as a foreign key to `vic_vertragspartner.vp_nummer` (REQ-063);
  3. `crm_xref_partner.crm_guid` is described as a foreign key to `crm_kunde.crm_guid`, and `crm_xref_partner.partn_nr` is described as corresponding to the national customer number (REQ-040).
- **REQ-084** **Where the source does not state a relationship, the warehouse must not assume one.** For every pair of registers not covered by REQ-083, whether the two describe the same real-world things — wholly, partly, or not at all — is an **open question for the business**, not a matter to be decided from column names, field formats or resemblance of content. Until it is answered, each register must be reported separately.
- **REQ-085** The extract contains **several registers of named parties** — partners (section 3), contact persons (section 4), contract partners (section 5), CRM records (section 6), and, subject to REQ-074, possibly the legacy holdings (section 10). The business must state, register by register, which populations overlap and which do not.
- **REQ-086** Where two registers do hold a record for the same party, the business must further state which register is **authoritative** for each attribute, and what happens when they disagree — for instance when a name is spelled differently in two places. A survivorship rule is a business decision and must be stated, not inferred.
- **REQ-087** **Name-based matching is not a substitute for these decisions.** Every register holds names as a single free-text field, with no structure, no normalisation and no separate legal-form field. Matching parties by name alone will produce both false matches and missed matches, and its results must not be presented as fact.
- **REQ-088** All identifier columns in the extract are typed `varchar`. Before any value from an identifier column is compared, matched or used as a join criterion — within this source or against values held anywhere else — the actual formats must be profiled on real data: leading zeros, prefixes, padding, casing and separators. A format resemblance stated in a data dictionary is not evidence that two columns hold comparable values.

### Change over time

- **REQ-090** **No table in this extract carries a last-changed timestamp, a load timestamp, a validity period or a status flag.** The only dates present are three business dates, each with a meaning of its own: `partn_seit` (customer since), `vertrag_beginn` (contract start) and `uebernahme_datum` (takeover date). None of them is a change-detection signal.
- **REQ-091** The business must therefore state, and the warehouse must implement, how change is to be detected and what history is required. The following do change and are analytically relevant: partner name and customer-since date; contact person name, function and partner assignment; contract-partner designation and role; CRM display name and marketing segment; the migration assignment rows; account kind; contract start date.
- **REQ-092** **The source carries no deletion marker anywhere.** If a record is removed operationally it simply disappears from the extract. The business must state whether removals have to be detected and retained, for which registers, and what a removal is taken to mean.
- **REQ-093** The delivery mechanism is not described in the source. The business must confirm the delivery frequency, whether each delivery is a full snapshot or a delta, and whether late-arriving corrections occur.

### Data quality

- **REQ-100** The business needs **referential completeness reporting** on the relationships the source states (REQ-083): contact persons whose `partn_nr` resolves to no partner; contracts whose `vp_nummer` resolves to no contract partner; assignment rows whose `crm_guid` resolves to no CRM record. Each of these is a defect the business wants counted, not silently discarded.
- **REQ-101** The business needs the **unmatched populations** of the migration assignment reported in both directions (REQ-044).
- **REQ-102** The business needs visibility of **duplicates within each register** — the same real-world party or thing recorded twice under different identifiers. Nothing in the source prevents this in any of the registers, and it directly affects every count reported to the business.
- **REQ-103** Four fields carry classifying values with **no reference list supplied**: `kontakt_funktion`, `vp_rolle`, `konto_art` and `segment`. For each, the business must supply the admissible values and their business meaning. The warehouse must report values that fall outside the supplied list rather than mapping them to a default.
- **REQ-104** The source states data types only. **Nothing in it states which fields are mandatory.** The business must state, per field, whether an empty value is a defect or a legitimate state — in particular for `partn_seit`, `kontakt_funktion`, `vp_rolle`, `konto_art`, `segment` and `vertrag_beginn`.
- **REQ-105** The business needs a **record count and a plausibility expectation per table** before first load, so that a materially wrong extract is recognised as such rather than accepted.

### Privacy and access

- **REQ-110** This area holds **personal data about identifiable individuals**. Contact persons are named individuals by definition. Partner and contract-partner names are held in fields that do not distinguish natural persons from legal entities, so those name fields must be treated as potentially personal data until the business states otherwise (REQ-004, section 3).
- **REQ-111** The **marketing segment** (REQ-034) is a profiling attribute assigned to a record. Its use must be restricted to roles with a legitimate business need, and it must not be exposed in broadly available reporting at record level.
- **REQ-112** Access to record-level party detail must be restricted; aggregated reporting — counts per segment, per function, per account kind, contracts per period — can be made available more widely.
- **REQ-113** **The extract carries no consent attribute of any kind.** Before the marketing segment is used for campaign selection, the business must state where marketing consent is held, and how a downstream use of this data is prevented from breaching it.

---

## 12. Assumptions, exclusions and open points

**Assumptions** — each to be confirmed, none of them established by the source:

- The extract is a complete delivery of each table, not a filtered subset.
- Each table's stated identifier is unique within that table. The source states this explicitly only for `crm_guid` ("Primärschlüssel im CRM").
- The three dates in the extract are recorded in a single, consistent time zone and calendar convention.

**Out of scope for this area** — needed for complete reporting but not delivered by this source:

- Balances, turnover, transactions and any monetary amount
- Product master data, contract terms, premiums and pricing
- Addresses, telephone numbers, e-mail addresses and any other contact channel
- Marketing consent (REQ-113)
- Classification of a party as a natural person or a legal entity
- Whatever else the core banking system holds about a party: this extract carries the national customer number and nothing further from that system
- Account ownership (REQ-054)
- Advisor, organisational unit and any sales-organisation structure

**Open points requiring business clarification**

1. What population does the partner register cover, and how is a corporate customer recognised (section 3, REQ-006)?
2. Is `kontakt_id` stable across reloads, and what is a contact person's business identifier (REQ-011)?
3. Can a contact person work for more than one partner, and where would that be recorded (REQ-016)?
4. Can a contract partner hold different roles in different contracts (REQ-024)?
5. What kinds of party appear in the contract-partner register (REQ-025)?
6. Is the migration assignment table authoritative, what is its cardinality, on what basis were its rows created, and what happens to it after the migration (REQ-041 to REQ-045)?
7. Where is account ownership held (REQ-054)?
8. Can a contract involve more than one party, and how is a contract known to be still in force (REQ-064, REQ-065)?
9. What does a row of the legacy holdings represent, and is the outcome of a takeover traceable (REQ-074, REQ-075)?
10. For each pair of registers not covered by a stated foreign key, do they describe the same real-world things (REQ-084, REQ-085)? Which register is authoritative where they overlap, and what is the survivorship rule (REQ-086)?
11. How is change to be detected, given that no table carries a change timestamp, and what history is required (REQ-090, REQ-091)?
12. Must removals be detected and retained (REQ-092)?
13. What are the admissible values of `kontakt_funktion`, `vp_rolle`, `konto_art` and `segment` (REQ-103)?
14. Which fields are mandatory (REQ-104)?
15. Where is marketing consent held (REQ-113)?
