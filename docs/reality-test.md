# Reality test — vault-agent on a deliberately messy, multi-source requirements doc

> **Purpose.** Empirically pressure-test the pipeline against input built to break it (the
> opposite of the clean toy demos), to confirm or refute the [pre-mortem](pre-mortem.md) and
> produce a concrete hardening backlog. **Snapshot: 2026-06-17.**

## Setup

- **Input:** [`examples/inputs/messy_insurance_requirements.md`](../examples/inputs/messy_insurance_requirements.md)
  — a DACH insurer "Fachkonzept" that is deliberately contradictory, incomplete, mixed DE/EN,
  multi-source, and mixes functional/non-functional/compliance noise. It stresses every pre-mortem
  risk at once: business keys buried/ambiguous (AHV/UID *"sofern vorhanden"*, plus a GUID surrogate
  trap), person/company subtyping, multi-role participations (policyholder / insured / payer /
  beneficiary), a stated contradiction (one policyholder vs. *Verbundverträge*), temporal history
  (address, premium versioning), a transactional concept (claim payments), and three source systems
  (VICTOR / CRM / ClaimsPro) describing the same partners differently.
- **Cryptic source schema:** [`examples/inputs/messy_insurance_source_schema.yml`](../examples/inputs/messy_insurance_source_schema.yml)
  — physical legacy names (`PARTN_NR`, `KD_NAME_1`, `AHV_NR`, …) that deliberately differ from the
  business prose, to test grounding.
- **Two runs:** (1) prose only — tests graceful degradation; (2) `--source-schema …` — tests
  grounding (ADR-0004).

## TL;DR verdict

**The pre-mortem is confirmed empirically: no showstopper.** On input designed to break it, the
pipeline did not crash and did not produce confident garbage. It produced a **coherent, competent,
reviewable** model, **flagged** the gaps, and the **safety net (validator + grounding + HITL)
caught the worst issues**. Every weakness found is **assist-quality / UX**, each with a small, clear
fix — none is architectural.

## Run 1 — prose only: what the model got right

(From the generated `automatedv.yml`.)

- **Business keys (the sharpest risk):** avoided the GUID surrogate trap; took the natural keys and
  *encoded the harmonisation need in the name* — `hub_partner.src_nk =
  PARTNER_BUSINESS_KEY_HARMONISED_AHV_UID_PARTN_NR`. It surfaced the ambiguity instead of inventing
  a wrong simple key.
- **Multi-source identity:** a dedicated `sat_partner_source_ids` holding `AHV_NUMBER, UID,
  VICTOR_PARTN_NR, CRM_ACCOUNT_ID` — competent DV thinking (track the unreconciled source keys
  rather than wrongly merge them).
- **Subtyping:** one `hub_partner` + a type attribute (`PARTNER_TYPE_PRIVATE_COMPANY`), not
  over-engineered into two hubs.
- **Compliance/PII:** health-claim data split into its own `sat_claim_health_data` — the DSG/DSGVO
  "besonders schützenswerte Daten" requirement actually honoured.
- **Temporal:** premium versioning (`sat_contract_premium`), address (`sat_partner_address`,
  multi-active with `src_cdk=ADDRESS_TYPE`), policyholder period (a *real* eff_sat with
  `src_dfk=CONTRACT_HK`).
- **Safety net engaged:** the validator flagged the redundant links
  (`W_LINK_REDUNDANT_GRAIN`); the HITL checkpoint required owners for 5 contracts and flagged
  "inferred from prose — review against the real source".

## Run 1 — what went wrong (modeling weaknesses)

- **Contradiction duplicated, not resolved:** the §3.3-vs-§4 contradiction (one policyholder vs.
  multi-role *Verbundverträge*) produced **two overlapping** contract↔partner links
  (`link_contract_partner_policyholder` **and** `link_contract_partner_role`). The validator caught
  it, but the modeler should resolve it or flag the contradiction explicitly, not emit both.
- **eff_sat inconsistency:** `sat_contract_partner_role_effectivity` is named "effectivity" but was
  emitted as a **standard** satellite (has `src_hashdiff`, no `src_dfk`) carrying
  `EFFECTIVE_FROM/TO` as payload — inconsistent with its sibling
  `sat_contract_policyholder_effectivity`, which is a real eff_sat. No gate caught this.
