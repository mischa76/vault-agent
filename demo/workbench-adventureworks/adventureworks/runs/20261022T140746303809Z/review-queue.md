# Human-in-the-loop checkpoint

**Status:** advisory only — 3 decision(s), 19 disclosure(s).

## Decisions

### Review flags (advisory)

- **entity_resolver: concept 'AccountNumber (vendor account number)' is asserted equivalent to 'hub_business_entity' but is keyed differently — two constructs are modelled and a human decides what relates them; never merged** _(entity_resolver)_
- **entity_resolver: concept 'Name (vendor company name)' could not be resolved against the existing vault — a human decides whether it is an existing construct or new** _(entity_resolver)_
- **model_merger: the delta re-states existing link 'link_purchase_order_line_product'; links are never extended in place — additional attributes belong in a NEW satellite on the same parent. The existing link is kept unchanged and this is flagged for human review** _(model_merger)_

## Disclosures (no answer needed)

### Validation warnings (advisory)

- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_business_entity_department_shift_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **W_EFFSAT_DATE_ORDER_UNVERIFIED on sat_product_assembly_component_effectivity** — cannot verify that the effectivity date attributes ('StartDate', 'EndDate') are in (start, end) order; confirm 'StartDate' is the start and 'EndDate' the end of the active period _(validator)_
- **12× W_SAT_ATTR_OVERLAP_CROSS_SOURCE** — e.g. hub_business_entity, hub_inventory_transaction, … — review before agreeing _(validator)_

### Review flags (advisory)

- **requirements_parser: document 'demo/workbench-adventureworks/adventureworks/inputs/purchasing_requirements.md' did not fit one model response and was extracted over 2 segment(s) split on section boundaries; requirement ids are per-segment and were de-collided — review the extracted set for completeness** _(requirements_parser)_
- **link_proposer: ratified link to hub_product not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **link_proposer: ratified link to hub_unit_measure not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **link_proposer: ratified link to hub_business_entity not applied: no hub was modelled for ProductVendor** _(link_proposer)_
- **code_generator: staging model 'stg_work_order_product_location' assumes raw source 'raw_work_order_product_location' (no declared source table matched); provide it as a seed/table of that name or correct the binding** _(code_generator)_
