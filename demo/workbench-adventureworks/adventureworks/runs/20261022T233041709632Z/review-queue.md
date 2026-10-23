# Human-in-the-loop checkpoint

**Status:** advisory only — 2 decision(s), 4 disclosure(s).

## Decisions

### Review flags (advisory)

- **code_generator: satellite 'sat_business_entity_employee_pay' of type 'multi_active' on multi-source hub 'hub_business_entity' is not supported; flagged for human review** _(code_generator)_
- **code_generator: staging model 'stg_business_entity_contact' was bound to 'BusinessEntityContact', which declares none of ORGANISATION_BUSINESSENTITYID, CONTACT_PERSON_BUSINESSENTITYID that the stage hashes or derives; the binding is refused and the stage reads 'raw_business_entity_contact' until a human maps the relation** _(code_generator)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_SAT_ATTR_OVERLAP_CROSS_SOURCE on hub_business_entity** — attribute 'ModifiedDate' appears in several satellites of 'hub_business_entity' fed by different source relations (sat_business_entity_credential <- PASSWORD, sat_business_entity_details <- BUSINESSENTITY, sat_business_entity_email <- EMAILADDRESS, sat_business_entity_employee_details <- EMPLOYEE, sat_business_entity_employee_pay <- EMPLOYEEPAYHISTORY, sat_business_entity_person_name <- PERSON, sat_business_entity_phone <- PERSONPHONE); same-named columns of different relations are different attributes, but check they are not one measure historised twice _(validator)_

### Review flags (advisory)

- **link_proposer: ratified link to hub_business_entity not applied: no hub was modelled for EmployeeDepartmentHistory** _(link_proposer)_
- **link_proposer: ratified link to hub_business_entity not applied: no hub was modelled for EmployeePayHistory** _(link_proposer)_
