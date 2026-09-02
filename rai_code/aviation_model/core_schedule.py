"""core_schedule.py - UC2: schedules, routes, route states and the change/amendment evidence.

**This module contains the demo's central semantic beat, and it is one line long.**

The customer's Neo4j model versions state by ``(schedule_key, valid_from)`` but hangs it off
``ROUTE`` via ``(ROUTE)-[:HAS]->(ROUTE_STATE)``. A generic SCD Type 2 builder has exactly one
structural assumption - at most one open ``valid_to`` per parent key - so their builder has to be
told, per relationship, that the partition is ``schedule_key`` and not the parent ``route``.
Nothing in the graph schema records that. Get it wrong and you either close states that should
stay open or you raise an integrity error on a route that legitimately has hundreds of
concurrent open schedules.

In RAI there is nothing to relax, because there was never a constraint to relax:

.. code-block:: python

    RouteState = model.Concept("RouteState", identify_by={"route_state_key": String})

``Route`` does not appear in that identity. The versioning partition is therefore a structural,
readable property of the ontology sitting in one line a reviewer can check, rather than a
parameter passed to a builder. And because cardinality in RAI is declared per relationship and
points one way, ``Route.states`` - an ``.alt()`` reading over the same fields as
``RouteState.route`` - carries no cardinality claim at all. Multi-open is the default; single-open
is what you would have to opt into.

Measured, live: at knowledge date 2026-08-31 the route ``SFO->LAX`` has **1,339 concurrent open
route states**, and one query returns them without error. The mirror-image mistake is one
reversed arrow away and fails loudly - ``Route.current_state = model.Property(...)`` raises
``FDError: Found non-unique values`` naming the offending relation and printing the two
conflicting hashes. Note for the talk track: it fails at the **first evaluation** of the
relation, after 13-19 seconds of engine work, not at define time. Saying "define time" on stage
would be a factual error the audience can check on screen.

One honest limitation, stated because the credibility of the limitations list matters: RAI
cannot *express* "this route may have many concurrent open states" as a positive assertion.
``SD/std/constraints.py`` offers ``unique``, ``exclusive``, ``anyof`` and ``oneof`` and nothing
else - there is no minimum-cardinality or negative-constraint vocabulary. The property is proved
by a query returning ``open_states > 1``, which is what HT-18 asks for, not by a declaration.

``Schedule`` is identity-only, deliberately. SS-02 ``schedule_key_readable`` is tempting to hang
on it and is per-*observation* lineage that can legitimately differ across snapshots for the
same key, so a ``Property`` on ``Schedule`` would ``FDError``. It lives on ``RouteState`` and on
``ScheduleObservation`` instead.
"""

from relationalai.semantics import Date, String

from ._binding import bind_scalars, scalar_properties
from .constants import RESOLUTION_EXACT
from .core_reference import Airline, Airport, SnapshotDate
from .model import model
from .sources import (
    MI_ROUTE,
    MI_ROUTE_STATE,
    MI_ROUTE_STATE_LINEAGE,
    MI_SCHEDULE_AMENDMENT_CANDIDATE,
    MI_SCHEDULE_AMENDMENT_GROUP,
    MI_SCHEDULE_AMENDMENT_GROUP_MEMBER,
    MI_SCHEDULE_AMENDMENT_SIDE,
    MI_SCHEDULE_CANONICAL_OBSERVATION,
    MI_SCHEDULE_COMPARISON,
    MI_SCHEDULE_EXACT_CHANGE,
    SCHEMA_MI_ROUTE,
    SCHEMA_MI_ROUTE_STATE,
    SCHEMA_MI_ROUTE_STATE_LINEAGE,
    SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE,
    SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP,
    SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER,
    SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE,
    SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION,
    SCHEMA_MI_SCHEDULE_COMPARISON,
    SCHEMA_MI_SCHEDULE_EXACT_CHANGE,
)

# --- Schedule (SS-01) - identity only ---------------------------------------------

Schedule = model.Concept("Schedule", identify_by={"schedule_key": String})

model.define(Schedule.new(schedule_key=MI_SCHEDULE_CANONICAL_OBSERVATION.schedule_key))
model.define(Schedule.new(schedule_key=MI_ROUTE_STATE.schedule_key))

# --- Route (DV-12) - carrier-agnostic and directional ------------------------------

Route = model.Concept("Route", identify_by={"route_id": String})

