# Walkthrough: Health Insurance

The second demo domain, chosen to show the pipeline generalizes beyond retail banking into
a DACH-relevant insurance domain with richer Data Vault structure (effectivity, multi-active
satellites, and an auditable coverage/status split).

## Input

[`examples/inputs/health_insurance_requirements.md`](../../examples/inputs/health_insurance_requirements.md) —
a toy spec: insured persons hold policies (transferable within a household), premiums are
paid against policies, claims are submitted against policies and reference a healthcare
provider, and coverage/status changes must be auditable.

## Run

```bash
vault-agent run examples/inputs/health_insurance_requirements.md --out output
```

## Representative result

```
requirements:  29
business keys: 6
model:         4 hubs, 3 links, 8 satellites
dbt models:    15
validation:    PASSED (0 issues)
```

**Hubs** — `hub_insured_person` (national insured number), `hub_policy` (policy number),
`hub_claim` (claim number), `hub_healthcare_provider` (provider registration number).

**Links** — `link_insured_person_policy`, `link_policy_claim`,
`link_claim_healthcare_provider`.

**Satellites** — note the modelling quality:

- `sat_policy_coverage` and `sat_policy_status` are **split** because coverage and status
  change independently and each needs its own audit trail (who/what/when/why).
- `sat_insured_person_policy_effectivity` is an **effectivity satellite on the link** —
  exactly how Data Vault models the transferable insured-person→policy relationship: a
  transfer end-dates the current link row and opens a new one. It is generated as
  `automate_dv.eff_sat` (driving FK = `INSURED_PERSON_HK`, secondary FK = `POLICY_HK`).
- `sat_insured_person_address` is **multi-active** (one person, several active addresses),
  generated as `automate_dv.ma_sat` with `ADDRESS_TYPE` as the child dependent key.

Every construct is traced back to specific requirement ids in the generated
`ADR-0004` (status `Proposed`, pending human review).

## Flags surfaced for human review (honest limitations)

The pipeline does not pretend to be perfect — it surfaces what it cannot yet do correctly
rather than emitting wrong code:

- **Premium payments were dropped.** The modeler proposed `link_policy_premium_payment`
  connecting only one hub, which violates the "a link connects ≥2 hubs" rule, so the
  structural check dropped it (and its satellite). Premium payments have no business key
  and relate only to the policy, so they are better modelled as a transactional link or a
  multi-active satellite — a known area for the modeler to improve.
- **Transactional links** (`automate_dv.nh_link`, the macro that supersedes the deprecated
  `t_link`) are not yet templated; when the modeler proposes one it is flagged for human
  review rather than generated.

The multi-active and effectivity satellites above *are* generated (code generator Phase 2):
`automate_dv.ma_sat` and `automate_dv.eff_sat`.

## What this demonstrates

- The pipeline generalizes across domains with no code changes — only a new input document.
- The DV2.0 rules act as a guardrail: invalid constructs are dropped and reported rather
  than silently turned into broken dbt models.
- The deterministic stages (code generation, validation, ADR authoring) make the output
  reproducible and the architecture record free of hallucination.
