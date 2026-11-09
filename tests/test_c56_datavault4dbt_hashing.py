"""C56 — the oracle's two hash models pinned against what datavault4dbt 2.3.0 built on PostgreSQL
16.15 (`dv4x.stg_nasty`, 2026-11-09; eval/datavault4dbt/README.md). Keyless: the hashes are the
warehouse's, recorded. If the package is upgraded and the probe re-run, a fixed defect shows here
as the documented model starting to match — update these rows with the new measurement and the
README's defect list together."""

from __future__ import annotations

import pytest

from eval.datavault4dbt.hashing import (
    ZERO_KEY,
    built_hashdiff,
    documented_hashdiff,
    documented_hashkey,
)

# id: (k1, k2, attr, hk_nasty_h as built, hd_nasty_s as built) — the stage hashes [k1, k2] and
# [attr, k1]
MEASURED = {
    1: ("a||", "b", "x", "96b5e6d768a640882c1d163b943fb760", "e99498f5365f12b5ffcbefb7a40017b4"),
    2: ("a", "||b", "x", "01b1ea2bd33c2386ab639a952f98a70f", "a649973cadf70c39710f699e0fcbc689"),
    3: ("Ab", "c", "Same", "702ce0312bc60c3f45ce492a55d90495", "f075bfe45dcb44a1f0ce90857f398218"),
    4: ("AB", "C", "same", "702ce0312bc60c3f45ce492a55d90495", "f075bfe45dcb44a1f0ce90857f398218"),
    5: (
        " pad ",
        "q",
        " pad ",
        "27cd541621bb46fee6db112bc8c96115",
        "5b9b3336ddddebe817286da6ff46562c",
    ),
    6: ("pad", "q", "pad", "27cd541621bb46fee6db112bc8c96115", "5b9b3336ddddebe817286da6ff46562c"),
    7: (
        "^^",
        None,
        '"quoted"',
        "cb7197e51cb6e480e59c7b8e87c27a5e",
        "279048ef6205280ad1b792c0b046628c",
    ),
    8: (None, "^^", None, "a47296d63e33a786b0e5703c52f4b3d8", ZERO_KEY),
    9: (None, None, "all-null key", ZERO_KEY, "e45ff451ee0f4bff183847f3fef2d1d8"),
    10: ("z", "n1", "ab", "f60471aa9c0e1981dfa621cc9cab13a6", "749cd699f81e22ef4da4c91096086b8d"),
    11: ("z", "n2", "a\nb", "104a1760561942725e8a924122845ff3", "749cd699f81e22ef4da4c91096086b8d"),
    12: (
        "z",
        "n3",
        "a\nb\nc",
        "788eb13b44a7cd279384aa37ea432b8f",
        "40df8401ca375301040c36c59bc4b220",
    ),
    13: (
        "z",
        "n4",
        "ab\nc",
        "74e8690766710f7908a97d7e98eb4394",
        "a162e20ff8e43219957d2e4b7abc7132",
    ),
    14: ("z", "n5", "abc", "cc1863a3e0741468ebf30fd1313320ee", "a162e20ff8e43219957d2e4b7abc7132"),
}


@pytest.mark.parametrize("row", sorted(MEASURED))
def test_the_built_model_reproduces_every_measured_hashdiff(row: int) -> None:
    k1, _, attr, _, hashdiff = MEASURED[row]
    assert built_hashdiff([attr, k1]) == hashdiff


@pytest.mark.parametrize("row", sorted(MEASURED))
def test_every_measured_hashkey_follows_the_documented_rule(row: int) -> None:
    k1, k2, _, hashkey, _ = MEASURED[row]
    assert documented_hashkey([k1, k2]) == hashkey


def test_defect_3_the_documented_hashdiff_is_case_sensitive_the_built_one_is_not() -> None:
    assert documented_hashdiff(["Same", "Ab"]) != documented_hashdiff(["same", "AB"])
    assert MEASURED[3][4] == MEASURED[4][4]  # what the warehouse built
    assert documented_hashdiff(["Same", "Ab"]) != MEASURED[3][4]


def test_defect_4_only_the_first_line_break_is_removed() -> None:
    assert MEASURED[10][4] == MEASURED[11][4]  # 'ab' == 'a\nb'
    assert MEASURED[13][4] == MEASURED[14][4]  # 'ab\nc' == 'abc'
    assert MEASURED[12][4] not in (MEASURED[13][4], MEASURED[14][4])  # 'a\nb\nc' differs from both
    assert documented_hashdiff(["ab", "z"]) != documented_hashdiff(
        ["a\nb", "z"]
    )  # the documented rule keeps it


def test_the_delimiter_tokens_prevent_the_naive_collision() -> None:
    assert MEASURED[1][3] != MEASURED[2][3]
    assert (
        "a||" + "||" + "b" == "a" + "||" + "||b"
    )  # what naive concatenation would have hashed alike
