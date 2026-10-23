# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-10-23
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 197 requirement(s) and 20 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (11)

- **hub_customer** — business key `AccountNumber`. A customer (individual person or store), identified by the customer account number assigned by the accounting system. _(requirements: REQ-003, REQ-004, REQ-050-2, REQ-054-3)_
- **hub_sales_order** — business key `SalesOrderNumber`. A sales order, identified by its unique sales order number. _(requirements: REQ-016, REQ-001, REQ-054-3)_
- **hub_sales_order_line** — business key `sales_order_line`. A sales order line, identified within its order by an incremental line number. _(requirements: REQ-044, REQ-042-2)_
- **hub_sales_territory** — business key `TerritoryID`. A sales territory in the territory catalogue. _(requirements: REQ-067, REQ-054-2)_
- **hub_credit_card** — business key `CreditCardID`. A credit card in the payment card register, identified by its operational card record. _(requirements: REQ-074)_
- **hub_currency** — business key `CurrencyCode`. A currency identified by its ISO currency code. _(requirements: REQ-021-2)_
- **hub_currency_rate** — business key `currency_rate`. A daily currency exchange rate, identified by rate date, from-currency and to-currency. _(requirements: REQ-023-2, REQ-057-2, REQ-019-3, REQ-020-3)_
- **hub_special_offer** — business key `SpecialOfferID`. A special offer (promotion) in the offer catalogue. _(requirements: REQ-008-2, REQ-050)_
- **hub_sales_reason** — business key `SalesReasonID`. A sales reason in the sales reason catalogue. _(requirements: REQ-054)_
- **hub_shopping_cart_item** — business key `shopping_cart_item`. A shopping cart item, identified within its shopping cart. _(requirements: REQ-001-2, REQ-002-2, REQ-059-2)_
- **hub_sales_tax_rate** — business key `sales_tax_rate`. A sales tax rate for a jurisdiction and tax type. _(requirements: REQ-033-2, REQ-058-2)_

### Links (20)

