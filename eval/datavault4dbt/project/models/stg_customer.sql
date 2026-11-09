{%- set yaml_metadata -%}
source_model:
  probe: customer
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_customer_h:
    - customerid
  hk_person_business_entity_h:
    - personid
  hk_store_business_entity_h:
    - storeid
  hk_customer_business_entity_l:
    - customerid
    - personid
    - storeid
  hd_customer_s:
    is_hashdiff: true
    columns:
      - segment
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
