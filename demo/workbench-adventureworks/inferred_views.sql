-- The two relations the demo's last run (20261115T113044562235Z) could not bind (staging metadata:
-- source_binding inferred). They are declared under the `inferred` source in the run's sources.yml
-- ("provide each as a table or view of that name in the target schema"); these views provide them
-- from the AdventureWorks tables. Target schema `aw` — change it to yours. Written by hand after
-- reading each stage's expected columns.
BEGIN;

-- stg_product_subcategory stages link_product_subcategory (PRODUCTNUMBER, NAME): which product is
-- placed in which subcategory. hub_product_subcategory is keyed on the subcategory's name; Product
-- carries its id. An inner join: a product without a subcategory has no row in this link. The
-- name rule had tried the table ProductSubcategory, which carries no product number (backlog C71).
CREATE VIEW aw.raw_product_subcategory AS
SELECT p.productnumber, s.name, p.load_datetime, p.record_source
FROM "Production"."Product" p
JOIN "Production"."ProductSubcategory" s ON s.productsubcategoryid = p.productsubcategoryid;

-- stg_work_order_operation stages hub_work_order_operation and link_work_order_operation
-- (WORKORDERID, OPERATIONSEQUENCE, PRODUCTNUMBER, NAME): an operation of a work order, its product
-- and its location, whose hubs are keyed on the product number and the location's name;
-- WorkOrderRouting carries their ids (backlog C64).
CREATE VIEW aw.raw_work_order_operation AS
SELECT r.*, p.productnumber, l.name
FROM "Production"."WorkOrderRouting" r
LEFT JOIN "Production"."Product" p ON p.productid = r.productid
LEFT JOIN "Production"."Location" l ON l.locationid = r.locationid;

COMMIT;
