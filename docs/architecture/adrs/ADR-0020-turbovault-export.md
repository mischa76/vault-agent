# ADR-0020: Exporting a ratified model into TurboVault Engine's formats — not now; when a datavault4dbt customer asks, into the round-trip project JSON, never into the MCP proposal schema

**Status:** Proposed (2026-10-31 — draft by Claude on the owner's go to continue the plan of 2026-10-30; the
recommendation is Option 1 with Option 3 as the prepared path)
**Date:** 2026-10-31
**Decision makers:** Mischa Eismann

## Context

Backlog C32 (2026-10-30, found by reading the competitor) asks whether Vault-Agent should export a ratified model
into Scalefree's TurboVault Engine, so that a customer on datavault4dbt gets this project's modelling and their
generation, without a second generator here. The candidate names three preconditions: a decision whether exporting
into a competitor's format is wanted at all, an ADR under ADR-0007's layer scope, and a pinned fixture of their
schema at the version read. This ADR is the first two. Nothing is built.

**What the target is, read at the repository on 2026-10-31** (`ScalefreeCOM/turbovault-engine`, HEAD `2dd2d98`
of 2026-10-29, `pyproject.toml` version 0.21.0). The engine has **two** import shapes, not one:

1. **`ModelImportSchema`** (`backend/engine/services/model_import_schema.py`; the MCP server's `commit_model` and
   `turbovault model import-json`): a flat list of hubs, links and satellites. A hub has one `source_table` and
   `business_keys` matched to source columns *by the same name*; a link has `hubs` by name, an optional
   `hub_source_columns` override „only applied to single-key hubs", `payload_columns`, `dependent_child_keys`; a
   satellite has `parent_hub` xor `parent_link`, `columns` that are „informational — staging mappings require
   source metadata", one `source_table`; a free-text `reasoning` the importer ignores. Its own doc calls it
   „intentionally minimal: it captures entity names and relationships, but does not require source column mappings
   or staging metadata. Column-level detail can be added later in the Django Admin interface." `commit_model` skips
   an existing entity of the same name silently („idempotent").
2. **The project round-trip JSON** (`docs/04_concepts/04_json-import.md`; `turbovault generate --type json` →
   `turbovault project init --source model.json`), whose intermediate model `backend/engine/services/imports/domain.py`
   holds what the minimal schema cannot: a hub column with **several source mappings** (`DHubSourceMapping`,
   `is_primary_source`), a link's hub reference with its own **hashkey alias** (`hub_hashkey_alias_in_link`), a
   link's hub source mapping with a **prejoin target** (`DLinkHubSourceMapping.prejoin_target_table_identifier`,
   `DPrejoin` with join columns and extraction columns), typed link columns (payload, dependent child key),
   satellite columns with multi-active key and delta-detection flags, source systems and tables with record source
   and load date, derived columns, descriptions on every level. It is, by its own parser's docstring, „rev-locked
   to the engine's own export shape"; the `source_metadata` format is the one they version publicly.

**What this project's ratified model is.** `DVModel` (`state.py`): hubs with `business_key_columns` and
`sources` (several `HubSource`, each a table and its key column — multi-source hubs), links with `connected_hubs`
as `LinkHubRef` (`role`, `source_key_column`, `key_translation`), `driving_key`, `payload`, `link_type`
standard/transactional, satellites with `attributes`, `sat_type` standard/multi-active/effectivity,
`source_table`, `key_translation`, `participation_translations`, `participation_aliases`; the bindings
(`StageBinding`: relation and aliases, WP77/WP82) and the carried catalogue (`metadata/source_catalogue.yml`,
WP74) travel with the project. Beside the model: the review queue's decisions, the typed flags, the gates'
verdicts, the ADR, the data contracts, `requirement_ids` on every construct.

**What the gates guarantee, and where.** `E_LINK_KEY_NOT_IN_SOURCE`, the satellite grain gate, the translation
gates (WP36, WP93), the optional-participant gate (WP94) judge *this project's* staging — the columns hashed, the
relation read, the join a translation renders. An exported model is a description; whatever generator reads it
builds its own staging, and the guarantee does not travel with the file.

**Constraints.** ADR-0003 names AutomateDV the one code-generation backend; the owner's decision of 2026-10-04
keeps it so until that line runs clean, and this holds until he lifts it. ADR-0007 puts the raw vault on the
generate side. ADR-0015 positions the product as the modelling, with the dbt project as its proof. The engine is
AGPL-3.0 with a dual-licence offer: a file written in its format, or a call to its MCP server, links none of its
code; running their package to validate an export file is use, not distribution. Their open issues #214 and #215
touch `commit_model` and `validate_model`: the minimal schema is moving.

## Decision (proposed)

**Option 1, with Option 3 prepared: nothing is built now, and when it is built, it targets the round-trip project
JSON, never the MCP proposal schema.**

1. **No exporter until a datavault4dbt customer is in front of us, or release criteria 2 and 5 are met,
   whichever comes first.** The reasons, in order of weight: nobody has asked; the target is a pre-MVP engine
   whose export shape is rev-locked and moving, so a fixture would be re-pinned per their release for a feature
   nobody uses; the owner's „one thing at a time" of 2026-10-04 names what comes first; and the exporter is a
   sales deliverable — built in a day when the customer exists, from the mapping below, which is this ADR's
   durable part.
2. **The MCP proposal schema is ruled out as a target now.** It cannot hold a multi-source hub (one
   `source_table`), a role (two participations of one hub in one link collapse to one name), a key translation
   (business keys are matched by name, the override is single-key only), a composite participation, an
   effectivity satellite, a binding's alias. Exported into it, a ratified AdventureWorks model would arrive as
   the model this project refuses to build — and `commit_model`'s skip-on-same-name makes a re-export of a
   brownfield step silently keep the old shape. A lossy export of a verified model is worse than none: the
   customer reads the loss as our modelling.
