# Human-in-the-loop checkpoint

**Status:** advisory only — 0 decision(s), 11 disclosure(s).

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_SAT_ATTR_OVERLAP_CROSS_SOURCE on hub_business_entity** — attribute 'ModifiedDate' appears in several satellites of 'hub_business_entity' fed by different source relations (sat_business_entity_credential <- PASSWORD, sat_business_entity_details <- BUSINESSENTITY, sat_business_entity_email <- EMAILADDRESS, sat_business_entity_person_name <- PERSON); same-named columns of different relations are different attributes, but check they are not one measure historised twice _(validator)_
- **W_BK_COLLISION_RISK on hub_address_type, hub_contact_type, hub_state_province** — hubs hub_address_type, hub_contact_type, hub_state_province share business key 'Name' across different source entities ['AddressType', 'ContactType', 'StateProvince']; confirm whether a collision code is needed _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_business_entity** — hub 'hub_business_entity' is keyed on BusinessEntityID, BusinessEntity's technical primary key — BusinessEntity declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_address** — hub 'hub_address' is keyed on AddressID, Address's technical primary key — Address declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_phone_number_type** — hub 'hub_phone_number_type' is keyed on PhoneNumberTypeID, PhoneNumberType's technical primary key — PhoneNumberType declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/person_requirements.md' did not fit one model response and was extracted over 2 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **link_proposer: link link_address_state_province, built by the modeler from Address, requires surrogate→natural-key translation through StateProvince for hub_state_province (StateProvinceID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_business_entity_address, built by the modeler from BusinessEntityAddress, requires surrogate→natural-key translation through AddressType for hub_address_type (AddressTypeID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: satellite sat_business_entity_address_details reads BusinessEntityAddress, which carries AddressTypeID but not hub_address_type's key NAME: joined in through AddressType under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_business_entity_contact, built by the modeler from BusinessEntityContact, requires surrogate→natural-key translation through ContactType for hub_contact_type (ContactTypeID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: satellite sat_business_entity_contact_details reads BusinessEntityContact, which carries ContactTypeID but not hub_contact_type's key NAME: joined in through ContactType under a ratified key; review the translation model** _(link_proposer)_
