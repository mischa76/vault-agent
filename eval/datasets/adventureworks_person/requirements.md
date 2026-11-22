# Business Requirements: People, Organisations and Contact Information

**Area:** Person / Party master data
**Prepared by:** Business Analysis
**Status:** Draft for review
**Scope:** The operational system area that records the people and organisations the company deals with, how we reach them, and where they are located.

---

## 1. Purpose and business context

We are a bicycle manufacturer and retailer. Almost every business process we run — selling to individual consumers, selling to reseller stores, employing staff, buying from vendors — depends on knowing *who* we are dealing with, *how to reach them*, and *where they are*.

Today this information lives in one operational area that deliberately treats customers, employees, vendor staff and store contacts as variations of the same thing: a party we do business with. The planned warehouse must support reporting and analysis on this shared party information so that the sales, HR, purchasing and marketing areas can all be joined back to a single, consistent view of a person or organisation.

This document describes **what the business needs to know**. It does not propose how the warehouse should be structured.

---

## 2. Business entities in scope

The area covers the following business concepts:

| Concept | What it is in business terms |
|---|---|
| Business entity | Any party — a person or an organisation — that we do business with |
| Person | A named human being: a customer, employee, salesperson, vendor contact or store contact |
| Address | A physical postal location |
| Address type | The role an address plays for a party (billing, home, shipping, …) |
| Contact type | The role a person plays for an organisation (e.g. a job-related contact role) |
| Email address | An electronic mail address belonging to a person |
| Telephone number | A phone number belonging to a person |
| Phone number type | The kind of phone number (home, work, mobile, …) |
| Login credential | The stored, protected sign-in secret for a person's account |
| State or province | An administrative region within a country |
| Country or region | A sovereign country or region we operate in or ship to |

---

## 3. The business entity (party)

The system uses a single, shared party identifier across the whole company. This is the backbone of the area and the reason the warehouse must handle it carefully.

- **REQ-001** The business must maintain a register of **business entities** — the umbrella concept covering all customers, vendors and employees.
- **REQ-002** Each business entity must be identified by a **single company-wide business entity number** that is unique across every party we deal with, regardless of whether that party is a customer, a vendor or an employee.
- **REQ-003** The same business entity number must be usable to link a party to information held in other areas of the business (sales, purchasing, HR). The party register is the integration point for the rest of the company.
- **REQ-004** Because one number spans customers, vendors and employees, the business must be able to recognise that the *same* party may play more than one role at the same time (for example, an employee who is also a retail customer). The system does not force a party into a single role.
- **REQ-005** Each business entity record carries a **last-changed timestamp** recording when it was last updated. The business needs this to understand the currency of the party register.
- **REQ-006** Each business entity also carries a **globally unique record identifier**. This exists to support data replication between systems. It has no business meaning and is not a business key — it should be treated as technical metadata and needs no business reporting.

**Clarification needed:** the source area only records the *existence* of a business entity and the timestamp of its last change. It does not record what kind of party it is, when it was first registered, or whether it is still active. If the business needs to report on party lifecycle (created, dormant, closed), that information must come from elsewhere and is currently unavailable in this area.

---

## 4. Person

A person is a business entity that is a named individual. Not every business entity is a person — organisations (vendors and stores) are business entities too — but every person is a business entity and uses the same party number.

### Identity

- **REQ-010** The business must record every **person** it deals with, identified by the same company-wide business entity number described in REQ-002. A person does not have a separate identifier of their own.
- **REQ-011** The business must record the **primary type of person**, which classifies why the person exists in our systems. The recognised types are:
  - Store contact — a named contact at a reseller store
  - Individual (retail) customer — a consumer who buys from us directly
  - Salesperson — a member of our own sales force
  - Employee (non-sales) — any other member of staff
  - Vendor contact — a named contact at a supplier
  - General contact — a contact that does not fall into the above
- **REQ-012** Person type is a key reporting dimension. The business must be able to count, segment and filter people by their primary type in every analysis (for example, "how many individual customers do we hold in Germany?").
- **REQ-013** The list of person types is a small, fixed set of codes held in the person record itself rather than in a separate reference list. The warehouse must present the meaning of each code in business language, not the two-letter code.

### Name

- **REQ-020** The business must record each person's **first name**, **middle name or middle initial**, and **last name**.
- **REQ-021** The business must record an optional **courtesy title** (for example "Mr." or "Ms.") for use in correspondence.
- **REQ-022** The business must record an optional **surname suffix** (for example "Sr." or "Jr.").
- **REQ-023** The business must record a **name style** indicating whether the person's name should be presented in *western* order (first name then last name) or *eastern* order (last name then first name). This is a presentation rule for correspondence and reporting, and it matters because the company sells internationally.
- **REQ-024** Any report or output that displays a person's full name must be able to honour the recorded name style. Reporting must not assume western ordering.
- **REQ-025** Middle name, title and suffix are optional. Reporting must cope with people who have none of them.

