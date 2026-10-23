# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-10-23
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 122 requirement(s) and 20 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (7)

- **hub_business_entity** — business key `BusinessEntityID`. Company-wide party register (customers, vendors, employees, persons). A person is a business entity with no separate identifier, so persons share this hub rather than getting a hub of their own. Email, phone and credential relations are also keyed by BusinessEntityID and feed this hub. Integrated from 5 source(s): BusinessEntity.BusinessEntityID, Person.BusinessEntityID, EmailAddress.BusinessEntityID, PersonPhone.BusinessEntityID, Password.BusinessEntityID; canonical staging key column `BUSINESSENTITYID`. _(requirements: REQ-001, REQ-002, REQ-003, REQ-004, REQ-007, REQ-008, REQ-045, REQ-047, REQ-049, REQ-077)_
- **hub_address** — business key `AddressID`. Postal address, recorded once and shareable by many parties. _(requirements: REQ-001-2, REQ-007-2)_
- **hub_address_type** — business key `AddressTypeID`. Reference list of address types (Billing, Home, Shipping). _(requirements: REQ-011-2, REQ-015-2, REQ-068)_
- **hub_contact_type** — business key `ContactTypeID`. Reference list of contact roles a person plays for an organisation. _(requirements: REQ-037-2, REQ-038-2, REQ-068)_
- **hub_phone_number_type** — business key `PhoneNumberTypeID`. Reference list of phone number kinds (home, work, mobile). _(requirements: REQ-037, REQ-041, REQ-068)_
- **hub_country_region** — business key `CountryRegionCode`. Country or region identified by ISO code. _(requirements: REQ-022-2, REQ-068)_
- **hub_state_province** — business key `StateProvinceID`. State or province identified by its own number. _(requirements: REQ-023-2, REQ-068)_

### Links (4)

- **link_address_state_province** — connects hub_address, hub_state_province. The state or province in which an address sits; country is derived via the state. Unit of work: AddressID + StateProvinceID from Address. _(requirements: REQ-002-2, REQ-003-2, REQ-005-2, REQ-055)_
- **link_state_province_country_region** — connects hub_state_province, hub_country_region. Each state or province belongs to exactly one country or region. Unit of work: StateProvinceID + CountryRegionCode from StateProvince. _(requirements: REQ-024-2, REQ-025-2, REQ-005-2)_
- **link_business_entity_address** — connects hub_business_entity, hub_address, hub_address_type. Party-address relationship in a given capacity (address type); unique by party, address and type. Unit of work: BusinessEntityID + AddressID + AddressTypeID from BusinessEntityAddress. _(requirements: REQ-009-2, REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2, REQ-016-2, REQ-017-2, REQ-020-2, REQ-056)_
- **link_business_entity_contact** — connects hub_business_entity (organisation), hub_business_entity (contact_person), hub_contact_type. Organisational contact relationship: an organisation (BusinessEntityID), the person acting as its contact (PersonID) and the contact role; unique by all three. Unit of work: BusinessEntityID + PersonID + ContactTypeID from BusinessEntityContact. _(requirements: REQ-035-2, REQ-036-2, REQ-037-2, REQ-039-2, REQ-040-2, REQ-041-2, REQ-042-2, REQ-045-2, REQ-046, REQ-057)_

### Satellites (17)

