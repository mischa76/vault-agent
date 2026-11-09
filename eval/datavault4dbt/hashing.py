"""C56 — datavault4dbt's hash rules, twice: as the package documents them and as it builds them on
PostgreSQL.

Documented (datavault4dbt 2.3.0, `dbt_project.yml` and
docs/26_general-usage-notes/29_global-variables): each input trimmed and cast to text; inside a
value the quote character, the null placeholder and the concat string replaced by their tokens;
each value wrapped in the quote character; NULL → the null placeholder; the values joined by the
concat string; a hashkey's input upper-cased (`hashkey_input_case_sensitive: FALSE`), a hashdiff's
not (`hashdiff_input_case_sensitive: TRUE`); MD5, lower-case hex; an input that is all NULL is the
zero key.

As built on PostgreSQL (measured 2026-11-09, README): the hashdiff is upper-cased too unless the
root project sets the variable itself (defect 3), and `regexp_replace` without the `g` flag touches
only the FIRST backslash, the FIRST quote character and the FIRST of each of `\\n \\t \\v \\r` in
the whole input (defect 4). Pure functions — the keyless tests pin them against hashes the
warehouse produced."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

CONCAT = "||"
QUOTE = '"'
NULL = "^^"
TOKENS = {
    QUOTE: "dv4dbt-quote-replacement",
    NULL: "dv4dbt-null-replacement",
    CONCAT: "dv4dbt-concat-replacement",
}
ZERO_KEY = "0" * 32
ERROR_KEY = "f" * 32
CONTROL = ("\n", "\t", "\v", "\r")


def _documented(value: object) -> str:
    if value is None:
        return NULL
    text = str(value).strip()
    for token in (QUOTE, NULL, CONCAT):
        text = text.replace(token, TOKENS[token])
    return QUOTE + text + QUOTE


def _as_built(value: object) -> str:
    if value is None:
        return NULL
    text = str(value).strip().replace("\\", "\\\\", 1).replace(QUOTE, TOKENS[QUOTE], 1)
    return QUOTE + text.replace(NULL, TOKENS[NULL]).replace(CONCAT, TOKENS[CONCAT]) + QUOTE


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def documented_hashkey(values: Sequence[object]) -> str:
    if all(v is None for v in values):
        return ZERO_KEY
    return _md5(CONCAT.join(_documented(v) for v in values).upper())


def documented_hashdiff(values: Sequence[object]) -> str:
    if all(v is None for v in values):
        return ZERO_KEY
    return _md5(CONCAT.join(_documented(v) for v in values))


def built_hashkey(values: Sequence[object]) -> str:
    """The hashkey as built on PostgreSQL — equal to the documented one unless a value holds a
    second quote, a backslash or a control character."""
    return _built(values)


def built_hashdiff(values: Sequence[object]) -> str:
    """The hashdiff as built on PostgreSQL with the package's defaults: upper-cased (defect 3),
    first-occurrence replacements and control-character removal (defect 4)."""
    return _built(values)


def _built(values: Sequence[object]) -> str:
    if all(v is None for v in values):
        return ZERO_KEY
    text = CONCAT.join(_as_built(v) for v in values).upper()
    for character in CONTROL:
        text = text.replace(character, "", 1)
    return _md5(text)
