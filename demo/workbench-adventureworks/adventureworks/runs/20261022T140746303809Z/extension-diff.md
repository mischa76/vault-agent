# Extension diff

This run extended the vault at `demo/workbench-adventureworks/adventureworks/runs/20261022T133219892412Z`: **103 unchanged**, **1 extended**, **16 new** construct(s).

Unchanged constructs render byte-identically, so their tables are untouched by a rebuild. The files listed under *extended* are the ones that genuinely changed.

## Unchanged (103)

`hub_address`, `hub_address_type`, `hub_contact_type`, `hub_phone_number_type`, `hub_country_region`, `hub_state_province`, `hub_department`, `hub_shift`, `hub_job_candidate`, `hub_product`, `hub_product_category`, `hub_product_subcategory`, `hub_product_model`, `hub_culture`, `hub_unit_measure`, `hub_product_description`, `hub_product_photo`, `hub_illustration`, `hub_document`, `hub_location`, `hub_scrap_reason`, `hub_work_order`, `hub_inventory_transaction`, `hub_product_review`, `link_business_entity_address`, `link_business_entity_contact`, `link_business_entity_phone_number_type`, `link_address_state_province`, `link_state_province_country_region`, `link_business_entity_department_shift`, `link_business_entity_job_candidate`, `link_product_product_subcategory`, `link_product_subcategory_product_category`, `link_product_product_model`, `link_product_unit_measure`, `link_product_assembly_component`, `link_product_model_description_culture`, `link_product_model_illustration`, `link_product_product_photo`, `link_product_document`, `link_document_business_entity`, `link_product_location`, `link_work_order_product`, `link_work_order_scrap_reason`, `link_work_order_product_location`, `link_inventory_transaction_product`, `link_product_review_product`, `sat_business_entity_details`, `sat_business_entity_person_name`, `sat_business_entity_marketing_consent`, `sat_business_entity_person_sensitive`, `sat_business_entity_credential`, `sat_business_entity_email`, `sat_business_entity_phone_number_type_phones`, `sat_business_entity_address_details`, `sat_business_entity_contact_details`, `sat_address_details`, `sat_address_location`, `sat_address_type_details`, `sat_contact_type_details`, `sat_phone_number_type_details`, `sat_country_region_details`, `sat_state_province_details`, `sat_state_province_territory`, `sat_business_entity_employee_details`, `sat_business_entity_employee_sensitive`, `sat_business_entity_employee_leave`, `sat_business_entity_employee_hierarchy`, `sat_business_entity_pay_history`, `sat_business_entity_department_shift_effectivity`, `sat_business_entity_department_shift_audit`, `sat_department_details`, `sat_shift_details`, `sat_job_candidate_resume`, `sat_product_details`, `sat_product_pricing`, `sat_product_inventory_policy`, `sat_product_lifecycle`, `sat_product_cost_history`, `sat_product_list_price_history`, `sat_product_category_details`, `sat_product_subcategory_details`, `sat_product_model_details`, `sat_product_model_content`, `sat_culture_details`, `sat_unit_measure_details`, `sat_product_description_details`, `sat_product_photo_details`, `sat_product_photo_images`, `sat_illustration_diagram`, `sat_document_details`, `sat_location_details`, `sat_scrap_reason_details`, `sat_work_order_details`, `sat_work_order_product_location_operation`, `sat_product_location_inventory`, `sat_product_product_photo_details`, `sat_product_assembly_component_effectivity`, `sat_product_assembly_component_details`, `sat_inventory_transaction_details`, `sat_inventory_transaction_archive`, `sat_product_review_details`, `sat_product_review_reviewer_pii`

## Extended (1)

- **hub_business_entity** — 1 source feed(s): Vendor.BusinessEntityID; 2 new satellite(s): sat_business_entity_vendor_details, sat_business_entity_vendor_status
  - changed file: `models/raw_vault/hub_business_entity.sql`

## New (16)

- **hub_purchase_order**
- **hub_purchase_order_line**
- **hub_ship_method**
- **link_product_vendor**
- **link_purchase_order_vendor_employee_ship_method**
- **link_purchase_order_line_product**
- **link_purchase_order_business_entity**
- **sat_business_entity_vendor_details** — on `hub_business_entity`
- **sat_business_entity_vendor_status** — on `hub_business_entity`
- **sat_product_vendor_terms** — on `link_product_vendor`
- **sat_product_vendor_receipt** — on `link_product_vendor`
- **sat_purchase_order_status** — on `hub_purchase_order`
- **sat_purchase_order_details** — on `hub_purchase_order`
- **sat_purchase_order_line_details** — on `hub_purchase_order_line`
- **sat_purchase_order_line_receipt** — on `hub_purchase_order_line`
- **sat_ship_method_details** — on `hub_ship_method`
