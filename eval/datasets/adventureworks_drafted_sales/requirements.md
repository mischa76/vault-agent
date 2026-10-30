<!-- Drafted deterministically from the AdventureWorks catalogue (Microsoft, MIT — see
NOTICE) by eval.adventureworks.draft_requirements: tables, descriptions, keys and foreign
keys as the catalogue states them. No analyst has read or written this. The C1 experiment,
2026-10-30. -->

# Requirements drafted from the source catalogue: sales

**Area:** Sales  
**Prepared by:** nobody — drafted from the catalogue  
**Status:** Draft, unreviewed

## 1. Purpose

The business needs to analyse what the sales area of the operational system records. This document lists what that area records, as the system's own catalogue describes it: its tables, what identifies each, what each records, and how they refer to one another. It states nothing the catalogue does not.

## 2. Business entities in scope

| Concept | What the catalogue says it is |
|---|---|
| Country region currency (a relationship) | Cross-reference table mapping ISO currency codes to a country or region. |
| Credit card | Customer credit card information. |
| Currency | Lookup table containing standard ISO currencies. |
| Currency rate | Currency exchange rates. |
| Customer | Current customer information. Also see the Person and Store tables. |
| Person credit card (a relationship) | Cross-reference table mapping people to their credit card information in the CreditCard table. |
| Sales order detail | Individual products associated with a specific sales order. See SalesOrderHeader. |
| Sales order header | General sales order information. |
| Sales order header sales reason (a relationship) | Cross-reference table mapping sales orders to sales reason codes. |
| Sales person (a kind of another concept) | Sales representative current information. |
| Sales person quota history | Sales performance tracking. |
| Sales reason | Lookup table of customer purchase reasons. |
| Sales tax rate | Tax rate lookup table. |
| Sales territory | Sales territory lookup table. |
| Sales territory history | Sales representative transfers to other sales territories. |
| Shopping cart item | Contains online customer orders until the order is submitted or cancelled. |
| Special offer | Sale discounts lookup table. |
| Special offer product (a relationship) | Cross-reference table mapping products to special offer discounts. |
| Store (a kind of another concept) | Customers (resellers) of Adventure Works products. |

## 3. Country region currency

Cross-reference table mapping ISO currency codes to a country or region.

- **REQ-001** The business must record which **country region**, **currency** are related, as a **country region currency**.
- **REQ-002** Each country region currency is identified by the combination of **country region code**, **currency code**.
- **REQ-003** Each country region currency carries a last-changed timestamp.

## 4. Credit card

Customer credit card information.

- **REQ-004** The business must record every **credit card**.
- **REQ-005** Each credit card is identified by its **card number**.
- **REQ-006** The business must record the **card type** of each credit card: Credit card name.
- **REQ-007** The business must record the **exp month** of each credit card: Credit card expiration month.
- **REQ-008** The business must record the **exp year** of each credit card: Credit card expiration year.
- **REQ-009** Each credit card carries a last-changed timestamp.

## 5. Currency

Lookup table containing standard ISO currencies.

- **REQ-010** The business must record every **currency**.
- **REQ-011** Each currency is identified by its **name**.
- **REQ-012** Each currency carries a last-changed timestamp.

## 6. Currency rate

Currency exchange rates.

- **REQ-013** The business must record every **currency rate**.
- **REQ-014** Each currency rate is identified by the combination of **currency rate date**, **from currency code**, **to currency code**.
- **REQ-015** The business must record the **average rate** of each currency rate: Average exchange rate for the day.
- **REQ-016** The business must record the **end of day rate** of each currency rate: Final exchange rate for the day.
- **REQ-017** Each currency rate refers to one **currency** (by its from currency code).
- **REQ-018** Each currency rate refers to one **currency** (by its to currency code).
- **REQ-019** Each currency rate carries a last-changed timestamp.

## 7. Customer

Current customer information. Also see the Person and Store tables.

- **REQ-020** The business must record every **customer**.
- **REQ-021** Each customer is identified by its **account number**.
- **REQ-022** Each customer refers to one **person** (by its person id).
- **REQ-023** Each customer refers to one **store** (by its store id).
- **REQ-024** Each customer refers to one **sales territory** (by its territory id).
- **REQ-025** Each customer carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 8. Person credit card

Cross-reference table mapping people to their credit card information in the CreditCard table.

- **REQ-026** The business must record which **person**, **credit card** are related, as a **person credit card**.
- **REQ-027** Each person credit card is identified by the combination of **business entity id**, **credit card id**.
- **REQ-028** Each person credit card carries a last-changed timestamp.

## 9. Sales order detail

Individual products associated with a specific sales order. See SalesOrderHeader.

