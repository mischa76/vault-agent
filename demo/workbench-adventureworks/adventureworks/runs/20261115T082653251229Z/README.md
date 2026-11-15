# Generated Data Vault project (vault-agent)

A runnable dbt project: `models/staging/` computes the hash keys / hashdiffs via
AutomateDV's `stage` macro, `models/raw_vault/` holds the generated hubs, links, and
satellites. Review `review-queue.md` and `contracts/` before agreeing the model.

## Provide the raw inputs

Each staging model reads one raw relation by name — provide it either as a dbt seed
(`seeds/<name>.csv`, headers exactly as listed) or as a table/view in the target schema:

- `BusinessEntity` → feeds `stg_business_entity_businessentity` (expected columns: BUSINESSENTITYID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Person` → feeds `stg_business_entity_person` (expected columns: BUSINESSENTITYID, PERSONTYPE, NAMESTYLE, TITLE, FIRSTNAME, MIDDLENAME, LASTNAME, SUFFIX, MODIFIEDDATE, EMAILPROMOTION, ADDITIONALCONTACTINFO, DEMOGRAPHICS, LOAD_DATETIME, RECORD_SOURCE)
- `EmailAddress` → feeds `stg_business_entity_emailaddress` (expected columns: BUSINESSENTITYID, EMAILADDRESS, MODIFIEDDATE, EMAILADDRESSID, LOAD_DATETIME, RECORD_SOURCE)
- `PersonPhone` → feeds `stg_business_entity_personphone` (expected columns: BUSINESSENTITYID, MODIFIEDDATE, PHONENUMBERTYPEID, PHONENUMBER, LOAD_DATETIME, RECORD_SOURCE)
- `Password` → feeds `stg_business_entity_password` (expected columns: BUSINESSENTITYID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Employee` → feeds `stg_business_entity_employee` (expected columns: BUSINESSENTITYID, JOBTITLE, HIREDATE, SALARIEDFLAG, CURRENTFLAG, LOGINID, MODIFIEDDATE, NATIONALIDNUMBER, BIRTHDATE, GENDER, MARITALSTATUS, VACATIONHOURS, SICKLEAVEHOURS, ORGANIZATIONNODE, ORGANIZATIONLEVEL, LOAD_DATETIME, RECORD_SOURCE)
- `EmployeePayHistory` → feeds `stg_business_entity_employeepayhistory` (expected columns: BUSINESSENTITYID, RATE, PAYFREQUENCY, MODIFIEDDATE, RATECHANGEDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address` (expected columns: ADDRESSID, LOAD_DATETIME, RECORD_SOURCE)
- `AddressType` → feeds `stg_address_type` (expected columns: NAME, LOAD_DATETIME, RECORD_SOURCE)
- `ContactType` → feeds `stg_contact_type` (expected columns: NAME, LOAD_DATETIME, RECORD_SOURCE)
- `PhoneNumberType` → feeds `stg_phone_number_type` (expected columns: PHONENUMBERTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `CountryRegion` → feeds `stg_country_region` (expected columns: COUNTRYREGIONCODE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province` (expected columns: NAME, LOAD_DATETIME, RECORD_SOURCE)
- `Department` → feeds `stg_department` (expected columns: NAME, LOAD_DATETIME, RECORD_SOURCE)
- `Shift` → feeds `stg_shift` (expected columns: NAME, LOAD_DATETIME, RECORD_SOURCE)
- `JobCandidate` → feeds `stg_job_candidate` (expected columns: JOBCANDIDATEID, LOAD_DATETIME, RECORD_SOURCE)
- `Product` → feeds `stg_product` (expected columns: PRODUCTNUMBER, NAME, MAKEFLAG, FINISHEDGOODSFLAG, COLOR, SIZE, WEIGHT, DAYSTOMANUFACTURE, PRODUCTLINE, CLASS, STYLE, SAFETYSTOCKLEVEL, REORDERPOINT, MODIFIEDDATE, STANDARDCOST, LISTPRICE, SELLSTARTDATE, SELLENDDATE, DISCONTINUEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductCategory` → feeds `stg_product_category` (expected columns: NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductSubcategory` → feeds `stg_product_subcategory` (expected columns: NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductModel` → feeds `stg_product_model` (expected columns: NAME, MODIFIEDDATE, CATALOGDESCRIPTION, INSTRUCTIONS, LOAD_DATETIME, RECORD_SOURCE)
- `Culture` → feeds `stg_culture` (expected columns: CULTUREID, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductDescription` → feeds `stg_product_description` (expected columns: PRODUCTDESCRIPTIONID, DESCRIPTION, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductPhoto` → feeds `stg_product_photo` (expected columns: PRODUCTPHOTOID, THUMBNAILPHOTOFILENAME, LARGEPHOTOFILENAME, MODIFIEDDATE, THUMBNAILPHOTO, LARGEPHOTO, LOAD_DATETIME, RECORD_SOURCE)
- `Illustration` → feeds `stg_illustration` (expected columns: ILLUSTRATIONID, DIAGRAM, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Document` → feeds `stg_document` (expected columns: DOCUMENTNODE, DOCUMENTLEVEL, TITLE, FOLDERFLAG, FILENAME, FILEEXTENSION, REVISION, CHANGENUMBER, STATUS, DOCUMENTSUMMARY, MODIFIEDDATE, DOCUMENT, LOAD_DATETIME, RECORD_SOURCE)
- `UnitMeasure` → feeds `stg_unit_measure` (expected columns: UNITMEASURECODE, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Location` → feeds `stg_location` (expected columns: NAME, COSTRATE, AVAILABILITY, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `WorkOrder` → feeds `stg_work_order` (expected columns: WORKORDERID, ORDERQTY, STOCKEDQTY, SCRAPPEDQTY, STARTDATE, ENDDATE, DUEDATE, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `WorkOrderRouting` → feeds `stg_work_order_operation` (expected columns: WORKORDERID, OPERATIONSEQUENCE, SCHEDULEDSTARTDATE, SCHEDULEDENDDATE, ACTUALSTARTDATE, ACTUALENDDATE, ACTUALRESOURCEHRS, PLANNEDCOST, ACTUALCOST, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ScrapReason` → feeds `stg_scrap_reason` (expected columns: NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `TransactionHistory` → feeds `stg_inventory_transaction_transactionhistory` (expected columns: TRANSACTIONID, REFERENCEORDERID, REFERENCEORDERLINEID, TRANSACTIONDATE, TRANSACTIONTYPE, QUANTITY, ACTUALCOST, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `TransactionHistoryArchive` → feeds `stg_inventory_transaction_transactionhistoryarchive` (expected columns: TRANSACTIONID, REFERENCEORDERID, REFERENCEORDERLINEID, TRANSACTIONDATE, TRANSACTIONTYPE, QUANTITY, ACTUALCOST, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductReview` → feeds `stg_product_review` (expected columns: PRODUCTREVIEWID, REVIEWDATE, RATING, COMMENTS, MODIFIEDDATE, REVIEWERNAME, EMAILADDRESS, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_state_province` (expected columns: ADDRESSID, STATEPROVINCEID, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_country_region` (expected columns: NAME, COUNTRYREGIONCODE, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityAddress` → feeds `stg_business_entity_address` (expected columns: BUSINESSENTITYID, ADDRESSID, ADDRESSTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityContact` → feeds `stg_business_entity_contact` (expected columns: BUSINESSENTITYID, PERSONID, CONTACTTYPEID, LOAD_DATETIME, RECORD_SOURCE)
- `EmployeeDepartmentHistory` → feeds `stg_business_entity_department_shift` (expected columns: BUSINESSENTITYID, DEPARTMENTID, SHIFTID, STARTDATE, ENDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `JobCandidate` → feeds `stg_job_candidate_business_entity` (expected columns: JOBCANDIDATEID, BUSINESSENTITYID, LOAD_DATETIME, RECORD_SOURCE)
- `Product` → feeds `stg_product_product_subcategory` (expected columns: PRODUCTNUMBER, PRODUCTSUBCATEGORYID, LOAD_DATETIME, RECORD_SOURCE)
- `ProductSubcategory` → feeds `stg_product_subcategory_product_category` (expected columns: NAME, PRODUCTCATEGORYID, LOAD_DATETIME, RECORD_SOURCE)
- `Product` → feeds `stg_product_product_model` (expected columns: PRODUCTNUMBER, PRODUCTMODELID, LOAD_DATETIME, RECORD_SOURCE)
- `Product` → feeds `stg_product_size_unit_measure` (expected columns: PRODUCTNUMBER, SIZEUNITMEASURECODE, LOAD_DATETIME, RECORD_SOURCE)
- `Product` → feeds `stg_product_weight_unit_measure` (expected columns: PRODUCTNUMBER, WEIGHTUNITMEASURECODE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductModelProductDescriptionCulture` → feeds `stg_product_model_description_culture` (expected columns: PRODUCTMODELID, PRODUCTDESCRIPTIONID, CULTUREID, LOAD_DATETIME, RECORD_SOURCE)
- `ProductProductPhoto` → feeds `stg_product_product_photo` (expected columns: PRODUCTID, PRODUCTPHOTOID, PRIMARY, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductModelIllustration` → feeds `stg_product_model_illustration` (expected columns: PRODUCTMODELID, ILLUSTRATIONID, LOAD_DATETIME, RECORD_SOURCE)
- `ProductDocument` → feeds `stg_product_document` (expected columns: PRODUCTID, DOCUMENTNODE, LOAD_DATETIME, RECORD_SOURCE)
- `Document` → feeds `stg_document_business_entity` (expected columns: DOCUMENTNODE, OWNER, LOAD_DATETIME, RECORD_SOURCE)
- `BillOfMaterials` → feeds `stg_product_assembly_component` (expected columns: PRODUCTNUMBER, COMPONENTID, UNITMEASURECODE, STARTDATE, ENDDATE, BOMLEVEL, PERASSEMBLYQTY, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `WorkOrder` → feeds `stg_work_order_product` (expected columns: WORKORDERID, PRODUCTID, LOAD_DATETIME, RECORD_SOURCE)
- `WorkOrder` → feeds `stg_work_order_scrap_reason` (expected columns: WORKORDERID, SCRAPREASONID, LOAD_DATETIME, RECORD_SOURCE)
- `raw_work_order_operation_location` → feeds `stg_work_order_operation_location` (expected columns: WORKORDERID, OPERATIONSEQUENCE, PRODUCTNUMBER, NAME, LOAD_DATETIME, RECORD_SOURCE)
- `ProductInventory` → feeds `stg_product_location` (expected columns: PRODUCTID, LOCATIONID, SHELF, BIN, QUANTITY, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `TransactionHistory` → feeds `stg_inventory_transaction_product` (expected columns: TRANSACTIONID, PRODUCTID, LOAD_DATETIME, RECORD_SOURCE)
- `ProductReview` → feeds `stg_product_review_product` (expected columns: PRODUCTREVIEWID, PRODUCTID, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_details` (expected columns: ADDRESSID, ADDRESSLINE1, ADDRESSLINE2, CITY, POSTALCODE, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Address` → feeds `stg_address_location` (expected columns: ADDRESSID, SPATIALLOCATION, LOAD_DATETIME, RECORD_SOURCE)
- `AddressType` → feeds `stg_address_type_details` (expected columns: NAME, ADDRESSTYPEID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ContactType` → feeds `stg_contact_type_details` (expected columns: NAME, CONTACTTYPEID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `PhoneNumberType` → feeds `stg_phone_number_type_details` (expected columns: PHONENUMBERTYPEID, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `CountryRegion` → feeds `stg_country_region_details` (expected columns: COUNTRYREGIONCODE, NAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_details` (expected columns: NAME, STATEPROVINCEID, STATEPROVINCECODE, ISONLYSTATEPROVINCEFLAG, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `StateProvince` → feeds `stg_state_province_territory` (expected columns: NAME, TERRITORYID, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityAddress` → feeds `stg_business_entity_address_details` (expected columns: BUSINESSENTITYID, ADDRESSID, ADDRESSTYPEID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `BusinessEntityContact` → feeds `stg_business_entity_contact_details` (expected columns: BUSINESSENTITYID, PERSONID, CONTACTTYPEID, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Department` → feeds `stg_department_details` (expected columns: NAME, GROUPNAME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `Shift` → feeds `stg_shift_details` (expected columns: NAME, STARTTIME, ENDTIME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `JobCandidate` → feeds `stg_job_candidate_details` (expected columns: JOBCANDIDATEID, RESUME, MODIFIEDDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductCostHistory` → feeds `stg_product_cost_history` (expected columns: PRODUCTID, ENDDATE, STANDARDCOST, MODIFIEDDATE, STARTDATE, LOAD_DATETIME, RECORD_SOURCE)
- `ProductListPriceHistory` → feeds `stg_product_list_price_history` (expected columns: PRODUCTID, ENDDATE, LISTPRICE, MODIFIEDDATE, STARTDATE, LOAD_DATETIME, RECORD_SOURCE)

Every raw relation must also carry `LOAD_DATETIME` and `RECORD_SOURCE`.

## Run it

1. Define a `vault_project` profile in `profiles.yml` (any AutomateDV-supported warehouse).
2. `dbt deps`
3. `dbt seed` (if using seeds), then `dbt build`.
