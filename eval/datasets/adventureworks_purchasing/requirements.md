# Business Requirements: Purchasing and Vendor Management Data Warehouse

## 1. Purpose and Scope

This document describes what the business needs to be able to see and analyse in the **purchasing area** of our bicycle manufacturing and retail operation. It covers the vendors we buy from, the products they supply to us, the purchase orders we place, what actually arrives against those orders, and the shipping methods used to get goods to us.

It is written from the operational purchasing system as it exists today. It states the business need only — how the warehouse is designed and modelled is a separate exercise.

Out of scope: sales to customers, manufacturing, inventory movements after goods are accepted, and finance/payables. Those areas touch purchasing but are not described here.

## 2. Business Context

We buy components and finished goods from external companies (vendors). Purchasing staff raise purchase orders with a chosen vendor, listing one or more products with quantities and agreed prices. The vendor ships against the order using an agreed shipping company; goods arrive, are inspected, and either accepted into stock or rejected. Alongside individual orders, we maintain a standing commercial relationship per vendor and product — typical price, typical lead time, and the order quantity limits we have agreed.

The business needs a single, historically complete view of this activity to answer questions about supplier performance, purchasing spend, delivery reliability, and quality of received goods.

## 3. Business Entities

### 3.1 Vendor

REQ-001 The warehouse must record every **vendor** — a company from which we purchase goods.

REQ-002 A vendor is identified in business terms by its **vendor account number**, the identification number by which purchasing staff and vendor correspondence refer to the company. The operational system also carries an internal business entity identifier for each vendor; both must be retained, since the internal identifier is what other purchasing records point to.

REQ-003 The **vendor's company name** must be recorded and reportable.

REQ-004 Each vendor carries a **credit rating** on a five-point scale, from *Superior* through *Excellent*, *Above average* and *Average* to *Below average*. Reporting must present this rating in its business wording, not as a bare code.

REQ-005 Each vendor carries a **preferred vendor status**: either "preferred over other vendors supplying the same product" or "do not use if another vendor is available". Purchasing management needs to see whether orders are in fact being placed with preferred vendors.

REQ-006 Each vendor carries an **active flag** indicating whether the vendor is still actively used or is no longer used. Vendors that are no longer used must remain in the warehouse — historical orders placed with them must stay reportable.

REQ-007 Where a vendor offers an electronic purchasing interface, the **purchasing web service address** must be recorded. This attribute is not always populated; reporting must tolerate its absence.

REQ-008 Vendor attributes change over time. Credit rating, preferred status and active flag in particular are commercial judgements that are revised. The warehouse must retain the history of these changes so that the state of a vendor **at the time an order was placed** can be reconstructed, not only the current state.

> *Clarification needed:* the source records only the date a vendor record was last updated, not the individual reasons for change. Whether the business needs the *reason* for a credit rating or preferred-status change, and from where that would come, needs to be confirmed with purchasing management.

### 3.2 Product supplied by a vendor (the supply relationship)

REQ-009 The warehouse must record, for each combination of **a product and a vendor**, the standing commercial terms under which we buy that product from that vendor. The same product may be supplied by several vendors, and a vendor supplies several products.

REQ-010 This supply relationship is identified in business terms by the pairing of the product and the vendor.

REQ-011 The **average lead time** must be recorded: the average span of time, in days, between placing an order with that vendor and receiving the purchased product. This is a key input to purchasing planning and to supplier comparison.

REQ-012 The **standard price** — the vendor's usual selling price for that product — must be recorded.

REQ-013 The **last receipt cost** — the selling price when the product was last purchased from that vendor — and the **last receipt date** — the date the product was last received from that vendor — must both be recorded. Together with the standard price these let the business see price drift between the agreed and the actually paid price.

REQ-014 The agreed **minimum and maximum order quantities** for the product from that vendor must be recorded, so that buyers and reporting can see whether orders respect the agreed bounds.

> *Note on a source inconsistency:* in the operational system the descriptions of the minimum and maximum order quantity fields are transposed — the field named as the minimum is described as "the maximum quantity that should be ordered" and vice versa. Which field carries which meaning must be confirmed with the purchasing team before either is used in reporting or in any threshold check.

REQ-015 The **quantity currently on order** for the product from that vendor must be available, as an indicator of open commitment.

REQ-016 The **unit of measure** in which the product is bought from that vendor must be recorded. The same product may plausibly be bought in different units from different vendors, so quantities and prices must always be interpreted together with this unit.

