# LLM Wiki mapping — Karpathy's knowledge-base pattern vs. vault-agent's docs

Source: Andrej Karpathy, *LLM Wiki — A pattern for building personal knowledge bases using
LLMs* (idea file, read 2026-07-30). House style follows `dsaf-mapping.md` /
`ireb-mapping.md` / `loops-mapping.md`: adopted / partially adopted / deviated, each with the
concrete counterpart and rationale.

**Status, stated first because it differs from the other three mappings: this one is
prospective.** DSAF, IREB and LOOPS were mapped *post hoc* against an implementation that
already existed. This document maps a pattern onto a problem that is **not yet solved** —
nothing below is implemented as of 2026-07-31. It is the decision basis for a `CLAUDE.md`
retrofit, and it is written before the retrofit so that the retrofit can be judged against it
rather than described by it.

## The problem being held against the pattern

Measured 2026-07-31:

| | |
|---|---|
| `CLAUDE.md` | 1,838 lines / 155,077 chars — lines 1–65 are stable context, 66–1835 are ~47 chronological WP paragraphs |
| `docs/` | 129 files / 820,975 chars (`architecture/` 102 files, `operations/` 14, `methodology/` 6) |
| of which dated records | 13 ADRs, 38 WP specs, 33 kick-offs, 4 reviews, 2 spike memos |
| cross-linking | 2 files contain any wikilink; there is no global index |

The structural cause is that every WP **appends a paragraph** instead of updating a state.
Any one-off cleanup therefore regrows at the same rate.

**The restatement that makes the pattern applicable:** the cost is not size, it is that
`CLAUDE.md` is the only layer paid *in full on every single request*. Claude Code loads
`CLAUDE.md` at launch and re-injects it after `/compact` (verified 2026-07-31 against
`code.claude.com/docs/en/memory`). Everything else in `docs/` is paid only when read. So the
question is not "what can be deleted" but **"which load class does each piece of knowledge
belong in"** — which is exactly the question Karpathy's three-layer split answers, arrived at
from a different direction (he is avoiding re-derivation at query time; we are avoiding a
fixed per-request toll).

## Layer-by-layer

### Layer 1 — Raw sources, immutable — **deviated**

The article's sources are articles and papers: the LLM reads them and never modifies them, and
they cannot go out of date relative to the wiki. **Here the source of truth is the code, and it
changes daily.** A wiki page can therefore go *silently* stale in a way an article wiki cannot.

The project has already been burned by exactly this and has the countermeasure written down in
prose: "count the codes in `validator.py`, don't trust prose"; WP21 §2.4 removed a gate count
from a docstring because "the literal had been wrong twice"; at the time of WP20 the docstring
said 30 and the operations catalogue said 32 while the true count was 33.

Rule for the wiki, therefore: **no derivable facts.** A number the code owns gets a pointer,
never a value. Independently corroborated by the tooling — Claude Code's `/doctor` trim check
"cuts content Claude can derive from the codebase … and keeps pitfalls, rationale, and
conventions that differ from tool defaults" (verified 2026-07-31), which is the same rule
stated as a product feature.

### Layer 2 — The wiki, LLM-owned — **partially adopted, split by ownership**

The article is unambiguous: *"You never (or rarely) write the wiki yourself — the LLM writes
and maintains all of it."* That is right for derived pages and **wrong for a large part of this
corpus**. ADRs, WP specs, kick-offs, reviews and spike memos are **dated records whose value
depends on not being rewritten**. The project already has the instinct — WP28 resolved a WP24
decision and recorded it as "resolved, history not rewritten"; WP31 corrected how WP30's
findings should be read by *adding* a dated paragraph, not by editing the old one.

So the layer splits into two, and the split is the main deviation from the article:

- **Append-only, human-ratified:** `docs/architecture/adrs/`, `backlog-*/`, `reviews/`, spike
  memos. The LLM may index, link and summarise them; it must never revise them. New insight
  produces a new document or a log entry.
- **LLM-maintained, derived:** the index, per-subsystem overview pages, the log. These are
  regenerable; if one is wrong, it is rewritten, not corrected in place.

This distinction is the reason the `type:` frontmatter field below is more than cosmetics: it
makes the ownership boundary machine-readable instead of a convention someone has to remember.

### Layer 3 — The schema — **adopted, and this is the diagnosis**

The article: the schema tells the LLM *how the wiki is structured and what workflows to follow*
— it is configuration, not content. **`CLAUDE.md` today does both jobs at once, and that is why
it reached 155k: a schema does not grow, a content store does.**

Adopted with one extension the article does not have, because Claude Code offers more than one
load class. All verified 2026-07-31 against `code.claude.com/docs/en/{memory,skills}`:

