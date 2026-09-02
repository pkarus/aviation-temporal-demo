"""test_uc1.py - QUERY-UC1 live gate for Q01 to Q04 plus Q02F.

Every test here fires real PyRel queries at the live ``PK_AVIATION_TEMPORAL`` model under
``RAI_DEMO_AVIATION_TEMPORAL`` on the ``aviation_temporal_logic_s`` reasoner and compares the
**complete** result set - every row, every column, every cell, in the frozen ``order_by`` order -
against ``EXPECTED_ANSWERS.yaml``. Nothing is mocked, no producer's claim is trusted, and a row
count on its own is never accepted as evidence: three of the four questions would pass a
count-only check while returning wrong cells.

Run it warm::

    .venv/bin/rai reasoners resume --type Logic --name aviation_temporal_logic_s --wait
    PYTHONPATH=rai_code TERM=dumb .venv/bin/python -m pytest tests/test_uc1.py -q

The first query in the process pays a 100 to 270 second full-model sync, so the module-scoped
``uc1`` fixture exists to pay it once. One ``Model`` per process, deliberately: a second one
makes the free ``distinct(...)`` raise ``[Ambiguous model]`` (PROBE N-02).

Coverage beyond the frozen result sets, one test per boundary the frozen answers exist to pin:

* before the first assignment versus outside existence (the two absence statuses),
* the exclusive end-of-life bound (``<`` and not ``<=``),
* the explicit unknown gap, and that it is never backfilled from master,
* same-day event ordering on the audit stream, which the daily projection loses,
* the repeated ``A -> B -> A``, which any de-duplication on the status value destroys,
* Q03's 120 distinct month ends and the multiplicity gate the count silently depends on,
* Q04's two unaligned stream boundaries and the three-valued ``is_type_change``,
* DV-33 mutual exclusivity, evaluated over every branch rather than short-circuited.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rai_code"))

pytestmark = pytest.mark.live

ROLE = "RAI_DEMO_AVIATION_TEMPORAL"
DB = "PK_AVIATION_TEMPORAL"


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def uc1():
    """The query module, with the ontology loaded and synced. One ``Model`` per process.

    ``warm_model()`` pays the ~130 second sync once and retries through
    ``prepareIndex: model is currently locked``, which is what a *concurrent* process building
    the same model raises at a reader. Without it the first parametrised case absorbs the sync
    and a colliding sibling turns into a spurious test failure.
    """
    from queries import uc1 as module

    module.warm_model()
    return module


@pytest.fixture(scope="module")
def manifest(uc1):
    return uc1.load_manifest()


@pytest.fixture(scope="module")
def questions(uc1, manifest):
    return uc1.frozen_questions(manifest)


@pytest.fixture(scope="module")
def result_sets(questions):
    """``{result_set_id: (question_id, result_set)}`` for every UC1 result set."""
    index = {}
    for question_id, question in questions.items():
        for result_set in question["result_sets"]:
            index[result_set["result_set_id"]] = (question_id, result_set)
    return index


def sql(query: str) -> list[dict]:
    """One read-only query as the demo role, for the independent multiplicity guards."""
    import json

    proc = subprocess.run(
        ["snow", "sql", "-c", "rai", "--role", ROLE, "--format", "json", "-q", query],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- structure


def test_output_schemas_match_the_frozen_manifest(uc1, questions):
    """The hardcoded column tuples and order clauses must equal the manifest's own.

    A drifted column list is the one failure mode that would make every other assertion in
    this file compare the wrong thing while still passing, so it is checked first.
    """
    for question_id, question in questions.items():
        declared = tuple(column["name"] for column in question["output_schema"])
        assert uc1.CATALOG[question_id]["columns"] == declared, question_id
        order_by = tuple(
            clause.split()[0] for clause in question["order_by"]
        )
        assert uc1.CATALOG[question_id]["order_by"] == order_by, question_id
        assert all(
            clause.endswith(" ASC") for clause in question["order_by"]
        ), f"{question_id} has a non-ASC order clause this module does not implement"


def test_frozen_row_ids_are_a_contiguous_ascending_run(uc1, questions):
    """``row_id`` is a supplied manifest label (D-0018), so the numbering itself is the check.

    Each function stamps ``<prefix>-R<n:0width>`` from ``row_id_start``. Two conventions are
    live at once: the v1.1.1 sets use ``<QID>-R<nnn>`` (``Q01-R001``) and every v1.2.0 set uses
    ``<RESULT_SET_ID>-R<nnnn>`` (``Q01-ENRICHED-MID-STORAGE-R0001``). Both are read off the
    manifest rather than hardcoded, and this test is what proves the read is faithful.
    """
    for question_id, question in questions.items():
        for result_set in question["result_sets"]:
            rows = result_set.get("rows") or []
            if not rows:
                continue
            base, prefix, width = uc1.row_id_convention(result_set, question_id)
            expected = [f"{prefix}-R{base + i:0{width}d}" for i in range(len(rows))]
            assert [row["row_id"] for row in rows] == expected, result_set["result_set_id"]
            assert prefix in (question_id, result_set["result_set_id"])


# ------------------------------------------------------------------- every frozen result set


def _all_result_set_ids() -> list[str]:
    """Every UC1 result set id, read from the manifest at collection time.

    Parametrising off the manifest rather than off a hardcoded list is deliberate: manifest
    v1.2.0 added thirteen result sets to Q01 to Q04 plus the whole of Q02F, and a hardcoded
    list would have gone on passing nine tests while silently covering none of them.
    """
    import yaml

    with (REPO_ROOT / "EXPECTED_ANSWERS.yaml").open(encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    from queries.uc1 import UC1_QUESTION_IDS

    return [
        result_set["result_set_id"]
        for question in manifest["questions"]
        if question["question_id"] in UC1_QUESTION_IDS
        for result_set in question["result_sets"]
    ]


@pytest.mark.parametrize("result_set_id", _all_result_set_ids())
def test_frozen_result_set_reproduced_exactly(uc1, result_sets, result_set_id):
    """The complete result set, cell by cell, in the frozen order. Every invocation."""
    question_id, result_set = result_sets[result_set_id]
    verdict, problems = uc1.run_result_set(question_id, result_set)
    assert verdict == "PASS", f"{result_set_id}: " + "; ".join(problems[:12])


# --------------------------------------------------------------------------- Q01 boundaries


def test_q01_before_first_is_no_recorded_state_not_outside_existence(uc1):
    """Aircraft 1004 at 2019-06-30: inside existence, before its first assignment.

    Existence runs from 2019-01-01 (AM-07) while the first eligible event is 2020-01-01, so all
    four dimensions are ``NO_RECORDED_STATE`` and every payload cell is null. Collapsing this
    into ``OUTSIDE_EXISTENCE`` - or into ``UNKNOWN_STATE`` - fails a different frozen result set
    in each direction, which is exactly why both cases are frozen.
    """
    frame = uc1.aircraft_as_of(1004, dt.date(2019, 6, 30))
    assert len(frame) == 1
    row = frame.iloc[0]
    assert [
        row["aircraft_state_status"],
        row["aircraft_type_status"],
        row["engine_type_status"],
        row["aircraft_status_status"],
    ] == ["NO_RECORDED_STATE"] * 4
    assert row["is_complete"] is False
    for column in (
        "aircraft_type_id",
        "aircraft_type",
        "engine_type_id",
        "engine_type",
        "engine_count",
        "mixed_engine_set_complete",
        "lifecycle_status",
        "registration_number",
        "base_airport_code_iata",
    ):
        assert row[column] is None, column


def test_q01_end_of_life_bound_is_exclusive(uc1):
    """Aircraft 1002 has ``existence_to = 2024-07-01``; D-0003 makes that bound exclusive.

    The day before is inside and resolves; the bound itself is outside. One character - ``<``
    versus ``<=`` in ``temporal.within_existence`` - decides this, and an inclusive bound would
    return four ``OK`` statuses and a plausible, wrong answer.
    """
    inside = uc1.aircraft_as_of(1002, dt.date(2024, 6, 30)).iloc[0]
    assert inside["aircraft_state_status"] == "OK"
    assert inside["aircraft_status_status"] == "OK"
    assert inside["registration_number"] == "SYN-REG-1002"

    on_bound = uc1.aircraft_as_of(1002, dt.date(2024, 7, 1)).iloc[0]
    assert [
        on_bound["aircraft_state_status"],
        on_bound["aircraft_type_status"],
        on_bound["engine_type_status"],
        on_bound["aircraft_status_status"],
    ] == ["OUTSIDE_EXISTENCE"] * 4
    assert on_bound["registration_number"] is None


def test_q01_unknown_gap_is_not_backfilled(uc1):
    """Aircraft 1002 at 2022-05-15: a covering assignment that resolves to nothing.

    The type and engine streams both have an assignment for 2022-05-01 to 2022-06-01 whose
    configuration did not resolve, so the answer is ``UNKNOWN_STATE`` with null definitions,
    while the state and status clocks are independently ``OK``. The aircraft *does* have a
    resolved ``SYN-TYPE-A`` assignment on either side of the gap; coalescing to it, or to the
    ``CURRENT_ONLY`` master fields under D-0005, would look more complete and be wrong.
    """
    row = uc1.aircraft_as_of(1002, dt.date(2022, 5, 15)).iloc[0]
    assert row["aircraft_type_status"] == "UNKNOWN_STATE"
    assert row["engine_type_status"] == "UNKNOWN_STATE"
    assert row["aircraft_state_status"] == "OK"
    assert row["aircraft_status_status"] == "OK"
    assert row["aircraft_type_id"] is None and row["aircraft_type"] is None
    assert row["engine_type_id"] is None and row["engine_count"] is None
    assert row["lifecycle_status"] == "Storage"
    assert row["base_airport_code_iata"] == "SEA"

    # the gap is real, not an artefact of the query: the same aircraft resolves on both sides
    assert uc1.aircraft_as_of(1002, dt.date(2022, 4, 30)).iloc[0]["aircraft_type_id"] == (
        "SYN-TYPE-A"
    )
    assert uc1.aircraft_as_of(1002, dt.date(2022, 7, 1)).iloc[0]["aircraft_type_id"] == (
        "SYN-TYPE-A"
    )


def test_q01_is_complete_only_when_all_four_dimensions_are_ok(uc1, result_sets):
    """One true among the four frozen OK-status result sets, and it is the canonical one."""
    complete = {}
    for result_set_id in (
        "Q01-CANONICAL",
        "Q01-BEFORE-FIRST",
        "Q01-UNKNOWN-GAP",
        "Q01-EOL-BOUNDARY",
    ):
        _, result_set = result_sets[result_set_id]
        row = result_set["rows"][0]
        complete[result_set_id] = row["is_complete"]
    assert complete == {
        "Q01-CANONICAL": True,
        "Q01-BEFORE-FIRST": False,
        "Q01-UNKNOWN-GAP": False,
        "Q01-EOL-BOUNDARY": False,
    }
    frame = uc1.aircraft_as_of(1001, dt.date(2026, 8, 31))
    assert bool(frame.iloc[0]["is_complete"]) is True


def test_q01_dv33_branches_are_mutually_exclusive_per_dimension(uc1):
    """Evaluate **every** branch for every dimension; exactly one must fire.

    The production path short-circuits at the first hit because the branches are mutually
    exclusive structurally. This test removes the short-circuit for the two cases where an
    overlap is plausible - the unknown gap, where ``OK`` and ``UNKNOWN_STATE`` once both fired
    because the negation was written as ``not_(ref.aircraft_type == AircraftType)`` and because
    an unscoped ref ranged over all four dimensions - and for the before-first case, where
    ``NO_RECORDED_STATE`` has to win against two present-row branches.
    """
    import aviation_model as am

    for aircraft_id, as_of, expected in (
        (1002, dt.date(2022, 5, 15), {
            am.DIM_AIRCRAFT_STATE: am.DV33_OK,
            am.DIM_AIRCRAFT_TYPE: am.DV33_UNKNOWN_STATE,
            am.DIM_ENGINE_TYPE: am.DV33_UNKNOWN_STATE,
            am.DIM_AIRCRAFT_STATUS: am.DV33_OK,
        }),
        (1004, dt.date(2019, 6, 30), {
            am.DIM_AIRCRAFT_STATE: am.DV33_NO_RECORDED_STATE,
            am.DIM_AIRCRAFT_TYPE: am.DV33_NO_RECORDED_STATE,
            am.DIM_ENGINE_TYPE: am.DV33_NO_RECORDED_STATE,
            am.DIM_AIRCRAFT_STATUS: am.DV33_NO_RECORDED_STATE,
        }),
    ):
        dimensions = uc1._q01_dimensions(f"exclusive_{aircraft_id}_{as_of:%Y%m%d}")
        for dimension in dimensions:
            token, _ = uc1._resolve_dimension(aircraft_id, dimension, as_of, strict=True)
            assert token == expected[dimension.name], (aircraft_id, as_of, dimension.name)


# --------------------------------------------------------------------------- Q02 boundaries


def test_q02_preserves_the_same_day_zero_duration_spell(uc1):
    """The 2020-06-01 spell exists only on the audit stream. This is the demo beat.

    Aircraft 1001 has four status observations on 2020-06-01 at row sequences 5, 10, 20 and 30.
    The daily projection keeps one row per aircraft, dimension and date, so on that stream the
    Storage observation at sequence 20 does not exist at all and this spell vanishes with no
    error. ``storage_days`` is 0 and ``same_day`` is true because dates plus source sequence
    establish order, not intraday elapsed time.
    """
    frame = uc1.status_reversion_spells(1001)
    assert len(frame) == 2
    same_day = frame[frame["same_day"].astype(bool)]
    assert len(same_day) == 1
    row = same_day.iloc[0]
    assert row["storage_event_id"] == 101010
    assert row["return_event_id"] == 101011
    assert row["storage_start_date"] == dt.date(2020, 6, 1)
    assert row["return_date"] == dt.date(2020, 6, 1)
    assert row["storage_start_sequence"] == 20
    assert row["return_sequence"] == 30
    assert row["storage_days"] == 0

    # and the daily projection really would lose it
    daily = sql(
        f"SELECT COUNT(*) AS N FROM {DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT "
        "WHERE AIRCRAFT_ID = 1001 AND DIMENSION = 'aircraft_status' "
        "AND VALID_FROM = '2020-06-01' AND AIRCRAFT_STATUS_CODE = 'Storage'"
    )
    assert int(daily[0]["N"]) == 0


def test_q02_keeps_repeated_a_b_a_as_three_assignments(uc1):
    """Two spells for one aircraft, so the status value repeats globally and must not collapse.

    Aircraft 1001's status stream is In Service, Storage, In Service, ..., Storage, In Service.
    Consecutive equality is suppressed upstream but global equality is not, so both reversions
    survive. Any ``distinct()`` on the watched status, or any "collapse repeated states" step,
    would delete the later In Service observations and return one row or none.
    """
    frame = uc1.status_reversion_spells(1001)
    assert len(frame) == 2
    assert list(frame["storage_event_id"]) == [101003, 101010]
    assert list(frame["storage_start_date"]) == [dt.date(2018, 3, 1), dt.date(2020, 6, 1)]
    assert list(frame["storage_days"]) == [45, 0]
    assert [bool(x) for x in frame["same_day"]] == [False, True]

    # Two spells need at least three In Service observations on the audit stream: the one
    # before the first Storage, the return that is also the run-up to the second, and the
    # second return. The bound is ``>=`` and not ``==`` deliberately - the exact count is
    # fixture-dependent (it was 3 before the D-0023 enrichment and is 4 after) while the claim
    # under test, that a globally repeated status value is not collapsed, is not.
    ordinals = sql(
        f"SELECT COUNT(*) AS N FROM {DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT "
        "WHERE AIRCRAFT_ID = 1001 AND DIMENSION = 'aircraft_status' "
        "AND AIRCRAFT_STATUS_CODE = 'In Service'"
    )
    assert int(ordinals[0]["N"]) >= 3


def test_q02_empty_is_an_answer(uc1):
    """Aircraft 1004 never leaves Maintenance. Zero rows, full schema, no filler.

    An empty RAI result is a zero-*column* DataFrame (PROBE D11), so the declared columns have
    to be supplied by the query module rather than read off the returned frame - otherwise a
    downstream ``df["storage_days"]`` raises ``KeyError`` instead of yielding an empty column.
    """
    frame = uc1.status_reversion_spells(1004)
    assert len(frame) == 0
    assert list(frame.columns) == list(uc1.Q02_COLUMNS)


def test_q02_pairing_agrees_with_the_sql_oracle_fleet_wide(uc1):
    """The pairing rule must not over- or under-count outside the anchored aircraft.

    ``status_reversion_spells`` pairs each Storage with the *minimal* later In Service, which is
    the question's "next qualifying" wording; ``q02_status_reversion_spells.sql`` uses ``LEAD``,
    which additionally requires the *immediate* successor to be In Service. The two semantics
    can differ in principle, so this asserts they do not differ on this fixture, and it does so
    fleet-wide through Q02F rather than by looping RAI over several hundred aircraft.
    """
    rows = sql(
        f"""
        WITH s AS (
          SELECT AIRCRAFT_ID, DIMENSION_SEQUENCE AS D, AIRCRAFT_STATUS_CODE AS ST
          FROM {DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT
          WHERE DIMENSION = 'aircraft_status'
        ), w AS (
          SELECT s.*,
                 LAG(ST)  OVER (PARTITION BY AIRCRAFT_ID ORDER BY D) AS PREV,
                 LEAD(ST) OVER (PARTITION BY AIRCRAFT_ID ORDER BY D) AS NXT
          FROM s
        )
        SELECT COUNT_IF(PREV = 'In Service' AND ST = 'Storage'
                        AND NXT = 'In Service') AS LEAD_SPELLS,
               (SELECT COUNT(*) FROM (
                  SELECT (SELECT MIN(r.D) FROM s r
                          WHERE r.AIRCRAFT_ID = st.AIRCRAFT_ID AND r.D > st.D
                            AND r.ST = 'In Service') AS RET
                  FROM w st
                  WHERE st.PREV = 'In Service' AND st.ST = 'Storage'
                ) x WHERE x.RET IS NOT NULL) AS MIN_LATER_SPELLS
        FROM w
        """
    )
    assert int(rows[0]["LEAD_SPELLS"]) == int(rows[0]["MIN_LATER_SPELLS"]) == 439


# --------------------------------------------------------------------------- Q03 boundaries


def test_q03_has_132_rows_over_120_distinct_month_ends(uc1):
    """One query, a joined calendar, 120 distinct dates, 132 nonzero cells.

    240 cells are possible over 120 month ends and two types; the manifest omits the 108 zeros
    and so does the inner join. No ``| 0``, no completed grid.
    """
    frame = uc1.month_end_fleet_composition(dt.date(2015, 1, 31), dt.date(2024, 12, 31))
    assert len(frame) == 132
    assert frame["month_end"].nunique() == 120
    assert sorted(frame["aircraft_type_id"].unique()) == ["SYN-TYPE-A", "SYN-TYPE-B"]
    assert sorted(set(frame["in_service_aircraft_count"])) == [1, 2]
    assert frame["month_end"].iloc[0] == dt.date(2015, 1, 31)
    assert frame["month_end"].iloc[-1] == dt.date(2024, 12, 31)
    assert all(isinstance(value, dt.date) for value in frame["month_end"])


def test_q03_month_ends_are_real_and_irregularly_spaced(uc1):
    """Every returned date is the true last day of its month, and the gaps are not constant.

    This is the test that fails if the calendar was derived by adding 30 or 31 days, or by
    ``date + n * interval``. February appears as 28 and, in the four leap years of the window,
    as 29 - which no fixed-step arithmetic produces.
    """
    frame = uc1.month_end_fleet_composition(dt.date(2015, 1, 31), dt.date(2024, 12, 31))
    dates = sorted(set(frame["month_end"]))
    assert len(dates) == 120
    for value in dates:
        following = value + dt.timedelta(days=1)
        assert following.day == 1, f"{value} is not a month end"
    gaps = {(b - a).days for a, b in zip(dates, dates[1:])}
    assert gaps == {28, 29, 30, 31}, gaps
    assert dt.date(2016, 2, 29) in dates
    assert dt.date(2015, 2, 28) in dates


def test_q03_window_narrows_with_the_parameters(uc1):
    """The bounds are query parameters against the joined calendar, not a hardcoded decade.

    A 2020 window must return 2020's month ends only, which also proves the same query shape
    answers an arbitrary sub-calendar rather than the frozen ten years.
    """
    frame = uc1.month_end_fleet_composition(dt.date(2020, 1, 31), dt.date(2020, 12, 31))
    assert frame["month_end"].nunique() == 12
    assert min(frame["month_end"]) == dt.date(2020, 1, 31)
    assert max(frame["month_end"]) == dt.date(2020, 12, 31)
    assert dt.date(2020, 2, 29) in set(frame["month_end"])


def test_q03_multiplicity_gate_holds_so_the_count_cannot_inflate(uc1):
    """Binding two assignment streams through one shared ``Aircraft`` inflates counts silently.

    The product is intended here, but only because at most one assignment per
    (aircraft, dimension, date) can cover a given date. If that gate ever regresses this query
    over-counts with no error and the failure surfaces three phases downstream, so it is
    asserted independently in SQL over the whole daily stream rather than inferred from the
    answer being right today.
    """
    overlaps = sql(
        f"""
        SELECT COUNT(*) AS N FROM (
          SELECT a.DIMENSION, a.AIRCRAFT_ID, COUNT(*) AS C
          FROM {DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT a
          JOIN {DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT b
            ON b.DIMENSION = a.DIMENSION AND b.AIRCRAFT_ID = a.AIRCRAFT_ID
           AND b.DAILY_ASSIGNMENT_ID <> a.DAILY_ASSIGNMENT_ID
           AND b.VALID_FROM < a.VALID_TO AND a.VALID_FROM < b.VALID_TO
          GROUP BY 1, 2
        )
        """
    )
    assert int(overlaps[0]["N"]) == 0


# --------------------------------------------------------------------------- Q04 boundaries


def test_q04_streams_are_independent_and_never_aligned(uc1):
    """Four rows. The type break at 2019-01-01 never appears in the engine stream, and vice versa.

    Any merge of the two timelines - an overlap join, a full outer join, an "as-of both"
    reconstruction - produces three, five or six rows. Four is the signature of leaving them
    alone.
    """
    frame = uc1.type_engine_histories(1001)
    assert len(frame) == 4
    assert list(frame["dimension"]) == [
        "aircraft_type",
        "aircraft_type",
        "engine_type",
        "engine_type",
    ]
    type_bounds = set(frame[frame["dimension"] == "aircraft_type"]["valid_from"])
    engine_bounds = set(frame[frame["dimension"] == "engine_type"]["valid_from"])
    assert dt.date(2019, 1, 1) in type_bounds
    assert dt.date(2021, 7, 1) in engine_bounds
    assert dt.date(2019, 1, 1) not in engine_bounds
    assert dt.date(2021, 7, 1) not in type_bounds
    assert list(frame["assignment_id"]) == [
        "aircraft_type|1001|2015-01-01|101001",
        "aircraft_type|1001|2019-01-01|101005",
        "engine_type|1001|2015-01-01|101001",
        "engine_type|1001|2021-07-01|101007",
    ]


def test_q04_is_type_change_is_three_valued(uc1):
    """``false`` on the first type assignment, ``true`` on the change, null on every engine row.

    Null and ``false`` are different answers: ``is_type_change`` is not defined for the engine
    stream at all, and a ``| False`` fallback would turn two frozen nulls into two wrong cells.
    """
    frame = uc1.type_engine_histories(1001)
    values = list(frame["is_type_change"])
    assert values[0] is False
    assert values[1] is True
    assert values[2] is None and values[3] is None
    assert list(frame["previous_definition_id"]) == [
        None,
        "SYN-TYPE-A",
        None,
        "SYN-ENGINE-A",
    ]


def test_q04_payload_sits_on_the_assignment_not_the_definition(uc1):
    """``engine_count`` and ``mixed_engine_set_complete`` are assignment-level; type rows are null.

    Asserting one engine count per engine subseries identity would be wrong in the domain, and
    only accidentally functional in this fixture. ``mixed_engine_set_complete`` is also not
    ``has_multiple_engine_types``: the exact mixed set is unsupported by the supplied schema and
    is never fabricated.
    """
    frame = uc1.type_engine_histories(1001)
    type_rows = frame[frame["dimension"] == "aircraft_type"]
    engine_rows = frame[frame["dimension"] == "engine_type"]
    assert list(type_rows["engine_count"]) == [None, None]
    assert list(type_rows["mixed_engine_set_complete"]) == [None, None]
    assert list(engine_rows["engine_count"]) == [2, 2]
    assert [bool(x) for x in engine_rows["mixed_engine_set_complete"]] == [True, True]
    assert list(frame["definition_id"]) == [
        "SYN-TYPE-A",
        "SYN-TYPE-B",
        "SYN-ENGINE-A",
        "SYN-ENGINE-B",
    ]
    assert list(frame["definition_label"]) == [
        "Synthetic narrowbody A",
        "Synthetic narrowbody B",
        "Synthetic turbofan A",
        "Synthetic turbofan B",
    ]


def test_q04_open_interval_uses_the_model_sentinel(uc1):
    """Open intervals end at the model sentinel ``9999-01-01``, never the source ``9999-12-31``.

    The two are different facts and never collapse: the source value means "unknown future" and
    DATA-04 normalises it away before RAI sees it. ``9999-01-01`` is also past
    ``pandas.Timestamp.max``, which is why the date normalisation is element-wise rather than a
    vectorised ``pd.to_datetime``.
    """
    frame = uc1.type_engine_histories(1001)
    open_bounds = [value for value in frame["valid_to"] if value.year == 9999]
    assert open_bounds == [dt.date(9999, 1, 1), dt.date(9999, 1, 1)]
    assert dt.date(9999, 12, 31) not in set(frame["valid_to"])


# --------------------------------------------------------------------------- parameters


def test_invalid_aircraft_id_raises_the_frozen_error_code(uc1):
    """``Q01-INVALID-AIRCRAFT-ID`` - validation fires before any query reaches the engine."""
    with pytest.raises(uc1.QueryParameterError) as excinfo:
        uc1.aircraft_as_of(-1, dt.date(2026, 8, 31))
    assert excinfo.value.error_code == "INVALID_AIRCRAFT_ID"
    assert excinfo.value.invocation_status == "PARAMETER_ERROR"

    for bad in (None, 0, -1, "not-a-number", 12.5, True):
        for call in (uc1.aircraft_as_of, uc1.status_reversion_spells, uc1.type_engine_histories):
            with pytest.raises(uc1.QueryParameterError) as excinfo:
                if call is uc1.aircraft_as_of:
                    call(bad, dt.date(2026, 8, 31))
                else:
                    call(bad)
            assert excinfo.value.error_code == "INVALID_AIRCRAFT_ID", (call, bad)


def test_invalid_q01_date_and_q03_parameters_are_rejected(uc1):
    with pytest.raises(uc1.QueryParameterError):
        uc1.aircraft_as_of(1001, None)
    with pytest.raises(uc1.QueryParameterError):
        uc1.aircraft_as_of(1001, "not-a-date")
    with pytest.raises(uc1.QueryParameterError):
        uc1.month_end_fleet_composition(None, dt.date(2024, 12, 31))
    with pytest.raises(uc1.QueryParameterError):
        uc1.month_end_fleet_composition(dt.date(2015, 1, 31), dt.date(2024, 12, 31), "Storage")
    with pytest.raises(uc1.QueryParameterError):
        uc1.month_end_fleet_composition(dt.date(2024, 12, 31), dt.date(2015, 1, 31))


def test_iso_string_parameters_are_accepted(uc1):
    """The catalog layer hands raw ISO strings through; both forms must agree."""
    from_date = uc1.aircraft_as_of(1001, "2026-08-31")
    from_object = uc1.aircraft_as_of(1001, dt.date(2026, 8, 31))
    assert from_date.equals(from_object)


def test_state_and_status_dimensions_have_no_unresolved_rows(uc1):
    """Guards the one mapping asymmetry in Q01's four dimensions.

    ``aircraft_type`` and ``engine_type`` resolve to a definition entity, so DV-33 can tell
    ``OK`` from ``UNKNOWN_STATE`` by negating that link's existence. ``aircraft_state`` has no
    exact target to negate at all: AH-17 and AH-25 are plain strings and the contract resolved
    no ``Airport`` for the base IATA code, so ``uc1`` passes no ``exact_target`` for it and a
    present state row is always reported ``OK``.

    That is correct against the data as it stands - ``DIMENSION_QUERY_STATUS`` is ``OK`` on all
    1,004 state rows and all 1,003 status rows, with ``UNKNOWN_STATE`` confined to the two type
    rows and the two engine rows. It is *not* correct in general, so this asserts the premise
    rather than trusting it: if the loader ever emits an unresolved state or status row, this
    goes red and names the work, instead of Q01 quietly reporting ``OK`` for a gap.
    """
    rows = sql(
        f"SELECT DIMENSION, DIMENSION_QUERY_STATUS AS ST, COUNT(*) AS N "
        f"FROM {DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT "
        "GROUP BY 1, 2 ORDER BY 1, 2"
    )
    observed = {(row["DIMENSION"], row["ST"]): int(row["N"]) for row in rows}
    unresolved = {
        key: count
        for key, count in observed.items()
        if key[0] in ("aircraft_state", "aircraft_status") and key[1] != "OK"
    }
    assert unresolved == {}, (
        "aircraft_state / aircraft_status now carry a non-OK DIMENSION_QUERY_STATUS; "
        "Q01 needs an exact_target or an explicit status branch for them: " + repr(unresolved)
    )
    assert observed[("aircraft_type", "UNKNOWN_STATE")] == 2
    assert observed[("engine_type", "UNKNOWN_STATE")] == 2
