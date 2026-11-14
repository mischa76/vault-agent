---
name: project-docs
description: How to maintain this project's knowledge base — where a new fact goes, how to close a work package with a log entry, when something earns a place in CLAUDE.md, and how to run the lint pass. Use when closing a WP, recording a measurement or finding, adding an ADR or spec, updating the index, or when CLAUDE.md is growing.
---

# Maintaining the vault-agent knowledge base

The structure and its rationale: `docs/methodology/llm-wiki-mapping.md`. This file is the
procedure. It loads only when you are actually maintaining something, which is why the procedure
is not in `CLAUDE.md`.

## Where a new fact goes

Ask in this order and stop at the first yes.

1. **Would an agent silently do the wrong thing without it?** → an invariant in `CLAUDE.md`, in
   trigger/action/evidence form. See the admission rule below — this is the expensive layer.
2. **Is it true only while working on one subsystem?** → `.claude/rules/<topic>.md` with a
   `paths:` glob, so it loads only when a matching file is read.
3. **Is it a decision with alternatives and consequences?** → a new ADR in
   `docs/architecture/adrs/`, numbered, from `ADR-template.md`.
4. **Is it work to be done?** → a spec plus kick-off under `docs/architecture/backlog-2026-07/`.
5. **Otherwise** → an entry in `docs/log.md`. This is the default, and most things belong here.

## Closing a work package

1. Definition of done first: `uv run pytest`, `uv run ruff check`, bare `uv run mypy`.
2. Append one entry to `docs/log.md`: `## [YYYY-MM-DD] WPnn — one line`. Newest at the bottom.
   Write what changed, *why it was wrong before*, what is proven live versus keyless only, and
   what you deliberately did not do. Corrections to earlier entries go in this entry, never into
   the earlier one.
3. If the WP added or changed a document, add it to `docs/index.md`.
4. If it changed a count, threshold or version that a doc repeats, update that doc in the same
   commit — or better, replace the value with a pointer to the code.
5. Only then consider `CLAUDE.md` (next section). Most WPs change nothing there.

## Securing the evidence of a paid run

`eval/results/` (result JSON, step files, `review.json`, LLM transcripts, ablation comparisons)
is git-ignored and exists only on this machine, yet every measurement entry in `docs/log.md`
cites it by stamp. Since 2026-11-14 the directory is **a git repository of its own** (remote
`tank:/tank/git/vault-agent-eval-results.git`, branch `master`). After recording a run — or at
the latest in the same session — commit and push it:

```bash
git -C eval/results pull --ff-only     # a second machine (ZEUS) pushes there too
git -C eval/results add -A
git -C eval/results commit -m "<what was run, with its stamp>"
git -C eval/results push               # never --force: the remote refuses it, by the owner's setting
```

Verify with `git -C eval/results status -sb` (nothing ahead) and `git -C eval/results ls-remote
origin` naming the commit. On a checkout without the directory: `git clone
tank:/tank/git/vault-agent-eval-results.git eval/results`. Kept projects of a run
(`--keep-outputs`) go under `eval/results/kept-outputs/<case>/<stamp>/` without dbt's `target/`.
The repository is the evidence's second copy, not a dataset: nothing reads it back, and it never
goes to GitHub.

**Not `rsync`:** every key of the `git` user on `tank` is restricted to `git-shell` since
2026-11-12, so `rsync`, `scp` and a shell are refused — deliberately; do not look for a way
round it. A new repository on `tank` is the owner's to create. The repository holds every
run since 2026-07-08 (ZEUS's 858 files were merged in on 2026-11-14) and is the only copy
besides the working machines: the former `rsync` mirror on `tank` was removed by the owner on
2026-11-15, without a file-by-file comparison. The remote has `receive.denyNonFastForwards`
and `receive.denyDeletes` set — do not test that with a real force-push.

## The admission rule for CLAUDE.md

Budget: **250 lines** (200 until 2026-10-09, raised by the owner: condensing at 200 had started to cost knowledge), and it is a real limit, not an aspiration — the file is loaded in full on
every request, and the documented guidance is that longer files reduce adherence.

An entry is admitted only if **both** hold:

- there is a concrete incident where an agent did the wrong thing without it — name it; and
- it can be phrased as trigger / action / evidence. If it cannot, it is a fact, not a rule, and
  facts go in the log or the index.

At budget, an addition requires an **eviction**: say which rule leaves and why it is no longer
earning its place (usually because a gate, a type or a test now enforces it mechanically —
that is the good outcome).

Never put in `CLAUDE.md`: counts, versions, thresholds, test totals, "N tests green", file
inventories, or anything derivable from the code. `/doctor` will propose trimming exactly these.

## The lint pass

Run periodically, and after any batch of doc changes. It is a reading task, not a script.

- **Contradictions** — two documents stating incompatible things. Newer wins; record the
  correction as a new dated entry, do not edit the older. Check the maintained pages against the
  **record**, not only against each other: `CLAUDE.md`'s "Open items" is the likeliest place for
  a claim that a later log entry or findings document has already overtaken. The first lint pass
  missed exactly this by comparing maintained pages among themselves.
- **Derivable facts stored as values** — gate counts, version pins, caps, thresholds in prose.
  Replace with a pointer. This is the failure mode this project has hit most often.
- **Stale status** — a document claiming live verification whose subject has changed since.
  Downgrade the claim in a new entry; say what is now merely keyless-tested.
- **Orphans** — files in `docs/` that `docs/index.md` does not list, and index entries whose
  file no longer exists.
- **Rules without a trigger** — entries in `CLAUDE.md` that read as memories rather than rules.
  They are eviction candidates.
- **Budget** — `wc -l CLAUDE.md` against 250 (200 until 2026-10-09).

Report findings; apply only the mechanical ones (index, pointers) without asking. Anything that
changes meaning is the human's call.

## Ownership — append-only

`docs/architecture/` (ADRs, specs, kick-offs, reviews, spike memos) and `docs/log.md` are
**dated records**. Index them, link them, quote them. Never revise them, never "clean them up",
never fix a claim inside them — a new dated entry does that. Their value is precisely that they
show what was believed when, which is what makes a later correction legible.

Maintained and rewritable: `docs/index.md`, `CLAUDE.md`, `.claude/rules/`, this skill.

## Frontmatter for new documents

New documents under `docs/` carry:

```yaml
---
type: adr | spec | kickoff | review | memo | guide | log | index
status: verified-live | keyless-only | not-measured | superseded
updated: YYYY-MM-DD
supersedes: <path>#<section>   # optional
---
```

`status` is the axis this project argues about most — say which claims are live-proven and which
are only keyless-tested. Existing documents were **not** retrofitted: adding frontmatter to a
dated record would mean editing it, which the ownership rule forbids.

## The guard that protects the move

`tests/test_log_completeness.py` asserts that every paragraph of the pre-retrofit `CLAUDE.md`
still exists verbatim in `docs/log.md`. If you ever restructure the log, that test must keep
passing — the log is append-only, so it only ever gets stricter.
