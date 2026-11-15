# Extension diff

This run extended the vault at `demo/workbench-adventureworks/adventureworks/runs/20261115T111031038199Z`: **28 unchanged**, **1 extended**, **16 new** construct(s).

Unchanged constructs render byte-identically, so their tables are untouched by a rebuild. The files listed under *extended* are the ones that genuinely changed.

## Unchanged (28)

`hub_address`, `hub_address_type`, `hub_contact_type`, `hub_phone_number_type`, `hub_country_region`, `hub_state_province`, `link_business_entity_address`, `link_business_entity_contact`, `link_business_entity_phone_number_type`, `link_address_state_province`, `link_state_province_country_region`, `sat_business_entity_details`, `sat_business_entity_person_name`, `sat_business_entity_person_consent`, `sat_business_entity_person_sensitive`, `sat_business_entity_email`, `sat_business_entity_credential`, `sat_business_entity_phone_number_type_numbers`, `sat_business_entity_address_details`, `sat_business_entity_contact_details`, `sat_address_details`, `sat_address_location`, `sat_address_type_details`, `sat_contact_type_details`, `sat_phone_number_type_details`, `sat_country_region_details`, `sat_state_province_details`, `sat_state_province_territory`

## Extended (1)

- **hub_business_entity** — 2 source feed(s): Employee.BusinessEntityID, EmployeePayHistory.BusinessEntityID; 6 new satellite(s): sat_business_entity_employee_identifiers, sat_business_entity_employee_job, sat_business_entity_employee_personal, sat_business_entity_employee_leave, sat_business_entity_employee_hierarchy, sat_business_entity_employee_pay
  - changed file: `models/raw_vault/hub_business_entity.sql`

## New (16)

- **hub_department**
- **hub_shift**
- **hub_job_candidate**
- **link_business_entity_department_shift**
- **link_job_candidate_business_entity**
- **sat_business_entity_employee_identifiers** — on `hub_business_entity`
- **sat_business_entity_employee_job** — on `hub_business_entity`
- **sat_business_entity_employee_personal** — on `hub_business_entity`
- **sat_business_entity_employee_leave** — on `hub_business_entity`
- **sat_business_entity_employee_hierarchy** — on `hub_business_entity`
- **sat_business_entity_employee_pay** — on `hub_business_entity`
- **sat_department_details** — on `hub_department`
- **sat_shift_details** — on `hub_shift`
- **sat_business_entity_department_shift_effectivity** — on `link_business_entity_department_shift`
- **sat_business_entity_department_shift_details** — on `link_business_entity_department_shift`
- **sat_job_candidate_resume** — on `hub_job_candidate`
