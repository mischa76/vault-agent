# Extension diff

This run extended the vault at `demo/workbench-adventureworks/adventureworks/runs/20261022T232630984833Z`: **27 unchanged**, **1 extended**, **15 new** construct(s).

Unchanged constructs render byte-identically, so their tables are untouched by a rebuild. The files listed under *extended* are the ones that genuinely changed.

## Unchanged (27)

`hub_address`, `hub_address_type`, `hub_contact_type`, `hub_phone_number_type`, `hub_country_region`, `hub_state_province`, `link_address_state_province`, `link_state_province_country_region`, `link_business_entity_address`, `link_business_entity_contact`, `sat_business_entity_details`, `sat_business_entity_person_name`, `sat_business_entity_person_type`, `sat_business_entity_person_consent`, `sat_business_entity_person_sensitive`, `sat_business_entity_email`, `sat_business_entity_phone`, `sat_business_entity_credential`, `sat_address_details`, `sat_address_location`, `sat_address_type_details`, `sat_contact_type_details`, `sat_phone_number_type_details`, `sat_country_region_details`, `sat_state_province_details`, `sat_state_province_territory`, `sat_business_entity_address_details`

## Extended (1)

- **hub_business_entity** — 2 source feed(s): Employee.BusinessEntityID, EmployeePayHistory.BusinessEntityID; 5 new satellite(s): sat_business_entity_employee_details, sat_business_entity_employee_sensitive, sat_business_entity_employee_leave, sat_business_entity_employee_hierarchy, sat_business_entity_employee_pay
  - changed file: `models/raw_vault/hub_business_entity.sql`

## New (15)

- **hub_department**
- **hub_shift**
- **hub_job_candidate**
- **link_business_entity_department_shift**
- **link_job_candidate_business_entity**
- **sat_business_entity_employee_details** — on `hub_business_entity`
- **sat_business_entity_employee_sensitive** — on `hub_business_entity`
- **sat_business_entity_employee_leave** — on `hub_business_entity`
- **sat_business_entity_employee_hierarchy** — on `hub_business_entity`
- **sat_business_entity_employee_pay** — on `hub_business_entity`
- **sat_department_details** — on `hub_department`
- **sat_shift_details** — on `hub_shift`
- **sat_job_candidate_resume** — on `hub_job_candidate`
- **sat_business_entity_department_shift_effectivity** — on `link_business_entity_department_shift`
- **sat_business_entity_department_shift_details** — on `link_business_entity_department_shift`
