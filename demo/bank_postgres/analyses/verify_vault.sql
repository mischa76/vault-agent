-- Verification query for the bank Durchstich (spec §8). Run with:
--   uv run dbt compile --select verify_vault   (then run target/compiled/.../verify_vault.sql)
-- or paste the body straight into psql. It shows (1) row counts per vault table — every
-- one must be > 0 — and (2) the ownership history of the transferred account ACC-503.

-- (1) Row counts per vault table.
select 'hub_customer'             as vault_table, count(*) as rows from {{ ref('hub_customer') }}
union all select 'hub_account',              count(*) from {{ ref('hub_account') }}
union all select 'link_account_customer',    count(*) from {{ ref('link_account_customer') }}
union all select 'sat_customer_details',     count(*) from {{ ref('sat_customer_details') }}
union all select 'sat_account_details',      count(*) from {{ ref('sat_account_details') }}
union all select 'sat_account_customer_eff', count(*) from {{ ref('sat_account_customer_eff') }}
order by vault_table;

-- (2) End-dating of the transferred account ACC-503 — the effectivity satellite's signature
-- behaviour. After the two-phase load (README → "Phase B2"), the first owner (CH-1001) is
-- closed to the transfer date and the new owner (CH-1002) stays open. AutomateDV's eff_sat is
-- append-only, so it INSERTS a closing record rather than updating in place; the CURRENT view
-- is the latest record per relationship (by LOAD_DATETIME).
-- Expected after Phase B2:
--   CH-1001 | 2026-01-01 | 2026-04-01   (closed at the transfer date)
--   CH-1002 | 2026-04-01 | 9999-12-31   (open)
-- with ranked as (
--     select
--         cust.national_customer_id,
--         eff.effective_from,
--         eff.effective_to,
--         row_number() over (partition by eff.account_hk, eff.customer_hk
--                            order by eff.load_datetime desc) as rn
--     from {{ ref('sat_account_customer_eff') }} eff
--     join {{ ref('hub_account') }}  acc  on acc.account_hk  = eff.account_hk
--     join {{ ref('hub_customer') }} cust on cust.customer_hk = eff.customer_hk
--     where acc.account_number = 'ACC-503'
-- )
-- select national_customer_id, effective_from, effective_to
-- from ranked where rn = 1 order by effective_from;
