# ADR-0019: Requirements drafted from the source catalogue — a command that writes a document a human corrects, not a source-driven mode

**Status:** Proposed (2026-10-31 — draft by Claude on the owner's word, after the C1 experiment of 2026-10-30;
the recommendation is Option 3 as refined below)
**Date:** 2026-10-31
**Decision makers:** Mischa Eismann

## Context

Backlog C1 (the owner's question of 2026-10-21) asks what the product does when only a source model is attached.
Today: nothing starts. `vault-agent run` requires the requirements document, the workbench's `StartRun.requirements`
is required, and an empty document yields no hubs, because the modeler's rule is *model only what the requirements
support*. C1 names the candidate — a *source-driven* mode, a raw vault taking the source's shape — and says why it
is an ADR and not a flag: it inverts the product's premise. An associative table would become a hub, a surrogate
key a business key, and the gates that make the requirements-driven mode safe (`E_HUB_PAYLOAD_UNREAD`, the key
licences, entity resolution) assume a modeler that chose its constructs from the business's words. C27 stage 4
names the same thing from the other side: *requirements from the catalogue — a drafted requirements skeleton, LLM
text marked as such*. Stages 1–3 are built (WP96, WP98, WP99; ADR-0017, ADR-0018), so a customer's catalogue now
arrives in the house format by one command, with types, nullability, comments, keys and foreign keys.

C1 asked for evidence before deciding, and the owner commissioned it on 2026-10-30: the C1 experiment
(`backlog-2026-07/c1-experiment-drafted-requirements.md`, pre-registered, two chains on one commit, `docs/log.md`
2026-10-30). Its instrument is option 3's machine half: `eval.adventureworks.draft_requirements` drafts one
document per subject area from the extract, deterministically — a table is a *relationship* when two or more
foreign keys cover its primary key, a *subtype* when exactly one does, else an *entity* identified by the declared
natural key where one exists, else by the primary key; columns in words, never by physical name; one requirement
per described column, one per foreign key; no analyst's sentence anywhere. What the experiment found:

- **The feared inversion did not happen.** Subtypes stayed subtypes (no own hub for `Employee`, `Vendor`, `Store`,
  `SalesPerson`, `Person`), all twelve relationship tables stayed links, in the drafted arm as in the authored one.
- **The keys got better, not worse.** C1 warned the draft would make surrogates business keys. The opposite: the
  draft names Microsoft's declared natural keys (`ProductNumber`, `CardNumber`, the `Name` of every reference
  table) and the modeler keyed 14 of 39 hubs on an `…ID` column against 29 of 40 from the analyst's prose. The
  catalogue carried the natural keys; the analyst's documents had lost them. Seven translated proposals followed —
  the translation path's first live cases.
- **The draft builds fewer constructs and costs more review.** One hub, four links and three satellites fewer; 146
  review decisions against 91 (+60 %), on every step — the per-column requirements become mapping and contract
  questions. The authored arm built the one construct a human declines (`hub_national_id`, zero satellites).
- **Both arms green on every gate**, `mapping_coverage` 1.0 on every step in the drafted arm. Neither fifth project
  built as written — three generator classes found the same day and closed since (C33–C35, WP100–WP102); the
  drafted arm's 51 translations found two of them.
- **Not measured:** a human-corrected draft (nobody corrected anything), and any second landscape. One chain per
  arm is a shape, not a distribution.

Two standing positions bound the decision. IREB names three requirement sources — stakeholders, documents, and
*systems in operation* (`docs/methodology/ireb-mapping.md` §5) — and the product maps the catalogue onto the third
as *grounding*, never as the document; the parser does not elicit (§4.2). ADR-0007 puts *source identification*
under **Assist + HITL**: the agent proposes, the human confirms. A draft nobody reads would be elicitation by
machine; a draft a human corrects is a proposal under ADR-0007. WP34 §3.8 makes any change to the modeler's input
a measured change.

## Decision (proposed)

**Option 3, refined — `vault-agent draft-requirements`: a deterministic command writes a requirements document
from the declared source schema, marked as a draft nobody has reviewed; a human corrects it; the normal run takes
it as any document. No source-driven mode, no new run mode, no change to the pipeline.**

1. **A command, not a mode.** `vault-agent draft-requirements --source-schema FILE --out FILE` reads the house
   format (`source_schema.yml` — written by hand, by `source-schema` from a catalogue, or by the eval's
   derivation) and writes one Markdown document. `run`, the workbench and the eval are unchanged: the document
   enters where every document enters. There is no run without a document, and the modeler's rule stands.
2. **Deterministic and keyless; the experiment's rules, promoted.** The rules are the instrument's, moved into
   `src/vault_agent/` and read by the eval's `draft_requirements` so that the six `adventureworks_drafted_*`
   documents regenerate byte-identically (the guard): relationship / subtype / entity by how the foreign keys
   cover the primary key; the identifier is the single-column declared unique key where one exists, else the
   primary key; columns in words, never by physical name; one requirement per described column, the undescribed
   columns of a table in one requirement, one requirement per foreign key; the table's own comment and the column
   comments verbatim; no sentence the catalogue did not say. One rule the house format needs that the extract did
   not: a unique key on a column of a GUID type (`uniqueidentifier`, `uuid` — the type, never the name) is not an
   identifier, since a catalogue read by `source-schema` carries `rowguid`'s unique index where the derivation
   dropped it (`technical_guid`). The draft is deterministic text, **not** LLM text: C27 stage 4 wrote *LLM text
   marked as such*, and the experiment shows the modeler reads the deterministic draft well (coverage 1.0, every
   gate green); an LLM paraphrase would add sentences nobody said and could not be marked apart.
