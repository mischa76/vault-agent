# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 94 requirement(s) and 10 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (3)

- **hub_department** — business key `Name`. Register of departments, the organisational units people work in, keyed on department name (agreed decided key). _(requirements: REQ-030, REQ-031, REQ-034)_
- **hub_shift** — business key `Name`. Register of eight-hour working shifts, keyed on shift name (agreed decided key). _(requirements: REQ-037, REQ-038)_
- **hub_job_candidate** — business key `JobCandidateID`. Job candidates: people who applied for a position and whose application is held by HR. _(requirements: REQ-029-2, REQ-034-2, REQ-052)_

### Links (2)

- **link_business_entity_department_shift** — connects hub_business_entity, hub_department, hub_shift. Employee assignment to a department and shift over time, from EmployeeDepartmentHistory. Supports headcount at a point in time, mobility and movement reporting, and tracking how long an employee stays in an assignment. Unit of work: BusinessEntityID + DepartmentID + ShiftID (one assignment, starting on StartDate). Driving key: hub_business_entity. _(requirements: REQ-001-2, REQ-002-2, REQ-007-2, REQ-008-2, REQ-009-2, REQ-010-2, REQ-015-2, REQ-040, REQ-049)_
- **link_job_candidate_business_entity** — connects hub_job_candidate, hub_business_entity. Links a candidate record to the employee hired from it. A candidate with no link was not hired, or has not been hired yet. Unit of work: JobCandidateID + BusinessEntityID (hire of a candidate). _(requirements: REQ-032-2, REQ-033-2, REQ-035-2, REQ-036-2, REQ-034-2)_

### Satellites (9)

- **sat_business_entity_employee_details** — on hub_business_entity; payload: JobTitle, HireDate, SalariedFlag, CurrentFlag, LoginID, ModifiedDate. Employee job and employment-status attributes: job title, hire date, salaried/hourly flag, active/inactive flag, network login, and the last-modified timestamp. Source table: Employee. Split rationale: Employment attributes that are not sensitive and change slowly. ModifiedDate is kept only here. rowguid is left out because it has no business meaning (REQ-006).. _(requirements: REQ-005, REQ-007, REQ-008, REQ-009, REQ-010, REQ-012, REQ-013, REQ-014, REQ-039-2, REQ-040-2, REQ-043)_
- **sat_business_entity_employee_sensitive** — on hub_business_entity; payload: NationalIDNumber, BirthDate, Gender, MaritalStatus. Restricted personal data about employees: national ID number, date of birth, gender and marital status. Source table: Employee. Split rationale: Split out by data classification (PII), so access can be restricted to authorised HR users.. _(requirements: REQ-002, REQ-015, REQ-016, REQ-017, REQ-018, REQ-019, REQ-020)_
- **sat_business_entity_employee_leave** — on hub_business_entity; payload: VacationHours, SickLeaveHours. Leave balances (vacation and sick-leave hours remaining). The satellite builds a history of balance readings over time. Source table: Employee. Split rationale: Leave balances change much more often than other employee attributes.. _(requirements: REQ-021, REQ-022, REQ-023, REQ-024, REQ-051)_
- **sat_business_entity_employee_hierarchy** — on hub_business_entity; payload: OrganizationNode, OrganizationLevel. The employee's position and level in the corporate hierarchy. History builds up as changes are captured. Source table: Employee. Split rationale: Hierarchy position changes at its own rate and is used for reporting-line analysis.. _(requirements: REQ-025, REQ-026, REQ-027, REQ-028, REQ-029)_
- **sat_business_entity_employee_pay** — on hub_business_entity; payload: Rate, PayFrequency, ModifiedDate. Pay-rate history per employee: one row per effective rate-change date, with the hourly rate and the pay frequency. Multi-active satellite, child dependent key: RateChangeDate. Source table: EmployeePayHistory. Split rationale: Comes from its own source relation at a finer grain (employee + RateChangeDate), and the source keeps its history. EmployeePayHistory is now declared as a feed of hub_business_entity so this binding is valid.. _(requirements: REQ-016-2, REQ-017-2, REQ-018-2, REQ-019-2, REQ-020-2, REQ-021-2, REQ-022-2, REQ-023-2, REQ-024-2, REQ-050)_
- **sat_department_details** — on hub_department; payload: GroupName, ModifiedDate. Department group membership and last-change timestamp. History is captured over time to support as-was reporting. Source table: Department. _(requirements: REQ-032, REQ-033, REQ-034, REQ-035, REQ-036, REQ-044)_
- **sat_shift_details** — on hub_shift; payload: StartTime, EndTime, ModifiedDate. Shift start and end times. Captured historically because shift definitions can be adjusted. Source table: Shift. _(requirements: REQ-039, REQ-041, REQ-042)_
- **sat_job_candidate_details** — on hub_job_candidate; payload: Resume, ModifiedDate. The candidate's résumé (a structured document) and the last-modified timestamp. Source table: JobCandidate. _(requirements: REQ-030-2, REQ-031-2, REQ-037-2, REQ-039-2)_
- **sat_business_entity_department_shift_effectivity** — on link_business_entity_department_shift; payload: StartDate, EndDate. Active period of each department/shift assignment. A missing EndDate marks the current assignment. Effectivity satellite. Source table: EmployeeDepartmentHistory. _(requirements: REQ-003-2, REQ-004-2, REQ-005-2, REQ-006-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2, REQ-025-2)_