### Marketing consent

- **REQ-030** The business must record each person's **email promotion preference**, which expresses the consent they have given for marketing contact. Three levels are recognised:
  - The person does **not** wish to receive email promotions
  - The person wishes to receive email promotions **from AdventureWorks only**
  - The person wishes to receive email promotions **from AdventureWorks and from selected partners**
- **REQ-031** Marketing and campaign selection must be able to filter by this preference, and must be able to distinguish the "our company only" case from the "our company and partners" case, because the two permit different uses of the person's details.
- **REQ-032** Consent is a compliance-sensitive attribute. The business needs to be able to state what a person's preference was, not only what it is now. The source records only the current value plus a last-changed timestamp, so **historical tracking of consent changes must be introduced by the warehouse** if the business requires an audit trail. This is a stated business need for review.

### Additional descriptive information

- **REQ-040** The business must retain **additional contact information** held for a person in a free-form structured (XML) format. The source does not constrain its content, so its business value cannot be assessed from the schema alone. **Clarification needed:** what fields this actually contains in practice, and whether the business wants them reported.
- **REQ-041** The business must retain **demographic information** collected from online shoppers — described in the source as personal information such as hobbies and income — which is explicitly captured **for sales analysis**.
- **REQ-042** Because demographics are stated to exist for sales analysis, the business needs this content made analysable (for example, segmenting customers by income band or interest) rather than stored as an opaque block. **Clarification needed:** the exact set of demographic questions asked, since the schema does not expose them.
- **REQ-043** Demographic and additional contact information are personal data collected from individuals. Access to them must be treated as sensitive and restricted, separately from ordinary name and contact reporting.
- **REQ-044** Each person record carries a **last-changed timestamp**. The business needs it to know how current a person's details are and to identify records that have not been touched for a long time.

---

## 5. Email addresses

- **REQ-050** The business must record the **email addresses** of people.
- **REQ-051** A person **may have more than one email address**. The system numbers each address within the person, so the business must be able to report all of a person's addresses, not just one.
- **REQ-052** An email address belongs to exactly one person and is meaningless without that person.
- **REQ-053** The business must be able to identify people who have **no** email address at all, since these cannot be reached by email campaigns regardless of their promotion preference.
- **REQ-054** Each email address carries its own **last-changed timestamp**, so the business can see when a person's email details were last touched independently of the rest of their record.
- **REQ-055** Email addresses change over time (people change employer, provider or domain). The business needs to understand whether an address currently on file is still the one previously used in a campaign. **The source keeps only the current value; historical retention of superseded email addresses is a warehouse requirement, not something the operational system provides.**
- **REQ-056** The source does not mark one email address as the primary or preferred one when a person has several. **Clarification needed:** how the business decides which address to use for correspondence.

---

## 6. Telephone numbers

- **REQ-060** The business must record the **telephone numbers** of people.
- **REQ-061** A person **may have several telephone numbers**, and each number is qualified by the **kind of phone number** it is — the same person can hold, for example, more than one number of different kinds.
- **REQ-062** The business must maintain a reference list of **phone number types**, each with a name describing the kind of number (for example home, work or mobile).
- **REQ-063** Reporting must be able to select a person's number *by type* — for example, "the work number of every store contact in Bavaria".
- **REQ-064** A telephone number belongs to exactly one person.
- **REQ-065** Each recorded telephone number carries its own **last-changed timestamp**.
- **REQ-066** Phone number types are referenced across the whole person population, so a change to a type's name (a rename) affects the meaning of historical reporting. The business needs consistent naming of these types over time.

---

## 7. Sign-in credentials

- **REQ-070** The business records a **sign-in credential** for a person, consisting of a protected (hashed) password value and the random value used to protect it.
- **REQ-071** The credential is described in the source as relating to the person's **email account**, indicating that people can sign in to our systems — most obviously the online store.
- **REQ-072** **Credentials must never be brought into the warehouse as readable values, reported on, or exposed to analysts.** They carry no analytical value.
- **REQ-073** The only business-relevant fact about a credential is **whether a person has one at all** and **when it was last changed** — which tells us whether the person has a self-service account and how recently they maintained it. If the business does not need that, the whole credential record should be excluded from scope.
- **REQ-074** The credential record does not carry a description of the person it belongs to; it is attached by the same party number. One person has at most one credential.

---

## 8. Addresses

### The address itself