- **link_customer_person** — connects hub_customer, hub_business_entity (person). An individual customer and the person who is the customer. _(requirements: REQ-005, REQ-004, REQ-050-2, REQ-002)_
- **link_customer_store** — connects hub_customer, hub_business_entity (store). A store customer and the store it represents. _(requirements: REQ-006, REQ-004, REQ-050-2)_
- **link_customer_sales_territory** — connects hub_customer, hub_sales_territory. The sales territory in which a customer is located. _(requirements: REQ-007, REQ-009, REQ-049-2, REQ-023-3)_
- **link_store_sales_person** — connects hub_business_entity (store), hub_business_entity (sales_person). The sales representative assigned to a reseller store. _(requirements: REQ-013, REQ-051-2, REQ-023-3, REQ-037-3)_
- **link_sales_person_sales_territory** — connects hub_business_entity (sales_person), hub_sales_territory. The territory a sales representative is currently assigned to (from the representative record). _(requirements: REQ-060, REQ-052-2, REQ-016-3)_
- **link_sales_person_territory_history** — connects hub_business_entity (sales_person), hub_sales_territory. Dated history of territory assignments per sales representative. Driving key: hub_business_entity (sales_person). _(requirements: REQ-053-2, REQ-009-3, REQ-010-3, REQ-011-3, REQ-012-3, REQ-014-3, REQ-015-3)_
- **link_sales_territory_country_region** — connects hub_sales_territory, hub_country_region. The country/region a sales territory belongs to. _(requirements: REQ-068, REQ-054-2, REQ-073)_
- **link_sales_order** — connects hub_sales_order, hub_customer, hub_business_entity (sales_person), hub_sales_territory, hub_address (bill_to), hub_address (ship_to), hub_ship_method, hub_credit_card, hub_currency_rate. The sales order header event: the order with its customer, representative, territory, billing and shipping addresses, ship method, credit card and currency rate. Unit of work: SalesOrderNumber with CustomerID, SalesPersonID, TerritoryID, BillToAddressID, ShipToAddressID, ShipMethodID, CreditCardID, CurrencyRateID. _(requirements: REQ-017, REQ-019, REQ-020, REQ-028, REQ-029, REQ-030, REQ-039, REQ-042, REQ-039-2, REQ-040-2, REQ-041-2, REQ-046-2, REQ-048-2, REQ-061-2, REQ-062-2, REQ-002)_
- **link_sales_order_line** — connects hub_sales_order_line, hub_sales_order, hub_product, hub_special_offer. An order line within its order, selling one product under a special offer. Unit of work: SalesOrderID, SalesOrderDetailID, ProductID, SpecialOfferID. _(requirements: REQ-045, REQ-050, REQ-042-2, REQ-043-2, REQ-044-2, REQ-020-2)_
- **link_sales_order_sales_reason** — connects hub_sales_order, hub_sales_reason. Sales reasons cited on an order (many-to-many). _(requirements: REQ-056, REQ-045-2, REQ-057, REQ-058)_
- **link_business_entity_credit_card** — connects hub_business_entity, hub_credit_card. Credit cards registered to persons (many-to-many). _(requirements: REQ-079, REQ-047-2, REQ-080)_
- **link_currency_rate_currency** — connects hub_currency_rate, hub_currency (from), hub_currency (to). The from- and to-currency of an exchange rate. _(requirements: REQ-023-2, REQ-057-2)_
- **link_country_region_currency** — connects hub_country_region, hub_currency. Currencies used in countries/regions (many-to-many). _(requirements: REQ-030-2, REQ-031-2, REQ-056-2, REQ-032-2)_
- **link_sales_tax_rate_state_province** — connects hub_sales_tax_rate, hub_state_province. The state/province jurisdiction a tax rate applies to. _(requirements: REQ-034-2, REQ-058-2, REQ-037-2)_
- **link_special_offer_product** — connects hub_special_offer, hub_product. Products covered by a special offer (many-to-many). _(requirements: REQ-018-2, REQ-019-2, REQ-055-2, REQ-020-2)_
- **link_shopping_cart_item_product** — connects hub_shopping_cart_item, hub_product. The product in a shopping cart item. _(requirements: REQ-003-2, REQ-059-2, REQ-006-2)_
- **link_sales_order_line_product** — connects hub_sales_order_line, hub_product. Declared foreign key SalesOrderDetail.ProductID references PRODUCTID; ratified from the source catalogue (WP34). _(requirements: —)_
- **link_sales_order_address** — connects hub_sales_order, hub_address. Declared foreign key SalesOrderHeader.BillToAddressID references ADDRESSID; ratified from the source catalogue (WP34). _(requirements: —)_
- **link_sales_order_business_entity** — connects hub_sales_order, hub_business_entity. Declared foreign key SalesOrderHeader.SalesPersonID references BUSINESSENTITYID; ratified from the source catalogue (WP34). _(requirements: —)_
- **link_sales_order_ship_method** — connects hub_sales_order, hub_ship_method. Declared foreign key SalesOrderHeader.ShipMethodID references SHIPMETHODID; ratified from the source catalogue (WP34). _(requirements: —)_

### Satellites (23)

