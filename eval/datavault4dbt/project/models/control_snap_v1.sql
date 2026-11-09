{{ config(materialized="view") }}
{{ datavault4dbt.control_snap_v1(control_snap_v0="control_snap_v0") }}