- **Multi-role half-modelled:** "role" (VN / insured / payer / beneficiary) never became a clean
  first-class construct.
- **Minor:** `hub_claim_payment` modelled as a hub (a payment is arguably a transactional event);
  `hub_broker` has no satellite (`W_HUB_NO_SAT`); names are business-language (the known Phase-2
  gap).

## Run 2 — grounded: grounding works (and steers)

- **Per-source-table contracts** (VICTOR_PARTNER, VICTOR_VERTRAG, CRM_ACCOUNT, CLAIMSPRO_CLAIM,
  CLAIMSPRO_PAYMENT) — the data-contract agent switched to the schema-driven mode.
- **Warnings fire precisely:** `W_BK_NOT_IN_SOURCE` / `W_ATTR_NOT_IN_SOURCE` flagged exactly the
  modeller-invented concepts with **no** source backing — `broker_code` (no broker source table
  supplied), `role_type`, `effective_from/to`, `commission_*`.
- **The strong part — steering, not just flagging:** attributes that warned as business names in
  run 1 (`NAME`, `STREET`, `AHV_NUMBER`) did **not** warn in run 2, because the schema in the prompt
  steered the modeler to the real source columns (the [GUIDE] half of ADR-0004). Grounding both
  **directs** to real columns *and* **flags** the genuinely unbacked — as designed.

## Run 2 — the new finding (signal-to-noise + types)

51 review items, of which **39 are `undetermined type; review required`** — one per source column,
even obvious ones (`Amount`, `ValueDate`, `Currency`). Root cause: the declared schema carries only
`{table, columns}` with **no types**, so the contract enricher cannot type the cryptic columns and
honestly returns "unknown". Two problems:

1. **Signal-to-noise:** the 39 routine type flags **bury** the 7 substantive warnings (redundant
   grain, BK-not-in-source). The checkpoint becomes hard to read.
2. **Type gap:** without types in the schema, contract typing is worthless.

*(Verify by inspecting `output_messy_grounded/contracts/VICTOR_PARTNER.contract.yml` — expect all
`data_type: unknown`.)*

## Hardening backlog (prioritized)

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | Contradiction → duplicated links instead of resolution | Medium | Modeler prompt: resolve OR explicitly flag a stated contradiction; consider escalating `W_LINK_REDUNDANT_GRAIN` to a blocking review item |
| 2 | "effectivity" satellite emitted as a standard sat | Medium | New validator gate: a satellite whose payload is essentially a start/end date pair on a link → warn "should this be an effectivity satellite?" |
| 3 | Review-queue noise: 39 `undetermined type` flags drown the substantive warnings | Medium (UX) | Aggregate routine flags ("N fields with undetermined type") and order blocking-first; keep individual detail in the artifact, not the headline queue |
| 4 | Declared schema carries no types | Medium | Extend the schema format to typed columns (`{name, type}`) and/or the DDL-parsing producer (already on the roadmap) so types come from the source, not a guess |
| 5 | Multi-role participations not a first-class pattern | Low–Med | Give the modeler a clear DV pattern (role-typed link / per-role links) for multi-role relationships |
| 6 | `hub_broker` has no satellite; `hub_claim_payment` as a hub | Low | Modeler-guide nuances; both already validator-flagged / reviewable |

All six are **assist-quality or UX**, consistent with the pre-mortem: the structure holds, the work
is to sharpen assistance and reduce review noise.

## Caveats

- This is **one run per mode**; the modeler is non-deterministic, so a re-run may differ in detail.
  Treat as a strong sample, not a proof — which is itself an argument for the eval harness
  (pre-mortem C2) to make quality measurable rather than anecdotal.

## Conclusion

The test built to embarrass the project did the opposite: it produced a credible model on genuinely
messy, multi-source input, flagged its own gaps, and the safety net caught the rest. The output is a
**concrete, prioritized hardening list**, not a verdict against the architecture. This is the
position to be in before going wide — and the inputs/outputs here double as honest evidence that the
tool degrades gracefully.
