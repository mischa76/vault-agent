# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 209 requirement(s) and 23 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (11)

- **hub_customer** — business key `AccountNumber`. Customer (individual person or store), identified by the account number assigned by the accounting system. _(requirements: REQ-003, REQ-004, REQ-005, REQ-057-3)_
- **hub_sales_order** — business key `SalesOrderNumber`. Sales order identified by its unique sales order number. _(requirements: REQ-017, REQ-018, REQ-057-3)_
- **hub_sales_order_line** — business key `sales_order_line`. Sales order line, identified within its order by an incremental line number. _(requirements: REQ-051, REQ-042-2)_
- **hub_sales_territory** — business key `Name`. Sales territory catalogue, keyed on the territory name (decided key). _(requirements: REQ-075, REQ-022, REQ-041-2)_
- **hub_credit_card** — business key `CardNumber`. Register of credit cards used for payment, keyed on card number (decided key); payment-sensitive. _(requirements: REQ-082, REQ-083, REQ-085, REQ-050-3)_
- **hub_currency** — business key `CurrencyCode`. Currency identified by its ISO currency code. _(requirements: REQ-021-2, REQ-022-2)_
- **hub_currency_rate** — business key `currency_rate`. Daily currency exchange rate, identified by from-currency, to-currency and rate date. _(requirements: REQ-023-2, REQ-057-2, REQ-017-3, REQ-018-3)_
- **hub_special_offer** — business key `SpecialOfferID`. Special offer (promotional code) catalogue. _(requirements: REQ-008-2, REQ-058)_
- **hub_sales_reason** — business key `SalesReasonID`. Sales reason catalogue. _(requirements: REQ-062)_
- **hub_sales_tax_rate** — business key `SalesTaxRateID`. Register of sales tax rates. _(requirements: REQ-033-2, REQ-058-2)_
- **hub_shopping_cart_item** — business key `shopping_cart_item`. Shopping cart item, identified within its shopping cart. _(requirements: REQ-001-2, REQ-002-2, REQ-059-2)_

### Links (24)

