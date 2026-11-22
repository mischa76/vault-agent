# Human-in-the-loop checkpoint

**Status:** advisory only — 4 decision(s), 46 disclosure(s).

## Decisions

### Review flags (advisory)

- **link_proposer: 3 construct(s) translate to hub_product_model's key NAME by joining through ProductModel — confirm the translation model once** — key hub_product_model=ProductModel.NAME; constructs: Product.ProductModelID, ProductModelIllustration.ProductModelID, ProductModelProductDescriptionCulture.ProductModelID _(link_proposer)_
- **link_proposer: 1 construct(s) translate to hub_product_category's key NAME by joining through ProductCategory — confirm the translation model once** — key hub_product_category=ProductCategory.NAME; constructs: ProductSubcategory.ProductCategoryID _(link_proposer)_
- **source_mapper: concept 'work_order_operation' could not be resolved to a single source column; candidates: Composite key concept (WorkOrderID, ProductID, OperationSequence) in WorkOrderRouting; a single column cannot represent it, candidate: WorkOrderRouting.OperationSequence, WorkOrderRouting.WorkOrderID — a human ratifies it (a multi-source key is deferred to WP10)** _(source_mapper)_
- **code_generator: staging model 'stg_product_subcategory' was bound to 'ProductSubcategory', which declares none of PRODUCTNUMBER that the stage hashes or derives; the binding is refused and the stage reads 'raw_product_subcategory' until a human maps the relation** _(code_generator)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_product_assembly_component_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **12× W_SAT_ATTR_OVERLAP_CROSS_SOURCE** — e.g. hub_business_entity, hub_inventory_transaction, … — review before agreeing _(validator)_
- **W_BK_COLLISION_RISK on hub_address_type, hub_contact_type, hub_department, hub_location, hub_product_category, hub_product_model, hub_product_subcategory, hub_scrap_reason, hub_shift, hub_state_province** — hubs hub_address_type, hub_contact_type, hub_department, hub_location, hub_product_category, hub_product_model, hub_product_subcategory, hub_scrap_reason, hub_shift, hub_state_province share business key 'Name' across different source entities ['AddressType', 'ContactType', 'Department', 'Location', 'ProductCategory', 'ProductModel', 'ProductSubcategory', 'ScrapReason', 'Shift', 'StateProvince']; confirm whether a collision code is needed _(validator)_
- **6× W_HUB_ON_TECHNICAL_KEY** — e.g. hub_product_description, hub_product_photo, … — review before agreeing _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/production_requirements.md' did not fit one model response and was extracted over 4 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **source_mapper: the 105 concept(s) did not fit one model response; mapping ran over 2 segment(s) of the concept list (each saw the full source schema) — review the proposals for consistency** _(source_mapper)_
- **14× construct(s) translating to hub_product's key PRODUCTNUMBER through Product** — e.g. BillOfMaterials.ComponentID, BillOfMaterials.ProductAssemblyID, … — review before agreeing _(link_proposer)_
- **link_proposer: link link_product_product_model, built by the modeler from Product, requires surrogate→natural-key translation through ProductModel for hub_product_model (ProductModelID → NAME); repaired under a ratified key; review the translation model; Product.Name has the hub key's name but is not declared as its key — not read (a copy or a homonym; the declared key decides)** _(link_proposer)_
- **link_proposer: link link_product_model_illustration, built by the modeler from ProductModelIllustration, requires surrogate→natural-key translation through ProductModel for hub_product_model (ProductModelID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_product_model_description_culture, built by the modeler from ProductModelProductDescriptionCulture, requires surrogate→natural-key translation through ProductModel for hub_product_model (ProductModelID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_product_location, built by the modeler from ProductInventory, requires surrogate→natural-key translation through Location for hub_location (LocationID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: satellite sat_product_location_inventory reads ProductInventory, which carries LocationID but not hub_location's key NAME: joined in through Location under a ratified key; review the translation model** _(link_proposer)_
- **link_proposer: link link_product_subcategory_category, built by the modeler from ProductSubcategory, requires surrogate→natural-key translation through ProductCategory for hub_product_category (ProductCategoryID → NAME); repaired under a ratified key; review the translation model; ProductSubcategory.Name has the hub key's name but is not declared as its key — not read (a copy or a homonym; the declared key decides)** _(link_proposer)_
- **link_proposer: link link_work_order_scrap_reason, built by the modeler from WorkOrder, requires surrogate→natural-key translation through ScrapReason for hub_scrap_reason (ScrapReasonID → NAME); repaired under a ratified key; review the translation model** _(link_proposer)_
- **source_mapper: concept 'EndDate' has no in-scope source (derived/enriched); it belongs to the Business Vault / marts, not the Raw Vault** _(source_mapper)_
- **code_generator: staging model 'stg_work_order_operation' assumes raw source 'raw_work_order_operation' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
