# Architecture diagrams

Two views, maintained by hand alongside the code: the component/layer architecture and a
standard (grounded) processing run. Update when the graph topology or a layer changes —
last verified against `graph.py` / CLAUDE.md milestones 2026-07-19.

## Components / layers

```mermaid
flowchart TB
    subgraph IF["Interface"]
        CLI["CLI: vault-agent run / resume<br/>(+ interactive checkpoint prompt, WP12)"]
        REP["report.html (WP11)"]
        RQ["review-queue.md · mappings.review.yml"]
    end

    subgraph ORCH["Orchestration"]
        GRAPH["LangGraph state machine (graph.py — no business logic)"]
        STATE["VaultAgentState (pydantic, single state model)"]
        CKPT["SQLite checkpointer — HITL interrupt/resume (ADR-0006)"]
    end

    subgraph AGENTS["Agents"]
        direction LR
        subgraph LLMA["LLM-backed"]
            RP["requirements_parser"]
            BK["business_key_identifier"]
            DC["data_contract"]
            DM["dv2_modeler"]
            SM["source_mapper"]
        end
        subgraph DETA["Deterministic"]
            OR["orchestrator"]
            VAL["validator (32 E_/W_ gates)"]
            CG["code_generator + staging_generator"]
            HC["human_checkpoint"]
            AA["adr_author"]
        end
    end

    subgraph FOUND["Foundations"]
        RULES["rules/ — DV2.0 rules, naming, thresholds"]
        PROMPTS["prompts/*.md"]
        GROUND["grounding: source_schema · profiling"]
        LLM["llm.py ForcedToolCaller — retry · prompt cache · usage"]
    end

    subgraph EXT["External"]
        API["Anthropic API (Claude; Bedrock/Vertex EU routes: see deployment-residency.md)"]
        DBT["dbt + AutomateDV → Postgres / Snowflake / Fabric"]
    end

    EVAL["eval/ — datasets · scorers · runner · scale generator (quality instrument, separate)"]

    IF --> ORCH --> AGENTS --> FOUND
    LLMA --> LLM --> API
    CG --> DBT
    EVAL -.measures.-> ORCH
```

## Standard run (grounded)

```mermaid
flowchart TB
    IN["Inputs: requirements doc · --source-schema · --profiling"] --> OR["orchestrator<br/>ExecutionPlan, grounding on/off"]
    OR --> RP["requirements_parser"] --> BK["business_key_identifier"]
    BK --> DC["data_contract<br/>one contract per source table"]
    DC --> DM["dv2_modeler<br/>hubs · links · satellites"]
    DM --> CG["code_generator<br/>AutomateDV models + staging + scaffolding"]
    CG --> VAL{"validator<br/>32 gates"}
    VAL -- "fail (bounded by MAX_MODELING_ATTEMPTS)" --> DM
    VAL -- pass --> SM["source_mapper<br/>concept → column, honest gaps/unresolved"]
    SM --> HC{"human_checkpoint<br/>requires sign-off?"}
    HC -- "yes: interrupt()" --> PAUSE["pause — outputs so far + pending.json<br/>ratify via terminal prompt or resume flags<br/>(--owner · --mappings · --map · --accept)"]
    PAUSE --> HC
    HC -- no / ratified --> AA["adr_author<br/>per-run ADR-0001"]
    AA --> OUT["write_outputs: dbt project · contracts ·<br/>ADR · review-queue.md · report.html"]
```

Notes: the re-model loop feeds only `severity=error` issues back (WP3); the mapper runs
post-validation and re-binds staging itself (WP9 §4 note); the checkpoint node stays
pure before `interrupt()` because it re-executes on resume (ADR-0006).
