# Human-in-the-loop checkpoint

**Status:** requires sign-off — 16 decision(s), 2 disclosure(s).

## Decisions

### Contract owners to assign (block agreement)

- **Assign an owner for contract 'Address'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'AddressType'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'BusinessEntity'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'BusinessEntityAddress'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'BusinessEntityContact'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'ContactType'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'CountryRegion'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'EmailAddress'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'Password'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'Person'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'PersonPhone'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'PhoneNumberType'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'StateProvince'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_

### Review flags (advisory)

- **code_generator: satellite 'sat_business_entity_email' of type 'multi_active' on multi-source hub 'hub_business_entity' is not supported; flagged for human review** _(code_generator)_
- **code_generator: satellite 'sat_business_entity_phone' of type 'multi_active' on multi-source hub 'hub_business_entity' is not supported; flagged for human review** _(code_generator)_
- **code_generator: satellite 'sat_business_entity_credential' declares source_table 'Password', which is not one of the feeds of its multi-source parent 'hub_business_entity' (BusinessEntity, Person); a finer-grain relation under one feed cannot say which feed it belongs to (ADR-0011), so this is flagged for human review** _(code_generator)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_SAT_ATTR_OVERLAP_CROSS_SOURCE on hub_business_entity** — attribute 'ModifiedDate' appears in several satellites of 'hub_business_entity' fed by different source relations (sat_business_entity_credential <- PASSWORD, sat_business_entity_details <- BUSINESSENTITY, sat_business_entity_email <- EMAILADDRESS, sat_business_entity_person_name <- PERSON, sat_business_entity_phone <- PERSONPHONE); same-named columns of different relations are different attributes, but check they are not one measure historised twice _(validator)_

### Review flags (advisory)

- **requirements_parser: document '/mnt/c/Users/misch/projects/vault-agent/workbench-demo$/workbench-demo/inputs/requirements.md' did not fit one model response and was extracted over 2 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
