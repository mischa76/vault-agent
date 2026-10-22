# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-10-22
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 98 requirement(s) and 11 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (3)

- **hub_purchase_order** — business key `PurchaseOrderID`. Purchase order placed with a vendor, identified by its purchase order number. _(requirements: REQ-030, REQ-031, REQ-044-2, REQ-045-2)_
- **hub_purchase_order_line** — business key `purchase_order_line`. A purchase order line, identified by its purchase order together with its line number. Receipt and inspection outcomes attach to the line. _(requirements: REQ-001-2, REQ-002-2, REQ-034-2, REQ-008-2)_
- **hub_ship_method** — business key `ShipMethodID`. Shipping method (shipping company and rate agreement) used for inbound purchases. Keyed on ShipMethodID, the identifier purchase orders carry, so orders can join to it. The shipping company name is kept in the satellite. _(requirements: REQ-020-2, REQ-021-2, REQ-022-2, REQ-036)_

### Links (4)

- **link_product_vendor** — connects hub_product, hub_business_entity (vendor), hub_unit_measure. Supply relationship between a product and the vendor (business entity) that supplies it, together with the unit of measure the product is bought in. Many-to-many. Unit of work: ProductID + vendor BusinessEntityID (+ UnitMeasureCode) from ProductVendor. _(requirements: REQ-015, REQ-016, REQ-017, REQ-025, REQ-026, REQ-029, REQ-029-2, REQ-042-2)_
- **link_purchase_order_vendor_employee_ship_method** — connects hub_purchase_order, hub_business_entity (vendor), hub_business_entity (employee), hub_ship_method. Purchase order header relationship: each order is placed with one vendor, created by one employee and shipped by one shipping method. Vendor and employee are both business entities, so each takes part under its own role. Unit of work: PurchaseOrderID + VendorID + EmployeeID + ShipMethodID from PurchaseOrderHeader. _(requirements: REQ-032, REQ-033, REQ-034, REQ-035, REQ-036, REQ-049, REQ-031-2, REQ-032-2, REQ-033-2)_
- **link_purchase_order_line_product** — connects hub_purchase_order_line, hub_purchase_order, hub_product. Places each purchase order line in its order and ties it to the one product it refers to. Unit of work: PurchaseOrderID + PurchaseOrderDetailID + ProductID from PurchaseOrderDetail. _(requirements: REQ-001-2, REQ-003-2, REQ-029, REQ-035-2, REQ-036-2, REQ-050)_
- **link_purchase_order_business_entity** — connects hub_purchase_order, hub_business_entity. Declared foreign key PurchaseOrderHeader.EmployeeID references BUSINESSENTITYID; ratified from the source catalogue (WP34). _(requirements: —)_

### Satellites (9)

- **sat_business_entity_vendor_details** — on hub_business_entity; payload: AccountNumber, Name, PurchasingWebServiceURL. Vendor identification and descriptive details: account number, company name and the optional purchasing web service address. Source table: Vendor. Split rationale: Identifying details that rarely change, kept apart from the commercial status codes that change more often.. _(requirements: REQ-002, REQ-004, REQ-011, REQ-012)_
- **sat_business_entity_vendor_status** — on hub_business_entity; payload: CreditRating, PreferredVendorStatus, ActiveFlag, ModifiedDate. Vendor credit rating, preferred status and active flag, with history kept so the vendor's state at order time can be reconstructed. Source table: Vendor. Split rationale: Coded status attributes that change faster and whose history is explicitly required. Holds the single ModifiedDate for the Vendor source.. _(requirements: REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-013, REQ-014, REQ-037-2, REQ-040-2)_
- **sat_product_vendor_terms** — on link_product_vendor; payload: AverageLeadTime, StandardPrice, MinOrderQty, MaxOrderQty, ModifiedDate. Standing commercial terms agreed for a product from a vendor: lead time, standard price and order quantity bounds. History is kept for trend analysis. Source table: ProductVendor. Split rationale: Agreed terms that change slowly. Holds the single ModifiedDate for ProductVendor.. _(requirements: REQ-018, REQ-019, REQ-022, REQ-023, REQ-027, REQ-030-2, REQ-009-2, REQ-019-2, REQ-037-2)_
- **sat_product_vendor_receipt** — on link_product_vendor; payload: LastReceiptCost, LastReceiptDate, OnOrderQty. Running purchasing figures for the supply relationship: last receipt cost and date, and quantity currently on order. Source table: ProductVendor. Split rationale: Running values that change with each order or receipt, much faster than the agreed terms.. _(requirements: REQ-020, REQ-021, REQ-024, REQ-028, REQ-018-2)_
- **sat_purchase_order_status** — on hub_purchase_order; payload: Status, RevisionNumber, ModifiedDate. Purchase order status and revision number, with history kept so status transitions and revisions can be traced. Source table: PurchaseOrderHeader. Split rationale: Workflow attributes that change with each revision or status transition. Holds the single ModifiedDate for PurchaseOrderHeader.. _(requirements: REQ-040, REQ-041, REQ-042, REQ-043, REQ-044, REQ-045, REQ-046, REQ-047, REQ-037-2)_
- **sat_purchase_order_details** — on hub_purchase_order; payload: OrderDate, ShipDate, SubTotal, TaxAmt, Freight, TotalDue. Purchase order dates and financial totals: order date, estimated ship date, subtotal, tax, freight and total due. Source table: PurchaseOrderHeader. Split rationale: Order dates and monetary totals, split from the workflow status attributes.. _(requirements: REQ-037, REQ-038, REQ-039, REQ-048, REQ-049, REQ-050, REQ-051, REQ-052, REQ-039-2)_
- **sat_purchase_order_line_details** — on hub_purchase_order_line; payload: DueDate, OrderQty, UnitPrice, LineTotal. Ordered terms of a purchase order line: due date, ordered quantity, unit price and line total. Source table: PurchaseOrderDetail. Split rationale: Terms fixed when the order is placed, which rarely change afterwards.. _(requirements: REQ-004-2, REQ-005-2, REQ-006-2, REQ-007-2, REQ-008-2, REQ-009-2, REQ-017-2, REQ-050)_
- **sat_purchase_order_line_receipt** — on hub_purchase_order_line; payload: ReceivedQty, RejectedQty, StockedQty, ModifiedDate. Cumulative received, rejected and accepted (stocked) quantities per line. History is kept so the quantity received as at a date, and partial deliveries, are visible. Source table: PurchaseOrderDetail. Split rationale: Receipt progression that changes with each delivery. Holds the single ModifiedDate for PurchaseOrderDetail.. _(requirements: REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2, REQ-015-2, REQ-016-2, REQ-034-2, REQ-037-2)_
- **sat_ship_method_details** — on hub_ship_method; payload: Name, ShipBase, ShipRate, ModifiedDate. Shipping company name and agreed ship base and ship rate, with history kept so historical freight can be checked against the rates then in force. The rowguid replication identifier is left out. Source table: ShipMethod. _(requirements: REQ-021-2, REQ-023-2, REQ-024-2, REQ-025-2, REQ-026-2, REQ-027-2, REQ-028-2)_

