# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 102 requirement(s) and 9 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (3)

- **hub_purchase_order** — business key `PurchaseOrderID`. A purchase order placed with a vendor, identified by its purchase order number. _(requirements: REQ-033, REQ-034, REQ-042-2)_
- **hub_purchase_order_line** — business key `purchase_order_line`. A purchase order line, identified by its purchase order together with its line number. _(requirements: REQ-001-2, REQ-002-2, REQ-008-2, REQ-033-2)_
- **hub_ship_method** — business key `Name`. A shipping method (shipping company and rate agreement) for inbound purchases, identified by the shipping company name. _(requirements: REQ-020-2, REQ-021-2, REQ-022-2, REQ-039)_

### Links (6)

- **link_product_vendor** — connects hub_product, hub_business_entity (vendor), hub_unit_measure. Product-vendor supply relationship from ProductVendor: a product bought from a vendor in a given unit of measure. Unit of work: ProductID + BusinessEntityID (vendor) with UnitMeasureCode of the supply terms. _(requirements: REQ-016, REQ-017, REQ-018, REQ-027, REQ-028, REQ-028-2, REQ-029-2, REQ-031, REQ-032, REQ-040-2)_
- **link_purchase_order_vendor** — connects hub_purchase_order, hub_business_entity (vendor). The vendor a purchase order is placed with (PurchaseOrderHeader.VendorID). Unit of work: PurchaseOrderID + VendorID. _(requirements: REQ-035, REQ-030-2, REQ-008, REQ-014, REQ-055)_
- **link_purchase_order_employee** — connects hub_purchase_order, hub_business_entity (employee). The employee (buyer) who created the purchase order (PurchaseOrderHeader.EmployeeID). Unit of work: PurchaseOrderID + EmployeeID. _(requirements: REQ-036, REQ-031-2, REQ-037, REQ-038, REQ-055)_
- **link_purchase_order_ship_method** — connects hub_purchase_order, hub_ship_method. The shipping method specified on a purchase order (PurchaseOrderHeader.ShipMethodID). Unit of work: PurchaseOrderID + ShipMethodID. _(requirements: REQ-039, REQ-032-2, REQ-024-2, REQ-025-2, REQ-055)_
- **link_purchase_order_line** — connects hub_purchase_order_line, hub_purchase_order, hub_product. A purchase order line belonging to its purchase order and referring to exactly one product (PurchaseOrderDetail). Unit of work: PurchaseOrderID + PurchaseOrderDetailID + ProductID. _(requirements: REQ-001-2, REQ-002-2, REQ-003-2, REQ-013-2, REQ-014-2, REQ-034-2, REQ-031, REQ-032)_
- **link_purchase_order_line_product** — connects hub_purchase_order_line, hub_product. Declared foreign key PurchaseOrderDetail.ProductID references PRODUCTNUMBER; ratified from the source catalogue (WP34). _(requirements: —)_

### Satellites (9)

