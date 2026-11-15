# Human-in-the-loop checkpoint

**Status:** advisory only — 1 decision(s), 27 disclosure(s).

## Decisions

### Review flags (advisory)

- **entity_resolver: concept 'AccountNumber (vendor account number)' could not be resolved against the existing vault — a human decides whether it is an existing construct or new** _(entity_resolver)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_product_assembly_component_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **12× W_SAT_ATTR_OVERLAP_CROSS_SOURCE** — e.g. hub_business_entity, hub_inventory_transaction, … — review before agreeing _(validator)_
- **W_BK_COLLISION_RISK on hub_address_type, hub_contact_type, hub_department, hub_location, hub_product_category, hub_product_model, hub_product_subcategory, hub_scrap_reason, hub_shift, hub_ship_method, hub_state_province** — hubs hub_address_type, hub_contact_type, hub_department, hub_location, hub_product_category, hub_product_model, hub_product_subcategory, hub_scrap_reason, hub_shift, hub_ship_method, hub_state_province share business key 'Name' across different source entities ['AddressType', 'ContactType', 'Department', 'Location', 'ProductCategory', 'ProductModel', 'ProductSubcategory', 'ScrapReason', 'Shift', 'ShipMethod', 'StateProvince']; confirm whether a collision code is needed _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_purchase_order** — hub 'hub_purchase_order' is keyed on PurchaseOrderID, PurchaseOrderHeader's technical primary key — PurchaseOrderHeader declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/purchasing_requirements.md' did not fit one model response and was extracted over 2 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **link_proposer: ratified link to hub_product not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **link_proposer: ratified link to hub_unit_measure not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **link_proposer: ratified link to hub_business_entity not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **5× construct(s) translating to hub_product's key PRODUCTNUMBER through Product** — e.g. PurchaseOrderDetail.ProductID, ProductVendor.ProductID, … — review before agreeing _(link_proposer)_
- **link_proposer: link link_purchase_order_ship_method, built by the modeler from PurchaseOrderHeader, requires surrogate→natural-key translation through ShipMethod for hub_ship_method (ShipMethodID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **code_generator: staging model 'stg_work_order_operation_location' assumes raw source 'raw_work_order_operation_location' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
