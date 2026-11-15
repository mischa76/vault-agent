# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-11-15
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 203 requirement(s) and 19 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (11)

- **hub_customer** — business key `AccountNumber`. Customer (individual person or reseller store), identified by the account number assigned by the accounting system. _(requirements: REQ-001, REQ-002, REQ-007, REQ-047-3)_
- **hub_sales_order** — business key `SalesOrderNumber`. Sales order, identified by its unique sales order number. _(requirements: REQ-016, REQ-047-3)_
- **hub_sales_order_line** — business key `sales_order_line`. Sales order line, identified within its order by an incremental line number. _(requirements: REQ-044, REQ-045, REQ-047-2)_
- **hub_sales_territory** — business key `Name`. Sales territory from the territory catalogue, keyed on territory name (decided key). _(requirements: REQ-068)_
- **hub_credit_card** — business key `CardNumber`. Credit card used for payment, keyed on card number (decided key); payment-sensitive. _(requirements: REQ-075, REQ-076, REQ-078, REQ-041-3)_
- **hub_currency** — business key `CurrencyCode`. Currency identified by its ISO currency code. _(requirements: REQ-022-2, REQ-086)_
- **hub_currency_rate** — business key `currency_rate`. Daily exchange rate converting one currency to another on a given date. _(requirements: REQ-024-2, REQ-025-2, REQ-062-2, REQ-013-3)_
- **hub_special_offer** — business key `SpecialOfferID`. Special offer / promotional discount. _(requirements: REQ-008-2, REQ-051, REQ-085)_
- **hub_sales_reason** — business key `SalesReasonID`. Sales reason from the sales reason catalogue. _(requirements: REQ-055)_
- **hub_shopping_cart_item** — business key `shopping_cart_item`. Online shopping cart item, identified within its shopping cart. _(requirements: REQ-001-2, REQ-002-2, REQ-087)_
- **hub_sales_tax_rate** — business key `SalesTaxRateID`. Sales tax rate from the tax rate register. _(requirements: REQ-035-2, REQ-084)_

### Links (20)

