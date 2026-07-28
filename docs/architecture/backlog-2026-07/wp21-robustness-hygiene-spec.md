# WP21 — Document-read robustness + hygiene batch

Status: Proposed · Size: S/M · Depends on: WP17 (touches the resume flow, §2.7) ·
Source: project review 2026-07-28, findings 6 + 7a–f

## 1. Problems

**(6)** One unreadable document kills a run instead of being flagged:
`_read_document` flags-and-skips unknown extensions, but `read_text(encoding="utf-8")`
(UnicodeDecodeError on a Latin-1 file), a corrupt PDF (pypdf raises), or a broken .docx
propagate uncaught (`requirements_parser.py:271-277`) — against the module's own
flag-and-skip contract, and (pre-WP17) unrecoverably.

**(7a)** `ForcedToolCaller._record_usage`'s docstring promises a recorder error "never
disturbs the call path", but unlike `emit_trace` there is no try/except
(`llm.py:334-348`) — a raising usage recorder kills the call after a successful, billed
response.

**(7b)** `aggregate_review_flags` hardcodes `source="data_contract"` on every collapsed
line (`orchestrator.py:197`) — wrong attribution for the source-binding
(code_generator) and mapping (source_mapper) groups.

**(7c)** The validator docstring says "30 as of WP8"; the module has 32 codes (WP10 added
`E_HUB_DUP_FEED` and `W_HUBSOURCE_BK_NOT_IN_SOURCE`).

**(7d)** The WP10 multi-source satellite path skips `_collision_warnings`
(`code_generator.py:452-477` `continue`s before `_render_satellite`, where the check
lives).

**(7e)** `dv2_modeler._validate_items` drops invalid records with no `asset` attribution
— the one DROPPED_RECORD flag a reviewer cannot trace to a construct.

**(7f)** `run --no-write` on a paused run still writes `pending.json` and prints resume
instructions whose resume WILL write to disk — undecided semantics across the pause.

## 2. Target design [ENFORCE]

### 2.1 (6) Flag-and-skip for unreadable documents

Wrap the three extraction branches in `_read_document`: catch `OSError`,
`UnicodeDecodeError`, and the library-specific extraction errors (catch `Exception` from
the pypdf/python-docx calls — their exception surfaces are not a stable API; a comment
says why the broad catch is right here). On failure: `state.flag(...)` with
`severity="error"`, `kind=FlagKind.MISSING_INPUT` (reuse — consumers do not distinguish
missing from unreadable; the message does), `asset=doc_path`, message naming the exception
— then return `None` (skip). A multi-document run continues past one bad file; a
single-document run then produces zero requirements and fails attributably downstream
(the existing MISSING_INPUT flow).

### 2.2 (7a) Guard the usage recorder

Mirror `emit_trace`: wrap the `recorder(...)` call in try/except, log a warning with
`exc_info`, never propagate. The docstring finally tells the truth.

### 2.3 (7b) Honest source attribution on collapsed lines

Derive the collapsed `ReviewItem.source` from its members: one distinct source → that
source; several → `"multiple agents"`. Never a hardcoded agent name.

### 2.4 (7c) Validator docstring

Drop the literal count ("30 as of WP8") — the docstring already declares the code the
source of truth; keep only the instruction to count the `E_`/`W_` codes. While there:
check CLAUDE.md's older count mentions still carry their "may grow — count the codes"
hedge (they do; no rewrite, just verify).

### 2.5 (7d) Collision warnings on the multi-source path

In the multi-source satellite branch, emit
`_collision_warnings(sat.attributes + sat.child_dependent_key, sat.name)` once (not per
source) before the per-source render loop — parity with `_render_satellite`.

### 2.6 (7e) Asset attribution for dropped records

`_validate_items`: when the raw record carries a usable `name` (string, non-empty), pass
it as the flag's `asset`. Message unchanged otherwise.

### 2.7 (7f) `--no-write` semantics across the pause

Decision: `--no-write` governs **artifacts only**; run state (checkpoints, pending,
traces) is not an artifact and is always written — otherwise a paused `--no-write` run
would be unresumable. Make the behaviour symmetric and documented:

- `resume` gains `--write/--no-write` (default `--write`), same meaning.
- `run --no-write` on a pause: keep writing `pending.json`, skip the interactive
  checkpoint (already the case — it requires `write`), and extend the printed resume
  instructions with a note that resuming will write artifacts unless `--no-write` is
  passed again.
- Help text for both flags states the artifacts-only scope.

## 3. Tests

1. (6) Latin-1 `.md`, corrupt `.pdf`, corrupt `.docx`: each → error flag naming the file,
   run continues; second good document still parsed.
2. (7a) A raising usage recorder: call path completes, payload returned, warning logged
   (extend the `tests/test_llm.py` raising-recorder pattern the trace seam already has).
3. (7b) Collapsed groups from two agents → `"multiple agents"`; single-agent group → that
   agent. Renderer parity (md + CLI + report all read the same item).
4. (7d) Multi-source hub satellite with colliding labels → exactly one COLUMN_COLLISION
   flag.
5. (7e) Invalid record with a `name` → flag carries it as `asset`.
6. (7f) `resume --no-write` finalises without writing artifacts but prunes/clears state;
   `run --no-write` pause prints the extended note. Non-TTY byte-identity guard for the
   default path stays green.

## 4. Acceptance criteria

1. No input document can crash the pipeline; every skip is an attributable flag.
2. The observational seams (usage + trace) are provably non-fatal — both raising-recorder
   tests green.
3. Review-queue renderings never misattribute a collapsed line.
4. Standard DoD; report fixture (`tests/fixtures/report/report_fixture.html`) only
   changes if a rendered source attribution appears in it — if so, regenerate
   deliberately and say so in the commit.

## 5. Out of scope

New FlagKind values, changing what `--no-write` means for run state (decided above), and
any behaviour change to the happy paths beyond §2.3's rendered source text.
