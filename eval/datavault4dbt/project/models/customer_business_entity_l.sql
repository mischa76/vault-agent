{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
link_hashkey: hk_customer_business_entity_l
foreign_hashkeys:
  - hk_customer_h
  - hk_person_business_entity_h
  - hk_store_business_entity_h
source_models: stg_customer
{%- endset -%}
{{ datavault4dbt.link(yaml_metadata=yaml_metadata) }}
