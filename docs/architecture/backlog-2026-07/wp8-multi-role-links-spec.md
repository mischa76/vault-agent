# WP8 — Role-qualified link hub references (self-referencing links)

Status: Proposed (includes draft ADR-0009 — get the ADR accepted before coding) ·
Size: L · Depends on: WP1, WP7

## 1. Problem (reality-test #5; poc spec §9 "self-referencing links")

`Link.connected_hubs: list[str]` cannot express one hub participating twice in different
roles — e.g. a transaction linking `hub_account` (payer) to `hub_account` (counterparty).
Today such a relationship is unmodelable: the modeler either drops a hub or produces a
2-element list with a duplicate the generator collapses (both FKs named `ACCOUNT_HK`).

## 2. Draft ADR-0009 (to be filed in docs/architecture/adrs/)

**Decision:** extend link hub references with an optional role qualifier; role-qualify the
generated FK column names; keep the plain-string form 100 % backward compatible.

**Alternatives rejected:** (a) duplicating hubs per role (violates "one hub per business
key"); (b) free-text column overrides on the link (bypasses the naming rules);
(c) modeling the second role as a separate link (splits one Unit of Work).

## 3. Model change [ENFORCE]

```python
class LinkHubRef(BaseModel):
    hub: str                 # hub name, e.g. "hub_account"
    role: str | None = None  # e.g. "counterparty"; None = unqualified

class Link(BaseModel):
    connected_hubs: list[str | LinkHubRef]   # str coerces to LinkHubRef(hub=str)
```

Implementation notes:

- Add a pydantic `field_validator(mode="before")` normalising every entry to `LinkHubRef`
  so downstream code sees exactly one shape; the *declared* type stays the union so LLM
  tool schemas and existing YAML/tests keep working with plain strings.
- `driving_key: list[str]` entries may name either a hub (`"hub_account"`, matches the
  unqualified ref) or `"hub_account:counterparty"` (role-qualified). Add
  `Link.resolve_driving_refs() -> list[LinkHubRef]` as the single resolution point.
- Serialisation: `model_dump()` must round-trip through the checkpointer (serde picks the
  models up automatically) and stay readable in metadata YAML.

## 4. Naming rules (`rules/dv2_rules.py`)

Single source of truth, used by generator + staging + validator:

```python
def role_fk_column(hub_hashkey: str, role: str | None) -> str:
    """ACCOUNT_HK + 'counterparty' -> COUNTERPARTY_ACCOUNT_HK; None -> unchanged."""
```

Role is normalised with `normalize_identifier` and prefixed. Business-key source columns
get the same treatment in staging (`role_bk_column(bk_col, role)` →
`COUNTERPARTY_ACCOUNT_NUMBER`): a self-referencing raw table necessarily carries the two
participations as two columns — the role prefix is the documented expectation, and an
unmatched grounded column is exactly what `W_BK_NOT_IN_SOURCE`-style warnings are for
(add `W_ROLE_BK_NOT_IN_SOURCE` mirroring it when grounded).

## 5. Ripple-through (each with tests)

- **code_generator:** `_render_link`/`_render_nh_link` FKs via `role_fk_column`;
  link hashkey unchanged (link name based). eff_sat driving/secondary FK split works on
  resolved refs (role-qualified driving keys select the role-qualified FK).
- **staging_generator:** hashed columns per ref: `role_fk_column(hub_hk, role)` hashed
  from `role_bk_column(bk, role)`; link HK hashes the role-qualified BK columns in
  declared order; `expected columns` in sources.yml/README show the role-qualified names.
- **validator:** adapt `E_LINK_UNKNOWN_HUB`, `E_DRIVING_KEY_NOT_IN_LINK` (driving ref must
  match a connected ref incl. role), `W_LINK_REDUNDANT_GRAIN` (grain key = multiset of
  (hub, role)); new `E_LINK_DUP_ROLE`: two refs with identical (hub, role) — the case
  roles exist to disambiguate.
- **dv2_modeler prompt [GUIDE]:** one rule line: "when one hub participates twice in a
  relationship, qualify each participation with a role (e.g. payer/counterparty) instead
  of dropping or duplicating it". Tool schema updates automatically from the model.
- **adr_author:** render refs as `hub_account (counterparty)`.
- **data_contract / orchestrator:** no changes expected — verify, don't assume.

## 6. Demo extension (proof, mirrors the eff_sat pattern)

Extend `demo/bank_postgres` with a transactional self-referencing link:
`link_transfer` connecting `hub_account` (unqualified) + `hub_account` (role
`counterparty`), payload amount/currency, seed `raw_transfer.csv` with
`ACCOUNT_NUMBER, COUNTERPARTY_ACCOUNT_NUMBER, …`. `build_vault_models.py` + guardrail
test + README section; verify green on Postgres (`dbt build`) before closing the WP.

## 7. Acceptance criteria

1. Plain-string links behave byte-identically (regression guard on the bank demo:
   regenerated models unchanged except the new link).
2. A self-referencing link generates distinct, role-prefixed FK columns end-to-end
   (raw vault + staging + metadata + ADR) and builds green on Postgres.
3. Validator catches duplicate (hub, role) pairs and role-aware driving-key mismatches.
4. ADR-0009 accepted and filed; CLAUDE.md milestone updated. Standard DoD.
