# 13. Glossary

Short definitions with pointers to the chapter that explains each term in context.

| Term | Short definition | Details |
|------|------------------|---------|
| Ablation | Running an eval case with one steering rule dropped to measure whether the model still needs it | 11.4 |
| Backstop | Deterministic pre-gate repair of a known LLM mistake; fires are counted, re-tested per model release | 8.3, 10.4 |
| Business key (BK) | The stable, business-recognised natural identifier a hub is built on | 2.1 |
| Child dependent key (CDK) | The sub-sequence key of a multi-active satellite — a key column, not payload | 2.2, 2.4 |
| Collision code | Source differentiation added when the same key value from different systems can mean different objects | 8.2 (`W_BK_COLLISION_RISK`) |
| Confidence category | Deterministic class of a mapping proposal: `exact_name` > `comment_grounded` > `profiled_key` > `llm_semantic` | 7.6 |
| Data boundary | Row data is processed only by generated dbt SQL in the warehouse; the LLM sees requirements, metadata, and (optionally) profiling example values | 10.7 |
| Data contract | JSON-Schema-based description of one source asset incl. failure modes and owner; drafted per asset | 2.3, 6.4 |
| Driving key | The link participation that stays fixed while others rotate; required for effectivity satellites | 2.2 |
| Effectivity satellite | Tracks a relationship's active period (start, end); end-dates superseded rows | 2.2, 9.4 |
| Flag | Typed pipeline signal (agent, severity, kind, asset); feeds the review queue | 2.3, 7.3 |
| Gap (mapping) | A concept with no in-scope source — honest output, not a defect | 7.1, 7.6 |
| Gate (E_/W_ code) | One deterministic validator check; E_ blocks, W_ advises | 8 |
| Golden dataset | An eval case pairing an input with the expected model and optional score gates | 11.1 |
| Grounding | Declaring a source schema so keys/attributes are steered to and checked against real columns | 2.3, 6.1 |
| Hashdiff | Hash over a satellite's payload used for change detection | 2.1 |
| Hash key (HK) | Hash of the business key(s) identifying hub/link rows | 2.1 |
| HITL checkpoint | The pause point where a human signs off, assigns owners, and ratifies mappings | 7 |
| Hub | One business concept identified by one business key; key + technical columns only | 2.1 |
| Link | A relationship between hubs; one link = one unit of work | 2.1, 2.2 |
| Mapping (business↔source) | Proposal which physical column feeds each model concept; binding only after ratification | 7.6 |
| Multi-active satellite | Satellite with several concurrent rows per parent, distinguished by a CDK | 2.2 |
| Multi-source hub | One hub fed by several source systems; same key value hashes identically across feeds | 2.2, 9.4 |
| Profiling evidence | Per-column statistics fed to the mapper; establishes structure, never intent | 6.1, 7.6 |
| Ratification | The human decision that promotes proposals (mappings, owners) into the model | 7.5–7.6 |
| Re-model loop | Validation-failure retry: errors fed back to the modeler, bounded by 3 attempts | 3.2, 6.3 |
| Review queue | The categorized, blocking-first list a human answers at the checkpoint | 7.3 |
| Role (link participation) | Qualifier letting one hub participate twice in a link (payer/counterparty) | 2.2 |
| Satellite | Descriptive, historised attributes hanging off one hub or link | 2.1 |
| Source binding | How a staging model references its raw relation: inferred, declared bare-name, or `source()` | 9.3 |
| Staging model (`stg_*`) | Generated layer deriving hash keys, hashdiffs, and derived columns from a raw relation | 2.1, 9.1 |
| Steering rule | A registered prompt rule (id, origin, optional linked backstop); ablatable | 8.3, 11.4 |
| Steering ledger | The per-rule inventory of evidence and keep/delete verdicts | 11.4 |
| Trace | The per-run jsonl LLM transcript under `.vault-agent/traces/` | 10.2 |
| Transactional link | Link recording atomic business events (one row per event, `t_link`) | 2.2 |
| Unit of work | The business keys of one atomic business event — the grain of one link | 2.2 |