REQ-017 The supply terms change over time — prices are renegotiated, lead times improve or deteriorate, and quantity bounds are adjusted. The warehouse must retain this history so that trends in agreed price and lead time per vendor and product can be analysed.

REQ-018 The quantity on order and the last receipt figures are, by their nature, running values that are updated as activity occurs. Reporting must be clear about whether it is showing the current value or the value as at a point in time.

REQ-019 Products themselves are maintained outside the purchasing area. The warehouse must nonetheless be able to identify each purchased product consistently and to join purchasing activity to the wider product information held elsewhere.

### 3.3 Purchase order

REQ-020 The warehouse must record every **purchase order** we place with a vendor.

REQ-021 A purchase order is identified in business terms by its **purchase order number**.

REQ-022 Each purchase order is **placed with exactly one vendor** — the vendor with whom the order is placed.

REQ-023 Each purchase order is **created by one employee**, the buyer who raised it. The warehouse must be able to report purchasing activity by the employee who created the order.

> *Note:* employee master data is maintained outside the purchasing area. Only the identity of the creating employee is available here; name, department and role must come from the HR/employee area if the business wants to report on them.

REQ-024 Each purchase order names a **shipping method** — the shipping company and rate agreement used to bring the goods to us.

REQ-025 Each purchase order carries an **order date**, the date the order was created.

REQ-026 Each purchase order carries an **estimated shipment date** — the date the vendor is expected to ship. The business needs to compare this expectation against actual receipt activity.

REQ-027 Each purchase order carries a **status**, which is one of *Pending*, *Approved*, *Rejected* or *Complete*. Reporting must present the status in business wording. The business needs to see the population of orders in each status, in particular orders that are approved but not yet complete.

REQ-028 Each purchase order carries a **revision number**, an incrementing counter tracking how the order has changed over time. The business needs to know that an order was revised and how many times — a frequently revised order is a signal about the order or the vendor relationship.

REQ-029 The warehouse must retain the **history of a purchase order as it changes**: status transitions (for example Pending → Approved → Complete) and revisions must be traceable over time, not overwritten by the latest state. The business needs to answer "when was this order approved?" and "how long did it sit pending?".

> *Clarification needed:* the operational system holds only the current version of an order together with its revision number and last-updated date; it does not appear to keep prior versions. Whether the warehouse can reconstruct a full revision history depends on how frequently the source is captured, and the business expectation on this needs to be agreed.

REQ-030 Each purchase order carries financial totals: a **subtotal** (the sum of the value of its lines), a **tax amount**, a **freight (shipping cost)** amount, and a **total due to the vendor** (subtotal plus tax plus freight).

REQ-031 The business must be able to analyse **purchasing spend** by vendor, by employee, by shipping method, and over time, using these order totals.

REQ-032 Because the subtotal and total due are derived from the order lines and the other charges, the warehouse must be able to demonstrate that the totals it reports are consistent with the underlying lines. Any discrepancy between the stated order total and the sum of its lines is itself a finding the business wants to see.

REQ-033 Freight and tax are order-level charges and are **not** attributed to individual products in the source. If the business wants product-level landed cost, the basis for allocating freight and tax across lines must be decided by the business; it cannot be derived from the source as it stands.

### 3.4 Purchase order line

REQ-034 Each purchase order **contains one or more lines**, one per purchased product.

REQ-035 A line is identified in business terms by the purchase order it belongs to together with its **line number**.

REQ-036 Each line refers to **exactly one product**.

REQ-037 Each line carries the **quantity ordered**.

REQ-038 Each line carries the **unit price**, the vendor's selling price for a single unit of that product on this order.

REQ-039 Each line carries a **line total** — the ordered quantity multiplied by the unit price.

REQ-040 Each line carries a **due date**, the date on which the product is expected to be received. Note that this expectation is held per line, so different products on the same order may be expected at different times; delivery-performance analysis must work at line level, not only at order level.

REQ-041 The business must be able to compare the **unit price actually paid on a line** with the **standard price agreed** for that product and vendor, to identify off-contract purchasing.

### 3.5 Receipt and inspection against a line

REQ-042 Each purchase order line records the **quantity actually received** from the vendor.

REQ-043 Each line records the **quantity rejected during inspection**.

REQ-044 Each line records the **quantity accepted into inventory**, being the received quantity less the rejected quantity.

REQ-045 The business must be able to measure, per line, per order, per product and per vendor, the **fulfilment gap** between what was ordered and what was received, including under-delivery and over-delivery.

