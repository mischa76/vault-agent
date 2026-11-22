# ADR-0001: Data Vault model derived from requirements

**Status:** Proposed
**Date:** 2026-06-10
**Decision makers:** Vault-Agent (generated) — pending human review

## Context

This model was derived automatically by the Vault-Agent pipeline from 1 requirement(s) and 1 business key candidate(s). It records the Data Vault 2.0 structures the modeler chose and traces each back to the requirements that justify it.

## Decision

Model the following Data Vault 2.0 structures.

### Hubs (1)

- **hub_customer** — business key `national customer ID`. The customer. _(requirements: REQ-007)_

### Links (1)

- **link_account_customer** — connects hub_account, hub_customer. Account ownership. Unit of work: one ownership event per (account, customer). _(requirements: REQ-001)_

### Satellites (2)

- **sat_customer_details** — on hub_customer; payload: customer name, date of birth. Customer attributes. Split rationale: split from PII by rate of change. _(requirements: REQ-009, REQ-010)_
- **sat_account_balances** — on hub_customer; payload: balance. Balances. _(requirements: REQ-011)_

## Alternatives considered

The automated modeler did not record alternative designs. Reviewers should consider whether any object modelled as a hub is better expressed as a link (or vice versa), and whether the satellite splits match the true rate of change of the attributes.

## Consequences

- Positive: every construct is traceable to the specific requirements listed above.
- Neutral: status is Proposed — a human must review and accept this model.
- Caveat: 1 construct(s) could not be generated and are flagged for human review: sat_account_balances.

## References

- Source requirement document(s): examples/inputs/bank_account_requirements.md
- Generated dbt models: 2 raw-vault model(s) + 2 staging model(s) (see `state.artifacts`)
