# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-10-23
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 97 requirement(s) and 9 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (3)

- **hub_purchase_order** — business key `PurchaseOrderID`. Purchase order placed with a vendor, identified by its purchase order number. _(requirements: REQ-029, REQ-030, REQ-044, REQ-044-2)_
- **hub_purchase_order_detail** — business key `purchase_order_line`. Purchase order line, identified by the purchase order plus its line number. _(requirements: REQ-001-2, REQ-002-2, REQ-034-2, REQ-008-2)_
- **hub_ship_method** — business key `ShipMethodID`. Shipping method for inbound purchases. Keyed on ShipMethodID, the identifier purchase orders reference (REQ-022-2), so orders can join to it. The shipping company name is kept in a satellite. _(requirements: REQ-020-2, REQ-021-2, REQ-022-2, REQ-035, REQ-033-2)_

### Links (5)

- **link_product_vendor** — connects hub_product, hub_business_entity, hub_unit_measure. Vendor-product supply relationship: which vendor supplies which product, and the unit of measure it is bought in. Many-to-many. Unit of work: ProductID + vendor BusinessEntityID (with the UnitMeasureCode the product is bought in). _(requirements: REQ-014, REQ-015, REQ-016, REQ-024, REQ-025, REQ-028, REQ-029-2, REQ-030-2, REQ-042-2)_
- **link_purchase_order** — connects hub_purchase_order, hub_business_entity (vendor), hub_business_entity (employee), hub_ship_method. Purchase order header: the vendor the order is placed with, the employee who created it, and the shipping method it names. Unit of work: PurchaseOrderID with VendorID, EmployeeID and ShipMethodID from one order header. _(requirements: REQ-031, REQ-032, REQ-033, REQ-034, REQ-035, REQ-048, REQ-008, REQ-031-2, REQ-032-2, REQ-033-2)_
- **link_purchase_order_detail** — connects hub_purchase_order_detail, hub_purchase_order, hub_product. Purchase order line: the order it belongs to and the product it refers to. Unit of work: PurchaseOrderID + PurchaseOrderDetailID with the line's ProductID. _(requirements: REQ-001-2, REQ-002-2, REQ-003-2, REQ-028, REQ-035-2, REQ-036-2, REQ-049)_
- **link_purchase_order_detail_product** — connects hub_purchase_order_detail, hub_product. Declared foreign key PurchaseOrderDetail.ProductID references PRODUCTID; ratified from the source catalogue (WP34). _(requirements: —)_
- **link_purchase_order_business_entity** — connects hub_purchase_order, hub_business_entity. Declared foreign key PurchaseOrderHeader.EmployeeID references BUSINESSENTITYID; ratified from the source catalogue (WP34). _(requirements: —)_

### Satellites (10)

