-- Hand-authored AutomateDV staging model (WP8, ADR-0009) for the self-referencing
-- transfer table. A transfer connects hub_account twice — the paying account and the
-- COUNTERPARTY account — so the two participations are role-qualified: the counterparty
-- FK and its source business-key column carry a COUNTERPARTY_ prefix
-- (rules.role_fk_column / role_bk_column). ACCOUNT_HK is hashed from ACCOUNT_NUMBER,
-- COUNTERPARTY_ACCOUNT_HK from COUNTERPARTY_ACCOUNT_NUMBER, and the transactional link's
-- own hash key from both in declared order.
--
-- Mirrors what the staging generator emits for this model (byte-identical hashed_columns);
-- kept hand-authored alongside the other demo stg_* models. No load_batch filter is needed
-- here — a transfer is a non-historized event, inserted once and never end-dated.
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'raw_transfer'
hashed_columns:
  ACCOUNT_HK: 'ACCOUNT_NUMBER'
  COUNTERPARTY_ACCOUNT_HK: 'COUNTERPARTY_ACCOUNT_NUMBER'
  LINK_TRANSFER_HK:
    - 'ACCOUNT_NUMBER'
    - 'COUNTERPARTY_ACCOUNT_NUMBER'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}
{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