- **REQ-029** The business must record every **sales order detail**.
- **REQ-030** Each sales order detail is identified by the combination of **sales order id**, **sales order detail id**.
- **REQ-031** The business must record the **carrier tracking number** of each sales order detail: Shipment tracking number supplied by the shipper.
- **REQ-032** The business must record the **order qty** of each sales order detail: Quantity ordered per product.
- **REQ-033** The business must record the **unit price** of each sales order detail: Selling price of a single product.
- **REQ-034** The business must record the **unit price discount** of each sales order detail: Discount amount.
- **REQ-035** The business must record the **line total** of each sales order detail: Per product subtotal. Computed as UnitPrice * (1 - UnitPriceDiscount) * OrderQty.
- **REQ-036** Each sales order detail refers to one **sales order header** (by its sales order id).
- **REQ-037** Each sales order detail refers to one **special offer product** (by its special offer id, product id).
- **REQ-038** Each sales order detail carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 10. Sales order header

General sales order information.

- **REQ-039** The business must record every **sales order header**.
- **REQ-040** Each sales order header is identified by its **sales order number**.
- **REQ-041** The business must record the **revision number** of each sales order header: Incremental number to track changes to the sales order over time.
- **REQ-042** The business must record the **order date** of each sales order header: Dates the sales order was created.
- **REQ-043** The business must record the **due date** of each sales order header: Date the order is due to the customer.
- **REQ-044** The business must record the **ship date** of each sales order header: Date the order was shipped to the customer.
- **REQ-045** The business must record the **status** of each sales order header: Order current status. 1 = In process; 2 = Approved; 3 = Backordered; 4 = Rejected; 5 = Shipped; 6 = Cancelled
- **REQ-046** The business must record the **online order flag** of each sales order header: 0 = Order placed by sales person. 1 = Order placed online by customer.
- **REQ-047** The business must record the **purchase order number** of each sales order header: Customer purchase order number reference.
- **REQ-048** The business must record the **account number** of each sales order header: Financial accounting number reference.
- **REQ-049** The business must record the **credit card approval code** of each sales order header: Approval code provided by the credit card company.
- **REQ-050** The business must record the **sub total** of each sales order header: Sales subtotal. Computed as SUM(SalesOrderDetail.LineTotal)for the appropriate SalesOrderID.
- **REQ-051** The business must record the **tax amt** of each sales order header: Tax amount.
- **REQ-052** The business must record the **freight** of each sales order header: Shipping cost.
- **REQ-053** The business must record the **total due** of each sales order header: Total due from customer. Computed as Subtotal + TaxAmt + Freight.
- **REQ-054** The business must record the **comment** of each sales order header: Sales representative comments.
- **REQ-055** Each sales order header refers to one **address** (by its bill to address id).
- **REQ-056** Each sales order header refers to one **address** (by its ship to address id).
- **REQ-057** Each sales order header refers to one **credit card** (by its credit card id).
- **REQ-058** Each sales order header refers to one **currency rate** (by its currency rate id).
- **REQ-059** Each sales order header refers to one **customer** (by its customer id).
- **REQ-060** Each sales order header refers to one **sales person** (by its sales person id).
- **REQ-061** Each sales order header refers to one **ship method** (by its ship method id).
- **REQ-062** Each sales order header refers to one **sales territory** (by its territory id).
- **REQ-063** Each sales order header carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 11. Sales order header sales reason

Cross-reference table mapping sales orders to sales reason codes.

- **REQ-064** The business must record which **sales reason**, **sales order header** are related, as a **sales order header sales reason**.
- **REQ-065** Each sales order header sales reason is identified by the combination of **sales order id**, **sales reason id**.
- **REQ-066** Each sales order header sales reason carries a last-changed timestamp.

## 12. Sales person

Sales representative current information.

- **REQ-067** The business must record every **sales person**. Every sales person is a **employee** and is identified by the same **business entity id**.
- **REQ-068** The business must record the **sales quota** of each sales person: Projected yearly sales.
- **REQ-069** The business must record the **bonus** of each sales person: Bonus due if quota is met.
- **REQ-070** The business must record the **commission pct** of each sales person: Commision percent received per sale.
- **REQ-071** The business must record the **sales ytd** of each sales person: Sales total year to date.
- **REQ-072** The business must record the **sales last year** of each sales person: Sales total of previous year.
- **REQ-073** Each sales person refers to one **sales territory** (by its territory id).
- **REQ-074** Each sales person carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 13. Sales person quota history

Sales performance tracking.

- **REQ-075** The business must record every **sales person quota history**.
- **REQ-076** Each sales person quota history is identified by the combination of **business entity id**, **quota date**.
- **REQ-077** The business must record the **sales quota** of each sales person quota history: Sales quota amount.
- **REQ-078** Each sales person quota history refers to one **sales person** (by its business entity id).
- **REQ-079** Each sales person quota history carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 14. Sales reason