- **link_customer_business_entity** — connects hub_customer, hub_business_entity (person), hub_business_entity (store). Customer kind: the person who is an individual customer or the store that is a store customer. Unit of work: Customer AccountNumber with its PersonID / StoreID references. _(requirements: REQ-003, REQ-004, REQ-005, REQ-008, REQ-055-2, REQ-083)_
- **link_customer_sales_territory** — connects hub_customer, hub_sales_territory. Sales territory in which a customer is located. _(requirements: REQ-006, REQ-054-2, REQ-010)_
- **link_business_entity_store_sales_person** — connects hub_business_entity, hub_business_entity (sales_person). Sales representative assigned to a reseller store. _(requirements: REQ-013, REQ-056-2, REQ-030-3)_
- **link_business_entity_sales_territory** — connects hub_business_entity, hub_sales_territory. Territory a sales representative is currently assigned to (current value on the representative record). _(requirements: REQ-061, REQ-057-2, REQ-011-3)_
- **link_business_entity_sales_territory_history** — connects hub_business_entity, hub_sales_territory. Dated history of which representative worked which territory. Driving key: hub_business_entity. _(requirements: REQ-006-3, REQ-007-3, REQ-008-3, REQ-009-3, REQ-010-3, REQ-058-2)_
- **link_sales_order_header** — connects hub_sales_order, hub_customer, hub_business_entity (sales_person), hub_sales_territory, hub_address (bill_to), hub_address (ship_to), hub_ship_method, hub_credit_card. Order header context: ordering customer, sales representative, order territory, billing and shipping address, ship method and credit card. Unit of work: One sales order header row and the business keys it references. _(requirements: REQ-017, REQ-019, REQ-020, REQ-021, REQ-028, REQ-029, REQ-030, REQ-039, REQ-041-2, REQ-043-2, REQ-046-2, REQ-051-2, REQ-066-2, REQ-067-2, REQ-083)_
- **link_sales_order_currency_rate** — connects hub_sales_order, hub_currency_rate. Currency exchange rate applied to an order, where the order was not in base currency (read from SalesOrderHeader). _(requirements: REQ-042, REQ-043, REQ-053-2, REQ-028-2, REQ-031-2)_
- **link_sales_order_line** — connects hub_sales_order_line, hub_sales_order, hub_product, hub_special_offer. Order line within its order, the product sold and the special offer applied. Unit of work: One sales order detail row. _(requirements: REQ-044, REQ-046, REQ-051, REQ-047-2, REQ-048-2, REQ-049-2, REQ-083)_
- **link_sales_order_sales_reason** — connects hub_sales_order, hub_sales_reason. Sales reasons recorded against an order (many-to-many). _(requirements: REQ-056, REQ-057, REQ-050-2)_
- **link_credit_card_business_entity** — connects hub_credit_card, hub_business_entity. Credit cards registered to persons (many-to-many). _(requirements: REQ-080, REQ-081, REQ-052-2, REQ-082)_
- **link_special_offer_product** — connects hub_special_offer, hub_product. Products a special offer applies to (many-to-many). _(requirements: REQ-085, REQ-019-2, REQ-020-2, REQ-060-2)_
- **link_country_region_currency** — connects hub_country_region, hub_currency. Currencies in which each country/region trades (many-to-many). _(requirements: REQ-086, REQ-032-2, REQ-033-2, REQ-061-2)_
- **link_currency_rate_currency** — connects hub_currency_rate, hub_currency (from_currency), hub_currency (to_currency). Currency converted from and currency converted to by an exchange rate. _(requirements: REQ-025-2, REQ-062-2)_
- **link_sales_tax_rate_state_province** — connects hub_sales_tax_rate, hub_state_province. State/province a sales tax rate applies to. _(requirements: REQ-036-2, REQ-063-2, REQ-084)_
- **link_sales_territory_country_region** — connects hub_sales_territory, hub_country_region. Country/region a sales territory belongs to. _(requirements: REQ-069, REQ-059-2, REQ-074)_
- **link_shopping_cart_item_product** — connects hub_shopping_cart_item, hub_product. Product placed in a shopping cart item. _(requirements: REQ-003-2, REQ-064-2, REQ-006-2)_
- **link_sales_order_line_product** — connects hub_sales_order_line, hub_product. Declared foreign key SalesOrderDetail.ProductID references PRODUCTNUMBER; ratified from the source catalogue (WP34). _(requirements: —)_
- **link_sales_order_address** — connects hub_sales_order, hub_address. Declared foreign key SalesOrderHeader.BillToAddressID references ADDRESSID; ratified from the source catalogue (WP34). _(requirements: —)_
- **link_sales_order_business_entity** — connects hub_sales_order, hub_business_entity. Declared foreign key SalesOrderHeader.SalesPersonID references BUSINESSENTITYID; ratified from the source catalogue (WP34). _(requirements: —)_
- **link_sales_order_ship_method** — connects hub_sales_order, hub_ship_method. Declared foreign key SalesOrderHeader.ShipMethodID references NAME; ratified from the source catalogue (WP34). _(requirements: —)_

### Satellites (26)

