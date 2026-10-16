# Generated Data Vault project (vault-agent)

A runnable dbt project: `models/staging/` computes the hash keys / hashdiffs via
AutomateDV's `stage` macro, `models/raw_vault/` holds the generated hubs, links, and
satellites. Review `review-queue.md` and `contracts/` before agreeing the model.

## Provide the raw inputs

Each staging model reads one raw relation by name — provide it either as a dbt seed
(`seeds/<name>.csv`, headers exactly as listed) or as a table/view in the target schema:

- `BusinessEntity` → feeds `stg_business_entity` (expected columns: BUSINESSENTITYID, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address` (expected columns: ADDRESSID, LOAD_DATETIME, RECORD_SOURCE)
- `AddressType` → feeds `stg_address_type` (expected columns: ADDRESSTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `ContactType` → feeds `stg_contact_type` (expected columns: CONTACTTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `PhoneNumberType` → feeds `stg_phone_number_type` (expected columns: PHONENUMBERTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `CountryRegion` → feeds `stg_country_region` (expected columns: COUNTRYREGIONCODE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province` (expected columns: STATEPROVINCEID, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityAddress` → feeds `stg_business_entity_address` (expected columns: BUSINESSENTITYID, ADDRESSID, ADDRESSTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityContact` → feeds `stg_business_entity_contact` (expected columns: BUSINESSENTITYID, PERSONID, CONTACTTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_state_province` (expected columns: ADDRESSID, STATEPROVINCEID, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_country_region` (expected columns: STATEPROVINCEID, COUNTRYREGIONCODE, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntity` → feeds `stg_business_entity_details` (expected columns: BUSINESSENTITYID, ROWGUID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Person` → feeds `stg_business_entity_person_name` (expected columns: BUSINESSENTITYID, PERSONTYPE, NAMESTYLE, TITLE, FIRSTNAME, MIDDLENAME, LASTNAME, SUFFIX, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Person` → feeds `stg_business_entity_person_consent` (expected columns: BUSINESSENTITYID, EMAILPROMOTION, LOAD_DATETIME, RECORD_SOURCE)
- `Person` → feeds `stg_business_entity_person_sensitive` (expected columns: BUSINESSENTITYID, ADDITIONALCONTACTINFO, DEMOGRAPHICS, LOAD_DATETIME, RECORD_SOURCE)
- `EmailAddress` → feeds `stg_business_entity_email` (expected columns: BUSINESSENTITYID, EMAILADDRESS, MODIFIEDDATE, EMAILADDRESSID, LOAD_DATETIME, RECORD_SOURCE)
- `PersonPhone` → feeds `stg_business_entity_phone` (expected columns: BUSINESSENTITYID, MODIFIEDDATE, PHONENUMBERTYPEID, PHONENUMBER, LOAD_DATETIME, RECORD_SOURCE)
- `Password` → feeds `stg_business_entity_credential` (expected columns: BUSINESSENTITYID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_details` (expected columns: ADDRESSID, ADDRESSLINE1, ADDRESSLINE2, CITY, POSTALCODE, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_location` (expected columns: ADDRESSID, SPATIALLOCATION, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityAddress` → feeds `stg_business_entity_address_details` (expected columns: BUSINESSENTITYID, ADDRESSID, ADDRESSTYPEID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityContact` → feeds `stg_business_entity_contact_details` (expected columns: BUSINESSENTITYID, PERSONID, CONTACTTYPEID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `AddressType` → feeds `stg_address_type_details` (expected columns: ADDRESSTYPEID, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ContactType` → feeds `stg_contact_type_details` (expected columns: CONTACTTYPEID, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `PhoneNumberType` → feeds `stg_phone_number_type_details` (expected columns: PHONENUMBERTYPEID, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `CountryRegion` → feeds `stg_country_region_details` (expected columns: COUNTRYREGIONCODE, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_details` (expected columns: STATEPROVINCEID, STATEPROVINCECODE, ISONLYSTATEPROVINCEFLAG, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_territory` (expected columns: STATEPROVINCEID, TERRITORYID, LOAD_DATETIME, RECORD_SOURCE)

Every raw relation must also carry `LOAD_DATETIME` and `RECORD_SOURCE`.

## Run it

1. Define a `vault_project` profile in `profiles.yml` (any AutomateDV-supported warehouse).
2. `dbt deps`
3. `dbt seed` (if using seeds), then `dbt build`.