Lookup table of customer purchase reasons.

- **REQ-080** The business must record every **sales reason**.
- **REQ-081** Each sales reason is identified by its **sales reason id**.
- **REQ-082** The business must record the **name** of each sales reason: Sales reason description.
- **REQ-083** The business must record the **reason type** of each sales reason: Category the sales reason belongs to.
- **REQ-084** Each sales reason carries a last-changed timestamp.

## 15. Sales tax rate

Tax rate lookup table.

- **REQ-085** The business must record every **sales tax rate**.
- **REQ-086** Each sales tax rate is identified by the combination of **state province id**, **tax type**.
- **REQ-087** The business must record the **tax rate** of each sales tax rate: Tax rate amount.
- **REQ-088** The business must record the **name** of each sales tax rate: Tax rate description.
- **REQ-089** Each sales tax rate refers to one **state province** (by its state province id).
- **REQ-090** Each sales tax rate carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 16. Sales territory

Sales territory lookup table.

- **REQ-091** The business must record every **sales territory**.
- **REQ-092** Each sales territory is identified by its **name**.
- **REQ-093** The business must record the **group** of each sales territory: Geographic area to which the sales territory belong.
- **REQ-094** The business must record the **sales ytd** of each sales territory: Sales in the territory year to date.
- **REQ-095** The business must record the **sales last year** of each sales territory: Sales in the territory the previous year.
- **REQ-096** The business must record the **cost ytd** of each sales territory: Business costs in the territory year to date.
- **REQ-097** The business must record the **cost last year** of each sales territory: Business costs in the territory the previous year.
- **REQ-098** Each sales territory refers to one **country region** (by its country region code).
- **REQ-099** Each sales territory carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 17. Sales territory history

Sales representative transfers to other sales territories.

- **REQ-100** The business must record every **sales territory history**.
- **REQ-101** Each sales territory history is identified by the combination of **business entity id**, **start date**, **territory id**.
- **REQ-102** The business must record the **end date** of each sales territory history: Date the sales representative left work in the territory.
- **REQ-103** Each sales territory history refers to one **sales person** (by its business entity id).
- **REQ-104** Each sales territory history refers to one **sales territory** (by its territory id).
- **REQ-105** Each sales territory history carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 18. Shopping cart item

Contains online customer orders until the order is submitted or cancelled.

- **REQ-106** The business must record every **shopping cart item**.
- **REQ-107** Each shopping cart item is identified by its **shopping cart item id**.
- **REQ-108** The business must record the **shopping cart id** of each shopping cart item: Shopping cart identification number.
- **REQ-109** The business must record the **quantity** of each shopping cart item: Product quantity ordered.
- **REQ-110** The business must record the **date created** of each shopping cart item: Date the time the record was created.
- **REQ-111** Each shopping cart item refers to one **product** (by its product id).
- **REQ-112** Each shopping cart item carries a last-changed timestamp.

## 19. Special offer

Sale discounts lookup table.

- **REQ-113** The business must record every **special offer**.
- **REQ-114** Each special offer is identified by its **special offer id**.
- **REQ-115** The business must record the **description** of each special offer: Discount description.
- **REQ-116** The business must record the **discount pct** of each special offer: Discount precentage.
- **REQ-117** The business must record the **type** of each special offer: Discount type category.
- **REQ-118** The business must record the **category** of each special offer: Group the discount applies to such as Reseller or Customer.
- **REQ-119** The business must record the **start date** of each special offer: Discount start date.
- **REQ-120** The business must record the **end date** of each special offer: Discount end date.
- **REQ-121** The business must record the **min qty** of each special offer: Minimum discount percent allowed.
- **REQ-122** The business must record the **max qty** of each special offer: Maximum discount percent allowed.
- **REQ-123** Each special offer carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 20. Special offer product

Cross-reference table mapping products to special offer discounts.

- **REQ-124** The business must record which **product**, **special offer** are related, as a **special offer product**.
- **REQ-125** Each special offer product is identified by the combination of **special offer id**, **product id**.
- **REQ-126** Each special offer product carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 21. Store

Customers (resellers) of Adventure Works products.

- **REQ-127** The business must record every **store**. Every store is a **business entity** and is identified by the same **business entity id**.
- **REQ-128** The business must record the **name** of each store: Name of the store.
- **REQ-129** The business must record the **demographics** of each store: Demographic informationg about the store such as the number of employees, annual sales and store type.
- **REQ-130** Each store refers to one **sales person** (by its sales person id).
- **REQ-131** Each store carries a last-changed timestamp and a technical row identifier, which is not a business key.
