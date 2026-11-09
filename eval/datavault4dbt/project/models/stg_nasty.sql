{%- set yaml_metadata -%}
source_model:
  probe: nasty
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_nasty_h:
    - k1
    - k2
  hd_nasty_s:
    is_hashdiff: true
    columns:
      - attr
      - k1
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
