# 5. Configuration reference

## 5.1 Settings & environment variables

All runtime configuration is environment-based (with `.env` as fallback), defined in
`src/vault_agent/config.py` and constructed lazily on first use. Variable names are the
upper-case forms of the fields:

| Variable | Default | Consumed by | Notes |
|----------|---------|-------------|-------|
| `LLM_PROVIDER` | `anthropic` | all LLM agents | The route to Claude and therefore where text and metadata are processed: `anthropic`, `bedrock`, `vertex` (5.5) |
| `ANTHROPIC_API_KEY` | — (required for `anthropic`) | all LLM agents | Required only at the first LLM call, not at import; not needed on the other routes |
| `AWS_REGION`, `AWS_PROFILE` | — (`AWS_REGION` required for `bedrock`) | client construction | Region of the Bedrock endpoint, e.g. `eu-central-2` (Zurich); credentials via the standard AWS chain |
| `GCP_PROJECT_ID`, `GCP_REGION` | — (both required for `vertex`) | client construction | `europe-west1`, `eu` or `global`; auth via Application Default Credentials |
| `PRIMARY_MODEL` | `claude-sonnet-4-6` | parser, key identifier, contracts, mapper | Sonnet tier. Passed to the provider **as written** — on `bedrock`/`vertex` set the ID the provider lists (5.5) |
| `HEAVY_MODEL` | `claude-opus-4-8` | dv2_modeler | Opus tier for the hard reasoning step; same rule |
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
| `DEFAULT_TARGET_PLATFORM` | `postgres` | `rules/platforms.py` | The platform a run without `--target-platform` generates for; its output is the byte-identity baseline |
| `DATABRICKS_UNSCALED_DECIMAL` | `decimal(38,18)` | `rules/platforms.py` | Seed type for a contract `number` on Databricks, where bare `NUMERIC` would be `DECIMAL(10,0)` and truncate fractions (9.6) |

## 5.5 LLM route and data residency

`LLM_PROVIDER` selects which client `ForcedToolCaller` is built with
(`llm.make_client`); everything above that function is route-agnostic. The choice
decides where requirements text, schema metadata and profiling statistics are processed —
the assessment behind it is `docs/architecture/deployment-residency.md` (Bedrock with an
EU region is the default answer for Swiss/DACH class-1 contexts).

| Route | Client (anthropic SDK) | You supply | Install |
|---|---|---|---|
| `anthropic` | `AsyncAnthropic` | `ANTHROPIC_API_KEY` | default |
| `bedrock` | `AsyncAnthropicBedrockMantle` (Bedrock's Messages-API endpoint) | `AWS_REGION`, AWS credentials (env, `AWS_PROFILE`, role) | `uv sync --extra bedrock` |
| `vertex` | `AsyncAnthropicVertex` | `GCP_PROJECT_ID`, `GCP_REGION`, ADC login | `uv sync --extra vertex` |

A route with a missing value fails **at construction**, naming the variable
(`llm_provider='bedrock' requires aws_region (AWS_REGION)`); a missing provider library
fails at the first client build, naming the extra to install. Both before any token is
spent. The route is visible twice per run: the summary's `llm route:` line, and the
`llm_route` header plus the per-call `client` field in the trace (10.2) — the evidence a
customer's residency questionnaire asks for.

**Model identifiers are not translated.** Set `PRIMARY_MODEL`/`HEAVY_MODEL` to what the
chosen provider lists: first-party `claude-sonnet-4-6`; Bedrock IDs carry an `anthropic.`
prefix and, on the legacy InvokeModel route, a geography profile such as `eu.`; Vertex
uses bare or `@`-versioned IDs. Look them up in the provider console at deployment time —
they change per release, and a guessed ID is a 404 after the first prompt has been built.

**Verification status (2026-09-12): keyless-only.** The switch, its validation and the
factory's dispatch are pinned by `tests/test_llm_provider.py` against recording fakes and
against the installed SDK's class names (anthropic 0.107.0). No run has gone through
Bedrock or Vertex; prompt caching and forced tool use are listed as available on both by
the SDK's platform table, which is a statement about the platforms, not a measurement of
this pipeline on them. The first customer deployment on either route is the measurement.

## 5.4 LangSmith (optional, eval-only)

With `LANGSMITH_API_KEY` set *and* the `eval` extra installed, live eval runs create
one LangSmith dataset per case and log runs with scores as feedback (11.5). Without
either, the upload layer is a silent no-op. The pipeline itself never talks to
LangSmith — run observability is local-first via traces (chapter 10).