- **REQ-080** The business must record **postal addresses**, each identified by its own address number.
- **REQ-081** An address consists of a **first street address line**, an optional **second street address line**, a **city**, a **postal code**, and the **state or province** in which it sits.
- **REQ-082** The state or province determines the country, so the country of an address is known indirectly through its state or province rather than being stated on the address itself.
- **REQ-083** The business must record the **geographic location (latitude and longitude)** of an address. This supports mapping, distance and territory analysis — for example, showing reseller stores on a map or measuring how far customers are from a store.
- **REQ-084** Addresses must be reportable at each geographic level: street, city, postal code, state or province, and country or region.
- **REQ-085** Each address carries a **last-changed timestamp**, so the business can see when address details were corrected.
- **REQ-086** An address is recorded once and can be **shared by more than one party** — for example, several employees of the same reseller store, or a household. The business must not assume an address belongs to a single party.
- **REQ-087** Addresses are corrected and re-used over time. Because an address record can be edited in place, an analysis of *where a customer was* at the time of a past order may be affected by later corrections. **The business needs to decide whether historical address values must be retained** so that past activity can be reported against the address as it stood then.

### How addresses relate to parties

- **REQ-090** The business must record which **addresses belong to which business entity**, and in what capacity.
- **REQ-091** A **party can have several addresses**, and the same address can serve several parties (REQ-086).
- **REQ-092** Every party–address relationship must carry an **address type** stating the role the address plays for that party. Examples given by the business are **Billing**, **Home** and **Shipping**.
- **REQ-093** A party may have **different addresses for different purposes** — for example, one address to bill and another to ship to.
- **REQ-094** The combination of party, address and address type is what makes a relationship unique. The business therefore accepts that a party may hold the *same* address under two *different* types (for example, an address that is both the billing and the shipping address), and both must be visible.
- **REQ-095** The business must maintain a reference list of **address types**, each with a descriptive name.
- **REQ-096** The business must be able to answer "what is the shipping address of this customer?" and "which customers ship to this city?".
- **REQ-097** Each party–address relationship carries its own **last-changed timestamp**.
- **REQ-098** Party–address relationships change: parties move, add and drop addresses. The source holds only the currently valid set of relationships. **If the business needs to know which address a party used at a given point in the past, that history must be built and kept by the warehouse** — the operational system will not supply it.
- **REQ-099** The business must be able to identify parties with **no address on file**, since these cannot be shipped to or invoiced by post.

---

## 9. Geography

- **REQ-100** The business must maintain a reference list of **countries and regions**, each identified by its **ISO standard country or region code** and carrying its name.
- **REQ-101** The business must maintain a reference list of **states and provinces**, each identified by its own number and carrying an **ISO standard state or province code** and a descriptive name.
- **REQ-102** Every state or province belongs to exactly one **country or region**.
- **REQ-103** A country or region may contain many states or provinces, and some may contain none.
- **REQ-104** The state or province code is not always meaningful: the system carries a flag indicating that **no genuine state or province code exists** for that entry and that the country or region code is being used in its place. Reporting must handle this gracefully and must not present a substituted country code as if it were a real state code.
- **REQ-105** Every state or province is assigned to a **sales territory**. This is the link between where an address is and which part of the sales organisation is responsible for it.
- **REQ-106** The business must be able to roll addresses — and therefore customers, stores and employees — up to sales territory via their state or province. This supports territory-level sales and coverage reporting.
- **REQ-107** The detail of sales territories (name, group, targets) lives outside this area. Only the assignment of a state or province to a territory is available here, and the warehouse must obtain territory descriptions from the sales area.
- **REQ-108** Territory assignment of a state or province can be changed by the business. Reassigning a state to a different territory retrospectively changes every historical geographic roll-up. **The business must decide whether territory assignments should be tracked over time**, so that past performance can be reported on the territory structure that applied at the time.
- **REQ-109** Country, state and territory reference lists each carry a **last-changed timestamp**.
- **REQ-110** Country and state or province names are used in customer-facing output and in reporting. Consistent, current naming is a business requirement, and renames must be visible rather than silent.

---

## 10. Organisational contacts

- **REQ-120** The business must record which **people act as contacts for which organisations** — for example, the named individual who is our contact at a reseller store or at a supplier.
- **REQ-121** A contact relationship links **two parties**: the organisation (a business entity) and the person acting as its contact.
- **REQ-122** Every contact relationship must carry a **contact type** describing the role the person plays for that organisation.
- **REQ-123** The business must maintain a reference list of **contact types**, each with a descriptive name.
- **REQ-124** The same organisation may have **several contacts**, each in a different role — the combination of organisation, person and role is what makes the relationship unique.
- **REQ-125** The same person may act as a contact for **more than one organisation**, and may hold **more than one role** at the same organisation.
- **REQ-126** The business must be able to answer "who is our contact at this store, and in what role?" and "which organisations does this person represent?".
- **REQ-127** Each contact relationship carries its own **last-changed timestamp**.
- **REQ-128** Contact roles change frequently as people move jobs. The source holds only the current set of relationships. **If the business needs to know who the contact was at a given time — for example, when investigating a past order — that history must be retained by the warehouse.**
- **REQ-129** Because both sides of the relationship are business entities using the same party number, the business must be able to distinguish clearly, in reporting, which side is the organisation and which is the individual. Nothing in the relationship itself labels them; the distinction comes from the party's role.