| Mechanism | When it is paid | What belongs there |
|---|---|---|
| root `CLAUDE.md` | in full, every session (target: **under 200 lines**, official guidance) | invariants — *without this sentence an agent silently does the wrong thing* — plus the index pointer |
| `.claude/rules/*.md` with `paths:` globs | only when a matching file is read | subsystem conventions (`src/vault_agent/agents/**`, `eval/**`, `docs/architecture/adrs/**`) |
| subdirectory `CLAUDE.md` | on demand, when a file in that directory is read | same purpose; weaker than `rules/` because it is not glob-scoped |
| skills (`.claude/skills/*/SKILL.md`) | description always in the listing (≤1,536 chars/entry), **body only when invoked** | procedures: how to ingest a WP, how to lint, how to run the eval harness |
| `docs/` | only when grepped or linked | the record |
| auto memory (`~/.claude/projects/<p>/memory/`) | `MEMORY.md` index every session (first 200 lines / 25 KB), topic files on demand | machine-local session-carryover; **not** a substitute for the repo record |

Three consequences worth stating because they contradict plausible assumptions:

1. **`@path` imports do not help.** "Imported files still load and enter the context window at
   launch." Splitting `CLAUDE.md` into imports is organisation, not savings.
2. **Even the schema need not be always-loaded.** "How do I maintain this wiki" is only needed
   *while maintaining it* — so the schema belongs in a skill, and `CLAUDE.md` keeps one line
   pointing at it. This corrects the version of this plan discussed on 2026-07-30, which put
   the schema itself into `CLAUDE.md`.
3. **`.claude/rules/` with `paths:` is the better fit than nested `CLAUDE.md`** for subsystem
   knowledge: same laziness, but declared centrally and glob-scoped rather than depending on
   directory layout.

## Operation-by-operation

### Ingest — **adopted, re-targeted**

There is no stream of external articles here. The equivalent of "a new source arrived" is **a
closed WP, a live measurement, or a review finding** — and the operation already happens: every
WP ends by writing a paragraph. It is merely routed to the wrong file. Re-targeted, one ingest
produces: a `log.md` entry, an index update, an update to any derived overview page, and — only
if the eviction test below passes — a promotion into the invariants.

### Query — **partially adopted**

"Good answers can be filed back into the wiki" has strong precedent here: `spike-mapping-
results.md`, `spike-entity-resolution-results.md` and `scale-test-findings.md` are exactly
that, and the 2026-07-28 method note ("audit the traces before paying for another run") is a
filed answer that later saved money. The gap is the smaller explorations, which today land in
`CLAUDE.md` prose or nowhere.

### Lint — **adopted as a named operation; it currently happens by accident**