- **sat_business_entity_vendor_details** — on hub_business_entity; payload: AccountNumber, Name, PurchasingWebServiceURL. Vendor identifying and descriptive attributes: account number, company name and purchasing web service address (may be empty). Source table: Vendor. Split rationale: Slowly changing descriptive attributes, kept apart from the classification codes that change more often.. _(requirements: REQ-002, REQ-004, REQ-011, REQ-012)_
- **sat_business_entity_vendor_status** — on hub_business_entity; payload: CreditRating, PreferredVendorStatus, ActiveFlag, ModifiedDate. Vendor credit rating, preferred status and active flag, with history so a vendor's state when an order was placed can be rebuilt. Source table: Vendor. Split rationale: Coded classification attributes whose history is explicitly required; they change at a different rate from the name and account details.. _(requirements: REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-013, REQ-037-2, REQ-040-2)_
- **sat_product_vendor_terms** — on link_product_vendor; payload: AverageLeadTime, StandardPrice, MinOrderQty, MaxOrderQty, ModifiedDate. Agreed supply terms: average lead time, standard price, and minimum/maximum order quantities (the min/max meaning must be confirmed, REQ-022). History is kept for trend analysis. Source table: ProductVendor. Split rationale: Negotiated terms that change rarely, kept apart from the running receipt and on-order figures.. _(requirements: REQ-017, REQ-018, REQ-021, REQ-022, REQ-026, REQ-030-2, REQ-009-2, REQ-019-2, REQ-037-2)_
- **sat_product_vendor_receipt** — on link_product_vendor; payload: LastReceiptCost, LastReceiptDate, OnOrderQty. Running operational figures: last receipt cost, last receipt date and quantity currently on order. Source table: ProductVendor. Split rationale: Fast-changing running values, separated from the agreed terms by rate of change.. _(requirements: REQ-019, REQ-020, REQ-023, REQ-027, REQ-018-2)_
- **sat_purchase_order_details** — on hub_purchase_order; payload: RevisionNumber, Status, OrderDate, ShipDate, ModifiedDate. Order status, revision number, order date and estimated ship date, with history of status changes and revisions. Source table: PurchaseOrderHeader. Split rationale: Lifecycle and status attributes, kept apart from the financial totals.. _(requirements: REQ-036, REQ-037, REQ-038, REQ-039, REQ-040, REQ-041, REQ-042, REQ-043, REQ-044, REQ-045, REQ-046, REQ-037-2)_
- **sat_purchase_order_totals** — on hub_purchase_order; payload: SubTotal, TaxAmt, Freight, TotalDue. Order-level financial totals: subtotal, tax, freight and total due. Source table: PurchaseOrderHeader. Split rationale: Monetary amounts, split from the status attributes by data type.. _(requirements: REQ-047, REQ-048, REQ-049, REQ-050, REQ-051, REQ-052, REQ-025-2, REQ-026-2, REQ-039-2)_
- **sat_purchase_order_detail_order** — on hub_purchase_order_detail; payload: OrderQty, UnitPrice, LineTotal, DueDate, ModifiedDate. Ordered terms on each line: quantity ordered, unit price, line total and due date. Source table: PurchaseOrderDetail. Split rationale: Values set when the order is placed, which rarely change afterwards.. _(requirements: REQ-004-2, REQ-005-2, REQ-006-2, REQ-007-2, REQ-008-2, REQ-009-2, REQ-017-2, REQ-037-2)_
- **sat_purchase_order_detail_receipt** — on hub_purchase_order_detail; payload: ReceivedQty, RejectedQty, StockedQty. Cumulative received, rejected and accepted quantities on each line. History shows how they progress, including partial deliveries. Source table: PurchaseOrderDetail. Split rationale: Receipt and inspection progress changes over the life of the order, separately from the ordered terms.. _(requirements: REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2, REQ-015-2, REQ-016-2, REQ-034-2)_
- **sat_ship_method_details** — on hub_ship_method; payload: Name. Shipping company name (the business identifier). The rowguid replication column is left out because it has no business meaning. Source table: ShipMethod. Split rationale: Stable descriptive name, kept apart from the rates.. _(requirements: REQ-021-2, REQ-028-2)_
- **sat_ship_method_rates** — on hub_ship_method; payload: ShipBase, ShipRate, ModifiedDate. Ship base (minimum charge) and ship rate (charge per pound), with history so historical freight can be checked against the rates in force at the time. Source table: ShipMethod. Split rationale: Commercial rates with required history, which change at a different rate from the name.. _(requirements: REQ-023-2, REQ-024-2, REQ-025-2, REQ-026-2, REQ-027-2, REQ-037-2)_

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
- `RevisionNumber` → `PurchaseOrderHeader`.`RevisionNumber` — exact_name, accepted
- `Status` → `PurchaseOrderHeader`.`Status` — exact_name, accepted
- `OrderDate` → `PurchaseOrderHeader`.`OrderDate` — exact_name, accepted
- `ShipDate` → `PurchaseOrderHeader`.`ShipDate` — exact_name, accepted
- `ModifiedDate` → `PurchaseOrderHeader`.`ModifiedDate` — exact_name, accepted
- `SubTotal` → `PurchaseOrderHeader`.`SubTotal` — exact_name, accepted
- `TaxAmt` → `PurchaseOrderHeader`.`TaxAmt` — exact_name, accepted
- `Freight` → `PurchaseOrderHeader`.`Freight` — exact_name, accepted
- `TotalDue` → `PurchaseOrderHeader`.`TotalDue` — exact_name, accepted
- `OrderQty` → `PurchaseOrderDetail`.`OrderQty` — exact_name, accepted
- `UnitPrice` → `PurchaseOrderDetail`.`UnitPrice` — exact_name, accepted
- `LineTotal` → `PurchaseOrderDetail`.`LineTotal` — exact_name, accepted
- `DueDate` → `PurchaseOrderDetail`.`DueDate` — exact_name, accepted
- `ModifiedDate` → `PurchaseOrderDetail`.`ModifiedDate` — exact_name, accepted
- `ReceivedQty` → `PurchaseOrderDetail`.`ReceivedQty` — exact_name, accepted
- `RejectedQty` → `PurchaseOrderDetail`.`RejectedQty` — exact_name, accepted
- `StockedQty` → `PurchaseOrderDetail`.`StockedQty` — exact_name, accepted
- `Name` → `ShipMethod`.`Name` — exact_name, accepted
- `ShipBase` → `ShipMethod`.`ShipBase` — exact_name, accepted
- `ShipRate` → `ShipMethod`.`ShipRate` — exact_name, accepted
- `ModifiedDate` → `ShipMethod`.`ModifiedDate` — exact_name, accepted

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261022T233308793834Z`) carrying 26 hub(s), 22 link(s) and 57 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

104 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/purchasing_requirements.md
- Generated dbt models: 123 raw-vault model(s) + 108 staging model(s) (see `state.artifacts`)