_route_scalars = scalar_properties(Route, SCHEMA_MI_ROUTE, exclude=("route_id",))
model.define(Route.new(route_id=MI_ROUTE.route_id))
bind_scalars(Route, MI_ROUTE, {"route_id": MI_ROUTE.route_id}, _route_scalars)

# Two same-type slots, so two separately role-labelled Properties rather than one two-slot
# Relationship. With a single Relationship, ``define(...)`` silently binds both slots to
# whichever column is listed first, collapsing origin and destination into the same entity.
Route.origin_airport = model.Property(f"{Route:route} starts at {Airport:origin_airport}")
Route.destination_airport = model.Property(
    f"{Route:route} ends at {Airport:destination_airport}"
)
model.define(
    Route.lookup(route_id=MI_ROUTE.route_id).origin_airport(
        Airport.lookup(airport_id=MI_ROUTE.origin_airport_id)
    )
).where(MI_ROUTE.origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    Route.lookup(route_id=MI_ROUTE.route_id).destination_airport(
        Airport.lookup(airport_id=MI_ROUTE.destination_airport_id)
    )
).where(MI_ROUTE.destination_airport_resolution_status == RESOLUTION_EXACT)

# --- RouteState (DV-13) - the multi-open case -------------------------------------

RouteState = model.Concept("RouteState", identify_by={"route_state_key": String})

_route_state_scalars = scalar_properties(
    RouteState, SCHEMA_MI_ROUTE_STATE, exclude=("route_state_key",)
)
model.define(RouteState.new(route_state_key=MI_ROUTE_STATE.route_state_key))
bind_scalars(
    RouteState,
    MI_ROUTE_STATE,
    {"route_state_key": MI_ROUTE_STATE.route_state_key},
    _route_state_scalars,
)

# The FD points from the state to its parents, which is the functional direction. Each state has
# exactly one route and one schedule; a route has as many concurrent states as the source says.
RouteState.route = model.Property(f"{RouteState:state} covers {Route:route}")
RouteState.schedule = model.Property(f"{RouteState:state} versions {Schedule:schedule}")

model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).route(
        Route.lookup(route_id=MI_ROUTE_STATE.route_id)
    )
)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).schedule(
        Schedule.lookup(schedule_key=MI_ROUTE_STATE.schedule_key)
    )
)

# The Neo4j ``HAS`` edge, recovered exactly. An ``.alt()`` reading refers to the *same*
# underlying relationship fields under a different name, so it adds a name and never an inverse
# FD. This is the line that makes multi-open free.
Route.states = RouteState.route.alt(f"{Route:route} has state {RouteState:state}")
Schedule.states = RouteState.schedule.alt(
    f"{Schedule:schedule} has version {RouteState:state}"
)

# DELIBERATELY ABSENT, and this comment must survive every refactor:
#   there is no ``unique(...)`` over the Route slot of ``Route.states``, and no
#   ``Route.current_state`` Property. SOURCE_CONTRACT.md: the one-open-per-route constraint is
#   *prohibited*. See constraints.py, where the absence is recorded next to the assertions that
#   are present.

# --- Carrier roles: two Properties, never one generic ``airline`` -----------------
#
# ATTRIBUTE_AUTHORITY.md: "SS-04 and SS-05 are separate carrier roles. No generic airline owner
# exists." The ``carrier_role`` query parameter selects which Property a query traverses, and a
# missing role is a clarification state at the API boundary (P0-09.1), never a default.
#
# Only an EXACT cardinality-one resolution creates the link. An ambiguous or unresolved carrier
# code cannot produce an airline-level market at all, and the raw code stays bound as a string so
# a failed resolution still shows the code rather than vanishing.

RouteState.marketing_airline = model.Property(
    f"{RouteState:state} marketed by {Airline:marketing_airline}"
)
RouteState.operating_airline = model.Property(
    f"{RouteState:state} operated by {Airline:operating_airline}"
)
RouteState.codeshare_airline = model.Property(
    f"{RouteState:state} codeshared with {Airline:codeshare_airline}"
)

model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).marketing_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.marketing_airline_id)
    )
).where(MI_ROUTE_STATE.marketing_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).operating_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.operating_airline_id)
    )
).where(MI_ROUTE_STATE.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).codeshare_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.codeshare_airline_id)
    )
).where(MI_ROUTE_STATE.codeshare_airline_resolution_status == RESOLUTION_EXACT)

