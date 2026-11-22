# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 132 requirement(s) and 18 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (7)

- **hub_business_entity** — business key `BusinessEntityID`. Company-wide party (business entity) register; persons share the same business entity number and therefore the same hub (one hub per business key). Integration point for sales, HR, purchasing and marketing. Email addresses and sign-in credentials attach via the same business entity number and are declared as feeds so their satellites bind to their own source relations. Integrated from 4 source(s): BusinessEntity.BusinessEntityID, Person.BusinessEntityID, EmailAddress.BusinessEntityID, Password.BusinessEntityID; canonical staging key column `BUSINESSENTITYID`. _(requirements: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-011, REQ-012, REQ-037, REQ-055, REQ-076)_
- **hub_address** — business key `AddressID`. Postal address identified by its own address number, shareable by several parties. _(requirements: REQ-001-2, REQ-007-2)_
- **hub_address_type** — business key `Name`. Reference list of address types (Billing, Home, Shipping), keyed on name per decided key. _(requirements: REQ-011-2, REQ-012-2, REQ-016-2, REQ-067)_
- **hub_contact_type** — business key `Name`. Reference list of contact types (role a person plays for an organisation), keyed on name per decided key. _(requirements: REQ-037-2, REQ-038-2, REQ-067)_
- **hub_phone_number_type** — business key `PhoneNumberTypeID`. Reference list of phone number types (home, work, mobile). _(requirements: REQ-045, REQ-049, REQ-067)_
- **hub_country_region** — business key `CountryRegionCode`. Country or region identified by its ISO code. _(requirements: REQ-022-2, REQ-025-2, REQ-067)_
- **hub_state_province** — business key `Name`. State or province reference list, keyed on name per decided key. _(requirements: REQ-023-2, REQ-024-2, REQ-067)_

### Links (5)

- **link_business_entity_address** — connects hub_business_entity, hub_address, hub_address_type. Party-address relationship: which address a party uses and in what capacity (address type). Many-to-many. Unit of work: BusinessEntityID + AddressID + AddressTypeID (BusinessEntityAddress). _(requirements: REQ-009-2, REQ-010-2, REQ-011-2, REQ-013-2, REQ-014-2, REQ-015-2, REQ-017-2, REQ-018-2, REQ-021-2, REQ-055-2)_
- **link_business_entity_contact** — connects hub_business_entity, hub_business_entity (person), hub_contact_type. Contact relationship: organisation (business entity), the person acting as its contact (role-qualified), and the contact type. Unit of work: BusinessEntityID + PersonID + ContactTypeID (BusinessEntityContact). _(requirements: REQ-035-2, REQ-036-2, REQ-037-2, REQ-039-2, REQ-040-2, REQ-041-2, REQ-042-2, REQ-043-2, REQ-046-2, REQ-056-2)_
- **link_business_entity_phone_number_type** — connects hub_business_entity, hub_phone_number_type. A person's telephone numbers qualified by phone number type (PersonPhone). Unit of work: BusinessEntityID + PhoneNumberTypeID (PersonPhone). _(requirements: REQ-043, REQ-044, REQ-046, REQ-047, REQ-062)_
- **link_address_state_province** — connects hub_address, hub_state_province. The state or province an address sits in (country derived via the state). _(requirements: REQ-002-2, REQ-003-2, REQ-005-2, REQ-029-2)_
- **link_state_province_country_region** — connects hub_state_province, hub_country_region. Each state or province belongs to exactly one country or region. _(requirements: REQ-024-2, REQ-025-2, REQ-005-2)_

### Satellites (17)

