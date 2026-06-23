# Spec — Effectivity-satellite incremental fix + demonstrable end-dating

> **Purpose.** Make the generated effectivity satellite work on AutomateDV's **incremental**
> path (today only full-refresh is green) so its signature feature — **auto end-dating of a
> superseded relationship** — actually runs, and prove it in the bank demo. Implementation-ready
> for Claude Code; `[ENFORCE]`/`[GUIDE]` discipline as in the other specs.
>
> **Author of spec:** review pass, 2026-06-17. **Implements:** Claude Code. **Builds on:**
> [poc-end-to-end-dbt-spec.md](./poc-end-to-end-dbt-spec.md).

## How to use this in Claude Code

This is a **generator fix** (product code, not just the demo) plus a demo enhancement. Keep
`ruff`/`mypy`/`pytest` green. **Verify against the real tool**: AutomateDV's exact incremental
behaviour must be confirmed by running `dbt run` incrementally on Postgres — do not assume; the
recommended fix below is a hypothesis to validate and adjust against the actual generated SQL.

Definition of done: an **incremental** `dbt run` of the eff_sat is green (no "column … specified
more than once"), and a **two-phase load** demonstrably end-dates the transferred account's first
ownership row; generator unit tests pin the fix; demo models regenerated; docs updated.

---

## 0. Symptom & evidence

On the bank Durchstich the eff_sat builds and loads on **full-refresh**, but:

- Both ownership rows of the transferred account `…91873fa8…` carry `effective_to = 9999-12-31`
  (verified): the superseded relationship was **not end-dated**.
- An **incremental** re-run fails on Postgres with `column "effective_from" specified more than
  once` (documented in `CLAUDE.md`'s milestone note).

So the effectivity feature is structurally present but never exercised — the most important thing
an eff_sat does (close out old relationships) is unproven.

## 1. Root cause

`_render_eff_sat` in `src/vault_agent/agents/code_generator.py` maps `src_eff` to the **same
column** as `src_start_date`:

```python
start_date, end_date = dates[0], dates[1]
...
"src_start_date": start_date,
"src_end_date":   end_date,
"src_eff":        start_date,   # ← same column as src_start_date (EFFECTIVE_FROM)
```

The effectivity satellite carries only two date attributes (start, end), so the generator reused
the start column for `src_eff`. On AutomateDV's incremental path the records CTE then references
that column twice → the Postgres error. AutomateDV needs `src_eff` to be a column **distinct from
`src_start_date`** (and, to be safe, distinct from `src_end_date` and `src_ldts`).

## 2. Fix — generator [ENFORCE]

`src_eff` must reference a **dedicated effectivity column**, distinct from start/end/ldts.

**Recommended approach (validate empirically — see §7):** introduce a conventional effectivity
column the staging supplies, carrying the **same value as the start date** so end-dating closes the
old record to the business effective date of the new one (e.g. the transfer date 2026-04-01), not a
technical load timestamp.

- Add a naming constant in `src/vault_agent/rules/dv2_rules.py` next to the existing column-name
  constants (single source of truth), e.g. `EFFECTIVITY_APPLIED_COLUMN = "APPLIED_DTS"`.
- In `_render_eff_sat`, set `src_eff` to that constant (not `start_date`); leave `src_start_date`
  /`src_end_date` as the two declared date attributes and `src_ldts`/`src_source` unchanged.
- The generator now **requires** an eff_sat's staging to provide that `APPLIED_DTS` column —
  document this as a generator contract (it is also a future staging-generator responsibility).

**Fallback if empirical testing shows AutomateDV is happy with a load-timestamp effectivity:**
`src_eff = LOAD_DATETIME` is simpler (no staging column) but (a) may itself collide with
`src_ldts` (also `LOAD_DATETIME`) and (b) end-dates to the load time, not the business date. Only
use this if §7 verification proves it works and the load-time end-date is acceptable.

## 3. Fix — staging provides the effectivity column [ENFORCE]

In the demo's `models/staging/stg_account_customer.sql`, add a derived column
`APPLIED_DTS` equal to `EFFECTIVE_FROM` (same value, distinct column). With AutomateDV's stage
macro this is a `derived_columns` entry, e.g. `APPLIED_DTS: "EFFECTIVE_FROM"`. Confirm the staged
view then exposes `APPLIED_DTS` alongside `EFFECTIVE_FROM`/`EFFECTIVE_TO`/`LOAD_DATETIME`/
`RECORD_SOURCE` and the hash keys.

(Conceptually this is what a future staging generator would emit automatically for eff_sat parents.)

## 4. Regenerate the demo's raw-vault models [ENFORCE]

After the generator change, re-run the deterministic builder so the committed SQL reflects the fix:

```bash
uv run python demo/bank_postgres/build_vault_models.py
```

`models/raw_vault/sat_account_customer_eff.sql` must now show `src_eff = "APPLIED_DTS"` (distinct
from `src_start_date = "EFFECTIVE_FROM"`). Commit the regenerated file.

## 5. Demonstrate end-dating — two-phase incremental load [GUIDE]

Full-refresh inserts all relationships as open, so end-dating never triggers. Show it with two
incremental loads where the transfer arrives **after** the initial ownerships:

- Split the ownership seed: **batch 1** = initial owners (incl. account `…91873fa8…` owned by
  customer A, effective 2026-01-01); **batch 2** = the transfer (same account → customer B,
  effective 2026-04-01).
- Drive it with a load-batch column + a dbt `var` (e.g. `--vars 'load_batch: 1'` then `2`) filtered
  in staging, or two seed files loaded in sequence. Between batches run the staging + eff_sat
  models **incrementally** (no `--full-refresh`).
- Provide a small runbook target in the demo README ("Phase B2 — demonstrate end-dating"):
  `dbt seed` → run batch 1 → run batch 2 → verify.

**Expected result after batch 2:** the account's **first** ownership row has
`effective_to = 2026-04-01` (closed), the **new** row stays open (`9999-12-31`). Add this query to
`analyses/verify_vault.sql` (or the README) so the end-dating is visible.

## 6. Tests [ENFORCE]

- Update the generator unit tests in `tests/test_agents/test_code_generator.py`: assert the eff_sat
  renders `src_eff` **distinct from** `src_start_date` (e.g. `src_eff == "APPLIED_DTS"`,
  `src_start_date == "EFFECTIVE_FROM"`), in metadata and in the `{%- set src_eff … -%}` line.
- Keep the existing driving-key assertions (H-1) intact.
- These run without an API key (deterministic generator).

## 7. Acceptance criteria & verification mandate [ENFORCE]

- **Incremental green:** an incremental `dbt run` of `sat_account_customer_eff` on Postgres
  succeeds — the `column "…" specified more than once` error is gone. *Confirm by actually running
  it*, not by inspection.
- **End-dating proven:** after the two-phase load, the transferred account's first row is closed
  (`effective_to = 2026-04-01`) and the new row is open. Show it with a query.
- **Idempotency:** re-running batch 2 with unchanged data adds no rows and changes no end-dates.
- **Regression:** full-refresh still green; all other vault tables unchanged; H-1 driving-key
  behaviour intact.
- If the recommended `APPLIED_DTS` approach does not clear AutomateDV's incremental SQL, iterate
  empirically (try distinctness from `src_ldts` too; consult AutomateDV's eff_sat macro source) and
  record what AutomateDV actually requires in the demo README.

## 8. Docs to update [ENFORCE]

- `CLAUDE.md`: change the eff_sat milestone note from "incremental re-run is the documented limit"
  to "incremental eff_sat fixed (src_eff decoupled from src_start_date); end-dating demonstrated via
  two-phase load".
- `docs/architecture/poc-end-to-end-dbt-spec.md` §3 note and §9: mark the eff_sat-incremental
  limitation resolved; point to this spec.
- `demo/bank_postgres/README.md`: add the "Phase B2 — demonstrate end-dating" runbook + expected
  output.

## Rollout order

1. **Generator + constant** (§2) and its **unit tests** (§6) — `ruff`/`mypy`/`pytest` green.
2. **Staging column** (§3) + **regenerate** demo models (§4).
3. **Incremental run** on Postgres — confirm the error is gone (§7). Iterate if needed.
4. **Two-phase load** (§5) — prove end-dating; add the verification query.
5. **Docs** (§8).

## Traceability

| Item | Section | Touches |
|---|---|---|
| src_eff ≠ src_start_date | §2 | `code_generator.py`, `rules/dv2_rules.py` |
| staging effectivity column | §3 | `demo/bank_postgres/models/staging/stg_account_customer.sql` |
| demonstrate end-dating | §5 | demo seeds/README, `analyses/verify_vault.sql` |
| generator tests | §6 | `tests/test_agents/test_code_generator.py` |
