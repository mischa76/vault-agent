{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
source_model: stg_customer
tracked_hashkey: hk_customer_business_entity_l
source_is_single_batch: false
{%- endset -%}
{{ datavault4dbt.eff_sat_v0(yaml_metadata=yaml_metadata) }}
