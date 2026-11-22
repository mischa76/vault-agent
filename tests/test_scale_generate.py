"""Keyless tests for the WP13 scale-hardness tooling (§5 acceptance).

Covers: generator determinism (byte-identity for a fixed seed), the five trap classes are
present, schema/profiling/golden mutual consistency, requirements size scales and the
near-``MAX_DOCUMENT_CHARS`` warning fires, the committed ``scale_30`` case loads through the
WP6 loader and its inputs match a fresh generation, ``materialize_case`` synthesises a
``generate`` case, and the eval-runner usage/metrics plumbing is populated (WP13 §3).
"""
from pathlib import Path

import pytest

from eval.datasets import GenerateSpec, load_eval_case, materialize_case
from eval.mapping import load_golden_mapping
from eval.scale import generate as gen
from vault_agent.profiling import load_profiling
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.source_schema import load_source_schemas

_SCALE_30 = Path(__file__).parent.parent / "eval" / "datasets" / "scale_30"


# ── determinism ───────────────────────────────────────────────────────────────────────────
def test_generation_is_byte_deterministic(tmp_path: Path) -> None:
    a = gen.write_landscape(gen.generate_landscape(40, 7), tmp_path / "a")
    b = gen.write_landscape(gen.generate_landscape(40, 7), tmp_path / "b")
    for kind, path_a in a.items():
        assert path_a.read_bytes() == b[kind].read_bytes(), f"{kind} not byte-identical"


def test_different_seed_changes_output(tmp_path: Path) -> None:
    a = gen.write_landscape(gen.generate_landscape(40, 7), tmp_path / "a")
    c = gen.write_landscape(gen.generate_landscape(40, 8), tmp_path / "c")
    assert a["source_schema"].read_bytes() != c["source_schema"].read_bytes()


def test_table_count_is_exact() -> None:
    for n in (1, 5, 30, 100, 300):
        landscape = gen.generate_landscape(n, 3)
        assert len(landscape.tables) == n


def test_rejects_non_positive_tables() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        gen.generate_landscape(0, 1)


# ── trap classes present (count, not exact strings) ───────────────────────────────────────
def test_all_five_trap_classes_present(tmp_path: Path) -> None:
    landscape = gen.generate_landscape(120, 42)
    files = gen.write_landscape(landscape, tmp_path)
    schemas = load_source_schemas(files["source_schema"])
    golden = load_golden_mapping(files["golden_mapping"])

    guid_shadow = sum(1 for t in schemas for c in t.column_names if c == "TECH_GUID")
    false_friend = sum(1 for t in schemas for c in t.column_names if c == "KD_NR")
    fk_comment = sum(
        1
        for t in schemas
        for cr in t.column_refs
        if cr.comment and cr.comment.startswith("FK to ")
    )
    wide = sum(1 for t in schemas if len(t.column_names) >= gen.WIDE_MIN_COLS)

    assert guid_shadow > 0, "GUID-shadow trap missing"
    assert false_friend > 0, "false-friend trap missing"
    assert fk_comment > 0, "FK-comment trap missing"
    assert wide > 0, "no wide table (width axis missing)"
    assert len(golden.ambiguous) > 0, "synonym/multi-source trap missing (no ambiguous concept)"
    assert len(golden.false_friends) > 0, "false friends not recorded in the golden set"


def test_statistics_trap_guid_profiles_better_than_the_key(tmp_path: Path) -> None:
    landscape = gen.generate_landscape(60, 42)
    files = gen.write_landscape(landscape, tmp_path)
    schemas = load_source_schemas(files["source_schema"])
    prof = load_profiling(files["profiling"])

    trap_seen = False
    for t in schemas:
        names = t.column_names
        if "TECH_GUID" not in names:
            continue
        pcols = prof.get(t.table, {})
        bk = names[0]
        if "TECH_GUID" in pcols and bk in pcols:
            assert pcols["TECH_GUID"].uniqueness_ratio >= pcols[bk].uniqueness_ratio
            assert pcols[bk].null_ratio > 0.0  # the real key carries a realistic wart
            trap_seen = True
    assert trap_seen, "statistics trap not exercised"


# ── schema/profiling/golden mutual consistency ────────────────────────────────────────────
def _columns_by_table(schemas: list) -> dict[str, set[str]]:
    return {t.table: {normalize_identifier(c) for c in t.column_names} for t in schemas}


