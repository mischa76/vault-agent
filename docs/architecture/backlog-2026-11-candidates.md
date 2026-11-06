---
type: backlog
status: proposed
updated: 2026-11-05
---

# Backlog candidates of November 2026

Status: **Proposed, not prioritised** (2026-11-05) · Owner: Mischa Eismann · Author: Claude.
Continues `backlog-2026-10-candidates-3.md` (C22–C44, all closed per its status note of 2026-11-05), append-only.
„C" stands for *candidate*: a finding or idea, not yet a work package.

## C45 — The workbench has three button kinds and no rule for when to use which; the „attach" controls do not read as buttons (owner, 2026-11-05)

**Observed by the owner** in the Project perspective, section Inputs: the three controls „attach requirements",
„attach schema", „attach profiling" are not recognisable at a glance as buttons; they disappear among the file rows
above them (mono file names, grey pills, the small bordered `delete` per file). Asked whether a concept governs when
a button looks like „Run the generator" (filled orange), like „delete project" (orange-red text and border) or like
the attach controls (grey border, white text).

**Read in the code (`frontend/src`, 2026-11-05, `1314107`):** `components/ui.tsx` `Button` has three kinds —
`primary` (`bg-accent text-bg`, filled, `--color-accent` #d97757), `danger` (`border-bad text-bad`, `--color-bad`
#e06c5b), `ghost` (`border-line text-ink`, the default text colour). Usage implies a rule — primary for the one action a
perspective exists for (Run the generator), danger for anything that destroys, ghost for the rest — but **it is
written down nowhere** (not in `docs/operations/14-workbench.md`, no ADR, no comment). The attach controls are not
`Button` at all: a hand-written `<label>` around a hidden file input (`perspectives/Project.tsx`, the Inputs
section), `border-line text-sm`, without `font-medium` — visually one step below ghost, and of the same family as
the per-file `delete` buttons and the pills, which is why they sink. Two more things seen on the way: `danger` and
`accent` differ little in hue (#e06c5b vs #d97757), so the owner reads delete as orange too; and the per-file and
per-run `delete` are bordered grey, not `danger`.

**Shape of a WP:** (1) write the rule — one short paragraph in the workbench chapter: primary at most once per
perspective, the step that moves the project forward; danger for every destructive action, at every size; a
secondary kind for actions that add something (attach, parse, record); ghost for navigation and toggles; (2) give
the attach controls that secondary look — e.g. accent outline or `accent-soft` fill, with an icon or „+" — through
`Button` (it needs an `as="label"` or a file-input variant so the hidden input keeps working); (3) decide whether
`danger` gets a hue clearly apart from the accent; (4) the per-file/per-run `delete` follow the rule. Guard first:
the existing `Project.test.tsx` queries by role and name (`getByRole("button", …)`); the attach controls are found
by `aria-label` on the input, which must survive the change.

## C46 — Reading the source catalogue and profiling from the workbench (owner, 2026-11-05)

**Asked by the owner** while driving the twenty-fourth chain: where in the workbench is the connection to the source
database configured, the catalogue read and the profile made — including the choice of what goes into the profile?
**Answer read in the repo (2026-11-05, `c8fd28c`): nowhere in the workbench.** Both producers are CLI commands only —
`vault-agent source-schema` (WP96, C27 stage 1: metadata, no row) and `vault-agent profile` (WP98, C27 stage 2: reads
rows; ADR-0008 #4's explicitly invoked, read-only, scoped step, note of 2026-10-30). The connection is
`VAULT_AGENT_SOURCE_URL` (manual 5, „the place for the password") or `--url`. The profile's scope is `--schema`,
`--table`, `--check` (range, lengths, patterns by default; examples; all; none), `--sample` (10 000) and `--examples`
(0). The workbench only takes the resulting files through „attach schema" / „attach profiling". The omission was
deliberate and recorded only in the two specs' „not done" lists: WP96 — „a catalogue step in the workbench is a
later increment under ADR-0015"; WP98 — „The workbench". No candidate carried it until now.

**Shape of a WP:** a „Source" section in the Project perspective, above Inputs: (1) the connection — dialect and
host/database shown, the password **not** entered in the browser by default; (2) „read catalogue": schema choice
(the catalogue's schema list offered once connected), views on/off, writes the project's schema input as the CLI
would, the provenance header included; (3) „make profile": schema and table choice (from the read catalogue),
checks as toggles with `examples` off and marked as the one that writes values, sample size, writes the profiling
input; (4) every action recorded as its CLI equivalent like the rest of the workbench, the URL in it with the
password hidden (`hidden_url`).

**Open before a spec:** (a) **where the password lives.** Today's rule: in the environment or `.env`, never in a file
or a shell history; the API key follows the same rule in WP113's settings (`anthropic_api_key_set` as a boolean,
never the key). A browser field would break it — the candidate shapes are the environment variable only (the
section shows „set / not set", like the API key), a per-project URL without password plus the password from the
environment, or a secret store; the owner decides. (b) **Consent for row reads.** WP96's spec tied profiling to
consent and sampling in `deployment-residency.md`; a button makes a row read one click away, so the section has to
say what is read and confirm it. (c) ADR-0015 (single-user tool, Option C) — whether it already settles (a), read
before the spec. (d) Long profiles: the CLI blocks; the workbench needs the run-style progress and cancel
(WP68/WP69) or a limit. Guard: the CLI's outputs for the same arguments as the byte-identity reference — the
workbench must write the same files the commands write.

**C46 (a) read against ADR-0015 (2026-11-06).** ADR-0015 does not name a source-database password, but it settles
the principle: its context lists „Secrets (the Anthropic key, Bedrock/Vertex credentials) are read from the
operator's `.env`", and the consequences of the accepted Option C say „Security stays simple: no listener beyond
`127.0.0.1`, secrets in the operator's `.env`". A second argument comes from the same ADR: the output is handed over
as a project in the customer's git, and WP92 made project folders relocatable for handover — a password stored per
project would travel with it. So, under ADR-0015, the password stays in the environment (`VAULT_AGENT_SOURCE_URL` or
`.env`); the section shows „set / not set" like the API key, and may at most store a URL **without** password per
project. A browser field that persists the password would need an amendment of ADR-0015; one that only passes it
for a single call without storing it is not excluded by the text, but would still put it into the request and
possibly the console log — not recommended. Left open by the ADR: several sources per engagement (one variable per
workbench process today).

## C46 — taken up as WP119 (2026-11-07)

On the owner's go, specified and built as WP119 (): the connection
from the workbench's environment only, as the ADR-0015 reading above says; a per-project connection and progress for
long profiles stay out (its §3).