- **sat_business_entity_vendor_details** — on hub_business_entity; payload: AccountNumber, Name, PurchasingWebServiceURL. Vendor identifying and descriptive attributes: vendor account number, company name and optional purchasing web service address. Source table: Vendor. Split rationale: Slowly changing identity/description of the vendor, separated from the status codes that change more often.. _(requirements: REQ-002, REQ-003, REQ-004, REQ-011, REQ-012)_
- **sat_business_entity_vendor_status** — on hub_business_entity; payload: CreditRating, PreferredVendorStatus, ActiveFlag, ModifiedDate. Vendor status codes with history: credit rating, preferred vendor status and active flag. Source table: Vendor. Split rationale: Status codes change at a different rate and need tracked history; carries the vendor ModifiedDate once.. _(requirements: REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-013, REQ-014, REQ-035-2, REQ-038-2)_
- **sat_product_vendor_terms** — on link_product_vendor; payload: AverageLeadTime, StandardPrice, MinOrderQty, MaxOrderQty, ModifiedDate. Agreed standing supply terms per product and vendor: lead time, standard price and order quantity bounds. Source table: ProductVendor. Split rationale: Agreed contractual terms change rarely; split from operational running values.. _(requirements: REQ-019, REQ-020, REQ-023, REQ-024, REQ-025, REQ-029, REQ-029-2, REQ-009-2, REQ-019-2, REQ-035-2)_
- **sat_product_vendor_receipts** — on link_product_vendor; payload: LastReceiptCost, LastReceiptDate, OnOrderQty. Running operational values on the supply relationship: last receipt cost and date, and quantity currently on order. Source table: ProductVendor. Split rationale: Running values change with every receipt/order, far faster than the agreed terms.. _(requirements: REQ-021, REQ-022, REQ-023, REQ-026, REQ-030, REQ-018-2)_
- **sat_purchase_order_details** — on hub_purchase_order; payload: RevisionNumber, Status, OrderDate, ShipDate, ModifiedDate. Purchase order header state with history: revision number, status, order date and estimated shipment date. Source table: PurchaseOrderHeader. Split rationale: Lifecycle/status attributes tracked for status transitions and revisions.. _(requirements: REQ-040, REQ-041, REQ-042, REQ-043, REQ-044, REQ-045, REQ-046, REQ-047, REQ-048, REQ-049, REQ-050, REQ-035-2)_
- **sat_purchase_order_amounts** — on hub_purchase_order; payload: SubTotal, TaxAmt, Freight, TotalDue. Purchase order monetary amounts: subtotal, tax, freight and total due. Source table: PurchaseOrderHeader. Split rationale: Monetary amounts (different data type/concern) separated from lifecycle status.. _(requirements: REQ-051, REQ-052, REQ-053, REQ-054, REQ-055, REQ-056, REQ-057, REQ-058, REQ-025-2, REQ-037-2)_
- **sat_purchase_order_line_details** — on hub_purchase_order_line; payload: DueDate, OrderQty, UnitPrice, LineTotal, ModifiedDate. Ordered terms of a purchase order line: due date, ordered quantity, unit price and line total. Source table: PurchaseOrderDetail. Split rationale: Order terms set at ordering, rarely changing; split from receipt progression.. _(requirements: REQ-004-2, REQ-005-2, REQ-006-2, REQ-007-2, REQ-008-2, REQ-009-2, REQ-017-2, REQ-035-2)_
- **sat_purchase_order_line_receipt** — on hub_purchase_order_line; payload: ReceivedQty, RejectedQty, StockedQty. Cumulative receipt and inspection outcomes per line: received, rejected and accepted (stocked) quantities, with history of progression. Source table: PurchaseOrderDetail. Split rationale: Receipt quantities change repeatedly over the order life; separate rate of change from ordered terms.. _(requirements: REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2, REQ-015-2, REQ-016-2, REQ-033-2)_
- **sat_ship_method_details** — on hub_ship_method; payload: ShipBase, ShipRate, ModifiedDate. Shipping method rate terms with history: minimum charge (ship base) and charge per pound (ship rate). rowguid excluded as it has no business meaning. Source table: ShipMethod. _(requirements: REQ-023-2, REQ-024-2, REQ-025-2, REQ-026-2, REQ-027-2)_

### Hub keys decided before modelling (1)

- **ShipMethod** — key `Name`: the declared natural key, taken as the default of a contested case; primary key `ShipMethodID`.

### Source mappings (38)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `PurchaseOrderID` → `PurchaseOrderHeader`.`PurchaseOrderID` — exact_name, accepted
- `purchase_order_line` → `PurchaseOrderDetail`.`PurchaseOrderDetailID` — comment_grounded, accepted
- `Name` → `ShipMethod`.`Name` — exact_name, accepted
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
- `RevisionNumber` → `PurchaseOrderHeader`.`RevisionNumber` — exact_name, accepted
- `Status` → `PurchaseOrderHeader`.`Status` — exact_name, accepted
- `OrderDate` → `PurchaseOrderHeader`.`OrderDate` — exact_name, accepted
- `ShipDate` → `PurchaseOrderHeader`.`ShipDate` — exact_name, accepted
- `ModifiedDate` → `PurchaseOrderHeader`.`ModifiedDate` — exact_name, accepted
- `SubTotal` → `PurchaseOrderHeader`.`SubTotal` — exact_name, accepted
- `TaxAmt` → `PurchaseOrderHeader`.`TaxAmt` — exact_name, accepted
- `Freight` → `PurchaseOrderHeader`.`Freight` — exact_name, accepted
- `TotalDue` → `PurchaseOrderHeader`.`TotalDue` — exact_name, accepted
- `DueDate` → `PurchaseOrderDetail`.`DueDate` — exact_name, accepted
- `OrderQty` → `PurchaseOrderDetail`.`OrderQty` — exact_name, accepted
- `UnitPrice` → `PurchaseOrderDetail`.`UnitPrice` — exact_name, accepted
- `LineTotal` → `PurchaseOrderDetail`.`LineTotal` — exact_name, accepted
- `ModifiedDate` → `PurchaseOrderDetail`.`ModifiedDate` — exact_name, accepted
- `ReceivedQty` → `PurchaseOrderDetail`.`ReceivedQty` — exact_name, accepted
- `RejectedQty` → `PurchaseOrderDetail`.`RejectedQty` — exact_name, accepted
- `StockedQty` → `PurchaseOrderDetail`.`StockedQty` — exact_name, accepted
- `ShipBase` → `ShipMethod`.`ShipBase` — exact_name, accepted
- `ShipRate` → `ShipMethod`.`ShipRate` — exact_name, accepted
- `ModifiedDate` → `ShipMethod`.`ModifiedDate` — exact_name, accepted

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261115T082653251229Z`) carrying 26 hub(s), 23 link(s) and 56 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

104 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/purchasing_requirements.md
- Generated dbt models: 123 raw-vault model(s) + 166 staging model(s) (see `state.artifacts`)