- **sat_business_entity_details** — on hub_business_entity; payload: ModifiedDate. Business entity existence and last-changed timestamp; rowguid excluded as technical metadata. Source table: BusinessEntity. _(requirements: REQ-007, REQ-009, REQ-010)_
- **sat_business_entity_person_name** — on hub_business_entity; payload: PersonType, NameStyle, Title, FirstName, MiddleName, LastName, Suffix, ModifiedDate. Person type and name details with full history. Source table: Person. Split rationale: Ordinary name/contact data, separated from compliance-sensitive consent and sensitive demographics.. _(requirements: REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-018, REQ-019, REQ-020, REQ-021, REQ-022, REQ-023, REQ-034, REQ-051-2)_
- **sat_business_entity_person_consent** — on hub_business_entity; payload: EmailPromotion. Email promotion preference (marketing consent) with history built by the warehouse. Source table: Person. Split rationale: Compliance-sensitive classification; history tracked separately.. _(requirements: REQ-024, REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-052-2, REQ-073, REQ-074)_
- **sat_business_entity_person_sensitive** — on hub_business_entity; payload: AdditionalContactInfo, Demographics. Additional contact information and demographics (XML), access restricted. Source table: Person. Split rationale: Sensitive data classification and XML data type; restricted separately from name reporting.. _(requirements: REQ-030, REQ-031, REQ-032, REQ-033, REQ-069, REQ-070)_
- **sat_business_entity_email** — on hub_business_entity; payload: EmailAddress, ModifiedDate. A person's email addresses, numbered within the person, with history of superseded values. Multi-active satellite, child dependent key: EmailAddressID. Source table: EmailAddress. Split rationale: Own source relation at finer grain (several per person); EmailAddress is declared as a feed of the hub.. _(requirements: REQ-035, REQ-036, REQ-037, REQ-038, REQ-039, REQ-040, REQ-041, REQ-042, REQ-053-2, REQ-061)_
- **sat_business_entity_credential** — on hub_business_entity; payload: ModifiedDate. Existence and last-change of a person's sign-in credential; hash and salt deliberately excluded. Source table: Password. Split rationale: Separate source (declared as a hub feed); credential values excluded from analytical use.. _(requirements: REQ-050, REQ-051, REQ-052, REQ-053, REQ-055, REQ-056, REQ-072)_
- **sat_business_entity_phone_number_type_numbers** — on link_business_entity_phone_number_type; payload: ModifiedDate. Telephone numbers of a person per phone number type, with history. Multi-active satellite, child dependent key: PhoneNumber. Source table: PersonPhone. _(requirements: REQ-043, REQ-044, REQ-048, REQ-053-2)_
- **sat_business_entity_address_details** — on link_business_entity_address; payload: ModifiedDate. Last-changed timestamp of the party-address relationship; history of relationships retained. Source table: BusinessEntityAddress. _(requirements: REQ-019-2, REQ-020-2, REQ-055-2)_
- **sat_business_entity_contact_details** — on link_business_entity_contact; payload: ModifiedDate. Last-changed timestamp of the contact relationship; history retained. Source table: BusinessEntityContact. _(requirements: REQ-044-2, REQ-045-2, REQ-056-2)_
- **sat_address_details** — on hub_address; payload: AddressLine1, AddressLine2, City, PostalCode, ModifiedDate. Street, city and postal details of an address with full history. Source table: Address. _(requirements: REQ-002-2, REQ-005-2, REQ-006-2, REQ-008-2, REQ-054-2)_
- **sat_address_location** — on hub_address; payload: SpatialLocation. Geographic location (latitude/longitude) of an address. Source table: Address. Split rationale: Spatial data type and personal-data classification (geographic coordinates).. _(requirements: REQ-004-2, REQ-065, REQ-069)_
- **sat_address_type_details** — on hub_address_type; payload: ModifiedDate. Address type reference metadata. Source table: AddressType. _(requirements: REQ-016-2)_
- **sat_contact_type_details** — on hub_contact_type; payload: ModifiedDate. Contact type reference metadata. Source table: ContactType. _(requirements: REQ-038-2)_
- **sat_phone_number_type_details** — on hub_phone_number_type; payload: Name, ModifiedDate. Phone number type name, with history of renames. Source table: PhoneNumberType. _(requirements: REQ-045, REQ-049)_
- **sat_country_region_details** — on hub_country_region; payload: Name, ModifiedDate. Country or region name with visible rename history. Source table: CountryRegion. _(requirements: REQ-022-2, REQ-032-2, REQ-033-2, REQ-034-2)_
- **sat_state_province_details** — on hub_state_province; payload: StateProvinceCode, IsOnlyStateProvinceFlag, ModifiedDate. State or province ISO code and no-genuine-code flag. Source table: StateProvince. _(requirements: REQ-023-2, REQ-026-2, REQ-027-2, REQ-032-2, REQ-066)_
- **sat_state_province_territory** — on hub_state_province; payload: TerritoryID. Sales territory assignment of a state or province, history preserved; territory descriptions come from the sales area. Source table: StateProvince. Split rationale: Different rate of change and business meaning (territory reassignment) from code/flag details.. _(requirements: REQ-028-2, REQ-029-2, REQ-030-2, REQ-031-2, REQ-057)_

### Hub keys decided before modelling (4)

- **AddressType** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `AddressTypeID` (0.55); primary key `AddressTypeID`.
- **ContactType** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `ContactTypeID` (0.55); primary key `ContactTypeID`.
- **CountryRegion** — key `CountryRegionCode`: the primary key is itself a natural key; primary key `CountryRegionCode`.
- **StateProvince** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `StateProvinceCode` (0.50); primary key `StateProvinceID`.

### Source mappings (38)

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
- `ModifiedDate` → `PersonPhone`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `BusinessEntityAddress`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `BusinessEntityContact`.`ModifiedDate` — exact_name, accepted
- `AddressLine1` → `Address`.`AddressLine1` — exact_name, accepted
- `AddressLine2` → `Address`.`AddressLine2` — exact_name, accepted
- `City` → `Address`.`City` — exact_name, accepted
- `PostalCode` → `Address`.`PostalCode` — exact_name, accepted
- `ModifiedDate` → `Address`.`ModifiedDate` — exact_name, accepted
- `SpatialLocation` → `Address`.`SpatialLocation` — exact_name, accepted
- `ModifiedDate` → `AddressType`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `ContactType`.`ModifiedDate` — exact_name, accepted
- `Name` → `PhoneNumberType`.`Name` — exact_name, accepted
- `ModifiedDate` → `PhoneNumberType`.`ModifiedDate` — exact_name, accepted
- `Name` → `CountryRegion`.`Name` — exact_name, accepted
- `ModifiedDate` → `CountryRegion`.`ModifiedDate` — exact_name, accepted
- `StateProvinceCode` → `StateProvince`.`StateProvinceCode` — exact_name, accepted
- `IsOnlyStateProvinceFlag` → `StateProvince`.`IsOnlyStateProvinceFlag` — exact_name, accepted
- `ModifiedDate` → `StateProvince`.`ModifiedDate` — exact_name, accepted
- `TerritoryID` → `StateProvince`.`TerritoryID` — exact_name, accepted

## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/person_requirements.md
- Generated dbt models: 29 raw-vault model(s) + 45 staging model(s) (see `state.artifacts`)
