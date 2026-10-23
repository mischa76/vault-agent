-- Generated zero-key rows for hub_customer (WP86): a link whose participant is missing
-- carries the zero key; these rows give it a hub row to join.
{{ config(materialized='view') }}
SELECT CAST('-1' AS varchar) AS NATIONAL_CUSTOMER_ID, CAST('1900-01-01' AS timestamp) AS LOAD_DATETIME, CAST('SYSTEM' AS varchar) AS RECORD_SOURCE
UNION ALL
SELECT CAST('-2' AS varchar) AS NATIONAL_CUSTOMER_ID, CAST('1900-01-01' AS timestamp) AS LOAD_DATETIME, CAST('SYSTEM' AS varchar) AS RECORD_SOURCE