- **sat_business_entity_details** — on hub_business_entity; payload: ModifiedDate. Business entity register change timestamp; rowguid excluded as replication-only technical metadata. Source table: BusinessEntity. _(requirements: REQ-005, REQ-006)_
- **sat_business_entity_person_name** — on hub_business_entity; payload: NameStyle, Title, FirstName, MiddleName, LastName, Suffix, ModifiedDate. Person name details with full history. Source table: Person. Split rationale: Ordinary personal name data; carries the Person last-modified timestamp (held in this satellite only).. _(requirements: REQ-014, REQ-015, REQ-016, REQ-017, REQ-018, REQ-019, REQ-028, REQ-052)_
- **sat_business_entity_person_type** — on hub_business_entity; payload: PersonType. Primary person type classification code. Source table: Person. Split rationale: Classification used for wide aggregated reporting; changes at a different rate from names.. _(requirements: REQ-009, REQ-010, REQ-011, REQ-012, REQ-013)_
- **sat_business_entity_person_consent** — on hub_business_entity; payload: EmailPromotion. Email promotion (marketing consent) preference with full history for compliance audit. Source table: Person. Split rationale: Compliance-sensitive consent tracked independently of name changes.. _(requirements: REQ-020, REQ-021, REQ-022, REQ-023, REQ-053, REQ-074, REQ-075)_
- **sat_business_entity_person_sensitive** — on hub_business_entity; payload: AdditionalContactInfo, Demographics. Sensitive XML additional contact information and demographics, access-restricted. Source table: Person. Split rationale: Data classification: sensitive personal data restricted separately; XML data type.. _(requirements: REQ-024, REQ-025, REQ-026, REQ-027, REQ-070, REQ-071)_
- **sat_business_entity_email** — on hub_business_entity; payload: EmailAddress, ModifiedDate. A person's email addresses, numbered within the person, with history. Multi-active satellite, child dependent key: EmailAddressID. Source table: EmailAddress. Split rationale: Own source relation at finer grain (several per person).. _(requirements: REQ-029, REQ-030, REQ-031, REQ-032, REQ-033, REQ-034, REQ-054, REQ-062)_
- **sat_business_entity_phone** — on hub_business_entity; payload: ModifiedDate. A person's telephone numbers qualified by phone number type, with history. Multi-active satellite, child dependent key: PhoneNumberTypeID, PhoneNumber. Source table: PersonPhone. Split rationale: Own source relation at finer grain (several per person).. _(requirements: REQ-035, REQ-036, REQ-038, REQ-039, REQ-040, REQ-054, REQ-063)_
- **sat_business_entity_credential** — on hub_business_entity; payload: ModifiedDate. Existence and last-change date of a sign-in credential only; hash and salt are never loaded. Source table: Password. Split rationale: Separate source; credential values excluded for security.. _(requirements: REQ-042, REQ-043, REQ-044, REQ-045, REQ-073)_
- **sat_address_details** — on hub_address; payload: AddressLine1, AddressLine2, City, PostalCode, ModifiedDate. Street, city and postal details of an address with full history. Source table: Address. _(requirements: REQ-002-2, REQ-005-2, REQ-006-2, REQ-008-2, REQ-055)_
- **sat_address_location** — on hub_address; payload: SpatialLocation. Geographic coordinates of an address for mapping and territory analysis. Source table: Address. Split rationale: Spatial data type and personal-data classification differ from street details.. _(requirements: REQ-004-2, REQ-066, REQ-070)_
- **sat_address_type_details** — on hub_address_type; payload: Name, ModifiedDate. Address type descriptive name. Source table: AddressType. _(requirements: REQ-015-2)_
- **sat_contact_type_details** — on hub_contact_type; payload: Name, ModifiedDate. Contact type descriptive name. Source table: ContactType. _(requirements: REQ-038-2)_
- **sat_phone_number_type_details** — on hub_phone_number_type; payload: Name, ModifiedDate. Phone number type name, historised so renames are visible. Source table: PhoneNumberType. _(requirements: REQ-037, REQ-041)_
- **sat_country_region_details** — on hub_country_region; payload: Name, ModifiedDate. Country or region name, historised so renames are visible. Source table: CountryRegion. _(requirements: REQ-022-2, REQ-033-2, REQ-034-2)_
- **sat_state_province_details** — on hub_state_province; payload: StateProvinceCode, IsOnlyStateProvinceFlag, Name, ModifiedDate. State or province ISO code, no-genuine-code flag and name. Source table: StateProvince. _(requirements: REQ-023-2, REQ-026-2, REQ-027-2, REQ-033-2, REQ-034-2, REQ-067)_
- **sat_state_province_territory** — on hub_state_province; payload: TerritoryID. Sales territory assignment of a state or province, historised; territory descriptions come from the sales area. Source table: StateProvince. Split rationale: Territory reassignment changes at a different rate and drives historical roll-ups.. _(requirements: REQ-028-2, REQ-029-2, REQ-030-2, REQ-031-2, REQ-032-2, REQ-058)_
- **sat_business_entity_address_details** — on link_business_entity_address; payload: ModifiedDate. Last-changed timestamp of the party-address relationship. Source table: BusinessEntityAddress. _(requirements: REQ-018-2, REQ-019-2, REQ-056)_

