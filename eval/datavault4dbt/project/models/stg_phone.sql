{%- set yaml_metadata -%}
source_model:
  probe: phone
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_contact_h:
    - contactid
  hd_contact_phone_s:
    is_hashdiff: true
    columns:
      - phonenumber
multi_active_config:
  multi_active_key: phonetype
  main_hashkey_column: hk_contact_h
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