def test_every_golden_concept_exists_in_the_schema(tmp_path: Path) -> None:
    landscape = gen.generate_landscape(90, 13)
    files = gen.write_landscape(landscape, tmp_path)
    schemas = load_source_schemas(files["source_schema"])
    golden = load_golden_mapping(files["golden_mapping"])
    cols = _columns_by_table(schemas)

    for m in golden.mappings:
        assert m.source_table in cols
        assert normalize_identifier(m.source_column) in cols[m.source_table]
    for a in golden.ambiguous:
        for cand in a.candidates:
            assert cand.table in cols
            assert normalize_identifier(cand.column) in cols[cand.table]
    for ff in golden.false_friends:
        assert ff.table in cols
        assert normalize_identifier(ff.column) in cols[ff.table]


def test_profiling_only_names_declared_columns(tmp_path: Path) -> None:
    landscape = gen.generate_landscape(90, 13)
    files = gen.write_landscape(landscape, tmp_path)
    schemas = load_source_schemas(files["source_schema"])
    prof = load_profiling(files["profiling"])
    cols = _columns_by_table(schemas)

    for table, pcols in prof.items():
        assert table in cols
        for column in pcols:
            assert normalize_identifier(column) in cols[table]


def test_golden_universe_is_sampled_not_all_tables(tmp_path: Path) -> None:
    # WP9.2 semantics: the golden set is a hand-verifiable sample (~30), never one per table.
    landscape = gen.generate_landscape(300, 5)
    files = gen.write_landscape(landscape, tmp_path)
    golden = load_golden_mapping(files["golden_mapping"])
    universe = len(golden.mappings) + len(golden.ambiguous) + len(golden.gaps)
    assert universe <= gen.GOLDEN_SAMPLE_SIZE + len(gen.GAP_CONCEPTS) + 2
    assert universe < 300


# ── requirements size scales + near-limit warning ─────────────────────────────────────────
def test_requirements_size_scales_with_table_count() -> None:
    small = gen.render_requirements(gen.generate_landscape(30, 1))
    large = gen.render_requirements(gen.generate_landscape(300, 1))
    assert len(large) > len(small)


def test_near_max_document_chars_warning_fires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Rather than generate a 4000-table landscape, shrink the guard so a normal one trips it.
    monkeypatch.setattr(gen, "MAX_DOCUMENT_CHARS", 5000)
    rc = gen.main(["--tables", "60", "--seed", "1", "--out", str(tmp_path)])
    assert rc == 0
    err = capsys.readouterr().err
    assert "WARNING" in err and "MAX_DOCUMENT_CHARS" in err


def test_no_warning_well_below_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gen.main(["--tables", "20", "--seed", "1", "--out", str(tmp_path)])
    assert "WARNING" not in capsys.readouterr().err


# ── committed scale_30 case ───────────────────────────────────────────────────────────────
def test_scale_30_loads_through_the_wp6_loader() -> None:
    case = load_eval_case(_SCALE_30 / "dataset.yml")
    assert case.name == "scale_30"
    assert case.input_document is not None and case.input_document.is_file()
    assert case.source_schema is not None and case.source_schema.is_file()
    assert case.profiling is not None and case.profiling.is_file()
    # WP14: scale scores the mapper on column binding, not concept naming (Candidate #2).
    assert case.mapping_match == "column"
    assert case.expectations.min_scores["mapping_coverage"] == 0.8
    assert case.expectations.min_scores["false_friend_hits"] == 1.0
    # the mapper inputs load cleanly
    assert load_source_schemas(case.source_schema)
    assert load_profiling(case.profiling)
    assert load_golden_mapping(_SCALE_30 / "golden_mapping.yml").mappings


def test_committed_scale_30_matches_a_fresh_generation(tmp_path: Path) -> None:
    # Provenance + determinism: the committed inputs ARE `generate --tables 30 --seed 42`.
    files = gen.write_landscape(gen.generate_landscape(30, 42), tmp_path)
    assert (
        files["source_schema"].read_text()
        == (_SCALE_30 / "inputs" / "source_schema.yml").read_text()
    )
    assert (
        files["profiling"].read_text() == (_SCALE_30 / "inputs" / "profiling.yml").read_text()
    )
    assert (
        files["requirements"].read_text()
        == (_SCALE_30 / "inputs" / "requirements.md").read_text()
    )
    assert (
        files["golden_mapping"].read_text() == (_SCALE_30 / "golden_mapping.yml").read_text()
    )


