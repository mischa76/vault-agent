# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 115 requirement(s) and 18 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (7)

- **hub_business_entity** — business key `BusinessEntityID`. Company-wide party register (customers, vendors, employees, persons); persons share the same party number and are not a separate hub. Email, phone and credential relations are registered as feeds since they carry the same party number. Integrated from 5 source(s): BusinessEntity.BusinessEntityID, Person.BusinessEntityID, EmailAddress.BusinessEntityID, PersonPhone.BusinessEntityID, Password.BusinessEntityID; canonical staging key column `BUSINESSENTITYID`. _(requirements: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-009, REQ-010, REQ-065)_
- **hub_address** — business key `AddressID`. Postal address identified by its own address number, shareable across parties. _(requirements: REQ-001-2, REQ-007-2)_
- **hub_address_type** — business key `Name`. Address type reference (Billing, Home, Shipping), keyed on name per decided key. _(requirements: REQ-011-2, REQ-014-2, REQ-056)_
- **hub_contact_type** — business key `Name`. Contact type reference describing the role a person plays for an organisation, keyed on name per decided key. _(requirements: REQ-035-2, REQ-036-2, REQ-056)_
- **hub_phone_number_type** — business key `PhoneNumberTypeID`. Phone number type reference (home, work, mobile). _(requirements: REQ-040, REQ-041, REQ-045, REQ-056)_
- **hub_country_region** — business key `CountryRegionCode`. Country or region identified by ISO code. _(requirements: REQ-020-2, REQ-056)_
- **hub_state_province** — business key `Name`. State or province reference, keyed on name per decided key. _(requirements: REQ-021-2, REQ-056)_

### Links (4)

- **link_address_state_province** — connects hub_address, hub_state_province. The state or province in which an address sits (country derived via state). Unit of work: AddressID + StateProvince. _(requirements: REQ-002-2, REQ-003-2, REQ-005-2)_
- **link_state_province_country_region** — connects hub_state_province, hub_country_region. Every state or province belongs to exactly one country or region. Unit of work: StateProvince + CountryRegionCode. _(requirements: REQ-022-2, REQ-023-2, REQ-003-2)_
- **link_business_entity_address** — connects hub_business_entity, hub_address, hub_address_type. Party-address relationship qualified by address type; party, address and type together are unique. Unit of work: BusinessEntityID + AddressID + AddressType. _(requirements: REQ-009-2, REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-015-2, REQ-016-2, REQ-018-2)_
- **link_business_entity_contact** — connects hub_business_entity, hub_business_entity (person), hub_contact_type. Organisational contact relationship: organisation party, person party acting as contact, and contact role. Unit of work: BusinessEntityID (organisation) + PersonID + ContactType. _(requirements: REQ-033-2, REQ-034-2, REQ-035-2, REQ-037-2, REQ-038-2, REQ-039-2, REQ-040-2, REQ-042-2, REQ-043-2)_

### Satellites (17)

- **sat_business_entity_details** — on hub_business_entity; payload: ModifiedDate. Business entity register last-changed timestamp; rowguid excluded as technical metadata. Source table: BusinessEntity. _(requirements: REQ-006, REQ-007, REQ-008)_
- **sat_business_entity_person_name** — on hub_business_entity; payload: PersonType, NameStyle, Title, FirstName, MiddleName, LastName, Suffix, ModifiedDate. Person type and name details with history. Source table: Person. Split rationale: Ordinary name/type reporting data; carries the Person last-modified timestamp.. _(requirements: REQ-011, REQ-012, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-018, REQ-019, REQ-020, REQ-021, REQ-032, REQ-049-2)_
- **sat_business_entity_person_consent** — on hub_business_entity; payload: EmailPromotion. Email promotion consent with full history. Source table: Person. Split rationale: Compliance-sensitive consent split out for audit history and access control.. _(requirements: REQ-022, REQ-023, REQ-024, REQ-025, REQ-026, REQ-027, REQ-062, REQ-063)_
- **sat_business_entity_person_sensitive** — on hub_business_entity; payload: AdditionalContactInfo, Demographics. Sensitive XML additional contact info and demographics. Source table: Person. Split rationale: Sensitive classification and XML data type; restricted separately.. _(requirements: REQ-028, REQ-029, REQ-030, REQ-031, REQ-058)_
- **sat_business_entity_email** — on hub_business_entity; payload: EmailAddress, ModifiedDate. All email addresses of a person, numbered within the person, with history. Multi-active satellite, child dependent key: EmailAddressID. Source table: EmailAddress. _(requirements: REQ-033, REQ-034, REQ-035, REQ-036, REQ-037, REQ-038, REQ-049-2)_
- **sat_business_entity_phone** — on hub_business_entity; payload: ModifiedDate. All telephone numbers of a person qualified by phone number type, with history. Multi-active satellite, child dependent key: PhoneNumberTypeID, PhoneNumber. Source table: PersonPhone. _(requirements: REQ-039, REQ-040, REQ-042, REQ-043, REQ-044, REQ-049-2)_
- **sat_business_entity_credential** — on hub_business_entity; payload: ModifiedDate. Existence and last-change of a sign-in credential only; hash and salt excluded. Source table: Password. Split rationale: Separate source; credential values never loaded.. _(requirements: REQ-046, REQ-047, REQ-048, REQ-050, REQ-061)_
- **sat_address_details** — on hub_address; payload: AddressLine1, AddressLine2, City, PostalCode, ModifiedDate. Street address details with history. Source table: Address. _(requirements: REQ-002-2, REQ-005-2, REQ-006-2, REQ-008-2, REQ-049-2)_
- **sat_address_location** — on hub_address; payload: SpatialLocation. Geographic coordinates of an address. Source table: Address. Split rationale: Personal geographic data and spatial data type.. _(requirements: REQ-004-2, REQ-054, REQ-058)_
- **sat_address_type_details** — on hub_address_type; payload: AddressTypeID, ModifiedDate. Address type source identifier and last change. Source table: AddressType. _(requirements: REQ-014-2)_
- **sat_contact_type_details** — on hub_contact_type; payload: ContactTypeID, ModifiedDate. Contact type source identifier and last change. Source table: ContactType. _(requirements: REQ-036-2)_
- **sat_phone_number_type_details** — on hub_phone_number_type; payload: Name, ModifiedDate. Phone number type name with history of renames. Source table: PhoneNumberType. _(requirements: REQ-041, REQ-045)_
- **sat_country_region_details** — on hub_country_region; payload: Name, ModifiedDate. Country or region name with visible renames. Source table: CountryRegion. _(requirements: REQ-020-2, REQ-031-2, REQ-032-2)_
- **sat_state_province_details** — on hub_state_province; payload: StateProvinceID, StateProvinceCode, IsOnlyStateProvinceFlag, ModifiedDate. State or province code, no-genuine-code flag and identifier. Source table: StateProvince. _(requirements: REQ-021-2, REQ-024-2, REQ-025-2, REQ-031-2, REQ-055)_
- **sat_state_province_territory** — on hub_state_province; payload: TerritoryID. Sales territory assignment of a state or province, tracked over time; territory descriptions come from the sales area. Source table: StateProvince. Split rationale: Territory assignment changes independently and needs its own history.. _(requirements: REQ-026-2, REQ-027-2, REQ-028-2, REQ-029-2, REQ-030-2, REQ-049-2)_
- **sat_business_entity_address_details** — on link_business_entity_address; payload: ModifiedDate. Last-changed timestamp of the party-address relationship. Source table: BusinessEntityAddress. _(requirements: REQ-017-2, REQ-018-2)_
- **sat_business_entity_contact_details** — on link_business_entity_contact; payload: ModifiedDate. Last-changed timestamp of the contact relationship. Source table: BusinessEntityContact. _(requirements: REQ-041-2, REQ-042-2)_

