# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-10-21
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 115 requirement(s) and 18 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (7)

- **hub_business_entity** — business key `BusinessEntityID`. Company-wide party register (customers, vendors, employees, stores, persons). Persons share the same business entity number, so person data attaches here as satellites rather than a separate hub. Email addresses and credentials are keyed by the same number and are declared as feeds so their satellites bind to their own source. Integrated from 4 source(s): BusinessEntity.BusinessEntityID, Person.BusinessEntityID, EmailAddress.BusinessEntityID, Password.BusinessEntityID; canonical staging key column `BUSINESSENTITYID`. _(requirements: REQ-001, REQ-002, REQ-003, REQ-004, REQ-008, REQ-009, REQ-034, REQ-050, REQ-065)_
- **hub_address** — business key `AddressID`. Postal address recorded once and shareable by many parties. _(requirements: REQ-001-2, REQ-007-2)_
- **hub_address_type** — business key `AddressTypeID`. Reference list of address types (Billing, Home, Shipping). _(requirements: REQ-015-2, REQ-011-2, REQ-056)_
- **hub_contact_type** — business key `ContactTypeID`. Reference list of contact roles. _(requirements: REQ-035-2, REQ-036-2, REQ-056)_
- **hub_phone_number_type** — business key `PhoneNumberTypeID`. Reference list of phone number types (home, work, mobile). _(requirements: REQ-039, REQ-040, REQ-056)_
- **hub_country_region** — business key `CountryRegionCode`. Countries and regions identified by ISO code. _(requirements: REQ-021-2, REQ-056)_
- **hub_state_province** — business key `StateProvinceID`. States and provinces identified by their own number. _(requirements: REQ-022-2, REQ-056)_

### Links (5)

- **link_business_entity_address** — connects hub_business_entity, hub_address, hub_address_type. Which addresses a party uses and in what capacity; party+address+type is unique. Unit of work: BusinessEntityID + AddressID + AddressTypeID. _(requirements: REQ-009-2, REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2, REQ-016-2, REQ-017-2, REQ-019-2)_
- **link_business_entity_contact** — connects hub_business_entity, hub_business_entity (person), hub_contact_type. Organisation (business entity) to the person acting as its contact, in a contact role; organisation+person+role is unique. Unit of work: BusinessEntityID (organisation) + PersonID + ContactTypeID. _(requirements: REQ-033-2, REQ-034-2, REQ-035-2, REQ-037-2, REQ-038-2, REQ-039-2, REQ-040-2, REQ-042-2, REQ-043-2)_
- **link_business_entity_phone_number_type** — connects hub_business_entity, hub_phone_number_type. A person's telephone numbers qualified by phone number type. Unit of work: BusinessEntityID + PhoneNumberTypeID (phone number as child key). _(requirements: REQ-038, REQ-039, REQ-041, REQ-042)_
- **link_address_state_province** — connects hub_address, hub_state_province. The state or province in which an address sits (country derived via state). _(requirements: REQ-002-2, REQ-003-2, REQ-005-2, REQ-028-2)_
- **link_state_province_country_region** — connects hub_state_province, hub_country_region. Each state or province belongs to exactly one country or region. _(requirements: REQ-023-2, REQ-024-2, REQ-003-2)_

### Satellites (17)

