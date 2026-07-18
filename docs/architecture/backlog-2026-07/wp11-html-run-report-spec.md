# WP11 — Static HTML run report (model visualization, stage 1 of the UI track)

Status: Proposed · Size: M · Depends on: nothing new (write_outputs, WP5 §5.1 review-queue
presentation API, WP4 ValidationIssue, WP8 LinkHubRef, WP10 Hub.sources — all landed)

## 1. Problem & positioning

Every run already writes everything a reviewer needs (model, review queue, mappings,
contracts, ADR) — but as scattered YAML/Markdown/SQL. There is no single artifact a human
(or a prospect in a demo) can *open and see*: the DV model as a graph, the validation
verdict, and what needs sign-off. A DV model is a graph; it should be shown as one.

This is stage 1 of the UI track decided 2026-07-17: a **self-contained static HTML report
per run**, emitted by `write_outputs` — no server, no auth, no state, analogous in spirit
to dbt docs. Stage 2 (interactive HITL web UI over the existing interrupt/resume
checkpointer) is explicitly deferred and would need its own ADR (new framework rule).

**Invariant for the whole UI track (decided 2026-07-17): pure CLI operation stays a
complete, first-class mode at every stage.** Every operation — run, pause, resume,
mapping ratification, owner assignment — must remain fully possible from the console
alone. Any web layer is strictly additive: an optional view/control surface over the
same functions the CLI uses (a stage-2 server would live behind an optional dependency
extra, like `demo`), never the only path to a capability and never a required runtime
component. WP11 satisfies this trivially (the report is a passive output file), but the
invariant binds stage 2.

## 2. Non-goals

- No web server, no interactivity beyond native HTML (`<details>` collapsing is fine).
- No browser-side resume/ratification actions (stage 2).
- No run-to-run / attempt-to-attempt model diff (recorded follow-up — valuable for
  debugging the re-model loop, separate WP).
- No eval dashboard (LangSmith + `eval/results/` cover monitoring).
- No replacement of dbt docs / lineage; staging models are listed, not graphed.
- No standalone `.mermaid` artifact file (the source is embedded in the HTML).

## 3. Design decision: graph rendering

Considered:

| Option | Verdict |
|---|---|
| Pure-Python inline SVG (own layout) | Rejected: layout engineering for 20+ construct models is a project of its own; poor value for the effort. |
| D3/vis.js (vendored) | Rejected: MB-scale vendored JS in the wheel, imperative graph code to maintain, layout still ours to tune. |
| **Mermaid text + pinned CDN script, graceful fallback** | **Chosen.** The deterministic, keyless-testable core is the *Mermaid source text* (pure Python string generation); the browser does layout. Zero new Python deps, zero vendored assets. |

Offline behaviour: the `<script>` tag loads a **pinned major version** from jsdelivr
(e.g. `mermaid@11/dist/mermaid.min.js`; implementer verifies the current init API against
the installed docs — the WP8 t_link lesson: verify against reality, not memory). On load
failure the report still works: the Mermaid source is always present in a `<details>`
block ("Graph source — renders on GitHub / mermaid.live") and an `onerror` handler
un-collapses it. Vendoring `mermaid.min.js` for fully-offline demos is a recorded
alternative, deferred until an actual offline demo need arises.

Templating: **stdlib only** (string building + `html.escape`). jinja2 was deliberately
removed in WP5 §5.3; one template does not justify reintroducing it.

## 4. Module & wiring

- New module `src/vault_agent/report.py` — deterministic, no LLM, no agent (presentation,
  peer of `orchestrator.render_review_queue_md`). Public API:
  - `build_report(state: VaultAgentState) -> str` — the full HTML document.
  - `build_model_mermaid(model: DVModel) -> str` — the graph source (exposed separately
    for tests and potential reuse).
- `cli.write_outputs` writes `out_dir / "report.html"` unconditionally (both the
  interrupt path — artifacts-so-far — and the finalize path call it, so a paused run's
  report shows the pending state; a resumed run overwrites it). Counts dict gains
  `"report": 1`; the run summary prints the path.
- No business logic in graph.py; graph/topology untouched.

## 5. Report content (section order fixed)

1. **Header**: model counts (hubs/links/sats), raw-vault + staging model counts,
   contracts, ADRs; grounding on/off from `state.plan` (absent plan → "unknown");
   validation verdict badge (`validation_report.passed`) and a sign-off badge
   (`HumanReviewQueue.requires_signoff`). **No timestamps, no environment info** — the
   report must be byte-identical for identical state (house determinism/idempotency
   property, same as the WP2 ADR).
