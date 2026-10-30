<!-- Drafted deterministically from the AdventureWorks catalogue (Microsoft, MIT — see
NOTICE) by eval.adventureworks.draft_requirements: tables, descriptions, keys and foreign
keys as the catalogue states them. No analyst has read or written this. The C1 experiment,
2026-10-30. -->

# Requirements drafted from the source catalogue: human resources

**Area:** HumanResources  
**Prepared by:** nobody — drafted from the catalogue  
**Status:** Draft, unreviewed

## 1. Purpose

The business needs to analyse what the human resources area of the operational system records. This document lists what that area records, as the system's own catalogue describes it: its tables, what identifies each, what each records, and how they refer to one another. It states nothing the catalogue does not.

## 2. Business entities in scope

| Concept | What the catalogue says it is |
|---|---|
| Department | Lookup table containing the departments within the Adventure Works Cycles company. |
| Employee (a kind of another concept) | Employee information such as salary, department, and title. |
| Employee department history | Employee department transfers. |
| Employee pay history | Employee pay history. |
| Job candidate | Résumés submitted to Human Resources by job applicants. |
| Shift | Work shift lookup table. |

## 3. Department

Lookup table containing the departments within the Adventure Works Cycles company.

- **REQ-001** The business must record every **department**.
- **REQ-002** Each department is identified by its **name**.
- **REQ-003** The business must record the **group name** of each department: Name of the group to which the department belongs.
- **REQ-004** Each department carries a last-changed timestamp.

## 4. Employee

Employee information such as salary, department, and title.

- **REQ-005** The business must record every **employee**. Every employee is a **person** and is identified by the same **business entity id**.
- **REQ-006** The business must record the **national id number** of each employee: Unique national identification number such as a social security number.
- **REQ-007** The business must record the **login id** of each employee: Network login.
- **REQ-008** The business must record the **organization node** of each employee: Where the employee is located in corporate hierarchy.
- **REQ-009** The business must record the **organization level** of each employee: The depth of the employee in the corporate hierarchy.
- **REQ-010** The business must record the **job title** of each employee: Work title such as Buyer or Sales Representative.
- **REQ-011** The business must record the **birth date** of each employee: Date of birth.
- **REQ-012** The business must record the **marital status** of each employee: M = Married, S = Single
- **REQ-013** The business must record the **gender** of each employee: M = Male, F = Female
- **REQ-014** The business must record the **hire date** of each employee: Employee hired on this date.
- **REQ-015** The business must record the **salaried flag** of each employee: Job classification. 0 = Hourly, not exempt from collective bargaining. 1 = Salaried, exempt from collective bargaining.
- **REQ-016** The business must record the **vacation hours** of each employee: Number of available vacation hours.
- **REQ-017** The business must record the **sick leave hours** of each employee: Number of available sick leave hours.
- **REQ-018** The business must record the **current flag** of each employee: 0 = Inactive, 1 = Active
- **REQ-019** Each employee carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 5. Employee department history

Employee department transfers.

- **REQ-020** The business must record every **employee department history**.
- **REQ-021** Each employee department history is identified by the combination of **business entity id**, **start date**, **department id**, **shift id**.
- **REQ-022** The business must record the **end date** of each employee department history: Date the employee left the department. NULL = Current department.
- **REQ-023** Each employee department history refers to one **department** (by its department id).
- **REQ-024** Each employee department history refers to one **employee** (by its business entity id).
- **REQ-025** Each employee department history refers to one **shift** (by its shift id).
- **REQ-026** Each employee department history carries a last-changed timestamp.

## 6. Employee pay history

Employee pay history.

- **REQ-027** The business must record every **employee pay history**.
- **REQ-028** Each employee pay history is identified by the combination of **business entity id**, **rate change date**.
- **REQ-029** The business must record the **rate** of each employee pay history: Salary hourly rate.
- **REQ-030** The business must record the **pay frequency** of each employee pay history: 1 = Salary received monthly, 2 = Salary received biweekly
- **REQ-031** Each employee pay history refers to one **employee** (by its business entity id).
- **REQ-032** Each employee pay history carries a last-changed timestamp.

## 7. Job candidate

Résumés submitted to Human Resources by job applicants.

- **REQ-033** The business must record every **job candidate**.
- **REQ-034** Each job candidate is identified by its **job candidate id**.
- **REQ-035** The business must record the **resume** of each job candidate: Résumé in XML format.
- **REQ-036** Each job candidate refers to one **employee** (by its business entity id).
- **REQ-037** Each job candidate carries a last-changed timestamp.

## 8. Shift

Work shift lookup table.

- **REQ-038** The business must record every **shift**.
- **REQ-039** Each shift is identified by its **name**.
- **REQ-040** The business must record the **start time** of each shift: Shift start time.
- **REQ-041** The business must record the **end time** of each shift: Shift end time.
- **REQ-042** Each shift carries a last-changed timestamp.
