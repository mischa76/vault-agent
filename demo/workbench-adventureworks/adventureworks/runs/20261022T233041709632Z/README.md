# Generated Data Vault project (vault-agent)

A runnable dbt project: `models/staging/` computes the hash keys / hashdiffs via
AutomateDV's `stage` macro, `models/raw_vault/` holds the generated hubs, links, and
satellites. Review `review-queue.md` and `contracts/` before agreeing the model.

## Provide the raw inputs

Each staging model reads one raw relation by name — provide it either as a dbt seed
(`seeds/<name>.csv`, headers exactly as listed) or as a table/view in the target schema:

- `BusinessEntity` → feeds `stg_business_entity_businessentity` (expected columns: BUSINESSENTITYID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Person` → feeds `stg_business_entity_person` (expected columns: BUSINESSENTITYID, NAMESTYLE, TITLE, FIRSTNAME, MIDDLENAME, LASTNAME, SUFFIX, MODIFIEDDATE, PERSONTYPE, EMAILPROMOTION, ADDITIONALCONTACTINFO, DEMOGRAPHICS, LOAD_DATETIME, RECORD_SOURCE)
- `EmailAddress` → feeds `stg_business_entity_emailaddress` (expected columns: BUSINESSENTITYID, EMAILADDRESS, MODIFIEDDATE, EMAILADDRESSID, LOAD_DATETIME, RECORD_SOURCE)
- `PersonPhone` → feeds `stg_business_entity_personphone` (expected columns: BUSINESSENTITYID, MODIFIEDDATE, PHONENUMBERTYPEID, PHONENUMBER, LOAD_DATETIME, RECORD_SOURCE)
- `Password` → feeds `stg_business_entity_password` (expected columns: BUSINESSENTITYID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Employee` → feeds `stg_business_entity_employee` (expected columns: BUSINESSENTITYID, LOGINID, JOBTITLE, HIREDATE, SALARIEDFLAG, CURRENTFLAG, MODIFIEDDATE, NATIONALIDNUMBER, BIRTHDATE, GENDER, MARITALSTATUS, VACATIONHOURS, SICKLEAVEHOURS, ORGANIZATIONNODE, ORGANIZATIONLEVEL, LOAD_DATETIME, RECORD_SOURCE)
- `EmployeePayHistory` → feeds `stg_business_entity_employeepayhistory` (expected columns: BUSINESSENTITYID, RATE, PAYFREQUENCY, MODIFIEDDATE, RATECHANGEDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address` (expected columns: ADDRESSID, LOAD_DATETIME, RECORD_SOURCE)
- `AddressType` → feeds `stg_address_type` (expected columns: ADDRESSTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `ContactType` → feeds `stg_contact_type` (expected columns: CONTACTTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `PhoneNumberType` → feeds `stg_phone_number_type` (expected columns: PHONENUMBERTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `CountryRegion` → feeds `stg_country_region` (expected columns: COUNTRYREGIONCODE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province` (expected columns: STATEPROVINCEID, LOAD_DATETIME, RECORD_SOURCE)
- `Department` → feeds `stg_department` (expected columns: DEPARTMENTID, LOAD_DATETIME, RECORD_SOURCE)
- `Shift` → feeds `stg_shift` (expected columns: SHIFTID, LOAD_DATETIME, RECORD_SOURCE)
- `JobCandidate` → feeds `stg_job_candidate` (expected columns: JOBCANDIDATEID, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_state_province` (expected columns: ADDRESSID, STATEPROVINCEID, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_country_region` (expected columns: STATEPROVINCEID, COUNTRYREGIONCODE, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityAddress` → feeds `stg_business_entity_address` (expected columns: BUSINESSENTITYID, ADDRESSID, ADDRESSTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `raw_business_entity_contact` → feeds `stg_business_entity_contact` (expected columns: ORGANISATION_BUSINESSENTITYID, CONTACT_PERSON_BUSINESSENTITYID, CONTACTTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `EmployeeDepartmentHistory` → feeds `stg_business_entity_department_shift` (expected columns: BUSINESSENTITYID, DEPARTMENTID, SHIFTID, STARTDATE, ENDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `JobCandidate` → feeds `stg_job_candidate_business_entity` (expected columns: JOBCANDIDATEID, BUSINESSENTITYID, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_details` (expected columns: ADDRESSID, ADDRESSLINE1, ADDRESSLINE2, CITY, POSTALCODE, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_location` (expected columns: ADDRESSID, SPATIALLOCATION, LOAD_DATETIME, RECORD_SOURCE)
- `AddressType` → feeds `stg_address_type_details` (expected columns: ADDRESSTYPEID, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ContactType` → feeds `stg_contact_type_details` (expected columns: CONTACTTYPEID, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `PhoneNumberType` → feeds `stg_phone_number_type_details` (expected columns: PHONENUMBERTYPEID, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `CountryRegion` → feeds `stg_country_region_details` (expected columns: COUNTRYREGIONCODE, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_details` (expected columns: STATEPROVINCEID, STATEPROVINCECODE, ISONLYSTATEPROVINCEFLAG, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_territory` (expected columns: STATEPROVINCEID, TERRITORYID, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityAddress` → feeds `stg_business_entity_address_details` (expected columns: BUSINESSENTITYID, ADDRESSID, ADDRESSTYPEID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Department` → feeds `stg_department_details` (expected columns: DEPARTMENTID, NAME, GROUPNAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Shift` → feeds `stg_shift_details` (expected columns: SHIFTID, NAME, STARTTIME, ENDTIME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `JobCandidate` → feeds `stg_job_candidate_resume` (expected columns: JOBCANDIDATEID, RESUME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `EmployeeDepartmentHistory` → feeds `stg_business_entity_department_shift_details` (expected columns: BUSINESSENTITYID, DEPARTMENTID, SHIFTID, MODIFIEDDATE, STARTDATE, LOAD_DATETIME, RECORD_SOURCE)

Every raw relation must also carry `LOAD_DATETIME` and `RECORD_SOURCE`.

## Run it

1. Define a `vault_project` profile in `profiles.yml` (any AutomateDV-supported warehouse).
2. `dbt deps`
3. `dbt seed` (if using seeds), then `dbt build`.
