# Extension diff

This run extended the vault at `demo/workbench-adventureworks/adventureworks/runs/20261021T232716713739Z`: **44 unchanged**, **0 extended**, **60 new** construct(s).

Unchanged constructs render byte-identically, so their tables are untouched by a rebuild. The files listed under *extended* are the ones that genuinely changed.

## Unchanged (44)

`hub_business_entity`, `hub_address`, `hub_address_type`, `hub_contact_type`, `hub_phone_number_type`, `hub_country_region`, `hub_state_province`, `hub_department`, `hub_shift`, `hub_job_candidate`, `link_business_entity_address`, `link_business_entity_contact`, `link_business_entity_phone_number_type`, `link_address_state_province`, `link_state_province_country_region`, `link_business_entity_department_shift`, `link_business_entity_job_candidate`, `sat_business_entity_details`, `sat_business_entity_person_name`, `sat_business_entity_marketing_consent`, `sat_business_entity_person_sensitive`, `sat_business_entity_credential`, `sat_business_entity_email`, `sat_business_entity_phone_number_type_phones`, `sat_business_entity_address_details`, `sat_business_entity_contact_details`, `sat_address_details`, `sat_address_location`, `sat_address_type_details`, `sat_contact_type_details`, `sat_phone_number_type_details`, `sat_country_region_details`, `sat_state_province_details`, `sat_state_province_territory`, `sat_business_entity_employee_details`, `sat_business_entity_employee_sensitive`, `sat_business_entity_employee_leave`, `sat_business_entity_employee_hierarchy`, `sat_business_entity_pay_history`, `sat_business_entity_department_shift_effectivity`, `sat_business_entity_department_shift_audit`, `sat_department_details`, `sat_shift_details`, `sat_job_candidate_resume`

## Extended (0)

—

## New (60)

- **hub_product**
- **hub_product_category**
- **hub_product_subcategory**
- **hub_product_model**
- **hub_culture**
- **hub_unit_measure**
- **hub_product_description**
- **hub_product_photo**
- **hub_illustration**
- **hub_document**
- **hub_location**
- **hub_scrap_reason**
- **hub_work_order**
- **hub_inventory_transaction**
- **hub_product_review**
- **link_product_product_subcategory**
- **link_product_subcategory_product_category**
- **link_product_product_model**
- **link_product_unit_measure**
- **link_product_assembly_component**
- **link_product_model_description_culture**
- **link_product_model_illustration**
- **link_product_product_photo**
- **link_product_document**
- **link_document_business_entity**
- **link_product_location**
- **link_work_order_product**
- **link_work_order_scrap_reason**
- **link_work_order_product_location**
- **link_inventory_transaction_product**
- **link_product_review_product**
- **sat_product_details** — on `hub_product`
- **sat_product_pricing** — on `hub_product`
- **sat_product_inventory_policy** — on `hub_product`
- **sat_product_lifecycle** — on `hub_product`
- **sat_product_cost_history** — on `hub_product`
- **sat_product_list_price_history** — on `hub_product`
- **sat_product_category_details** — on `hub_product_category`
- **sat_product_subcategory_details** — on `hub_product_subcategory`
- **sat_product_model_details** — on `hub_product_model`
- **sat_product_model_content** — on `hub_product_model`
- **sat_culture_details** — on `hub_culture`
- **sat_unit_measure_details** — on `hub_unit_measure`
- **sat_product_description_details** — on `hub_product_description`
- **sat_product_photo_details** — on `hub_product_photo`
- **sat_product_photo_images** — on `hub_product_photo`
- **sat_illustration_diagram** — on `hub_illustration`
- **sat_document_details** — on `hub_document`
- **sat_location_details** — on `hub_location`
- **sat_scrap_reason_details** — on `hub_scrap_reason`
- **sat_work_order_details** — on `hub_work_order`
- **sat_work_order_product_location_operation** — on `link_work_order_product_location`
- **sat_product_location_inventory** — on `link_product_location`
- **sat_product_product_photo_details** — on `link_product_product_photo`
- **sat_product_assembly_component_effectivity** — on `link_product_assembly_component`
- **sat_product_assembly_component_details** — on `link_product_assembly_component`
- **sat_inventory_transaction_details** — on `hub_inventory_transaction`
- **sat_inventory_transaction_archive** — on `hub_inventory_transaction`
- **sat_product_review_details** — on `hub_product_review`
- **sat_product_review_reviewer_pii** — on `hub_product_review`
