"""test_rotation.py - QUERY-ROT live gate for Q08 ``actual_rotation_enriched``.

Every test here executes against the live ``PK_AVIATION_TEMPORAL`` model under
``RAI_DEMO_AVIATION_TEMPORAL`` on the ``aviation_temporal_logic_s`` reasoner. Nothing is mocked
and nothing is asserted from a producer's claim: an import that succeeds is not a chain that
reconstructs.

Run with a warm engine::

    .venv/bin/rai reasoners resume --type Logic --name aviation_temporal_logic_s --wait
    PYTHONPATH=rai_code TERM=dumb .venv/bin/python -m pytest tests/test_rotation.py -q

The file is organised by what each group defends against, and the groups exist because the
failure they catch is a *plausible wrong answer* rather than an error:

1. The three frozen result sets, compared as complete ordered sequences.
2. The chain is a chain: same aircraft, non-decreasing time, no self-loop, no cycle, one segment
   head per leg.
3. It is a traversal and not a filter plus a sort. Aircraft 1100 is the discriminator: seven legs
   in strictly increasing time order that a sort would number 1..7 in one segment, and that the
   link structure correctly reports as seven singleton segments.
4. The diversion trap. Flight 7200 landed at LAS with LAX on the plan, and aircraft 1100's leg
   5103 departs LAX at exactly 7200's arrival minute. Chaining on the planned arrival would join
   them; chaining on the actual arrival does not.
5. Cancellation, missing time and broken links stay visible as typed anomalies rather than
   vanishing from the answer.
6. Per-leg enrichment is the shared as-of resolution on AF-06, scoped per dimension.
7. Typed parameter validation and the frozen error code.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rai_code"))

from queries import rotation  # noqa: E402

pytestmark = pytest.mark.live

CANONICAL_AIRCRAFT = 1001
ANOMALY_AIRCRAFT = 1099
DIVERSION_AIRCRAFT = 1100
OTHER_AIRCRAFT = 1098
SELECTED_DAY = dt.date(2026, 8, 31)
UTC_DAY = dt.date(2026, 9, 1)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="session")
def am():
    """The loaded ontology package. One ``Model`` per process, deliberately (PROBE N-02).

    ``warm_model`` takes the shared-model write-lock collision here rather than inside whichever
    test runs first. Importing a query module is a write transaction on ``aviation_temporal``, and
    a concurrent read fails outright rather than queueing - it arrives as
    ``SnowflakeTableObjectsException: Getting the following table failed with the error in
    Snowflake``, with ``model is currently locked by active write transaction(s)`` only in the
    debug span. Without this, a sibling agent's install fails one arbitrary test case and the
    failure reads like a query defect.
    """
    import aviation_model

    return rotation.warm_model(aviation_model)


@pytest.fixture(scope="session")
def manifest() -> dict:
    """Q08 straight out of ``EXPECTED_ANSWERS.yaml``. FROZEN; this file only reads it."""
    with (REPO_ROOT / "EXPECTED_ANSWERS.yaml").open() as handle:
        loaded = yaml.safe_load(handle)
    return next(q for q in loaded["questions"] if q["question_id"] == "Q08")


@pytest.fixture(scope="session")
def canonical(am) -> pd.DataFrame:
    return rotation.actual_rotation_enriched(
        CANONICAL_AIRCRAFT, SELECTED_DAY, am=am, row_id_start=1
    )


@pytest.fixture(scope="session")
def anomalies(am) -> pd.DataFrame:
    return rotation.actual_rotation_enriched(
        ANOMALY_AIRCRAFT, SELECTED_DAY, am=am, row_id_start=4
    )


@pytest.fixture(scope="session")
def evidence(am) -> pd.DataFrame:
    return rotation.rotation_anomaly_evidence(am, ANOMALY_AIRCRAFT, SELECTED_DAY)


@pytest.fixture(scope="session")
def diverted(am) -> pd.DataFrame:
    return rotation.actual_rotation_enriched(
        DIVERSION_AIRCRAFT, SELECTED_DAY, am=am, row_id_start=1
    )


def legs_only(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["row_kind"] == rotation.ROW_KIND_LEG].reset_index(drop=True)


def anomalies_only(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["row_kind"] == rotation.ROW_KIND_ANOMALY].reset_index(drop=True)


def row_for(frame: pd.DataFrame, flight_id: int) -> pd.Series:
    match = frame[frame["flight_id"] == flight_id]
    assert len(match) == 1, f"expected exactly one row for flight {flight_id}, got {len(match)}"
    return match.iloc[0]


# ----------------------------------------------- 1. the three frozen result sets, complete


def test_manifest_shape_is_what_this_module_targets(manifest):
    """The frozen contract this file asserts against, restated so a manifest change is loud."""
    assert [column["name"] for column in manifest["output_schema"]] == list(
        rotation.OUTPUT_COLUMNS
    )
    assert manifest["order_by"] == [
        "segment_id ASC",
        "row_kind DESC",
        "leg_order ASC NULLS LAST",
        "flight_id ASC",
        "anomaly_code ASC NULLS LAST",
    ]
    assert [rs["result_set_id"] for rs in manifest["result_sets"]] == [
        "Q08-CANONICAL",
        "Q08-ANOMALIES",
        "Q08-NOT-FOUND",
        "Q08-ENRICHED-ROTATION",
        "Q08-ENRICHED-ANOMALIES",
        "Q08-ENRICHED-CLEAN",
    ]
    assert [rs["expected_cardinality"] for rs in manifest["result_sets"]] == [
        3,
        11,
        0,
        5,
        11,
        4,
    ]


@pytest.mark.parametrize(
    "result_set_id",
    [
        "Q08-CANONICAL",
        "Q08-ANOMALIES",
        "Q08-NOT-FOUND",
        "Q08-ENRICHED-ROTATION",
        "Q08-ENRICHED-ANOMALIES",
        "Q08-ENRICHED-CLEAN",
    ],
)
def test_every_frozen_result_set_is_reproduced_exactly(am, result_set_id):
    """Every Q08 result set, v1.1.1 and v1.2.0 alike, cell for cell and in the frozen order.

    The v1.2.0 sets label their rows with a different ``row_id`` template
    (``Q08-ENRICHED-CLEAN-R0001`` rather than ``Q08-R001``). ``row_id`` is a supplied manifest
    label under D-0021, so :func:`rotation.row_id_label_format` reads that template off the
    expected rows; every other one of the sixteen columns is compared without being told anything.
    """
    frozen = next(
        rs for rs in rotation.frozen_result_sets() if rs["result_set_id"] == result_set_id
    )
    prefix, width, start = rotation.row_id_label_format(frozen)
    outcome = rotation.retry_on_model_lock(
        lambda: rotation.invoke(
            frozen["parameters"]["aircraft_id"],
            frozen["parameters"]["flight_departure_date"],
            am=am,
            row_id_start=start,
            row_id_prefix=prefix,
            row_id_width=width,
        )
    )
    assert outcome.invocation_status == frozen["invocation_status"]
    assert outcome.error_code == frozen["error_code"]
    assert list(outcome.rows.columns) == list(rotation.OUTPUT_COLUMNS)
    assert len(outcome.rows) == frozen["expected_cardinality"]
    assert rotation.diff_rows(rotation.canonical_rows(outcome.rows), frozen["rows"]) == []
    # No shipped result set touches a beyond-vocabulary anomaly class; if one ever does, the
    # comparison above would still pass while the SQL oracle silently disagreed.
    assert outcome.beyond_manifest_anomaly_classes == ()


def test_target_not_operated_is_emitted_and_flagged_not_silently_dropped(am):
    """D-0020 A5's twelfth class is real in the enriched universe and must never be quiet.

    Flight 5310 (aircraft 1225, 2027-06-24) points at 5311, which is itself cancelled, so
    ``MODEL_INPUT`` rejects the link as ``TARGET_NOT_OPERATED``. The class is outside the
    manifest's eleven-class DV-25 vocabulary and the independent SQL oracle has no branch for it,
    so this selection is exactly where a conformance harness would diverge. The row is emitted -
    ``is_accepted_link`` is false, so the chain genuinely stops there - and the divergence is
    reported rather than absorbed.
    """
    outcome = rotation.invoke(1225, dt.date(2027, 6, 24), am=am)
    assert outcome.invocation_status == "OK"
    assert outcome.beyond_manifest_anomaly_classes == ("TARGET_NOT_OPERATED",)

    flagged = outcome.rows[outcome.rows["anomaly_code"] == "TARGET_NOT_OPERATED"]
    assert list(flagged["flight_id"]) == [5310]
    assert list(flagged["row_kind"]) == [rotation.ROW_KIND_ANOMALY]
    assert list(flagged["link_outcome"]) == ["REJECTED"]

    # The refused link ends its segment; 5312 starts a new one rather than being absorbed.
    legs = legs_only(outcome.rows)
    assert sorted(zip(legs["flight_id"], legs["leg_order"])) == [
        (5309, 1),
        (5310, 2),
        (5312, 1),
    ]
    assert outcome.rows[outcome.rows["flight_id"] == 5311]["anomaly_code"].tolist() == [
        "CANCELLED"
    ]


def test_q08_canonical_is_the_complete_frozen_result_set(canonical):
    """``Q08-CANONICAL``: all 3 rows, all 16 columns, in the frozen order. No column excluded."""
    frozen = next(
        rs for rs in rotation.frozen_result_sets() if rs["result_set_id"] == "Q08-CANONICAL"
    )
    assert list(canonical.columns) == list(rotation.OUTPUT_COLUMNS)
    assert rotation.diff_rows(rotation.canonical_rows(canonical), frozen["rows"]) == []


def test_q08_anomalies_is_the_complete_frozen_result_set(anomalies):
    """``Q08-ANOMALIES``: all 11 rows, zero ``LEG`` rows, one row per DV-25 class."""
    frozen = next(
        rs for rs in rotation.frozen_result_sets() if rs["result_set_id"] == "Q08-ANOMALIES"
    )
    assert list(anomalies.columns) == list(rotation.OUTPUT_COLUMNS)
    assert rotation.diff_rows(rotation.canonical_rows(anomalies), frozen["rows"]) == []
    assert len(legs_only(anomalies)) == 0
    assert len(set(anomalies["anomaly_code"])) == 11


def test_q08_not_found_raises_the_frozen_error_code(am):
    """``Q08-NOT-FOUND``: aircraft 1999 exists and flew in 2040, so the selected day is empty."""
    with pytest.raises(rotation.RotationNotFound) as raised:
        rotation.actual_rotation_enriched(1999, SELECTED_DAY, am=am)
    assert raised.value.error_code == "NO_ACTUAL_FLIGHTS"
    assert raised.value.invocation_status == "NOT_FOUND"

    outcome = rotation.invoke(1999, SELECTED_DAY, am=am)
    assert outcome.invocation_status == "NOT_FOUND"
    assert outcome.error_code == "NO_ACTUAL_FLIGHTS"
    # An empty RAI result is a zero-COLUMN frame (PROBE D11); the catalog shape supplies the
    # declared columns itself so a caller can still index them.
    assert list(outcome.rows.columns) == list(rotation.OUTPUT_COLUMNS)
    assert len(outcome.rows) == 0


def test_emitted_order_equals_the_frozen_order_by(canonical, anomalies, diverted):
    """The sequence is constructed from the traversal, and it already satisfies the frozen sort.

    Ordering is not applied to the answer; it falls out of the construction. Sorting each frame
    independently by the declared keys must therefore be a no-op, which is the cheap proof that
    the two agree.
    """
    for frame in (canonical, anomalies, diverted):
        resorted = frame.sort_values(
            ["segment_id", "row_kind", "leg_order", "flight_id", "anomaly_code"],
            ascending=[True, False, True, True, True],
            na_position="last",
            kind="stable",
        ).reset_index(drop=True)
        assert list(resorted["row_id"]) == list(frame["row_id"])


# --------------------------------------------------- 2. the chain really is a chain


def test_same_aircraft_continuity(am, canonical):
    """Every leg in the chain was flown by the parameter aircraft, and the rule is enforced.

    The positive half is the answer itself; the negative half is flight 8105, whose AF-20 points
    at 8205. 8205 departs from 8105's actual arrival airport at a valid time, so it would chain
    on endpoints and clock alone, and it belongs to a **different** aircraft. The link is
    ``DIFFERENT_AIRCRAFT`` and the chain stops.
    """
    flights = [int(x) for x in canonical["flight_id"]]
    owners = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.Aircraft.id.alias("aircraft_id"),
        )
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.AircraftFlight.flight_departure_date == SELECTED_DAY,
            am.Aircraft.id == CANONICAL_AIRCRAFT,
        )
        .to_df()
    )
    assert sorted(int(x) for x in owners["flight_id"]) == sorted(flights)
    assert set(int(x) for x in owners["aircraft_id"]) == {CANONICAL_AIRCRAFT}

    link = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.AircraftFlight.next_flight_id.alias("next_flight_id"),
            am.Aircraft.id.alias("aircraft_id"),
        )
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.AircraftFlight.flight_id == 8205,
        )
        .to_df()
    )
    assert int(link.iloc[0]["aircraft_id"]) == OTHER_AIRCRAFT != ANOMALY_AIRCRAFT
    different = row_for(anomalies_only(rotation.actual_rotation_enriched(
        ANOMALY_AIRCRAFT, SELECTED_DAY, am=am, row_id_start=4
    )), 8105)
    assert different["anomaly_code"] == "DIFFERENT_AIRCRAFT"
    assert int(different["next_flight_id"]) == 8205
    assert different["link_outcome"] == "REJECTED"


def test_time_is_non_decreasing_along_the_traversal(canonical):
    """Leg n+1 departs no earlier than leg n arrives, in the order the traversal produced."""
    legs = legs_only(canonical)
    assert [int(x) for x in legs["leg_order"]] == list(range(1, len(legs) + 1))
    departures = list(legs["actual_departure_utc"])
    arrivals = list(legs["actual_arrival_utc"])
    for index in range(len(legs) - 1):
        assert departures[index + 1] >= arrivals[index], (
            f"leg {index + 2} departs before leg {index + 1} arrives"
        )
        assert arrivals[index] >= departures[index]


def test_no_self_loop_and_no_cycle_in_the_answer(am, canonical, anomalies):
    """A leg never points at itself, and no leg reaches itself over the accepted edge.

    Cycle detection is scoped to the reconstructed per-aircraft, per-day chain (D-0022), so the
    closure is read back for exactly the selected legs. ``hops = 0`` is the reflexive base case;
    any pair with ``from == to`` and ``hops > 0`` would be a cycle inside the accepted edge set.
    """
    for frame in (canonical, anomalies):
        legs = legs_only(frame)
        for _, row in legs.iterrows():
            if row["next_flight_id"] is not pd.NA and not pd.isna(row["next_flight_id"]):
                assert int(row["next_flight_id"]) != int(row["flight_id"])
        assert len(set(legs["flight_id"])) == len(legs)

    other = am.AircraftFlight.ref("closure_target")
    for aircraft_id in (CANONICAL_AIRCRAFT, ANOMALY_AIRCRAFT):
        pairs = (
            am.model.select(
                am.AircraftFlight.flight_id.alias("from_flight_id"),
                other.flight_id.alias("to_flight_id"),
                am.rotation_leg_distance(am.AircraftFlight, other).alias("hops"),
            )
            .where(
                am.AircraftFlight.aircraft == am.Aircraft,
                am.Aircraft.id == aircraft_id,
                am.AircraftFlight.flight_departure_date == SELECTED_DAY,
                am.rotation_leg_distance(am.AircraftFlight, other),
            )
            .to_df()
        )
        loops = pairs[
            (pairs["from_flight_id"] == pairs["to_flight_id"]) & (pairs["hops"].map(int) > 0)
        ]
        assert loops.empty, f"aircraft {aircraft_id} reaches itself: {loops.to_dict('records')}"

    # The self-loop and the cycle are still reported, as their own classes and not as each other.
    assert row_for(anomalies_only(anomalies), 8101)["anomaly_code"] == "SELF_LOOP"
    assert int(row_for(anomalies_only(anomalies), 8101)["next_flight_id"]) == 8101
    assert row_for(anomalies_only(anomalies), 8102)["anomaly_code"] == "CYCLE"


def test_one_cycle_row_per_component_with_every_member_retained(evidence, anomalies):
    """8102 and 8103 form one cycle. One output row, anchored at the minimum flight id.

    Emitting one row per member would give 12 anomaly rows instead of 11, and dropping 8103
    outright would lose the evidence. Both halves are asserted here.
    """
    members = evidence[evidence["anomaly_code"] == "CYCLE"]
    assert sorted(int(x) for x in members["flight_id"]) == [8102, 8103]
    assert set(int(x) for x in members["cycle_component_id"]) == {8102}
    representatives = members[members["is_cycle_representative"].map(bool)]
    assert [int(x) for x in representatives["flight_id"]] == [8102]
    assert int(representatives.iloc[0]["flight_id"]) == min(
        int(x) for x in members["flight_id"]
    )

    emitted = anomalies_only(anomalies)
    assert [int(x) for x in emitted[emitted["anomaly_code"] == "CYCLE"]["flight_id"]] == [8102]
    assert 8103 not in set(int(x) for x in emitted["flight_id"])
    assert len(evidence) == 12 and len(emitted) == 11


def test_every_leg_has_exactly_one_segment_head(am, canonical, diverted):
    """One segment head per leg, so ``leg_order`` cannot double-count.

    ``accepted_next_flight`` is a ``Property``, so a leg has at most one accepted successor; the
    risk is on the inbound side, where two legs accepting the same target would make it reachable
    from two heads. The assembly raises ``RotationInvariantError`` if that ever happens; this test
    proves it does not today, in both a chained and an unchained day.
    """
    for frame in (canonical, diverted):
        legs = legs_only(frame)
        for segment_id, group in legs.groupby("segment_id"):
            positions = sorted(int(x) for x in group["leg_order"])
            assert positions == list(range(1, len(group) + 1)), segment_id

    heads = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.AircraftFlight.accepted_next_flight.flight_id.alias("next_flight_id"),
        )
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.Aircraft.id == CANONICAL_AIRCRAFT,
            am.AircraftFlight.flight_departure_date == SELECTED_DAY,
        )
        .to_df()
    )
    accepted_targets = [
        int(x) for x in heads["next_flight_id"] if not pd.isna(x)
    ]
    assert sorted(accepted_targets) == [8002, 8003]
    assert len(accepted_targets) == len(set(accepted_targets))


# ------------------------------- 3. a traversal, not a filter and a sort


def test_leg_order_comes_from_the_link_structure_not_the_clock(am, diverted):
    """Aircraft 1100 is the discriminator between the two implementations.

    Its seven legs on 2026-08-31 have strictly ordered actual times and not one accepted link
    between them. Sorting by ``actual_gate_departure_time_utc`` and numbering would return one
    segment with ``leg_order`` 1 to 7. The link structure returns seven singleton segments, each
    ``TERMINAL_NO_TARGET`` at ``leg_order`` 1, which is the true answer: the aircraft's day is
    seven unlinked observations, not a reconstructed rotation.
    """
    legs = legs_only(diverted)
    assert len(legs) == 7
    assert set(int(x) for x in legs["leg_order"]) == {1}
    assert len(set(legs["segment_id"])) == 7
    assert set(legs["link_outcome"]) == {"TERMINAL_NO_TARGET"}
    assert all(pd.isna(x) for x in legs["next_flight_id"])

    # And the time order that a sort would have used really is non-degenerate here.
    times = sorted(legs["actual_departure_utc"])
    assert times[0] < times[-1]

    # The canonical chain, by contrast, has real accepted links behind its ordering.
    edges = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.AircraftFlight.accepted_next_flight.flight_id.alias("next_flight_id"),
        )
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.Aircraft.id == CANONICAL_AIRCRAFT,
            am.AircraftFlight.flight_departure_date == SELECTED_DAY,
        )
        .to_df()
        .sort_values("flight_id")
    )
    assert [
        None if pd.isna(x) else int(x) for x in edges["next_flight_id"]
    ] == [8002, 8003, None]


def test_selection_is_the_local_date_and_not_the_utc_date(am, canonical):
    """AF-06 selects the day. AF-07 and the UTC gate times are one day later and select nothing.

    ``TT-US-CLOCK-AUTHORITY`` row ``TTUS-R05`` freezes this: AF-06 2026-08-31 with AF-07
    2026-09-01, selected day 2026-08-31. Asking for 2026-09-01 must therefore be ``NOT_FOUND``
    for this aircraft, which an AF-07-based or AF-13-derived selection would answer with the same
    three legs.
    """
    clocks = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.AircraftFlight.flight_departure_date.alias("af06_local"),
            am.AircraftFlight.flight_departure_date_utc.alias("af07_utc"),
        )
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.Aircraft.id == CANONICAL_AIRCRAFT,
            am.AircraftFlight.flight_departure_date == SELECTED_DAY,
        )
        .to_df()
    )
    # RAI Date values arrive as pandas Timestamp, so normalise or the comparison is vacuous.
    assert set(pd.to_datetime(clocks["af06_local"]).dt.date) == {SELECTED_DAY}
    assert set(pd.to_datetime(clocks["af07_utc"]).dt.date) == {UTC_DAY}
    assert set(pd.to_datetime(canonical["actual_departure_utc"]).dt.date) == {UTC_DAY}

    with pytest.raises(rotation.RotationNotFound) as raised:
        rotation.actual_rotation_enriched(CANONICAL_AIRCRAFT, UTC_DAY, am=am)
    assert raised.value.error_code == "NO_ACTUAL_FLIGHTS"


def test_no_scheduled_arrival_shortcut_in_the_implementation():
    """A source-level guard: the module reads no plan-side or UTC-date property.

    Prose in the docstrings names these fields to explain why they are excluded, so the scan is
    for the attribute-access form rather than the bare word.
    """
    source = (REPO_ROOT / "rai_code" / "queries" / "rotation.py").read_text()
    for forbidden in (
        ".flight_departure_date_utc",
        ".planned_destination_airport",
        ".planned_origin_airport",
        ".scheduled_arrival",
        ".fulfils",
    ):
        assert forbidden not in source, forbidden


# ------------------------------------------------------ 4. the diversion trap


def test_diverted_leg_does_not_chain_from_its_planned_arrival(am, diverted):
    """The sharpest continuity case in the fixture, and it is a live one.

    Flight 7200 planned SFO to LAX and actually landed at LAS; ``TT-PLAN-ACTUAL-DIVERSION``
    freezes both endpoints and requires both to be preserved. Aircraft 1100's leg 5103 departs
    from **LAX**, the planned arrival, at 16:00, exactly when 7200 actually arrived. A chain built
    on the planned arrival airport would link 7200 to 5103 and invent a two-leg rotation. The
    actual arrival is LAS, so there is no link, and the answer keeps them as two singleton
    segments.
    """
    plan_actual = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.AircraftFlight.actual_destination.airport_id.alias("actual_destination"),
            am.AircraftFlight.diverted_airport.airport_id.alias("diverted_airport"),
            am.AircraftFlight.is_diverted_boolean.alias("is_diverted"),
            am.AircraftFlight.fulfils.planned_destination_airport.airport_id.alias(
                "planned_destination"
            ),
        )
        .where(am.AircraftFlight.flight_id == 7200)
        .to_df()
    )
    assert len(plan_actual) == 1
    diverted_leg = plan_actual.iloc[0]
    assert bool(diverted_leg["is_diverted"]) is True
    assert diverted_leg["planned_destination"] == "SYN-AP-LAX"
    assert diverted_leg["actual_destination"] == "SYN-AP-LAS"
    assert diverted_leg["diverted_airport"] == "SYN-AP-LAS"

    answer_7200 = row_for(diverted, 7200)
    answer_5103 = row_for(diverted, 5103)
    assert answer_5103["actual_origin"] == diverted_leg["planned_destination"] == "SYN-AP-LAX"
    assert answer_5103["actual_departure_utc"] == answer_7200["actual_arrival_utc"]
    assert answer_7200["segment_id"] != answer_5103["segment_id"]
    assert pd.isna(answer_7200["next_flight_id"])
    assert int(answer_7200["leg_order"]) == int(answer_5103["leg_order"]) == 1
    assert answer_7200["actual_destination"] == "SYN-AP-LAS"


def test_diversion_endpoint_conflict_terminates_continuity(am, anomalies):
    """8109's diverted airport contradicts its actual arrival, so the link is refused.

    Its target 8106 departs from 8109's actual arrival at a valid time, so every other acceptance
    condition holds; ``DIVERSION_ENDPOINT_CONFLICT`` is the sole match, and AF-10 never repairs
    AF-09.
    """
    row = row_for(anomalies_only(anomalies), 8109)
    assert row["anomaly_code"] == "DIVERSION_ENDPOINT_CONFLICT"
    assert row["link_outcome"] == "REJECTED"
    assert int(row["next_flight_id"]) == 8106
    assert row["actual_destination"] == "SYN-AP-LAS"

    endpoints = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.AircraftFlight.actual_destination.airport_id.alias("actual_destination"),
            am.AircraftFlight.diverted_airport.airport_id.alias("diverted_airport"),
        )
        .where(am.AircraftFlight.flight_id == 8109)
        .to_df()
    )
    assert endpoints.iloc[0]["diverted_airport"] == "SYN-AP-LAX"
    assert endpoints.iloc[0]["actual_destination"] == "SYN-AP-LAS"
    assert endpoints.iloc[0]["diverted_airport"] != endpoints.iloc[0]["actual_destination"]


# ----------------------------- 5. cancellation, missing time, broken links


def test_cancelled_leg_is_excluded_and_still_visible(am, anomalies):
    """8110 is cancelled: ``EXCLUDED`` from the chain, present as an anomaly row."""
    row = row_for(anomalies_only(anomalies), 8110)
    assert row["anomaly_code"] == "CANCELLED"
    assert row["link_outcome"] == "EXCLUDED"
    assert row["leg_order"] is None or pd.isna(row["leg_order"])
    assert 8110 not in set(int(x) for x in legs_only(anomalies)["flight_id"])

    flags = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.AircraftFlight.is_cancelled_boolean.alias("is_cancelled"),
            am.AircraftFlight.cancellation_flag_status.alias("cancellation_flag_status"),
        )
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.Aircraft.id == ANOMALY_AIRCRAFT,
            # Compare the boolean explicitly. where(Concept.bool_property) matches every entity
            # that HAS the property, whatever its value.
            am.AircraftFlight.is_cancelled_boolean == True,  # noqa: E712
        )
        .to_df()
    )
    assert [int(x) for x in flags["flight_id"]] == [8110]

    # The third state is a different class and is not folded into CANCELLED: 8112's raw flag is
    # neither 0 nor 1, so the boolean is absent rather than false.
    unknown = row_for(anomalies_only(anomalies), 8112)
    assert unknown["anomaly_code"] == "UNKNOWN_OR_INVALID_CANCELLATION_FLAG"
    assert unknown["link_outcome"] == "EXCLUDED"


def test_missing_time_leg_keeps_its_row_with_null_times(anomalies):
    """8111 has no actual gate times. The row survives with two nulls rather than being dropped.

    A missing property in PyRel silently fails to match rather than raising, so binding a time in
    ``where`` would have removed this leg from the answer entirely.
    """
    row = row_for(anomalies_only(anomalies), 8111)
    assert row["anomaly_code"] == "MISSING_TIME"
    assert row["link_outcome"] == "EXCLUDED"
    assert pd.isna(row["actual_departure_utc"])
    assert pd.isna(row["actual_arrival_utc"])
    assert row["actual_origin"] == "SYN-AP-SFO"
    assert row["actual_destination"] == "SYN-AP-LAX"


def test_broken_links_are_typed_rather_than_silent(am, anomalies):
    """Two different ways a link can be broken, both reported and both distinguished.

    8104 points at 8999, which does not exist: ``MISSING_TARGET``. The raw AF-20 value is retained
    on the row while the resolved ``next_flight_raw`` association has no fact at all, which is the
    contract's "a failed resolution must still show the code".

    8108 points at 8107, which exists, departs late enough and belongs to the same aircraft and
    day, but departs from SFO while 8108 arrived at LAX: ``BROKEN_CONTINUITY``.
    """
    missing_target = row_for(anomalies_only(anomalies), 8104)
    assert missing_target["anomaly_code"] == "MISSING_TARGET"
    assert int(missing_target["next_flight_id"]) == 8999
    assert missing_target["link_outcome"] == "REJECTED"

    dangling = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            am.AircraftFlight.next_flight_id.alias("raw_next_flight_id"),
            am.AircraftFlight.next_flight_raw.flight_id.alias("resolved_next_flight_id"),
        )
        .where(am.AircraftFlight.flight_id == 8104)
        .to_df()
    )
    assert int(dangling.iloc[0]["raw_next_flight_id"]) == 8999
    assert pd.isna(dangling.iloc[0]["resolved_next_flight_id"])
    target_exists = (
        am.model.select(am.AircraftFlight.flight_id.alias("flight_id"))
        .where(am.AircraftFlight.flight_id == 8999)
        .to_df()
    )
    assert target_exists.shape[0] == 0

    broken = row_for(anomalies_only(anomalies), 8108)
    assert broken["anomaly_code"] == "BROKEN_CONTINUITY"
    assert int(broken["next_flight_id"]) == 8107
    assert broken["actual_destination"] == "SYN-AP-LAX"
    assert row_for(anomalies_only(anomalies), 8107)["actual_origin"] == "SYN-AP-SFO"

    backward = row_for(anomalies_only(anomalies), 8107)
    assert backward["anomaly_code"] == "BACKWARD_TIME"
    assert int(backward["next_flight_id"]) == 8101
    assert row_for(anomalies_only(anomalies), 8101)["actual_departure_utc"] < backward[
        "actual_arrival_utc"
    ]

    outside_day = row_for(anomalies_only(anomalies), 8106)
    assert outside_day["anomaly_code"] == "OUTSIDE_SELECTED_DAY"
    assert int(outside_day["next_flight_id"]) == 8206


# ------------------------------------------------------- 6. per-leg as-of enrichment


def test_per_leg_enrichment_is_the_shared_as_of_resolution_on_af06(am, canonical):
    """The enrichment the answer carries is the same as-of resolution Q01 uses, on AF-06.

    The answer reads the ontology's materialized ``as_of_aircraft_type`` and ``as_of_engine_type``.
    This test reproduces them independently through ``temporal.visible_on`` - the shared half-open
    predicate - with the per-dimension scope, and requires the two to agree leg by leg. That is
    what makes "one reusable semantic model" a checkable claim rather than a slogan.
    """
    legs = legs_only(canonical)
    assert list(legs["as_of_aircraft_type_id"]) == ["SYN-TYPE-B"] * 3
    assert list(legs["as_of_engine_type_id"]) == ["SYN-ENGINE-B"] * 3

    typ = am.DailyAssignment.ref("shared_type_at_leg")
    eng = am.DailyAssignment.ref("shared_engine_at_leg")
    shared = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            typ.aircraft_type.subseries.alias("as_of_aircraft_type_id"),
            eng.engine_type.subseries.alias("as_of_engine_type_id"),
        )
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.Aircraft.id == CANONICAL_AIRCRAFT,
            am.AircraftFlight.flight_departure_date == SELECTED_DAY,
            typ.aircraft == am.Aircraft,
            # AircraftDimensionDailyAssignment is ONE concept with a dimension discriminator, so
            # the scope is required. Without it the same reference ranges over all four streams.
            typ.dimension == am.DIM_AIRCRAFT_TYPE,
            *am.visible_on(typ, am.AircraftFlight.flight_departure_date),
            eng.aircraft == am.Aircraft,
            eng.dimension == am.DIM_ENGINE_TYPE,
            *am.visible_on(eng, am.AircraftFlight.flight_departure_date),
        )
        .to_df()
        .sort_values("flight_id")
        .reset_index(drop=True)
    )
    assert len(shared) == 3
    assert list(shared["flight_id"].map(int)) == [8001, 8002, 8003]
    assert list(shared["as_of_aircraft_type_id"]) == list(legs["as_of_aircraft_type_id"])
    assert list(shared["as_of_engine_type_id"]) == list(legs["as_of_engine_type_id"])


def test_unscoped_dimension_resolution_would_inflate(am):
    """The trap the scope defends against, measured rather than described.

    Dropping ``dimension ==`` from the same query returns four rows per leg, one per stream, three
    of which carry no aircraft type at all. It is a silently wrong answer, not an error.
    """
    asg = am.DailyAssignment.ref("unscoped_assignment")
    unscoped = (
        am.model.select(
            am.AircraftFlight.flight_id.alias("flight_id"),
            asg.dimension.alias("dimension"),
            asg.aircraft_type.subseries.alias("as_of_aircraft_type_id"),
        )
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.Aircraft.id == CANONICAL_AIRCRAFT,
            am.AircraftFlight.flight_departure_date == SELECTED_DAY,
            asg.aircraft == am.Aircraft,
            *am.visible_on(asg, am.AircraftFlight.flight_departure_date),
        )
        .to_df()
    )
    assert len(unscoped) == 12
    assert set(unscoped["dimension"]) == {
        am.DIM_AIRCRAFT_STATE,
        am.DIM_AIRCRAFT_STATUS,
        am.DIM_AIRCRAFT_TYPE,
        am.DIM_ENGINE_TYPE,
    }
    resolved = unscoped[unscoped["dimension"] == am.DIM_AIRCRAFT_TYPE]
    assert len(resolved) == 3
    assert set(resolved["as_of_aircraft_type_id"]) == {"SYN-TYPE-B"}


def test_type_discrepancy_is_reported_and_never_reconciled(canonical):
    """Leg 8002's source description disagrees with aircraft history. Both values ship.

    AF-17 is discrepancy evidence and never aircraft-history authority, so the as-of type stays
    ``SYN-TYPE-B`` while the source text stays "Synthetic narrowbody A" and the flag is true.
    """
    legs = legs_only(canonical)
    assert [bool(x) for x in legs["type_discrepancy"]] == [False, True, False]
    row = row_for(legs, 8002)
    assert row["as_of_aircraft_type_id"] == "SYN-TYPE-B"
    assert row["actual_source_aircraft_type"] == "Synthetic narrowbody A"
    assert bool(row["type_discrepancy"]) is True
    for other in (8001, 8003):
        assert row_for(legs, other)["actual_source_aircraft_type"] == "Synthetic narrowbody B"


def test_anomaly_rows_carry_no_enrichment(anomalies):
    """An anomaly has no position in the operated chain, so all five derived cells are null."""
    for _, row in anomalies_only(anomalies).iterrows():
        assert pd.isna(row["leg_order"])
        assert row["as_of_aircraft_type_id"] is None
        assert row["as_of_engine_type_id"] is None
        assert row["actual_source_aircraft_type"] is None
        assert pd.isna(row["type_discrepancy"])


# ------------------------------------------------------ 7. typed parameter validation


@pytest.mark.parametrize(
    ("aircraft_id", "day", "error_code"),
    [
        (None, SELECTED_DAY, "MISSING_AIRCRAFT_ID"),
        (CANONICAL_AIRCRAFT, None, "MISSING_FLIGHT_DEPARTURE_DATE"),
        (-1, SELECTED_DAY, "INVALID_AIRCRAFT_ID"),
        (0, SELECTED_DAY, "INVALID_AIRCRAFT_ID"),
        ("not-a-number", SELECTED_DAY, "INVALID_AIRCRAFT_ID"),
        (True, SELECTED_DAY, "INVALID_AIRCRAFT_ID"),
        (1001.5, SELECTED_DAY, "INVALID_AIRCRAFT_ID"),
        (CANONICAL_AIRCRAFT, "2026-02-30", "INVALID_DATE"),
        (CANONICAL_AIRCRAFT, "not-a-date", "INVALID_DATE"),
        (CANONICAL_AIRCRAFT, 20260831, "INVALID_DATE"),
    ],
)
def test_parameter_validation_rejects_before_any_query(aircraft_id, day, error_code):
    """Validation runs before execution, so these need no engine and no model."""
    with pytest.raises(rotation.RotationParameterError) as raised:
        rotation.actual_rotation_enriched(aircraft_id, day, am=object())
    assert raised.value.error_code == error_code
    assert raised.value.invocation_status == "PARAMETER_ERROR"

    outcome = rotation.invoke(aircraft_id, day, am=object())
    assert outcome.invocation_status == "PARAMETER_ERROR"
    assert outcome.error_code == error_code
    assert list(outcome.rows.columns) == list(rotation.OUTPUT_COLUMNS)
    assert len(outcome.rows) == 0


def test_accepted_parameter_spellings_agree(am, canonical):
    """An ISO string, a ``date`` and a ``datetime`` are the same day; the answer is identical."""
    as_string = rotation.actual_rotation_enriched(
        str(CANONICAL_AIRCRAFT), "2026-08-31", am=am
    )
    assert rotation.canonical_rows(as_string) == rotation.canonical_rows(canonical)
    as_datetime = rotation.actual_rotation_enriched(
        CANONICAL_AIRCRAFT, dt.datetime(2026, 8, 31, 23, 59), am=am
    )
    assert rotation.canonical_rows(as_datetime) == rotation.canonical_rows(canonical)


def test_row_id_offset_is_a_supplied_label(am, canonical):
    """``row_id`` is a supplied manifest label (D-0021), so its offset is the caller's.

    The manifest numbers Q08 continuously across result sets, which is why ``Q08-ANOMALIES``
    starts at ``Q08-R004``. Nothing else in the answer moves when the offset does.
    """
    assert list(canonical["row_id"]) == ["Q08-R001", "Q08-R002", "Q08-R003"]
    shifted = rotation.actual_rotation_enriched(
        CANONICAL_AIRCRAFT, SELECTED_DAY, am=am, row_id_start=4
    )
    assert list(shifted["row_id"]) == ["Q08-R004", "Q08-R005", "Q08-R006"]
    without_ids = [
        {k: v for k, v in row.items() if k != "row_id"}
        for row in rotation.canonical_rows(shifted)
    ]
    assert without_ids == [
        {k: v for k, v in row.items() if k != "row_id"}
        for row in rotation.canonical_rows(canonical)
    ]