2. **Model graph** (Mermaid `flowchart LR`):
   - Hubs: rectangles, one CSS class; label = name + business key. A multi-source hub
     (WP10 `Hub.sources` non-empty) additionally gets one cylinder node per `HubSource`
     (label `source_table.business_key_column`) with an edge into the hub.
   - Links: hexagons; `link_type=="transactional"` annotated in the label. One edge per
     participation via `Link.hub_refs` (NOT raw `connected_hubs` — WP8: re-coercion),
     edge label = role when `LinkHubRef.role` is set; participations resolved by
     `Link.resolve_driving_refs()` render as thick edges (`==>`) — the driving-key marker.
   - Satellites: rounded rectangles, one CSS class per `sat_type`
     (standard/multi_active/effectivity); edge to `parent`; a sat with its own
     `source_table` (WP7 §7.1) notes it in the label.
   - Node IDs via `rules.normalize_identifier` (single source of truth — no new
     normalisation logic); display labels are the raw names, quoted and escaped
     (Mermaid `["..."]` form; `"` → `#quot;`). Two constructs normalising identically is
     a validator concern (E_DUP_HUB etc.), not the report's — last-write-wins is fine.
   - Deterministic emission order: hubs, links, satellites each in model list order.
3. **Construct inventory**: three tables (hubs: BK, source entity, sources, description;
   links: type, participations incl. roles, driving key, UoW, payload count; satellites:
   type, parent, attribute count, CDK, source_table, split_rationale). `requirement_ids`
   rendered as plain text lists.
4. **Validation**: verdict + one table over `validation_report.issues`
   (severity/code/construct/message — WP4 attribute access, no dict parsing).
5. **Review queue**: renders `assemble_review_queue(state)` using the WP5 §5.1
   presentation API — import `KIND_HEADINGS`, `KIND_ORDER`, `aggregate_review_flags`
   from `agents.orchestrator`; the report becomes the third renderer and MUST NOT
   duplicate that knowledge. Same blocking-first order, same aggregation semantics as
   `review-queue.md`.
6. **Mappings** (only when `state.mappings` is non-empty, mirroring the
   `mappings.review.yml` condition): proposals table (concept, table.column, category,
   confidence, ratification_status), then gaps and unresolved lists, with a one-line
   pointer to `mappings.review.yml` / `resume --mappings` for ratification.
7. **Contracts**: name, owner (placeholder rendered as "⚠ unassigned" — match on
   `ContractOwner.PLACEHOLDER_NAME`, never on message text), field count.
8. **Generated files** (collapsed `<details>`): relative paths of dbt models, staging
   models, scaffolding, contracts, ADRs as written by `write_outputs`.

Styling: one inline `<style>` block, minimal and legible (no CSS framework). All
dynamic strings — construct names, descriptions, messages, mapping evidence — are
LLM-derived and MUST pass through `html.escape` (and the Mermaid label escaping in the
graph). Treat every state string as hostile.

## 6. Tests (keyless, deterministic)

In `tests/test_report.py` (+ one integration case in the existing write_outputs tests):

- **Idempotency pin**: `build_report(state)` twice on a fixed populated state →
  byte-identical; and no timestamp-like content (assert absence of the current year is
  too brittle — instead pin the full output of a small fixed state as a fixture, the
  staging-baseline pattern).
- **Escaping**: a hub named `<script>alert(1)</script>` with a `"` in the description
  appears escaped in both HTML body and Mermaid labels; raw `<script>` (other than the
  single pinned mermaid include) absent from the document.
- **Mermaid structure pins** on `build_model_mermaid`: role-qualified self-referencing
  link (WP8 bank transfer shape) → two edges to the same hub node, one carrying the role
  label; driving-key participation → `==>`; multi-source hub → one cylinder per feed;
  sat_type class assignment; deterministic order.
- **Review parity**: for a state with >AGGREGATE_THRESHOLD aggregatable flags plus
  blocking items, the report's review section contains exactly the same summaries in the
  same order as `render_review_queue_md` (extends the WP5 parity test pattern to the
  third renderer).
- **Empty/minimal state**: report renders with header + empty-model note, no graph
  section, no crash.
- **write_outputs integration**: `report.html` written at the output root; counts include
  `"report": 1`; existing files untouched.

## 7. Acceptance criteria

1. `vault-agent run` on the bank demo inputs produces `report.html` at the output root;
   opened in a browser (online) the model graph renders; with the CDN blocked the report
   is still fully readable and shows the graph source.
2. The messy_insurance end-to-end run's report renders all 22 raw-vault constructs,
   shows hub_partner as multi-source (VICTOR_PARTNER + CRM_ACCOUNT cylinders), the two
   mapping gaps in the mappings section, and the same review items as `review-queue.md`.
3. Byte-identical report for identical state (pinned fixture green).
4. Hostile-name escaping test green; no unescaped LLM-derived string reaches the HTML.
5. No new runtime dependency in pyproject; full suite + ruff + mypy strict green;
   existing byte-identity guards (staging baseline, bank demo) untouched and green.

## 8. Follow-ups (out of scope, record only)

- Model diff between runs / between re-model attempts (developer-facing; likely the next
  highest-value slice).
- Stage 2: interactive HITL UI (FastAPI + htmx over the existing checkpointer) — needs
  an ADR before any framework lands; bound by the CLI-first invariant in §1 (optional
  extra, wraps `apply_human_decision`/resume — no capability may become web-only).
- Vendored-mermaid offline mode, if offline demos become a real requirement.
