# Status and limits

What vault-agent has been shown to do, how it was shown, and what is not shown yet. Three words are
used strictly here and in every release note:

- **live** — a paid run against the real model API, end to end;
- **built** — the generated dbt project built by `dbt build` on a real warehouse, without a model call;
- **keyless** — covered by the offline test suite only.

## What runs

The pipeline runs end to end, from the command line and from the browser workbench: requirements
parsing, business keys, data contracts, entity resolution and link proposals, a resolution
checkpoint, the Data Vault model, code generation on AutomateDV, validation with a bounded
re-model loop, source mapping, a sign-off checkpoint, and a proposed decision record. An existing
vault can be extended (`run --existing`); an extension adds and never migrates.

## What is verified

- **Live:** the five-step AdventureWorks chain (person, human resources, purchasing, production,
  sales — 68 tables) has been run more than twenty times since September 2026; the recent runs on
  the current model generation are green. The modeller's choices vary between runs: one run is a shape, not a
  distribution.
- **Built on PostgreSQL:** the chain's projects, the bank and mapping demos, and the shipped
  workbench demo (`demo/workbench-adventureworks/`), which builds whole and inserts nothing on a
  second build. Two of its link stages still need a hand-made view.
- **Built on Databricks:** the bank demo and the AdventureWorks chain (October 2026, operations
  manual 9.6).
- **Keyless:** every gate, every generator path and the workbench API, in a suite that runs without
  an API key.

## Limits

- **Scale.** Verified at about 30 tables of real semantic variety per increment. Larger synthetic
  landscapes complete and validate, but they repeat structure rather than add meaning, so they
  measure width, not semantic scale. The model itself is one artefact that cannot be split.
- **Domains.** One real schema family (AdventureWorks) and synthetic bank and insurance examples.
  No second real domain and no customer project yet.
- **Platforms.** PostgreSQL and Databricks are built. Snowflake and Microsoft Fabric are targets,
  not results.
- **Layers.** Staging and Raw Vault are generated. In the Business Vault, point-in-time tables and
  bridges along a ratified link path are generated; business rules are flagged for a human, never
  emitted as authoritative. Marts are not built.
- **Hub keys.** Since ADR-0021 the key of a hub is decided from the source's declared keys and the
  ranked candidates, and asked at the checkpoint where they disagree. A source catalogue without
  declared keys gets no decision.
- **Loading.** The generated vault has no record-tracking satellites and no delete detection.
- **Use.** A single-user tool run by a practitioner on their own machine (ADR-0015); no
  authentication, no shared state.
- **Review load.** A human answers on the order of 85 decisions for the five-step chain. That
  number is tracked per run and has not been driven down as a goal of its own.

## What 1.0 waits for

Versions stay below 1.0 until all five hold, each checked by a recorded measurement:

1. **A second real domain** — not AdventureWorks, from banking or insurance, modelled from
   requirements written independently of the schema, built and idempotent on PostgreSQL.
2. **Two consecutive minor releases without a wrong-data fix** — no correction that changes the
   rows of a generated vault for unchanged inputs. A gate that refuses more is not such a
   correction; a generator that hashes another column is.
3. **AdventureWorks builds without a hand-made view** — every link stage bound by rule or at
   sign-off.
4. **Positioning decided and its consequences built** — decided as the single-user tool
   (ADR-0015) and built.
5. **One evaluator walk-through by someone outside the project**, following
   [the written guide](evaluator-guide.md).

Not criteria: Snowflake or Fabric builds, marts, semantic scale above about 30 tables, a package
on PyPI.

Until then an output-changing correction is a minor release, never hidden in a patch; the
[CHANGELOG](../CHANGELOG.md) says for each release what was verified live and what keyless.
