# WP2 — ADR author remediation

Status: Proposed · Size: S · Depends on: — 

## 1. Problems (project review 2026-07-06, findings 5 + 6)

All in `src/vault_agent/agents/adr_author.py`:

1. **Stale, false caveat.** `_render` appends: "construct(s) use specialised Data Vault
   types that need dedicated AutomateDV macros not yet generated" for every non-standard
   link/sat. False since nh_link/ma_sat/eff_sat templates landed (2026-06) — every
   generated ADR for such a model now misinforms its human reviewer.
2. **Repo-layout coupling.** `_DEFAULT_ADR_DIR = Path(__file__).resolve().parents[3]/docs/
   architecture/adrs` breaks when the package is installed as a wheel (points into
   site-packages' grandparent → silently yields ADR-0001).
3. **Non-idempotent numbering.** The number is derived from the *repo's* ADR directory but
   written to the *output* directory: two runs to different out dirs collide on the same
   number; adding a repo ADR later silently shifts subsequent run numbers.

## 2. Target design [ENFORCE]

### 2.1 Numbering: the generated ADR is a per-run output artifact

Drop the repo-continuation idea entirely. The generated ADR documents *one* pipeline run
inside *one* output project — number it **ADR-0001 within the output**, deterministically:

- Remove `_DEFAULT_ADR_DIR`, `_next_adr_number`, and the `adr_dir` constructor parameter.
- Keep `start_number: int | None = None` for tests/overrides; default resolves to `1`.
- Re-running the pipeline into the same out dir overwrites the previous run's ADR
  (`cli.write_outputs` already writes by heading-derived filename) — same model in,
  byte-identical ADR out, consistent with the generator's idempotency guarantee.
- Docstring: state explicitly that repo-level ADR numbering happens when a human *accepts*
  the proposal and moves it into `docs/architecture/adrs/` — the pipeline never numbers
  into the repo sequence.

### 2.2 Caveat: derive from flags, never restate capability

Replace the `specials`-based caveat with one derived from reality:

- Constructs the generator actually skipped are flagged
  (`FlagKind.GENERATION_GAP`, `asset` = construct name). In `run`, collect
  `[f.asset for f in state.flags if f.kind == FlagKind.GENERATION_GAP and f.asset]`
  (deduplicated, sorted) and pass to `_render`.
- If non-empty → caveat: "N construct(s) could not be generated and are flagged for human
  review: …" (list). If empty → no caveat line at all.
- Non-standard types that *were* generated get no caveat — they work.

Note the ordering constraint: `adr_author` runs after `code_generator` on the validated
path (graph: `code_generator → validator → human_checkpoint → adr_author`), so the flags
are present. Add a comment stating this dependency.

### 2.3 Reference section correctness

`## References` claims `Generated dbt models: N (see state.artifacts)` — extend to
`N raw-vault model(s) + M staging model(s)` now that staging exists.

## 3. Tests (`tests/test_agents/test_adr_author.py`)

- Number defaults to 1; `start_number` override still wins; two runs → identical ADR.
- Model with a generated eff_sat (no GENERATION_GAP flags) → **no** caveat text.
- State carrying a GENERATION_GAP flag (e.g. ma_sat without cdk) → caveat naming exactly
  that construct.
- Reference line counts raw-vault + staging models.
- Remove/replace tests asserting the old repo-dir scanning behaviour.

## 4. Acceptance criteria

1. `rg "parents\[3\]|_next_adr_number|_DEFAULT_ADR_DIR" src` finds nothing.
2. Generated ADRs contain no false capability claims; caveats appear iff GENERATION_GAP
   flags exist and name their assets.
3. Same state in → byte-identical ADR out (idempotency test).
4. Standard DoD.
