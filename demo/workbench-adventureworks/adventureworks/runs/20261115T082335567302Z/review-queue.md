# Human-in-the-loop checkpoint

**Status:** advisory only — 0 decision(s), 9 disclosure(s).

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_SAT_ATTR_OVERLAP_CROSS_SOURCE on hub_business_entity** — attribute 'ModifiedDate' appears in several satellites of 'hub_business_entity' fed by different source relations (sat_business_entity_credential <- PASSWORD, sat_business_entity_details <- BUSINESSENTITY, sat_business_entity_email <- EMAILADDRESS, sat_business_entity_employee_details <- EMPLOYEE, sat_business_entity_employee_pay <- EMPLOYEEPAYHISTORY, sat_business_entity_person_name <- PERSON, sat_business_entity_phone <- PERSONPHONE); same-named columns of different relations are different attributes, but check they are not one measure historised twice _(validator)_
- **W_BK_COLLISION_RISK on hub_address_type, hub_contact_type, hub_department, hub_shift, hub_state_province** — hubs hub_address_type, hub_contact_type, hub_department, hub_shift, hub_state_province share business key 'Name' across different source entities ['AddressType', 'ContactType', 'Department', 'Shift', 'StateProvince']; confirm whether a collision code is needed _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_job_candidate** — hub 'hub_job_candidate' is keyed on JobCandidateID, JobCandidate's technical primary key — JobCandidate declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/hr_requirements.md' did not fit one model response and was extracted over 2 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **link_proposer: ratified link to hub_business_entity not applied: no hub was modelled for EmployeeDepartmentHistory** _(link_proposer)_
- **link_proposer: ratified link to hub_business_entity not applied: no hub was modelled for EmployeePayHistory** _(link_proposer)_
- **link_proposer: link link_business_entity_department_shift, built by the modeler from EmployeeDepartmentHistory, requires surrogate→natural-key translation through Department for hub_department (DepartmentID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_business_entity_department_shift, built by the modeler from EmployeeDepartmentHistory, requires surrogate→natural-key translation through Shift for hub_shift (ShiftID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
