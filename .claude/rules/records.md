---
paths:
  - "docs/architecture/**/*.md"
  - "docs/log.md"
---

# These files are append-only records

ADRs, WP specs, kick-offs, reviews, spike memos and `docs/log.md` are **dated records**. Their
value depends on showing what was believed when — that is what makes a later correction legible
instead of invisible.

- **Do not revise them.** Not to fix a claim, not to tidy prose, not to update a number that has
  since changed. A new finding becomes a new dated entry (`docs/log.md`) or a new document that
  says what it supersedes.
- **Adding is fine**: a dated "resolved" or "corrected" note appended to a spec's own results
  section is how WP28 and WP31 handled it — history stated, not rewritten.
- **Status headers may move** along their intended path (Proposed → Accepted → Superseded), with
  the date.
- Editing one of these is a deliberate act that needs the human's word. If you believe a record
  is wrong, say so and propose the entry that corrects it.

Maintained and freely rewritable instead: `docs/index.md`, `CLAUDE.md`, `.claude/rules/`,
`.claude/skills/`. Procedure: `.claude/skills/project-docs/SKILL.md`.
