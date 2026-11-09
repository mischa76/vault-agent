{{ config(materialized='incremental') }}
{{ datavault4dbt.control_snap_v0(start_date='2026-01-01', daily_snapshot_time='07:00:00') }}
