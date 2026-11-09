"""C56 — the oracle: what the probe's vault must hold, computed from the sources and the scenario's
loads, independently of datavault4dbt, and compared with what the package built. Each check names
the defect it is expected to expose, or none (README)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from eval.datavault4dbt.hashing import (
    ERROR_KEY,
    ZERO_KEY,
    built_hashdiff,
    documented_hashdiff,
    documented_hashkey,
)

GHOSTS = "('SYSTEM','ERROR')"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""
    defect: int | None = None  # the README's defect number this check exposes, if any
    informational: bool = False


def run_checks(connection: Any) -> list[Check]:
    cursor = connection.cursor()

    def rows(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        cursor.execute(sql, params)
        return list(cursor.fetchall())

    out: list[Check] = []
    out += _hashing(rows)
    out += _hubs_and_links(rows)
    out += _satellites(rows)
    out += _pit_and_multi_active(rows)
    return out


def _hashing(rows: Any) -> list[Check]:
    nasty = {
        r[0]: r[1:]
        for r in rows(
            "select n.id, n.k1, n.k2, n.attr, s.hk_nasty_h, s.hd_nasty_s from dv4x_src.nasty n "
            "join dv4x.stg_nasty s using (id) order by id"
        )
    }
    first = [i for i in nasty if i < 10]
    return [
        Check(
            "hashkeys = the documented rule",
            all(nasty[i][3] == documented_hashkey([nasty[i][0], nasty[i][1]]) for i in first),
        ),
        Check(
            "hashdiffs = the documented rule (case-sensitive)",
            all(nasty[i][4] == documented_hashdiff([nasty[i][2], nasty[i][0]]) for i in nasty),
            defect=3,
        ),
        Check(
            "hashdiffs = the rule as built (upper, first-only, control characters)",
            all(nasty[i][4] == built_hashdiff([nasty[i][2], nasty[i][0]]) for i in nasty),
        ),
        Check("no collision of 'a||'+'b' with 'a'+'||b'", nasty[1][3] != nasty[2][3]),
        Check("hashkey case-insensitive (Ab,c = AB,C)", nasty[3][3] == nasty[4][3]),
        Check("hashdiff case-sensitive (Same != same)", nasty[3][4] != nasty[4][4], defect=3),
        Check("blanks trimmed (' pad ' = 'pad')", nasty[5][3:] == nasty[6][3:]),
        Check("'^^' as a value is not NULL", nasty[7][3] != nasty[8][3]),
        Check("an all-NULL key is the zero key", nasty[9][3] == ZERO_KEY),
        Check(
            "'ab' and 'a<LF>b' differ in the hashdiff",
            nasty[10][4] != nasty[11][4],
            "collide",
            defect=4,
        ),
        Check(
            "line breaks treated alike ('a<LF>b<LF>c', 'ab<LF>c', 'abc')",
            len({nasty[12][4], nasty[13][4], nasty[14][4]}) in (1, 3),
            " ".join(nasty[i][4][:8] for i in (12, 13, 14)),
            defect=4,
        ),
    ]


def _hubs_and_links(rows: Any) -> list[Check]:
    source = {r[0] for r in rows('select jobcandidateid from "HumanResources"."JobCandidate"')}
    hub = dict(
        rows(
            f"select jobcandidateid, hk_job_candidate_h from dv4x.job_candidate_h where rsrc "
            f"not in {GHOSTS}"
        )
    )
    ghosts = rows(f"select count(*) from dv4x.job_candidate_h where rsrc in {GHOSTS}")[0][0]
    union = {
        r[0]
        for r in rows(
            "select businessentityid from dv4x_src.business_entity union select vendorid from "
            "dv4x_src.vendor"
        )
    }
    two_source = {
        r[0]
        for r in rows(
            f"select businessentityid from dv4x.business_entity_ms_h where rsrc not in {GHOSTS}"
        )
    }
    k = documented_hashkey
    delivered = {
        (k([1]), k([10]), ZERO_KEY),
        (k([2]), ZERO_KEY, k([20])),
        (k([3]), k([30]), k([20])),
        (k([1]), k([30]), ZERO_KEY),
    }
    link = set(
        rows(
            "select hk_customer_h, hk_person_business_entity_h, hk_store_business_entity_h "
            f"from dv4x.customer_business_entity_l where rsrc not in {GHOSTS}"
        )
    )
    link_keys = rows(
        "select hk_customer_business_entity_l, customerid, personid, storeid "
        f"from dv4x.stg_customer where rsrc not in {GHOSTS}"
    )
    return [
        Check("hub keys = the source's keys", set(hub) == source, f"{len(hub)} vs {len(source)}"),
        Check("hub has two ghost rows", ghosts == 2, str(ghosts)),
        Check("every hub hashkey = the oracle's", all(h == k([key]) for key, h in hub.items())),
        Check("two-source hub = the union of both sources' keys", two_source == union),
        Check(
            "link combinations = the deliveries",
            link == delivered,
            f"{len(link)} vs {len(delivered)}",
        ),
        Check("link hashkeys = the oracle's", all(r[0] == k(list(r[1:])) for r in link_keys)),
        Check(
            "a dangling reference becomes the zero key (product 9)",
            rows("select hk_product_h from dv4x.stg_order_line where orderlineid = 102")[0][0]
            == ZERO_KEY,
            informational=True,
            detail="unflagged — README, observations",
        ),
    ]


def _satellites(rows: Any) -> list[Check]:
    same = rows(
        "select bool_and(s.resume::text = j.resume::text and s.modifieddate = j.modifieddate), "
        "count(*) "
        "from dv4x.job_candidate_s0 s join dv4x.stg_job_candidate g using (hk_job_candidate_h) "
        f'join "HumanResources"."JobCandidate" j using (jobcandidateid) where s.rsrc not in '
        f"{GHOSTS}"
    )[0]
    xml_diffs = rows(
        "select s.hd_job_candidate_s, j.resume::text, j.modifieddate::varchar from "
        "dv4x.job_candidate_s0 s "
        "join dv4x.stg_job_candidate g using (hk_job_candidate_h) "
        f'join "HumanResources"."JobCandidate" j using (jobcandidateid) where s.rsrc not in '
        f"{GHOSTS}"
    )
    types = rows(
        "select (select data_type from information_schema.columns where table_schema = "
        "'HumanResources' and "
        "table_name = 'JobCandidate' and column_name = 'modifieddate'), (select data_type from "
        "information_schema.columns where table_schema = 'dv4x' and table_name = "
        "'job_candidate_s0' and "
        "column_name = 'modifieddate')"
    )[0]
    history: dict[int, list[tuple[str, str]]] = {}
    for contact, segment, ldts in rows(
        "select c.contactid, s.segment, s.ldts from dv4x.contact_nohwm_s0 s join (select 1 "
        "contactid, %s hk "
        f"union select 2, %s) c on c.hk = s.hk_contact_h where s.rsrc not in {GHOSTS} order by "
        f"1, 3",
        (documented_hashkey([1]), documented_hashkey([2])),
    ):
        history.setdefault(contact, []).append((segment, ldts.strftime("%Y-%m-%d")))
    expected = {
        1: [("bronze", "2026-02-15"), ("gold", "2026-03-01")],
        2: [("silver", "2026-03-01")],
    }
    with_hwm = [
        r[0]
        for r in rows(
            f"select segment from dv4x.contact_s0 where rsrc not in {GHOSTS} and hk_contact_h = "
            f"%s order by ldts",
            (documented_hashkey([1]),),
        )
    ]
    current = rows(
        "select (select segment from dv4x_src.contact where contactid = 1), (select segment from "
        "dv4x.contact_nohwm_s where is_current and hk_contact_h = %s)",
        (documented_hashkey([1]),),
    )[0]
    versions = rows(
        f"select hk_contact_h, ldts, ledts from dv4x.contact_nohwm_s where rsrc not in {GHOSTS} "
        "order by 1, 2"
    )
    bad = []
    for i, (key, _, ledts) in enumerate(versions):
        later = versions[i + 1] if i + 1 < len(versions) and versions[i + 1][0] == key else None
        if (
            later is None
            and ledts.year != 8888
            or later is not None
            and later[1] - ledts != timedelta(microseconds=1)
        ):
            bad.append(key[:8])
    return [
        Check(
            "xml satellite: one row per source row, payload = source",
            bool(same[0]) and same[1] == 13,
            f"{same[1]} rows",
        ),
        Check(
            "xml satellite: hashdiffs = the rule as built",
            all(d == built_hashdiff([r, m]) for d, r, m in xml_diffs),
        ),
        Check("source timestamp arrives as", True, f"{types[0]} -> {types[1]}", informational=True),
        Check(
            "satellite (high-water mark off): one row per change, late row included",
            history == expected,
            str(history),
        ),
        Check(
            "satellite (default high-water mark): the late row is not loaded",
            "bronze" not in with_hwm,
            str(with_hwm),
            informational=True,
        ),
        Check(
            "satellite's current value = the source's",
            current[0] == current[1],
            f"source {current[0]!r}, satellite {current[1]!r}",
            defect=3,
        ),
        Check("sat_v1: each version ends 1 µs before the next, the last open", not bad, str(bad)),
    ]


def _pit_and_multi_active(rows: Any) -> list[Check]:
    loads: dict[str, list[Any]] = {}
    for key, ldts in rows(
        f"select hk_customer_h, ldts from dv4x.customer_s0 where rsrc not in {GHOSTS}"
    ):
        loads.setdefault(key, []).append(ldts)
    pit = rows(
        "select hk_customer_h, sdts, ldts_customer_s from dv4x.customer_pit "
        "where hk_customer_h not in (%s, %s)",
        (ZERO_KEY, ERROR_KEY),
    )
    wrong = 0
    for key, sdts, ldts in pit:
        expect = max((x for x in loads.get(key, []) if x <= sdts), default=None)
        if (
            expect is None
            and ldts is not None
            and ldts.year > 1
            or expect is not None
            and ldts != expect
        ):
            wrong += 1
    groups: dict[str, set[tuple[str, str]]] = {}
    for ldts, kind, number in rows(
        "select ldts, phonetype, phonenumber from dv4x.contact_phone_ms0 where hk_contact_h = %s",
        (documented_hashkey([1]),),
    ):
        groups.setdefault(ldts.strftime("%Y-%m-%d"), set()).add((kind, number))
    expected = {
        "2026-03-01": {("cell", "222"), ("home", "111")},
        "2026-03-05": {("cell", "999"), ("home", "111")},
        "2026-03-10": {("cell", "999")},
    }
    return [
        Check(
            f"PIT: {len(pit)} rows, each the latest satellite load at or before its snapshot",
            wrong == 0,
            f"{wrong} wrong",
        ),
        Check(
            "multi-active: contact 1's phone groups per load = the deliveries",
            groups == expected,
            str(groups),
        ),
    ]
