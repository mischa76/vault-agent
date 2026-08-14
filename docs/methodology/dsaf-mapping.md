# Roelant Vos / DSAF — assessment outcome

> **Purpose:** Record the outcome of critically assessing Vos/DSAF against Vault-Agent, so future
> work neither repeats the assessment nor silently adopts Vos positions that diverge from the
> Linstedt/Olschimke DV2.0 canon (CDVP² conformance).
>
> **Sources:** a curated study set compiled from roelantvos.com (May 2026). Vos's tooling, repo
> and version specifics are volatile and deliberately not recorded here — look them up live when
> they matter; his current commercial product is listed where vendor names belong, in
> `docs/competitive-landscape.md`.

## The finding: nothing adopted

The assessment concluded with **zero adoptions**. The one genuine resemblance — metadata-driven
automation of Data Vault generation — is convergent, not inherited: Vault-Agent's
rules-and-metadata-in-code plus AutomateDV-template architecture predates the DSAF study and was
chosen independently. Vos/DSAF material is **commentary and an alternative school**, not a
foundation of this project. His tooling ecosystem (metadata tool, generator, run-time control)
is a parallel stack, not a dependency.

## The guardrail: where Vos ≠ Linstedt DV2.0

This is the part of this file that must survive. Vos has, over fifteen years, *deliberately
revised* several DV2.0 positions; an agent that encounters his material while researching a
modelling question must not mistake those revisions for canon. Stance: **anchor DV2.0 correctness
on Linstedt/Olschimke (matches CDVP²); each Vos revision is an opt-in, ADR-gated alternative —
never the silent default.**

| Topic | Linstedt DV2.0 canon | Vos's position | Vault-Agent |
|---|---|---|---|
| Surrogate key | Hash key (MD5/SHA-1) | **Natural Business Key (NBK)** preferred for small/medium; hash only for MPP | Default to hash (canon, AutomateDV-native). NBK = future ADR. |
| Satellite end-dating | Persisted load-end-date common | **Insert-only**, derive end-date on read; end-dating deprecated | Keep canon default; insert-only is a legitimate ADR. |
| Link-Satellites | Standard DV2.0 construct | **ELM** (Hultgren) — relationship-describing Hubs, no physical LSAT | Keep LSAT (canon). Flag ELM as an alternative school, not a default. |
| Driving keys | Driving-key LSAT + effectivity sat | **Foreign-key Link** (his 2023 remedy) | Encode the canon driving-key/effectivity first; FK-link is an alternative. |
| Multi-active sats | Attribute-in-PK / separate sat | Prefers **weak Hub** or JSON-in-SAT | Support canon; weak-Hub as option. |
| Key collision | **BKCC** (per-source collision code) | Composite/concatenated keys + Record Source | Note both; BKCC is the canon answer. |

Vos has adopted Hultgren's ELM as his preferred physical implementation since ~2023 — the
Genesee-Academy (modelling-only) vs Scalefree/Linstedt (full trilogy) tension. Vault-Agent stays
on the Linstedt trilogy as its spec of record and references ELM/Vos as commentary.

## Out-of-scope constructs (DV-generic, not DSAF debts)

PSA and PIT/Bridge entered the discussion via the study set but are generic warehouse constructs,
not Vos-specific ideas. Both are ADR-gated out of scope in code (see the out-of-scope comment in
`src/vault_agent/rules/dv2_rules.py`); the code generator's actual repertoire is owned by
`src/vault_agent/agents/code_generator.py` — read it there, don't trust prose. PIT/Bridge is the
codeable next feature (AutomateDV supports both — re-verify against the installed package when
implementing); PSA is architecturally heavy, sits outside the core DV2.0 raw vault, and is a
deliberate ADR decision if ever.

## Candidate ADRs

1. **PSA: yes/no** — persistent staging area, or AutomateDV staging + source replay?
2. **Hash key vs NBK** — keep hash as the canon default; document when NBK would win.
3. **End-dating vs insert-only satellites** — which is the generated default, on which target.
4. **ELM / foreign-key Link vs classic LSAT + driving key** — modelling-school stance.
5. **PIT/Bridge generation** — add to the code generator's repertoire for the presentation layer.

## Primary sources, if ever needed

*Data Engine Thinking* (Vos & Lerner, 2025) is the canonical methodology; the whitepapers on data
mart delivery, referential integrity and merging time-variant sets are the deep material for PSA
or presentation-layer work. Fetch them at implementation time.
