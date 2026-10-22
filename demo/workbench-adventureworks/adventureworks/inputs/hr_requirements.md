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
