# Human-in-the-loop checkpoint

**Status:** advisory only — 2 decision(s), 26 disclosure(s).

## Decisions

### Review flags (advisory)

- **entity_resolver: concept 'ProductID' is asserted equivalent to 'hub_product' but is keyed differently — two constructs are modelled and a human decides what relates them; never merged** _(entity_resolver)_
- **code_generator: staging model 'stg_product_subcategory' was bound to 'ProductSubcategory', which declares none of PRODUCTNUMBER that the stage hashes or derives; the binding is refused and the stage reads 'raw_product_subcategory' until a human maps the relation** _(code_generator)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_product_assembly_component_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **12× W_SAT_ATTR_OVERLAP_CROSS_SOURCE** — e.g. hub_business_entity, hub_inventory_transaction, … — review before agreeing _(validator)_
- **W_BK_COLLISION_RISK on hub_address_type, hub_contact_type, hub_department, hub_location, hub_product_category, hub_product_model, hub_product_subcategory, hub_scrap_reason, hub_shift, hub_ship_method, hub_state_province** — hubs hub_address_type, hub_contact_type, hub_department, hub_location, hub_product_category, hub_product_model, hub_product_subcategory, hub_scrap_reason, hub_shift, hub_ship_method, hub_state_province share business key 'Name' across different source entities ['AddressType', 'ContactType', 'Department', 'Location', 'ProductCategory', 'ProductModel', 'ProductSubcategory', 'ScrapReason', 'Shift', 'ShipMethod', 'StateProvince']; confirm whether a collision code is needed _(validator)_
- **W_HUB_ON_TECHNICAL_KEY on hub_purchase_order** — hub 'hub_purchase_order' is keyed on PurchaseOrderID, PurchaseOrderHeader's technical primary key — PurchaseOrderHeader declares no natural key; it identifies a row in this source system only, so a second source of the same concept cannot be integrated by key _(validator)_

### Review flags (advisory)

- **link_proposer: ratified link to hub_product not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **link_proposer: ratified link to hub_unit_measure not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **link_proposer: ratified link to hub_business_entity not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **5× construct(s) translating to hub_product's key PRODUCTNUMBER through Product** — e.g. PurchaseOrderDetail.ProductID, ProductVendor.ProductID, … — review before agreeing _(link_proposer)_
- **link_proposer: link link_purchase_order_business_entity_ship_method, built by the modeler from PurchaseOrderHeader, requires surrogate→natural-key translation through ShipMethod for hub_ship_method (ShipMethodID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **code_generator: staging model 'stg_work_order_operation' assumes raw source 'raw_work_order_operation' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