Airline.commercializes = RouteState.marketing_airline.alt(
    f"{Airline:marketing_airline} commercializes {RouteState:state}"
)
Airline.operates = RouteState.operating_airline.alt(
    f"{Airline:operating_airline} operates {RouteState:state}"
)

RouteState.origin_airport = model.Property(
    f"{RouteState:state} departs {Airport:origin_airport}"
)
RouteState.destination_airport = model.Property(
    f"{RouteState:state} arrives {Airport:destination_airport}"
)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).origin_airport(
        Airport.lookup(airport_id=MI_ROUTE_STATE.origin_airport_id)
    )
).where(MI_ROUTE_STATE.origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).destination_airport(
        Airport.lookup(airport_id=MI_ROUTE_STATE.destination_airport_id)
    )
).where(MI_ROUTE_STATE.destination_airport_resolution_status == RESOLUTION_EXACT)

# --- RouteStateSnapshotLineage ----------------------------------------------------
#
# Many contributing snapshots coalesce into one route state, so this is an association concept
# with its own identity rather than a property. Grain verified live: 60,076 rows, 60,076 distinct
# (route_state_key, publish_date, normalized_row_hash) tuples.

RouteStateSnapshotLineage = model.Concept(
    "RouteStateSnapshotLineage",
    identify_by={"route_state": RouteState, "publish_date": Date, "row_hash": String},
)

_rs_lineage_scalars = scalar_properties(
    RouteStateSnapshotLineage,
    SCHEMA_MI_ROUTE_STATE_LINEAGE,
    exclude=("route_state_key", "publish_date", "normalized_row_hash"),
)


def _rs_lineage_key() -> dict:
    return {
        "route_state": RouteState.lookup(
            route_state_key=MI_ROUTE_STATE_LINEAGE.route_state_key
        ),
        "publish_date": MI_ROUTE_STATE_LINEAGE.publish_date,
        "row_hash": MI_ROUTE_STATE_LINEAGE.normalized_row_hash,
    }


model.define(RouteStateSnapshotLineage.new(**_rs_lineage_key()))
bind_scalars(
    RouteStateSnapshotLineage,
    MI_ROUTE_STATE_LINEAGE,
    _rs_lineage_key(),
    _rs_lineage_scalars,
)

RouteState.lineage = model.Relationship(
    f"{RouteState:state} was contributed by {RouteStateSnapshotLineage:lineage}"
)
model.define(RouteState.lineage(RouteStateSnapshotLineage)).where(
    RouteStateSnapshotLineage.route_state == RouteState
)

# --- ScheduleObservation (SS-01, SS-03) -------------------------------------------
#
# The canonical per-snapshot observation with the watched SS-04..SS-38 payload. Grain verified
# live: 69,998 rows, 69,998 distinct (schedule_key, publish_date). This is the concept Q05
# compares across adjacent eligible snapshot dates.

ScheduleObservation = model.Concept(
    "ScheduleObservation", identify_by={"schedule": Schedule, "publish_date": Date}
)

_observation_scalars = scalar_properties(
    ScheduleObservation,
    SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION,
    exclude=("schedule_key", "publish_date"),
)


def _observation_key() -> dict:
    return {
        "schedule": Schedule.lookup(
            schedule_key=MI_SCHEDULE_CANONICAL_OBSERVATION.schedule_key
        ),
        "publish_date": MI_SCHEDULE_CANONICAL_OBSERVATION.publish_date,
    }


model.define(ScheduleObservation.new(**_observation_key()))
bind_scalars(
    ScheduleObservation,
    MI_SCHEDULE_CANONICAL_OBSERVATION,
    _observation_key(),
    _observation_scalars,
)

Schedule.observations = model.Relationship(
    f"{Schedule:schedule} was observed as {ScheduleObservation:observation}"
)
model.define(Schedule.observations(ScheduleObservation)).where(
    ScheduleObservation.schedule == Schedule
)

# ROUTE_ID is non-null on 69,993 of 69,998 observations; the five without one keep their identity
# and simply carry no route fact, which is the left-preserving behaviour P0-12.3 requires.
ScheduleObservation.route = model.Property(
    f"{ScheduleObservation:observation} covers {Route:route}"
)
model.define(
    ScheduleObservation.lookup(**_observation_key()).route(
        Route.lookup(route_id=MI_SCHEDULE_CANONICAL_OBSERVATION.route_id)
    )
)

