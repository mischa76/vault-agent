<!--
Conventions: CONTRIBUTING.md. Delete any section that genuinely does not apply — but prefer
answering "no" over deleting; an honest "no" is useful information for the reviewer.
-->

## What and why

<!-- What changed, and what was wrong before. The reasoning matters more than the diff. -->

## What I verified, and how

- [ ] `uv run pytest` — green, with **no** API key set
- [ ] `uv run ruff check .` — green
- [ ] `uv run mypy` — green (**bare**, no path argument; a path silently skips `eval/`)

Verification level of the behaviour this PR claims:

- [ ] **verified-live** — ran end to end against the real thing. Evidence:
      <!-- dbt PASS counts, trace file, eval scores, run cost -->
- [ ] **keyless-only** — covered by the offline suite; never run against the real API
- [ ] **not-measured** — believed to work, not checked

<!-- If a rendered dbt template changed, a real PostgreSQL build is the honest evidence.
     demo/bank_postgres/ and demo/mapping_postgres/ exist for this. -->

## Written down

- [ ] Entry appended to `docs/log.md` (`## [YYYY-MM-DD] …`) — what changed, why it was wrong
      before, what is verified vs. keyless-only, and what I deliberately did not do
- [ ] `docs/index.md` updated if a document was added or renamed
- [ ] No dated record was edited — corrections are new entries, never rewrites
- [ ] `CLAUDE.md` untouched, **or**: an invariant was added with the incident that justifies it
      (and, at the 200-line budget, the rule it evicts)

## Guards and decisions

- [ ] A change that must leave existing output untouched has its byte-identity guard, and the
      guard was committed **before** the change
- [ ] A deliberately updated fixture is updated in this commit, with the reason in the message
- [ ] Any library macro/signature/flag used here was checked against the **installed** package,
      not from memory — what I read:
- [ ] No new framework, and AutomateDV is not bypassed — or there is an ADR in this PR
- [ ] New prompt steering is registered and recorded in `docs/architecture/steering-ledger.md`

## Anything a reviewer should push back on

<!-- Known weak spots, things you were unsure about, scope you cut. Naming them here is
     cheaper for everyone than having them found. -->
