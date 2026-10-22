# Human-in-the-loop checkpoint

**Status:** advisory only — 1 decision(s), 18 disclosure(s).

## Decisions

### Review flags (advisory)

- **data_contract: field Document.'DocumentLevel' has an undetermined type; review required before the contract is agreed** _(data_contract)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_product_assembly_component_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **12× W_SAT_ATTR_OVERLAP_CROSS_SOURCE** — e.g. hub_business_entity, hub_inventory_transaction, … — review before agreeing _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/production_requirements.md' did not fit one model response and was extracted over 3 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **source_mapper: the 109 concept(s) did not fit one model response; mapping ran over 2 segment(s) of the concept list (each saw the full source schema) — review the proposals for consistency** _(source_mapper)_
- **source_mapper: concept 'EndDate' has no in-scope source (derived/enriched); it belongs to the Business Vault / marts, not the Raw Vault** _(source_mapper)_
- **code_generator: staging model 'stg_work_order_product_location' assumes raw source 'raw_work_order_product_location' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