3. **Marked as a draft, and the mark is typed.** The document opens with a machine-readable header
   (`vault-agent: drafted-from-catalogue`, the source file, the date, `status: unreviewed`) and a human-readable
   one (*nobody has read this; every statement is the catalogue's*). The human edits the document — cuts what is
   not in scope, renames what the business calls otherwise, adds the business's words — and sets the status.
   `run` reads the header: a document still `unreviewed` yields a flag (`requirements_unreviewed`, a typed
   `FlagKind`, in the review queue and the report), never a refusal — the run is the human's to start, and the
   flag makes a skipped correction visible instead of silent. The proposed ADR the run writes names the document's
   provenance when the header says drafted.
4. **What the draft does not read.** Inferred keys (ADR-0018): an inference stated as an identifier in a document
   would turn into a human-looking claim; the proposer offers them with provenance, as decided. Profiling.
   Nullability — the house format carries it since WP94/WP103, and *may be absent* in the draft would be a change
   to the modeler's input, a later, measured increment under WP34 §3.8, not part of the first build.
5. **What is measured, and by whom.** The build is keyless: byte-identity with the experiment's six documents, the
   GUID rule, the header, the flag. A corrected draft's effect on the model and the review load is the measurement
   C1 still lacks; it needs a human who corrects — the owner, on one subject area, one chain against the drafted
   arm of 2026-10-30, pre-registered as the experiment was. The ADR does not wait for it: the uncorrected draft is
   already measured and already green, and the corrected one can only cut what the uncorrected lists.

## Alternatives considered

- **Option 1 — do not build it; the product stays requirements-driven, the schema grounds.** Pros: the premise
  untouched, nothing new to maintain. Cons: a customer with a catalogue and no documents cannot start — the
  situation C27 was built for ends at the door; the experiment's one unambiguous gain, the catalogue's natural
  keys reaching the modeler where the prose lost them, stays an eval finding; the instrument exists and would
  live in `eval/` only. Rejected: the evidence C1 asked for says the draft helps the keys and harms nothing a
  gate watches.
- **Option 2 — a deterministic source-driven generator as a separate entry point, its output marked source-shaped.**
  Hubs from primary keys, links from foreign keys, satellites from the rest, no model call. Pros: no LLM cost,
  reproducible, the common first raw layer in practice. Cons: it is exactly the inversion C1 named — every
  reference table a hub keyed on its surrogate, no entity resolution, no payload gate, no licence; a second output
  class that can never meet a requirements-driven vault in one project; and the experiment removes its main
  argument, since the drafted arm got subtypes, relationships and keys right *through* the modeler and the gates.
  Rejected now; it stays a possible later ADR for a customer who wants a raw layer with no human at all, which
  is not this product's premise (ADR-0007, ADR-0015).
- **Option 3 as C1 wrote it, with LLM text.** A model paraphrases the catalogue into prose, *marked as such*. Cons:
  the marking cannot survive editing sentence by sentence, the paraphrase adds claims the catalogue did not make,
  and the experiment shows the deterministic draft needs no help. Rejected in favour of the deterministic draft.
- **The draft as the run's input without a correction step (a `--draft` flag on `run`).** One command instead of
  two. Rejected: it is Option 2 with a model in the middle — 60 % more review, every column modelled, the human's
  correction moved to the review queue where it is more expensive; and it would be elicitation by machine, which
  the IREB mapping keeps out of the parser on purpose. The flag of rule 3 is the compromise: the run accepts the
  uncorrected draft and says so.

## Consequences

- **Positive.** A customer can start from a catalogue alone: `source-schema` → `draft-requirements` → correct →
  `run`, every step deterministic until the run. The catalogue's declared natural keys reach the modeler in words.
  The experiment's instrument becomes product with its guards, and the eval keeps using it. The product's premise
  is intact: a human still says what the business is.
- **Negative.** A draft looks like a document; the typed header and the flag are what keep an uncorrected draft from
  passing as an analyst's work, and both must survive editing in a plain editor. An uncorrected draft costs 60 %
  more review on AdventureWorks — the number to put in the manual beside the command. The GUID rule reads the type;
  a catalogue that types its row GUIDs as `char(36)` gets a GUID identifier in the draft, which the human sees as
  the first line of that entity and cuts.
- **Neutral.** C27 stage 4 closes with this ADR's acceptance and the WP that builds it. Option 2 is not foreclosed,
  only unargued. The parser, the modeler and the gates see a document; nothing in the pipeline learns that it was
  drafted except the flag and the provenance line.

## References

- Backlog C1 (`docs/architecture/backlog-2026-10-candidates.md`), C27 stage 4 (`…-candidates-3.md`).
- The C1 experiment: `backlog-2026-07/c1-experiment-drafted-requirements.md` (§3 predictions, §6 results, §7 the
  builds); `docs/log.md` 2026-10-30; `eval/adventureworks/draft_requirements.py`, `eval/c1_compare.py`.
- ADR-0007 (Assist + HITL for source identification), ADR-0015 (positioning), ADR-0017, ADR-0018;
  `docs/methodology/ireb-mapping.md` §5 (requirement sources) and *what the parser deliberately does not do*.
- WP34 §3.8 (a change to the modeler's input is a measured change); WP96–WP99 (the catalogue in the house format).
