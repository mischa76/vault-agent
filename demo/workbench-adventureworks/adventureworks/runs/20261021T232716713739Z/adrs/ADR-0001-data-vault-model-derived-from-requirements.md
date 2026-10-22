# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-10-22
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 90 requirement(s) and 10 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (3)

- **hub_department** — business key `DepartmentID`. Register of departments, the organisational units in which people work. Keyed on the stable DepartmentID because department names can change. _(requirements: REQ-031, REQ-032, REQ-035, REQ-043)_
- **hub_shift** — business key `ShiftID`. Register of eight-hour working shifts. Keyed on the stable ShiftID because shift names and definitions can be adjusted. _(requirements: REQ-038, REQ-039, REQ-042)_
- **hub_job_candidate** — business key `JobCandidateID`. Job candidates whose applications are held by HR. _(requirements: REQ-068, REQ-072, REQ-090)_

### Links (2)

- **link_business_entity_department_shift** — connects hub_business_entity, hub_department, hub_shift. Employee assignment to a department and a shift over time, from EmployeeDepartmentHistory. An effectivity satellite tracks the start and end dates for each employee. Unit of work: BusinessEntityID + DepartmentID + ShiftID (assignment starting at StartDate). Driving key: hub_business_entity. _(requirements: REQ-041, REQ-043, REQ-044, REQ-047, REQ-048, REQ-049, REQ-050, REQ-051, REQ-055, REQ-064, REQ-087)_
- **link_business_entity_job_candidate** — connects hub_job_candidate, hub_business_entity. Links a candidate record to the employee hired from it. If this link exists, the applicant was hired. Unit of work: JobCandidateID + BusinessEntityID. _(requirements: REQ-071, REQ-072, REQ-073, REQ-074, REQ-090)_

### Satellites (10)

- **sat_business_entity_employee_details** — on hub_business_entity; payload: JobTitle, HireDate, SalariedFlag, CurrentFlag, LoginID, ModifiedDate. Non-sensitive employee details: job title, hire date, salaried/hourly flag, active status and network login. Changes are kept so values that the source overwrites still have a history. Source table: Employee. Split rationale: General employment attributes that change slowly and are not restricted; holds the single ModifiedDate audit column for Employee.. _(requirements: REQ-005, REQ-007, REQ-008, REQ-009, REQ-010, REQ-012, REQ-013, REQ-014, REQ-077, REQ-078, REQ-080, REQ-081)_
- **sat_business_entity_employee_sensitive** — on hub_business_entity; payload: NationalIDNumber, BirthDate, Gender, MaritalStatus. Personal and sensitive employee attributes, with access limited to authorised HR users. Source table: Employee. Split rationale: Split out by data classification (PII) so that access can be restricted.. _(requirements: REQ-002, REQ-015, REQ-016, REQ-017, REQ-018, REQ-019, REQ-066)_
- **sat_business_entity_employee_leave** — on hub_business_entity; payload: VacationHours, SickLeaveHours. Point-in-time readings of vacation and sick-leave balances. Keeping each change shows how balances move over time. Source table: Employee. Split rationale: Split out by rate of change: balances change much more often than other employee attributes.. _(requirements: REQ-020, REQ-021, REQ-022, REQ-023, REQ-024, REQ-089)_
- **sat_business_entity_employee_hierarchy** — on hub_business_entity; payload: OrganizationNode, OrganizationLevel. The employee's position and level in the organisational hierarchy. History is captured as changes occur. Source table: Employee. Split rationale: Hierarchy position is its own concern and changes on a different schedule from other attributes.. _(requirements: REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-030)_
- **sat_business_entity_pay_history** — on hub_business_entity; payload: Rate, PayFrequency, ModifiedDate. Pay rate history. RateChangeDate (the effective date) separates the concurrent records. Multi-active satellite, child dependent key: RateChangeDate. Source table: EmployeePayHistory. Split rationale: Comes from a separate source table at a finer grain (one row per rate change). EmployeePayHistory is now declared as a feed of hub_business_entity.. _(requirements: REQ-057, REQ-058, REQ-059, REQ-060, REQ-061, REQ-062, REQ-063, REQ-065, REQ-079, REQ-088)_
- **sat_business_entity_department_shift_effectivity** — on link_business_entity_department_shift; payload: StartDate, EndDate. Active period of each department/shift assignment. An assignment with no end date is the current one. Effectivity satellite. Source table: EmployeeDepartmentHistory. _(requirements: REQ-044, REQ-045, REQ-046, REQ-047, REQ-048, REQ-052, REQ-053, REQ-054, REQ-085)_
- **sat_business_entity_department_shift_audit** — on link_business_entity_department_shift; payload: ModifiedDate. When each assignment record was last updated, used to judge how current it is. Source table: EmployeeDepartmentHistory. Split rationale: The audit timestamp is kept apart from the effectivity dates.. _(requirements: REQ-077, REQ-078)_
- **sat_department_details** — on hub_department; payload: Name, GroupName, ModifiedDate. Department name, group membership and last-change date. History is kept for as-was reporting. Source table: Department. _(requirements: REQ-032, REQ-033, REQ-034, REQ-035, REQ-036, REQ-037, REQ-082)_
- **sat_shift_details** — on hub_shift; payload: Name, StartTime, EndTime, ModifiedDate. Shift name and start/end times. History is kept because definitions can be adjusted. Source table: Shift. _(requirements: REQ-039, REQ-040, REQ-042)_
- **sat_job_candidate_resume** — on hub_job_candidate; payload: Resume, ModifiedDate. The candidate's résumé, stored as a structured document. It is non-employee personal data, subject to its own retention rules. Source table: JobCandidate. _(requirements: REQ-069, REQ-070, REQ-075, REQ-077)_

### Source mappings (31)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `DepartmentID` → `Department`.`DepartmentID` — exact_name, accepted
- `ShiftID` → `Shift`.`ShiftID` — exact_name, accepted
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
- `StartDate` → `EmployeeDepartmentHistory`.`StartDate` — exact_name, accepted
- `EndDate` → `EmployeeDepartmentHistory`.`EndDate` — exact_name, accepted
- `ModifiedDate` → `EmployeeDepartmentHistory`.`ModifiedDate` — exact_name, accepted
- `Name` → `Department`.`Name` — exact_name, accepted
- `GroupName` → `Department`.`GroupName` — exact_name, accepted
- `ModifiedDate` → `Department`.`ModifiedDate` — exact_name, accepted
- `Name` → `Shift`.`Name` — exact_name, accepted
- `StartTime` → `Shift`.`StartTime` — exact_name, accepted
- `EndTime` → `Shift`.`EndTime` — exact_name, accepted
- `ModifiedDate` → `Shift`.`ModifiedDate` — exact_name, accepted
- `Resume` → `JobCandidate`.`Resume` — exact_name, accepted
- `ModifiedDate` → `JobCandidate`.`ModifiedDate` — exact_name, accepted

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261019T204027253108Z`) carrying 7 hub(s), 5 link(s) and 17 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

28 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.
- Caveat: 1 construct(s) could not be generated and are flagged for human review: sat_business_entity_pay_history.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/hr_requirements.md
- Generated dbt models: 44 raw-vault model(s) + 37 staging model(s) (see `state.artifacts`)