### Hub keys decided before modelling (2)

- **Department** — key `Name`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `Name` (0.60); primary key `DepartmentID`.
- **Shift** — key `Name`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `Name` (0.55); primary key `ShiftID`.

### Source mappings (28)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `Name` → `Department`.`Name` — exact_name, accepted
- `Name` → `Shift`.`Name` — exact_name, accepted
- `JobCandidateID` → `JobCandidate`.`JobCandidateID` — exact_name, accepted
- `JobTitle` → `Employee`.`JobTitle` — exact_name, accepted
- `HireDate` → `Employee`.`HireDate` — exact_name, accepted
- `SalariedFlag` → `Employee`.`SalariedFlag` — exact_name, accepted
- `CurrentFlag` → `Employee`.`CurrentFlag` — exact_name, accepted
- `LoginID` → `Employee`.`LoginID` — exact_name, accepted
- `ModifiedDate` → `Employee`.`ModifiedDate` — exact_name, accepted
- `NationalIDNumber` → `Employee`.`NationalIDNumber` — exact_name, accepted
- `BirthDate` → `Employee`.`BirthDate` — exact_name, accepted
- `Gender` → `Employee`.`Gender` — exact_name, accepted
- `MaritalStatus` → `Employee`.`MaritalStatus` — exact_name, accepted
- `VacationHours` → `Employee`.`VacationHours` — exact_name, accepted
- `SickLeaveHours` → `Employee`.`SickLeaveHours` — exact_name, accepted
- `OrganizationNode` → `Employee`.`OrganizationNode` — exact_name, accepted
- `OrganizationLevel` → `Employee`.`OrganizationLevel` — exact_name, accepted
- `Rate` → `EmployeePayHistory`.`Rate` — exact_name, accepted
- `PayFrequency` → `EmployeePayHistory`.`PayFrequency` — exact_name, accepted
- `GroupName` → `Department`.`GroupName` — exact_name, accepted
- `ModifiedDate` → `Department`.`ModifiedDate` — exact_name, accepted
- `StartTime` → `Shift`.`StartTime` — exact_name, accepted
- `EndTime` → `Shift`.`EndTime` — exact_name, accepted
- `ModifiedDate` → `Shift`.`ModifiedDate` — exact_name, accepted
- `Resume` → `JobCandidate`.`Resume` — exact_name, accepted
- `ModifiedDate` → `JobCandidate`.`ModifiedDate` — exact_name, accepted
- `StartDate` → `EmployeeDepartmentHistory`.`StartDate` — exact_name, accepted
- `EndDate` → `EmployeeDepartmentHistory`.`EndDate` — exact_name, accepted

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261115T081946810763Z`) carrying 7 hub(s), 4 link(s) and 17 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

27 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/hr_requirements.md
- Generated dbt models: 42 raw-vault model(s) + 59 staging model(s) (see `state.artifacts`)
