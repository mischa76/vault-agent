# Extension diff

This run extended the vault at `demo/workbench-adventureworks/adventureworks/runs/20261115T112757570638Z`: **128 unchanged**, **1 extended**, **57 new** construct(s).

Unchanged constructs render byte-identically, so their tables are untouched by a rebuild. The files listed under *extended* are the ones that genuinely changed.

## Unchanged (128)

`hub_address`, `hub_address_type`, `hub_contact_type`, `hub_phone_number_type`, `hub_country_region`, `hub_state_province`, `hub_department`, `hub_shift`, `hub_job_candidate`, `hub_product`, `hub_product_category`, `hub_product_subcategory`, `hub_product_model`, `hub_culture`, `hub_unit_measure`, `hub_product_description`, `hub_product_photo`, `hub_illustration`, `hub_document`, `hub_location`, `hub_work_order`, `hub_work_order_operation`, `hub_scrap_reason`, `hub_inventory_transaction`, `hub_product_review`, `hub_purchase_order`, `hub_purchase_order_line`, `hub_ship_method`, `link_business_entity_address`, `link_business_entity_contact`, `link_business_entity_phone_number_type`, `link_address_state_province`, `link_state_province_country_region`, `link_business_entity_department_shift`, `link_job_candidate_business_entity`, `link_product_subcategory`, `link_product_subcategory_category`, `link_product_product_model`, `link_product_unit_measure`, `link_product_model_description_culture`, `link_product_product_photo`, `link_product_model_illustration`, `link_product_document`, `link_document_business_entity`, `link_product_assembly_component`, `link_product_location`, `link_work_order_product`, `link_work_order_scrap_reason`, `link_work_order_operation`, `link_inventory_transaction_product`, `link_product_review_product`, `link_purchase_order_business_entity_ship_method`, `link_purchase_order_line`, `link_product_vendor`, `link_purchase_order_line_product`, `link_purchase_order_business_entity`, `sat_business_entity_details`, `sat_business_entity_person_name`, `sat_business_entity_person_consent`, `sat_business_entity_person_sensitive`, `sat_business_entity_email`, `sat_business_entity_credential`, `sat_business_entity_phone_number_type_numbers`, `sat_business_entity_address_details`, `sat_business_entity_contact_details`, `sat_address_details`, `sat_address_location`, `sat_address_type_details`, `sat_contact_type_details`, `sat_phone_number_type_details`, `sat_country_region_details`, `sat_state_province_details`, `sat_state_province_territory`, `sat_business_entity_employee_identifiers`, `sat_business_entity_employee_job`, `sat_business_entity_employee_personal`, `sat_business_entity_employee_leave`, `sat_business_entity_employee_hierarchy`, `sat_business_entity_employee_pay`, `sat_department_details`, `sat_shift_details`, `sat_business_entity_department_shift_effectivity`, `sat_business_entity_department_shift_details`, `sat_job_candidate_resume`, `sat_product_details`, `sat_product_pricing`, `sat_product_inventory_policy`, `sat_product_lifecycle`, `sat_product_cost_history`, `sat_product_list_price_history`, `sat_product_category_details`, `sat_product_subcategory_details`, `sat_product_model_catalog`, `sat_product_model_instructions`, `sat_culture_details`, `sat_unit_measure_details`, `sat_product_description_details`, `sat_product_photo_thumbnail`, `sat_product_photo_large`, `sat_product_product_photo_details`, `sat_illustration_details`, `sat_document_details`, `sat_document_revision`, `sat_document_content`, `sat_product_assembly_component_effectivity`, `sat_product_assembly_component_details`, `sat_location_details`, `sat_product_location_inventory`, `sat_work_order_quantities`, `sat_work_order_schedule`, `sat_work_order_operation_schedule`, `sat_work_order_operation_cost`, `sat_scrap_reason_details`, `sat_inventory_transaction_details`, `sat_inventory_transaction_archive_details`, `sat_product_review_details`, `sat_product_review_reviewer_pii`, `sat_business_entity_vendor_details`, `sat_business_entity_vendor_status`, `sat_purchase_order_status`, `sat_purchase_order_dates`, `sat_purchase_order_totals`, `sat_purchase_order_line_terms`, `sat_purchase_order_line_receipt`, `sat_product_vendor_terms`, `sat_product_vendor_running_values`, `sat_ship_method_rates`, `sat_ship_method_identifiers`

## Extended (1)

- **hub_business_entity** — 3 source feed(s): Store.BusinessEntityID, SalesPerson.BusinessEntityID, SalesPersonQuotaHistory.BusinessEntityID; 5 new satellite(s): sat_business_entity_store_details, sat_business_entity_store_demographics, sat_business_entity_sales_person_compensation, sat_business_entity_sales_person_running_totals, sat_business_entity_sales_quota_history
  - changed file: `models/raw_vault/hub_business_entity.sql`

## New (57)

- **hub_customer**
- **hub_sales_order**
- **hub_sales_order_line**
- **hub_sales_territory**
- **hub_credit_card**
- **hub_currency**
- **hub_currency_rate**
- **hub_special_offer**
- **hub_sales_reason**
- **hub_shopping_cart_item**
- **hub_sales_tax_rate**
- **link_customer_business_entity**
- **link_customer_sales_territory**
- **link_business_entity_store_sales_person**
- **link_business_entity_sales_territory**
- **link_business_entity_sales_territory_history**
- **link_sales_order_header**
- **link_sales_order_currency_rate**
- **link_sales_order_line**
- **link_sales_order_sales_reason**
- **link_credit_card_business_entity**
- **link_special_offer_product**
- **link_country_region_currency**
- **link_currency_rate_currency**
- **link_sales_tax_rate_state_province**
- **link_sales_territory_country_region**
- **link_shopping_cart_item_product**
- **link_sales_order_line_product**
- **link_sales_order_address**
- **link_sales_order_business_entity**
- **link_sales_order_ship_method**
- **sat_customer_details** — on `hub_customer`
- **sat_business_entity_store_details** — on `hub_business_entity`
- **sat_business_entity_store_demographics** — on `hub_business_entity`
- **sat_business_entity_sales_person_compensation** — on `hub_business_entity`
- **sat_business_entity_sales_person_running_totals** — on `hub_business_entity`
- **sat_business_entity_sales_quota_history** — on `hub_business_entity`
- **sat_business_entity_sales_territory_history_effectivity** — on `link_business_entity_sales_territory_history`
- **sat_sales_order_status** — on `hub_sales_order`
- **sat_sales_order_dates** — on `hub_sales_order`
- **sat_sales_order_totals** — on `hub_sales_order`
- **sat_sales_order_references** — on `hub_sales_order`
- **sat_sales_order_payment** — on `hub_sales_order`
- **sat_sales_order_line_pricing** — on `hub_sales_order_line`
- **sat_sales_order_line_shipment** — on `hub_sales_order_line`
- **sat_sales_reason_details** — on `hub_sales_reason`
- **sat_sales_territory_details** — on `hub_sales_territory`
- **sat_sales_territory_financials** — on `hub_sales_territory`
- **sat_credit_card_details** — on `hub_credit_card`
- **sat_credit_card_expiry** — on `hub_credit_card`
- **sat_currency_details** — on `hub_currency`
- **sat_currency_rate_details** — on `hub_currency_rate`
- **sat_special_offer_details** — on `hub_special_offer`
- **sat_special_offer_discount** — on `hub_special_offer`
- **sat_special_offer_validity** — on `hub_special_offer`
- **sat_sales_tax_rate_details** — on `hub_sales_tax_rate`
- **sat_shopping_cart_item_details** — on `hub_shopping_cart_item`
