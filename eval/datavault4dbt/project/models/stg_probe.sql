{%- set yaml_metadata -%}
source_model:
  probe: probe
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_probe_h:
    - probeid
  hd_probe_s:
    is_hashdiff: true
    columns:
      - doc
      - pos
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
