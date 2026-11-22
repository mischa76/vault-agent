# Human-in-the-loop checkpoint

**Status:** advisory only — 10 decision(s), 52 disclosure(s).

## Decisions

### Review flags (advisory)

- **link_proposer: 1 construct(s) translate to hub_customer's key ACCOUNTNUMBER by joining through Customer — confirm the translation model once** — key hub_customer=Customer.ACCOUNTNUMBER; constructs: SalesOrderHeader.CustomerID _(link_proposer)_
- **link_proposer: 1 construct(s) translate to hub_state_province's key NAME by joining through StateProvince — confirm the translation model once** — key hub_state_province=StateProvince.NAME; constructs: SalesTaxRate.StateProvinceID _(link_proposer)_
- **link_proposer: ratified relationship link for Store not built: two participations resolve to the same hub — a link with a missing or merged participation has a different grain** _(link_proposer)_
- **source_mapper: concept 'ModifiedDate' could not be resolved to a single source column — a human ratifies it (a multi-source key is deferred to WP10)** _(source_mapper)_
- **code_generator: staging model 'stg_product_subcategory' was bound to 'ProductSubcategory', which declares none of PRODUCTNUMBER that the stage hashes or derives; the binding is refused and the stage reads 'raw_product_subcategory' until a human maps the relation** _(code_generator)_
- **5× link-binding-evidence** — e.g. link_customer_sales_territory, link_business_entity_store_sales_person, … — review before agreeing _(link_proposer)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_product_assembly_component_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_sales_territory_history_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_LINK_REDUNDANT_GRAIN on link_business_entity_sales_territory, link_business_entity_sales_territory_history** — links link_business_entity_sales_territory, link_business_entity_sales_territory_history connect the same hubs with the same link_type; likely the same unit of work modeled twice or a grain error _(validator)_
- **15× W_SAT_ATTR_OVERLAP_CROSS_SOURCE** — e.g. hub_business_entity, hub_business_entity, … — review before agreeing _(validator)_
- **W_BK_COLLISION_RISK on hub_address_type, hub_contact_type, hub_department, hub_location, hub_product_category, hub_product_model, hub_product_subcategory, hub_sales_territory, hub_scrap_reason, hub_shift, hub_ship_method, hub_state_province** — hubs hub_address_type, hub_contact_type, hub_department, hub_location, hub_product_category, hub_product_model, hub_product_subcategory, hub_sales_territory, hub_scrap_reason, hub_shift, hub_ship_method, hub_state_province share business key 'Name' across different source entities ['AddressType', 'ContactType', 'Department', 'Location', 'ProductCategory', 'ProductModel', 'ProductSubcategory', 'SalesTerritory', 'ScrapReason', 'Shift', 'ShipMethod', 'StateProvince']; confirm whether a collision code is needed _(validator)_
- **W_ROLE_BK_NOT_IN_SOURCE on link_business_entity_store_sales_person** — role-qualified participation hub_business_entity (role 'sales_person') expects a source column 'SALES_PERSON_BUSINESSENTITYID', which matches no column in the declared source schema; verify the source or complete the schema _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_special_offer** — hub 'hub_special_offer' is keyed on SpecialOfferID, SpecialOffer's technical primary key — SpecialOffer declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_sales_reason** — hub 'hub_sales_reason' is keyed on SalesReasonID, SalesReason's technical primary key — SalesReason declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_sales_tax_rate** — hub 'hub_sales_tax_rate' is keyed on SalesTaxRateID, SalesTaxRate's technical primary key — SalesTaxRate declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/sales_requirements.md' did not fit one model response and was extracted over 3 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **8× declined foreign key(s) — no hub for the referenced table** — e.g. CountryRegionCurrency.CountryRegionCode, PersonCreditCard.BusinessEntityID, … — review before agreeing _(link_proposer)_
- **4× construct(s) translating to hub_product's key PRODUCTNUMBER through Product** — e.g. SalesOrderDetail.ProductID, SalesOrderDetail.ProductID, … — review before agreeing _(link_proposer)_
- **link_proposer: link to hub_ship_method from SalesOrderHeader requires surrogate→natural-key translation through ShipMethod (ShipMethodID → NAME); review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_header, built by the modeler from SalesOrderHeader, requires surrogate→natural-key translation through ShipMethod for hub_ship_method (ShipMethodID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **4× construct(s) translating to hub_sales_territory's key NAME through SalesTerritory** — e.g. Customer.TerritoryID, SalesOrderHeader.TerritoryID, … — review before agreeing _(link_proposer)_
- **link_proposer: link link_credit_card_business_entity, built by the modeler from PersonCreditCard, requires surrogate→natural-key translation through CreditCard for hub_credit_card (CreditCardID → CARDNUMBER); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_header, built by the modeler from SalesOrderHeader, requires surrogate→natural-key translation through CreditCard for hub_credit_card (CreditCardID → CARDNUMBER); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_line, built by the modeler from SalesOrderDetail, requires surrogate→natural-key translation through SalesOrderHeader for hub_sales_order (SalesOrderID → SALESORDERNUMBER); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_sales_reason, built by the modeler from SalesOrderHeaderSalesReason, requires surrogate→natural-key translation through SalesOrderHeader for hub_sales_order (SalesOrderID → SALESORDERNUMBER); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_header, built by the modeler from SalesOrderHeader, requires surrogate→natural-key translation through CurrencyRate for hub_currency_rate (CurrencyRateID → CURRENCYRATEDATE, FROMCURRENCYCODE, TOCURRENCYCODE); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_currency_rate, built by the modeler from SalesOrderHeader, requires surrogate→natural-key translation through CurrencyRate for hub_currency_rate (CurrencyRateID → CURRENCYRATEDATE, FROMCURRENCYCODE, TOCURRENCYCODE); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_header, built by the modeler from SalesOrderHeader, requires surrogate→natural-key translation through Customer for hub_customer (CustomerID → ACCOUNTNUMBER); repaired under a ratified key; review the translation model; SalesOrderHeader.AccountNumber has the hub key's name but is not declared as its key — not read (a copy or a homonym; the declared key decides)** _(link_proposer)_
- **link_proposer: link link_sales_tax_rate_state_province, built by the modeler from SalesTaxRate, requires surrogate→natural-key translation through StateProvince for hub_state_province (StateProvinceID → NAME); repaired under a ratified key; review the translation model; SalesTaxRate.Name has the hub key's name but is not declared as its key — not read (a copy or a homonym; the declared key decides)** _(link_proposer)_
- **code_generator: staging model 'stg_work_order_operation' assumes raw source 'raw_work_order_operation' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
