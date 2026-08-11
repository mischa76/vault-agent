# WP34 — Links proposed from the source's own foreign keys

Status: **Approved** (2026-08-11, Mischa — with §3.4's one open decision resolved: the staging alias IS in v1) · Proposed 2026-08-11 (Claude) · Owner: Mischa Eismann
Depends on: WP23 (brownfield mode), WP29 (the propose → pause → ratify checkpoint), WP24
(canonical staging keys), WP30.1-30.3 (the measurements that motivate it).
Supersedes nothing. **Closes the prompt route opened by WP30.1** and recorded as stopped in
`docs/log.md` (2026-08-09).

## 1. Problem

Arm B — modelling domain by domain into a growing vault — builds **2 links spanning two
domains** where arm A, one pass over the same 68 tables, builds **16**. Cross-domain
relationships are precisely what an incremental walk is structurally placed to miss, and the
charter's whole claim rests on the incremental result being comparable.

**Three prompt interventions have been measured against this, and the lever is exhausted:**

| intervention | cross-domain links | where | zero-satellite hubs | review items |
|---|---|---|---|---|
| nothing | 0 | — | ? | 456 |
| `preserved_reference_is_a_link` steering rule | 0 | — | ? | 489 |
| rewritten extension register (WP30.2) | 2 | first boundary | fewer — invention stopped | 619 |
| promoted likely targets (WP30.3, **reverted**) | 2 | last boundary | **6** | **777** |

The ledger row for `preserved_reference_is_a_link` carries the verdict this produced:
**keep — UNEVIDENCED**, evidence against it rather than for it. WP30.3's change met its
pre-registered bar and regressed the model elsewhere, and was reverted on 2026-08-10. Prompt
shaping moves *which* two links appear; across four runs it never moved *how many*, while review
load rose 70%.

**The instruction was present at five levels** — the foreign key in the schema, the requirement
in prose ("these references must be preserved so the sales information can later be joined to
those areas"), the extension prompt's inventory, an explicit steering rule, and a ratified
resolver merge — and the modeler still did not build the relationship. That is not a gap a sixth
level of instruction closes.

**What the evidence points at instead.** The links do not need a model. `Sales.Customer.PersonID`
references `Person.Person.BusinessEntityID`; an existing hub is keyed on `BusinessEntityID`. That
is a link, derivable by reading two rows of the source's own catalogue. WP29 already built the
machinery for offering a machine's proposal to a human before it can do damage — propose, pause,
ratify — and it is pointed at concepts. This points it at relationships.

## 2. The blocking fact, verified before designing [ENFORCE]

**Foreign keys do not reach the pipeline today.** Verified in the installed code, not assumed:

* `state.SourceTable` (`src/vault_agent/state.py:90-137`) carries `table`, `columns`
  (`name`/`type`/`comment`), `schema_name`, `database`. **There is no foreign-key field.**
* `eval/adventureworks/extract.py:174-183` *does* parse them — `_FK_RE` yields
  `{columns, references_schema, references_table, references_columns}` per constraint, and
  `Table.foreign_keys` holds them in the checked-in extract.
* `eval/adventureworks/derive.py:73-88` `build_source_schema` reads `table["columns"]` and
  **drops `table["foreign_keys"]` on the floor**.

So the 90 foreign keys that WP30 §7.1 used to derive arm B's step order have never once been
visible to an agent. Every measurement above was taken with the decisive evidence withheld from
the pipeline by its own input format. **That is the first deliverable, and it is not optional:
without it there is nothing to propose from.**

This also bounds what §1's four rows can be read to mean. They say prompt shaping did not make
the modeler infer a relationship *it was never shown*. They do not say the modeler would ignore a
declared foreign key, because it has never had one.

## 3. Target design [ENFORCE]

### 3.1 The input: a declared foreign key, optional and inert when absent

```python
class ForeignKeyRef(BaseModel):
    columns: list[str]                    # the referencing columns, in order
    references_table: str
    references_columns: list[str]         # the referenced columns, same order/arity
    references_schema: str | None = None
```

on `SourceTable.foreign_keys: list[ForeignKeyRef] = Field(default_factory=list)`.

**Byte-identity is the acceptance criterion, not a hope.** Absent `foreign_keys`, every artifact
of every existing case must be byte-identical to today. Per the invariant, **the guard is
committed first**: the existing fixture set is extended with a run over a case whose schema
declares foreign keys and whose expected output is unchanged, and it must fail if the pass
regresses to acting on them unratified.

`derive.py` then emits them, and the AdventureWorks cases are re-derived deterministically — the
extract itself does not change, so this is a re-`_dump`, not a re-parse.

### 3.2 The pass: deterministic, keyless, zero model calls

A new module `src/vault_agent/link_proposal.py` and a new node `link_proposer` — no prompt, no
`ForcedToolCaller`, per the agent conventions for a deterministic agent.

For each declared foreign key of each new source table, it emits a proposal **only** when all of
these hold, and is silent otherwise:

1. an existing hub's business key matches the *referenced* column — compared through
   `normalize_identifier` against `canonical_hub_key_column(hub)`, never by string equality and
   never re-derived at the call site (the WP24 invariant; three of five call sites once bypassed
   that helper and staged a hash from the wrong relation, the only defect class here that
   produced wrong *data*);
2. the foreign key is single-column. Composite keys are **flagged, never guessed** — a
   `LINK_PROPOSAL_SKIPPED` flag with the reason, which is honest output, not a defect;
3. the referencing table is one this increment actually declares.

```python
class LinkProposal(BaseModel):
    source_table: str            # the referencing table — also the staging binding, see 3.5
    source_column: str           # its own name for the key (PersonID)
    target_hub: str              # the existing hub (hub_person)
    target_business_key: str     # canonical_hub_key_column(target_hub) — BusinessEntityID
    category: LinkProposalCategory
    evidence: list[str]
    ratification_status: RatificationStatus = "proposed"
```

**`category` is DERIVED from the evidence, never claimed** — the WP29 §2.3 rule, adopted because
the spike measured the resolver reporting `semantic` for every case including the ones it got
right (`rules/dv2_rules.py:481-523`):

* `declared_fk_same_name` — a declared foreign key whose referencing column already carries the
  hub's canonical key name. Nothing to translate; the strongest tier.
* `declared_fk_renamed` — a declared foreign key whose referencing column is named differently
  (`PersonID` → `BusinessEntityID`). Equally certain as a *relationship*; it needs the alias of
  §3.4, which is where its extra risk lives.
* `key_name_only` — no declared foreign key, the column names simply coincide. This is the
  WP30.3 trap in numbers: measured against step 4's 30-hub vault, AdventureWorks Sales matches 13
  hubs by business-key column and **7 of those only because they are keyed on `Name`**. This tier
  exists so the noise is *labelled* rather than hidden, and §3.3 never auto-ratifies it.

### 3.3 Ratification: the WP29 checkpoint, extended — one pause, not two

`resolution_checkpoint` (`agents/entity_resolver.py:487-538`) already sits between the resolver
and the modeler for the reason this WP needs: a decision made at the sign-off checkpoint runs
after modelling, code generation and validation, and can no longer affect the model it is about.
Link proposals ratify **at that same node**, in the same `interrupt()` payload, because two
consecutive pauses for one human is a worse product than one pause with two sections.

The node's purity contract is inherited and must be preserved: everything above `interrupt()`
stays a pure filter over state, because a resume re-executes the node from the top.

**Nothing is auto-ratified.** A `key_name_only` proposal is never applied without a human answer,
and the `--accept` bulk path must not silently sweep them in. The WP30 arm run auto-ratified a
resolver merge at confidence 0.55 and no gate would have caught it had it been wrong — recorded
in the spec's own results section, and not to be repeated on an axis that writes joins.

### 3.4 Applying a ratified proposal: the alias is the correctness risk [ENFORCE]

This is the part that can produce wrong data, and it is why the WP is M and not S.

A link's staging projects, for each participation, the hub's **canonical** business-key column
and hashes the FK from it (`agents/staging_generator.py:236-240`,
`role_bk_column(canonical_hub_key_column(hub), ref.role)`). For `Sales.Customer.PersonID →
Person.BusinessEntityID` that spec would demand `BUSINESS_ENTITY_ID` from a relation that only
has `PersonID`. The staging model would not build, or — worse — would build against a
same-named column meaning something else.

`Hub.sources[].business_key_column` solves exactly this problem for multi-source hubs ("staging
aliases it to the canonical name before hashing so the same key value hashes identically
everywhere", `state.py:341-350`). Links have no equivalent. So:

**`LinkHubRef` gains `source_key_column: str | None = None`** — this participation's own physical
name for the hub's key, aliased to the canonical name in staging exactly as a hub feed's is.
`None` keeps today's behaviour and today's bytes.

**The decision this poses, and my recommendation.** Restricting v1 to `declared_fk_same_name`
would need no alias and no new field — but it drops `Sales.Customer.PersonID → hub_person`, which
is the flagship example, one of the two links arm A builds and arm B misses, and the case the
whole line of work has been quoting since WP30.1. A version that cannot express the motivating
example is not worth measuring. **Recommendation: build the alias in v1.** It is a field, a
staging alias that mirrors machinery already proven for hubs, and one gate (below).

**DECIDED 2026-08-11 (Mischa): the alias is in v1.** So `declared_fk_renamed` is in scope from the
first line of code, and `LinkHubRef.source_key_column` plus `E_LINK_KEY_NOT_IN_SOURCE` are binding
deliverables rather than options. What keeps that honest is §5.4 and §6's fourth clause: the alias
is the one part of this WP that can write a join against the wrong column, so it ships with its
gate or it does not ship. `Sales.Customer.PersonID -> hub_person` is therefore expected in the
measured run, and its absence would be a mechanism failure, not a scope note.

### 3.5 What the proposal buys beyond the link itself

A link's staging binding is inferred today: `bind_sources` (`staging_generator.py:342-384`) name-
matches the construct base against declared tables, finds nothing for `link_customer_person`,
falls back to `raw_link_customer_person` and raises a `SOURCE_BINDING` flag. Links get a real
relation only later, from the source mapper's `source_overrides` — an LLM step.

An FK-derived proposal already **knows** the relation: the referencing table. It supplies
`source_overrides[normalize_identifier(base)] = source_table` deterministically, which the
existing code path consumes unchanged and raises no flag for (`staging_generator.py:358-362`).
So the pass removes an inferred binding and an advisory flag per proposed link rather than
adding them.

### 3.6 Gates — a gate refuses, a backstop repairs

The pass is **not** a backstop: it does not repair model output, it contributes a construct
before modelling. Two deterministic gates keep it honest, and both are product, never ablated:

* **`E_LINK_KEY_NOT_IN_SOURCE`** — a link participation whose `source_key_column` (or, absent
  one, the hub's canonical key) is not a declared column of the staging model's bound relation.
  This is the gate that catches the §3.4 failure, and it protects every link, not only proposed
  ones.
* The existing `E_LINK_UNKNOWN_HUB` / `E_LINK_TOO_FEW_HUBS` / `E_BAD_NAME` already cover the
  rest; a proposed link goes through `merge_models` and the validator on the ordinary path, with
  **no privileged route into the model**. `_append_or_conflict` (`agents/model_merger.py:54-58`)
  treats it exactly as a modeler-emitted link.

### 3.7 Explicitly out of scope

Composite foreign keys (flagged); self-referencing keys; links between two constructs the same
increment introduces (the modeler's job, and it does that adequately — 36 links per run);
Business Vault; any inference from data rather than declaration. **No requirement to delete the
`preserved_reference_is_a_link` steering rule** — it is ledger-labelled `keep — UNEVIDENCED`, and
whether the prompt line goes is a separate WP16 judgement, not a side effect of this one.

### 3.8 Scope of effect, and what the modeler is deliberately NOT shown

Added 2026-08-11, after Mischa asked whether this is an arm-B-only change. It is not, and the
distinction matters for the product rather than only for the experiment.

**The trigger is a MODE, not an arm.** The pass needs an existing hub for the foreign key to point
at, so it is gated on an existing model plus a declared schema. Verified against the case
definitions rather than inferred:

* `eval/datasets/adventureworks_full/dataset.yml` (arm A) declares **no** `existing:` — it is a
  greenfield one-pass run over 68 tables, with no prior vault and therefore no delta detection at
  all. WP34 is inert there, and arm A's artifacts stay byte-identical.
* `eval/datasets/adventureworks_incremental/dataset.yml` (arm B) is a chain in which each step
  reads the previous step's `metadata/dv_model.yml` through the real WP23 `--existing` path
  (`eval/run.py:522`). WP34 is active from step 2 onward.

So "arm A is unaffected" is true of arm A **as measured**, and true because that case is
greenfield — not because one pass is somehow exempt. **A one-pass BROWNFIELD run — a large new
source system onto an existing vault in a single increment — gets proposals too**, and that is a
first-class product case, not a hypothetical: it is the everyday "onboard a new system onto our
vault" job, and `run --existing` already serves it. Neither arm is a code path the other replaces;
the comparison decides the charter's claim and the demo narrative, not which mode survives.

**The foreign keys are NOT rendered into the modeler's prompt, and that is a decision.**
`render_schema_prompt_section` (`grounding.py:29-46`) carries table and column **names** only —
not types, not comments, and under this WP not foreign keys either. Only the deterministic
proposer reads them. Two reasons, in order of weight:

1. **The arms' inputs must not diverge.** Re-deriving the AdventureWorks cases with foreign keys
   present would otherwise change arm A's prompt as well, and the arm comparison would then be
   measuring a changed input *and* a new mechanism at once. WP30.2 already paid for that mistake
   once — the steering rule and the rewritten register moved together, which is precisely why that
   run cannot say which of them produced its 2 links, and why the ledger row still reads
   `keep — UNEVIDENCED`.
2. It keeps §5.2's byte-identity guard meaningful: with nothing rendered, "declared foreign keys
   present, none ratified" is provably indistinguishable from today.

**Stated plainly because it is a choice and not a necessity:** showing declared foreign keys to
the modeler is cheap, plausible, and **untested**. Arm A builds 51 links without them, so the
expected upside is unclear rather than obviously positive. If it is ever tried it is a **separate
change, measured in a separate run** — never in the same run as the proposer, or the two cannot be
told apart, which is the WP30.2 confound repeating with new variables.

**A second consumer already exists in the tree, and it is out of scope here.**
`SourceMapperAgent._is_fk_to` (`agents/source_mapper.py:433-441`) answers "is this column a foreign
key to that table?" by substring-matching `"fk"` / `"foreign key"` in the column's **comment
text**, then token-matching the anchor table's name in the same comment. That is the input to
WP9.1's `fk_demotion` backstop, whose ledger row is `keep` on measured evidence (mapping accuracy
0.870 → 0.972). It is also a branch on human-readable text, which this project's own invariant
forbids — a typed field is exactly what it lacks, and this WP creates one.

Changing it here is nevertheless **forbidden**: it would move the mapper's measured behaviour in
the same run that introduces the proposer, confounding the two. Recorded as the first follow-on
once WP34 has a number.

## 4. What persistence does and does not need

WP29's open persistence gap does **not** recur here, and the reason is worth stating so nobody
re-solves it: a ratified proposal is applied *within the run*, so it lands in the merged model and
therefore in `metadata/dv_model.yml`, which `run --existing` already reads and `eval/run.py`
already passes between chain steps. The link survives because the model survives.

**A rejected proposal is a different matter and is v1's honest rough edge.** Nothing records the
rejection, so the next increment re-derives the same foreign key and asks again. For a five-step
chain that is a bounded annoyance; for a fifty-step landscape it is not. Recorded as a known
limitation rather than designed around, because the fix is the same `metadata/resolutions.yml`
decision WP29 left open and Mischa has not yet decided — **and this WP must not pre-empt that
architecture decision by inventing a second decision file.**

## 5. Acceptance

Keyless, verifiable without spending anything:

1. `uv run pytest`, `uv run ruff check`, bare `uv run mypy` green.
2. **Byte-identity**: every existing fixture unchanged; a schema *with* declared foreign keys and
   no ratification produces byte-identical output to the same schema without them. Guard
   committed before the change.
3. Greenfield inertness: no existing model → no proposals → prompt and artifacts byte-identical
   (`test_greenfield_inertness.py`, the WP16 steering fixture).
4. `E_LINK_KEY_NOT_IN_SOURCE` fires on a hand-built link whose alias is wrong, and does not fire
   on a correct one.
5. The five AdventureWorks cases re-derive deterministically with foreign keys present, and the
   FK edge count in the derived schemas equals the extract's — no silent loss.

Live, and it costs money:

6. One arm-B repeat (~$9) against the pre-registration in §6.

## 6. Pre-registration — written before the run, and deliberately not a count [ENFORCE]

WP30.3's post-mortem is the reason this section is shaped differently: *"a criterion a change can
meet while making the result worse is a bad criterion"*. WP30.3 optimised for "a late-step link
appears", got it, and the model regressed elsewhere while satisfying it. So this WP's bar is a
**conjunction**, and every clause must hold:

* **Links.** Cross-domain links ≥ **8** — half of arm A's 16. A deterministic pass over declared
  foreign keys should not be graded on the 2-link scale a prompt earned; if it lands below half
  while the foreign keys are right there in the input, the mechanism is broken, not shy.
* **No regress on invention.** Zero-satellite hubs must **not** rise above the WP30.2 baseline,
  and `hub_sales_representative` must **not** return. This is the clause WP30.3 failed.
* **Review load must fall, not rise.** Against the WP30.2 baseline of 619. The claim motivating
  this WP is that a proposed link is *one* review item with a clear answer, replacing a modelling
  decision spread across five increments. If review items rise again — a fifth consecutive rise —
  that claim is false and must be recorded as false, whatever the link count says.
* **Zero wrong joins.** Every applied link's staging must project a column the bound relation
  actually declares. This is checked deterministically, not by eye, and a single violation fails
  the WP regardless of every number above.

**Falsified if the links appear and review load rises**, which is the specific shape of the
WP30.3 failure repeating with a different mechanism. The honest response then is not a fifth
intervention: it is that the arm comparison's review-load axis is telling us domain-by-domain
costs more human attention than one pass, and the charter claim should be revised rather than
defended.

## 7. Size and cost

**M.** One state field, one derived-input change, one deterministic module, one node, one
`LinkHubRef` field with a staging alias, one gate, and the checkpoint extension. No prompt
change, no new model call, and the pass itself costs nothing per run. The measurable spend is
one arm-B repeat, ~$9, against ~$46 already spent on the prompt route.

## 8. Results

*(empty until the WP runs — filled by dated append, never by revision)*
