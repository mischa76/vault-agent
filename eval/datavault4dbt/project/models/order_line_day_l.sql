{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
link_hashkey: hk_order_line_day_l
foreign_hashkeys:
  - hk_order_line_h
  - hk_order_day_h
source_models: stg_order_line
{%- endset -%}
{{ datavault4dbt.link(yaml_metadata=yaml_metadata) }}
