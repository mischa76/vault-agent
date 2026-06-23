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

-- (2) Ownership history for the transferred account ACC-503 — join the effectivity
-- satellite back to the business keys via the link's hash keys.
-- select
--     acc.account_number,
--     cust.national_customer_id,
--     eff.effective_from,
--     eff.effective_to
-- from {{ ref('sat_account_customer_eff') }} eff
-- join {{ ref('hub_account') }}  acc  on acc.account_hk  = eff.account_hk
-- join {{ ref('hub_customer') }} cust on cust.customer_hk = eff.customer_hk
-- where acc.account_number = 'ACC-503'
-- order by eff.effective_from;