- **sat_customer_details** — on hub_customer; payload: ModifiedDate. Customer record change tracking for reconciliation with source. Source table: Customer. _(requirements: REQ-009, REQ-018-3)_
- **sat_business_entity_store_details** — on hub_business_entity; payload: Name, ModifiedDate. Store name. Source table: Store. Split rationale: Non-sensitive store descriptors separated from confidential demographics.. _(requirements: REQ-011, REQ-012)_
- **sat_business_entity_store_demographics** — on hub_business_entity; payload: Demographics. Confidential store demographics (employees, annual sales, store type). Source table: Store. Split rationale: Commercially confidential classification.. _(requirements: REQ-014, REQ-015, REQ-045-3, REQ-017-3)_
- **sat_business_entity_sales_person_compensation** — on hub_business_entity; payload: SalesQuota, Bonus, CommissionPct. Sales representative current quota, bonus and commission (remuneration data, access-restricted). Source table: SalesPerson. Split rationale: Remuneration data classification; changes on plan revisions.. _(requirements: REQ-062, REQ-063, REQ-064, REQ-004-3, REQ-044-3)_
- **sat_business_entity_sales_person_running_totals** — on hub_business_entity; payload: SalesYTD, SalesLastYear, ModifiedDate. Operationally maintained representative sales running totals. Source table: SalesPerson. Split rationale: High rate of change running totals.. _(requirements: REQ-065, REQ-038-3)_
- **sat_business_entity_sales_quota_history** — on hub_business_entity; payload: SalesQuota, ModifiedDate. Dated sales quota history per representative. Multi-active satellite, child dependent key: QuotaDate. Source table: SalesPersonQuotaHistory. _(requirements: REQ-001-3, REQ-002-3, REQ-003-3, REQ-044-3)_
- **sat_business_entity_sales_territory_history_effectivity** — on link_business_entity_sales_territory_history; payload: StartDate, EndDate. Active period of a representative's territory assignment. Effectivity satellite. Source table: SalesTerritoryHistory. _(requirements: REQ-006-3, REQ-007-3, REQ-008-3, REQ-009-3)_
- **sat_sales_order_status** — on hub_sales_order; payload: Status, RevisionNumber, OnlineOrderFlag, ModifiedDate. Order status, revision number and sales channel flag. Source table: SalesOrderHeader. Split rationale: Changes as the order progresses.. _(requirements: REQ-018, REQ-023, REQ-024, REQ-033, REQ-027-3)_
- **sat_sales_order_dates** — on hub_sales_order; payload: OrderDate, DueDate, ShipDate. Order lifecycle dates. Source table: SalesOrderHeader. _(requirements: REQ-022, REQ-025, REQ-026-3)_
- **sat_sales_order_totals** — on hub_sales_order; payload: SubTotal, TaxAmt, Freight, TotalDue. Order financial amounts. Source table: SalesOrderHeader. _(requirements: REQ-034, REQ-035, REQ-036, REQ-037, REQ-038, REQ-033-3)_
- **sat_sales_order_references** — on hub_sales_order; payload: PurchaseOrderNumber, AccountNumber, Comment. Customer PO number, financial account number reference and representative comments. Source table: SalesOrderHeader. _(requirements: REQ-026, REQ-027, REQ-031)_
- **sat_sales_order_payment** — on hub_sales_order; payload: CreditCardApprovalCode. Credit card approval code (payment-sensitive). Source table: SalesOrderHeader. Split rationale: Payment-sensitive classification.. _(requirements: REQ-040, REQ-041-3)_
- **sat_sales_order_line_pricing** — on hub_sales_order_line; payload: OrderQty, UnitPrice, UnitPriceDiscount, LineTotal, ModifiedDate. Order line quantity, price, discount and line total. Source table: SalesOrderDetail. _(requirements: REQ-047, REQ-048, REQ-049, REQ-050, REQ-053, REQ-054, REQ-034-3)_
- **sat_sales_order_line_shipment** — on hub_sales_order_line; payload: CarrierTrackingNumber. Shipper tracking number per line. Source table: SalesOrderDetail. Split rationale: Populated at shipment, different rate of change.. _(requirements: REQ-052)_
- **sat_sales_reason_details** — on hub_sales_reason; payload: Name, ReasonType, ModifiedDate. Sales reason description and category. Source table: SalesReason. _(requirements: REQ-055, REQ-058)_
- **sat_sales_territory_details** — on hub_sales_territory; payload: Group, ModifiedDate. Territory geographic group. Source table: SalesTerritory. _(requirements: REQ-070, REQ-074, REQ-017-3)_
- **sat_sales_territory_financials** — on hub_sales_territory; payload: SalesYTD, SalesLastYear, CostYTD, CostLastYear. Territory sales and cost running totals. Source table: SalesTerritory. Split rationale: High rate of change running totals.. _(requirements: REQ-071, REQ-072, REQ-073, REQ-024-3, REQ-038-3)_
- **sat_credit_card_details** — on hub_credit_card; payload: CardType, ModifiedDate. Card type. Source table: CreditCard. _(requirements: REQ-076, REQ-077)_
- **sat_credit_card_expiry** — on hub_credit_card; payload: ExpMonth, ExpYear. Card expiry data (sensitive, access-restricted). Source table: CreditCard. Split rationale: Sensitive payment data classification.. _(requirements: REQ-076, REQ-078, REQ-041-3)_
- **sat_currency_details** — on hub_currency; payload: Name, ModifiedDate. Currency name. Source table: Currency. _(requirements: REQ-022-2, REQ-023-2)_
- **sat_currency_rate_details** — on hub_currency_rate; payload: AverageRate, EndOfDayRate, ModifiedDate. Average and end-of-day exchange rates. Source table: CurrencyRate. _(requirements: REQ-026-2, REQ-027-2, REQ-028-2, REQ-014-3)_
- **sat_special_offer_details** — on hub_special_offer; payload: Description, Type, Category, MinQty, MaxQty, ModifiedDate. Special offer description, type, category group and quantity thresholds. Source table: SpecialOffer. _(requirements: REQ-008-2, REQ-010-2, REQ-011-2, REQ-012-2, REQ-013-2, REQ-018-2)_
- **sat_special_offer_discount** — on hub_special_offer; payload: DiscountPct. Special offer discount percentage, tracked over time. Source table: SpecialOffer. Split rationale: Commercially significant attribute whose history must be visible.. _(requirements: REQ-009-2, REQ-017-3)_
- **sat_special_offer_validity** — on hub_special_offer; payload: StartDate, EndDate. Special offer validity period. Source table: SpecialOffer. _(requirements: REQ-014-2, REQ-015-2, REQ-016-2, REQ-015-3, REQ-016-3, REQ-035-3)_
- **sat_sales_tax_rate_details** — on hub_sales_tax_rate; payload: Name, TaxType, TaxRate, ModifiedDate. Tax rate description, tax type and rate amount. Source table: SalesTaxRate. _(requirements: REQ-035-2, REQ-037-2, REQ-038-2, REQ-039-2)_
- **sat_shopping_cart_item_details** — on hub_shopping_cart_item; payload: Quantity, DateCreated, ModifiedDate. Cart item quantity and creation timestamp. Source table: ShoppingCartItem. _(requirements: REQ-004-2, REQ-005-2, REQ-007-2, REQ-031-3)_

