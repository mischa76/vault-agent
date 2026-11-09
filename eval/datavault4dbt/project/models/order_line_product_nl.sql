{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
link_hashkey: hk_order_line_product_l
foreign_hashkeys:
  - hk_order_line_h
  - hk_product_h
payload:
  - qty
source_models: stg_order_line
{%- endset -%}
{{ datavault4dbt.nh_link(yaml_metadata=yaml_metadata) }}
