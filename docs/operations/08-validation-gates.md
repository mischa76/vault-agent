# 8. Validation gates reference

Derived from `validator.py`, which is the source of truth for both the set and its size.
This page deliberately states no total: a count in prose has been wrong here more than
once. To list the current codes:

```bash
rg -o 'E_[A-Z0-9_]+|W_[A-Z0-9_]+' src/vault_agent/agents/validator.py | sort -u
```

If that list and this page disagree, the list wins — and the page is the thing to fix.

## 8.1 How to read a gate

An **`E_` error** blocks: inside the run it feeds the re-model loop (the modeler
retries with errors as feedback), and one that survives the loop blocks finalization
at the checkpoint. A **`W_` warning** advises: it appears in the review queue and the
report, never blocks, and is *not* fed back to the modeler. The dividing philosophy:
a gate fails only what is **provable** from the model or artifacts alone; heuristic
suspicions — however strong — warn. Codes are stable identifiers: scripts and humans
match on the code, never on message text.

## 8.2 Catalogue

### Model & artifact integrity

| Code | Meaning · typical fix |
|------|----------------------|
| `E_NO_HUBS` | The model has no hubs — nothing to validate. Usually a requirements document the parser could not extract entities from; check the document and the trace. |
| `E_DUP_NAME` | Two constructs share one name. Naming collision in the modeler's proposal; re-model usually clears it. |
| `E_BAD_NAME` | A construct name is not `hub_`/`link_`/`sat_` + lowercase snake_case. The name becomes a dbt model name *and* a file on disk, so a space, an uppercase letter or a path separator is caught here rather than at build time or in the writer (which refuses, never renames). Steered by the `construct_naming` rule. |
| `E_MISSING_COLUMN` | A generated construct lacks a DV-required column (hash key, load datetime, record source, hashdiff). Guards the generator's own output — seeing it indicates a generator bug, not a modeling error. |

### Hubs & business keys

| Code | Meaning · typical fix |
|------|----------------------|
| `E_HUB_NO_BK` | Hub without a business key. The concept isn't identifiable; the requirements likely describe an attribute cluster, not an entity. |
| `E_DUP_HUB` | Same business key on the same source entity in ≥2 hubs — one concept modelled twice. Merge to exactly one hub per business key. |
| `E_HUB_HK_COLLISION` | Hubs share a source entity but differ in business key: they would derive the same `X_HK` column and staging model, silently cross-binding keys (diagram in 2.4). Split the source entities or unify the key. |
| `E_HUB_DUP_FEED` | A multi-source hub declares the same (table, column) feed twice. Each `HubSource` must be distinct. |
| `W_HUB_NO_SAT` | Hub has no satellite — no descriptive data captured. Legitimate for pure reference hubs; otherwise attributes went missing. |
| `W_BK_COLLISION_RISK` | Different source entities share one business-key name across hubs. Confirm whether a collision code (source differentiation) is needed before values from different systems merge. |

### Links, roles & driving keys

| Code | Meaning · typical fix |
|------|----------------------|
| `E_LINK_TOO_FEW_HUBS` | Link connects <2 hub participations. A one-sided "relationship" is usually a satellite in disguise. |
| `E_LINK_UNKNOWN_HUB` | Link references a hub that doesn't exist in the model. |
| `E_LINK_DUP_ROLE` | The same hub participates twice with the same (or no) role. Qualify each repeated participation with a distinct role (payer/counterparty). |
| `E_DRIVING_KEY_NOT_IN_LINK` | The declared driving key names participations the link doesn't have (role-aware: `hub:role` must match an actual participation). |
| `E_TXNLINK_NO_TIMESTAMP` | Transactional link without an event timestamp — `t_link` needs it to order events. |
| `W_LINK_REDUNDANT_GRAIN` | Two links connect the same participations with the same type: likely one unit of work modelled twice, or a grain error. |

### Satellites & splitting

| Code | Meaning · typical fix |
|------|----------------------|
| `E_SAT_UNKNOWN_PARENT` | Satellite parent is neither a known hub nor link. |
| `E_SAT_NO_PAYLOAD` | Satellite with no attributes. Empty payload means nothing to historise — drop it or find its attributes. |
| `E_SAT_DUP_ATTR` | Two attribute labels (or an attribute and a CDK label) normalise to the same column — the warehouse would reject the duplicate (example in 2.4). The modeler's CDK backstop repairs the common case before this gate. |
| `E_SAT_ATTR_OVERLAP` | The same attribute appears in several satellites of one parent — an update would fork history. Matched on the *normalised* label, like `E_SAT_DUP_ATTR`: "Customer ID" in one satellite and `customer_id` in another are one column on that parent. Assign each attribute to exactly one satellite. |
| `E_MASAT_NO_CDK` | Multi-active satellite without a child dependent key — concurrent rows would be indistinguishable. |
| `W_SAT_WIDE` | More than 30 attributes: a smell for mixed rates of change / sources / classifications. Consider splitting along the four axes (2.2). |
| `W_MASAT_SHARED_GRAIN` | Multi-active satellite without its own `source_table` — sharing the parent's staging assumes equal grain, which multi-active data rarely has. Declare the finer-grained relation or confirm the shared source. |
| `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` | Satellite declares a `source_table` that is **not one of its multi-source parent's feeds**. Naming a feed is fine and is the canonical shape (ADR-0011): the satellite binds to that source system and is generated once. Naming anything else is an error, because a finer-grain relation *under* one feed cannot say which feed it belongs to. The message lists the available feeds. *Narrowed by ADR-0011 (2026-07-29); WP24 originally rejected every `source_table` on a multi-source hub.* |

