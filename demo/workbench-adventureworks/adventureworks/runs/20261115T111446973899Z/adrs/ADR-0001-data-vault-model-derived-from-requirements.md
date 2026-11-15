# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 96 requirement(s) and 12 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (3)

- **hub_department** — business key `Name`. Register of departments, the organisational units people work in, identified by department name. _(requirements: REQ-031, REQ-032)_
- **hub_shift** — business key `Name`. Register of eight-hour working shifts, identified by shift name. _(requirements: REQ-038, REQ-039)_
- **hub_job_candidate** — business key `JobCandidateID`. Job candidates: people who applied for a position and whose application HR holds. _(requirements: REQ-030-2)_

### Links (2)

- **link_business_entity_department_shift** — connects hub_business_entity, hub_department, hub_shift. Department and shift assignment of an employee over time, from EmployeeDepartmentHistory. An employee holds one department/shift assignment at a time. Unit of work: Employee (BusinessEntityID) + Department (Name) + Shift (Name), i.e. one assignment. Driving key: hub_business_entity. _(requirements: REQ-001-2, REQ-002-2, REQ-007-2, REQ-008-2, REQ-009-2, REQ-010-2, REQ-015-2, REQ-041, REQ-050)_
- **link_job_candidate_business_entity** — connects hub_job_candidate, hub_business_entity. Links a job candidate to the employee they became when hired. Candidates without a link were not hired. Unit of work: JobCandidateID + BusinessEntityID (hire of a candidate). _(requirements: REQ-033-2, REQ-034-2, REQ-035-2, REQ-036-2, REQ-037-2, REQ-053)_

### Satellites (11)

- **sat_business_entity_employee_identifiers** — on hub_business_entity; payload: NationalIDNumber, LoginID. Alternate employee identifiers: national ID number and network login. These are used to join data, not to anchor identity. Source table: Employee. Split rationale: Identifier-type attributes; the national ID is sensitive, so these are kept apart from operational job data.. _(requirements: REQ-002, REQ-005)_
- **sat_business_entity_employee_job** — on hub_business_entity; payload: JobTitle, HireDate, SalariedFlag, CurrentFlag, ModifiedDate. Employment details: job title, hire date, salaried/hourly classification, active status and last-updated timestamp. History is built by observing overwrites. Source table: Employee. Split rationale: Non-sensitive employment attributes that change slowly; this satellite holds the Employee ModifiedDate.. _(requirements: REQ-007, REQ-008, REQ-009, REQ-010, REQ-012, REQ-013, REQ-014, REQ-040-2, REQ-043-2, REQ-044, REQ-047, REQ-048)_
- **sat_business_entity_employee_personal** — on hub_business_entity; payload: BirthDate, Gender, MaritalStatus. Restricted personal employee data: date of birth, gender and marital status. Source table: Employee. Split rationale: Data classification: personal data restricted to authorised HR users.. _(requirements: REQ-015, REQ-016, REQ-017, REQ-018, REQ-019, REQ-020, REQ-028-2, REQ-049)_
- **sat_business_entity_employee_leave** — on hub_business_entity; payload: VacationHours, SickLeaveHours. Point-in-time leave balance readings. Changes are captured as a series of balances. Source table: Employee. Split rationale: Rate of change: leave balances change far more often than other employee attributes.. _(requirements: REQ-021, REQ-022, REQ-023, REQ-024, REQ-052)_
- **sat_business_entity_employee_hierarchy** — on hub_business_entity; payload: OrganizationNode, OrganizationLevel. The employee's position and depth in the corporate reporting hierarchy. History is built by capturing changes. Source table: Employee. Split rationale: Hierarchy position changes independently of job details and only its current value is held in the source.. _(requirements: REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-030)_
- **sat_business_entity_employee_pay** — on hub_business_entity; payload: Rate, PayFrequency, ModifiedDate. Pay rate history per employee, keyed by effective rate change date: hourly rate and pay frequency. Multi-active satellite, child dependent key: RateChangeDate. Source table: EmployeePayHistory. Split rationale: Separate source relation at a finer grain (one row per rate change); EmployeePayHistory is declared as a feed of hub_business_entity.. _(requirements: REQ-016-2, REQ-017-2, REQ-018-2, REQ-019-2, REQ-020-2, REQ-021-2, REQ-022-2, REQ-023-2, REQ-024-2, REQ-025-2, REQ-026-2, REQ-027-2, REQ-051)_
- **sat_department_details** — on hub_department; payload: GroupName, ModifiedDate. Department description: owning group and last change date. History is captured because the source overwrites it. Source table: Department. _(requirements: REQ-033, REQ-034, REQ-035, REQ-036, REQ-037, REQ-045)_
- **sat_shift_details** — on hub_shift; payload: StartTime, EndTime, ModifiedDate. Shift definition: start and end time and last-updated timestamp. These can be adjusted over time. Source table: Shift. _(requirements: REQ-040, REQ-042, REQ-043)_
- **sat_business_entity_department_shift_effectivity** — on link_business_entity_department_shift; payload: StartDate, EndDate. Active period of each department/shift assignment. A missing EndDate marks the current assignment. Effectivity satellite. Source table: EmployeeDepartmentHistory. _(requirements: REQ-002-2, REQ-003-2, REQ-004-2, REQ-005-2, REQ-006-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2)_
- **sat_business_entity_department_shift_details** — on link_business_entity_department_shift; payload: ModifiedDate. Last-updated timestamp of each assignment record, one row per assignment start date. Multi-active satellite, child dependent key: StartDate. Source table: EmployeeDepartmentHistory. Split rationale: Kept out of the effectivity satellite, which must carry exactly the start and end dates; multi-active on StartDate because repeated stints share the same link key.. _(requirements: REQ-040-2, REQ-041-2)_
- **sat_job_candidate_resume** — on hub_job_candidate; payload: Resume, ModifiedDate. The candidate's résumé, held as a structured document, plus a last-updated timestamp. Source table: JobCandidate. Split rationale: Candidate personal data has its own retention and access rules.. _(requirements: REQ-031-2, REQ-032-2, REQ-038-2, REQ-040-2)_