---

## 11. Cross-cutting requirements

### Single view of a party

- **REQ-140** The business needs a **single view of a party** bringing together, for one party number: their name and type, all their email addresses, all their telephone numbers with types, all their addresses with types, and all the organisations they are a contact for.
- **REQ-141** Reporting must correctly reflect that all of these are **one-to-many** relationships. Any report that assumes a person has exactly one address, one email or one phone number will be wrong.
- **REQ-142** The single view must remain correct when a party plays several roles at once (REQ-004).

### Change over time

- **REQ-150** **Every** record in this area carries only a *last modified* timestamp. The operational system holds the **current state only** and overwrites previous values in place.
- **REQ-151** The business therefore has **no history** today for any of the following, all of which do change and all of which matter analytically:
  - a person's name (marriage, legal change)
  - a person's marketing consent (REQ-032)
  - a person's email address (REQ-055) and telephone numbers
  - an address's street, city or postal details (REQ-087)
  - which addresses a party uses and for what purpose (REQ-098)
  - who is a contact for an organisation and in what role (REQ-128)
  - which sales territory a state or province belongs to (REQ-108)
- **REQ-152** The business requires that the warehouse **preserve the full history of change** for the items listed in REQ-151, so that any past activity can be reported against the party details that applied at the time. The last-changed timestamp on each record is the only change signal the source provides, and its reliability needs to be confirmed with the operational system owners.
- **REQ-153** **Clarification needed:** the source provides no deletion marker or status flag anywhere in this area. If a party, address or relationship is removed operationally it simply disappears. The business must state whether removals need to be detected and retained.

### Data quality

- **REQ-160** The business needs visibility of **incomplete party records**: people without an email address, without a phone number, or without any address.
- **REQ-161** The business needs visibility of **duplicate people** — the same individual registered more than once under different party numbers. Nothing in the source prevents this, and it directly affects customer counts and campaign accuracy.
- **REQ-162** The business needs visibility of addresses whose **geographic location is missing**, since these cannot be mapped or measured for territory purposes.
- **REQ-163** Where a state or province carries the "no genuine code" flag (REQ-104), reporting should highlight it rather than hide it, as it signals incomplete geographic reference data.
- **REQ-164** Reference lists (address type, contact type, phone number type, country or region, state or province) must be complete: every relationship and address must resolve to a named type, country or region. Unresolvable references are a data quality defect and must be reported.

### Privacy and access

- **REQ-170** This area holds **personal data about identifiable individuals** — names, home addresses, private email addresses, telephone numbers, geographic coordinates, marketing consent, and self-declared demographics including income.
- **REQ-171** Access to person-level detail must be restricted to roles with a legitimate business need. Aggregated reporting (counts by region, by person type, by consent level) should be available more widely.
- **REQ-172** Sign-in credentials must be excluded from all analytical use (REQ-072).
- **REQ-173** Marketing consent (REQ-030) must be respected by every downstream use of the data, including any extract that leaves the warehouse. The distinction between "our company only" and "our company and partners" consent must be carried through to any sharing decision.
- **REQ-174** The business needs to be able to answer, for an individual, what personal data we hold about them across this area — supported by the single view described in REQ-140.

---

## 12. Assumptions, exclusions and open points

**Assumptions**

- The company-wide party number is stable and is never re-used for a different party. This must be confirmed with the operational system owners.
- The "AdventureWorks" name appearing in the consent description is our own company name as used in the operational system.

**Out of scope for this area** — required for full reporting but sourced elsewhere:

- Customer accounts, orders and sales figures
- Employee records: job title, department, pay, hire and termination dates
- Vendor and supplier master data
- Reseller store master data
- Sales territory definitions, names, groups and targets (only the state-to-territory assignment is available here, REQ-107)

**Open points requiring business clarification**

1. What is actually stored in the additional contact information (REQ-040), and is it wanted?
2. What demographic questions are captured, and how should they be segmented (REQ-042)?
3. Which email address is the preferred one when a person has several (REQ-056)?
4. How far back does history need to be kept for consent, names, addresses and contact roles (REQ-152)?
5. Must deletions be detected and retained (REQ-153)?
6. How reliable is the last-changed timestamp as a change-detection signal (REQ-152)?
7. Is there any business need for the sign-in credential record at all, beyond "has an account, yes/no" (REQ-073)?
