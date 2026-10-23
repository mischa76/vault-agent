# Human-in-the-loop checkpoint

**Status:** advisory only — 4 decision(s), 4 disclosure(s).

## Decisions

### Review flags (advisory)

- **code_generator: satellite 'sat_business_entity_email' of type 'multi_active' on multi-source hub 'hub_business_entity' is not supported; flagged for human review** _(code_generator)_
- **code_generator: satellite 'sat_business_entity_phone' of type 'multi_active' on multi-source hub 'hub_business_entity' is not supported; flagged for human review** _(code_generator)_
- **code_generator: satellite 'sat_business_entity_credential' declares source_table 'Password', which is not one of the feeds of its multi-source parent 'hub_business_entity' (BusinessEntity, Person); a finer-grain relation under one feed cannot say which feed it belongs to (ADR-0011), so this is flagged for human review** _(code_generator)_
- **code_generator: staging model 'stg_business_entity_contact' was bound to 'BusinessEntityContact', which declares none of ORGANISATION_BUSINESSENTITYID, CONTACT_PERSON_BUSINESSENTITYID that the stage hashes or derives; the binding is refused and the stage reads 'raw_business_entity_contact' until a human maps the relation** _(code_generator)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_SAT_ATTR_OVERLAP_CROSS_SOURCE on hub_business_entity** — attribute 'ModifiedDate' appears in several satellites of 'hub_business_entity' fed by different source relations (sat_business_entity_credential <- PASSWORD, sat_business_entity_details <- BUSINESSENTITY, sat_business_entity_email <- EMAILADDRESS, sat_business_entity_person_name <- PERSON, sat_business_entity_phone <- PERSONPHONE); same-named columns of different relations are different attributes, but check they are not one measure historised twice _(validator)_
- **W_ROLE_BK_NOT_IN_SOURCE on link_business_entity_contact** — role-qualified participation hub_business_entity (role 'organisation') expects a source column 'ORGANISATION_BUSINESSENTITYID', which matches no column in the declared source schema; verify the source or complete the schema _(validator)_
- **W_ROLE_BK_NOT_IN_SOURCE on link_business_entity_contact** — role-qualified participation hub_business_entity (role 'contact_person') expects a source column 'CONTACT_PERSON_BUSINESSENTITYID', which matches no column in the declared source schema; verify the source or complete the schema _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/person_requirements.md' did not fit one model response and was extracted over 2 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