3. **The round-trip project JSON is the target when the day comes.** The mapping, recorded now so it is not
   re-derived: hub → `DHub` with one `DHubColumn` per key column and one `DHubSourceMapping` per `HubSource`
   (the first primary); `LinkHubRef.role` → `hub_hashkey_alias_in_link`; `key_translation` → a `DPrejoin`
   (source join column the surrogate as the referencing table calls it, target join column the referenced
   relation's own name for it, extraction columns the hub's natural key columns) plus the link's hub source
   mapping with that prejoin target; `payload` → link columns of type payload, a transactional link →
   `non_historized`; satellite → `DSatellite` on the bound relation (`StageBinding.relation`, else
   `source_table`) with one column per attribute, the multi-active key marked; a binding's alias → a
   `DDerivedColumn` on the source table; the carried catalogue → `DSourceSystem`/`DSourceTable`/`DSourceColumn`
   with `record_source` as `!<schema>.<table>`. Descriptions go where they have a field. **Not exportable, and
   said so in the export's report rather than dropped:** an effectivity satellite on a link (their flag is on the
   hub), `requirement_ids`, the evidence, the gates' verdicts, the review decisions, the data contracts — these
   stay in this project's own artefacts (`metadata/dv_model.yml`, the ADR, the queue), which the export names as
   its provenance.
4. **When built:** a keyless `vault-agent export --format turbovault-project` reading the kept project's
   `metadata/` (the model, the catalogue, the bindings) — no run, no model call, no MCP session; a pinned fixture
   of their JSON field names at the version built against, with a guard that fails when the fixture and the
   exporter disagree; a proof that their own `turbovault project init --source` and `generate_dbt --dry-run`
   accept the file at that version, run in a sandbox, recorded in the log with the version; the manual says
   what does not travel. A WP spec, guards first.
5. **Not a second backend, by construction.** The exporter writes a description; this repository generates
   nothing on datavault4dbt and runs nothing of theirs in the pipeline. ADR-0003 and the 2026-10-04 decision are
   untouched.

## Alternatives considered

- **Option 2 — export into the MCP proposal schema (`commit_model`), now.** The smallest build (an hour) and the
  one their documentation advertises for assistants. Rejected for the losses in point 2: the schema is sized for a
  chat proposal, not for a ratified model, and its silent idempotence would hide a brownfield change. Its one
  genuine use — demonstrating that a model made here can land there — is a demo, and a demo of a lossy path
  teaches the wrong thing.
- **Option 3 now — the round-trip JSON exporter today.** Everything in point 3 and 4, built this week. Rejected on
  timing only: a rev-locked target without a customer means a fixture re-pinned on their schedule, and release
  criteria 2 and 5 (two demo datasets; a comparison of outputs) are the work that makes a comparison with their
  output honest. The mapping is kept; the code waits.
- **Option 4 — a neutral interchange format of our own.** `metadata/dv_model.yml` with the catalogue and the
  bindings already is one, documented and read back by `run --existing`. Nothing to add; an adapter to any engine
  is the exporter of point 4, and a second format for its own sake would be a standard nobody asked for.
- **Option 5 — their MCP server as a *sink* in the pipeline** (calling `create_source_metadata` and
  `commit_model` from the HITL checkpoint). Rejected: it would be a second backend in all but name, it moves the
  customer's model through a server this project does not run, and it inherits every loss of Option 2.

## Consequences

- **Positive.** C32 is decided without code; the mapping is recorded while the reading is fresh and the files are
  named at a commit, so the day it is needed starts from this page and not from the repository. The product's
  claim stays coherent: the model is the product, the dbt project its proof, and nothing suggests the proof is
  optional.
- **Negative.** A datavault4dbt prospect today hears „we can, in a day" rather than „here is the file" — the
  cost of point 1, accepted. The mapping in point 3 is against an intermediate model (`domain.py`) read at one
  commit; the JSON field names were not read and will differ in spelling, which is what the fixture in point 4 is
  for.
- **Neutral.** Scalefree's channel is not entered and not avoided. Their `source_metadata` format — the one
  interface they version publicly — is the natural first file to write if a customer wants to hand them a
  catalogue this project read (WP96–WP99); it is not an export of a model and needs no ADR.

## References

- Backlog C32 (`docs/architecture/backlog-2026-10-candidates-3.md`); the finding of 2026-10-30 (`docs/log.md`,
  „TurboVault Engine (Scalefree): a competitor at the exit and in the channel"); `docs/competitive-landscape.md`,
  update 2026-10-30.
- Read on 2026-10-31 at `github.com/ScalefreeCOM/turbovault-engine`, HEAD `2dd2d9802f8884ea6002b5657a72e8a09e253ee9`
  (2026-10-29), version 0.21.0: `backend/engine/services/model_import_schema.py`,
  `backend/engine/services/imports/domain.py`, `backend/engine/services/imports/parsers/source_metadata.py`,
  `backend/engine/mcp.py` (`commit_model`, `validate_model`, `generate_dbt`), `docs/04_concepts/05_model-import-schema.md`,
  `docs/04_concepts/04_json-import.md`, `docs/02_getting-started/05_mcp-server.md`. Nothing installed or run.
- ADR-0003 (AutomateDV the backend), ADR-0007 (layer scope), ADR-0015 (positioning); `docs/log.md` 2026-10-04
  (AutomateDV stays the one backend until it runs clean); WP74 (the carried catalogue), WP77/WP82 (the bindings),
  WP36/WP93 (translations), WP94 (optional participants).