# ── materialize_case (generate on demand) ─────────────────────────────────────────────────
def test_materialize_committed_case_returns_golden_path(tmp_path: Path) -> None:
    case = load_eval_case(_SCALE_30 / "dataset.yml")
    resolved, golden = materialize_case(case, tmp_path)
    assert resolved is case  # unchanged
    assert golden is not None and golden.name == "golden_mapping.yml" and golden.is_file()


def test_materialize_generate_case_synthesises_inputs(tmp_path: Path) -> None:
    from eval.datasets import EvalCase, GoldenModel

    case = EvalCase(name="scale_x", generate=GenerateSpec(tables=50, seed=9), golden=GoldenModel())
    resolved, golden = materialize_case(case, tmp_path)
    assert resolved.input_document is not None and resolved.input_document.is_file()
    assert resolved.source_schema is not None and resolved.source_schema.is_file()
    assert resolved.profiling is not None and resolved.profiling.is_file()
    assert golden is not None and golden.is_file()
    # the synthesised inputs are valid mapper inputs
    assert len(load_source_schemas(resolved.source_schema)) == 50


def test_generate_case_rejects_committed_paths() -> None:
    from eval.datasets import EvalCase, GoldenModel

    with pytest.raises(ValueError, match="must not also declare"):
        EvalCase(
            name="bad",
            generate=GenerateSpec(tables=10, seed=1),
            source_schema=Path("x.yml"),
            golden=GoldenModel(),
        )


def test_case_requires_exactly_one_input_source() -> None:
    from eval.datasets import EvalCase, GoldenModel

    with pytest.raises(ValueError, match="exactly one"):
        EvalCase(name="neither", golden=GoldenModel())


# ── eval-runner usage/metrics plumbing (WP13 §3, acceptance #2) ───────────────────────────
def test_usage_totals_accumulate_by_model() -> None:
    from eval.run import UsageTotals

    usage = UsageTotals()
    usage.record("sonnet", 100, 20, 80)
    usage.record("sonnet", 50, 10, 40)
    usage.record("opus", 200, 30, 0)
    d = usage.as_dict()
    assert d["calls"] == 3
    assert d["input_tokens"] == 350 and d["output_tokens"] == 60 and d["cache_read_tokens"] == 120
    assert d["by_model"]["sonnet"]["calls"] == 2
    assert d["by_model"]["opus"]["input_tokens"] == 200


def test_result_payload_carries_usage_and_metrics() -> None:
    from eval.run import UsageTotals, build_result_payload, run_metrics
    from vault_agent.state import VaultAgentState

    usage = UsageTotals()
    usage.record("sonnet", 1000, 200, 800)
    metrics = run_metrics(VaultAgentState(), 12.5, usage)
    payload = build_result_payload(
        _dummy_case(), 1, [], models={"primary_model": "sonnet"}, git_sha="abc",
        timestamp="t", metrics=metrics,
    )
    assert payload["metrics"]["usage"]["input_tokens"] == 1000
    assert payload["metrics"]["usage"]["cache_read_tokens"] == 800
    assert payload["metrics"]["wall_clock_seconds"] == 12.5
    assert "review_items_total" in payload["metrics"]
    assert "review_queue_lines" in payload["metrics"]


def test_render_metrics_is_pure_and_reports_cache_share() -> None:
    from eval.run import render_metrics

    metrics = [
        {
            "wall_clock_seconds": 10.0,
            "usage": {
                "calls": 5,
                "input_tokens": 1000,
                "output_tokens": 200,
                "cache_read_tokens": 500,
            },
            "review_items_total": 7,
            "review_queue_lines": 20,
        }
    ]
    out = render_metrics("scale_30", metrics)
    # 500 cached of 1500 prompt tokens = 33%. This asserted 50% until 2026-08-12 — the share
    # was computed against `input_tokens` alone, which is the UNCACHED remainder and excludes
    # the cached tokens, so the denominator was missing the very tokens being counted.
    assert "33% cache hit" in out
    assert "prompt=1,500 tok" in out
    assert "1,000 uncached" in out
    assert "review items=7" in out


def _dummy_case():  # type: ignore[no-untyped-def]
    from eval.datasets import EvalCase, GoldenModel

    return EvalCase(name="scale_30", input_document=Path("x.md"), golden=GoldenModel())
