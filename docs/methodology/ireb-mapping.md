# IREB Requirements Engineering – Mapping to the Parser Agent

> How the Requirements Parser's output aligns with IREB CPRE conventions — and, specific to this
> project, how the IREB **structure-and-data aspect** of functional requirements becomes the input
> to Data Vault modeling.
>
> Grounded in the *IREB CPRE Foundation Level Syllabus* v3.2 (© IREB e.V.). Concepts are
> paraphrased and applied to the agent context; nothing is reproduced verbatim. Section numbers
> (§) refer to that syllabus.

## Why this mapping exists

The Requirements Parser turns a free-text requirements document into a list of atomic, structured
`ParsedRequirement` records (`state.requirements`) so that downstream agents reason over discrete
facts instead of prose. IREB CPRE FL is the established vocabulary for *what a requirement is* and
*what makes it good*, so the parser's record shape and guardrails are deliberately aligned to it.
The parser **only extracts**; it does not model, elicit, or validate semantics — those are separate
agents (Business-Key Identifier, DV2.0 Modeler, Validator), mirroring IREB's separation of
documentation from elicitation, negotiation and validation (§4).

## 1. IREB requirement kinds → the parser's `category`

IREB distinguishes **three kinds** of requirement (§1.1): *functional*, *quality*, and *constraints
(Randbedingungen)*. The parser uses a **four-way** `category`, splitting IREB's single "constraints"
bucket into two, because the two halves play very different roles downstream:

| IREB kind (§1.1) | Parser `category` | Why / what it feeds |
|---|---|---|
| Functional requirement | `functional` | An actor performs an action on an object. The raw material for the data model (see §3 below). |
| Quality requirement | `non-functional` | Performance, security, availability… Recorded for completeness; not a Data Vault structure. |
| Constraint (Randbedingung) — *internal data/behaviour policy* | `business-rule` | Cardinalities, allowed status values, ownership/temporal rules. **First-class modeling input** — drives link grain, driving keys, effectivity. |
| Constraint (Randbedingung) — *external/technical* | `constraint` | Regulatory, compliance, platform limits. Bounds the solution but is not itself a vault structure. |

The split is a project-specific refinement of IREB, not a contradiction of it: both `business-rule`
and `constraint` are IREB *Randbedingungen*; we separate them because a rule *about the data*
(e.g. "an account belongs to one customer at a time") is something the modeler must act on, whereas
an external constraint is context the human ratifies.

## 2. The requirement-sentence template → the `actor / action / obj` triple

IREB describes **template-based work products** (§3.3), of which *Satzschablonen* (sentence
templates — e.g. ISO 29148, Rupp) give a requirement a predefined syntactic structure:
*subject — process — object*, optionally under a condition. The parser captures exactly this
backbone for functional requirements as the `actor / action / obj` triple:

- `actor` ← the subject / role or system that acts (`customer`, `bank`)
- `action` ← the process / verb (`open`, `transfer`, `assign`)
- `obj` ← the object the action targets (`account`, `transaction`)

The triple is filled only for `functional` requirements and left `null` where a part genuinely
cannot be determined — consistent with IREB's view that templates *aid* capture but must not be
filled for form's sake (§3.3, "Nachteile und Tücken").

## 3. The "structure-and-data" aspect → the Data Vault model

This is the bridge that makes the mapping matter for *this* project. IREB notes (§3.1.4) that
functional requirements address several aspects — **structure & data**, **function & flow**, and
**state & behaviour** — always understood within a **context** (external actors, system boundary).
Of these, the **structure-and-data aspect** (§3.4.3) is what a Data Vault models: static domain
models specify the *(business) objects, their attributes, and their relationships* — the entities a
system must know to do its job.

The parser captures the raw signal of that aspect; the Business-Key Identifier and DV2.0 Modeler
realize it:

| IREB structure-and-data element (§3.4.3) | Captured by the parser as | Becomes (downstream) |
|---|---|---|
| Business object / entity | `obj` (and `actor` when it is a business entity) | `Hub` (anchored on its business key) |
| Relationship between objects | `functional` requirement relating two objects + `business-rule` on its cardinality/temporality | `Link` (with grain, driving key, effectivity) |
| Attribute / descriptive property | requirement `text` describing properties of an object | `Satellite` |
| Business policy on data | `business-rule` (cardinality, ownership, allowed values) | Link grain / driving key / satellite split rationale |

The *function-and-flow* and *state-and-behaviour* aspects are recorded (as `functional` /
`business-rule` text) but not turned into structures by this pipeline — the Raw Vault models
structure and data, not process. This is a deliberate scope choice consistent with
[ADR-0007](../architecture/adrs/ADR-0007-automation-scope-by-layer.md).

## 4. IREB quality criteria → parser guardrails and downstream gates

IREB lists quality criteria for individual requirements (§3.8): *adequate, necessary, unambiguous,
complete, comprehensible, verifiable* — and, for work products covering many requirements:
*consistent, non-redundant, complete, modifiable, traceable, conformant*. They map to where each is
enforced:

- **Adequate / necessary** → the parser's first guardrail: *extract only what the text supports,
  never invent requirements, fields, or rules* ("fidelity over coverage").
- **Unambiguous / atomic** → *one record per atomic requirement; split compound statements*; keep
  `text` a single self-contained sentence free of markup.
- **Traceable (Verfolgbarkeit)** → every requirement carries a stable `id` (`REQ-001`…), and every
  downstream `Hub`/`Link`/`Satellite` keeps `requirement_ids` back to the statements that justify
  it — the spine of the ADR trail.
- **Complete / consistent / verifiable** → *not* the parser's job; surfaced later by the Validator's
  gates and the human-in-the-loop review queue, which flag gaps rather than guessing — matching
  IREB's placement of validation in a separate practice (§4.4).

## 5. Requirement sources → the two-input model

IREB classifies requirement sources into three types (§4.1): **stakeholders**, **documents**, and
**systems in operation** — and stresses fixing the **system boundary/context** to focus on the
relevant requirements. Vault-Agent's inputs map onto this:

- **Documents** → `state.input_documents` (the requirements document the parser reads).
- **Systems in operation** → the optional declared **source schema** (`SourceTable`, ADR-0004), and,
  prospectively, live profiling of the source system
  ([ADR-0008](../architecture/adrs/ADR-0008-source-to-target-mapping.md)). This is the "what things
  are physically called" input.
- **System boundary / context** → the requirements-scoped subset that bounds what the agent
  attempts (also ADR-0008, premise (b)).

## 6. Glossary and consistent terminology → business keys and contracts

IREB treats the **glossary** as a work product (§3.5) and makes "use terms consistently, as defined
in the glossary" a documentation guideline (§3.1.5). In Vault-Agent this surfaces as: business-entity
and business-key naming that stays faithful to the source vocabulary, and the data-contract layer
([ADR-0005](../architecture/adrs/ADR-0005-data-contract-spec.md)) that pins field meaning — the place
where a project's *Fachsprache* is recorded rather than invented.

## What the parser deliberately does not do

Consistent with IREB's separation of practices, the parser does **not** elicit (§4.2), resolve
conflicts (§4.3), validate (§4.4), or model (§3.4). It produces clean, traceable, atomic
requirements; the modeling agents and the validator do the rest. Coverage matters less than
fidelity — an empty `actor`/`action`/`obj` is preferred over an invented one.

## Source

*IREB Certified Professional for Requirements Engineering — Foundation Level, Syllabus* v3.2,
© IREB e.V. Concepts paraphrased and mapped to the agent; section references (§) point into that
syllabus for cross-checking.
