-- The seven relations the demo's link stages could not bind (staging metadata: source_binding
-- inferred, reason `none`). Each is declared under the `inferred` source in the run's sources.yml
-- ("provide each as a table or view of that name in the target schema"); these views provide them
-- from the AdventureWorks tables. Target schema `aw` as in the owner's build — change it to yours.
-- Created by hand during the owner's build on 2026-10-22; the run never generated them (backlog C18).
BEGIN;
-- Production step (20261022T133219892412Z): WorkOrderRouting carries all three keys but declares no
-- foreign key on ProductID, so no rule found it.
CREATE VIEW aw.raw_work_order_product_location AS
  SELECT * FROM "Production"."WorkOrderRouting";
-- Sales step (20261022T151530662480Z).
CREATE VIEW aw.raw_business_entity_credit_card AS
  SELECT businessentityid, creditcardid, load_datetime, record_source
  FROM "Sales"."PersonCreditCard";
CREATE VIEW aw.raw_business_entity_sales_territory AS
  SELECT businessentityid, territoryid, load_datetime, record_source
  FROM "Sales"."SalesPerson";
CREATE VIEW aw.raw_business_entity_sales_territory_assignment AS
  SELECT businessentityid, territoryid, startdate, enddate, load_datetime, record_source
  FROM "Sales"."SalesTerritoryHistory";
CREATE VIEW aw.raw_business_entity_store_sales_person AS
  SELECT businessentityid AS storeid, salespersonid AS sales_person_businessentityid, load_datetime, record_source
  FROM "Sales"."Store";
CREATE VIEW aw.raw_customer_sales_territory AS
  SELECT accountnumber, territoryid, load_datetime, record_source
  FROM "Sales"."Customer";
CREATE VIEW aw.raw_sales_order_currency_rate AS
  SELECT h.salesordernumber, r.currencyratedate, r.fromcurrencycode, r.tocurrencycode, h.load_datetime, h.record_source
  FROM "Sales"."SalesOrderHeader" h LEFT JOIN "Sales"."CurrencyRate" r ON r.currencyrateid = h.currencyrateid;
COMMIT;
