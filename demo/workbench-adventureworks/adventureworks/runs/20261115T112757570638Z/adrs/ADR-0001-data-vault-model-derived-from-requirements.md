# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 87 requirement(s) and 9 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (3)

- **hub_purchase_order** — business key `PurchaseOrderID`. A purchase order placed with a vendor, identified by its purchase order number. _(requirements: REQ-030, REQ-031, REQ-086)_
- **hub_purchase_order_line** — business key `purchase_order_line`. A line of a purchase order, identified by the purchase order together with its line number. _(requirements: REQ-051, REQ-052, REQ-058)_
- **hub_ship_method** — business key `Name`. A shipping method (shipping company and rate agreement) for inbound purchases, identified by the shipping company name. _(requirements: REQ-070, REQ-071, REQ-035)_

### Links (5)

- **link_purchase_order_business_entity_ship_method** — connects hub_purchase_order, hub_business_entity (vendor), hub_business_entity (employee), hub_ship_method. Purchase order header relationships: the order is placed with exactly one vendor, created by one employee (buyer) and names one shipping method. Built from PurchaseOrderHeader (VendorID, EmployeeID, ShipMethodID). Unit of work: PurchaseOrderID with its VendorID, EmployeeID and ShipMethodID as recorded on the order header. _(requirements: REQ-032, REQ-033, REQ-034, REQ-035, REQ-046, REQ-008, REQ-074)_
- **link_purchase_order_line** — connects hub_purchase_order_line, hub_purchase_order, hub_product. A purchase order line belongs to its purchase order and refers to exactly one product (joined to the existing product hub via ProductID). Unit of work: PurchaseOrderID + PurchaseOrderDetailID with the ProductID ordered on that line. _(requirements: REQ-051, REQ-053, REQ-029, REQ-063, REQ-064, REQ-078)_
- **link_product_vendor** — connects hub_product, hub_business_entity (vendor), hub_unit_measure. Vendor-product supply relationship (many-to-many) from ProductVendor, including the unit of measure in which the product is bought from that vendor. Unit of work: ProductID + BusinessEntityID (vendor) pairing with its UnitMeasureCode. _(requirements: REQ-015, REQ-016, REQ-017, REQ-025, REQ-026, REQ-029, REQ-079)_
- **link_purchase_order_line_product** — connects hub_purchase_order_line, hub_product. Declared foreign key PurchaseOrderDetail.ProductID references PRODUCTNUMBER; ratified from the source catalogue (WP34). _(requirements: —)_
- **link_purchase_order_business_entity** — connects hub_purchase_order, hub_business_entity. Declared foreign key PurchaseOrderHeader.EmployeeID references BUSINESSENTITYID; ratified from the source catalogue (WP34). _(requirements: —)_

### Satellites (11)

- **sat_business_entity_vendor_details** — on hub_business_entity; payload: AccountNumber, Name, PurchasingWebServiceURL. Vendor identification and descriptive details: account number, company name, optional purchasing web service address. Source table: Vendor. Split rationale: Slow-changing identifying/descriptive vendor attributes, separated from the status codes whose history is analysed.. _(requirements: REQ-002, REQ-004, REQ-011, REQ-012)_
- **sat_business_entity_vendor_status** — on hub_business_entity; payload: CreditRating, PreferredVendorStatus, ActiveFlag, ModifiedDate. Vendor classification codes with history: credit rating, preferred status, active flag. Source table: Vendor. Split rationale: Coded status attributes whose change history must be retained and reconstructed at order time; carries the record's ModifiedDate.. _(requirements: REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-013, REQ-014, REQ-080, REQ-083)_
- **sat_purchase_order_status** — on hub_purchase_order; payload: Status, RevisionNumber, ModifiedDate. Purchase order status and revision number, historised to trace status transitions and revisions. Source table: PurchaseOrderHeader. Split rationale: Fast-changing workflow state, kept apart from dates and financial totals.. _(requirements: REQ-038, REQ-039, REQ-040, REQ-041, REQ-042, REQ-043, REQ-044, REQ-080)_
- **sat_purchase_order_dates** — on hub_purchase_order; payload: OrderDate, ShipDate. Order date and estimated shipment date of the purchase order. Source table: PurchaseOrderHeader. Split rationale: Scheduling dates, largely static once set.. _(requirements: REQ-036, REQ-037)_
- **sat_purchase_order_totals** — on hub_purchase_order; payload: SubTotal, TaxAmt, Freight, TotalDue. Order-level financial totals: subtotal, tax, freight and total due. Source table: PurchaseOrderHeader. Split rationale: Monetary amounts grouped together for spend analysis and reconciliation against lines.. _(requirements: REQ-045, REQ-046, REQ-047, REQ-048, REQ-049, REQ-075, REQ-082)_
- **sat_purchase_order_line_terms** — on hub_purchase_order_line; payload: OrderQty, UnitPrice, LineTotal, DueDate. Ordered quantity, unit price, line total and due date of the line. Source table: PurchaseOrderDetail. Split rationale: Order terms set when the line is placed, changing rarely.. _(requirements: REQ-054, REQ-055, REQ-056, REQ-057, REQ-059, REQ-067)_
- **sat_purchase_order_line_receipt** — on hub_purchase_order_line; payload: ReceivedQty, RejectedQty, StockedQty, ModifiedDate. Cumulative received, rejected and accepted (stocked) quantities, historised to show receipt progression. Source table: PurchaseOrderDetail. Split rationale: Running receipt figures that change with deliveries, split from the static order terms; carries ModifiedDate.. _(requirements: REQ-060, REQ-061, REQ-062, REQ-063, REQ-064, REQ-065, REQ-066, REQ-080)_
- **sat_product_vendor_terms** — on link_product_vendor; payload: AverageLeadTime, StandardPrice, MinOrderQty, MaxOrderQty. Standing commercial supply terms: average lead time, standard price, min/max order quantities. Source table: ProductVendor. Split rationale: Agreed terms changing slowly, historised for trend analysis; separated from running values.. _(requirements: REQ-018, REQ-019, REQ-022, REQ-023, REQ-027, REQ-069)_
- **sat_product_vendor_running_values** — on link_product_vendor; payload: LastReceiptCost, LastReceiptDate, OnOrderQty, ModifiedDate. Running values updated with activity: last receipt cost and date, quantity on order. Source table: ProductVendor. Split rationale: Fast-changing activity-driven figures, split from agreed terms by rate of change; carries ModifiedDate.. _(requirements: REQ-020, REQ-021, REQ-024, REQ-028, REQ-068, REQ-080)_
- **sat_ship_method_rates** — on hub_ship_method; payload: ShipBase, ShipRate, ModifiedDate. Ship base and ship rate, historised so historical freight can be assessed against rates in force. Source table: ShipMethod. Split rationale: Changing rate terms; rowguid excluded as it has no business meaning (REQ-077).. _(requirements: REQ-073, REQ-074, REQ-075, REQ-076, REQ-080)_
- **sat_ship_method_identifiers** — on hub_ship_method; payload: ShipMethodID. Internal shipping method identifier used on purchase orders. Source table: ShipMethod. Split rationale: Static internal identifier, separated from changing rates.. _(requirements: REQ-072)_

