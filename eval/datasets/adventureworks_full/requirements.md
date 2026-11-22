# Subject area: Person

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

---

# Subject area: HumanResources

# Business Requirements: Human Resources Data Warehouse

**Prepared by:** Business Analysis, People & Operations
**Scope:** Human Resources operational area — workforce, organisational structure, working patterns, pay history and recruitment candidates
**Status:** Draft for review

---

## 1. Purpose and background

The company designs, manufactures and sells bicycles and related components. Its Human Resources function maintains the operational record of everyone employed by the business: who they are, where they sit in the organisation, which department they work in, which shift they work, what they are paid, and — for people who applied for a job — the candidate record that preceded their employment.

Today that information lives in the operational HR system and is only visible as a *current* picture, or in fragments of history that are hard to combine. The business needs a reporting foundation that can answer questions about the workforce **as it is now and as it was at any point in the past**: headcount by department over time, movement of people between departments and shifts, pay progression, tenure, and the composition of the workforce.

This document describes what the business needs to know. It does not propose how the warehouse should be built.

---

## 2. Scope

**In scope:** departments and their grouping into larger organisational areas; employees and their personal, employment and classification attributes; the corporate reporting hierarchy; the history of employees' departmental and shift assignments; the history of employees' pay rates; the defined working shifts; job candidates and their résumés.

**Out of scope (for this increment):** payroll transactions and actual payments, benefits administration, time and attendance capture, training and certification, performance management, and any customer- or product-facing area of the business. Employee contact details, addresses and person names are held elsewhere in the operational system and are not part of the HR schema supplied for this analysis — see the open questions in section 11.

---

## 3. Business entities in this area

Five business entities are visible, plus two important historical relationships:

| Entity | What it is | Business identifier |
|---|---|---|
| **Employee** | A person employed by the company | National identification number (e.g. social security number), stated to be unique; the employee is also carried under the company-wide business entity number |
| **Department** | An organisational unit people work in | Department name, within its group |
| **Shift** | A defined 8-hour working period | Shift name |
| **Job candidate** | Someone who applied for a role and submitted a résumé | Candidate record number (no natural business key is evident — see open questions) |
| **Pay rate change** | A change to an employee's pay, effective from a date | Employee plus the date the change takes effect |

