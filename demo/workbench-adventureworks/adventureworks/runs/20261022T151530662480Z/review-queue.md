# Human-in-the-loop checkpoint

**Status:** advisory only — 12 decision(s), 31 disclosure(s).

## Decisions

### Review flags (advisory)

- **entity_resolver: concept 'PurchaseOrderNumber' could not be resolved against the existing vault — a human decides whether it is an existing construct or new** _(entity_resolver)_
- **link_proposer: link link_sales_order_line_product_special_offer, built by the modeler from SalesOrderDetail, requires surrogate→natural-key translation through SalesOrderHeader for hub_sales_order (SalesOrderID → SALESORDERNUMBER); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_sales_order_sales_reason, built by the modeler from SalesOrderHeaderSalesReason, requires surrogate→natural-key translation through SalesOrderHeader for hub_sales_order (SalesOrderID → SALESORDERNUMBER); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: satellite sat_sales_order_sales_reason_details reads SalesOrderHeaderSalesReason, which carries SalesOrderID but not hub_sales_order's key SALESORDERNUMBER: joined in through SalesOrderHeader under a ratified key; review the translation model** _(link_proposer)_
- **code_generator: satellite 'sat_business_entity_sales_quota_history' of type 'multi_active' on multi-source hub 'hub_business_entity' is not supported; flagged for human review** _(code_generator)_
- **source_mapper: concept 'rowguid' could not be resolved to a single source column — a human ratifies it (a multi-source key is deferred to WP10)** _(source_mapper)_
- **source_mapper: concept 'ModifiedDate' could not be resolved to a single source column — a human ratifies it (a multi-source key is deferred to WP10)** _(source_mapper)_
- **5× inferred staging source binding(s)** — e.g. stg_customer_sales_territory, stg_business_entity_store_sales_person, … — review before agreeing _(code_generator)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_HUB_NO_SAT on hub_shopping_cart** — hub has no satellite; no descriptive data is captured for it _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_product_assembly_component_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_sales_territory_assignment_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_LINK_REDUNDANT_GRAIN on link_business_entity_sales_territory, link_business_entity_sales_territory_assignment** — links link_business_entity_sales_territory, link_business_entity_sales_territory_assignment connect the same hubs with the same link_type; likely the same unit of work modeled twice or a grain error _(validator)_
- **16× W_SAT_ATTR_OVERLAP_CROSS_SOURCE** — e.g. hub_business_entity, hub_business_entity, … — review before agreeing _(validator)_
- **W_ROLE_BK_NOT_IN_SOURCE on link_business_entity_store_sales_person** — role-qualified participation hub_business_entity (role 'sales_person') expects a source column 'SALES_PERSON_BUSINESSENTITYID', which matches no column in the declared source schema; verify the source or complete the schema _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/sales_requirements.md' did not fit one model response and was extracted over 3 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **source_mapper: the 97 concept(s) did not fit one model response; mapping ran over 2 segment(s) of the concept list (each saw the full source schema) — review the proposals for consistency** _(source_mapper)_
- **5× declined foreign key(s) — no hub for the referenced table** — e.g. CountryRegionCurrency.CountryRegionCode, PersonCreditCard.BusinessEntityID, … — review before agreeing _(link_proposer)_
- **code_generator: staging model 'stg_work_order_product_location' assumes raw source 'raw_work_order_product_location' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
- **code_generator: staging model 'stg_sales_order_currency_rate' assumes raw source 'raw_sales_order_currency_rate' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