### Hub keys decided before modelling (1)

- **ShipMethod** — key `Name`: the declared natural key, taken as the default of a contested case; primary key `ShipMethodID`.

### Source mappings (39)

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
- `Status` → `PurchaseOrderHeader`.`Status` — exact_name, accepted
- `RevisionNumber` → `PurchaseOrderHeader`.`RevisionNumber` — exact_name, accepted
- `ModifiedDate` → `PurchaseOrderHeader`.`ModifiedDate` — exact_name, accepted
- `OrderDate` → `PurchaseOrderHeader`.`OrderDate` — exact_name, accepted
- `ShipDate` → `PurchaseOrderHeader`.`ShipDate` — exact_name, accepted
- `SubTotal` → `PurchaseOrderHeader`.`SubTotal` — exact_name, accepted
- `TaxAmt` → `PurchaseOrderHeader`.`TaxAmt` — exact_name, accepted
- `Freight` → `PurchaseOrderHeader`.`Freight` — exact_name, accepted
- `TotalDue` → `PurchaseOrderHeader`.`TotalDue` — exact_name, accepted
- `OrderQty` → `PurchaseOrderDetail`.`OrderQty` — exact_name, accepted
- `UnitPrice` → `PurchaseOrderDetail`.`UnitPrice` — exact_name, accepted
- `LineTotal` → `PurchaseOrderDetail`.`LineTotal` — exact_name, accepted
- `DueDate` → `PurchaseOrderDetail`.`DueDate` — exact_name, accepted
- `ReceivedQty` → `PurchaseOrderDetail`.`ReceivedQty` — exact_name, accepted
- `RejectedQty` → `PurchaseOrderDetail`.`RejectedQty` — exact_name, accepted
- `StockedQty` → `PurchaseOrderDetail`.`StockedQty` — exact_name, accepted
- `ModifiedDate` → `PurchaseOrderDetail`.`ModifiedDate` — exact_name, accepted
- `AverageLeadTime` → `ProductVendor`.`AverageLeadTime` — exact_name, accepted
- `StandardPrice` → `ProductVendor`.`StandardPrice` — exact_name, accepted
- `MinOrderQty` → `ProductVendor`.`MinOrderQty` — exact_name, accepted
- `MaxOrderQty` → `ProductVendor`.`MaxOrderQty` — exact_name, accepted
- `LastReceiptCost` → `ProductVendor`.`LastReceiptCost` — exact_name, accepted
- `LastReceiptDate` → `ProductVendor`.`LastReceiptDate` — exact_name, accepted
- `OnOrderQty` → `ProductVendor`.`OnOrderQty` — exact_name, accepted
- `ModifiedDate` → `ProductVendor`.`ModifiedDate` — exact_name, accepted
- `ShipBase` → `ShipMethod`.`ShipBase` — exact_name, accepted
- `ShipRate` → `ShipMethod`.`ShipRate` — exact_name, accepted
- `ModifiedDate` → `ShipMethod`.`ModifiedDate` — exact_name, accepted
- `ShipMethodID` → `ShipMethod`.`ShipMethodID` — exact_name, accepted

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261115T111823849877Z`) carrying 26 hub(s), 23 link(s) and 61 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

109 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/purchasing_requirements.md
- Generated dbt models: 129 raw-vault model(s) + 199 staging model(s) (see `state.artifacts`)
