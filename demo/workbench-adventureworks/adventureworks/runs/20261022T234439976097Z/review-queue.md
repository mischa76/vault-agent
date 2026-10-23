# Human-in-the-loop checkpoint

**Status:** advisory only — 14 decision(s), 29 disclosure(s).

## Decisions

### Review flags (advisory)

- **data_contract: field Customer.'AccountNumber' has an undetermined type; review required before the contract is agreed** _(data_contract)_
- **link_proposer: link link_sales_order_line, built by the modeler from SalesOrderDetail, requires surrogate→natural-key translation through SalesOrderHeader for hub_sales_order (SalesOrderID → SALESORDERNUMBER); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_sales_reason, built by the modeler from SalesOrderHeaderSalesReason, requires surrogate→natural-key translation through SalesOrderHeader for hub_sales_order (SalesOrderID → SALESORDERNUMBER); repaired under a ratified key; review the translation model** _(link_proposer)_
- **source_mapper: concept 'ModifiedDate' could not be resolved to a single source column — a human ratifies it (a multi-source key is deferred to WP10)** _(source_mapper)_
- **source_mapper: concept 'rowguid' could not be resolved to a single source column — a human ratifies it (a multi-source key is deferred to WP10)** _(source_mapper)_
- **4× binding-rejected** — e.g. stg_product_subcategory, stg_product_model, … — review before agreeing _(code_generator)_
- **5× inferred staging source binding(s)** — e.g. stg_customer_sales_territory, stg_store_sales_person, … — review before agreeing _(code_generator)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_bill_of_materials_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_sales_person_territory_history_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_LINK_REDUNDANT_GRAIN on link_sales_person_sales_territory, link_sales_person_territory_history** — links link_sales_person_sales_territory, link_sales_person_territory_history connect the same hubs with the same link_type; likely the same unit of work modeled twice or a grain error _(validator)_
- **16× W_SAT_ATTR_OVERLAP_CROSS_SOURCE** — e.g. hub_business_entity, hub_business_entity, … — review before agreeing _(validator)_
- **W_ROLE_BK_NOT_IN_SOURCE on link_store_sales_person** — role-qualified participation hub_business_entity (role 'sales_person') expects a source column 'SALES_PERSON_BUSINESSENTITYID', which matches no column in the declared source schema; verify the source or complete the schema _(validator)_
- **W_ROLE_BK_NOT_IN_SOURCE on link_sales_person_sales_territory** — role-qualified participation hub_business_entity (role 'sales_person') expects a source column 'SALES_PERSON_BUSINESSENTITYID', which matches no column in the declared source schema; verify the source or complete the schema _(validator)_
- **W_ROLE_BK_NOT_IN_SOURCE on link_sales_person_territory_history** — role-qualified participation hub_business_entity (role 'sales_person') expects a source column 'SALES_PERSON_BUSINESSENTITYID', which matches no column in the declared source schema; verify the source or complete the schema _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/sales_requirements.md' did not fit one model response and was extracted over 3 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **4× declined foreign key(s) — no hub for the referenced table** — e.g. CountryRegionCurrency.CountryRegionCode, PersonCreditCard.BusinessEntityID, … — review before agreeing _(link_proposer)_
- **code_generator: staging model 'stg_work_order_operation' assumes raw source 'raw_work_order_operation' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
