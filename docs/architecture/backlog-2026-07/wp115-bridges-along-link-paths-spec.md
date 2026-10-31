---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP115 — Bridges along link paths (C22, the open half of ADR-0016)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog) · Owner: Mischa Eismann ·
Author: Claude. The last item of the old backlog the owner ordered; C22's PIT half is WP91 (2026-10-23).

## 1 What is missing

ADR-0016 (accepted 2026-10-23, option B) decided that the Business Vault's PIT and bridge are rendered in
vault-agent's own SQL, PIT first, bridge second, and left one thing open: „the bridge path language". WP91 built the
as-of spine and the PIT; the manual (9.7), the README's capability table and ADR-0016's own consequence line still
say „bridges: not generated yet". A bridge is the construct that answers a query across hubs without re-deriving
the joins every time: one row per start key and as-of date per path instance — which account a customer held on
that date, which account that account transferred to. Unlike the PIT it is not deterministic from the model: there
are as many paths as the graph has walks, and which of them is worth a table is a business decision. ADR-0007 keeps
Business Vault logic human-ratified; ADR-0016 says „a bridge needs a path, proposed from the requirements and
ratified as a decision".

## 2 The rules

1. **The path language.** A path is a comma-separated walk `hub,link,hub[,link,hub…]` — at least one link, hubs and
   links alternating, every link joining the hub before and the hub after it. A hub step may carry a role,
   `hub:role` (ADR-0009's notation, the one `driving_key` uses): the first hub's role names its participation in the
   first link; every later hub's role names its participation in the link just walked. A middle hub leaves by the
   participation of the next link that is not the one the path arrives at the next hub by — unqualified where both
   remain, and refused as ambiguous where that leaves two. `parse_bridge_path(path, model)` is the one reader
   (`rules/`-style helper in the generator module; the modeler never writes paths) and refuses, by message, a step
   that names no construct, two hubs in a row, a link that does not join its neighbours, a role the link does not
   carry. The model name is `bridge_<base of every hub, in path order>` — `bridge_customer_account`,
   `bridge_account_account` — so two paths over the same hubs in a different order are two tables.
2. **Two ways to a path: named at start, or proposed and ratified.** `BusinessVaultOptions.bridges: list[str]`, the
   CLI's repeatable `run --bridge PATH`, the workbench's `bridges` on the run start; a bridge needs the spine's bounds
   exactly as a PIT does (`as_of_start`, `as_of_end`), validated by the same model. And, ADR-0016's second way:
   `propose_bridge_paths(model)` proposes, deterministically, one path for every pair of links that **cite the same
   requirement** (`requirement_ids`, the modeler's own citations — WP109 made the citation a disclosure when missing)
   **and share a hub**, from the first link's other hub through the shared one to each other participation of the
   second link (a self-link yields both its exits). Proposals exist only while the Business Vault is on (`pit` or a
   named bridge): a run that asked for no Business Vault keeps its review queue byte-identical. Each proposal is a
   `BridgeProposal` on the state (`path`, `requirement_ids`, `evidence`, `ratification_status`) and a
   `bridge_proposed` flag — a **decision** (ADR-0007): unanswered at `--accept`, a proposal is declined, never built
   by default; `resume --bridge PATH` / `--no-bridge PATH`, the workbench's `bridges: {path: bool}`, and the
   interactive prompt (default no) are the three answers, the same `Decision` payload, the same applier. A path
   answered yes that no proposal carries but the model parses is built too (an operator's path at sign-off, the
   same as one at start); a path that does not parse is a warning, skipped, never a guess.
3. **Rendering, in our own SQL (ADR-0016's exception), over the as-of spine.** `render_bridge(steps, raw_metadata)`:
   the first hub's keys cross-joined with `as_of_dates`, then per link an inner join on the arriving participation's
   FK column (the link metadata's `src_fk`, role-qualified by `role_fk_column` — the raw vault's columns by
   construction, as the PIT's are) and a validity clause: **by the link's effectivity satellite** where one exists —
   the latest effectivity row (`src_ldts <= AS_OF_DATE`) whose `src_start_date <= AS_OF_DATE` and whose
   `src_end_date` is null or after it — and **by the link's load date** (`src_ldts <= AS_OF_DATE`) otherwise; the
   header says which. Output: the first hub's hash key, `AS_OF_DATE`, per link its hash key and the far
   participation's FK column (a repeated column name gets `_2`, `_3`). Materialised `table`, rebuilt whole, like the
   PIT; no `automate_dv.bridge()` (deprecated as „not fit-for-purpose", the spike). `metadata/automatedv.yml` records
   each bridge under `bridge:` (path, spine, the steps with their validity source and columns); one
   `bridge_generated` disclosure per bridge; `as_of_dates` and `packages.yml`'s `dbt_utils` come with the first
   bridge as with the first PIT. A path whose link or hub the generator could not render is a `generation_gap`
   naming the step, not a crash.
4. **Ratified at sign-off means rendered at sign-off.** `apply_human_decision` applies the bridge answers, then
   re-renders the Business Vault's bridges from the artifacts' own metadata (the raw vault is already generated), so
   the written project after `resume --accept --bridge PATH` holds the bridge; its flags are replaced, not stacked.
5. **Workbench parity (WP82).** `StartRun.bridges`, `Decision.bridges`, the checkpoint's `bridges` list at sign-off
   (`path`, `requirement_ids`, `evidence`), the CLI equivalents carrying `--bridge`/`--no-bridge`, the Review
   perspective listing each proposal unchecked with „build" as the choice, the Project perspective's Business Vault
   block taking paths one per line. The parity guard's rows name them.
6. **Nothing else moves.** Bridges off and no proposal possible: every artifact, flag and fixture is what it was;
   the PIT's rules (WP91) are untouched.

## 3 Acceptance (keyless)

`tests/test_wp115_bridges.py` (committed red before the change) and one Vitest test on the Review perspective:
the options' bounds rule; the path language (roles, the five refusals, the model name); a named bridge rendered over
the spine with the effectivity satellite's columns, its metadata and disclosure, no PIT asked for; a role-qualified
step naming the role column and falling back to the load date; an unknown path a generation gap; two links citing
one requirement proposing both exits of the self-link, nothing proposed uncited or with the Business Vault off; a
ratified proposal rendered and a declined one not, the proposal flags gone; the CLI decision carrying the answers;
a workbench run recording named bridges, its checkpoint listing proposals, its decision reproducing them in the CLI
equivalent; the parity rows. Every existing fixture byte-identical.

## 4 Pre-registration

- **P1 — keyless.** The guards go green; every frozen fixture is byte-identical with bridges off; suite, ruff, bare
  mypy, tsc and vitest green.
- **P2 — PostgreSQL build of the bank project.** The bank model (`tests` fixture shape: `hub_customer`,
  `hub_account`, `link_account_customer` with `sat_account_customer_eff`, `link_transfer` over
  `hub_account`/`hub_account:counterparty`) generated keyless with the demo's seeds, `--bridge
  hub_customer,link_account_customer,hub_account` and `--bridge hub_account,link_transfer,hub_account:counterparty`,
  spine 2026-01-01 → 2026-03-01 by day, builds on PostgreSQL (`dbt build`, all PASS). For every as-of date D,
  `bridge_customer_account` holds exactly the (customer, account) pairs whose latest effectivity row at D has
  `EFFECTIVE_FROM <= D` and `EFFECTIVE_TO` after D — checked by a SQL over the built effectivity satellite, and
  compared with the seed's own `EFFECTIVE_FROM`/`EFFECTIVE_TO` (a difference, if any, is AutomateDV's auto
  end-dating and is recorded, not explained away). `bridge_account_account` holds, per D, the transfers whose link
  load date is at or before D. Falsified by any PASS short of all, or any as-of date whose pairs differ from the rule.
- **P3 — idempotent.** A second `dbt build` on the same schema leaves every bridge's row count unchanged and adds no
  raw-vault row.
- **P4 — the proposer on real models.** On the twenty-third chain's five step models (kept outputs, 2026-10-31),
  every proposed path parses back, and no step proposes more paths than it has links squared; the per-step counts
  are recorded, not predicted — the citation density of the 5.5 modeler decides them.

## 5 Not in scope

An incremental bridge; a bridge whose path crosses a link more than once or starts at a link; multi-hop validity
beyond the per-link clause (no „all links valid on one effectivity source"); Databricks and Snowflake builds (the
SQL uses only `cross join`, `join`, `max`, `group by` and `coalesce`, the PIT's dialect); a proposal from anything
but the model's citations (no LLM proposes paths); ADR-0016's re-evaluation when AutomateDV publishes the
redesigned macros.

## 6 Measured (2026-10-31, keyless)

- **P1 ✔.** Eleven Python guards and one Vitest test red before the change (`3a8718d`: red at import, and the
  Review perspective without the control), green after; every frozen fixture byte-identical with bridges off (the
  business vault model block and `dbt_utils` now follow `enabled`, which is `pit` where only a PIT is asked for);
  suite 1560 passed, 5 skipped; ruff; bare mypy; tsc; vitest 34. One existing guard updated deliberately
  (`test_build_decision_collects_owners`: the decision payload gains `bridges: {}`).
- **P2 ✔.** The bank project (the fixture's two hubs, `link_account_customer` with its effectivity satellite,
  `link_transfer` over `hub_account`/`hub_account:counterparty`) generated keyless with the two paths and the demo's
  four seeds, spine 2026-01-01 → 2026-03-01 by day: `dbt build` PASS=18 of 18 on PostgreSQL (`wp115_bank`).
  `bridge_customer_account`: 236 rows over 59 dates; on **every** date the bridge's count equals the count by the
  rule over the built effectivity satellite and the count by the seed's own `EFFECTIVE_FROM`/`EFFECTIVE_TO`
  (0 differing dates), and pair for pair by business key: 236 bridge pairs, 236 seed-valid pairs, 0 in either
  difference. `bridge_account_account`: 73 rows, on every date equal to the transfers loaded by then (0 differing
  dates). **Not exercised by this data:** the seed's one superseded relationship (`ACC-503`, re-assigned on
  2026-04-01) lies after the spine's end, so AutomateDV's auto end-dating and the seed's own dates could not differ
  inside the spine — the rule and the seed agree trivially there; a spine over that date is the next measurement.
- **P3 ✔.** The second `dbt build` PASS=18; `bridge_customer_account` 236, `bridge_account_account` 73,
  `link_account_customer` 5, `sat_account_customer_eff` 5, `link_transfer` 3, `hub_account` 4 — unchanged.
- **P4 ✔.** On the twenty-third chain's five step models (kept outputs `20261031T032606335763Z`): 1, 9, 12, 24, 38
  proposals for 4, 6, 23, 29, 50 links (every link but 3 + 3 cited), every path parsing back, every count far under
  the links-squared bound. The paths are three-hop walks a person would ask for (address → state province →
  country region; address → business entity → department / shift; a sales order's bill-to and ship-to addresses →
  ship method), and the counts say what the citation rule costs at sign-off: on the sales step 38 decisions,
  declined by default — a run with the Business Vault on pays that attention once; a run without it sees none.

Open after WP115: a spine crossing an end-dating event (P2's unexercised clause); Databricks; the proposal count on
a large step as a review-load question (a cap or a grouping is a later WP, measured first).
