# ADR-0001: Primary LLM = Anthropic Claude

**Status:** Accepted
**Date:** 2026-06-07
**Decision makers:** Mischa Eismann

## Context

The agents need an LLM with strong structured reasoning, reliable tool use, and a mature
MCP ecosystem. Token costs matter but are secondary to quality at this stage.

## Decision

Use Anthropic Claude (Sonnet as default, Opus for the DV2.0 Modeler's hardest cases) via
the official `anthropic` Python SDK and `langchain-anthropic` integration. Tool calls
follow Anthropic's tool-use schema; MCP is the standard tool-integration mechanism.

## Alternatives considered

- **OpenAI GPT-4.1 / o-series** – strong but tool-use ergonomics noisier; MCP support newer
- **Open-source models (Llama 3.3, Mistral)** – cost-attractive but quality gap on structured
  output tasks is still significant for production demos
- **Multi-provider abstraction (LiteLLM)** – extra abstraction without immediate benefit;
  can be added later if needed

## Consequences

- (+) Best-in-class tool use means less prompt engineering
- (+) MCP-native means tool layer designs cleanly
- (-) Vendor lock-in at the SDK level (mitigated by keeping prompt and state pure data)
- (-) API costs (mitigated by Sonnet-default + Opus-on-demand)

## References

- Anthropic Claude docs: https://docs.anthropic.com
- LangChain-Anthropic integration
