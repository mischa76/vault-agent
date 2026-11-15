-- Generated zero-key rows for hub_product (WP86): a link whose participant is missing
-- carries the zero key; these rows give it a hub row to join.
-- depends_on: {{ ref('stg_product') }}
{{ config(materialized='view') }}
{%- set types = {} -%}
{%- if execute -%}
{%- for c in adapter.get_columns_in_relation(ref('stg_product')) -%}
{%- do types.update({c.name | upper: c.data_type}) -%}
{%- endfor -%}
{%- endif %}
SELECT CAST('-1' AS {{ types.get('PRODUCTNUMBER', 'varchar') }}) AS PRODUCTNUMBER, CAST('1900-01-01' AS timestamp) AS LOAD_DATETIME, CAST('SYSTEM' AS varchar) AS RECORD_SOURCE
UNION ALL
SELECT CAST('-2' AS {{ types.get('PRODUCTNUMBER', 'varchar') }}) AS PRODUCTNUMBER, CAST('1900-01-01' AS timestamp) AS LOAD_DATETIME, CAST('SYSTEM' AS varchar) AS RECORD_SOURCE