- **sat_business_entity_details** — on hub_business_entity; payload: ModifiedDate. Business entity register last-changed timestamp; rowguid excluded as technical replication metadata. Source table: BusinessEntity. _(requirements: REQ-005, REQ-006, REQ-007)_
- **sat_business_entity_person_name** — on hub_business_entity; payload: PersonType, NameStyle, Title, FirstName, MiddleName, LastName, Suffix, ModifiedDate. Person type and name details with history. Source table: Person. Split rationale: Ordinary name/contact PII; carries the Person ModifiedDate once.. _(requirements: REQ-010, REQ-011, REQ-012, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-018, REQ-019, REQ-020, REQ-029, REQ-030, REQ-049-2)_
- **sat_business_entity_marketing_consent** — on hub_business_entity; payload: EmailPromotion. Email promotion consent level, historised for audit. Source table: Person. Split rationale: Consent is a distinct classification with its own audit need and rate of change.. _(requirements: REQ-021, REQ-022, REQ-023, REQ-024, REQ-062, REQ-063)_
- **sat_business_entity_person_sensitive** — on hub_business_entity; payload: AdditionalContactInfo, Demographics. Sensitive XML additional contact info and demographics, access-restricted. Source table: Person. Split rationale: Sensitive data classification restricted separately from name reporting.. _(requirements: REQ-025, REQ-026, REQ-027, REQ-028, REQ-058)_
- **sat_business_entity_credential** — on hub_business_entity; payload: ModifiedDate. Existence and last-change of a sign-in credential only; hash and salt are excluded. Source table: Password. Split rationale: Separate source; credential values excluded from the warehouse.. _(requirements: REQ-045, REQ-046, REQ-047, REQ-048, REQ-050, REQ-061)_
- **sat_business_entity_email** — on hub_business_entity; payload: EmailAddress, ModifiedDate. All email addresses of a person, numbered within the person, historised. Multi-active satellite, child dependent key: EmailAddressID. Source table: EmailAddress. Split rationale: Own source at finer grain, several concurrent rows per person.. _(requirements: REQ-031, REQ-032, REQ-033, REQ-034, REQ-035, REQ-036, REQ-037)_
- **sat_business_entity_phone_number_type_phones** — on link_business_entity_phone_number_type; payload: ModifiedDate. Telephone numbers of a person per phone type, historised. Multi-active satellite, child dependent key: PhoneNumber. Source table: PersonPhone. _(requirements: REQ-038, REQ-039, REQ-043, REQ-049-2)_
- **sat_business_entity_address_details** — on link_business_entity_address; payload: ModifiedDate. Last-changed timestamp of party-address relationships. Source table: BusinessEntityAddress. _(requirements: REQ-018-2, REQ-019-2)_
- **sat_business_entity_contact_details** — on link_business_entity_contact; payload: ModifiedDate. Last-changed timestamp of contact relationships. Source table: BusinessEntityContact. _(requirements: REQ-041-2, REQ-042-2)_
- **sat_address_details** — on hub_address; payload: AddressLine1, AddressLine2, City, PostalCode, ModifiedDate. Street, city and postal details, historised. Source table: Address. _(requirements: REQ-002-2, REQ-005-2, REQ-006-2, REQ-008-2, REQ-049-2)_
- **sat_address_location** — on hub_address; payload: SpatialLocation. Geographic coordinates of the address. Source table: Address. Split rationale: Distinct data type (spatial) and sensitive classification.. _(requirements: REQ-004-2, REQ-054, REQ-058)_
- **sat_address_type_details** — on hub_address_type; payload: Name, ModifiedDate. Address type name. Source table: AddressType. _(requirements: REQ-015-2)_
- **sat_contact_type_details** — on hub_contact_type; payload: Name, ModifiedDate. Contact type name. Source table: ContactType. _(requirements: REQ-036-2)_
- **sat_phone_number_type_details** — on hub_phone_number_type; payload: Name, ModifiedDate. Phone number type name, historised so renames are visible. Source table: PhoneNumberType. _(requirements: REQ-040, REQ-044)_
- **sat_country_region_details** — on hub_country_region; payload: Name, ModifiedDate. Country or region name, historised so renames are visible. Source table: CountryRegion. _(requirements: REQ-021-2, REQ-031-2, REQ-032-2)_
- **sat_state_province_details** — on hub_state_province; payload: StateProvinceCode, IsOnlyStateProvinceFlag, Name, ModifiedDate. State/province code, no-genuine-code flag and name. Source table: StateProvince. _(requirements: REQ-022-2, REQ-025-2, REQ-026-2, REQ-031-2, REQ-032-2, REQ-055)_
- **sat_state_province_territory** — on hub_state_province; payload: TerritoryID. Sales territory assignment of the state/province, historised; territory descriptions come from the sales area. Source table: StateProvince. Split rationale: Territory assignment changes at a different rate and needs separate history tracking.. _(requirements: REQ-027-2, REQ-028-2, REQ-029-2, REQ-030-2, REQ-049-2)_