- **link_customer_person** — connects hub_customer, hub_business_entity (person). Individual customer to the person who is the customer (Customer.PersonID). _(requirements: REQ-006, REQ-002, REQ-050-2, REQ-052-3)_
- **link_customer_store** — connects hub_customer, hub_business_entity (store). Store customer to the store (Customer.StoreID). _(requirements: REQ-007, REQ-050-2)_
- **link_customer_sales_territory** — connects hub_customer, hub_sales_territory. Sales territory in which the customer is located. _(requirements: REQ-008, REQ-010, REQ-049-2, REQ-021-3)_
- **link_store_sales_person** — connects hub_business_entity, hub_business_entity (sales_person). Sales representative assigned to a reseller store (Store.BusinessEntityID as the store side, Store.SalesPersonID as the representative). _(requirements: REQ-014, REQ-051-2, REQ-021-3)_
- **link_sales_person_sales_territory** — connects hub_business_entity (sales_person), hub_sales_territory. Territory the representative is currently assigned to (SalesPerson.TerritoryID). _(requirements: REQ-068, REQ-052-2, REQ-015-3)_
- **link_sales_person_territory_history** — connects hub_business_entity, hub_sales_territory. Dated history of which representative worked which territory (SalesTerritoryHistory). Unit of work: BusinessEntityID + TerritoryID + StartDate. Driving key: hub_business_entity. _(requirements: REQ-009-3, REQ-010-3, REQ-011-3, REQ-012-3, REQ-013-3, REQ-014-3, REQ-053-2)_
- **link_sales_territory_country_region** — connects hub_sales_territory, hub_country_region. Country/region a territory belongs to. _(requirements: REQ-076, REQ-081, REQ-054-2, REQ-002)_
- **link_sales_order_customer** — connects hub_sales_order, hub_customer. Customer who placed the order. _(requirements: REQ-019, REQ-039-2)_
- **link_sales_order_sales_person** — connects hub_sales_order, hub_business_entity (sales_person). Sales representative who created a non-online order. _(requirements: REQ-021, REQ-040-2)_
- **link_sales_order_sales_territory** — connects hub_sales_order, hub_sales_territory. Territory in which the sale was made, as recorded on the order. _(requirements: REQ-022, REQ-023, REQ-041-2)_
- **link_sales_order_bill_to_address** — connects hub_sales_order, hub_address (bill_to). Billing address used for the order. _(requirements: REQ-032, REQ-061-2, REQ-002)_
- **link_sales_order_ship_to_address** — connects hub_sales_order, hub_address (ship_to). Shipping address used for the order. _(requirements: REQ-033, REQ-061-2, REQ-002)_
- **link_sales_order_ship_method** — connects hub_sales_order, hub_ship_method. Shipping method chosen for the order. _(requirements: REQ-034, REQ-062-2, REQ-002)_
- **link_sales_order_credit_card** — connects hub_sales_order, hub_credit_card. Credit card used to pay for the order. _(requirements: REQ-046, REQ-048, REQ-046-2, REQ-089)_
- **link_sales_order_currency_rate** — connects hub_sales_order, hub_currency_rate. Currency exchange rate applied to the order. _(requirements: REQ-049, REQ-050, REQ-026-2, REQ-048-2)_
- **link_sales_order_line** — connects hub_sales_order_line, hub_sales_order, hub_product, hub_special_offer. Order line within its order, the product sold and the special offer applied. Unit of work: SalesOrderID + SalesOrderDetailID + ProductID + SpecialOfferID. _(requirements: REQ-051, REQ-052, REQ-058, REQ-042-2, REQ-043-2, REQ-044-2, REQ-002)_
- **link_sales_order_sales_reason** — connects hub_sales_order, hub_sales_reason. Sales reasons recorded against an order (many-to-many). _(requirements: REQ-063, REQ-064, REQ-045-2)_
- **link_person_credit_card** — connects hub_business_entity (person), hub_credit_card. Credit cards registered to persons (many-to-many). _(requirements: REQ-087, REQ-088, REQ-047-2)_
- **link_special_offer_product** — connects hub_special_offer, hub_product. Products each special offer applies to (many-to-many). _(requirements: REQ-018-2, REQ-019-2, REQ-055-2, REQ-020-2)_
- **link_currency_rate_currency** — connects hub_currency_rate, hub_currency (from), hub_currency (to). Currency converted from and currency converted to by an exchange rate. _(requirements: REQ-023-2, REQ-057-2)_
- **link_country_region_currency** — connects hub_country_region, hub_currency. Currencies used in countries/regions (many-to-many). _(requirements: REQ-030-2, REQ-031-2, REQ-056-2, REQ-032-2)_
- **link_sales_tax_rate_state_province** — connects hub_sales_tax_rate, hub_state_province. State/province a sales tax rate applies to. _(requirements: REQ-034-2, REQ-058-2, REQ-002)_
- **link_shopping_cart_item_product** — connects hub_shopping_cart_item, hub_product. Product for each shopping cart item. _(requirements: REQ-003-2, REQ-006-2, REQ-059-2)_
- **link_sales_order_line_product** — connects hub_sales_order_line, hub_product. Declared foreign key SalesOrderDetail.ProductID references PRODUCTNUMBER; ratified from the source catalogue (WP34). _(requirements: —)_

### Satellites (25)