The two historical relationships are **employee-to-department assignment** (which department and shift a person worked in, between which dates) and **employee pay history** (what a person's rate was, from when).

---

## 4. Employee

### 4.1 Identity

**REQ-001** The business must be able to identify each employee uniquely and consistently across all HR reporting.

**REQ-002** Each employee carries a **national identification number** (such as a social security number), described in the source system as unique. This is the strongest natural business identifier available for a person.

**REQ-003** Each employee is also registered under a company-wide **business entity number**. This number is shared with a broader business-entity register outside the HR area, which indicates that employees are one kind of party among several that the company tracks. The warehouse must be able to reconcile the HR view of a person with that wider register.

**REQ-004** Each employee has a **network login** identifying them in company IT systems. This is useful for joining HR data to system-generated activity, but it is an IT identifier and should not be treated as the business identity of the person.

**REQ-005** The source system also holds a technical row identifier used to support data replication. This carries no business meaning and is not required for reporting.

### 4.2 Employment attributes

**REQ-006** For each employee the business must record the **job title** — the work title such as "Buyer" or "Sales Representative".

**REQ-007** The business must record each employee's **hire date**, being the date they were taken on.

**REQ-008** The business must be able to derive **tenure** (length of service) from the hire date.

**REQ-009** The business must record whether an employee is **salaried or hourly**. This classification also carries an industrial-relations meaning: salaried staff are exempt from collective bargaining, hourly staff are not. Reporting must be able to distinguish the two populations for both cost and labour-relations purposes.

**REQ-010** The business must record whether an employee is currently **active or inactive**. This is the operational statement of whether the person is presently employed.

**REQ-011** Headcount reporting must be able to count only active employees, only inactive employees, or all people ever employed, as the question requires.

### 4.3 Personal attributes

**REQ-012** The business must record each employee's **date of birth**, to support age-profile and workforce-planning analysis.

**REQ-013** The business must record each employee's **gender** (recorded in the source as male or female).

**REQ-014** The business must record each employee's **marital status** (recorded in the source as married or single).

**REQ-015** Date of birth, gender and marital status are personal data. Access to them in the warehouse must be restricted to authorised HR users, and reporting for a wider audience must be possible without exposing them (for example, age bands rather than birth dates). The exact restrictions require a data-protection review — see open questions.

### 4.4 Leave entitlement balances

**REQ-016** The business must record each employee's **available vacation hours**.

**REQ-017** The business must record each employee's **available sick leave hours**.

**REQ-018** These are described as *available* balances — that is, a remaining entitlement at a point in time rather than an accrual or a consumption transaction. They therefore change as leave is taken and as entitlement is granted, and reporting must be clear about the date to which any stated balance applies.

**REQ-019** The business needs the ability to see how leave balances have moved over time, in order to identify unusually high accrued balances and their associated liability. The source area supplied does not contain individual leave bookings, so this can only be observed as a series of balance readings, not reconstructed from transactions.

---

## 5. Organisational hierarchy

**REQ-020** The business must record where each employee sits in the **corporate hierarchy** — that is, who reports to whom, expressed in the source as the employee's position within an organisational structure.

**REQ-021** The business must record the employee's **depth (level) in the hierarchy**, so that reporting can distinguish senior levels from front-line staff and can aggregate to any chosen level.

**REQ-022** The business needs to answer questions about spans of control and reporting lines: how many people report to a given manager directly, and how many report to them in total at all levels below.

**REQ-023** Employees move within the hierarchy — promotions, reorganisations and changes of manager occur. The business needs to see the reporting structure as it stands today and, where the record permits, as it stood previously. The source area only carries the current position for each employee, so the ability to reconstruct past structures depends on capturing changes as they occur.

---

## 6. Department

**REQ-024** The business must maintain a register of **departments** — the organisational units in which people work.

**REQ-025** Each department is known by its **name**, which is how the business refers to it.

**REQ-026** Each department belongs to a **group** — a larger organisational area — identified by the group's name. Examples of what such grouping supports include rolling headcount and cost up from individual departments to broader functions.

**REQ-027** Reporting must be able to aggregate any departmental measure (headcount, pay, movement) to the group level.

**REQ-028** Department names and group memberships can be changed and departments can be created or retired. The business needs to know when a department's details were last changed, and would like to see figures both on today's departmental structure and on the structure in force at the time — the latter requires history to be captured, since the source holds only the current description of each department.

---

## 7. Shifts

**REQ-029** The business must maintain a register of **working shifts**. Each shift represents an eight-hour working period.

**REQ-030** Each shift is known by its **name** (its shift description), which is how the business refers to it.

**REQ-031** For each shift the business must record its **start time** and **end time**.

**REQ-032** Reporting must be able to analyse the workforce by shift — for example, how many people work each shift, in which departments, and how that has changed.

**REQ-033** Shift definitions (name, start time, end time) can be adjusted. Where a shift's times change, the business needs to understand that a person recorded on "Evening shift" in the past may have worked different hours than someone recorded on "Evening shift" today.

---

## 8. Employee assignment to department and shift (history)

This is the central historical relationship in this area and the source of most workforce-movement reporting.

**REQ-034** The business must record, for each employee, **which department they worked in and on which shift**, over time. An employee moves through several departments and shifts during their employment, and each of those assignments must remain visible after it ends.

**REQ-035** Each assignment records the **date the employee started work in the department**.

**REQ-036** Each assignment records the **date the employee left the department**. Where no leaving date is recorded, the assignment is the employee's *current* department. The business must be able to identify current assignments reliably on that basis.

**REQ-037** The business must be able to state, for any given date in the past, which department and shift an employee was working in.

**REQ-038** The business must be able to produce **headcount by department at any point in time**, not merely today.

**REQ-039** The business must be able to report **movement between departments** — transfers in, transfers out, and net change — for any period, by department and by group.

**REQ-040** The business must be able to report **movement between shifts** in the same way.

**REQ-041** The business must be able to measure **how long an employee spends in a department** before moving, and the average length of assignment by department and by group.

**REQ-042** It must be possible for an employee to have held the same department more than once at different times (for example, leaving and later returning). Reporting must treat these as separate assignments rather than merging them.

**REQ-043** The combination of employee, department, shift and start date is how an individual assignment is recognised in the source. Whether an employee may be assigned to more than one department at the same time is not settled by the schema and needs confirmation — see open questions.

---

## 9. Pay history

**REQ-044** The business must record the **pay rate** of each employee and how it has changed over time. An employee's rate changes on defined dates and each change must remain visible.

**REQ-045** Each pay record carries the **date on which the change in pay becomes effective**. This is the business-meaningful date for the change — not the date the record happened to be entered.

**REQ-046** Each pay record carries the **rate**, expressed as an hourly rate in money terms.

**REQ-047** Each pay record carries the **pay frequency**: monthly or biweekly. This tells the business how the employee is actually paid, and must be available for cost-phasing and payroll-cycle analysis.

**REQ-048** The business must be able to state an employee's **rate as at any given date**, by taking the rate whose effective date was most recent on or before that date.

**REQ-049** The business must be able to report **pay progression** for an individual: the sequence of rates, the size of each change, and the interval between changes.

**REQ-050** The business must be able to report **average, minimum and maximum rates** by department, by group, by job title, by shift and by salaried/hourly classification, at a chosen point in time.

**REQ-051** The business must be able to combine pay history with departmental assignment history so that a rate is attributed to the department the employee was actually working in when it applied.

**REQ-052** The business must be able to analyse pay differences across groups of employees (for example between job titles or between departments) in support of pay-equity review. Any such analysis touching gender or other personal attributes is subject to the access restrictions in REQ-015.

**REQ-053** Rates are hourly figures while pay frequency is monthly or biweekly. The conversion from an hourly rate to a periodic cost (contracted hours per period, treatment of salaried staff) is not stated in the source and must be confirmed with Payroll before any cost figure is published — see open questions.

---

## 10. Job candidates

**REQ-054** The business must record **job candidates** — people who applied for a position and whose application is held by HR.

**REQ-055** Each candidate record carries the candidate's **résumé**, held as a structured document rather than as separate fields. The business needs at minimum to know that a résumé exists and to be able to retrieve it; extracting individual facts (education, previous employers, skills) from within the résumé is a separate, larger requirement and is not assumed here.

**REQ-056** A candidate record may be linked to an **employee**, and that link means the applicant **was hired**. Where no employee is linked, the candidate was not hired (or has not been hired yet).

**REQ-057** The business must therefore be able to report on **hiring outcomes**: how many candidates were recorded, how many were subsequently employed, and the conversion rate between the two.

**REQ-058** The business must be able to trace an employed person back to the candidate record that preceded their employment, where one exists. Not every employee will have a candidate record — the source permits employees with no application on file.

**REQ-059** Candidate records contain personal data of people who are not employees. Retention and access rules for them are likely to differ from those for employees and must be established before this data is published — see open questions.

**REQ-060** The source area does not record which position a candidate applied for, an application date, or a rejection reason, so recruitment-funnel reporting beyond the hired/not-hired outcome is not supported by this data.

---

## 11. Change over time and data currency

**REQ-061** Every record in this area carries the **date and time it was last updated** in the operational system. The business needs this so that it can tell how current a given piece of information is, and can identify records that have not been touched for an unexpectedly long time.

**REQ-062** Two kinds of change must be distinguished throughout this area:
- Changes the source system **keeps a history of** — departmental and shift assignments, and pay rates. Here the past is recoverable from the source itself.
- Changes the source system **overwrites** — an employee's job title, marital status, leave balances, active/inactive status, position in the hierarchy, and department and shift descriptions. Here only the current value exists in the source, and any history must be built by observing changes as they occur.

**REQ-063** For the overwritten attributes in REQ-062, the business needs the warehouse to preserve the succession of values so that questions such as "how many people held the title Buyer at the end of last year" become answerable in future, even though they cannot be answered for the past.

**REQ-064** Reporting must clearly distinguish **as-is** figures (using today's department structure and today's employee attributes) from **as-was** figures (using the structure and attributes in force at the time). Both are legitimate and are used for different purposes; presenting one as the other would be misleading.

**REQ-065** The business must be able to reproduce a previously published figure. Once a report has been issued for a period, re-running it must give the same answer, notwithstanding later corrections to the source.

---

## 12. Reporting the business expects to perform

These are illustrative uses that the requirements above must support; they are not an exhaustive report catalogue.

**REQ-066** Headcount and full-time-equivalent style summaries by department, group, shift, job title and salaried/hourly classification, at a chosen date.

**REQ-067** Joiners and leavers by period, derived from hire dates and from the ending of assignments and the active/inactive status.

**REQ-068** Tenure and age profiles of the workforce, in bands.

**REQ-069** Internal mobility: how many people changed department or shift in a period, and the flows between specific departments.

**REQ-070** Pay-rate distribution and progression, by the dimensions listed in REQ-050.

**REQ-071** Accrued vacation and sick-leave balances by department and group, as an indicator of liability.

**REQ-072** Recruitment conversion, per REQ-057.

---

## 13. Open questions requiring clarification

The following cannot be resolved from the schema supplied and must be settled with the business before the data is relied upon.

**Q-01 — Employee names and contact details.** The HR area supplied contains no name, address, telephone number or email address for employees. These are understood to be held in the wider business-entity register that the employee number points to. Confirm where they live and whether they are in scope for this warehouse; most HR reporting at individual level is unusable without a name.

**Q-02 — What identifies a job candidate.** The candidate record has no name, email address or application reference outside the résumé document. Confirm how the business recognises the same person applying twice, and whether any candidate identity can be established at all without opening the résumé.

**Q-03 — Concurrent assignments.** Confirm whether an employee can be assigned to more than one department, or more than one shift, at the same time. This materially affects how headcount by department is counted.

**Q-04 — Meaning of "active".** Confirm the relationship between an employee being marked inactive and their departmental assignment being ended. It is not clear whether a leaver is always reflected in both, nor whether there is a recorded termination date distinct from the end of the last assignment. If there is no termination date, leaver reporting rests on an assumption that must be agreed.

**Q-05 — Rehires.** Confirm how a person who leaves and is later re-employed is handled: one employee record with a gap, or two. This affects tenure, joiner counts and the uniqueness of the national identification number.

**Q-06 — Hourly rate to periodic cost.** Per REQ-053, confirm the standard hours per period and the treatment of salaried staff, so that pay can be expressed as cost.

**Q-07 — Currency.** The rate is held as a money amount with no stated currency. Confirm whether a single currency applies across the whole workforce.

**Q-08 — Leave balance semantics.** Confirm whether vacation and sick-leave hours are a remaining entitlement, an accrued amount, or an annual allowance, and on what cycle they are reset or granted.

**Q-09 — Data protection.** Establish, with the data-protection officer, the access rules for date of birth, gender, marital status, national identification number, pay, and candidate résumés; and the retention rules for candidates who were never hired (REQ-059).

**Q-10 — Historical depth.** Confirm how far back the source's assignment and pay history reliably extends, and from what date the business considers the data trustworthy.

**Q-11 — Reporting hierarchy history.** Confirm whether any record exists of past reporting lines (REQ-023), or whether the warehouse must build that history from the point of go-live onwards.

**Q-12 — Résumé content.** Confirm whether the business wants facts extracted from within the résumé documents (REQ-055). If so, that is a separate piece of work with its own requirements.

---

# Subject area: Production

# Business Requirements: Production and Product Management Data Warehouse

## Document purpose

This document describes what the business needs to know and track in the production and product management area of our bicycle manufacturing and retail operation. It is written from the operational system that supports this area today, and it deliberately stops short of proposing any warehouse design. The intent is to state the business subject matter, the entities involved, what identifies them, what we need to know about them, and how they relate — so that a data modelling specialist can take it from here.

## Scope

The area covered is everything from the definition of a product, through how products are structured and manufactured, where they are stored, what they cost, what we sell them for, how they are described and illustrated for catalogue and marketing purposes, and how inventory moves. It excludes customers, sales orders as such, purchasing and supplier management, and human resources — those areas are owned by other parts of the business and are referenced here only where production data points at them.

This is the largest single area of our operational landscape. Roughly a quarter of the operational tables in the system belong to it.

---

## 1. Product — the central business entity

Everything in this area revolves around the product. A product in our business may be something we manufacture ourselves, something we buy in, a finished sellable item, or a component that never appears in a catalogue.

**REQ-001** The business must be able to identify every product uniquely and unambiguously. Products carry a product number that is stated to be unique — this is the identifier people use when talking about a product in day-to-day work, and it is the natural business key.

**REQ-002** Every product must carry a product name. The name is descriptive and is not guaranteed to be unique; it must not be relied on to identify a product.

**REQ-003** The business must know, for every product, whether it is manufactured in-house or purchased from outside. This is a fundamental distinction: it determines whether the product has a manufacturing route, a bill of materials, and work orders, or whether it arrives via purchasing.

**REQ-004** The business must know whether a product is a salable item or not. Many products in the catalogue are components and sub-assemblies that are never offered to a customer. Reporting on the product portfolio must be able to separate salable finished goods from internal-only items.

**REQ-005** The business must track product colour where it applies. Colour is a genuine merchandising attribute in our range and not all products have one.

**REQ-006** The business must track product size and the unit in which that size is expressed. Size is recorded as a short code or value, and separately the unit of measure that gives it meaning. The two must always be read together.

**REQ-007** The business must track product weight and, separately, the unit in which the weight is expressed. As with size, the weight figure is meaningless without its unit.

**REQ-008** The business must know how many days are required to manufacture a product. This figure supports lead-time planning and promise dates.

**REQ-009** Products are grouped into a product line. The lines recognised in the operational system are Road, Mountain, Touring and Standard. Reporting on the range, on sales performance and on manufacturing load is expected to be possible by product line.

**REQ-010** Products carry a class of High, Medium or Low. The business meaning of this classification is not stated in the source system. It is used in practice but its definition should be confirmed with the product management team before it is used as an analytical dimension.

**REQ-011** Products carry a style of Womens, Mens or Universal. This is a merchandising attribute and should be available for analysis of the range.

**REQ-012** The business must record the standard cost of a product — the cost figure used for costing and margin purposes.

**REQ-013** The business must record the list price of a product — the price at which it is offered for sale.

**REQ-014** The business must be able to compare list price against standard cost in order to understand the margin position of each product.

**REQ-015** The business must record two inventory control parameters for each product: the safety stock level (the minimum inventory quantity we intend to hold) and the reorder point (the inventory level at which a purchase order or a work order is triggered).

**REQ-016** The business must be able to compare actual inventory on hand against the safety stock level and the reorder point, in order to identify products at risk of stock-out and products where a replenishment action is overdue.

### Product lifecycle dates

**REQ-017** The business must know the date from which a product became available for sale.

**REQ-018** The business must know the date from which a product ceased to be available for sale, where that has happened. A product may be current, in which case no such date exists.

**REQ-019** The business must know the date on which a product was discontinued, where applicable. Discontinuation and the end of sale availability are recorded separately in the operational system and should be treated as two distinct business events; product management should confirm the difference in meaning between them.

**REQ-020** The business must be able to report on the active product range as at any point in time, using the sell start and sell end dates — for example, "which products were sellable in March of last year".

---

## 2. Product classification hierarchy

**REQ-021** Products are organised into a two-level classification: a product category, which is subdivided into product subcategories.

**REQ-022** A product category must be identifiable by its name (its description). Categories are the top level of the merchandising hierarchy — in our business these are the broad groupings such as bikes, components, clothing and accessories.

**REQ-023** A product subcategory must be identifiable by its name and must be known to belong to exactly one product category.

**REQ-024** A product belongs to at most one subcategory. Not every product is placed in a subcategory — components and internal items may sit outside the merchandising hierarchy entirely. Reporting must handle unclassified products gracefully rather than dropping them.

**REQ-025** The business must be able to roll up any product-level measure — inventory, cost, price, transaction volume, scrap — to subcategory and then to category level.

---

## 3. Product models

A product model is the design a product is built to. Several individual products — different sizes and colours of the same bicycle, for instance — can share one model.

**REQ-026** The business must be able to identify a product model by its name.

**REQ-027** A product belongs to at most one product model. As with subcategory, not every product has one.

**REQ-028** The business must be able to group and report products by product model, as this is the level at which design, catalogue content and manufacturing instructions are held.

**REQ-029** Detailed catalogue information is held at product model level, in a structured document format. The business needs this content available for catalogue and web publication purposes.

**REQ-030** Manufacturing instructions are held at product model level, also in a structured document format. Manufacturing and quality teams need access to the instructions that apply to a given model. Because these are structured documents rather than simple fields, the level of detail that can be extracted from them needs to be scoped separately with the manufacturing engineering team.

---

## 4. Product descriptions, cultures and multilingual catalogue content

**REQ-031** The business maintains a library of product descriptions — free-text marketing descriptions of products, held independently of any one product.

**REQ-032** The business maintains a list of cultures (language and locale designations), each identified by a short culture code and carrying a descriptive name.

**REQ-033** A product model is associated with a product description in a specific culture. This is how our catalogue supports multiple languages: the same model has different descriptions for different markets.

**REQ-034** The business must be able to report which models have catalogue descriptions in which cultures, and specifically which models are missing a description in a culture we sell into. This is a content-completeness question the marketing team needs answered.

**REQ-035** The combination of model, description and culture is the meaningful business fact. A description on its own tells us little; it becomes useful when we know which model it describes and in which language.

---

## 5. Product photography

**REQ-036** The business maintains a library of product photographs. Each photograph exists in a small (thumbnail) and a large version, and each version has its own image file and file name.

**REQ-037** A product may have several photographs, and a photograph may be used for more than one product.

**REQ-038** For each product, one photograph is designated the principal image. The business must be able to identify the principal image for a product, since this is the one used as the lead image in the catalogue and on the web.

**REQ-039** The business must be able to identify products that have no photograph at all, and products that have photographs but no designated principal image. Both are content gaps that marketing needs to close.

---

## 6. Illustrations

**REQ-040** The business maintains a set of illustrations used in manufacturing instructions. These are technical diagrams held in a structured format.

**REQ-041** An illustration is associated with one or more product models, and a product model may have several illustrations.

**REQ-042** The business must be able to determine which illustrations support which product models, so that manufacturing documentation can be assembled and kept complete.

---

## 7. Documents and engineering change control

The operational system holds a controlled document library. It is organised hierarchically — documents sit inside folders — and it carries approval and revision control.

**REQ-043** The business must be able to identify each document in the library and know its title.

**REQ-044** The business must know whether an entry in the library is a folder or an actual document, and must be able to reconstruct the folder structure, since documents are organised in a hierarchy and their depth in that hierarchy is recorded.

**REQ-045** Each document has an owner, who is an employee. The business must be able to report on documents by owner — for example, to find documents whose owner has left the company. Employee master data is owned outside this area and must be sourced from there.

**REQ-046** Each document carries a revision number. The business must be able to see which revision of a document is current.

**REQ-047** Each document is associated with an engineering change approval number. The business must be able to trace documents to the engineering change that authorised them.

**REQ-048** Each document has an approval status of Pending approval, Approved or Obsolete. The business must be able to report on documents by status — in particular, to find documents pending approval and documents still in circulation that are marked obsolete.

**REQ-049** Each document carries a file name and a file extension indicating its type (for example a word-processing document or a plain text file). The business needs to know the document type for archiving and access purposes.

**REQ-050** Each document has a short abstract or summary, distinct from the full document content. The summary is what most business reporting needs; the full binary document content is generally not required in analytical reporting and its inclusion should be confirmed rather than assumed.

**REQ-051** Documents are linked to products. A product may have several associated documents (assembly instructions, specifications, safety notices), and a document may apply to several products.

**REQ-052** The business must be able to identify manufactured products that have no associated document, as a documentation-completeness check.

---

## 8. Bill of materials — how products are assembled

This is one of the most important structures in the area: it describes how our products are put together from other products.

**REQ-053** A product may be assembled from other products. The business must be able to record, for a given assembly, which products are components of it.

**REQ-054** Both sides of an assembly relationship are products in their own right. A component in one assembly may itself be an assembly of further components, so the structure is recursive and can be several levels deep.

**REQ-055** The business must know, for each component in an assembly, the quantity of that component needed to make one of the assembly item.

**REQ-056** The business must know the unit of measure in which that component quantity is expressed. Quantity without unit is not actionable.

**REQ-057** The business must know how deep a component sits below its parent assembly — the level in the bill of materials. This supports both explosion of a bill of materials to raw components and summary reporting at a chosen level.

**REQ-058** Bill of materials relationships change over time. Each component-in-assembly relationship carries the date the component started being used in the assembly and the date it stopped being used. The business must therefore be able to answer "what was this product made of on a given date", not only "what is it made of now".

**REQ-059** The business must be able to identify currently active bill of materials relationships — those that have started and have not yet ended — as the default view for planning and costing.

**REQ-060** The business must be able to see component substitutions over time: where one component stopped being used in an assembly on a date and another started, this is a design change the engineering and cost teams need visibility of.

**REQ-061** The business must be able to determine, for any component, all the assemblies it is used in ("where used"), in order to assess the impact of a component shortage, price change or quality problem.

**REQ-062** The business must be able to cost an assembly from the costs of its components and the quantities required, and to compare that built-up cost with the assembly's recorded standard cost.

---

## 9. Units of measure

**REQ-063** The business maintains a standard list of units of measure, each identified by a short code and carrying a descriptive name.

**REQ-064** Units of measure are used in several places: the quantity of a component in an assembly, the unit for a product's size, and the unit for a product's weight. The same standard list serves all of them.

**REQ-065** All quantity and dimension reporting must present the unit alongside the figure, and must never aggregate figures expressed in different units without conversion. Whether conversion factors between units exist anywhere in the business needs clarification — they are not held in this system.

---

## 10. Manufacturing locations

**REQ-066** The business operates a number of manufacturing locations, each identified by a name. In practice these are the shop floors and work centres within our plant.

**REQ-067** Each location has a standard hourly cost rate. This is the rate used to cost the time products spend at that location.

**REQ-068** Each location has a stated work capacity expressed in hours. The business must be able to compare actual hours consumed at a location against its stated capacity, in order to identify bottlenecks and under-used capacity.

**REQ-069** Locations serve two distinct purposes in the business: they are where manufacturing operations are performed, and they are where inventory is held. Reporting must be able to address both uses of the same location.

---

## 11. Inventory

**REQ-070** The business must know the quantity of each product held at each location.

**REQ-071** Within a location, stock is stored in a specific shelf, and within a shelf, in a specific bin. The business must be able to report inventory down to shelf and bin level, since this is what stock-picking and stock-counting operations work with.

**REQ-072** The same product may be held at several locations, and a location holds many products. The meaningful business fact is the quantity of a given product at a given location in a given shelf and bin.

**REQ-073** The business must be able to total inventory for a product across all locations, and to total inventory at a location across all products.

**REQ-074** The business must be able to value inventory by combining quantities on hand with the applicable standard cost of the product.

**REQ-075** The operational system holds the current inventory position, not a history of it. If the business needs to report inventory levels as at past dates, that history has to be built by capturing the position over time — this is an explicit expectation on the warehouse and should be confirmed as a requirement with the supply chain team.

---

## 12. Work orders — manufacturing execution

**REQ-076** The business raises work orders to manufacture products. Each work order must be uniquely identifiable and must state which product is being made.

**REQ-077** Each work order states the quantity ordered.

**REQ-078** Each work order records the quantity actually stocked — that is, the good output that reached inventory.

**REQ-079** Each work order records the quantity scrapped.

**REQ-080** The business must be able to calculate and report a scrap rate: scrapped quantity against ordered quantity, by product, by product line, by category and over time. Scrap is a direct cost and a quality signal.

**REQ-081** Where a quantity was scrapped, the work order records a scrap reason. The business maintains a standard list of scrap reasons, each carrying a failure description.

**REQ-082** The business must be able to report scrap volumes and scrap costs by scrap reason, in order to prioritise quality improvement effort.

**REQ-083** Not every work order has a scrap reason — a work order completed without scrap will have none. Reporting must handle this.

**REQ-084** Each work order records a start date, an end date and a due date. The business must be able to report on manufacturing lead time (start to end) and on schedule adherence (end against due).

**REQ-085** The business must be able to identify work orders that are open — started but not ended — and work orders that are overdue against their due date.

**REQ-086** The business must be able to report work order volume and output over time, by product and by product grouping.

---

## 13. Work order routing — operations on the shop floor

A work order is executed as a sequence of operations, each performed at a location.

**REQ-087** Each work order is broken down into a sequence of operations. The business must know the sequence number of each operation, since the order in which they are performed is meaningful.

**REQ-088** Each operation is performed at a manufacturing location. The business must be able to report the manufacturing workload falling on each location.

**REQ-089** Each operation carries a scheduled start date and a scheduled end date.

**REQ-090** Each operation carries an actual start date and an actual end date. Both scheduled and actual must be retained: the comparison between them is the basis of schedule adherence reporting at the operation level.

**REQ-091** The business must be able to identify operations that are scheduled but not yet started, started but not yet finished, and completed, based on the presence of the actual dates.

**REQ-092** Each operation records the actual resource hours consumed. The business must be able to compare hours consumed at a location against that location's stated capacity.

**REQ-093** Each operation carries a planned cost and an actual cost. The business must be able to report cost variance at operation level, at work order level, at product level and at location level.

**REQ-094** The business must be able to combine actual resource hours with the location's standard hourly cost rate to understand how operation costs arise, and to reconcile that against the recorded actual cost.

**REQ-095** The business must be able to roll up all operations of a work order to give a total manufactured cost for that work order, and to compare it against the standard cost of the product manufactured.

**REQ-096** Each operation identifies the product being manufactured as well as the work order. The two are expected to agree; any disagreement is a data quality issue that should be flagged.

---

## 14. Cost history

**REQ-097** The standard cost of a product changes over time. The business maintains a history of standard cost for each product, with a start date and an end date defining the period during which each cost applied.

**REQ-098** The business must be able to determine the standard cost that applied to a product on any given date, not just the cost that applies now.

**REQ-099** The current standard cost period is the one with no end date. The business must be able to identify the currently applicable cost for every product.

**REQ-100** The business must be able to report cost movements over time — how the standard cost of a product, a product line or a category has changed, and by how much.

**REQ-101** The current product record also carries a standard cost figure. The business expects this to agree with the currently applicable entry in the cost history; a reconciliation between the two is required and any disagreement must be reported as a data quality issue.

**REQ-102** Historic transactions must be valued using the cost applicable at the time of the transaction, not today's cost, wherever the business is analysing margin or manufacturing cost over a period.

---

## 15. List price history

**REQ-103** The list price of a product changes over time. The business maintains a history of list price for each product, with a start date and an end date defining the period during which each price applied.

**REQ-104** The business must be able to determine the list price that applied to a product on any given date.

**REQ-105** The current list price period is the one with no end date. The business must be able to identify the currently applicable price for every product.

**REQ-106** The business must be able to report price movements over time — the frequency, size and direction of price changes by product, product line and category.

**REQ-107** As with cost, the current product record also carries a list price, and this is expected to agree with the currently applicable entry in the price history. A reconciliation is required.

**REQ-108** The business must be able to analyse margin over time by combining the list price applicable on a date with the standard cost applicable on the same date. Cost history and price history are maintained independently and their periods do not necessarily align, so margin analysis must handle overlapping but non-identical periods.

---

## 16. Inventory transactions

Every movement of stock is recorded as a transaction. This is the movement history behind the current inventory position.

**REQ-109** The business must be able to identify each inventory transaction uniquely.

**REQ-110** Each transaction states the product involved, the quantity moved, and the date and time it occurred.

**REQ-111** Each transaction states its type: work order, sales order or purchase order. The business must be able to separate manufacturing movements, outbound sales movements and inbound purchase movements.

**REQ-112** Each transaction refers to the originating order and to the specific line on that order. Depending on the transaction type, this refers to a work order, a sales order or a purchase order. The business must be able to trace a stock movement back to the document that caused it. Note that the order reference alone is ambiguous — it must always be read together with the transaction type to know which kind of order is meant.

**REQ-113** Each transaction carries an actual cost. The business must be able to value stock movements at the cost actually applied, and to report cost of goods manufactured, sold and purchased on that basis.

**REQ-114** The business must be able to reconcile the net effect of transactions for a product against the current inventory quantity held for that product, as a data quality and stock-accuracy control.

**REQ-115** Transactions do not record a location. Movement history is therefore available at product level but not at location level; if location-level movement analysis is required, this is a gap that needs raising with the operational system owners.

**REQ-116** The business must be able to report transaction volume and value over time, by product, product grouping, and transaction type.

### Archived transactions

**REQ-117** Older inventory transactions are moved out of the live operational store into an archive. The archive holds the same information as the live store: transaction identifier, product, order reference and line, date, type, quantity and actual cost.

**REQ-118** For long-run historical analysis, the business must be able to see live and archived transactions as one continuous history. Reporting that covers a multi-year period and looks only at the live store will silently under-report.

**REQ-119** The business needs clarity on the rule that governs when a transaction is archived, and confirmation that a transaction exists in exactly one of the two stores at any time and is never counted twice. This should be established with the operational system owners.

---

## 17. Product reviews

**REQ-120** Customers submit reviews of products. The business must be able to identify each review and know which product it relates to.

**REQ-121** Each review records the name of the reviewer, their e-mail address and the date the review was submitted.

**REQ-122** Each review carries a rating on a scale of one to five, with five the highest.

**REQ-123** Each review carries free-text comments from the reviewer.

**REQ-124** The business must be able to report average rating and review volume by product, by product model, by subcategory and by category, and to track how ratings move over time.

**REQ-125** The business must be able to identify products with consistently low ratings, so that quality and product management can act on them, and to relate poorly rated products to their scrap and manufacturing cost history.

**REQ-126** Reviewer e-mail addresses are personal data. Any use of review data in reporting must respect data protection obligations; how reviewer identity is handled in analytical reporting needs to be agreed with the data protection officer before this data is published in reports.

**REQ-127** Reviewers are identified only by name and e-mail address, with no link to our customer master. Whether a reviewer can or should be matched to a known customer is an open question for the customer data owners and is out of scope here.

---

## 18. Cross-cutting requirements

**REQ-128** Every record in the operational system carries the date and time it was last updated. The business needs this to understand the currency of the data it is looking at, and to detect records that have not been maintained.

**REQ-129** The business must be able to report the "as at" date of any figure presented, so that users know what point in time a report reflects.

**REQ-130** Historical accuracy matters in this area. Bills of materials, standard costs and list prices all change, and the operational system keeps history for each. Analysis of past periods must use the values that applied at the time, and must not be silently restated when a cost, price or assembly structure changes.

**REQ-131** Several relationships in this area are optional: a product may have no subcategory, no model, no photograph, no document, no review, and no bill of materials. Reporting must treat these absences as legitimate business situations, not as errors, while still being able to report on them as completeness gaps where that is the question being asked.

**REQ-132** Several relationships are many-to-many: products to documents, products to photographs, models to illustrations, and models to descriptions by culture. Each of these associations is a business fact in its own right and needs to be retained as such.

**REQ-133** Two references in this area point outside the production area entirely — the owner of a document is an employee, and inventory transactions refer to sales orders and purchase orders. The business needs these to join up with the human resources, sales and purchasing areas of the warehouse when those are built. Until then, they can only be reported as identifiers.

**REQ-134** Some content in this area is held as structured documents or as binary content rather than as simple fields: catalogue descriptions, manufacturing instructions, illustration diagrams, photograph images and full document content. What of this is genuinely needed for business reporting, and at what level of detail, needs to be agreed with marketing and manufacturing engineering rather than assumed.

**REQ-135** Where the operational system carries technical record identifiers that have no business meaning, these are of no interest to the business and should not surface in business reporting.

---

## Open questions requiring clarification

The following points could not be resolved from the operational system alone and need to be settled with the relevant business owners before the design work proceeds:

1. The business meaning of the product **Class** attribute (High / Medium / Low) — REQ-010.
2. The difference in meaning between a product's **sell end date** and its **discontinued date** — REQ-019.
3. Whether the business needs **historical inventory positions**, which the operational system does not keep — REQ-075.
4. Whether **conversion factors between units of measure** exist anywhere in the business — REQ-065.
5. The **archiving rule** for inventory transactions, and confirmation that a transaction is never in both stores — REQ-119.
6. The absence of a **location on inventory transactions**, and whether location-level movement analysis is needed — REQ-115.
7. Handling of **reviewer personal data** in analytical reporting — REQ-126, and whether reviewers should be matched to customers — REQ-127.
8. How much of the **structured and binary content** (catalogue XML, manufacturing instructions, illustrations, images, document bodies) is needed for reporting — REQ-134.
9. The level of detail that can usefully be extracted from **manufacturing instructions** held as structured documents — REQ-030.

---

# Subject area: Purchasing

# Business Requirements: Purchasing and Vendor Management Data Warehouse

## 1. Purpose and Scope

This document describes what the business needs to be able to see and analyse in the **purchasing area** of our bicycle manufacturing and retail operation. It covers the vendors we buy from, the products they supply to us, the purchase orders we place, what actually arrives against those orders, and the shipping methods used to get goods to us.

It is written from the operational purchasing system as it exists today. It states the business need only — how the warehouse is designed and modelled is a separate exercise.

Out of scope: sales to customers, manufacturing, inventory movements after goods are accepted, and finance/payables. Those areas touch purchasing but are not described here.

## 2. Business Context

We buy components and finished goods from external companies (vendors). Purchasing staff raise purchase orders with a chosen vendor, listing one or more products with quantities and agreed prices. The vendor ships against the order using an agreed shipping company; goods arrive, are inspected, and either accepted into stock or rejected. Alongside individual orders, we maintain a standing commercial relationship per vendor and product — typical price, typical lead time, and the order quantity limits we have agreed.

The business needs a single, historically complete view of this activity to answer questions about supplier performance, purchasing spend, delivery reliability, and quality of received goods.

## 3. Business Entities

### 3.1 Vendor

REQ-001 The warehouse must record every **vendor** — a company from which we purchase goods.

REQ-002 A vendor is identified in business terms by its **vendor account number**, the identification number by which purchasing staff and vendor correspondence refer to the company. The operational system also carries an internal business entity identifier for each vendor; both must be retained, since the internal identifier is what other purchasing records point to.

REQ-003 The **vendor's company name** must be recorded and reportable.

REQ-004 Each vendor carries a **credit rating** on a five-point scale, from *Superior* through *Excellent*, *Above average* and *Average* to *Below average*. Reporting must present this rating in its business wording, not as a bare code.

REQ-005 Each vendor carries a **preferred vendor status**: either "preferred over other vendors supplying the same product" or "do not use if another vendor is available". Purchasing management needs to see whether orders are in fact being placed with preferred vendors.

REQ-006 Each vendor carries an **active flag** indicating whether the vendor is still actively used or is no longer used. Vendors that are no longer used must remain in the warehouse — historical orders placed with them must stay reportable.

REQ-007 Where a vendor offers an electronic purchasing interface, the **purchasing web service address** must be recorded. This attribute is not always populated; reporting must tolerate its absence.

REQ-008 Vendor attributes change over time. Credit rating, preferred status and active flag in particular are commercial judgements that are revised. The warehouse must retain the history of these changes so that the state of a vendor **at the time an order was placed** can be reconstructed, not only the current state.

> *Clarification needed:* the source records only the date a vendor record was last updated, not the individual reasons for change. Whether the business needs the *reason* for a credit rating or preferred-status change, and from where that would come, needs to be confirmed with purchasing management.

### 3.2 Product supplied by a vendor (the supply relationship)

REQ-009 The warehouse must record, for each combination of **a product and a vendor**, the standing commercial terms under which we buy that product from that vendor. The same product may be supplied by several vendors, and a vendor supplies several products.

REQ-010 This supply relationship is identified in business terms by the pairing of the product and the vendor.

REQ-011 The **average lead time** must be recorded: the average span of time, in days, between placing an order with that vendor and receiving the purchased product. This is a key input to purchasing planning and to supplier comparison.

REQ-012 The **standard price** — the vendor's usual selling price for that product — must be recorded.

REQ-013 The **last receipt cost** — the selling price when the product was last purchased from that vendor — and the **last receipt date** — the date the product was last received from that vendor — must both be recorded. Together with the standard price these let the business see price drift between the agreed and the actually paid price.

REQ-014 The agreed **minimum and maximum order quantities** for the product from that vendor must be recorded, so that buyers and reporting can see whether orders respect the agreed bounds.

> *Note on a source inconsistency:* in the operational system the descriptions of the minimum and maximum order quantity fields are transposed — the field named as the minimum is described as "the maximum quantity that should be ordered" and vice versa. Which field carries which meaning must be confirmed with the purchasing team before either is used in reporting or in any threshold check.

REQ-015 The **quantity currently on order** for the product from that vendor must be available, as an indicator of open commitment.

REQ-016 The **unit of measure** in which the product is bought from that vendor must be recorded. The same product may plausibly be bought in different units from different vendors, so quantities and prices must always be interpreted together with this unit.

REQ-017 The supply terms change over time — prices are renegotiated, lead times improve or deteriorate, and quantity bounds are adjusted. The warehouse must retain this history so that trends in agreed price and lead time per vendor and product can be analysed.

REQ-018 The quantity on order and the last receipt figures are, by their nature, running values that are updated as activity occurs. Reporting must be clear about whether it is showing the current value or the value as at a point in time.

REQ-019 Products themselves are maintained outside the purchasing area. The warehouse must nonetheless be able to identify each purchased product consistently and to join purchasing activity to the wider product information held elsewhere.

### 3.3 Purchase order

REQ-020 The warehouse must record every **purchase order** we place with a vendor.

REQ-021 A purchase order is identified in business terms by its **purchase order number**.

REQ-022 Each purchase order is **placed with exactly one vendor** — the vendor with whom the order is placed.

REQ-023 Each purchase order is **created by one employee**, the buyer who raised it. The warehouse must be able to report purchasing activity by the employee who created the order.

> *Note:* employee master data is maintained outside the purchasing area. Only the identity of the creating employee is available here; name, department and role must come from the HR/employee area if the business wants to report on them.

REQ-024 Each purchase order names a **shipping method** — the shipping company and rate agreement used to bring the goods to us.

REQ-025 Each purchase order carries an **order date**, the date the order was created.

REQ-026 Each purchase order carries an **estimated shipment date** — the date the vendor is expected to ship. The business needs to compare this expectation against actual receipt activity.

REQ-027 Each purchase order carries a **status**, which is one of *Pending*, *Approved*, *Rejected* or *Complete*. Reporting must present the status in business wording. The business needs to see the population of orders in each status, in particular orders that are approved but not yet complete.

REQ-028 Each purchase order carries a **revision number**, an incrementing counter tracking how the order has changed over time. The business needs to know that an order was revised and how many times — a frequently revised order is a signal about the order or the vendor relationship.

REQ-029 The warehouse must retain the **history of a purchase order as it changes**: status transitions (for example Pending → Approved → Complete) and revisions must be traceable over time, not overwritten by the latest state. The business needs to answer "when was this order approved?" and "how long did it sit pending?".

> *Clarification needed:* the operational system holds only the current version of an order together with its revision number and last-updated date; it does not appear to keep prior versions. Whether the warehouse can reconstruct a full revision history depends on how frequently the source is captured, and the business expectation on this needs to be agreed.

REQ-030 Each purchase order carries financial totals: a **subtotal** (the sum of the value of its lines), a **tax amount**, a **freight (shipping cost)** amount, and a **total due to the vendor** (subtotal plus tax plus freight).

REQ-031 The business must be able to analyse **purchasing spend** by vendor, by employee, by shipping method, and over time, using these order totals.

REQ-032 Because the subtotal and total due are derived from the order lines and the other charges, the warehouse must be able to demonstrate that the totals it reports are consistent with the underlying lines. Any discrepancy between the stated order total and the sum of its lines is itself a finding the business wants to see.

REQ-033 Freight and tax are order-level charges and are **not** attributed to individual products in the source. If the business wants product-level landed cost, the basis for allocating freight and tax across lines must be decided by the business; it cannot be derived from the source as it stands.

### 3.4 Purchase order line

REQ-034 Each purchase order **contains one or more lines**, one per purchased product.

REQ-035 A line is identified in business terms by the purchase order it belongs to together with its **line number**.

REQ-036 Each line refers to **exactly one product**.

REQ-037 Each line carries the **quantity ordered**.

REQ-038 Each line carries the **unit price**, the vendor's selling price for a single unit of that product on this order.

REQ-039 Each line carries a **line total** — the ordered quantity multiplied by the unit price.

REQ-040 Each line carries a **due date**, the date on which the product is expected to be received. Note that this expectation is held per line, so different products on the same order may be expected at different times; delivery-performance analysis must work at line level, not only at order level.

REQ-041 The business must be able to compare the **unit price actually paid on a line** with the **standard price agreed** for that product and vendor, to identify off-contract purchasing.

### 3.5 Receipt and inspection against a line

REQ-042 Each purchase order line records the **quantity actually received** from the vendor.

REQ-043 Each line records the **quantity rejected during inspection**.

REQ-044 Each line records the **quantity accepted into inventory**, being the received quantity less the rejected quantity.

REQ-045 The business must be able to measure, per line, per order, per product and per vendor, the **fulfilment gap** between what was ordered and what was received, including under-delivery and over-delivery.

REQ-046 The business must be able to measure **inspection reject rates** — rejected quantity as a share of received quantity — by vendor and by product, as the primary indicator of incoming quality.

REQ-047 Receipt and rejection quantities accumulate as goods arrive and are inspected; a line's received quantity may change over the life of the order. The warehouse must retain this progression so that "how much had been received as at a given date" can be answered, and so that partial deliveries are visible rather than only the final position.

> *Clarification needed:* the source records only cumulative received, rejected and accepted quantities per line, together with a last-updated date. It does not record individual receipt events, receipt dates, or inspection outcomes per delivery. If the business needs to analyse individual deliveries (for example, how many part-shipments made up an order line, or the date of each), that information must be sourced elsewhere or the requirement dropped.

REQ-048 The business must be able to compare the **due date on a line** against evidence of when goods were actually received, in order to measure **on-time delivery** by vendor. Given the limitation noted above, the practical measure of actual receipt timing available today is the last receipt date held on the vendor–product supply relationship; whether that is a sufficient basis for an on-time-delivery metric needs to be agreed with the business.

REQ-049 The business must be able to compare **actual elapsed time from order to receipt** against the **average lead time** recorded for that vendor and product, to validate whether recorded lead times are realistic.

### 3.6 Shipping method

REQ-050 The warehouse must record every **shipping method** available for inbound purchases.

REQ-051 A shipping method is identified in business terms by the **shipping company name**, and by an internal shipping method identifier used on purchase orders.

REQ-052 Each shipping method carries a **minimum shipping charge (ship base)** and a **charge per pound (ship rate)**. These are the terms on which freight is expected to be charged.

REQ-053 The business must be able to analyse **freight cost by shipping method**, and to compare the freight actually charged on orders against the base and per-pound rates agreed with the shipping company.

REQ-054 Shipping rates change over time. The warehouse must retain the history of ship base and ship rate so that freight charged on a historical order can be assessed against the rates in force at that time.

REQ-055 The source system carries a technical replication identifier on shipping method records. It carries no business meaning and is not required for reporting.

## 4. How the Entities Relate

Stated in business terms, the picture is:

- A **vendor** supplies one or more **products**, and a product may be supplied by more than one vendor. Each such supply relationship carries its own agreed price, lead time and order quantity bounds.
- A **purchase order** is placed with exactly one **vendor**, is created by one **employee**, and specifies one **shipping method**.
- A purchase order **contains one or more lines**; each line is for exactly one **product** and carries its own quantity, price and expected due date.
- Receipt and inspection outcomes attach to the **line**, not to the order as a whole.
- The products bought on an order's lines are normally, but not necessarily, products for which a supply relationship with that vendor exists. Where a line names a product with no recorded supply relationship for that vendor, that is a finding the business wants surfaced rather than a data error to be hidden.

## 5. Cross-Cutting Requirements

REQ-056 Every record in the purchasing source carries a **last-modified date and time**. The warehouse must use these to establish when information changed and must not present a value as current when a more recent change exists.

REQ-057 All monetary amounts in this area are held in a single currency in the source; no currency indicator is present. If the business buys from vendors in other currencies, the currency of purchase orders and prices needs to be clarified — it cannot be established from the schema.

REQ-058 Codes with defined business meanings — purchase order status, vendor credit rating, preferred vendor status, active flag — must be presented in reporting in their business wording. The mapping must be held once and applied consistently.

REQ-059 Quantities must always be interpreted together with the unit of measure recorded on the relevant vendor–product supply relationship. Aggregating quantities across products or across units of measure without regard to the unit produces meaningless figures and must be prevented in reporting.

REQ-060 Records that no longer represent current operational reality — inactive vendors, completed or rejected orders, discontinued supply relationships — must be retained in full. Purchasing analysis is largely historical; nothing may be physically removed because it has ceased to be current.

## 6. Open Points for the Business

1. The transposed minimum/maximum order quantity descriptions (REQ-014) must be resolved before either value is used.
2. Whether individual receipt and inspection events are needed, and if so where they can be sourced (REQ-047, REQ-048).
3. Whether prior versions of a purchase order are needed, or whether the revision counter and current state suffice (REQ-029).
4. Whether purchasing is single-currency (REQ-057).
5. Whether freight and tax need allocating to product level, and on what basis (REQ-033).
6. Which employee attributes are needed for buyer reporting, from the employee area (REQ-023).

---

# Subject area: Sales

# Business Requirements: Sales Data Warehouse

**Area:** Sales operations — customers, sales orders, sales force, territories, pricing/promotions, currency and tax
**Author:** Business Analysis
**Status:** Draft for review
**Basis:** Technical schema of the `Sales` area of the operational system (19 tables), including the column descriptions maintained in that system.

---

## 1. Purpose and scope

The company sells bicycles and related products through two distinct channels: directly to individual consumers who order online, and through reseller stores served by our own sales representatives. Today, the operational sales system holds the record of what was sold, to whom, by whom, at what price, in which territory and in which currency — but that record is only usable transaction by transaction. The business needs a consolidated, historical view of sales activity for reporting, performance management and planning.

This document describes **what the business needs to know and track** in the sales area. It does not propose how that information should be stored or modelled.

### 1.1 In scope

- Customers (both individual consumers and reseller stores) and their commercial identity
- Sales orders and their individual order lines
- The reasons customers give for buying
- The sales force: representatives, their quotas, their bonuses and commissions, and their territory assignments
- Sales territories and their commercial performance
- Special offers and discounts, and which products they apply to
- Currencies, currency exchange rates and the currencies in which each country/region trades
- Sales tax rates by state/province and transaction type
- Payment instruments (credit cards) and their association with people
- Online shopping cart activity

### 1.2 Out of scope but referenced

The sales area repeatedly refers to information that is maintained elsewhere in the operational system and is **not** part of this schema. These references must be preserved so the sales information can later be joined to those areas, but the source data itself is owned by other domains:

- **Products** — order lines, shopping cart items and special offers all reference a product; product master data (name, category, cost, colour, size) is not in this area.
- **People and business entities** — a customer, a sales representative and a credit-card holder are all identified by a business entity/person reference maintained in a person/HR area.
- **Employees** — a sales representative is an employee; employment attributes are held elsewhere.
- **Addresses** — billing and shipping addresses on an order are referenced, not held here.
- **Shipping methods** — an order names a shipping method that is defined elsewhere.
- **Countries/regions and states/provinces** — territories, currency assignments and tax rates all reference a geography master maintained elsewhere.

> **Clarification needed (C-01):** The boundary of the warehouse programme has not been agreed. This document covers only the sales area; whether products, people and geography are delivered in the same increment must be decided, because several sales reports (e.g. revenue by product category) cannot be produced from sales data alone.

---

## 2. Business entities

This section describes the things the business deals with in this area, how each is identified in business terms, and what the business needs to know about each.

### 2.1 Customer

The company recognises a single notion of "customer" that covers two quite different commercial relationships. A customer is either an **individual person** who buys directly, or a **reseller store** that buys from us to sell on. Every customer is assigned an account number by the accounting system, and every customer is located in a sales territory.

- **REQ-001** The business must be able to identify every customer by the **customer account number** assigned by the accounting system, which is described as uniquely identifying the customer.
- **REQ-002** The business must be able to distinguish an **individual-person customer** from a **store customer**, because the two are served, priced and reported on differently.
- **REQ-003** For an individual customer, the business must retain the reference to the **person** who is the customer.
- **REQ-004** For a store customer, the business must retain the reference to the **store**.
- **REQ-005** The business must know the **sales territory in which each customer is located**.
- **REQ-006** The business must know when a customer's record was last changed in the operating system, so that reporting can be reconciled against the source.
- **REQ-007** The business must be able to report the customer base by territory, and by customer kind (individual vs. store).

> **Clarification needed (C-02):** The schema allows a customer to carry either a person reference or a store reference. It does not state whether both may be populated at once, nor whether either may be absent. The business rule ("a customer is exactly one of person or store") needs to be confirmed with the sales operations team before reporting relies on it.

### 2.2 Store (reseller)

A store is a reseller business that buys from us. Stores are named businesses, are assigned a sales representative, and we hold a demographic profile of each one.

- **REQ-008** The business must be able to identify each **store by its business entity reference**, and must record its **store name**.
- **REQ-009** The business must know **which sales representative is assigned to each store**, since reseller relationships are managed by a named individual.
- **REQ-010** The business must retain the **store demographics** captured for each store. The schema describes this as covering the number of employees, annual sales and store type.
- **REQ-011** The business must be able to segment reseller performance by store demographic characteristics (e.g. store size or store type).

> **Clarification needed (C-03):** Store demographics are held in a structured document rather than as individual columns. The specific demographic attributes the business wants to report on must be listed explicitly, so they can be extracted; "annual sales", "number of employees" and "store type" are named in the schema description but the full set is not visible.

> **Clarification needed (C-04):** The schema describes the store identifier as a foreign key to the customer, while the customer also refers to the store. The direction of this relationship — and therefore whether every store is necessarily a customer — needs confirmation.

### 2.3 Sales order

A sales order is the central business event of this area. It is placed by a customer, it may be placed online by the customer or entered by a sales representative, it is fulfilled to a shipping address, and it carries the money.

- **REQ-012** The business must identify every order by its **sales order number**, which the schema describes as a unique sales order identification number.
- **REQ-013** The business must know **which customer placed each order**.
- **REQ-014** The business must know **whether the order was placed online by the customer or entered by a sales representative**, since this distinguishes the two sales channels.
- **REQ-015** For orders that were not placed online, the business must know **which sales representative created the order**.
- **REQ-016** The business must know **the territory in which each sale was made**. This is recorded on the order itself and is not necessarily the same as the customer's own territory or the representative's current territory — all three are held separately and reporting must be explicit about which is meant.
- **REQ-017** The business must track the **order lifecycle dates**: the date the order was created, the date it is due to the customer, and the date it was shipped.
- **REQ-018** The business must track the **current status of an order** using the operational status values: in process, approved, backordered, rejected, shipped, cancelled.
- **REQ-019** The business must be able to measure **order fulfilment performance**, i.e. whether orders shipped on or before their due date.
- **REQ-020** The business must retain the **customer's own purchase order number** where the customer supplied one, so that reseller enquiries can be answered in the customer's own terms.
- **REQ-021** The business must retain the **financial accounting number reference** carried on the order, to allow reconciliation with finance.
- **REQ-022** The business must know the **billing address** and the **shipping address** used for each order, as two separate pieces of information.
- **REQ-023** The business must know the **shipping method** chosen for each order.
- **REQ-024** The business must retain **sales representative comments** recorded against an order, as context for enquiries and disputes.
- **REQ-025** The business must be able to report **order counts and values by channel, by territory, by representative, by customer and by period**.

#### Order revisions

- **REQ-026** The business must track the **revision number** of an order, which the schema describes as an incremental number tracking changes to the order over time. The business needs to be able to tell that an order has been amended, and how many times.

> **Clarification needed (C-05):** The operational system holds only the current revision of an order, with a counter. It is not visible from the schema whether prior revisions are retained anywhere. If the business needs to see what an order looked like before it was amended, that requirement must be raised explicitly, because the source may not be able to answer it.

#### Order amounts

- **REQ-027** The business must record the **order subtotal**, described as the sum of the line totals for the order.
- **REQ-028** The business must record the **tax amount** charged on the order.
- **REQ-029** The business must record the **freight (shipping cost)** charged on the order.
- **REQ-030** The business must record the **total due from the customer**, described as subtotal plus tax plus freight.
- **REQ-031** The business must be able to analyse revenue with tax and freight separated from product revenue, since these are managed by different parts of the business.

#### Payment on an order

- **REQ-032** The business must know **which credit card was used** to pay for an order, where a card was used.
- **REQ-033** The business must retain the **credit card approval code** provided by the card company, for payment reconciliation and dispute handling.
- **REQ-034** The business must be able to report the share of orders paid by card versus those with no card recorded (e.g. reseller accounts on credit terms).

> **Clarification needed (C-06):** The schema does not describe any payment method other than credit card. How reseller orders are settled (invoice, credit terms) is not visible here and may sit in a finance system outside this area.

#### Currency on an order

- **REQ-035** The business must know **which currency exchange rate was applied to each order**, where the order was not in the company's base currency.
- **REQ-036** The business must be able to report sales both in the transaction currency and converted to a reporting currency, using the rate that applied to the order.

### 2.4 Sales order line

Each order is made up of one or more lines, each line being one product sold in a given quantity at a given price, optionally under a promotion.

- **REQ-037** The business must identify each **order line** within its order; the schema describes one incremental unique number per product sold.
- **REQ-038** The business must know **which product** was sold on each line.
- **REQ-039** The business must know the **quantity ordered per product**.
- **REQ-040** The business must know the **unit selling price** of the product on that line.
- **REQ-041** The business must know the **discount amount** applied to that line.
- **REQ-042** The business must know the **line total**, described as unit price × (1 − discount) × quantity.
- **REQ-043** The business must know **which special offer (promotional code) applied to each line**, so that promotional effectiveness can be measured.
- **REQ-044** The business must retain the **shipment tracking number supplied by the shipper** for each line, because lines of one order may ship separately.
- **REQ-045** The business must be able to analyse sales **by product, by quantity, by realised price and by discount level**.
- **REQ-046** The business must be able to distinguish **list-price revenue from discount given away**, at line level.

### 2.5 Sales reason

Customers may state one or more reasons for a purchase. Reasons are categorised.

- **REQ-047** The business must maintain the catalogue of **sales reasons**, each with a description and a **reason category** ("the category the sales reason belongs to").
- **REQ-048** The business must know **which sales reasons were recorded against each order**. An order may have several reasons, and a reason applies to many orders.
- **REQ-049** The business must be able to report **order volume and value by sales reason and by reason category** (e.g. promotion-driven vs. quality-driven purchases).
- **REQ-050** The business must be able to report the proportion of orders for which **no reason was recorded**, as a data-quality measure.

### 2.6 Sales representative

Sales representatives are employees who carry a quota, earn a bonus and a commission, and work a territory.

- **REQ-051** The business must identify each **sales representative** by their business entity reference, which is also their employee reference.
- **REQ-052** The business must know the **territory a representative is currently assigned to**.
- **REQ-053** The business must know each representative's **projected yearly sales quota**.
- **REQ-054** The business must know the **bonus due if the quota is met**.
- **REQ-055** The business must know the **commission percentage received per sale**.
- **REQ-056** The business must know the representative's **year-to-date sales total** and **previous-year sales total** as maintained by the operational system.
- **REQ-057** The business must be able to compare a representative's **actual sales against quota**, and identify who is on track to earn the bonus.
- **REQ-058** The business must be able to report **sales by representative over time**, independently of the running totals held in the operational system.

> **Clarification needed (C-07):** The year-to-date and last-year totals held against a representative are running figures maintained by the operational system. They may not agree with totals calculated from orders (for example, if cancelled or rejected orders are treated differently). The business must decide which figure is authoritative for performance reporting, and the two must be reconcilable.

> **Clarification needed (C-08):** Not every representative necessarily has a territory or a quota recorded. How representatives without a territory should appear in territory reporting needs a business rule.

### 2.7 Sales territory

Territories are the geographic organisation of the sales business. They roll up into larger geographic groups, sit within a country/region, and carry their own performance figures.

- **REQ-059** The business must maintain the catalogue of **sales territories**, each with a territory name.
- **REQ-060** The business must know the **country or region** each territory belongs to.
- **REQ-061** The business must know the **geographic group** a territory belongs to (the wider area above territory level), so that results can be rolled up regionally.
- **REQ-062** The business must know each territory's **year-to-date sales** and **previous-year sales**.
- **REQ-063** The business must know each territory's **year-to-date business costs** and **previous-year costs**.
- **REQ-064** The business must be able to report **territory contribution** — sales against costs — for the current and previous year.
- **REQ-065** The business must be able to roll territory results up to geographic group and to country/region.

> **Clarification needed (C-09):** As with representatives, the sales and cost totals held against a territory are running figures maintained operationally. Whether territory performance reporting should use these figures or figures recomputed from orders needs a decision (see C-07).

### 2.8 Credit card

- **REQ-066** The business must maintain the register of **credit cards** used for payment, identified by the card record held in the operational system.
- **REQ-067** The business must know the **card type (card name)**, the **card number**, and the **expiry month and year**.
- **REQ-068** The business must be able to report **sales by card type**.
- **REQ-069** Credit card numbers and expiry data are sensitive personal and payment information. Access must be restricted, and the business must state whether the card number is needed at all in the warehouse or whether a masked or partial value is sufficient.

### 2.9 Person-to-credit-card relationship

- **REQ-070** The business must know **which credit cards belong to which person**. A person may hold several cards, and the schema allows a card to be associated with more than one person.
- **REQ-071** The business must be able to identify **cards used on orders that are not registered to the ordering customer**, as an input to fraud and data-quality review.

### 2.10 Shopping cart activity

The online channel records products that shoppers have put into a cart, whether or not an order followed.

- **REQ-072** The business must retain **shopping cart items**, each identified within its shopping cart.
- **REQ-073** For each cart item, the business must know the **shopping cart identifier**, the **product**, the **quantity ordered**, and the **date and time the item was created**.
- **REQ-074** The business must be able to report **which products are added to carts**, and in what quantities.
- **REQ-075** The business must be able to measure **cart activity over time**, using the creation date of cart items.

> **Clarification needed (C-10):** The schema gives no link from a shopping cart to a customer, a session or a resulting sales order. Abandonment analysis ("carts that did not become orders") and per-customer cart analysis therefore **cannot** be answered from this area as it stands. If the business needs them, an additional source or an additional operational field is required. This should be raised explicitly rather than assumed.

> **Clarification needed (C-11):** It is not visible whether cart items are deleted once an order is placed. If they are, the warehouse will only ever see open carts, which materially changes what cart reporting can mean.

### 2.11 Special offer (promotion / discount)

Special offers are the company's promotions. They have a discount percentage, a type and a category, a validity period, and quantity thresholds.

- **REQ-076** The business must maintain the catalogue of **special offers**, each with a **discount description**.
- **REQ-077** The business must know each offer's **discount percentage**.
- **REQ-078** The business must know each offer's **discount type category**.
- **REQ-079** The business must know the **group the discount applies to**, described as e.g. Reseller or Customer, so that promotions can be reported per channel.
- **REQ-080** The business must know each offer's **minimum and maximum quantity** thresholds.
- **REQ-081** The business must know each offer's **start date and end date**, i.e. the period during which it is valid.
- **REQ-082** The business must be able to determine **which offers were valid at any given date**, including offers that have since expired, so that historical orders can be explained.
- **REQ-083** The business must be able to report **revenue and discount attributable to each special offer**, and to each offer type and category.

> **Clarification needed (C-12):** The minimum and maximum quantity fields are described in the source as "Minimum discount percent allowed" and "Maximum discount percent allowed", which contradicts their names and their placement. Their true business meaning must be confirmed before they are used in any rule or report.

### 2.12 Special offer applicability to products

- **REQ-084** The business must know **which products each special offer applies to**. An offer may cover many products, and a product may be covered by several offers.
- **REQ-085** The business must be able to check that the offer recorded on an order line was in fact **applicable to the product on that line**, as a data-quality and pricing-governance control.

### 2.13 Currency

- **REQ-086** The business must maintain the list of **currencies**, identified by their **ISO currency code**, with the **currency name**.
- **REQ-087** The business must be able to present currency names in reporting rather than raw codes.

### 2.14 Currency exchange rate

Exchange rates are captured per day and per currency pair, with both an average and an end-of-day value.

- **REQ-088** The business must retain **exchange rates as a time series**: for each rate, the **date and time the rate was obtained**, the **currency converted from**, and the **currency converted to**.
- **REQ-089** The business must retain both the **average exchange rate for the day** and the **final (end-of-day) rate**, as these serve different reporting purposes.
- **REQ-090** The business must be able to reproduce **the rate that was actually applied to a given order**, not merely today's rate, so that historical reporting is stable and does not change when rates move.
- **REQ-091** The business must be able to report **the same sales figures in more than one currency**, and must state which of the two rates (average or end-of-day) is used for each report.
- **REQ-092** The business must be able to identify orders **where no exchange rate was recorded** and understand how those are to be treated (presumed base currency).

### 2.15 Country/region trading currency

- **REQ-093** The business must know **which currencies are used in which countries/regions**. A country/region may be associated with more than one currency, and a currency with more than one country/region.
- **REQ-094** The business must be able to check that sales in a given country/region were transacted in a currency valid for that country/region.

### 2.16 Sales tax rate

- **REQ-095** The business must maintain the register of **sales tax rates**, each with a **tax rate description**.
- **REQ-096** The business must know the **state, province or country/region each tax rate applies to**.
- **REQ-097** The business must know the **tax type** for each rate, using the operational meanings: applied to retail transactions, applied to wholesale transactions, or applied to all sales.
- **REQ-098** The business must know the **tax rate amount**.
- **REQ-099** The business must be able to report **tax collected by jurisdiction and by tax type**.
- **REQ-100** The business must be able to compare the **tax amount charged on an order** with the tax rates applicable to the relevant jurisdiction, as a compliance check.

> **Clarification needed (C-13):** The tax rate table has no validity period. It therefore records the rates as they stand now, not the rate that applied when a historical order was taxed. If the business needs to explain historical tax amounts, the warehouse must capture rate changes as they occur going forward; it cannot recover past rates from this source.

---

## 3. How the entities relate

Stated in business terms, ignoring technical keys:

- **REQ-101** A **sales order is placed by exactly one customer**, and a customer may place many orders over time.
- **REQ-102** A **sales order is handled by at most one sales representative** — orders placed online by the customer have no representative — and a representative handles many orders.
- **REQ-103** A **sales order is made in one sales territory**; a territory carries many orders.
- **REQ-104** A **sales order consists of one or more order lines**, and each order line belongs to exactly one order.
- **REQ-105** An **order line sells one product**; a product is sold on many order lines.
- **REQ-106** An **order line may be sold under one special offer**; an offer is used on many order lines.
- **REQ-107** A **sales order may cite several sales reasons**, and a sales reason may be cited on many orders.
- **REQ-108** A **sales order may be paid with one credit card**; a card may be used on many orders.
- **REQ-109** A **credit card may be registered to one or more people**, and a person may hold several cards.
- **REQ-110** A **sales order may use one currency exchange rate**; a rate may apply to many orders.
- **REQ-111** A **customer is located in one sales territory**; a territory contains many customers.
- **REQ-112** A **customer is either a person or a store** (see C-02).
- **REQ-113** A **reseller store is served by one sales representative**; a representative serves many stores.
- **REQ-114** A **sales representative is currently assigned to at most one territory**, and has worked a series of territories over time (see §4).
- **REQ-115** A **sales territory belongs to one country/region and to one geographic group**.
- **REQ-116** A **special offer applies to one or more products**, and a product may be covered by several offers.
- **REQ-117** A **country/region may trade in several currencies**, and a currency may be used in several countries/regions.
- **REQ-118** An **exchange rate converts from one currency to another** on a given day.
- **REQ-119** A **sales tax rate applies to one state/province or country/region** for a given tax type.
- **REQ-120** A **shopping cart contains one or more cart items**, each for one product. There is no recorded link from a cart to a customer or to an order (see C-10).
- **REQ-121** A **sales order carries a billing address and a shipping address**, which may differ.
- **REQ-122** A **sales order is shipped using one shipping method**.

---

## 4. Information that changes over time

Several parts of this area are explicitly historical, and the business must be able to answer "what was true then", not only "what is true now".

### 4.1 Sales quota history

- **REQ-123** The business must retain the **full history of sales quotas per representative**, with the **quota date** and the **quota amount** in force from that date.
- **REQ-124** The business must be able to determine **the quota that applied to a representative at any point in the past**, and compare it to the sales actually achieved in that period.
- **REQ-125** The business must be able to report **how a representative's quota has moved over time**, and how often it was revised.
- **REQ-126** The business must be aware that the representative record also carries a **single current quota figure**, alongside the dated history. Reporting must state which of the two it uses; the two must be reconcilable.

### 4.2 Territory assignment history

- **REQ-127** The business must retain the **history of which representative worked which territory**, with the **date the representative started work in the territory** and the **date they left**.
- **REQ-128** A representative's assignment is **open-ended while they are still working the territory** (no end date recorded); the business must be able to identify the currently active assignment for each representative.
- **REQ-129** The business must be able to determine **who was responsible for a territory on any given date**, so that historical sales can be credited to the person who actually held the territory at the time.
- **REQ-130** The business must be able to see the **sequence of representatives who have held a territory**, and how long each held it.
- **REQ-131** The business must be aware that the representative record also carries the **territory currently assigned**, alongside the dated history — the same current-versus-historical duality as the quota (see REQ-126).
- **REQ-132** Where an order's territory differs from the representative's territory at the time of the order, the business must be able to see and explain that difference (see REQ-016).

> **Clarification needed (C-14):** It is not visible from the schema whether a representative may hold two territories simultaneously, or whether assignment periods are guaranteed not to overlap. This affects how territory-based credit is calculated and needs a business rule.

### 4.3 Currency rates

- **REQ-133** Exchange rates are, by their nature, a **daily time series**; the business needs the rate as at the relevant date, and rates must never be retrospectively overwritten in reporting (see REQ-090).

### 4.4 Promotion validity

- **REQ-134** Special offers have **explicit start and end dates**; the business must be able to determine the offers that were live at any date, including expired ones (see REQ-082).

### 4.5 Slowly changing descriptive information

- **REQ-135** The business must be able to see how **descriptive information changes over time** where it matters commercially — in particular a customer's territory, a store's assigned representative, a store's demographics, a special offer's discount percentage, and a territory's group.
- **REQ-136** Every record in this area carries a **"last modified" date and time**. The business needs this as the primary signal that something has changed, and as the basis for reconciling warehouse content with the operational system.
- **REQ-137** For all other entities in this area, the operational system holds only the **current state**. The business must accept that history for those entities can only be built from the point the warehouse starts capturing it, and must decide for which of them that is worth doing.

> **Clarification needed (C-15):** The business has not yet stated how far back history is required, or how frequently the sales data must be refreshed (daily, intra-day). Both materially affect what can be delivered.

---

## 5. Cross-cutting business requirements

### 5.1 Analysis the business expects to perform

- **REQ-138** Report **sales value and volume** by period, territory, geographic group, country/region, representative, customer, customer kind, product, channel, currency, special offer and sales reason.
- **REQ-139** Compare **actual sales against quota** per representative and per period, including the bonus and commission implications.
- **REQ-140** Report **territory profitability** using sales and cost figures at territory level.
- **REQ-141** Measure **discounting**: total discount given, by offer, by product, by channel and by customer kind.
- **REQ-142** Measure **fulfilment**: order-to-ship elapsed time, on-time-against-due-date performance, and the distribution of order statuses.
- **REQ-143** Measure **channel mix**: online orders versus representative-entered orders, in volume and value.
- **REQ-144** Report **tax and freight** separately from product revenue.
- **REQ-145** Report **sales in a single reporting currency** across all territories, using the rate that applied to each order.
- **REQ-146** Analyse the **reseller base** by store demographics and by assigned representative.
- **REQ-147** Analyse **online cart activity** by product and period, within the limits noted in C-10.

### 5.2 Data quality and governance

- **REQ-148** The business must be able to see, for each order, whether the **key commercial attributes are present**: customer, territory, representative (where not online), currency rate (where non-base currency), and payment reference.
- **REQ-149** The business must be able to check that the **order total agrees with the sum of its lines plus tax and freight**, and to report where it does not.
- **REQ-150** The business must be able to check that **line totals agree with quantity, unit price and discount** as described by the source.
- **REQ-151** The business must be able to report **orders referencing a special offer that is outside its validity period** at the order date.
- **REQ-152** The business must be able to report **customers that are neither a person nor a store**, or that are both, once C-02 is resolved.
- **REQ-153** The business must be able to report **representatives with no territory**, and **territories with no representative**, on any given date.
- **REQ-154** The business must be able to reconcile **operationally maintained running totals** (representative and territory year-to-date and last-year figures) against totals recalculated from orders, and to report material differences (see C-07, C-09).
- **REQ-155** Each entity in this area has a named business owner who is accountable for its definitions and for resolving the clarifications in this document. The owners have not yet been assigned and must be, before the warehouse is built.

### 5.3 Privacy and sensitivity

- **REQ-156** **Credit card data** (card number, expiry, card type, holder association) is payment-sensitive. Its handling, retention and access rules must be defined before it is loaded (see REQ-069).
- **REQ-157** **Individual customers are natural persons**. Personal-data handling rules — including retention limits and the treatment of deletion requests — must be defined for the customer information in this area.
- **REQ-158** **Sales representative quota, bonus, commission and achievement** figures are effectively remuneration data about identifiable individuals and must be access-restricted to those with a legitimate need.
- **REQ-159** **Store demographics** are commercially sensitive information about our reseller partners and must be treated as confidential.

### 5.4 Traceability and technical notes

- **REQ-160** Several records carry a **replication identifier** described in the source as supporting a merge-replication sample. It has no business meaning; the business does not require it, but it may be retained as a technical trace of the source record.
- **REQ-161** Some order and customer values are described as **computed by the operational system** (the order number, the customer account number, the line total, the order subtotal and the total due). The business expects these to be taken as given from the source rather than recalculated, but expects them to be **checkable** (see REQ-149, REQ-150).

---

## 6. Open points summary

| Ref | Open point |
|---|---|
| C-01 | Programme boundary — whether product, person and geography areas are delivered alongside sales |
| C-02 | Whether a customer is always exactly one of person or store |
| C-03 | Which store demographic attributes are actually required for reporting |
| C-04 | Direction of the store-to-customer relationship; whether every store is a customer |
| C-05 | Whether prior order revisions are retained anywhere in the source |
| C-06 | How non-card payments (reseller credit terms) are recorded, if at all |
| C-07 | Whether representative year-to-date/last-year totals or recalculated order totals are authoritative |
| C-08 | Treatment of representatives without a territory or quota |
| C-09 | Whether territory running totals or recalculated totals are authoritative |
| C-10 | No link from shopping cart to customer or order — abandonment analysis not answerable today |
| C-11 | Whether cart items survive after an order is placed |
| C-12 | Contradictory meaning of the special offer minimum/maximum quantity fields |
| C-13 | Sales tax rates carry no validity period — historical tax rates not recoverable |
| C-14 | Whether representative territory assignments may overlap |
| C-15 | Required history depth and refresh frequency |
