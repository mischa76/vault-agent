# WP10 — Multi-source hub: business-key harmonisation across sources

Status: Accepted for implementation (2026-07-13, split out of the WP9 draft per maintainer
decision) · Size: M/L · Depends on: WP9 (mapping) · Evidence:
[`spike-mapping-results.md`](./spike-mapping-results.md) thin-evidence #5 + Q6

## 1. Problem

The canonical DV2.0 integration case — *one* business key living in several source systems
(`Q_A.partner.partner_id`, `Q_B.customer.customer_id` → one `hub_customer`) — is not
representable: `state.Hub` carries a single `business_key`/`source_entity`, and
`_render_hub` emits one `source_model` + one `src_nk`. Without it, WP9's multi-candidate
key output has nowhere to land (it parks in `unresolved`), and the hub's defining property
(integration point on the business key, Linstedt) cannot be exercised across sources.

## 2. Design

### 2.1 Model
`state.Hub` gains `sources: list[HubSource] = []` with
`HubSource(source_table: str, business_key_column: str)` — per feeding source, the physical
key column. Empty list = today's single-source behaviour (**byte-identity guard, pinned
first**). Normalisation/union handling mirrors the WP8 `LinkHubRef` pattern so existing
YAML/tool schemas/tests stay valid.

### 2.2 Canonical key name (maintainer policy, decided 2026-07-13)
When the feeding sources disagree on the physical key column name, the canonical staging
name is a **business term** (normalised from `hub.business_key`, e.g. `CUSTOMER_ID`); when
a single source feeds the hub, the source name is kept (no gratuitous rename — consistent
with WP9 §6). The canonical name is computed in ONE place in `rules/dv2_rules.py`
(`canonical_hub_key_column(hub) -> str`).

### 2.3 Staging + generator
- `staging_generator`: one `stg_<entity>_<source>` per `HubSource`, each aliasing its
  `business_key_column` to the canonical name via `derived_columns`, hashing that to
  `X_HK` — the same key value hashes identically in every feeding stage (the integration
  property).
- `_render_hub`: `source_model` becomes a **list** of the per-source staging models
  (AutomateDV's `hub` macro unions a source_model list — verify against the pinned
  0.11.4 docs, not memory); `src_nk` = canonical name.
- Satellites on a multi-source hub: **one satellite per source**
  (`sat_<entity>_<source>`, split by `record_source`), each keeping its own source column
  names (spike Q6 answer; value harmonisation stays in the Business Vault, ADR-0007).
- Validator: a multi-source hub whose `HubSource` tables are not in the declared schema →
  the existing grounding warnings apply per source; two `HubSource`s naming the same
  (table, column) → error (duplicate feed).

### 2.4 Mapping hand-off (from WP9)
When WP9's mapper returns a multi-candidate key where **both** candidates are legitimate
feeds (the `ambiguous`-with-both-loaded case), ratification may resolve it into
`Hub.sources` entries via `mappings.review.yml` — the ratification file gains an optional
`sources:` form for key concepts. Genuinely uncertain candidates stay `unresolved`.

### 2.5 Explicitly deferred
Same-as links (keys asserted equivalent but *differing*, e.g. the ~70%-maintained
`PARTN_NR ↔ ExternalCustomerNo` bridge in the messy case) — flag, never force into one
hub. Own WP when needed.

## 3. Tests

Pinned-first byte-identity for single-source hubs (model + staging + hub SQL) · two-source
hub generates two stages whose canonical-key hash inputs are identical for the same key
value · `_render_hub` emits a source_model list · sat-per-source naming + record_source
split · duplicate-feed validator error · ratification `sources:` round-trip.

## 4. Acceptance criteria

1. A hub fed by two sources with different physical key columns builds ONE hub: the same
   key value loaded through either staging model resolves to one `hub_customer` row —
   **verified on Postgres** (load from both stages, assert row count and matching `X_HK`).
2. Satellites split per source, keeping source column names.
3. Single-source models byte-identical (guard pinned before any change).
4. Canonical-name policy honoured: business term only when sources disagree.
5. Suite + ruff + mypy green; CLAUDE.md milestone; demo README notes the scenario if the
   bank demo is extended (optional — a test-fixture Postgres proof suffices).
