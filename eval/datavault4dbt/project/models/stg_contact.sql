{%- set yaml_metadata -%}
source_model:
  probe: contact
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_contact_h:
    - contactid
  hd_contact_s:
    is_hashdiff: true
    columns:
      - segment
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