### Hub keys decided before modelling (4)

- **AddressType** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `AddressTypeID` (0.60); primary key `AddressTypeID`.
- **ContactType** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `ContactTypeID` (0.60); primary key `ContactTypeID`.
- **CountryRegion** — key `CountryRegionCode`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `CountryRegionCode` (0.90); primary key `CountryRegionCode`.
- **StateProvince** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `StateProvinceID` (0.75); primary key `StateProvinceID`.

### Source mappings (40)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `BusinessEntityID` → `BusinessEntity`.`BusinessEntityID` — exact_name, accepted
- `AddressID` → `Address`.`AddressID` — exact_name, accepted
- `Name` → `AddressType`.`Name` — exact_name, accepted
- `Name` → `ContactType`.`Name` — exact_name, accepted
- `PhoneNumberTypeID` → `PhoneNumberType`.`PhoneNumberTypeID` — exact_name, accepted
- `CountryRegionCode` → `CountryRegion`.`CountryRegionCode` — exact_name, accepted
- `Name` → `StateProvince`.`Name` — exact_name, accepted
- `ModifiedDate` → `BusinessEntity`.`ModifiedDate` — exact_name, accepted
- `PersonType` → `Person`.`PersonType` — exact_name, accepted
- `NameStyle` → `Person`.`NameStyle` — exact_name, accepted
- `Title` → `Person`.`Title` — exact_name, accepted
- `FirstName` → `Person`.`FirstName` — exact_name, accepted
- `MiddleName` → `Person`.`MiddleName` — exact_name, accepted
- `LastName` → `Person`.`LastName` — exact_name, accepted
- `Suffix` → `Person`.`Suffix` — exact_name, accepted
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
- `AddressTypeID` → `AddressType`.`AddressTypeID` — exact_name, accepted
- `ModifiedDate` → `AddressType`.`ModifiedDate` — exact_name, accepted
- `ContactTypeID` → `ContactType`.`ContactTypeID` — exact_name, accepted
- `ModifiedDate` → `ContactType`.`ModifiedDate` — exact_name, accepted
- `Name` → `PhoneNumberType`.`Name` — exact_name, accepted
- `ModifiedDate` → `PhoneNumberType`.`ModifiedDate` — exact_name, accepted
- `Name` → `CountryRegion`.`Name` — exact_name, accepted
- `ModifiedDate` → `CountryRegion`.`ModifiedDate` — exact_name, accepted
- `StateProvinceID` → `StateProvince`.`StateProvinceID` — exact_name, accepted
- `StateProvinceCode` → `StateProvince`.`StateProvinceCode` — exact_name, accepted
- `IsOnlyStateProvinceFlag` → `StateProvince`.`IsOnlyStateProvinceFlag` — exact_name, accepted
- `ModifiedDate` → `StateProvince`.`ModifiedDate` — exact_name, accepted
- `TerritoryID` → `StateProvince`.`TerritoryID` — exact_name, accepted
- `ModifiedDate` → `BusinessEntityAddress`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `BusinessEntityContact`.`ModifiedDate` — exact_name, accepted

## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/person_requirements.md
- Generated dbt models: 28 raw-vault model(s) + 42 staging model(s) (see `state.artifacts`)
