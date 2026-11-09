{%- set yaml_metadata -%}
source_model:
  probe: product
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_product_h:
    - productnumber
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
