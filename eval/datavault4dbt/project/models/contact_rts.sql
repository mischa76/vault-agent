{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
tracked_hashkey: hk_contact_h
source_models:
  stg_contact:
    rsrc_static: dv4x_src.contact
{%- endset -%}
{{ datavault4dbt.rec_track_sat(yaml_metadata=yaml_metadata) }}
