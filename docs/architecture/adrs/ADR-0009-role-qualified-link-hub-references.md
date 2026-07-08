# ADR-0009: Role-qualified link hub references (self-referencing links)

**Status:** Accepted (2026-07-08)
**Date:** 2026-07-08
**Decision makers:** Mischa Eismann

## Context

`Link.connected_hubs: list[str]` cannot express one hub participating twice in a
relationship under different roles — the canonical case being a transfer/transaction
linking `hub_account` (payer side) to `hub_account` (counterparty side). Today such a
relationship is unmodelable: the modeler either drops one participation or emits a
duplicate hub name whose generated FK columns collide (both would be `ACCOUNT_HK`).
Recorded as a modeling-capability gap since the Postgres Durchstich
(poc-end-to-end-dbt-spec §9, reality-test #5); the transactional-link demo scope was
deferred for exactly this reason.

Data Vault 2.0 handles this with role-playing participations: the link references the
same hub more than once, and the physical FK columns are disambiguated by a role prefix
(Linstedt/Olschimke; hierarchical and same-as links are the canon's own examples of one
hub participating twice). The model layer must be able to express what the physical
layer needs to render.

## Decision

Extend link hub references with an **optional role qualifier**, keeping the plain-string
form 100 % backward compatible:

```python
class LinkHubRef(BaseModel):
    hub: str                 # hub name, e.g. "hub_account"
    role: str | None = None  # e.g. "counterparty"; None = unqualified

class Link(BaseModel):
    connected_hubs: list[str | LinkHubRef]  # str coerces to LinkHubRef(hub=str)
```

- A `before`-mode validator normalises every entry to `LinkHubRef`, so downstream code
  sees exactly one shape; plain strings stay valid everywhere (tool schemas, YAML,
  existing tests, checkpoints).
- **Naming rule** (single source of truth in `rules/dv2_rules.py`): a role prefixes the
  normalised FK column and its staging business-key column —
  `role_fk_column("ACCOUNT_HK", "counterparty") == "COUNTERPARTY_ACCOUNT_HK"`,
  `role_bk_column("ACCOUNT_NUMBER", "counterparty") == "COUNTERPARTY_ACCOUNT_NUMBER"`.
  Unqualified refs render exactly as today (byte-identical output for all existing
  models — regression-pinned).
- `driving_key` entries may name a hub (matches the unqualified ref) or
  `"hub:role"` (role-qualified); one resolution helper on `Link` is the single
  interpretation point.
- Validator: duplicate `(hub, role)` pairs become an error (`E_LINK_DUP_ROLE`); the
  existing link gates (unknown hub, driving-key subset, redundant grain) become
  role-aware.
- The modeler prompt gains one [GUIDE] rule: qualify repeated participations with roles
  instead of dropping or duplicating them. The tool schema follows the pydantic model
  automatically.
- Proof obligation: the bank demo gains a self-referencing transactional `link_transfer`
  (`hub_account` + `hub_account` as `counterparty`), built green on Postgres before the
  change is considered done.

## Alternatives considered

- **Duplicate hubs per role** (e.g. `hub_counterparty_account`): violates "one hub per
  business key" — the counterparty IS an account; splitting it breaks integration on the
  business key and doubles satellite maintenance. Rejected.
- **Free-text FK column overrides on the link:** bypasses the naming rules that keep
  generator, staging, and validator provably consistent; unreviewable. Rejected.
- **A second link per role:** splits one atomic Unit of Work across links, violating the
  UoW rule the modeler is steered by. Rejected.
- **Full role objects with cardinality/semantics:** over-engineering at this stage; roles
  are a naming/disambiguation concern in the Raw Vault. Revisit only if Business-Vault
  work (ADR-0007 assist tier) demands richer semantics.

## Consequences

- Positive: self-referencing and multi-role relationships become expressible end-to-end
  (model → validator → raw vault → staging → ADR) with deterministic, rule-derived
  column names; the known Durchstich gap closes with a Postgres-verified demo.
- Positive: zero migration — existing models, checkpoints, and prompts keep working;
  plain-string links render byte-identically.
- Negative: `connected_hubs` becomes a union type; every consumer must go through the
  normalised `LinkHubRef` shape (enforced by the model validator, but it is a ripple
  through generator, staging, validator, and ADR author — sized L in the backlog).
- Neutral: grounded source schemas are expected to carry the role-prefixed BK columns
  (e.g. `COUNTERPARTY_ACCOUNT_NUMBER`); a grounded mismatch surfaces as the usual
  not-in-source warning, never a silent guess.

## Implementation

Spec: `docs/architecture/backlog-2026-07/wp8-multi-role-links-spec.md` (WP8) — model
change, naming helpers, ripple-through with tests, demo extension. Implementation starts
only after this ADR is Accepted.