### Effectivity

| Code | Meaning · typical fix |
|------|----------------------|
| `E_EFFSAT_DATES` | Effectivity satellite must carry exactly two date attributes (start, end); more or fewer can't be generated. |
| `E_EFFSAT_DATE_ORDER` | The two dates are recognisably reversed (read positionally as start/end — example in 2.4). Swap them. |
| `E_EFFSAT_NO_DRIVING_KEY` | The parent link declares no driving key — end-dating is undefined without knowing which side stays fixed. |
| `E_EFFSAT_PARENT_NOT_LINK` | Effectivity satellite on a hub: active periods describe relationships; hang it off the link. |
| `W_EFFSAT_DATE_ORDER_UNVERIFIED` | The date tokens don't match the known from/to vocabulary, so order can't be verified either way. Confirm manually — a heuristic non-match never hard-fails. |
| `W_SAT_MAYBE_EFFECTIVITY` | A *standard* satellite on a link carries a from/to date pair — probably a mis-modelled effectivity satellite. Re-model with `sat_type=effectivity` and the link's driving key, or confirm it's genuine payload. |

### Grounding (only with a declared source schema)

All four are warnings by design — a declared schema may be partial, so an unmatched
name is a prompt to verify, not proof of error.

| Code | Meaning · typical fix |
|------|----------------------|
| `W_BK_NOT_IN_SOURCE` | A hub's business key matches no declared column. |
| `W_HUBSOURCE_BK_NOT_IN_SOURCE` | A multi-source feed's physical key column isn't in the schema. |
| `W_ROLE_BK_NOT_IN_SOURCE` | A role-qualified participation expects a role-prefixed source column (e.g. `COUNTERPARTY_ACCOUNT_NUMBER`) that isn't declared — self-referencing raw tables carry each participation as its own column. |
| `W_ATTR_NOT_IN_SOURCE` | A satellite attribute matches no declared column. |

In every case: either the model names something the source truly doesn't have (fix the
model or map it in ratification), or the schema declaration is incomplete (complete
it).

### Extension mode (only with `run --existing`)

Inert on a greenfield run. These compare the merged model against the vault that
already exists, and they all defend one promise: an extension adds, it never migrates.
What the existing vault has, it keeps — because the alternative is a rename or a
backfill against tables that hold history.

| Code | Meaning · typical fix |
|------|----------------------|
| `E_EXISTING_REMOVED` | An existing hub, link or satellite is absent from the extended model. An extension run must never drop what the vault already contains. |
| `E_EXISTING_BK_CHANGED` | An existing hub's business key **or source entity** changed (compared normalised). The key is what every stored hash was derived from, so changing it is a migration, not an extension. |
| `E_EXISTING_GRAIN_CHANGED` | An existing link's grain — the multiset of its participations, roles included — or its driving key changed. Those define the hash key of every stored row. |
| `E_EXISTING_SAT_RESHAPED` | An existing satellite changed parent, type, child dependent key, source table or attribute set. **Growth counts too:** a new attribute on a satellite with history is a backfill, so new attributes belong in a NEW satellite on the same parent. |
| `W_EXISTING_EXTENDED` | Advisory inventory, not a problem: an existing hub gained source feeds (named in the message), or this run added a new construct. It is the extension's summary in the review queue. |

The delta is also reported outside the gates: `extension-diff.md` and the report's
Extension section attribute which generated files a pre-existing construct's SQL
actually changed in — see 6.7.

## 8.3 Gates vs. backstops vs. steering

The boundary that chapter 11.4 operationalises: **gates are the product** — the
deterministic, auditable proof that an output conforms, kept regardless of how good
models get, and never ablated. **Backstops** and **steering rules** are
model-compensation: they exist because a current model makes a specific mistake, they
announce themselves when they fire (trace events, 10.4), and they are re-tested — and
potentially deleted — on every model release. Deleting a backstop is a reversible
experiment precisely because its gate stays behind it.

| Backstop | Repairs | Gate behind it |
|----------|---------|----------------|
| `attributes_without_cdk` (modeler) | CDK also listed as payload | `E_SAT_DUP_ATTR` |
| `fk_demotion` (source mapper) | A key's FK occurrence mistaken for a second source | — (mapping quality; honest `unresolved` is the fallback) |
| `effsat_two_attributes` (code generator) | Effectivity satellite with ≠2 attributes reaching generation | `E_EFFSAT_DATES` |

The full inventory with evidence and verdicts lives in
`docs/architecture/steering-ledger.md`.
