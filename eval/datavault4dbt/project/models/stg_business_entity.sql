{%- set yaml_metadata -%}
source_model:
  probe: business_entity
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_business_entity_h:
    - businessentityid
  hd_business_entity_s:
    is_hashdiff: true
    columns:
      - name
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
