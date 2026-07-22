# 5. Configuration reference

## 5.1 Settings & environment variables

All runtime configuration is environment-based (with `.env` as fallback), defined in
`src/vault_agent/config.py` and constructed lazily on first use. Variable names are the
upper-case forms of the fields:

| Variable | Default | Consumed by | Notes |
|----------|---------|-------------|-------|
| `ANTHROPIC_API_KEY` | — (required) | all LLM agents | Required only at the first LLM call, not at import |
| `PRIMARY_MODEL` | `claude-sonnet-4-6` | parser, key identifier, contracts, mapper | Sonnet tier |
| `HEAVY_MODEL` | `claude-opus-4-8` | dv2_modeler | Opus tier for the hard reasoning step |
| `LANGSMITH_API_KEY` | unset | eval upload only (11.5) | Pipeline never uses it |
| `LANGSMITH_TRACING` | `false` | eval harness | |
| `LANGSMITH_PROJECT` | `vault-agent-dev` | eval upload | Workspace name |

Unknown variables in the environment or `.env` are ignored (`extra="ignore"`) — a
stale entry never crashes startup. There is deliberately no logging configuration
here: logging is a CLI concern (`--debug`, 10.1), never a library setting.

## 5.2 Model tiers

Four of the five LLM agents run on the **primary model** (Sonnet tier); only the
**dv2_modeler** — the one hard-reasoning step, where construct selection and splitting
decisions happen — runs on the **heavy model** (Opus tier). Model id strings must be
valid Anthropic API model ids; when bumping either variable, run the model-release
protocol (11.4) before trusting the output, and expect the modeler bump to be the one
that matters.

Cost behaviour worth knowing: every call forces a single tool response, and the system
prompt is sent as a cache-controlled block. Since the modeler's system prompt is
byte-identical across its retries, a re-model loop hits the prompt cache and pays
mainly output tokens. The data-contract agent enriches in bounded units (per asset,
and per 40-column chunk for wide tables), so wide legacy schemas scale in call count,
not in per-call size — with the cached system prompt keeping the extra calls cheap.

## 5.3 Pipeline constants worth knowing

These are code constants, not configuration — changing them is a code change — but
they explain behaviour you will observe:

| Constant | Value | Where | Effect |
|----------|-------|-------|--------|
| `MAX_MODELING_ATTEMPTS` | 3 | `graph.py` | Re-model loop budget; at the cap the run ends as failed |
| `MAX_DOCUMENT_CHARS` | 400 000 | `requirements_parser.py` | Longer documents are cut to the head and flagged (never silently) |
| `SAT_WIDE_ATTRIBUTE_THRESHOLD` | 30 | `rules/dv2_rules.py` | Wider satellites get an advisory split flag (`W_SAT_WIDE`) |
| `AUTOMATE_DV_VERSION` | 0.11.4 | `rules/dv2_rules.py` | Pin written into generated `packages.yml`; bump deliberately and re-verify the demos |
| `AGGREGATE_THRESHOLD` | 3 | orchestrator | More than 3 advisory flags per group collapse to one review-queue line |

## 5.4 LangSmith (optional, eval-only)

With `LANGSMITH_API_KEY` set *and* the `eval` extra installed, live eval runs create
one LangSmith dataset per case and log runs with scores as feedback (11.5). Without
either, the upload layer is a silent no-op. The pipeline itself never talks to
LangSmith — run observability is local-first via traces (chapter 10).