- **sat_customer_details** — on hub_customer; payload: ModifiedDate, rowguid. Customer record technical trace and last-modified date for reconciliation. Source table: Customer. _(requirements: REQ-008, REQ-024-3, REQ-053-3)_
- **sat_business_entity_store_details** — on hub_business_entity; payload: Name, ModifiedDate, rowguid. Store name and change tracking. Source table: Store. Split rationale: Non-confidential store descriptors separated from confidential demographics.. _(requirements: REQ-012, REQ-024-3)_
- **sat_business_entity_store_demographics** — on hub_business_entity; payload: Demographics. Confidential store demographics (employees, annual sales, store type). Source table: Store. Split rationale: Commercially sensitive classification.. _(requirements: REQ-014, REQ-015, REQ-052-3, REQ-023-3)_
- **sat_business_entity_sales_person_compensation** — on hub_business_entity; payload: SalesQuota, Bonus, CommissionPct. Current quota, bonus and commission of a sales representative (remuneration data, restricted). Source table: SalesPerson. Split rationale: Remuneration data, restricted access, changes rarely.. _(requirements: REQ-061, REQ-062, REQ-063, REQ-006-3, REQ-051-3)_
- **sat_business_entity_sales_person_performance** — on hub_business_entity; payload: SalesYTD, SalesLastYear, ModifiedDate, rowguid. Operational running sales totals of a representative. Source table: SalesPerson. Split rationale: Running totals change frequently.. _(requirements: REQ-064, REQ-065, REQ-046-3, REQ-051-3)_
- **sat_business_entity_sales_quota_history** — on hub_business_entity; payload: SalesQuota, ModifiedDate, rowguid. Dated sales quota history per representative. Multi-active satellite, child dependent key: QuotaDate. Source table: SalesPersonQuotaHistory. _(requirements: REQ-001-3, REQ-002-3, REQ-003-3, REQ-004-3, REQ-005-3, REQ-008-3, REQ-051-3)_
- **sat_sales_person_territory_history_effectivity** — on link_sales_person_territory_history; payload: StartDate, EndDate. Active period of each representative territory assignment; open-ended while active. Effectivity satellite. Source table: SalesTerritoryHistory. _(requirements: REQ-009-3, REQ-010-3, REQ-011-3, REQ-012-3, REQ-013-3, REQ-015-3, REQ-044-3, REQ-045-3)_
- **sat_sales_territory_details** — on hub_sales_territory; payload: Name, Group, ModifiedDate, rowguid. Territory name and geographic group. Source table: SalesTerritory. Split rationale: Slow-changing descriptors separated from running financials.. _(requirements: REQ-067, REQ-069, REQ-073, REQ-023-3)_
- **sat_sales_territory_financials** — on hub_sales_territory; payload: SalesYTD, SalesLastYear, CostYTD, CostLastYear. Territory year-to-date and previous-year sales and costs. Source table: SalesTerritory. Split rationale: Running totals change frequently.. _(requirements: REQ-070, REQ-071, REQ-072, REQ-031-3, REQ-046-3)_
- **sat_sales_order_details** — on hub_sales_order; payload: RevisionNumber, OrderDate, DueDate, ShipDate, Status, OnlineOrderFlag, PurchaseOrderNumber, AccountNumber, Comment, ModifiedDate, rowguid. Order dates, status, channel, references, comments and revision. Source table: SalesOrderHeader. _(requirements: REQ-018, REQ-021, REQ-022, REQ-023, REQ-024, REQ-025, REQ-026, REQ-027, REQ-031, REQ-033, REQ-033-3, REQ-034-3)_
- **sat_sales_order_totals** — on hub_sales_order; payload: SubTotal, TaxAmt, Freight, TotalDue. Order financial amounts as computed by the source. Source table: SalesOrderHeader. Split rationale: Financial measures grouped separately from descriptive order data.. _(requirements: REQ-034, REQ-035, REQ-036, REQ-037, REQ-038, REQ-040-3, REQ-054-3)_
- **sat_sales_order_payment** — on hub_sales_order; payload: CreditCardApprovalCode. Payment approval code for reconciliation and disputes. Source table: SalesOrderHeader. Split rationale: Payment-sensitive classification.. _(requirements: REQ-040, REQ-049-3)_
- **sat_sales_order_line_details** — on hub_sales_order_line; payload: CarrierTrackingNumber, OrderQty, UnitPrice, UnitPriceDiscount, LineTotal, ModifiedDate, rowguid. Order line quantity, pricing, discount, line total and tracking number. Source table: SalesOrderDetail. _(requirements: REQ-046, REQ-047, REQ-048, REQ-049, REQ-051, REQ-052, REQ-053, REQ-041-3)_
- **sat_credit_card_details** — on hub_credit_card; payload: CardType, ModifiedDate. Card type of a credit card. Source table: CreditCard. Split rationale: Non-restricted card attributes.. _(requirements: REQ-075, REQ-076)_
- **sat_credit_card_sensitive** — on hub_credit_card; payload: CardNumber, ExpMonth, ExpYear. Restricted card number and expiry data. Source table: CreditCard. Split rationale: Sensitive payment data, restricted access.. _(requirements: REQ-075, REQ-077, REQ-078, REQ-049-3)_
- **sat_currency_details** — on hub_currency; payload: Name, ModifiedDate. Currency name. Source table: Currency. _(requirements: REQ-021-2, REQ-022-2)_
- **sat_currency_rate_details** — on hub_currency_rate; payload: AverageRate, EndOfDayRate, ModifiedDate. Average and end-of-day exchange rates. Source table: CurrencyRate. _(requirements: REQ-024-2, REQ-025-2, REQ-026-2, REQ-028-2)_
- **sat_special_offer_details** — on hub_special_offer; payload: Description, Type, Category, MinQty, MaxQty, ModifiedDate, rowguid. Special offer description, type, category and quantity thresholds. Source table: SpecialOffer. _(requirements: REQ-008-2, REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-017-2)_
- **sat_special_offer_discount** — on hub_special_offer; payload: DiscountPct. Discount percentage of a special offer, tracked over time. Source table: SpecialOffer. Split rationale: Commercially significant attribute whose change history is required.. _(requirements: REQ-009-2, REQ-023-3)_
- **sat_special_offer_validity** — on hub_special_offer; payload: StartDate, EndDate. Validity period of a special offer. Source table: SpecialOffer. _(requirements: REQ-014-2, REQ-015-2, REQ-016-2, REQ-021-3, REQ-022-3, REQ-042-3)_
- **sat_sales_reason_details** — on hub_sales_reason; payload: Name, ReasonType, ModifiedDate. Sales reason description and reason category. Source table: SalesReason. _(requirements: REQ-054, REQ-055, REQ-057)_
- **sat_sales_tax_rate_details** — on hub_sales_tax_rate; payload: Name, TaxRate, ModifiedDate, rowguid. Tax rate description and amount. Source table: SalesTaxRate. _(requirements: REQ-033-2, REQ-035-2, REQ-036-2, REQ-038-2)_
- **sat_shopping_cart_item_details** — on hub_shopping_cart_item; payload: Quantity, DateCreated, ModifiedDate. Cart item quantity and creation timestamp. Source table: ShoppingCartItem. _(requirements: REQ-004-2, REQ-005-2, REQ-006-2, REQ-007-2, REQ-038-3)_