ScheduleObservation.snapshot = model.Property(
    f"{ScheduleObservation:observation} was published on {SnapshotDate:snapshot}"
)
model.define(
    ScheduleObservation.lookup(**_observation_key()).snapshot(
        SnapshotDate.lookup(
            expected_publish_date=MI_SCHEDULE_CANONICAL_OBSERVATION.publish_date
        )
    )
)

# --- ScheduleComparison (DV-34) ---------------------------------------------------
#
# A Concept and not a per-invocation parameter, because Q05 must emit ``comparison_date``,
# ``previous_knowledge_date`` and ``crosses_snapshot_gap`` per comparison, and those are facts
# derived from the eligible ``SnapshotDate`` sequence rather than inputs supplied by the caller.
# Seven comparisons exist in the fixture.

ScheduleComparison = model.Concept("ScheduleComparison", identify_by={"comparison_id": String})

_comparison_scalars = scalar_properties(
    ScheduleComparison, SCHEMA_MI_SCHEDULE_COMPARISON, exclude=("comparison_id",)
)
model.define(ScheduleComparison.new(comparison_id=MI_SCHEDULE_COMPARISON.comparison_id))
bind_scalars(
    ScheduleComparison,
    MI_SCHEDULE_COMPARISON,
    {"comparison_id": MI_SCHEDULE_COMPARISON.comparison_id},
    _comparison_scalars,
)

ScheduleComparison.comparison_snapshot = model.Property(
    f"{ScheduleComparison:comparison} compares {SnapshotDate:comparison_snapshot}"
)
ScheduleComparison.previous_snapshot = model.Property(
    f"{ScheduleComparison:comparison} against {SnapshotDate:previous_snapshot}"
)
model.define(
    ScheduleComparison.lookup(
        comparison_id=MI_SCHEDULE_COMPARISON.comparison_id
    ).comparison_snapshot(
        SnapshotDate.lookup(expected_publish_date=MI_SCHEDULE_COMPARISON.comparison_date)
    )
)
model.define(
    ScheduleComparison.lookup(
        comparison_id=MI_SCHEDULE_COMPARISON.comparison_id
    ).previous_snapshot(
        SnapshotDate.lookup(
            expected_publish_date=MI_SCHEDULE_COMPARISON.previous_knowledge_date
        )
    )
)

# --- ScheduleExactChange ----------------------------------------------------------
#
# Exact presence-and-content facts. They stand on their own and are never consumed or replaced
# by the conservative amendment evidence below - NEO4J_PARITY_MATRIX.md lists "a candidate key
# shift is an exact schedule amendment" as a prohibited statement.
#
# Identity is the full four-tuple. FIELD_NAME is 100% non-null across all 12,040 rows (measured;
# a nullable identity component would silently drop the row - PROBE E3f took 48,000 rows down to
# 1 that way), and the tuple is unique.

ScheduleExactChange = model.Concept(
    "ScheduleExactChange",
    identify_by={
        "comparison": ScheduleComparison,
        "schedule_key": String,
        "change_kind": String,
        "field_name": String,
    },
)

_exact_change_scalars = scalar_properties(
    ScheduleExactChange,
    SCHEMA_MI_SCHEDULE_EXACT_CHANGE,
    exclude=("comparison_id", "schedule_key", "change_kind", "field_name"),
)


def _exact_change_key() -> dict:
    return {
        "comparison": ScheduleComparison.lookup(
            comparison_id=MI_SCHEDULE_EXACT_CHANGE.comparison_id
        ),
        "schedule_key": MI_SCHEDULE_EXACT_CHANGE.schedule_key,
        "change_kind": MI_SCHEDULE_EXACT_CHANGE.change_kind,
        "field_name": MI_SCHEDULE_EXACT_CHANGE.field_name,
    }


model.define(ScheduleExactChange.new(**_exact_change_key()))
bind_scalars(
    ScheduleExactChange,
    MI_SCHEDULE_EXACT_CHANGE,
    _exact_change_key(),
    _exact_change_scalars,
)

ScheduleExactChange.schedule = model.Property(
    f"{ScheduleExactChange:change} changed {Schedule:schedule}"
)
model.define(
    ScheduleExactChange.lookup(**_exact_change_key()).schedule(
        Schedule.lookup(schedule_key=MI_SCHEDULE_EXACT_CHANGE.schedule_key)
    )
)