### Source mappings (39)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `PurchaseOrderID` → `PurchaseOrderHeader`.`PurchaseOrderID` — exact_name, accepted
- `purchase_order_line` → `PurchaseOrderDetail`.`PurchaseOrderDetailID` — comment_grounded, accepted
- `ShipMethodID` → `ShipMethod`.`ShipMethodID` — exact_name, accepted
- `AccountNumber` → `Vendor`.`AccountNumber` — exact_name, accepted
- `Name` → `Vendor`.`Name` — exact_name, accepted
- `PurchasingWebServiceURL` → `Vendor`.`PurchasingWebServiceURL` — exact_name, accepted
- `CreditRating` → `Vendor`.`CreditRating` — exact_name, accepted
- `PreferredVendorStatus` → `Vendor`.`PreferredVendorStatus` — exact_name, accepted
- `ActiveFlag` → `Vendor`.`ActiveFlag` — exact_name, accepted
- `ModifiedDate` → `Vendor`.`ModifiedDate` — exact_name, accepted
- `AverageLeadTime` → `ProductVendor`.`AverageLeadTime` — exact_name, accepted
- `StandardPrice` → `ProductVendor`.`StandardPrice` — exact_name, accepted
- `MinOrderQty` → `ProductVendor`.`MinOrderQty` — exact_name, accepted
- `MaxOrderQty` → `ProductVendor`.`MaxOrderQty` — exact_name, accepted
- `ModifiedDate` → `ProductVendor`.`ModifiedDate` — exact_name, accepted
- `LastReceiptCost` → `ProductVendor`.`LastReceiptCost` — exact_name, accepted
- `LastReceiptDate` → `ProductVendor`.`LastReceiptDate` — exact_name, accepted
- `OnOrderQty` → `ProductVendor`.`OnOrderQty` — exact_name, accepted
- `Status` → `PurchaseOrderHeader`.`Status` — exact_name, accepted
- `RevisionNumber` → `PurchaseOrderHeader`.`RevisionNumber` — exact_name, accepted
- `ModifiedDate` → `PurchaseOrderHeader`.`ModifiedDate` — exact_name, accepted
- `OrderDate` → `PurchaseOrderHeader`.`OrderDate` — exact_name, accepted
- `ShipDate` → `PurchaseOrderHeader`.`ShipDate` — exact_name, accepted
- `SubTotal` → `PurchaseOrderHeader`.`SubTotal` — exact_name, accepted
- `TaxAmt` → `PurchaseOrderHeader`.`TaxAmt` — exact_name, accepted
- `Freight` → `PurchaseOrderHeader`.`Freight` — exact_name, accepted
- `TotalDue` → `PurchaseOrderHeader`.`TotalDue` — exact_name, accepted
- `DueDate` → `PurchaseOrderDetail`.`DueDate` — exact_name, accepted
- `OrderQty` → `PurchaseOrderDetail`.`OrderQty` — exact_name, accepted
- `UnitPrice` → `PurchaseOrderDetail`.`UnitPrice` — exact_name, accepted
- `LineTotal` → `PurchaseOrderDetail`.`LineTotal` — exact_name, accepted
- `ReceivedQty` → `PurchaseOrderDetail`.`ReceivedQty` — exact_name, accepted
- `RejectedQty` → `PurchaseOrderDetail`.`RejectedQty` — exact_name, accepted
- `StockedQty` → `PurchaseOrderDetail`.`StockedQty` — exact_name, accepted
- `ModifiedDate` → `PurchaseOrderDetail`.`ModifiedDate` — exact_name, accepted
- `Name` → `ShipMethod`.`Name` — exact_name, accepted
- `ShipBase` → `ShipMethod`.`ShipBase` — exact_name, accepted
- `ShipRate` → `ShipMethod`.`ShipRate` — exact_name, accepted
- `ModifiedDate` → `ShipMethod`.`ModifiedDate` — exact_name, accepted

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261022T133219892412Z`) carrying 25 hub(s), 23 link(s) and 56 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

103 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/purchasing_requirements.md
- Generated dbt models: 120 raw-vault model(s) + 88 staging model(s) (see `state.artifacts`)
