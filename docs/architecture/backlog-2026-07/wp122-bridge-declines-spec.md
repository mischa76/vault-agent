---
type: spec
status: measured
updated: 2026-11-08
---

# WP122 — Bridge proposals: no path back to its start, and a declined path is not proposed again (C53, option b)

Status: **Approved and in progress** (2026-11-08, the owner chose option (b) now and (a), grouping, later with the
checkpoint controls of C45/C51/C52) · Owner: Mischa Eismann · Author: Claude. Candidate C53.

## 1 What is wrong

The twenty-fifth chain declined every bridge and still answered **89** bridge decisions over five steps (1, 1, 7, 27,
53 — the chain's entry said 88; the person step had one too). Measured keylessly on the five saved models
(`propose_bridge_paths` re-run, 2026-11-08): **6** paths end on the participation they start from (e.g.
`hub_product,link_product_size_unit_measure,hub_unit_measure:size,link_product_weight_unit_measure,hub_product`), and
**36** were proposed again after an earlier step had declined them — the decline lives in the run's state, and an
extension starts without it.

## 2 The rules

1. `propose_bridge_paths` leaves out a path whose last participation equals its first (hub and role). A path between
   two roles of one hub (`hub_business_entity:vendor … hub_business_entity:employee`) is not a cycle and stays.
2. `propose_bridge_paths(model, declined=…)` leaves out the paths in `declined`. `VaultAgentState.declined_bridges`
   carries them; the code generator passes it.
3. `write_outputs` writes `metadata/bridge_decisions.yml` — `declined:` sorted, the carried declines plus this run's
   declined proposals, less any path this run built — only when the list is not empty (every other output stays
   byte-identical). `load_declined_bridges(path)` reads it (the output directory, the model file or the metadata
   directory, as `load_existing_naming`); a missing file is `[]`.
4. The CLI's `run --existing` and the workbench's extension pass `load_declined_bridges(existing)` into the run.
5. An operator can still build a declined path by naming it (`--bridge PATH`, WP115); it then leaves the list.

## 3 Not done

Grouping the variants of one link pair (option (a), later with C52's control); carrying *built* bridges into an
extension's `business_vault.bridges`; any change to the checkpoint's controls.

## 4 Pre-registration

- **P1** guards T1–T7 (`tests/test_wp122_bridge_declines.py`) red first, then green.
- **P2** suite, ruff, bare mypy green with no key reachable; WP115's guards unchanged.
- **P3 replayed on the chain, keylessly:** the five saved models, each step proposing with the declines the steps
  before it declined (in the chain: every proposal) — **49** proposals over the chain (1, 0, 5, 20, 23) instead of
  89, and no path whose start equals its end.
- **Not measured:** a live extension writing and reading `bridge_decisions.yml` end to end through the workbench
  (covered by T5/T6 through `write_outputs` and the loader, not by a paid run).

## 5 Measured (2026-11-08, keyless)

- **P1 ✔.** T1–T7 (8 tests), red by import at `9495180`; one fixture correction before green (the unit-of-measure
  hubs need `source_entity`), checked first against the code before the change: it proposed the cycle and the
  cross-role path, so T1 was red for its own reason.
- **P2 ✔.** Suite with no key reachable 1682 passed / 5 skipped (1674 + 8), ruff, bare mypy; WP115's 10 guards
  unchanged and green.
- **P3 ✔ exactly as pre-registered.** The five saved models, each step proposing with what the steps before
  declined: **1, 0, 5, 20, 23 — 49** over the chain instead of 89, no path whose start equals its end.
- **Not measured:** a live extension writing and reading `bridge_decisions.yml` through the workbench (T4–T7 cover the
  writer, the loader and both callers keylessly).