### Source mappings (83)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `AccountNumber` → `Customer`.`AccountNumber` — exact_name, accepted
- `SalesOrderNumber` → `SalesOrderHeader`.`SalesOrderNumber` — exact_name, accepted
- `sales_order_line` → `SalesOrderDetail`.`SalesOrderDetailID` — llm_semantic, accepted
- `TerritoryID` → `SalesTerritory`.`TerritoryID` — exact_name, accepted
- `CreditCardID` → `CreditCard`.`CreditCardID` — exact_name, accepted
- `CurrencyCode` → `Currency`.`CurrencyCode` — exact_name, accepted
- `currency_rate` → `CurrencyRate`.`CurrencyRateID` — llm_semantic, accepted
- `SpecialOfferID` → `SpecialOffer`.`SpecialOfferID` — exact_name, accepted
- `SalesReasonID` → `SalesReason`.`SalesReasonID` — exact_name, accepted
- `shopping_cart_item` → `ShoppingCartItem`.`ShoppingCartItemID` — llm_semantic, accepted
- `sales_tax_rate` → `SalesTaxRate`.`SalesTaxRateID` — llm_semantic, accepted
- `ModifiedDate` → `Customer`.`ModifiedDate` — exact_name, accepted
- `rowguid` → `Customer`.`rowguid` — exact_name, accepted
- `Name` → `Store`.`Name` — exact_name, accepted
- `Demographics` → `Store`.`Demographics` — exact_name, accepted
- `SalesQuota` → `SalesPerson`.`SalesQuota` — exact_name, accepted
- `Bonus` → `SalesPerson`.`Bonus` — exact_name, accepted
- `CommissionPct` → `SalesPerson`.`CommissionPct` — exact_name, accepted
- `SalesYTD` → `SalesPerson`.`SalesYTD` — exact_name, accepted
- `SalesLastYear` → `SalesPerson`.`SalesLastYear` — exact_name, accepted
- `StartDate` → `SalesTerritoryHistory`.`StartDate` — exact_name, accepted
- `EndDate` → `SalesTerritoryHistory`.`EndDate` — exact_name, accepted
- `Name` → `SalesTerritory`.`Name` — exact_name, accepted
- `Group` → `SalesTerritory`.`Group` — exact_name, accepted
- `ModifiedDate` → `SalesTerritory`.`ModifiedDate` — exact_name, accepted
- `rowguid` → `SalesTerritory`.`rowguid` — exact_name, accepted
- `SalesYTD` → `SalesTerritory`.`SalesYTD` — exact_name, accepted
- `SalesLastYear` → `SalesTerritory`.`SalesLastYear` — exact_name, accepted
- `CostYTD` → `SalesTerritory`.`CostYTD` — exact_name, accepted
- `CostLastYear` → `SalesTerritory`.`CostLastYear` — exact_name, accepted
- `RevisionNumber` → `SalesOrderHeader`.`RevisionNumber` — exact_name, accepted
- `OrderDate` → `SalesOrderHeader`.`OrderDate` — exact_name, accepted
- `DueDate` → `SalesOrderHeader`.`DueDate` — exact_name, accepted
- `ShipDate` → `SalesOrderHeader`.`ShipDate` — exact_name, accepted
- `Status` → `SalesOrderHeader`.`Status` — exact_name, accepted
- `OnlineOrderFlag` → `SalesOrderHeader`.`OnlineOrderFlag` — exact_name, accepted
- `PurchaseOrderNumber` → `SalesOrderHeader`.`PurchaseOrderNumber` — exact_name, accepted
- `AccountNumber` → `SalesOrderHeader`.`AccountNumber` — exact_name, accepted
- `Comment` → `SalesOrderHeader`.`Comment` — exact_name, accepted
- `ModifiedDate` → `SalesOrderHeader`.`ModifiedDate` — exact_name, accepted
- `rowguid` → `SalesOrderHeader`.`rowguid` — exact_name, accepted
- `SubTotal` → `SalesOrderHeader`.`SubTotal` — exact_name, accepted
- `TaxAmt` → `SalesOrderHeader`.`TaxAmt` — exact_name, accepted
- `Freight` → `SalesOrderHeader`.`Freight` — exact_name, accepted
- `TotalDue` → `SalesOrderHeader`.`TotalDue` — exact_name, accepted
- `CreditCardApprovalCode` → `SalesOrderHeader`.`CreditCardApprovalCode` — exact_name, accepted
- `CarrierTrackingNumber` → `SalesOrderDetail`.`CarrierTrackingNumber` — exact_name, accepted
- `OrderQty` → `SalesOrderDetail`.`OrderQty` — exact_name, accepted
- `UnitPrice` → `SalesOrderDetail`.`UnitPrice` — exact_name, accepted
- `UnitPriceDiscount` → `SalesOrderDetail`.`UnitPriceDiscount` — exact_name, accepted
- `LineTotal` → `SalesOrderDetail`.`LineTotal` — exact_name, accepted
- `ModifiedDate` → `SalesOrderDetail`.`ModifiedDate` — exact_name, accepted
- `rowguid` → `SalesOrderDetail`.`rowguid` — exact_name, accepted
- `CardType` → `CreditCard`.`CardType` — exact_name, accepted
- `ModifiedDate` → `CreditCard`.`ModifiedDate` — exact_name, accepted
- `CardNumber` → `CreditCard`.`CardNumber` — exact_name, accepted
- `ExpMonth` → `CreditCard`.`ExpMonth` — exact_name, accepted
- `ExpYear` → `CreditCard`.`ExpYear` — exact_name, accepted
- `Name` → `Currency`.`Name` — exact_name, accepted
- `ModifiedDate` → `Currency`.`ModifiedDate` — exact_name, accepted
- `AverageRate` → `CurrencyRate`.`AverageRate` — exact_name, accepted
- `EndOfDayRate` → `CurrencyRate`.`EndOfDayRate` — exact_name, accepted
- `ModifiedDate` → `CurrencyRate`.`ModifiedDate` — exact_name, accepted
- `Description` → `SpecialOffer`.`Description` — exact_name, accepted
- `Type` → `SpecialOffer`.`Type` — exact_name, accepted
- `Category` → `SpecialOffer`.`Category` — exact_name, accepted
- `MinQty` → `SpecialOffer`.`MinQty` — exact_name, accepted
- `MaxQty` → `SpecialOffer`.`MaxQty` — exact_name, accepted
- `ModifiedDate` → `SpecialOffer`.`ModifiedDate` — exact_name, accepted
- `rowguid` → `SpecialOffer`.`rowguid` — exact_name, accepted
- `DiscountPct` → `SpecialOffer`.`DiscountPct` — exact_name, accepted
- `StartDate` → `SpecialOffer`.`StartDate` — exact_name, accepted
- `EndDate` → `SpecialOffer`.`EndDate` — exact_name, accepted
- `Name` → `SalesReason`.`Name` — exact_name, accepted
- `ReasonType` → `SalesReason`.`ReasonType` — exact_name, accepted
- `ModifiedDate` → `SalesReason`.`ModifiedDate` — exact_name, accepted
- `Name` → `SalesTaxRate`.`Name` — exact_name, accepted
- `TaxRate` → `SalesTaxRate`.`TaxRate` — exact_name, accepted
- `ModifiedDate` → `SalesTaxRate`.`ModifiedDate` — exact_name, accepted
- `rowguid` → `SalesTaxRate`.`rowguid` — exact_name, accepted
- `Quantity` → `ShoppingCartItem`.`Quantity` — exact_name, accepted
- `DateCreated` → `ShoppingCartItem`.`DateCreated` — exact_name, accepted
- `ModifiedDate` → `ShoppingCartItem`.`ModifiedDate` — exact_name, accepted

Unresolved — the mapper could not decide (2): hub_business_entity::ModifiedDate, hub_business_entity::rowguid.

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261022T234118699534Z`) carrying 29 hub(s), 27 link(s) and 67 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

122 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/sales_requirements.md
- Generated dbt models: 177 raw-vault model(s) + 159 staging model(s) (see `state.artifacts`)
