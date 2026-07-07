# WP4 — Typed `ValidationIssue` (replaces issue dicts)

Status: Proposed · Size: S · Depends on: — · Blocks: WP1, WP6

## 1. Problem

`ValidationReport.issues` is `list[dict[str, Any]]` (`state.py`), contradicting the
pydantic-everywhere convention. Consumers defensive-parse it:
`orchestrator.assemble_review_queue` does `str(issue.get("severity", ""))` etc., and the
modeler's retry feedback (`dv2_modeler.run`) serialises raw dicts. A typo'd key would fail
silently. (Project review 2026-07-06, finding "Untyped dicts".)

## 2. Target design [ENFORCE]

In `src/vault_agent/state.py`, next to `ValidationReport`:

```python
IssueSeverity = Literal["error", "warning"]

class ValidationIssue(BaseModel):
    severity: IssueSeverity
    code: str        # stable machine code, e.g. "E_NO_HUBS" / "W_SAT_WIDE"
    construct: str   # the construct (or comma-joined constructs) concerned
    message: str     # human-readable; presentation only, never parsed

class ValidationReport(BaseModel):
    passed: bool = False
    issues: list[ValidationIssue] = Field(default_factory=list)
```

Checkpoint serde: no action needed — `cli._checkpoint_serde` collects every BaseModel in
the state module automatically.

## 3. Changes per file

- `agents/validator.py`: `_issue(...)` returns `ValidationIssue` (keep the helper; change
  its return type and constructor). Type the internal lists `list[ValidationIssue]`.
  `severity` comparisons become `issue.severity == "error"`.
- `agents/orchestrator.py` (`assemble_review_queue`): replace the `.get()` parsing with
  attribute access (`issue.severity`, `issue.code or "issue"` semantics: keep the current
  fallbacks — empty `code` renders as `"issue"`, empty `construct` as `"model"`).
- `agents/dv2_modeler.py` (`run`): retry feedback becomes
  `[issue.model_dump() for issue in state.validation_report.issues]` — payload content is
  unchanged for now (WP3 slims it; if WP3 already landed, keep its errors-only filter).
- Tests constructing issue dicts (`tests/test_agents/test_orchestrator.py`
  `_finished_state`/`_noisy_state`, `tests/test_cli.py`
  `test_cli_checkpoint_collapses_noise_like_the_md`) construct `ValidationIssue` instead.
  `tests/test_agents/test_validator.py` assertions move from `issue["code"]` style to
  `issue.code` style — do this mechanically, do not weaken any assertion.

## 4. Explicitly out of scope

- `state.decisions` stays `list[dict[str, Any]]` (append-only audit log, heterogeneous by
  design). Do not type it in this WP.
- No new gates, no severity changes, no message rewording (keeps diffs reviewable).

## 5. Acceptance criteria

1. `ValidationReport.issues` is `list[ValidationIssue]`; no `dict`-shaped issues remain
   anywhere in `src/` or `tests/`.
2. `rg "issue\.get\(|issue\[[\"']" src tests` finds nothing.
3. The rendered review queue (`render_review_queue_md`) output for the existing test
   fixtures is byte-identical to before the change.
4. Standard DoD (00-overview §Shared conventions).
