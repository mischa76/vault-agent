"""C44 — the gate count the README states, and the catalogue the manual keeps, are pinned to the
codes the validator actually raises. The code owns the count (CLAUDE.md invariant); prose that
repeated it has been wrong three times (36 on 2026-11-01, 32 read by a reviewer on 2026-11-03 from a
stale copy, and a bare token grep that says 42 because two constant names carry the prefix). This
test derives the number the only honest way — the string codes passed to `_issue` — and fails the
moment README, catalogue and code disagree. Keyless."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "src" / "vault_agent" / "agents" / "validator.py"
README = ROOT / "README.md"
CATALOGUE = ROOT / "docs" / "operations" / "08-validation-gates.md"


def raised_gate_codes() -> set[str]:
    """Every `E_` code the validator passes to `_issue` — positional (second argument, after the
    severity) or as `code=` — read from the AST, not from a regex over the text."""
    tree = ast.parse(VALIDATOR.read_text(encoding="utf-8"))
    codes: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_issue"):
            continue
        candidates: list[ast.expr] = []
        if len(node.args) > 1:
            candidates.append(node.args[1])
        candidates += [kw.value for kw in node.keywords if kw.arg == "code"]
        for expr in candidates:
            # a literal, or a conditional expression choosing between literals
            literals = [expr] if isinstance(expr, ast.Constant) else (
                [expr.body, expr.orelse] if isinstance(expr, ast.IfExp) else [])
            for lit in literals:
                if isinstance(lit, ast.Constant) and isinstance(lit.value, str) \
                        and lit.value.startswith("E_"):
                    codes.add(lit.value)
    return codes


def catalogue_codes() -> set[str]:
    rows = re.findall(r"^\| *`(E_[A-Z_]+)`", CATALOGUE.read_text(encoding="utf-8"), re.M)
    return set(rows)


def test_the_validator_raises_at_least_the_gates_the_project_has_argued_about() -> None:
    codes = raised_gate_codes()
    assert {"E_SAT_GRAIN_NOT_UNIQUE", "E_HUB_HK_COLLISION", "E_HUB_PAYLOAD_UNREAD",
            "E_LINK_KEY_WRONG_COLUMN"} <= codes
    assert all(c.startswith("E_") for c in codes)


def test_the_manual_catalogue_names_exactly_the_raised_codes() -> None:
    raised, documented = raised_gate_codes(), catalogue_codes()
    assert raised - documented == set(), f"raised but not in the catalogue: {sorted(raised - documented)}"
    assert documented - raised == set(), f"in the catalogue but not raised: {sorted(documented - raised)}"


def test_the_readme_states_the_count_the_code_has() -> None:
    n = len(raised_gate_codes())
    text = README.read_text(encoding="utf-8")
    stated = {int(m) for m in re.findall(r"(\d+) independent (?:`E_` gates|validator gates)", text)}
    assert stated, "the README no longer states the gate count in its two known phrasings"
    assert stated == {n}, f"README says {sorted(stated)}, the validator raises {n} distinct E_ codes"
