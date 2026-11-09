{%- set yaml_metadata -%}
source_model:
  probe: vendor
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_business_entity_h:
    - vendorid
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
