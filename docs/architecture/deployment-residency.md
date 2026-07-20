# Deployment & data residency (Charter B)

Status: Informational · Facts verified 2026-07-18 against the linked official sources —
**re-verify before quoting in a customer context**; cloud model/region availability
changes monthly.

## What data leaves the environment

vault-agent sends to the LLM: requirements-document **text**, declared **schema
metadata** (table/column names, types, comments), **profiling statistics**
(ratios, distinct counts, example values), and model/mapping context derived from
these. **No row-level data is read or transmitted by design** — the pipeline consumes
documents and metadata, never source-table contents. (Profiling example values are the
one field that *can* carry data-derived strings; a data-sensitive deployment can supply
profiling without `example_values` — the mapper degrades gracefully, see the WP9 §10.7
opacity probe.)

## Three supported routes to Claude

| | Anthropic API (first-party) | AWS Bedrock | Google Vertex AI |
|---|---|---|---|
| **No-training on customer content** | Contractual (Commercial ToS §B, eff. 2025-06-17) | AWS FAQ: no training, inputs/outputs not shared with the model provider; Anthropic has no access to prompts/completions | Google whitepaper: no training on customer data by default |
| **EU/CH processing** | **No EU inference option** (`inference_geo`: us/global only); EEA/CH/UK contract with Anthropic Ireland | **Yes**: EU geographic inference profile across EU regions incl. **eu-central-2 (Zurich)** — data at rest stays in the source region; inference may move *within* EU geography | **Yes**: `europe-west1` regional + `eu` multi-region endpoint; newest models partly global/multi-region only |
| **Retention** | 30 days standard; ZDR per org on request (per-feature eligibility; newest "Covered Models" excluded, 30-day floor) | Customer-side: no content logging unless customer opts in | Google as processor; regional at-rest guarantees |
| **Certifications (provider)** | SOC 2, ISO 27001:2022, ISO 42001:2023; DPA + trust.anthropic.com | AWS compliance programs apply | GCP compliance programs apply |

Key sources: anthropic.com/legal/commercial-terms · platform.claude.com/docs/en/manage-claude/data-residency ·
docs.aws.amazon.com/bedrock (models-region-compatibility, geographic-cross-region-inference, data-protection) ·
platform.claude.com/docs/en/build-with-claude/claude-on-amazon-bedrock and …/claude-on-vertex-ai.

## Recommendation for Swiss/DACH class-1 contexts

**Bedrock with the EU geographic profile** is the default answer (Zurich data-at-rest
possible via eu-central-2; note inference may run in other EU regions — encrypted,
logged via CloudTrail `inferenceRegion`; SCPs must allow the destination regions).
Vertex `europe-west1`/`eu` is the GCP-shop equivalent. The first-party API is fine for
development and non-restricted contexts. There is **no on-premises option for
Claude-class models today** — an open-weights fallback would first need a full pass
through the WP6 eval harness before any quality claim is made (honest gap, per house
rule: never claim what is not measured). FINMA context: Guidance 08/2024 (AI
governance) plus the outsourcing/operational-risk circulars 2018/3 and 2023/1 frame the
assessment; vault-agent's HITL ratification + ADR audit trail map directly onto its
model-risk-controls expectations.

## Configuration path (already architected, not yet wired)

All LLM traffic flows through one class (`vault_agent/llm.py: ForcedToolCaller`) with an
**injectable client** — the switch is confined to client construction: the Anthropic SDK
ships `AnthropicBedrock` (region + `eu.`-prefixed inference-profile model IDs) and
`AnthropicVertex` (`region="europe-west1"` or `"eu"`). Making this a config option
(provider + region in `config.py`) is a small, self-contained WP when the first
deployment needs it; model-ID mapping per provider is the only nuance.

## Vendor-questionnaire quick answers

**Is our data used for training?** No, on all three routes (contractual). ·
**Where is it processed?** Bedrock/Vertex: EU (CH at rest possible on AWS); first-party:
US/global. · **How long is it retained?** First-party 30 days (ZDR negotiable, with
model caveats); Bedrock/Vertex: no provider-side content retention, customer-side
logging is opt-in. · **Who can see prompts?** Bedrock: neither AWS operators nor
Anthropic (deployment-account architecture); first-party: Anthropic per DPA/trust
center. · **What data classes are sent?** Documents + metadata + profiling stats, no
row data (see above). · **Sub-processors?** trust.anthropic.com/subprocessors (check
live — the list is dynamic).