### Source mappings (41)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `BusinessEntityID` → `BusinessEntity`.`BusinessEntityID` — exact_name, proposed
- `AddressID` → `Address`.`AddressID` — exact_name, proposed
- `AddressTypeID` → `AddressType`.`AddressTypeID` — exact_name, proposed
- `ContactTypeID` → `ContactType`.`ContactTypeID` — exact_name, proposed
- `PhoneNumberTypeID` → `PhoneNumberType`.`PhoneNumberTypeID` — exact_name, proposed
- `CountryRegionCode` → `CountryRegion`.`CountryRegionCode` — exact_name, proposed
- `StateProvinceID` → `StateProvince`.`StateProvinceID` — exact_name, proposed
- `ModifiedDate` → `BusinessEntity`.`ModifiedDate` — exact_name, proposed
- `PersonType` → `Person`.`PersonType` — exact_name, proposed
- `NameStyle` → `Person`.`NameStyle` — exact_name, proposed
- `Title` → `Person`.`Title` — exact_name, proposed
- `FirstName` → `Person`.`FirstName` — exact_name, proposed
- `MiddleName` → `Person`.`MiddleName` — exact_name, proposed
- `LastName` → `Person`.`LastName` — exact_name, proposed
- `Suffix` → `Person`.`Suffix` — exact_name, proposed
- `EmailPromotion` → `Person`.`EmailPromotion` — exact_name, proposed
- `AdditionalContactInfo` → `Person`.`AdditionalContactInfo` — exact_name, proposed
- `Demographics` → `Person`.`Demographics` — exact_name, proposed
- `EmailAddress` → `EmailAddress`.`EmailAddress` — exact_name, proposed
- `ModifiedDate` → `PersonPhone`.`ModifiedDate` — exact_name, proposed
- `ModifiedDate` → `BusinessEntityAddress`.`ModifiedDate` — exact_name, proposed
- `ModifiedDate` → `BusinessEntityContact`.`ModifiedDate` — exact_name, proposed
- `AddressLine1` → `Address`.`AddressLine1` — exact_name, proposed
- `AddressLine2` → `Address`.`AddressLine2` — exact_name, proposed
- `City` → `Address`.`City` — exact_name, proposed
- `PostalCode` → `Address`.`PostalCode` — exact_name, proposed
- `ModifiedDate` → `Address`.`ModifiedDate` — exact_name, proposed
- `SpatialLocation` → `Address`.`SpatialLocation` — exact_name, proposed
- `Name` → `AddressType`.`Name` — exact_name, proposed
- `ModifiedDate` → `AddressType`.`ModifiedDate` — exact_name, proposed
- `Name` → `ContactType`.`Name` — exact_name, proposed
- `ModifiedDate` → `ContactType`.`ModifiedDate` — exact_name, proposed
- `Name` → `PhoneNumberType`.`Name` — exact_name, proposed
- `ModifiedDate` → `PhoneNumberType`.`ModifiedDate` — exact_name, proposed
- `Name` → `CountryRegion`.`Name` — exact_name, proposed
- `ModifiedDate` → `CountryRegion`.`ModifiedDate` — exact_name, proposed
- `StateProvinceCode` → `StateProvince`.`StateProvinceCode` — exact_name, proposed
- `IsOnlyStateProvinceFlag` → `StateProvince`.`IsOnlyStateProvinceFlag` — exact_name, proposed
- `Name` → `StateProvince`.`Name` — exact_name, proposed
- `ModifiedDate` → `StateProvince`.`ModifiedDate` — exact_name, proposed
- `TerritoryID` → `StateProvince`.`TerritoryID` — exact_name, proposed

## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.
- Caveat: 2 construct(s) could not be generated and are flagged for human review: sat_business_entity_credential, sat_business_entity_email.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/requirements.md
- Generated dbt models: 29 raw-vault model(s) + 26 staging model(s) (see `state.artifacts`)