- **sat_customer_details** — on hub_customer; payload: rowguid, ModifiedDate. Customer record change tracking and technical trace. Source table: Customer. _(requirements: REQ-009, REQ-022-3, REQ-056-3)_
- **sat_business_entity_store_details** — on hub_business_entity; payload: Name, rowguid, ModifiedDate. Store name and change tracking. Source table: Store. Split rationale: Non-confidential store descriptors split from confidential demographics.. _(requirements: REQ-012, REQ-013)_
- **sat_business_entity_store_demographics** — on hub_business_entity; payload: Demographics. Store demographics (employees, annual sales, store type); confidential. Source table: Store. Split rationale: Commercially confidential classification.. _(requirements: REQ-015, REQ-016, REQ-055-3, REQ-038-3, REQ-021-3)_
- **sat_business_entity_sales_person_compensation** — on hub_business_entity; payload: SalesQuota, Bonus, CommissionPct. Representative current quota, bonus and commission; remuneration data, access-restricted. Source table: SalesPerson. Split rationale: Remuneration terms change rarely; restricted classification.. _(requirements: REQ-069, REQ-070, REQ-071, REQ-054-3, REQ-006-3)_
- **sat_business_entity_sales_person_performance** — on hub_business_entity; payload: SalesYTD, SalesLastYear, rowguid, ModifiedDate. Representative running sales totals maintained by the operational system. Source table: SalesPerson. Split rationale: Running totals change frequently, unlike compensation terms.. _(requirements: REQ-072, REQ-073, REQ-047-3, REQ-054-3)_
- **sat_business_entity_sales_quota_history** — on hub_business_entity; payload: SalesQuota, rowguid, ModifiedDate. Dated sales quota history per representative. Multi-active satellite, child dependent key: QuotaDate. Source table: SalesPersonQuotaHistory. _(requirements: REQ-001-3, REQ-002-3, REQ-003-3, REQ-004-3, REQ-005-3, REQ-054-3)_
- **sat_sales_person_territory_history_effectivity** — on link_sales_person_territory_history; payload: StartDate, EndDate. Active period of a representative's territory assignment; open-ended while current. Effectivity satellite. Source table: SalesTerritoryHistory. _(requirements: REQ-009-3, REQ-010-3, REQ-011-3, REQ-012-3, REQ-014-3, REQ-045-3, REQ-046-3)_
- **sat_sales_territory_details** — on hub_sales_territory; payload: Group, rowguid, ModifiedDate. Territory geographic group. Source table: SalesTerritory. _(requirements: REQ-077, REQ-081, REQ-021-3)_
- **sat_sales_territory_financials** — on hub_sales_territory; payload: SalesYTD, SalesLastYear, CostYTD, CostLastYear. Territory running sales and cost totals. Source table: SalesTerritory. Split rationale: Running totals change far more often than descriptive data.. _(requirements: REQ-078, REQ-079, REQ-080, REQ-030-3, REQ-047-3)_
- **sat_sales_order_details** — on hub_sales_order; payload: RevisionNumber, OrderDate, DueDate, ShipDate, Status, OnlineOrderFlag, PurchaseOrderNumber, AccountNumber, Comment, rowguid, ModifiedDate. Order dates, status, channel, references and comments. Source table: SalesOrderHeader. _(requirements: REQ-020, REQ-024, REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-030, REQ-031, REQ-035, REQ-037, REQ-038)_
- **sat_sales_order_amounts** — on hub_sales_order; payload: SubTotal, TaxAmt, Freight, TotalDue. Order financial amounts. Source table: SalesOrderHeader. Split rationale: Financial measures grouped separately from descriptive order data.. _(requirements: REQ-039, REQ-040, REQ-041, REQ-042, REQ-043, REQ-044, REQ-045, REQ-041-3)_
- **sat_sales_order_payment** — on hub_sales_order; payload: CreditCardApprovalCode. Credit card approval code; payment-sensitive. Source table: SalesOrderHeader. Split rationale: Payment-sensitive classification.. _(requirements: REQ-047, REQ-050-3)_
- **sat_sales_order_line_details** — on hub_sales_order_line; payload: CarrierTrackingNumber, OrderQty, UnitPrice, UnitPriceDiscount, LineTotal, rowguid, ModifiedDate. Order line quantity, price, discount, line total and tracking number. Source table: SalesOrderDetail. _(requirements: REQ-053, REQ-054, REQ-055, REQ-056, REQ-057, REQ-059, REQ-060, REQ-061, REQ-042-3)_
- **sat_sales_order_sales_reason_details** — on link_sales_order_sales_reason; payload: ModifiedDate. Change tracking for order sales reasons. Source table: SalesOrderHeaderSalesReason. _(requirements: REQ-022-3)_
- **sat_sales_reason_details** — on hub_sales_reason; payload: Name, ReasonType, ModifiedDate. Sales reason description and category. Source table: SalesReason. _(requirements: REQ-062, REQ-065)_
- **sat_credit_card_details** — on hub_credit_card; payload: CardType, ModifiedDate. Card type. Source table: CreditCard. _(requirements: REQ-083, REQ-084)_
- **sat_credit_card_sensitive** — on hub_credit_card; payload: ExpMonth, ExpYear. Card expiry data; payment-sensitive, access-restricted. Source table: CreditCard. Split rationale: Sensitive payment classification.. _(requirements: REQ-083, REQ-085, REQ-050-3, REQ-051-3)_
- **sat_person_credit_card_details** — on link_person_credit_card; payload: ModifiedDate. Change tracking for person-card association. Source table: PersonCreditCard. _(requirements: REQ-022-3)_
- **sat_currency_details** — on hub_currency; payload: Name, ModifiedDate. Currency name. Source table: Currency. _(requirements: REQ-021-2, REQ-022-2)_
- **sat_currency_rate_details** — on hub_currency_rate; payload: AverageRate, EndOfDayRate, ModifiedDate. Average and end-of-day exchange rates. Source table: CurrencyRate. _(requirements: REQ-024-2, REQ-025-2, REQ-028-2, REQ-018-3)_
- **sat_country_region_currency_details** — on link_country_region_currency; payload: ModifiedDate. Change tracking for country/region currency association. Source table: CountryRegionCurrency. _(requirements: REQ-022-3)_
- **sat_special_offer_details** — on hub_special_offer; payload: Description, DiscountPct, Type, Category, StartDate, EndDate, MinQty, MaxQty, rowguid, ModifiedDate. Special offer description, discount terms and validity period. Source table: SpecialOffer. _(requirements: REQ-008-2, REQ-009-2, REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-014-2, REQ-015-2, REQ-016-2, REQ-019-3, REQ-020-3, REQ-021-3)_
- **sat_special_offer_product_details** — on link_special_offer_product; payload: rowguid, ModifiedDate. Change tracking for offer-product coverage. Source table: SpecialOfferProduct. _(requirements: REQ-022-3)_
- **sat_sales_tax_rate_details** — on hub_sales_tax_rate; payload: Name, TaxType, TaxRate, rowguid, ModifiedDate. Tax rate description, type and amount. Source table: SalesTaxRate. _(requirements: REQ-033-2, REQ-035-2, REQ-036-2, REQ-037-2, REQ-038-2)_
- **sat_shopping_cart_item_details** — on hub_shopping_cart_item; payload: Quantity, DateCreated, ModifiedDate. Cart item quantity and creation time. Source table: ShoppingCartItem. _(requirements: REQ-004-2, REQ-005-2, REQ-007-2, REQ-039-3)_

