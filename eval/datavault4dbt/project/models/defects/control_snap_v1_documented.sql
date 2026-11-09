-- Defect 2 (C56): control_snap_v1.md's own example. forever: 'TRUE' (a string) fails the macros'
-- `is true` test and compiles to INTERVAL ' ' on PostgreSQL; the boolean true builds.
{{ config(materialized='view') }}
{{ datavault4dbt.control_snap_v1(
    control_snap_v0='control_snap_v0',
    log_logic={
        'daily':   {'duration': 3, 'unit': 'MONTH'},
        'weekly':  {'duration': 1, 'unit': 'YEAR'},
        'monthly': {'duration': 5, 'unit': 'YEAR'},
        'yearly':  {'forever': 'TRUE'}
    }
) }}