### Hub keys decided before modelling (3)

- **CreditCard** — key `CardNumber`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `CreditCardID` (0.55); primary key `CreditCardID`.
- **Currency** — key `CurrencyCode`: the requirements name it and the catalogue declares it unique; the requirements' first choice was `CurrencyCode` (0.92); primary key `CurrencyCode`.
- **SalesTerritory** — key `Name`: the declared natural key, taken as the default of a contested case; the requirements' first choice was `TerritoryID` (0.50); primary key `TerritoryID`.

### Source mappings (76)

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
- `shopping_cart_item` → `ShoppingCartItem`.`ShoppingCartItemID` — llm_semantic, accepted
- `SalesTaxRateID` → `SalesTaxRate`.`SalesTaxRateID` — exact_name, accepted
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
- `Status` → `SalesOrderHeader`.`Status` — exact_name, accepted
- `RevisionNumber` → `SalesOrderHeader`.`RevisionNumber` — exact_name, accepted
- `OnlineOrderFlag` → `SalesOrderHeader`.`OnlineOrderFlag` — exact_name, accepted
- `ModifiedDate` → `SalesOrderHeader`.`ModifiedDate` — exact_name, accepted
- `OrderDate` → `SalesOrderHeader`.`OrderDate` — exact_name, accepted
- `DueDate` → `SalesOrderHeader`.`DueDate` — exact_name, accepted
- `ShipDate` → `SalesOrderHeader`.`ShipDate` — exact_name, accepted
- `SubTotal` → `SalesOrderHeader`.`SubTotal` — exact_name, accepted
- `TaxAmt` → `SalesOrderHeader`.`TaxAmt` — exact_name, accepted
- `Freight` → `SalesOrderHeader`.`Freight` — exact_name, accepted
- `TotalDue` → `SalesOrderHeader`.`TotalDue` — exact_name, accepted
- `PurchaseOrderNumber` → `SalesOrderHeader`.`PurchaseOrderNumber` — exact_name, accepted
- `AccountNumber` → `SalesOrderHeader`.`AccountNumber` — exact_name, accepted
- `Comment` → `SalesOrderHeader`.`Comment` — exact_name, accepted
- `CreditCardApprovalCode` → `SalesOrderHeader`.`CreditCardApprovalCode` — exact_name, accepted
- `OrderQty` → `SalesOrderDetail`.`OrderQty` — exact_name, accepted
- `UnitPrice` → `SalesOrderDetail`.`UnitPrice` — exact_name, accepted
- `UnitPriceDiscount` → `SalesOrderDetail`.`UnitPriceDiscount` — exact_name, accepted
- `LineTotal` → `SalesOrderDetail`.`LineTotal` — exact_name, accepted
- `ModifiedDate` → `SalesOrderDetail`.`ModifiedDate` — exact_name, accepted
- `CarrierTrackingNumber` → `SalesOrderDetail`.`CarrierTrackingNumber` — exact_name, accepted
- `Name` → `SalesReason`.`Name` — exact_name, accepted
- `ReasonType` → `SalesReason`.`ReasonType` — exact_name, accepted
- `ModifiedDate` → `SalesReason`.`ModifiedDate` — exact_name, accepted
- `Group` → `SalesTerritory`.`Group` — exact_name, accepted
- `ModifiedDate` → `SalesTerritory`.`ModifiedDate` — exact_name, accepted
- `SalesYTD` → `SalesTerritory`.`SalesYTD` — exact_name, accepted
- `SalesLastYear` → `SalesTerritory`.`SalesLastYear` — exact_name, accepted
- `CostYTD` → `SalesTerritory`.`CostYTD` — exact_name, accepted
- `CostLastYear` → `SalesTerritory`.`CostLastYear` — exact_name, accepted
- `CardType` → `CreditCard`.`CardType` — exact_name, accepted
- `ModifiedDate` → `CreditCard`.`ModifiedDate` — exact_name, accepted
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
- `DiscountPct` → `SpecialOffer`.`DiscountPct` — exact_name, accepted
- `StartDate` → `SpecialOffer`.`StartDate` — exact_name, accepted
- `EndDate` → `SpecialOffer`.`EndDate` — exact_name, accepted
- `Name` → `SalesTaxRate`.`Name` — exact_name, accepted
- `TaxType` → `SalesTaxRate`.`TaxType` — exact_name, accepted
- `TaxRate` → `SalesTaxRate`.`TaxRate` — exact_name, accepted
- `ModifiedDate` → `SalesTaxRate`.`ModifiedDate` — exact_name, accepted
- `Quantity` → `ShoppingCartItem`.`Quantity` — exact_name, accepted
- `DateCreated` → `ShoppingCartItem`.`DateCreated` — exact_name, accepted
- `ModifiedDate` → `ShoppingCartItem`.`ModifiedDate` — exact_name, accepted

Unresolved — the mapper could not decide (1): hub_business_entity::ModifiedDate.

## Extends

This is an EXTENSION of an existing vault (`demo/workbench-adventureworks/adventureworks/runs/20261115T112757570638Z`) carrying 29 hub(s), 28 link(s) and 72 satellite(s). Those constructs are unchanged by this run and are deliberately not re-listed below — this record documents the delta only.

128 construct(s) were left untouched and 1 were extended; see `extension-diff.md` for the per-construct detail, including which generated files changed content.


## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.

## References

- Source requirement document(s): demo/workbench-adventureworks/adventureworks/inputs/sales_requirements.md
- Generated dbt models: 186 raw-vault model(s) + 281 staging model(s) (see `state.artifacts`)