The self-corrections inside `CLAUDE.md` ("this paragraph originally overclaimed", "a correction
to WP30's findings", the gate count that was wrong twice) **are lint findings** — each one was
stumbled over by someone reading, at whatever cost that reading happened to have. As a named
operation with a checklist it becomes repeatable. The checklist differs from the article's:

- the article's items: contradictions, stale claims, orphan pages, missing pages, missing
  cross-references, data gaps;
- **added for this project:** derivable facts stored as values (deviation A), `status:` claims
  that no longer match reality (a `verified-live` page whose verification predates the code it
  describes), invariant budget overflow, and rules with no trigger — an entry in the invariant
  layer that cannot be phrased as Trigger/Action/Evidence is a memory, not a rule.

### `index.md` — **adopted, and load-bearing**

For the article this is a convenience that avoids RAG infrastructure. Here it is the mechanism
that solves the actual problem: a small always-loaded catalogue plus drill-down on demand. The
article's scale claim ("works surprisingly well at ~100 sources, hundreds of pages") sits right
at our 129 files.

### `log.md` — **adopted**

Chronological, append-only, one grep-able prefix per entry. **This is the destination of the
`CLAUDE.md` chronicle**, moved 1:1 rather than summarised — the retrospective corrections and
measurement findings in those 47 paragraphs are the most valuable content in the file and the
part no spec document carries.

### Optional CLI tooling (qmd, hybrid search) — **not adopted**

129 files; `rg` is sufficient. The article says so itself: "at small scale the index file is
enough". Revisit only if the corpus grows by an order of magnitude.

### Obsidian, Web Clipper, Marp, Dataview — **partially adopted**

Keep the substrate portable — markdown, `[[wikilinks]]`, YAML frontmatter, git — so that
Obsidian, `rg` and the agent all operate on the same files. Obsidian is then a *viewer*
(graph view for orphan detection is genuinely useful) and must never become load-bearing: no
plugin dependency, no Obsidian-only syntax. For the in-repo docs the review interface is the
PR, not the vault. Dataview is a consequence of adopting frontmatter, not a reason to.

### "Why this works" — **adopted, with one caution the article does not raise**

Near-zero maintenance cost is also near-zero cost to produce *plausible wrong text*. The
counterweight is that every page here is checkable against code and tests — hence the
no-derivable-facts rule, and hence `status:`.

## The frontmatter, and why only three fields

From the ecosystem survey (below), the portable part is frontmatter. Proposed field set —
deliberately not the OKF one, whose `content_hash` / `author` / `updated_by` re-implement git:

```yaml
type: adr | spec | kickoff | review | memo | guide | log | index
status: verified-live | keyless-only | not-measured | superseded
updated: 2026-07-31
supersedes: wp24-multi-source-composition-spec.md#5   # optional
```

`type:` makes the ownership boundary lintable. `status:` captures the axis this project already
tracks in prose at dozens of places — "what IS live-proven at 100 tables … what is
keyless-tested ONLY (it has never run against the real API)" — as a field instead of a
paragraph. `supersedes:` addresses the most expensive maintenance case: today a superseded
claim is only findable by reading the whole chronicle.

## What generalises beyond this repo: three scopes, and promotion between them

The article is about *one personal* knowledge base. The generalisation for "how CLAUDE.mds are
maintained across projects" is that the same three-layer split exists at more than one scope —
Claude Code exposes managed-policy, user (`~/.claude/`) and project scope — and that **knowledge
should be sorted by which scope it is true in**:

- **Project scope** (in-repo, versioned with the code, reviewable in a PR): the DV2.0 rules,
  the graph order, the gate codes, this corpus.
- **User scope** (`~/.claude/CLAUDE.md`, `~/.claude/rules/`, `~/.claude/skills/`): craft
  knowledge that every project inherits.

Apply that test to the current file and the result is not "shorten" but "**promote**":
"verify against the installed library, not from memory" (the `t_link` lesson, retold in WP8,
WP10, WP17 and WP22), "write the byte-identity guard before the change", "audit the existing
traces before paying for another live run", "branch on typed fields, never on message text".
None of those are vault-agent knowledge. They sit in a project file only because there was no
layer above it. Promotion in the other direction — project → user — is warranted once a lesson
recurs in a second project.

The corresponding rule format is **Trigger / Action / Evidence**, taken from mARC (below). It
is what turns a six-line war story into three lines, and its absence is why these lessons
currently cost so much space: they are stored as *how we found out*, not as *what to do*.

## What stops the regrowth

Three mechanisms, all cheap; without them the file regrows at its previous rate.

1. **A budget with a number.** Root `CLAUDE.md` ≤ 200 lines — not invented here, it is the
   documented guidance ("target under 200 lines per CLAUDE.md file. Longer files consume more
   context and reduce adherence").
2. **An admission rule, not judgement.** New knowledge defaults to the record. Promotion into
   the invariant layer requires (a) a concrete incident where an agent did the wrong thing
   without it, and (b) at budget, an **eviction** — which rule leaves. This is Karpathy's lint
   moved to the entrance.
3. **Lint as a scheduled operation**, with the checklist above.

Optionally enforceable rather than remembered: hooks run regardless of what the model decides,
and the `InstructionsLoaded` hook logs exactly which instruction files loaded — which is also
the honest way to *verify* a retrofit instead of asserting it.

## Adjacent implementations evaluated (2026-07-30), and why they are not adopted

- **mARC** (Markdown Agent Relay Chat) — solves *coordination between several agents* in one
  repo via a local daemon, MCP server, Node/pnpm and LanceDB. Wrong target problem, and
  disproportionate for "my markdown file is too long"; also "no new framework without an ADR".
  **Taken:** the bootstrap/rules split, and the **Trigger / Action / Evidence** rule format.
- **LLMWikiNG** — Karpathy's pattern maximally implemented: FastAPI backend, web editor,
  knowledge graph, 38 MCP tools, auth, SQLite audit log, weekly briefings. That is a product;
  what is needed here is a convention — and 38 MCP tools for writing markdown have negative
  value when Read/Write/Edit/Grep already exist. **Taken:** the frontmatter idea, reduced to
  the three fields above.

Both verdicts follow the article's own instruction: *"Everything mentioned above is optional
and modular — pick what's useful, ignore what isn't."*

## The one risk, named before the retrofit

**What leaves `CLAUDE.md` is no longer loaded automatically, and an agent only fetches what it
knows it needs.** Trading a bloated file for silent regressions would be a bad trade. Three
mitigations, all of which must hold: session-critical invariants stay in the always-loaded
layer (graph order `data_contract` before `code_generator`; branch on `kind`/`asset`, never on
message text; verify against the installed library; byte-identity guards before a change); the
index stays in the always-loaded layer, because a pointer is worth little if it is itself a
drill-down; and every skill description and rule `paths:` glob is written as a **trigger**
("when you touch X"), not as a title.

## Non-adopted context

The article targets a personal knowledge base accumulated from immutable curated sources, with
a human curator and an LLM doing the bookkeeping. This corpus is a working repository whose
truth is executable, whose records are dated and human-ratified, and whose consumer is an agent
under a per-request context budget rather than a reader browsing a graph. Those three
differences produce deviations A (no immutable source → no derivable facts), B (append-only
records → split ownership) and C (not green-field → this is a retrofit of index, linking and
lint onto 129 existing files, not the construction of a wiki). Cited alongside the DV2.0 /
DSAF / IREB / LOOPS foundations; ideas subject to revision as the harness changes — the load
classes above are Claude Code specifics verified on 2026-07-31 and are the part of this
document most likely to age.
