{%- set yaml_metadata -%}
source_model:
  probe: order_line
ldts: load_datetime
rsrc: record_source
prejoined_columns:
  productnumber:
    src_name: probe
    src_table: product
    bk: productnumber
    this_column_name: productid
    ref_column_name: productid
hashed_columns:
  hk_order_line_h:
    - orderlineid
  hk_product_h:
    - productnumber
  hk_order_day_h:
    - orderdate
  hk_order_guid_h:
    - rowguid
  hk_order_line_product_l:
    - orderlineid
    - productnumber
  hk_order_line_day_l:
    - orderlineid
    - orderdate
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
