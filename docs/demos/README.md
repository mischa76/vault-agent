# Demo datasets

Toy requirements documents used to exercise the full pipeline end to end. Two domains are
provided so the system can be shown to generalize beyond a single example (a prerequisite
before any UI work — see CLAUDE.md).

| Domain | Input document | Walkthrough |
|---|---|---|
| Retail banking | [`examples/inputs/bank_account_requirements.md`](../../examples/inputs/bank_account_requirements.md) | (see examples 01–07) |
| Health insurance | [`examples/inputs/health_insurance_requirements.md`](../../examples/inputs/health_insurance_requirements.md) | [health-insurance-walkthrough.md](./health-insurance-walkthrough.md) |

Run either through the CLI:

```bash
vault-agent run examples/inputs/health_insurance_requirements.md --out output
```

The requirements parser, business-key identifier, and DV2.0 modeler are LLM-driven, so the
exact model varies between runs; the code generator, validator, and ADR author are
deterministic. The walkthroughs show representative output.
