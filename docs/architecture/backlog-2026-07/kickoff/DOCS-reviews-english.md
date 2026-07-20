# Kick-off DOCS — Translate the two German review documents, move under docs/

You are a senior technical writer/engineer working on **vault-agent** (this repository —
a PUBLIC portfolio repo). Task: the two German-language internal reviews at the repo
root become English documents under `docs/architecture/reviews/`. Docs-only, one
conventional commit. The reviews stay public deliberately: the finding → remediation →
verified-milestone chain is portfolio evidence — nothing is softened or dropped.

## Files
- `ARCHITECTURE_REVIEW_2026-06-13.md` → `docs/architecture/reviews/architecture-review-2026-06-13.md`
- `PROJECT_REVIEW_2026-07-06.md` → `docs/architecture/reviews/project-review-2026-07-06.md`

## Rules
1. **Faithful 1:1 translation** into the repo's English register (match the tone of the
   specs/CLAUDE.md): no content changes, no re-assessment, no softening of verdicts.
   Keep finding IDs (H-1, P1–P10 …), dates, update-notes, and document structure exactly.
   Add one italic line under each title: *Translated from the German original
   (2026-07-20); content unchanged.*
2. **Public-readiness pass while translating** (report, do not silently fix): flag any
   real customer/employer name or non-demo-safe detail you encounter to the maintainer
   in your handover (repo convention: such names are anonymized, e.g. ATLAS-style
   placeholders). Expected: none — these are self-reviews of this codebase.
3. **Update every reference** to the old filenames — find them with
   `git grep -l "ARCHITECTURE_REVIEW_2026-06-13\|PROJECT_REVIEW_2026-07-06"`
   (at minimum: CLAUDE.md, `docs/architecture/backlog-2026-07/00-overview.md`,
   `docs/architecture/review-2026-06-remediation-spec.md`; there may be more). Old files
   are deleted in the same commit (`git mv` semantics — history stays connected).
4. No other content edits; do not touch code or tests.

## Definition of Done
`git grep` finds zero references to the old root filenames · both new files render
cleanly · handover lists any flagged names (or states none) · one conventional commit
(`docs(reviews): translate German reviews to English, move under docs/architecture`).
