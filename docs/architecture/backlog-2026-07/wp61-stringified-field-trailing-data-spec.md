---
type: spec
status: not-measured
updated: 2026-10-09
---

# WP61 — A stringified payload field with trailing data is still the value

Status: **Approved and in progress** (2026-10-09, within WP59's experiment the user approved) ·
Owner: Mischa Eismann · Author: Claude. Widens the `stringified_payload_field` backstop
(`llm.decoded_field`, 2026-09-17). A backstop with telemetry; no gate, no prompt change.

## 1 Problem, measured

Twelfth chain, `20261009T161212987101Z`, Sonnet 5.5 as the contract agent: in 10 of 68
`emit_contract_enrichment` answers the `assets` field came back as a **string** — a complete JSON
object followed by **one extra closing brace**. `decoded_field` decodes a stringified field only
when `json.loads` accepts it; `Extra data` made it fall back to the empty default, silently, and
every field of those tables got the type `unknown`: 158 `undetermined_type` decisions, 66 % of
the chain's 238, and the review clause's failure. Sonnet 4.6 never produced the shape (0 of 24
answers on the eleventh chain).

## 2 The rule

**A stringified field whose prefix is a complete JSON value of the expected shape is that value;
the trailing data is dropped and counted.** `decoded_field` decodes with
`json.JSONDecoder.raw_decode` on the stripped string; a value of the expected type is returned
even when non-whitespace follows, the backstop event `stringified_payload_field` carrying
`trailing: <the trailing characters, at most 40>`. A string that holds no complete value, or one
of another type, yields the default as before.

## 3 Guards before the change

1. `'{"a": {"doc": "x"}}}'` (one brace too many) decodes to the object, with the backstop event
   naming the trailing `}`. 2. A clean stringified value still decodes with no `trailing` in the
   detail. 3. `'not json'` and `'[1]'` for a dict default still yield the default.

## 4 Pre-registration

On the next 5.5 run no contract table loses its types to trailing data; `undetermined_type`
falls to the 4.x level (0–3 per chain).

## 5 Not in this WP

Strict-compatible tool schemas (the grammar that would prevent the shape); a flag for a field
that cannot be decoded at all.

## 6 Results

*(appended after the change)*

**2026-10-09 — built, keyless.** Guards in `tests/test_wp61_stringified_trailing_data.py`
(guard 1 failing before the change; 2 and 3 pinned the unchanged behaviour), change `95b0ae8`:
`json.JSONDecoder.raw_decode` on the stripped string, the tail in the backstop event's
`trailing`. The ten answers of the twelfth chain decode under it (verified by hand on three). 1174
tests, ruff, mypy. §4 is **not yet measured live**.

**2026-10-09 — thirteenth live chain** (`20261009T205307885768Z`): **12 repairs**, every one a stringified `assets`
with a trailing brace, none lost; `undetermined_type` from this class 0 (the twelfth: 158). §4 met
on the class it names — the 68 undetermined types that remained were declared columns the agent
never showed the model (WP63).
