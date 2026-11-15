-- The one relation the demo's last run (20261115T084203154127Z) could not bind (staging metadata:
-- source_binding inferred). It is declared under the `inferred` source in the run's sources.yml
-- ("provide each as a table or view of that name in the target schema"); this view provides it
-- from the AdventureWorks tables. Target schema `aw` — change it to yours. Written after reading the
-- stage's expected columns (WORKORDERID, OPERATIONSEQUENCE, PRODUCTNUMBER, NAME): the link joins a
-- work order operation to its product and location, whose hubs are keyed on the product number and
-- the location's name; WorkOrderRouting carries their ids (backlog C64).
BEGIN;
CREATE VIEW aw.raw_work_order_operation_location AS
SELECT r.*, p.productnumber, l.name
FROM "Production"."WorkOrderRouting" r
LEFT JOIN "Production"."Product" p ON p.productid = r.productid
LEFT JOIN "Production"."Location" l ON l.locationid = r.locationid;
COMMIT;
