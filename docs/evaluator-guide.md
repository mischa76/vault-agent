# Evaluating vault-agent with your own material

For someone who knows Data Vault and wants to judge the tool on real inputs — a requirements
document and a source model from a landscape you know — rather than on the bundled demos. Two
hours of your time, a few dollars of API credit, and an honest verdict in return.

## 1 What you need

- Python 3.12 and [`uv`](https://docs.astral.sh/uv/); a terminal. No warehouse is needed to
  evaluate the modelling; a local PostgreSQL is optional for building the generated dbt project
  (operations manual, chapter 9).
- An Anthropic API key with a few dollars of credit. A 20-table increment costs about 1 USD on
  the default models (Sonnet 5.5 / Opus 5.5) and takes 5 to 10 minutes; a five-step chain over
  AdventureWorks costs about 5 USD.
- **Your inputs go to the Anthropic API.** Use material you may send there: sanitised column
  names and documents are fine; customer data never is (the tool reads schemas and documents, not
  rows). API input is not used for training under Anthropic's commercial terms, but your
  organisation's rules decide.

```bash
git clone https://github.com/mischa76/vault-agent.git && cd vault-agent
uv sync
cp .env.example .env            # add ANTHROPIC_API_KEY
uv run pytest -q                # keyless; should be green before you spend a cent
```

Installation details and troubleshooting: `docs/operations/04-installation.md`.

## 2 What to prepare

**A requirements document** (`.md`, `.txt` or `.pdf`): the business view of one area — which
things the business tracks, how they are identified, which relationships matter, what changes
over time. Prose is fine; numbered requirements help the trace. Example:
`eval/datasets/adventureworks_person/requirements.md`.

**A declared source schema** (`.yml`), one entry per table, with columns, their types and, where
the catalogue has them, **foreign keys** — the link proposer reads those, and without them every
relationship rests on the model's reading of the document:

```yaml
- table: Address
  columns:
    - name: AddressID
      type: int
      comment: Primary key for Address records.
    - name: StateProvinceID
      type: int
  foreign_keys:
    - columns: [StateProvinceID]
      references_table: StateProvince
      references_columns: [StateProvinceID]
```

Example: `eval/datasets/adventureworks_person/source_schema.yml`. A bare list of column names
works too, with more review items as the price.

## 3 Running

```bash
uv run vault-agent run my_requirements.md --source-schema my_schema.yml --out output/first
```

The run pauses at a human-in-the-loop checkpoint and prints the **review queue**: items you
must decide first, then items it merely discloses. `uv run vault-agent resume --accept` continues
with the standard unattended decisions (what the eval harness does); `--interactive` lets you
answer in the terminal. A second increment on the same vault: `run ... --existing output/first`
(brownfield mode, chapter 6.7). The output directory holds a runnable dbt project (staging + raw
vault), data contracts, `review-queue.md`, an HTML report and a proposed ADR.

## 4 What to judge

Handling and result are two separate verdicts; both are wanted.

**Handling**
1. Did the inputs you had fit the formats without a fight? What did you have to invent?
2. Was the review queue readable — do the *decisions* ask the questions you would ask a
   modeller, and are the *disclosures* things you would want to know?
3. When a step failed validation, did the message say what and why, in your terms?

**Result**
4. Hubs: one per business concept, keyed on what you would key it on? List the ones you would
   not have built and the ones missing.
5. Links: do the relationships hold, including role-qualified ones and translations through
   surrogate keys? Anything joined wrong?
6. Satellites: is the payload where you would hang it; any table whose descriptive columns went
   nowhere?
7. The generated dbt project: would you let it into a repo — naming, structure, the contracts?
8. Against your own modelling of the same area: what would you have decided differently, and
   where would you have needed the document the tool did not have?

## 5 Sending feedback

A plain list beats a form. Per item: what you saw, what you expected, which run (the output
directory holds `metadata/` with the run stamp). The `.vault-agent/traces/*.jsonl` file beside
the run is the full LLM transcript; attach it if a result surprises you — it is how every
finding in this project has been traced so far.

Known limits worth knowing before you judge: scale is verified at about 30 tables per increment
of real variety; Business Vault logic and mart semantics are flagged for ratification, never
generated as authoritative; the Databricks target is built but has never run on a workspace.
The full catalogue of what is verified, and how: `docs/index.md` and `CLAUDE.md` (open items).
