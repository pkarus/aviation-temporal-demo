"""test_model.py - MODEL-01 / MODEL-02 live gate.

Every test here hits the live ``PK_AVIATION_TEMPORAL`` under ``RAI_DEMO_AVIATION_TEMPORAL`` and
the ``aviation_temporal_logic_s`` reasoner. An import that succeeds is not a model that loads,
so nothing here is mocked and nothing is asserted from a producer's claim.

Run with a warm engine::

    .venv/bin/rai reasoners resume --type Logic --name aviation_temporal_logic_s --wait
    .venv/bin/python -m pytest tests/test_model.py -m live -x -q

Cold start from SUSPENDED was measured at 631s, so a first run against a suspended engine looks
like a hang for ten minutes. Warm it first.

The tests are grouped by what they are defending against, and three of the groups exist only
because the failure they catch is **silent**:

* ``test_no_any_typed_columns`` - a mistyped column in a ``sources.py`` ``schema=`` dict binds
  as an ``Any`` relation with no error (PROBE U-01).
* ``test_declared_types_match_information_schema`` and ``test_per_column_non_null_matches_sql`` -
  a wrongly declared type yields an all-NaN column, not a ``TyperError`` (PROBE U-02). A
  row-count check passes happily; only a per-column non-null count catches it.
* ``test_bool_property_needs_explicit_comparison`` - ``where(Concept.bool_prop)`` matches every
  entity that *has* the property regardless of its value. Measured here, not in the probe run.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rai_code"))

pytestmark = pytest.mark.live

DB = "PK_AVIATION_TEMPORAL"
ROLE = "RAI_DEMO_AVIATION_TEMPORAL"
KNOWLEDGE_DATE = dt.date(2026, 8, 31)
OPERATING_DATE = dt.date(2026, 9, 7)


# --------------------------------------------------------------------------- helpers


def sql(query: str) -> list[dict]:
    """Run one read-only query as the demo role and return parsed rows."""
    proc = subprocess.run(
        ["snow", "sql", "-c", "rai", "--role", ROLE, "--format", "json", "-q", query],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def scalar(df):
    """First cell of a RAI result, or ``None``.

    An empty RAI result is a **zero-column** DataFrame, not a zero-row DataFrame with the
    expected columns (PROBE D11), so ``df["x"]`` would raise ``KeyError`` rather than give an
    empty column. Every assertion in this file goes through here or checks ``df.shape[1]``.
    """
    if df.shape[1] == 0 or df.shape[0] == 0:
        return None
    return df.iloc[0, 0]


def count_of(model, concept) -> int:
    from relationalai.semantics.std import aggregates as aggs

    value = scalar(model.select(aggs.count(concept).alias("n")).to_df())
    return 0 if value is None else int(value)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="session")
def am():
    """The loaded ontology package. One ``Model`` per process, deliberately.

    The free ``distinct(...)`` raises ``[Ambiguous model]`` as soon as a second ``Model`` exists
    in the interpreter (PROBE N-02), and every fresh ``Model`` pays 25-100s of indexing before
    its first query. Session scope keeps both problems away.
    """
    import aviation_model

    return aviation_model


@pytest.fixture(scope="session")
def inventory(am):
    from aviation_model.inventory import write_inventory

    return write_inventory()


# Concept -> (Snowflake object, expected row count). Counts come from the live tables and from
# build/task_reports/DATA-04a.json, not from the model.
CONCEPT_SOURCES: dict[str, tuple[str, str]] = {
    "Aircraft": ("MODEL_INPUT.AIRCRAFT_ELIGIBLE", "AIRCRAFT_ID"),
    "AircraftEvent": ("MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE", "AIRCRAFT_HISTORY_ID"),
    "AircraftEventQuarantine": ("MODEL_INPUT.AIRCRAFT_EVENT_QUARANTINE", "QUARANTINE_ID"),
    "AircraftType": ("MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION", "AIRCRAFT_SUBSERIES"),
    "EngineType": ("MODEL_INPUT.ENGINE_TYPE_DEFINITION", "ENGINE_SUBSERIES"),
    "AircraftConfiguration": ("SOURCE.AIRCRAFT_CONFIGURATION", "AIRCRAFT_CONFIGURATION_ID"),
    "AircraftDimensionAuditAssignment": (
        "MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT",
        "AUDIT_ASSIGNMENT_ID",
    ),
    "AircraftDimensionDailyAssignment": (
        "MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT",
        "DAILY_ASSIGNMENT_ID",
    ),
    "Airport": ("MODEL_INPUT.AIRPORT_CURRENT", "AIRPORT_ID"),
    "Airline": ("MODEL_INPUT.AIRLINE_CURRENT", "AIRLINE_ID"),
    "CodeResolutionCode": ("MODEL_INPUT.CODE_RESOLUTION_CODE", "RAW_CODE"),
    "CodeResolutionCodeCandidate": (
        "MODEL_INPUT.CODE_RESOLUTION_CODE_CANDIDATE",
        "CANDIDATE_ID",
    ),
    "SnapshotDate": ("SOURCE.SCHEDULE_SNAPSHOT_CALENDAR", "EXPECTED_PUBLISH_DATE"),
    "MonthEnd": ("MODEL_INPUT.MONTH_END_CALENDAR", "MONTH_END"),
    "Route": ("MODEL_INPUT.ROUTE", "ROUTE_ID"),
    "RouteState": ("MODEL_INPUT.ROUTE_STATE", "ROUTE_STATE_KEY"),
    "RouteStateSnapshotLineage": ("MODEL_INPUT.ROUTE_STATE_LINEAGE", "ROUTE_STATE_KEY"),
    "ScheduleObservation": (
        "MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION",
        "SCHEDULE_KEY",
    ),
    "ScheduleComparison": ("MODEL_INPUT.SCHEDULE_COMPARISON", "COMPARISON_ID"),
    "ScheduleExactChange": ("MODEL_INPUT.SCHEDULE_EXACT_CHANGE", "SCHEDULE_KEY"),
    "ScheduleAmendmentSide": ("MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE", "SCHEDULE_KEY"),
    "ScheduleAmendmentCandidate": (
        "MODEL_INPUT.SCHEDULE_AMENDMENT_CANDIDATE",
        "AMENDMENT_CANDIDATE_ID",
    ),
    "ScheduleAmendmentGroup": (
        "MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP",
        "AMENDMENT_GROUP_ID",
    ),
    "ScheduleAmendmentGroupMember": (
        "MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP_MEMBER",
        "AMENDMENT_GROUP_MEMBER_ID",
    ),
    "PassengerFlight": ("MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL", "PASSENGER_FLIGHT_KEY"),
    "PassengerSourceLineage": (
        "MODEL_INPUT.PASSENGER_SOURCE_LINEAGE",
        "PASSENGER_FLIGHT_KEY",
    ),
    "PassengerPlannedLeg": ("MODEL_INPUT.PASSENGER_PLANNED_LEG", "PASSENGER_FLIGHT_KEY"),
    "InvalidPassengerObservation": (
        "MODEL_INPUT.PASSENGER_FLIGHT_INVALID",
        "SOURCE_SYSTEM",
    ),
    "PassengerSourceQuarantine": (
        "MODEL_INPUT.PASSENGER_SOURCE_QUARANTINE",
        "QUARANTINE_ID",
    ),
    "AircraftFlight": ("MODEL_INPUT.AIRCRAFT_FLIGHT", "FLIGHT_ID"),
    "RotationLinkValidation": ("MODEL_INPUT.ROTATION_LINK_VALIDATION", "FLIGHT_ID"),
    "ExactFulfillment": ("MODEL_INPUT.FULFILLMENT_EXACT", "EXACT_FULFILLMENT_ID"),
    "FulfillmentCandidate": (
        "MODEL_INPUT.FULFILLMENT_CANDIDATE",
        "FULFILLMENT_CANDIDATE_ID",
    ),
    "FulfillmentGroupMember": (
        "MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP",
        "FULFILLMENT_GROUP_MEMBER_ID",
    ),
}


# --------------------------------------------------------------- 1. the model loads


def test_model_loads_without_warnings():
    """Importing the package must produce no ``relationalai`` warning of any kind.

    Specifically: no implicit-property warning (strict mode is on and every property is
    declared) and no deprecated-API warning (``Concept.lookup`` throughout, never the
    deprecated ``filter_by`` the design brief used).
    """
    import warnings

    proc = subprocess.run(
        [
            sys.executable,
            "-W",
            "always",
            "-c",
            "import sys; sys.path.insert(0, %r); import aviation_model" % str(REPO_ROOT / "rai_code"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    offenders = [
        line
        for line in proc.stderr.splitlines()
        if "relationalai" in line and "Warning" in line
    ]
    assert not offenders, offenders
    del warnings


@pytest.mark.parametrize("concept_name", sorted(CONCEPT_SOURCES))
def test_concept_count_matches_sql(am, concept_name):
    """Entity count per concept equals the source row count.

    Not cosmetic. A row whose ``Concept.lookup(...)`` parent does not resolve produces no
    entity **and no error** (PROBE U-08 - 23,952 of 48,000 rows silently produced nothing in
    that probe's restricted fixture). Without a count assertion a quarantine is invisible.
    """
    obj, key_column = CONCEPT_SOURCES[concept_name]
    expected = int(sql(f"SELECT COUNT(*) AS n FROM {DB}.{obj}")[0]["N"])
    got = count_of(am.model, getattr(am, concept_name))
    assert got == expected, f"{concept_name}: model {got} != SQL {expected} ({obj})"
    del key_column


# ------------------------------------------- 2. the two silent-typing defences


def test_no_any_typed_columns(inventory):
    """No discovered table column may be ``Any``-typed."""
    from aviation_model.inventory import assert_no_any_columns

    assert assert_no_any_columns(inventory) == []


def test_declared_types_match_information_schema():
    """Every ``sources.py`` declared type must equal the type derived from the live schema.

    Regenerating ``sources.py`` from ``INFORMATION_SCHEMA`` is what makes a column typo
    impossible; this test is what keeps it true after a DATA-04 change.
    """
    from aviation_model._regen_sources import derive_type, load_columns
    from aviation_model.sources import TABLE_INVENTORY

    live = load_columns()
    mismatches = []
    for alias, (_table, qualified, declared) in TABLE_INVENTORY.items():
        schema_name, table_name = qualified.split(".", 1)
        live_columns = live.get((schema_name, table_name))
        assert live_columns, f"{qualified} is missing from INFORMATION_SCHEMA"
        live_types = {c["COLUMN_NAME"].lower(): derive_type(c) for c in live_columns}
        if set(live_types) != set(declared):
            mismatches.append(
                (alias, "column set drift", sorted(set(live_types) ^ set(declared)))
            )
            continue
        for column, declared_type in declared.items():
            expected = live_types[column]
            if str(declared_type) != expected and _type_name(declared_type) != expected:
                mismatches.append((alias, column, str(declared_type), expected))
    assert not mismatches, mismatches


def _type_name(rai_type) -> str:
    """Map a RAI type object back onto the generator's textual type name."""
    from relationalai.semantics import (
        Bool,
        Date,
        DateTime,
        Float,
        Integer,
        Number,
        String,
    )

    for name, obj in (
        ("String", String),
        ("Date", Date),
        ("DateTime", DateTime),
        ("Float", Float),
        ("Bool", Bool),
        ("Integer", Integer),
    ):
        if rai_type is obj:
            return name
    # Only two integer types can legitimately appear, because the SDK buckets integer
    # precision by bit width: Number.size(18, 0) for 1..18 digits, Integer for 19..38.
    if rai_type is Number.size(18, 0):
        return "Number.size(18, 0)"
    return str(rai_type)


# Concept -> (Snowflake object, {property: column}) for the non-null comparison. Derived from
# the same generator metadata the properties were built from, so the mapping cannot drift.
def _non_null_targets():
    from aviation_model import core_aircraft, core_flight, core_reference, core_schedule
    from aviation_model import calendar_dates

    return {
        "Aircraft": ("MODEL_INPUT.AIRCRAFT_ELIGIBLE", core_aircraft._aircraft_scalars),
        "AircraftEvent": (
            "MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE",
            core_aircraft._event_scalars,
        ),
        "AircraftType": (
            "MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION",
            core_aircraft._aircraft_type_scalars,
        ),
        "EngineType": (
            "MODEL_INPUT.ENGINE_TYPE_DEFINITION",
            core_aircraft._engine_type_scalars,
        ),
        "AircraftConfiguration": (
            "SOURCE.AIRCRAFT_CONFIGURATION",
            core_aircraft._configuration_scalars,
        ),
        "AircraftDimensionAuditAssignment": (
            "MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT",
            core_aircraft._audit_scalars,
        ),
        "AircraftDimensionDailyAssignment": (
            "MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT",
            core_aircraft._daily_scalars,
        ),
        "Airport": ("MODEL_INPUT.AIRPORT_CURRENT", core_reference._airport_scalars),
        "Airline": ("MODEL_INPUT.AIRLINE_CURRENT", core_reference._airline_scalars),
        "CodeResolutionCode": (
            "MODEL_INPUT.CODE_RESOLUTION_CODE",
            core_reference._code_resolution_scalars,
        ),
        "SnapshotDate": (
            "SOURCE.SCHEDULE_SNAPSHOT_CALENDAR",
            core_reference._snapshot_scalars,
        ),
        "MonthEnd": (
            "MODEL_INPUT.MONTH_END_CALENDAR",
            calendar_dates._month_end_scalars,
        ),
        "Route": ("MODEL_INPUT.ROUTE", core_schedule._route_scalars),
        "RouteState": ("MODEL_INPUT.ROUTE_STATE", core_schedule._route_state_scalars),
        "RouteStateSnapshotLineage": (
            "MODEL_INPUT.ROUTE_STATE_LINEAGE",
            core_schedule._rs_lineage_scalars,
        ),
        "ScheduleObservation": (
            "MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION",
            core_schedule._observation_scalars,
        ),
        "ScheduleComparison": (
            "MODEL_INPUT.SCHEDULE_COMPARISON",
            core_schedule._comparison_scalars,
        ),
        "ScheduleExactChange": (
            "MODEL_INPUT.SCHEDULE_EXACT_CHANGE",
            core_schedule._exact_change_scalars,
        ),
        "ScheduleAmendmentSide": (
            "MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE",
            core_schedule._amendment_side_scalars,
        ),
        "PassengerFlight": (
            "MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL",
            core_flight._passenger_scalars,
        ),
        "PassengerSourceLineage": (
            "MODEL_INPUT.PASSENGER_SOURCE_LINEAGE",
            core_flight._lineage_scalars,
        ),
        "PassengerPlannedLeg": (
            "MODEL_INPUT.PASSENGER_PLANNED_LEG",
            core_flight._planned_leg_scalars,
        ),
        "AircraftFlight": ("MODEL_INPUT.AIRCRAFT_FLIGHT", core_flight._flight_scalars),
        "RotationLinkValidation": (
            "MODEL_INPUT.ROTATION_LINK_VALIDATION",
            core_flight._rotation_scalars,
        ),
        "ExactFulfillment": (
            "MODEL_INPUT.FULFILLMENT_EXACT",
            core_flight._exact_fulfillment_scalars,
        ),
        "FulfillmentGroupMember": (
            "MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP",
            core_flight._fulfillment_member_scalars,
        ),
    }


@pytest.mark.parametrize(
    "concept_name",
    sorted(
        [
            "Aircraft",
            "AircraftEvent",
            "AircraftType",
            "EngineType",
            "AircraftConfiguration",
            "AircraftDimensionAuditAssignment",
            "AircraftDimensionDailyAssignment",
            "Airport",
            "Airline",
            "CodeResolutionCode",
            "SnapshotDate",
            "MonthEnd",
            "Route",
            "RouteState",
            "RouteStateSnapshotLineage",
            "ScheduleObservation",
            "ScheduleComparison",
            "ScheduleExactChange",
            "ScheduleAmendmentSide",
            "PassengerFlight",
            "PassengerSourceLineage",
            "PassengerPlannedLeg",
            "AircraftFlight",
            "RotationLinkValidation",
            "ExactFulfillment",
            "FulfillmentGroupMember",
        ]
    ),
)
def test_per_column_non_null_matches_sql(am, concept_name):
    """Per-property non-null count in RAI equals ``COUNT(<column>)`` in Snowflake.

    This is the assertion that catches a wrongly declared type, which PROBE U-02 showed yields
    a silent all-NaN column rather than a ``TyperError``. A row count alone passes; only this
    fails.

    All properties of one concept are read in a single ``select``, which relies on the
    left-join semantics of a plain dot-chain (PROBE D1): a property with no value keeps the row
    and renders as ``NaN``. Binding the property in ``where()`` instead would drop exactly the
    rows this test is measuring (PROBE D3 - four rows became two).
    """
    obj, mapping = _non_null_targets()[concept_name]
    concept = getattr(am, concept_name)

    columns = list(mapping.items())
    projection = [getattr(concept, attr).alias(attr) for attr, _col in columns]
    df = am.model.select(*projection).to_df()

    expected_row = sql(
        "SELECT "
        # Snowflake stores unquoted identifiers upper-cased, and the schema dicts key them
        # lower-cased for readability, so both sides have to be normalised or the quoted
        # lower-case identifier fails to resolve.
        + ", ".join(f'COUNT("{col.upper()}") AS "{attr.upper()}"' for attr, col in columns)
        + f" FROM {DB}.{obj}"
    )[0]

    mismatches = []
    for attr, _col in columns:
        rai_non_null = int(df[attr].notna().sum())
        sql_non_null = int(expected_row[attr.upper()])
        if rai_non_null != sql_non_null:
            mismatches.append((attr, rai_non_null, sql_non_null))
    assert not mismatches, f"{concept_name}: (property, rai_non_null, sql_non_null) {mismatches}"


# ------------------------------------------------- 3. the TIME round-trip (U-03)


TIME_COLUMNS = [
    ("RouteState", "passenger_departure_utc_time", "MODEL_INPUT.ROUTE_STATE"),
    ("RouteState", "passenger_arrival_utc_time", "MODEL_INPUT.ROUTE_STATE"),
    ("RouteState", "passenger_departure_local_time", "MODEL_INPUT.ROUTE_STATE"),
    ("RouteState", "passenger_arrival_local_time", "MODEL_INPUT.ROUTE_STATE"),
    (
        "ScheduleObservation",
        "passenger_departure_utc_time",
        "MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION",
    ),
    (
        "PassengerFlight",
        "passenger_departure_local_time",
        "MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL",
    ),
]


@pytest.mark.parametrize("concept_name,prop,obj", TIME_COLUMNS)
def test_time_columns_round_trip_as_strings(am, concept_name, prop, obj):
    """A Snowflake ``TIME`` bound as ``String`` must be byte-identical to ``HH24:MI:SS.FF3``.

    Declared or discovered as ``DateTime`` these columns return 100% NULL with no error
    (PROBE U-03) - total silent data loss on 26 columns. Declared ``String`` they round-trip
    exactly, at the cost that every time-of-day literal must carry the millisecond suffix.
    ``test_time_literal_without_milliseconds_matches_nothing`` is the sharp edge.
    """
    concept = getattr(am, concept_name)
    df = am.model.select(getattr(concept, prop).alias("t")).to_df()
    rai_values = sorted(v for v in set(df["t"].dropna()))

    rows = sql(
        f"SELECT DISTINCT TO_VARCHAR(\"{prop.upper()}\", 'HH24:MI:SS.FF3') AS T "
        f"FROM {DB}.{obj} WHERE \"{prop.upper()}\" IS NOT NULL ORDER BY 1"
    )
    sql_values = sorted(r["T"] for r in rows)
    assert rai_values == sql_values, (concept_name, prop, rai_values, sql_values)


def test_time_literal_without_milliseconds_matches_nothing(am):
    """``'16:00:00'`` must match zero rows while ``'16:00:00.000'`` matches all of them.

    Asserted rather than merely documented, because a query author who writes Snowflake's
    rendering gets an empty result with no error and will debug the join instead of the literal.
    """
    from relationalai.semantics.std import aggregates as aggs

    with_ms = scalar(
        am.model.select(aggs.count(am.RouteState).alias("n"))
        .where(am.RouteState.passenger_departure_utc_time == "16:00:00.000")
        .to_df()
    )
    without_ms = scalar(
        am.model.select(aggs.count(am.RouteState).alias("n"))
        .where(am.RouteState.passenger_departure_utc_time == "16:00:00")
        .to_df()
    )
    assert with_ms == 12030
    assert without_ms is None


# ------------------------------------------------- 4. the multi-open route beat


def test_multi_open_route_states_from_one_query(am):
    """THE demo's central semantic beat, and the one result that must never regress.

    1,339 route states are concurrently valid on ``SFO->LAX`` at knowledge date 2026-08-31, and
    one query returns every one of them - individually, and as a per-route count - with no
    uniqueness failure. That is HT-18 satisfied by construction rather than by exception
    handling: ``Route`` does not appear in ``RouteState``'s identity, and ``Route.states`` is an
    ``.alt()`` reading that adds no functional dependency.

    Note the precise claim. These are states concurrently valid *at a knowledge date*, not
    open-ended ones: the fixture's knowledge clock ends at 2026-10-26 and **no** route state
    carries the model open sentinel ``9999-01-01``, so a narration promising "open-ended
    versions" would be false. ``test_no_route_state_carries_the_open_sentinel`` pins that.
    """
    from relationalai.semantics.std import aggregates as aggs

    per_route = am.model.select(
        am.Route.route_id.alias("route_id"),
        aggs.count(am.RouteState).per(am.Route).alias("open_states"),
    ).where(
        am.RouteState.route == am.Route,
        *am.known_on(am.RouteState, KNOWLEDGE_DATE),
    ).to_df()

    counts = dict(zip(per_route["route_id"], (int(x) for x in per_route["open_states"])))
    assert counts["SFO->LAX"] == 1339
    assert sum(1 for v in counts.values() if v > 1) >= 9

    individually = am.model.select(
        am.RouteState.route_state_key.alias("route_state_key"),
        am.RouteState.schedule_key.alias("schedule_key"),
    ).where(
        am.RouteState.route == am.Route,
        am.Route.route_id == "SFO->LAX",
        *am.known_on(am.RouteState, KNOWLEDGE_DATE),
    ).to_df()
    assert len(individually) == 1339
    assert individually["schedule_key"].nunique() == 1339

    expected = int(
        sql(
            f"SELECT COUNT(*) AS n FROM {DB}.MODEL_INPUT.ROUTE_STATE "
            "WHERE ROUTE_ID = 'SFO->LAX' AND KNOWLEDGE_VALID_FROM <= '2026-08-31' "
            "AND '2026-08-31' < KNOWLEDGE_VALID_TO"
        )[0]["N"]
    )
    assert expected == 1339


def test_no_route_state_carries_the_open_sentinel(am):
    """Honesty guard for the narration above.

    Zero route states carry ``knowledge_valid_to = 9999-01-01`` in this fixture, so the beat
    must be told as "concurrently valid at a knowledge date", never as "concurrently open-ended".
    If a future fixture adds open-ended states this test fails and the narration can be widened
    deliberately rather than drifting.
    """
    from relationalai.semantics.std import aggregates as aggs

    assert (
        scalar(
            am.model.select(aggs.count(am.RouteState).alias("n"))
            .where(am.RouteState.knowledge_valid_to == am.MODEL_OPEN_INTERVAL)
            .to_df()
        )
        is None
    )


# --------------------------------------------- 5. integrity guards that must be empty


def test_zero_count_guards_are_empty(am):
    """The five derived guards that stand in for constraints RAI cannot enforce.

    ``require(unique(...))`` is a silent no-op in 1.20.1 with and without ``emit_constraints``
    (PROBE U-04), and ``std/constraints`` has no negative-constraint vocabulary, so every claim
    a ``Property`` FD cannot express becomes a derived flag plus a zero-count assertion here.
    """
    from relationalai.semantics.std import aggregates as aggs

    from aviation_model.computed_schedule import (
        CabinDerivationDisagreement,
        PhysicalServiceDisagreement,
    )

    checks = {
        "SentinelLeak": (am.SentinelLeak, am.DailyAssignment),
        "EndEventDisagreement": (am.EndEventDisagreement, am.DailyAssignment),
        "CabinDerivationDisagreement": (CabinDerivationDisagreement, am.RouteState),
        "PhysicalServiceDisagreement": (PhysicalServiceDisagreement, am.RouteState),
    }
    offenders = {}
    for name, (flag, concept) in checks.items():
        value = scalar(
            am.model.select(aggs.count(concept).alias("n")).where(flag(concept)).to_df()
        )
        if value is not None:
            offenders[name] = int(value)
    assert not offenders, offenders


FD_PROBES = {
    # G-01: AircraftType definition attributes keyed on AC-05.
    "G-01": """
        SELECT COUNT(*) AS n FROM (
          SELECT aircraft_subseries FROM (
            SELECT DISTINCT aircraft_subseries, aircraft_family, aircraft_type,
                   aircraft_series, aircraft_manufacturer, aircraft_design_class
            FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_CONFIGURATION
            WHERE aircraft_subseries IS NOT NULL)
          GROUP BY 1 HAVING COUNT(*) > 1)
    """,
    # G-02: EngineType definition attributes keyed on AC-14.
    "G-02": """
        SELECT COUNT(*) AS n FROM (
          SELECT engine_subseries FROM (
            SELECT DISTINCT engine_subseries, engine_manufacturer, engine_family,
                   engine_type, engine_series, engine_propulsion_type
            FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_CONFIGURATION
            WHERE engine_subseries IS NOT NULL)
          GROUP BY 1 HAVING COUNT(*) > 1)
    """,
    # G-03: Airport attributes keyed on AP-01, against the bound projection.
    "G-03": """
        SELECT COUNT(*) AS n FROM (
          SELECT airport_id FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.AIRPORT_CURRENT
          GROUP BY 1 HAVING COUNT(*) > 1)
    """,
    # G-04: Airline attributes keyed on AL-01, against the bound projection.
    "G-04": """
        SELECT COUNT(*) AS n FROM (
          SELECT airline_id FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.AIRLINE_CURRENT
          GROUP BY 1 HAVING COUNT(*) > 1)
    """,
    # G-05: PassengerFlight.schedule_key, bound only from the DV-21 precedence winner.
    "G-05": """
        SELECT COUNT(*) AS n FROM (
          SELECT passenger_flight_key
          FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.PASSENGER_SOURCE_LINEAGE
          WHERE schedule_key IS NOT NULL AND is_selected_observation
          GROUP BY 1 HAVING COUNT(DISTINCT schedule_key) > 1)
    """,
    # G-06: AircraftFlight.aircraft is functional per flight id.
    "G-06": """
        SELECT COUNT(*) AS n FROM (
          SELECT flight_id FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.AIRCRAFT_FLIGHT
          GROUP BY 1 HAVING COUNT(DISTINCT aircraft_id) > 1)
    """,
}


@pytest.mark.parametrize("probe", sorted(FD_PROBES))
def test_functional_dependency_probes(probe):
    """The G-01..G-06 multiplicity gates, as zero-count assertions.

    ``SOURCE_CONTRACT.md``: "MODEL-01 may use a functional Property only after the multiplicity
    gate above passes." These are those gates, kept in the suite because two of them (G-03,
    G-04) are safe by *fixture* rather than by structure. If DATA-01 ever emits a second
    effective period for one reference entity, ``Airport.airport_name`` stops being functional
    and the model FDErrors at first evaluation - which is a named failure here in under a second
    instead of a mysterious ``RelQueryError`` twenty minutes into a demo.
    """
    assert int(sql(FD_PROBES[probe])[0]["N"]) == 0


def test_daily_assignment_multiplicity_gate():
    """No (aircraft, dimension, date) may match more than one daily assignment.

    Q03 binds two daily-assignment refs through one shared ``Aircraft`` in a single rule. The
    cross product is intended, but only because the contract guarantees "zero-or-one final
    relevant observation" per aircraft, dimension and date. If that gate regresses the Q03
    counts inflate *silently*, and the failure surfaces three phases downstream looking like a
    data bug.
    """
    n = int(
        sql(
            """
            SELECT COUNT(*) AS n FROM (
              SELECT aircraft_id, dimension, valid_from
              FROM PK_AVIATION_TEMPORAL.MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT
              GROUP BY 1,2,3 HAVING COUNT(*) > 1)
            """
        )[0]["N"]
    )
    assert n == 0


# ------------------------------------------- 6. the shared derived predicate layer


def test_bool_property_needs_explicit_comparison(am):
    """A boolean ``Property`` must be compared, never used as a bare truth filter.

    Measured here for the first time: ``where(RouteState.is_codeshare)`` returns **all 12,030**
    route states, because a bare property reference binds the value rather than testing it,
    while ``where(RouteState.is_codeshare == True)`` correctly returns the 4 codeshares. This is
    a silent wrong answer, not an error, and it is why every boolean filter in this package is
    written ``== True`` / ``== False``.
    """
    from relationalai.semantics.std import aggregates as aggs

    bare = scalar(
        am.model.select(aggs.count(am.RouteState).alias("n"))
        .where(am.RouteState.is_codeshare)
        .to_df()
    )
    compared = scalar(
        am.model.select(aggs.count(am.RouteState).alias("n"))
        .where(am.RouteState.is_codeshare == True)  # noqa: E712
        .to_df()
    )
    sql_true = int(
        sql(
            f"SELECT COUNT(*) AS n FROM {DB}.MODEL_INPUT.ROUTE_STATE WHERE IS_CODESHARE"
        )[0]["N"]
    )
    assert int(compared) == sql_true == 4
    assert int(bare) == 12030


def test_dv33_branches_are_mutually_exclusive(am):
    """Exactly one DV-33 branch fires for each frozen Q01 case.

    Mutual exclusivity is the whole point: overlapping conditions on a derived status would be
    an ``FDError``, and collapsing ``NO_RECORDED_STATE`` (inside existence, before the first
    assignment) into ``UNKNOWN_STATE`` (covered by an assignment with no resolved target) fails
    two frozen result sets. Section 5.3's ``|`` fallback chain does not compile at all - it
    raises ``[Unground Variable]`` - so the branches are built as mutually exclusive condition
    sets instead.
    """
    cases = {
        (1002, dt.date(2022, 5, 15)): "UNKNOWN_STATE",  # Q01-UNKNOWN-GAP
        (1002, dt.date(2024, 7, 1)): "OUTSIDE_EXISTENCE",  # Q01-EOL-BOUNDARY
        (1004, dt.date(2019, 6, 30)): "NO_RECORDED_STATE",  # Q01-BEFORE-FIRST
        (1001, dt.date(2022, 5, 15)): "OK",  # Q01-CANONICAL
    }
    for (aircraft_id, as_of), expected in cases.items():
        typ = am.DailyAssignment.ref(f"typ_{aircraft_id}_{as_of:%Y%m%d}")
        fired = []
        for token, conditions in am.dv33_branches(
            am.model,
            am.Aircraft,
            typ,
            as_of,
            scope=(typ.dimension == am.DIM_AIRCRAFT_TYPE,),
            exact_target=typ.aircraft_type,
        ):
            df = (
                am.model.where(am.Aircraft.id == aircraft_id, *conditions)
                .select(am.Aircraft.id.alias("aircraft_id"))
                .to_df()
            )
            if df.shape[1] and len(df):
                fired.append(token)
        assert fired == [expected], (aircraft_id, as_of, fired, expected)


def test_q03_month_end_rule_matches_sql(am):
    """The headline reusable temporal rule: two independent clocks, one calendar join.

    132 rows over exactly 120 distinct month ends, from **one** query rather than 120. The
    status clock and the type clock are separate half-open joins in the same rule and are
    visibly not aligned to each other.
    """
    from relationalai.semantics.std import aggregates as aggs

    df = am.model.select(
        am.MonthEnd.month_end.alias("month_end"),
        am.AircraftType.subseries.alias("aircraft_type_id"),
        aggs.count(am.Aircraft).per(am.MonthEnd, am.AircraftType).alias("n"),
    ).where(
        am.InServiceOnMonthEnd(am.Aircraft, am.MonthEnd, am.AircraftType),
        am.MonthEnd.month_end >= dt.date(2015, 1, 31),
        am.MonthEnd.month_end <= dt.date(2024, 12, 31),
    ).to_df()

    assert len(df) == 132
    assert df["month_end"].nunique() == 120
    assert sorted(df["aircraft_type_id"].unique()) == ["SYN-TYPE-A", "SYN-TYPE-B"]
    assert sorted({int(x) for x in df["n"]}) == [1, 2]


def test_q04_reconciliation_properties(am):
    """Two independently clocked streams side by side, never aligned to each other.

    Four rows for aircraft 1001. The type stream breaks at 2019-01-01 and the engine stream at
    2021-07-01, and neither boundary appears in the other - any attempt to merge the timelines
    produces more or fewer than four rows. ``is_type_change`` is three-valued: ``false`` on the
    first type assignment, ``true`` on the change, and absent (null) on every engine row.
    The frozen ``assignment_id`` spelling is read from DV-05, never re-derived.
    """
    df = am.model.select(
        am.DailyAssignment.dimension.alias("dimension"),
        am.DailyAssignment.daily_assignment_id.alias("assignment_id"),
        am.DailyAssignment.valid_from.alias("valid_from"),
        am.DailyAssignment.valid_to.alias("valid_to"),
        am.DailyAssignment.exact_aircraft_type_subseries.alias("type_id"),
        am.DailyAssignment.exact_engine_type_subseries.alias("engine_id"),
        am.DailyAssignment.engine_count.alias("engine_count"),
        am.DailyAssignment.mixed_engine_set_complete.alias("mixed_engine_set_complete"),
        am.DailyAssignment.previous_definition_id.alias("previous_definition_id"),
        am.DailyAssignment.is_type_change.alias("is_type_change"),
    ).where(
        am.Aircraft.id == 1001,
        am.DailyAssignment.aircraft == am.Aircraft,
        am.DailyAssignment.dimension.in_(["aircraft_type", "engine_type"]),
    ).to_df().sort_values(["dimension", "valid_from"]).reset_index(drop=True)

    assert len(df) == 4
    assert list(df["dimension"]) == [
        "aircraft_type",
        "aircraft_type",
        "engine_type",
        "engine_type",
    ]
    assert list(df["assignment_id"]) == [
        "aircraft_type|1001|2015-01-01|101001",
        "aircraft_type|1001|2019-01-01|101005",
        "engine_type|1001|2015-01-01|101001",
        "engine_type|1001|2021-07-01|101007",
    ]
    assert list(df["type_id"][:2]) == ["SYN-TYPE-A", "SYN-TYPE-B"]
    assert list(df["engine_id"][2:]) == ["SYN-ENGINE-A", "SYN-ENGINE-B"]
    assert df["previous_definition_id"].tolist()[1] == "SYN-TYPE-A"
    assert [bool(x) for x in df["is_type_change"].tolist()[:2]] == [False, True]
    assert [bool(x) for x in df["is_type_change"].isna().tolist()[2:]] == [True, True]
    assert str(df["valid_to"].iloc[1])[:10] == "9999-01-01"


def test_audit_stream_preserves_same_day_sequence(am):
    """Same-day audit observations stay distinct entities in the canonical order.

    Aircraft 1001's status stream has four observations on 2020-06-01 at row sequences 5, 10, 20
    and 30, and they receive ordinals 4, 5, 6, 7. The ``Storage -> In Service`` pair at ordinals
    6 and 7 is the zero-day spell Q02 must find; it exists **only** on the audit stream, because
    the daily projection keeps one row per aircraft/dimension/date and drops the Storage
    observation entirely.
    """
    import pandas as pd

    df = am.model.select(
        am.AuditAssignment.event_ordinal.alias("ordinal"),
        am.AuditAssignment.event_date.alias("event_date"),
        am.AuditAssignment.row_sequence.alias("row_sequence"),
        am.AuditAssignment.aircraft_status_code.alias("status"),
    ).where(
        am.Aircraft.id == 1001,
        am.AuditAssignment.aircraft == am.Aircraft,
        am.AuditAssignment.dimension == "aircraft_status",
    ).to_df().sort_values("ordinal").reset_index(drop=True)

    assert len(df) == 7
    assert [int(x) for x in df["ordinal"]] == [1, 2, 3, 4, 5, 6, 7]
    # RAI ``Date`` values arrive as pandas ``Timestamp``, not ``datetime.date``, so a naive
    # ``== dt.date(...)`` comparison silently matches nothing. Normalise before filtering.
    event_dates = pd.to_datetime(df["event_date"]).dt.date
    same_day = df[event_dates == dt.date(2020, 6, 1)]
    assert [int(x) for x in same_day["row_sequence"]] == [5, 10, 20, 30]
    assert list(df["status"][5:7]) == ["Storage", "In Service"]


def test_daily_ordinal_is_dense_per_aircraft_and_dimension(am):
    """The PyRel-computed daily ordinal must be dense 1..n in every partition.

    MODEL_INPUT has no dense ordinal on the daily stream - ``EVENT_ORDER_RANK`` violates
    density in 6 of 3,996 (aircraft, dimension) groups, measured - so this one is a real
    ``aggs.rank`` rule rather than a bound column, and it is worth asserting.
    """
    from relationalai.semantics.std import aggregates as aggs

    df = am.model.select(
        aggs.max(am.DailyAssignment.daily_ordinal).alias("mx"),
        aggs.count(am.DailyAssignment).alias("cnt"),
    ).where(
        am.Aircraft.id == 1001,
        am.DailyAssignment.aircraft == am.Aircraft,
        am.DailyAssignment.dimension == "aircraft_type",
    ).to_df()
    assert int(df["mx"].iloc[0]) == int(df["cnt"].iloc[0])


def test_snapshot_eligibility(am):
    """``is_present AND is_complete``, and nothing else. Row counts are evidence, not a gate."""
    from relationalai.semantics.std import aggregates as aggs

    got = int(
        scalar(
            am.model.select(aggs.count(am.SnapshotDate).alias("n"))
            .where(am.SnapshotDate.is_eligible())
            .to_df()
        )
    )
    expected = int(
        sql(
            f"SELECT COUNT(*) AS n FROM {DB}.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR "
            "WHERE IS_PRESENT AND IS_COMPLETE"
        )[0]["N"]
    )
    assert got == expected


def test_two_clock_predicate(am):
    """Both clocks, with their two different interval conventions, in one ``where()``.

    Knowledge is half-open and operating is inclusive at both ends. Dropping either clock
    returns a plausible, well-formed, wrong answer, which is why the shared predicates live in
    ``temporal.py`` and are never retyped in a query module.
    """
    from relationalai.semantics import distinct
    from relationalai.semantics.std import aggregates as aggs

    from aviation_model.computed_schedule import RouteStateOperatesOnWeekday

    df = am.model.select(
        distinct(
            am.Airline.airline_id.alias("airline_id"),
            am.Route.route_id.alias("route_id"),
            aggs.count(am.Schedule).per(am.Airline, am.Route).alias("active_schedule_count"),
            aggs.sum(am.RouteState.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_frequency"),
        )
    ).where(
        *am.known_on(am.RouteState, KNOWLEDGE_DATE),
        *am.operates_on(am.RouteState, OPERATING_DATE, RouteStateOperatesOnWeekday),
        am.RouteState.marketing_airline == am.Airline,
        am.RouteState.route == am.Route,
        am.RouteState.schedule == am.Schedule,
    ).to_df().sort_values(["airline_id", "route_id"]).reset_index(drop=True)

    assert len(df) == 3
    assert list(zip(df["airline_id"], df["route_id"])) == [
        ("SYN-MKT-B", "SFO->LAX"),
        ("SYN-MKT-X", "SFO->SEA"),
        ("SYN-OP-A", "SFO->LAX"),
    ]
    assert int(df.loc[df["airline_id"] == "SYN-OP-A", "active_schedule_count"].iloc[0]) == 2
    assert int(df.loc[df["airline_id"] == "SYN-OP-A", "weekly_frequency"].iloc[0]) == 10


# --------------------------------------------------------- 7. rotation and enrichment


def test_accepted_rotation_chain_and_leg_order(am):
    """A genuine chain from the link structure, not a filter-and-sort.

    ``leg_order`` is ``1 + the number of accepted-chain predecessors``, taken from the
    transitive closure over ``accepted_next_flight``. Sorting the day's legs by departure time
    would reproduce this answer on this fixture and is an explicit fail.
    """
    edges = am.model.select(
        am.AircraftFlight.flight_id.alias("flight_id"),
        am.AircraftFlight.accepted_next_flight.flight_id.alias("next_flight_id"),
    ).where(
        am.AircraftFlight.aircraft == am.Aircraft,
        am.Aircraft.id == 1001,
        am.AircraftFlight.flight_departure_date == dt.date(2026, 8, 31),
    ).to_df().sort_values("flight_id").reset_index(drop=True)

    import pandas as pd

    assert [int(x) for x in edges["flight_id"]] == [8001, 8002, 8003]
    assert [None if pd.isna(x) else int(x) for x in edges["next_flight_id"]] == [
        8002,
        8003,
        None,
    ]

    head = am.AircraftFlight.ref("head")
    chain = am.model.select(
        head.flight_id.alias("segment_id"),
        am.AircraftFlight.flight_id.alias("flight_id"),
        (am.rotation_leg_distance(head, am.AircraftFlight) + 1).alias("leg_order"),
    ).where(
        am.RotationSegmentHead(head),
        am.rotation_leg_distance(head, am.AircraftFlight),
        am.AircraftFlight.aircraft == am.Aircraft,
        am.Aircraft.id == 1001,
        am.AircraftFlight.flight_departure_date == dt.date(2026, 8, 31),
    ).to_df().sort_values("leg_order").reset_index(drop=True)

    assert [int(x) for x in chain["segment_id"]] == [8001, 8001, 8001]
    assert [int(x) for x in chain["flight_id"]] == [8001, 8002, 8003]
    assert [int(x) for x in chain["leg_order"]] == [1, 2, 3]


def test_q08_enrichment_uses_the_local_date(am):
    """Enrichment is as-of AF-06 local, never AF-07 UTC. The sharpest trap in Q08.

    All three canonical legs have AF-06 = 2026-08-31 while AF-07 = 2026-09-01. Using AF-07 would
    shift the as-of instant a day and can silently select the wrong type or engine interval;
    ``TT-US-CLOCK-AUTHORITY`` freezes the assertion. ``type_discrepancy`` is reported and never
    reconciled: leg 8002's source description disagrees with aircraft history, and the source
    value is not overwritten.
    """
    df = am.model.select(
        am.AircraftFlight.flight_id.alias("flight_id"),
        am.AircraftFlight.flight_departure_date.alias("af06_local"),
        am.AircraftFlight.flight_departure_date_utc.alias("af07_utc"),
        am.AircraftFlight.as_of_aircraft_type.subseries.alias("as_of_aircraft_type_id"),
        am.AircraftFlight.as_of_engine_type.subseries.alias("as_of_engine_type_id"),
        am.AircraftFlight.actual_source_aircraft_type.alias("actual_source_aircraft_type"),
        am.AircraftFlight.type_discrepancy.alias("type_discrepancy"),
    ).where(
        am.AircraftFlight.aircraft == am.Aircraft,
        am.Aircraft.id == 1001,
        am.AircraftFlight.flight_departure_date == dt.date(2026, 8, 31),
    ).to_df().sort_values("flight_id").reset_index(drop=True)

    import pandas as pd

    assert len(df) == 3
    # AF-06 is local and AF-07 is UTC and they differ by a day. RAI ``Date`` values come back
    # as pandas ``Timestamp``, so normalise before comparing or the assertion passes vacuously.
    assert set(pd.to_datetime(df["af06_local"]).dt.date) == {dt.date(2026, 8, 31)}
    assert set(pd.to_datetime(df["af07_utc"]).dt.date) == {dt.date(2026, 9, 1)}
    assert list(df["as_of_aircraft_type_id"]) == ["SYN-TYPE-B"] * 3
    assert list(df["as_of_engine_type_id"]) == ["SYN-ENGINE-B"] * 3
    assert [bool(x) for x in df["type_discrepancy"]] == [False, True, False]


def test_exact_fulfillment_is_the_only_source_of_the_fulfils_link(am):
    """``AircraftFlight.fulfils`` is derived from exact fulfillment only.

    ``FulfillmentCandidate`` never feeds it. That is the exact/heuristic separation made
    structural: a heuristic match can never become a confirmed link by accident.
    """
    from relationalai.semantics.std import aggregates as aggs

    fulfils = scalar(
        am.model.select(aggs.count(am.AircraftFlight).alias("n"))
        .where(am.AircraftFlight.fulfils == am.PassengerFlight)
        .to_df()
    )
    exact = int(sql(f"SELECT COUNT(*) AS n FROM {DB}.MODEL_INPUT.FULFILLMENT_EXACT")[0]["N"])
    assert int(fulfils) == exact == 4


# --------------------------------------------------------------- 8. the inventory


def test_inventory_artifact(inventory):
    """``build/design/ontology_inventory.json`` exists and describes the whole model."""
    from aviation_model.inventory import INVENTORY_PATH

    assert INVENTORY_PATH.exists()
    assert inventory["concept_count"] >= 40
    assert inventory["declared_source_count"] == 34
    assert inventory["declared_column_count"] == 749
    assert inventory["table_count"] == 34


# --------------------------------------------------------------- 9. MODEL-02 parity


def test_standalone_file_matches_the_package():
    """MODEL-02: the standalone Snowsight artifact must be the package, not a rewrite.

    Runs in a subprocess because both artifacts build a ``Model`` and a second ``Model`` in one
    interpreter makes the free ``distinct(...)`` raise ``[Ambiguous model]`` (PROBE N-02).
    Compares the full ``inspect.schema`` inventory and a set of smoke-query results.
    """
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "rai_code" / "aviation_model" / "_parity_check.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    assert report["inventory_identical"] is True, report
    assert report["smoke_identical"] is True, report
