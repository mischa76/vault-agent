<!-- Drafted deterministically from the AdventureWorks catalogue (Microsoft, MIT — see
NOTICE) by eval.adventureworks.draft_requirements: tables, descriptions, keys and foreign
keys as the catalogue states them. No analyst has read or written this. The C1 experiment,
2026-10-30. -->

# Requirements drafted from the source catalogue: purchasing

**Area:** Purchasing  
**Prepared by:** nobody — drafted from the catalogue  
**Status:** Draft, unreviewed

## 1. Purpose

The business needs to analyse what the purchasing area of the operational system records. This document lists what that area records, as the system's own catalogue describes it: its tables, what identifies each, what each records, and how they refer to one another. It states nothing the catalogue does not.

## 2. Business entities in scope

| Concept | What the catalogue says it is |
|---|---|
| Product vendor (a relationship) | Cross-reference table mapping vendors with the products they supply. |
| Purchase order detail | Individual products associated with a specific purchase order. See PurchaseOrderHeader. |
| Purchase order header | General purchase order information. See PurchaseOrderDetail. |
| Ship method | Shipping company lookup table. |
| Vendor (a kind of another concept) | Companies from whom Adventure Works Cycles purchases parts or other goods. |

## 3. Product vendor

Cross-reference table mapping vendors with the products they supply.

- **REQ-001** The business must record which **product**, **vendor** are related, as a **product vendor**.
- **REQ-002** Each product vendor is identified by the combination of **product id**, **business entity id**.
- **REQ-003** The business must record the **average lead time** of each product vendor: The average span of time (in days) between placing an order with the vendor and receiving the purchased product.
- **REQ-004** The business must record the **standard price** of each product vendor: The vendor's usual selling price.
- **REQ-005** The business must record the **last receipt cost** of each product vendor: The selling price when last purchased.
- **REQ-006** The business must record the **last receipt date** of each product vendor: Date the product was last received by the vendor.
- **REQ-007** The business must record the **min order qty** of each product vendor: The maximum quantity that should be ordered.
- **REQ-008** The business must record the **max order qty** of each product vendor: The minimum quantity that should be ordered.
- **REQ-009** The business must record the **on order qty** of each product vendor: The quantity currently on order.
- **REQ-010** Each product vendor refers to one **unit measure** (by its unit measure code).
- **REQ-011** Each product vendor carries a last-changed timestamp.

## 4. Purchase order detail

Individual products associated with a specific purchase order. See PurchaseOrderHeader.

- **REQ-012** The business must record every **purchase order detail**.
- **REQ-013** Each purchase order detail is identified by the combination of **purchase order id**, **purchase order detail id**.
- **REQ-014** The business must record the **due date** of each purchase order detail: Date the product is expected to be received.
- **REQ-015** The business must record the **order qty** of each purchase order detail: Quantity ordered.
- **REQ-016** The business must record the **unit price** of each purchase order detail: Vendor's selling price of a single product.
- **REQ-017** The business must record the **line total** of each purchase order detail: Per product subtotal. Computed as OrderQty * UnitPrice.
- **REQ-018** The business must record the **received qty** of each purchase order detail: Quantity actually received from the vendor.
- **REQ-019** The business must record the **rejected qty** of each purchase order detail: Quantity rejected during inspection.
- **REQ-020** The business must record the **stocked qty** of each purchase order detail: Quantity accepted into inventory. Computed as ReceivedQty - RejectedQty.
- **REQ-021** Each purchase order detail refers to one **product** (by its product id).
- **REQ-022** Each purchase order detail refers to one **purchase order header** (by its purchase order id).
- **REQ-023** Each purchase order detail carries a last-changed timestamp.

## 5. Purchase order header

General purchase order information. See PurchaseOrderDetail.

- **REQ-024** The business must record every **purchase order header**.
- **REQ-025** Each purchase order header is identified by its **purchase order id**.
- **REQ-026** The business must record the **revision number** of each purchase order header: Incremental number to track changes to the purchase order over time.
- **REQ-027** The business must record the **status** of each purchase order header: Order current status. 1 = Pending; 2 = Approved; 3 = Rejected; 4 = Complete
- **REQ-028** The business must record the **order date** of each purchase order header: Purchase order creation date.
- **REQ-029** The business must record the **ship date** of each purchase order header: Estimated shipment date from the vendor.
- **REQ-030** The business must record the **sub total** of each purchase order header: Purchase order subtotal. Computed as SUM(PurchaseOrderDetail.LineTotal)for the appropriate PurchaseOrderID.
- **REQ-031** The business must record the **tax amt** of each purchase order header: Tax amount.
- **REQ-032** The business must record the **freight** of each purchase order header: Shipping cost.
- **REQ-033** The business must record the **total due** of each purchase order header: Total due to vendor. Computed as Subtotal + TaxAmt + Freight.
- **REQ-034** Each purchase order header refers to one **employee** (by its employee id).
- **REQ-035** Each purchase order header refers to one **vendor** (by its vendor id).
- **REQ-036** Each purchase order header refers to one **ship method** (by its ship method id).
- **REQ-037** Each purchase order header carries a last-changed timestamp.

## 6. Ship method

Shipping company lookup table.

- **REQ-038** The business must record every **ship method**.
- **REQ-039** Each ship method is identified by its **name**.
- **REQ-040** The business must record the **ship base** of each ship method: Minimum shipping charge.
- **REQ-041** The business must record the **ship rate** of each ship method: Shipping charge per pound.
- **REQ-042** Each ship method carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 7. Vendor

Companies from whom Adventure Works Cycles purchases parts or other goods.

- **REQ-043** The business must record every **vendor**. Every vendor is a **business entity** and is identified by the same **business entity id**.
- **REQ-044** The business must record the **account number** of each vendor: Vendor account (identification) number.
- **REQ-045** The business must record the **name** of each vendor: Company name.
- **REQ-046** The business must record the **credit rating** of each vendor: 1 = Superior, 2 = Excellent, 3 = Above average, 4 = Average, 5 = Below average
- **REQ-047** The business must record the **preferred vendor status** of each vendor: 0 = Do not use if another vendor is available. 1 = Preferred over other vendors supplying the same product.
- **REQ-048** The business must record the **active flag** of each vendor: 0 = Vendor no longer used. 1 = Vendor is actively used.
- **REQ-049** The business must also record, for each vendor: **purchasing web service url**.
- **REQ-050** Each vendor carries a last-changed timestamp.