REQ-046 The business must be able to measure **inspection reject rates** — rejected quantity as a share of received quantity — by vendor and by product, as the primary indicator of incoming quality.

REQ-047 Receipt and rejection quantities accumulate as goods arrive and are inspected; a line's received quantity may change over the life of the order. The warehouse must retain this progression so that "how much had been received as at a given date" can be answered, and so that partial deliveries are visible rather than only the final position.

> *Clarification needed:* the source records only cumulative received, rejected and accepted quantities per line, together with a last-updated date. It does not record individual receipt events, receipt dates, or inspection outcomes per delivery. If the business needs to analyse individual deliveries (for example, how many part-shipments made up an order line, or the date of each), that information must be sourced elsewhere or the requirement dropped.

REQ-048 The business must be able to compare the **due date on a line** against evidence of when goods were actually received, in order to measure **on-time delivery** by vendor. Given the limitation noted above, the practical measure of actual receipt timing available today is the last receipt date held on the vendor–product supply relationship; whether that is a sufficient basis for an on-time-delivery metric needs to be agreed with the business.

REQ-049 The business must be able to compare **actual elapsed time from order to receipt** against the **average lead time** recorded for that vendor and product, to validate whether recorded lead times are realistic.

### 3.6 Shipping method

REQ-050 The warehouse must record every **shipping method** available for inbound purchases.

REQ-051 A shipping method is identified in business terms by the **shipping company name**, and by an internal shipping method identifier used on purchase orders.

REQ-052 Each shipping method carries a **minimum shipping charge (ship base)** and a **charge per pound (ship rate)**. These are the terms on which freight is expected to be charged.

REQ-053 The business must be able to analyse **freight cost by shipping method**, and to compare the freight actually charged on orders against the base and per-pound rates agreed with the shipping company.

REQ-054 Shipping rates change over time. The warehouse must retain the history of ship base and ship rate so that freight charged on a historical order can be assessed against the rates in force at that time.

REQ-055 The source system carries a technical replication identifier on shipping method records. It carries no business meaning and is not required for reporting.

## 4. How the Entities Relate

Stated in business terms, the picture is:

- A **vendor** supplies one or more **products**, and a product may be supplied by more than one vendor. Each such supply relationship carries its own agreed price, lead time and order quantity bounds.
- A **purchase order** is placed with exactly one **vendor**, is created by one **employee**, and specifies one **shipping method**.
- A purchase order **contains one or more lines**; each line is for exactly one **product** and carries its own quantity, price and expected due date.
- Receipt and inspection outcomes attach to the **line**, not to the order as a whole.
- The products bought on an order's lines are normally, but not necessarily, products for which a supply relationship with that vendor exists. Where a line names a product with no recorded supply relationship for that vendor, that is a finding the business wants surfaced rather than a data error to be hidden.

## 5. Cross-Cutting Requirements

REQ-056 Every record in the purchasing source carries a **last-modified date and time**. The warehouse must use these to establish when information changed and must not present a value as current when a more recent change exists.

REQ-057 All monetary amounts in this area are held in a single currency in the source; no currency indicator is present. If the business buys from vendors in other currencies, the currency of purchase orders and prices needs to be clarified — it cannot be established from the schema.

REQ-058 Codes with defined business meanings — purchase order status, vendor credit rating, preferred vendor status, active flag — must be presented in reporting in their business wording. The mapping must be held once and applied consistently.

REQ-059 Quantities must always be interpreted together with the unit of measure recorded on the relevant vendor–product supply relationship. Aggregating quantities across products or across units of measure without regard to the unit produces meaningless figures and must be prevented in reporting.

REQ-060 Records that no longer represent current operational reality — inactive vendors, completed or rejected orders, discontinued supply relationships — must be retained in full. Purchasing analysis is largely historical; nothing may be physically removed because it has ceased to be current.

## 6. Open Points for the Business

1. The transposed minimum/maximum order quantity descriptions (REQ-014) must be resolved before either value is used.
2. Whether individual receipt and inspection events are needed, and if so where they can be sourced (REQ-047, REQ-048).
3. Whether prior versions of a purchase order are needed, or whether the revision counter and current state suffice (REQ-029).
4. Whether purchasing is single-currency (REQ-057).
5. Whether freight and tax need allocating to product level, and on what basis (REQ-033).
6. Which employee attributes are needed for buyer reporting, from the employee area (REQ-023).
