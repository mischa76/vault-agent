{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
tracked_entity: customer_h
hashkey: hk_customer_h
sat_names:
  - customer_s
snapshot_relation: control_snap_v1
dimension_key: hk_customer_d
{%- endset -%}
{{ datavault4dbt.pit(yaml_metadata=yaml_metadata) }}