### Source mappings (39)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `BusinessEntityID` → `BusinessEntity`.`BusinessEntityID` — exact_name, accepted
- `AddressID` → `Address`.`AddressID` — exact_name, accepted
- `AddressTypeID` → `AddressType`.`AddressTypeID` — exact_name, accepted
- `ContactTypeID` → `ContactType`.`ContactTypeID` — exact_name, accepted
- `PhoneNumberTypeID` → `PhoneNumberType`.`PhoneNumberTypeID` — exact_name, accepted
- `CountryRegionCode` → `CountryRegion`.`CountryRegionCode` — exact_name, accepted
- `StateProvinceID` → `StateProvince`.`StateProvinceID` — exact_name, accepted
- `ModifiedDate` → `BusinessEntity`.`ModifiedDate` — exact_name, accepted
- `NameStyle` → `Person`.`NameStyle` — exact_name, accepted
- `Title` → `Person`.`Title` — exact_name, accepted
- `FirstName` → `Person`.`FirstName` — exact_name, accepted
- `MiddleName` → `Person`.`MiddleName` — exact_name, accepted
- `LastName` → `Person`.`LastName` — exact_name, accepted
- `Suffix` → `Person`.`Suffix` — exact_name, accepted
- `PersonType` → `Person`.`PersonType` — exact_name, accepted
- `EmailPromotion` → `Person`.`EmailPromotion` — exact_name, accepted
- `AdditionalContactInfo` → `Person`.`AdditionalContactInfo` — exact_name, accepted
- `Demographics` → `Person`.`Demographics` — exact_name, accepted
- `EmailAddress` → `EmailAddress`.`EmailAddress` — exact_name, accepted
- `AddressLine1` → `Address`.`AddressLine1` — exact_name, accepted
- `AddressLine2` → `Address`.`AddressLine2` — exact_name, accepted
- `City` → `Address`.`City` — exact_name, accepted
- `PostalCode` → `Address`.`PostalCode` — exact_name, accepted
- `ModifiedDate` → `Address`.`ModifiedDate` — exact_name, accepted
- `SpatialLocation` → `Address`.`SpatialLocation` — exact_name, accepted
- `Name` → `AddressType`.`Name` — exact_name, accepted
- `ModifiedDate` → `AddressType`.`ModifiedDate` — exact_name, accepted
- `Name` → `ContactType`.`Name` — exact_name, accepted
- `ModifiedDate` → `ContactType`.`ModifiedDate` — exact_name, accepted
- `Name` → `PhoneNumberType`.`Name` — exact_name, accepted
- `ModifiedDate` → `PhoneNumberType`.`ModifiedDate` — exact_name, accepted
- `Name` → `CountryRegion`.`Name` — exact_name, accepted
- `ModifiedDate` → `CountryRegion`.`ModifiedDate` — exact_name, accepted
- `StateProvinceCode` → `StateProvince`.`StateProvinceCode` — exact_name, accepted
- `IsOnlyStateProvinceFlag` → `StateProvince`.`IsOnlyStateProvinceFlag` — exact_name, accepted
- `Name` → `StateProvince`.`Name` — exact_name, accepted
- `ModifiedDate` → `StateProvince`.`ModifiedDate` — exact_name, accepted
- `TerritoryID` → `StateProvince`.`TerritoryID` — exact_name, accepted
- `ModifiedDate` → `BusinessEntityAddress`.`ModifiedDate` — exact_name, accepted

## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.
- Caveat: 3 construct(s) could not be generated and are flagged for human review: sat_business_entity_credential, sat_business_entity_email, sat_business_entity_phone.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/person_requirements.md
- Generated dbt models: 28 raw-vault model(s) + 24 staging model(s) (see `state.artifacts`)