### Hub keys decided before modelling (2)

- **Department** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `DepartmentID` (0.30); primary key `DepartmentID`.
- **Shift** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `ShiftID` (0.35); primary key `ShiftID`.

### Source mappings (29)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `Name` → `Department`.`Name` — exact_name, accepted
- `Name` → `Shift`.`Name` — exact_name, accepted
- `JobCandidateID` → `JobCandidate`.`JobCandidateID` — exact_name, accepted
- `NationalIDNumber` → `Employee`.`NationalIDNumber` — exact_name, accepted
- `LoginID` → `Employee`.`LoginID` — exact_name, accepted
- `JobTitle` → `Employee`.`JobTitle` — exact_name, accepted
- `HireDate` → `Employee`.`HireDate` — exact_name, accepted
- `SalariedFlag` → `Employee`.`SalariedFlag` — exact_name, accepted
- `CurrentFlag` → `Employee`.`CurrentFlag` — exact_name, accepted
- `ModifiedDate` → `Employee`.`ModifiedDate` — exact_name, accepted
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
- `StartDate` → `EmployeeDepartmentHistory`.`StartDate` — exact_name, accepted
- `EndDate` → `EmployeeDepartmentHistory`.`EndDate` — exact_name, accepted
- `ModifiedDate` → `EmployeeDepartmentHistory`.`ModifiedDate` — exact_name, accepted
- `Resume` → `JobCandidate`.`Resume` — exact_name, accepted
- `ModifiedDate` → `JobCandidate`.`ModifiedDate` — exact_name, accepted

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261115T111031038199Z`) carrying 7 hub(s), 5 link(s) and 17 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

28 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/hr_requirements.md
- Generated dbt models: 45 raw-vault model(s) + 64 staging model(s) (see `state.artifacts`)
