-- The ten relations the demo's last run (20261022T234439976097Z) could not bind (staging metadata:
-- source_binding inferred). Each is declared under the `inferred` source in the run's sources.yml
-- ("provide each as a table or view of that name in the target schema"); these views provide them
-- from the AdventureWorks tables. Target schema `aw` — change it to yours. Written after reading each
-- stage's expected columns (backlog C18: the generator cannot bind them yet).
BEGIN;
CREATE VIEW aw.raw_business_entity_contact AS SELECT t.*, t.businessentityid AS organisation_businessentityid, t.personid AS contact_person_businessentityid FROM "Person"."BusinessEntityContact" t;
CREATE VIEW aw.raw_business_entity_credit_card AS SELECT * FROM "Sales"."PersonCreditCard";
CREATE VIEW aw.raw_customer_sales_territory AS SELECT * FROM "Sales"."Customer";
CREATE VIEW aw.raw_product_model AS SELECT * FROM "Production"."Product";
CREATE VIEW aw.raw_product_subcategory AS SELECT * FROM "Production"."Product";
CREATE VIEW aw.raw_sales_order AS SELECT h.*, r.currencyratedate, r.fromcurrencycode, r.tocurrencycode FROM "Sales"."SalesOrderHeader" h LEFT JOIN "Sales"."CurrencyRate" r ON r.currencyrateid = h.currencyrateid;
CREATE VIEW aw.raw_sales_person_sales_territory AS SELECT t.*, t.businessentityid AS sales_person_businessentityid FROM "Sales"."SalesPerson" t;
CREATE VIEW aw.raw_sales_person_territory_history AS SELECT t.*, t.businessentityid AS sales_person_businessentityid FROM "Sales"."SalesTerritoryHistory" t;
CREATE VIEW aw.raw_store_sales_person AS SELECT t.*, t.businessentityid AS storeid, t.salespersonid AS sales_person_businessentityid FROM "Sales"."Store" t;
CREATE VIEW aw.raw_work_order_operation AS SELECT * FROM "Production"."WorkOrderRouting";
COMMIT;
