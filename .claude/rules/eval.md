---
paths:
  - "eval/**/*.py"
  - "eval/**/*.yml"
---

# Eval conventions

The eval harness is the quality gate everything else leans on. Its own defects have cost more
than most product bugs here, and they repeat in one shape:

- **Score structure, not free-form LLM names.** A model that is right must not score wrong
  because it named a construct differently. Match through `normalize_identifier`, and for links
  through the grain (the multiset of participating hubs) — the name only breaks a tie. This class
  of defect has now appeared three times (WP9.2, WP14, the link-name fix); hubs and satellites
  are *still* name-keyed, which is safe only for the hand-written cases.
- **A gate must never pass on absence of evidence.** A scorer with nothing to check returns 1.0
  with `VACUOUS_PREFIX` in its details — and a gated scorer that was vacuous in every repeat, or
  produced no score at all, fails the run (`unsatisfiable_gates`). The loader rejects a case that
  gates a scorer its golden cannot feed.
- **Persist as you go.** A repeat is written the moment it is scored, and a chain step the moment
  it completes. An exhausted credit balance mid-batch must never discard paid-for work.
- **Do not weaken a gate because a run came out badly.** Record the finding, split the causes,
  and change the instrument only with its own reasoning written down first.
- **Write the prediction before the run.** Pre-register what you expect and what would falsify
  it; a number produced after the fact explains anything.
- **Keyless by default.** `eval/` is type-checked in CI by the bare `uv run mypy` — never pass a
  path to mypy, it overrides the configured file list.