# --- Amendment evidence (DV-35, DV-36, DV-37) -------------------------------------
#
# Kept structurally separate from the exact changes. A key-shift pair is reported as
# ``CANDIDATE_UNIQUE`` with ``exactness = CANDIDATE``, never promoted to a modification; where
# one removal is compatible with two additions the answer is an ambiguous group plus its members
# at LOW confidence with no pair chosen. Picking a winner by any tie-break is wrong.
#
# ``AMENDMENT_GROUP_ID`` is non-null on only 3 of 12,029 member rows (unpaired evidence carries
# none, per D-0020 A6), so the member identity is its own id column and the group link is an
# optional Property.

ScheduleAmendmentSide = model.Concept(
    "ScheduleAmendmentSide",
    identify_by={"comparison": ScheduleComparison, "schedule_key": String, "side": String},
)

_amendment_side_scalars = scalar_properties(
    ScheduleAmendmentSide,
    SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE,
    exclude=("comparison_id", "schedule_key", "side"),
)


def _amendment_side_key() -> dict:
    return {
        "comparison": ScheduleComparison.lookup(
            comparison_id=MI_SCHEDULE_AMENDMENT_SIDE.comparison_id
        ),
        "schedule_key": MI_SCHEDULE_AMENDMENT_SIDE.schedule_key,
        "side": MI_SCHEDULE_AMENDMENT_SIDE.side,
    }


model.define(ScheduleAmendmentSide.new(**_amendment_side_key()))
bind_scalars(
    ScheduleAmendmentSide,
    MI_SCHEDULE_AMENDMENT_SIDE,
    _amendment_side_key(),
    _amendment_side_scalars,
)

ScheduleAmendmentCandidate = model.Concept(
    "ScheduleAmendmentCandidate", identify_by={"candidate_id": String}
)
_amendment_candidate_scalars = scalar_properties(
    ScheduleAmendmentCandidate,
    SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE,
    exclude=("amendment_candidate_id",),
)
model.define(
    ScheduleAmendmentCandidate.new(
        candidate_id=MI_SCHEDULE_AMENDMENT_CANDIDATE.amendment_candidate_id
    )
)
bind_scalars(
    ScheduleAmendmentCandidate,
    MI_SCHEDULE_AMENDMENT_CANDIDATE,
    {"candidate_id": MI_SCHEDULE_AMENDMENT_CANDIDATE.amendment_candidate_id},
    _amendment_candidate_scalars,
)

ScheduleAmendmentGroup = model.Concept(
    "ScheduleAmendmentGroup", identify_by={"group_id": String}
)
_amendment_group_scalars = scalar_properties(
    ScheduleAmendmentGroup,
    SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP,
    exclude=("amendment_group_id",),
)
model.define(
    ScheduleAmendmentGroup.new(group_id=MI_SCHEDULE_AMENDMENT_GROUP.amendment_group_id)
)
bind_scalars(
    ScheduleAmendmentGroup,
    MI_SCHEDULE_AMENDMENT_GROUP,
    {"group_id": MI_SCHEDULE_AMENDMENT_GROUP.amendment_group_id},
    _amendment_group_scalars,
)

ScheduleAmendmentGroupMember = model.Concept(
    "ScheduleAmendmentGroupMember", identify_by={"member_id": String}
)
_amendment_member_scalars = scalar_properties(
    ScheduleAmendmentGroupMember,
    SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER,
    exclude=("amendment_group_member_id",),
)
model.define(
    ScheduleAmendmentGroupMember.new(
        member_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id
    )
)
bind_scalars(
    ScheduleAmendmentGroupMember,
    MI_SCHEDULE_AMENDMENT_GROUP_MEMBER,
    {"member_id": MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id},
    _amendment_member_scalars,
)

ScheduleAmendmentGroupMember.group = model.Property(
    f"{ScheduleAmendmentGroupMember:member} belongs to {ScheduleAmendmentGroup:group}"
)
model.define(
    ScheduleAmendmentGroupMember.lookup(
        member_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id
    ).group(
        ScheduleAmendmentGroup.lookup(
            group_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_id
        )
    )
)
ScheduleAmendmentGroup.members = model.Relationship(
    f"{ScheduleAmendmentGroup:group} has member {ScheduleAmendmentGroupMember:member}"
)
model.define(ScheduleAmendmentGroup.members(ScheduleAmendmentGroupMember)).where(
    ScheduleAmendmentGroupMember.group == ScheduleAmendmentGroup
)