### Hub keys decided before modelling (3)

- **CreditCard** — key `CardNumber`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `CreditCardID` (0.60); primary key `CreditCardID`.
- **Currency** — key `CurrencyCode`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `CurrencyCode` (0.95); primary key `CurrencyCode`.
- **SalesTerritory** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `TerritoryID` (0.55); primary key `TerritoryID`.

### Source mappings (87)

Where each modelled concept's values come from (ADR-0008). The category is the deterministic confidence tier; `accepted` / `overridden` mark a human decision, `proposed` still awaits one.

- `AccountNumber` → `Customer`.`AccountNumber` — exact_name, accepted
- `SalesOrderNumber` → `SalesOrderHeader`.`SalesOrderNumber` — exact_name, accepted
- `sales_order_line` → `SalesOrderDetail`.`SalesOrderDetailID` — llm_semantic, accepted
- `Name` → `SalesTerritory`.`Name` — exact_name, accepted
- `CardNumber` → `CreditCard`.`CardNumber` — exact_name, accepted
- `CurrencyCode` → `Currency`.`CurrencyCode` — exact_name, accepted
- `currency_rate` → `CurrencyRate`.`CurrencyRateID` — llm_semantic, accepted
- `SpecialOfferID` → `SpecialOffer`.`SpecialOfferID` — exact_name, accepted
- `SalesReasonID` → `SalesReason`.`SalesReasonID` — exact_name, accepted
- `SalesTaxRateID` → `SalesTaxRate`.`SalesTaxRateID` — exact_name, accepted
- `shopping_cart_item` → `ShoppingCartItem`.`ShoppingCartItemID` — llm_semantic, accepted
- `rowguid` → `Customer`.`rowguid` — exact_name, accepted
- `ModifiedDate` → `Customer`.`ModifiedDate` — exact_name, accepted
- `Name` → `Store`.`Name` — exact_name, accepted
- `Demographics` → `Store`.`Demographics` — exact_name, accepted
- `SalesQuota` → `SalesPerson`.`SalesQuota` — exact_name, accepted
- `Bonus` → `SalesPerson`.`Bonus` — exact_name, accepted
- `CommissionPct` → `SalesPerson`.`CommissionPct` — exact_name, accepted
- `SalesYTD` → `SalesPerson`.`SalesYTD` — exact_name, accepted
- `SalesLastYear` → `SalesPerson`.`SalesLastYear` — exact_name, accepted
- `StartDate` → `SalesTerritoryHistory`.`StartDate` — exact_name, accepted
- `EndDate` → `SalesTerritoryHistory`.`EndDate` — exact_name, accepted
- `Group` → `SalesTerritory`.`Group` — exact_name, accepted
- `rowguid` → `SalesTerritory`.`rowguid` — exact_name, accepted
- `ModifiedDate` → `SalesTerritory`.`ModifiedDate` — exact_name, accepted
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
- `rowguid` → `SalesOrderHeader`.`rowguid` — exact_name, accepted
- `ModifiedDate` → `SalesOrderHeader`.`ModifiedDate` — exact_name, accepted
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
- `rowguid` → `SalesOrderDetail`.`rowguid` — exact_name, accepted
- `ModifiedDate` → `SalesOrderDetail`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `SalesOrderHeaderSalesReason`.`ModifiedDate` — exact_name, accepted
- `Name` → `SalesReason`.`Name` — exact_name, accepted
- `ReasonType` → `SalesReason`.`ReasonType` — exact_name, accepted
- `ModifiedDate` → `SalesReason`.`ModifiedDate` — exact_name, accepted
- `CardType` → `CreditCard`.`CardType` — exact_name, accepted
- `ModifiedDate` → `CreditCard`.`ModifiedDate` — exact_name, accepted
- `ExpMonth` → `CreditCard`.`ExpMonth` — exact_name, accepted
- `ExpYear` → `CreditCard`.`ExpYear` — exact_name, accepted
- `ModifiedDate` → `PersonCreditCard`.`ModifiedDate` — exact_name, accepted
- `Name` → `Currency`.`Name` — exact_name, accepted
- `ModifiedDate` → `Currency`.`ModifiedDate` — exact_name, accepted
- `AverageRate` → `CurrencyRate`.`AverageRate` — exact_name, accepted
- `EndOfDayRate` → `CurrencyRate`.`EndOfDayRate` — exact_name, accepted
- `ModifiedDate` → `CurrencyRate`.`ModifiedDate` — exact_name, accepted
- `ModifiedDate` → `CountryRegionCurrency`.`ModifiedDate` — exact_name, accepted
- `Description` → `SpecialOffer`.`Description` — exact_name, accepted
- `DiscountPct` → `SpecialOffer`.`DiscountPct` — exact_name, accepted
- `Type` → `SpecialOffer`.`Type` — exact_name, accepted
- `Category` → `SpecialOffer`.`Category` — exact_name, accepted
- `StartDate` → `SpecialOffer`.`StartDate` — exact_name, accepted
- `EndDate` → `SpecialOffer`.`EndDate` — exact_name, accepted
- `MinQty` → `SpecialOffer`.`MinQty` — exact_name, accepted
- `MaxQty` → `SpecialOffer`.`MaxQty` — exact_name, accepted
- `rowguid` → `SpecialOffer`.`rowguid` — exact_name, accepted
- `ModifiedDate` → `SpecialOffer`.`ModifiedDate` — exact_name, accepted
- `rowguid` → `SpecialOfferProduct`.`rowguid` — exact_name, accepted
- `ModifiedDate` → `SpecialOfferProduct`.`ModifiedDate` — exact_name, accepted
- `Name` → `SalesTaxRate`.`Name` — exact_name, accepted
- `TaxType` → `SalesTaxRate`.`TaxType` — exact_name, accepted
- `TaxRate` → `SalesTaxRate`.`TaxRate` — exact_name, accepted
- `rowguid` → `SalesTaxRate`.`rowguid` — exact_name, accepted
- `ModifiedDate` → `SalesTaxRate`.`ModifiedDate` — exact_name, accepted
- `Quantity` → `ShoppingCartItem`.`Quantity` — exact_name, accepted
- `DateCreated` → `ShoppingCartItem`.`DateCreated` — exact_name, accepted
- `ModifiedDate` → `ShoppingCartItem`.`ModifiedDate` — exact_name, accepted

Unresolved — the mapper could not decide (2): hub_business_entity::rowguid, hub_business_entity::ModifiedDate.

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261115T083836408464Z`) carrying 29 hub(s), 29 link(s) and 65 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

122 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/sales_requirements.md
- Generated dbt models: 183 raw-vault model(s) + 256 staging model(s) (see `state.artifacts`)
