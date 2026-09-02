"""core_flight.py - the plan side, the actual side, and the optional bridge between them.

Passenger flights and aircraft flights are **separate** and stay separate (BRIEF.md
non-negotiable). Fulfillment is optional and asymmetric, and that asymmetry is the single
cleanest demonstration in the whole model of what a directed ``Property`` plus an ``.alt()``
inverse buys you:

* ``AircraftFlight.fulfils`` is a ``Property``. The FD ``leg -> plan`` is enforced: one actual
  leg fulfils at most one planned service.
* ``PassengerFlight.fulfilled_by`` is the ``.alt()`` inverse over the *same* fields, so it
  carries no FD. The stopover case - one planned passenger service fulfilled by several actual
  legs - loads without error.

A property-graph edge cannot express that pair without an out-of-band constraint.

``ExactFulfillment`` stays a separate association concept even though ``fulfils`` exists,
because P0-10.6 requires candidates to be stored separately from confirmed fulfillment and the
association carries DV-39, the evidence and the sanity-check outcome. ``fulfils`` is derived
from ``ExactFulfillment`` **only**; ``FulfillmentCandidate`` never feeds it. That makes the
exact/heuristic separation structural rather than a convention.

Two code systems that must not be joined to each other: actual endpoints are ``SYN-AP-*``
internal ids resolved against AP-01, planned endpoints are public IATA labels resolved against
AP-04. Joining actual legs on IATA silently returns nothing.
"""

from relationalai.semantics import Integer, Number, String

from ._binding import bind_scalars, scalar_properties
from .constants import RESOLUTION_EXACT
from .core_aircraft import Aircraft
from .core_reference import Airline, Airport
from .core_schedule import Schedule
from .model import model
from .sources import (
    MI_AIRCRAFT_FLIGHT,
    MI_FULFILLMENT_AMBIGUOUS_GROUP,
    MI_FULFILLMENT_CANDIDATE,
    MI_FULFILLMENT_EXACT,
    MI_PASSENGER_FLIGHT_CANONICAL,
    MI_PASSENGER_FLIGHT_INVALID,
    MI_PASSENGER_PLANNED_LEG,
    MI_PASSENGER_SOURCE_LINEAGE,
    MI_PASSENGER_SOURCE_QUARANTINE,
    MI_ROTATION_LINK_VALIDATION,
    SCHEMA_MI_AIRCRAFT_FLIGHT,
    SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP,
    SCHEMA_MI_FULFILLMENT_CANDIDATE,
    SCHEMA_MI_FULFILLMENT_EXACT,
    SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL,
    SCHEMA_MI_PASSENGER_FLIGHT_INVALID,
    SCHEMA_MI_PASSENGER_PLANNED_LEG,
    SCHEMA_MI_PASSENGER_SOURCE_LINEAGE,
    SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE,
    SCHEMA_MI_ROTATION_LINK_VALIDATION,
)

# --- PassengerFlight (DV-20) - the plan side --------------------------------------

PassengerFlight = model.Concept(
    "PassengerFlight", identify_by={"passenger_flight_key": String}
)

_passenger_scalars = scalar_properties(
    PassengerFlight,
    SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL,
    exclude=("passenger_flight_key",),
)
model.define(
    PassengerFlight.new(
        passenger_flight_key=MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key
    )
)
bind_scalars(
    PassengerFlight,
    MI_PASSENGER_FLIGHT_CANONICAL,
    {"passenger_flight_key": MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key},
    _passenger_scalars,
)

# PH-02 ``schedule_key`` is bound as a ``Property`` from the canonical row, which by
# construction carries the DV-21 precedence-winning lineage observation's value. PROBE G-05
# passed only *vacuously* against the raw lineage - the one coalescing DV-20 key that absorbs
# two lineage rows has NULL PH-02 on both - so relying on that pass would have been relying on a
# fixture accident. Binding from the winner makes the functional dependency true by
# construction, which is what P0-10.3 requires anyway. Non-null on 7,951 of 19,446 canonical
# rows after the D-0023 enrichment; it was 1 of 19,996 before, which is why the binding had to
# be true by construction rather than by fixture accident.
PassengerFlight.schedule = model.Property(
    f"{PassengerFlight:plan} realises {Schedule:schedule}"
)
model.define(
    PassengerFlight.lookup(
        passenger_flight_key=MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key
    ).schedule(Schedule.lookup(schedule_key=MI_PASSENGER_FLIGHT_CANONICAL.schedule_key))
)

PassengerFlight.marketing_airline = model.Property(
    f"{PassengerFlight:plan} marketed by {Airline:marketing_airline}"
)
PassengerFlight.operating_airline = model.Property(
    f"{PassengerFlight:plan} operated by {Airline:operating_airline}"
)
PassengerFlight.planned_origin_airport = model.Property(
    f"{PassengerFlight:plan} planned from {Airport:planned_origin_airport}"
)
PassengerFlight.planned_destination_airport = model.Property(
    f"{PassengerFlight:plan} planned to {Airport:planned_destination_airport}"
)


def _plan_key() -> dict:
    return {"passenger_flight_key": MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key}


model.define(
    PassengerFlight.lookup(**_plan_key()).marketing_airline(
        Airline.lookup(airline_id=MI_PASSENGER_FLIGHT_CANONICAL.marketing_airline_id)
    )
).where(MI_PASSENGER_FLIGHT_CANONICAL.marketing_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    PassengerFlight.lookup(**_plan_key()).operating_airline(
        Airline.lookup(airline_id=MI_PASSENGER_FLIGHT_CANONICAL.operating_airline_id)
    )
).where(MI_PASSENGER_FLIGHT_CANONICAL.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    PassengerFlight.lookup(**_plan_key()).planned_origin_airport(
        Airport.lookup(airport_id=MI_PASSENGER_FLIGHT_CANONICAL.planned_origin_airport_id)
    )
).where(
    MI_PASSENGER_FLIGHT_CANONICAL.planned_origin_airport_resolution_status
    == RESOLUTION_EXACT
)
model.define(
    PassengerFlight.lookup(**_plan_key()).planned_destination_airport(
        Airport.lookup(
            airport_id=MI_PASSENGER_FLIGHT_CANONICAL.planned_destination_airport_id
        )
    )
).where(
    MI_PASSENGER_FLIGHT_CANONICAL.planned_destination_airport_resolution_status
    == RESOLUTION_EXACT
)

# --- PassengerSourceLineage -------------------------------------------------------
#
# Historical and forward lineage are BOTH retained (SOURCE_CONTRACT.md), which is why this is an
# association concept rather than a set of columns on the flight. ``IS_SELECTED_OBSERVATION``,
# ``SOURCE_PRECEDENCE_RANK`` and ``SELECTION_RANK`` are carried so the union precedence is
# auditable rather than implicit. Grain verified live: 19,998 rows, 19,998 distinct tuples.

PassengerSourceLineage = model.Concept(
    "PassengerSourceLineage",
    identify_by={
        "passenger_flight": PassengerFlight,
        "source_system": String,
        "source_row_token": String,
    },
)

_lineage_scalars = scalar_properties(
    PassengerSourceLineage,
    SCHEMA_MI_PASSENGER_SOURCE_LINEAGE,
    exclude=("passenger_flight_key", "source_system", "source_row_token"),
)


def _lineage_key() -> dict:
    return {
        "passenger_flight": PassengerFlight.lookup(
            passenger_flight_key=MI_PASSENGER_SOURCE_LINEAGE.passenger_flight_key
        ),
        "source_system": MI_PASSENGER_SOURCE_LINEAGE.source_system,
        "source_row_token": MI_PASSENGER_SOURCE_LINEAGE.source_row_token,
    }


model.define(PassengerSourceLineage.new(**_lineage_key()))
bind_scalars(
    PassengerSourceLineage,
    MI_PASSENGER_SOURCE_LINEAGE,
    _lineage_key(),
    _lineage_scalars,
)

PassengerFlight.lineage = model.Relationship(
    f"{PassengerFlight:plan} was observed as {PassengerSourceLineage:lineage}"
)
model.define(PassengerFlight.lineage(PassengerSourceLineage)).where(
    PassengerSourceLineage.passenger_flight == PassengerFlight
)

# --- PassengerPlannedLeg ----------------------------------------------------------
#
# The ordered planned station sequence. A single planned service with intermediate stops has
# several legs, which is what makes the stopover fulfillment case real.
#
# ``LEG_INDEX`` is ``NUMBER(9,0)`` and is declared ``Number.size(18, 0)``, not ``Integer`` and
# not ``Number.size(9, 0)``. The SDK buckets integer precision by bit width, so every
# ``NUMBER(p,0)`` with ``p <= 18`` discovers as ``Decimal(18,0)``; declaring the column's own
# precision instead relies on an undocumented leniency, and declaring ``Integer``
# (``Number.size(38, 0)``) would be a silent all-NaN column. See ``_regen_sources.derive_type``
# for the ``NUMBER(19,0)`` case where getting this wrong cost 600 values.

PassengerPlannedLeg = model.Concept(
    "PassengerPlannedLeg",
    identify_by={"passenger_flight": PassengerFlight, "leg_index": Number.size(18, 0)},
)

_planned_leg_scalars = scalar_properties(
    PassengerPlannedLeg,
    SCHEMA_MI_PASSENGER_PLANNED_LEG,
    exclude=("passenger_flight_key", "leg_index"),
)


def _planned_leg_key() -> dict:
    return {
        "passenger_flight": PassengerFlight.lookup(
            passenger_flight_key=MI_PASSENGER_PLANNED_LEG.passenger_flight_key
        ),
        "leg_index": MI_PASSENGER_PLANNED_LEG.leg_index,
    }


model.define(PassengerPlannedLeg.new(**_planned_leg_key()))
bind_scalars(
    PassengerPlannedLeg,
    MI_PASSENGER_PLANNED_LEG,
    _planned_leg_key(),
    _planned_leg_scalars,
)

PassengerFlight.planned_legs = model.Relationship(
    f"{PassengerFlight:plan} has planned leg {PassengerPlannedLeg:leg}"
)
model.define(PassengerFlight.planned_legs(PassengerPlannedLeg)).where(
    PassengerPlannedLeg.passenger_flight == PassengerFlight
)

# --- Invalid and quarantined passenger observations -------------------------------
#
# Retained with a deterministic identity plus a reason, never dropped. An observation that
# cannot form a DV-20 key is a fact about the source, not an absence.

InvalidPassengerObservation = model.Concept(
    "InvalidPassengerObservation",
    identify_by={"source_system": String, "stable_source_row_id": Integer},
)
_invalid_scalars = scalar_properties(
    InvalidPassengerObservation,
    SCHEMA_MI_PASSENGER_FLIGHT_INVALID,
    exclude=("source_system", "stable_source_row_id"),
)
model.define(
    InvalidPassengerObservation.new(
        source_system=MI_PASSENGER_FLIGHT_INVALID.source_system,
        stable_source_row_id=MI_PASSENGER_FLIGHT_INVALID.stable_source_row_id,
    )
)
bind_scalars(
    InvalidPassengerObservation,
    MI_PASSENGER_FLIGHT_INVALID,
    {
        "source_system": MI_PASSENGER_FLIGHT_INVALID.source_system,
        "stable_source_row_id": MI_PASSENGER_FLIGHT_INVALID.stable_source_row_id,
    },
    _invalid_scalars,
)

PassengerSourceQuarantine = model.Concept(
    "PassengerSourceQuarantine", identify_by={"quarantine_id": String}
)
_passenger_quarantine_scalars = scalar_properties(
    PassengerSourceQuarantine,
    SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE,
    exclude=("quarantine_id",),
)
model.define(
    PassengerSourceQuarantine.new(
        quarantine_id=MI_PASSENGER_SOURCE_QUARANTINE.quarantine_id
    )
)
bind_scalars(
    PassengerSourceQuarantine,
    MI_PASSENGER_SOURCE_QUARANTINE,
    {"quarantine_id": MI_PASSENGER_SOURCE_QUARANTINE.quarantine_id},
    _passenger_quarantine_scalars,
)

# --- AircraftFlight (AF-01) - the actual side -------------------------------------

AircraftFlight = model.Concept("AircraftFlight", identify_by={"flight_id": Integer})

_flight_scalars = scalar_properties(
    AircraftFlight, SCHEMA_MI_AIRCRAFT_FLIGHT, exclude=("flight_id",)
)
model.define(AircraftFlight.new(flight_id=MI_AIRCRAFT_FLIGHT.flight_id))
bind_scalars(
    AircraftFlight,
    MI_AIRCRAFT_FLIGHT,
    {"flight_id": MI_AIRCRAFT_FLIGHT.flight_id},
    _flight_scalars,
)


def _leg_key() -> dict:
    return {"flight_id": MI_AIRCRAFT_FLIGHT.flight_id}


# PROBE G-06: ``AircraftFlight.aircraft`` is functional (zero violating flight ids) but the
# inverse is 1..13 flights per aircraft, so the inverse must be multi-valued. Easy to get
# backwards, and a ``Property`` on the inverse would FDError on the first aircraft with two legs.
AircraftFlight.aircraft = model.Property(f"{AircraftFlight:leg} was flown by {Aircraft:aircraft}")
model.define(
    AircraftFlight.lookup(**_leg_key()).aircraft(
        Aircraft.lookup(id=MI_AIRCRAFT_FLIGHT.aircraft_id)
    )
)
Aircraft.actual_flights = AircraftFlight.aircraft.alt(
    f"{Aircraft:aircraft} flew {AircraftFlight:leg}"
)

# Two same-type slots again, so two role-labelled Properties. AF-09 ``actual`` arrival is
# DV-45 and is the continuity endpoint; AF-10 ``diverted`` never repairs it.
AircraftFlight.actual_origin = model.Property(
    f"{AircraftFlight:leg} started at {Airport:actual_origin}"
)
AircraftFlight.actual_destination = model.Property(
    f"{AircraftFlight:leg} ended at {Airport:actual_destination}"
)
AircraftFlight.diverted_airport = model.Property(
    f"{AircraftFlight:leg} diverted to {Airport:diverted_airport}"
)
model.define(
    AircraftFlight.lookup(**_leg_key()).actual_origin(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.actual_origin_airport_id)
    )
).where(MI_AIRCRAFT_FLIGHT.actual_origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    AircraftFlight.lookup(**_leg_key()).actual_destination(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.actual_destination_airport_id)
    )
).where(
    MI_AIRCRAFT_FLIGHT.actual_destination_airport_resolution_status == RESOLUTION_EXACT
)
model.define(
    AircraftFlight.lookup(**_leg_key()).diverted_airport(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.diverted_airport_id)
    )
).where(MI_AIRCRAFT_FLIGHT.diverted_airport_resolution_status == RESOLUTION_EXACT)

AircraftFlight.operating_airline = model.Property(
    f"{AircraftFlight:leg} was operated by {Airline:operating_airline}"
)
AircraftFlight.marketing_airline = model.Property(
    f"{AircraftFlight:leg} was marketed by {Airline:marketing_airline}"
)
model.define(
    AircraftFlight.lookup(**_leg_key()).operating_airline(
        Airline.lookup(airline_id=MI_AIRCRAFT_FLIGHT.operating_airline_id)
    )
).where(MI_AIRCRAFT_FLIGHT.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    AircraftFlight.lookup(**_leg_key()).marketing_airline(
        Airline.lookup(airline_id=MI_AIRCRAFT_FLIGHT.marketing_airline_id)
    )
).where(MI_AIRCRAFT_FLIGHT.marketing_airline_resolution_status == RESOLUTION_EXACT)

# The raw AF-20 self-reference, chained through a lookup on both ends so the target must already
# exist. PROBE G-06 found exactly one dangling ``NEXT_FLIGHT_ID`` in the fixture - the
# ``MISSING_TARGET`` anomaly - and this binding silently produces no fact for it, which is the
# intended behaviour. ``RotationLinkValidation`` is the thing that surfaces it.
AircraftFlight.next_flight_raw = model.Property(
    f"{AircraftFlight:leg} points to next {AircraftFlight:next_leg_raw}"
)
model.define(
    AircraftFlight.lookup(flight_id=MI_AIRCRAFT_FLIGHT.flight_id).next_flight_raw(
        AircraftFlight.lookup(flight_id=MI_AIRCRAFT_FLIGHT.next_flight_id)
    )
)

# --- RotationLinkValidation (DV-24, DV-25) ----------------------------------------
#
# One row per candidate edge, plus a terminal row per leg whose target token is the literal
# ``NO_TARGET``. Grain verified live: 3,900 rows, 3,900 distinct (flight_id, target_token), of
# which 2 are ``ACCEPTED``, 3 ``EXCLUDED``, 9 ``REJECTED`` and 3,886 ``TERMINAL_NO_TARGET``.

RotationLinkValidation = model.Concept(
    "RotationLinkValidation",
    identify_by={"flight": AircraftFlight, "target_token": String},
)

_rotation_scalars = scalar_properties(
    RotationLinkValidation,
    SCHEMA_MI_ROTATION_LINK_VALIDATION,
    exclude=("flight_id", "target_token"),
)


def _rotation_key() -> dict:
    return {
        "flight": AircraftFlight.lookup(flight_id=MI_ROTATION_LINK_VALIDATION.flight_id),
        "target_token": MI_ROTATION_LINK_VALIDATION.target_token,
    }


model.define(RotationLinkValidation.new(**_rotation_key()))
bind_scalars(
    RotationLinkValidation,
    MI_ROTATION_LINK_VALIDATION,
    _rotation_key(),
    _rotation_scalars,
)

RotationLinkValidation.target_flight = model.Property(
    f"{RotationLinkValidation:validation} validates target {AircraftFlight:target_flight}"
)
model.define(
    RotationLinkValidation.lookup(**_rotation_key()).target_flight(
        AircraftFlight.lookup(flight_id=MI_ROTATION_LINK_VALIDATION.target_flight_id)
    )
)

AircraftFlight.rotation_validations = model.Relationship(
    f"{AircraftFlight:leg} was validated by {RotationLinkValidation:validation}"
)
model.define(AircraftFlight.rotation_validations(RotationLinkValidation)).where(
    RotationLinkValidation.flight == AircraftFlight
)

# --- Fulfillment: exact, candidate, and ambiguous ---------------------------------

ExactFulfillment = model.Concept(
    "ExactFulfillment", identify_by={"exact_fulfillment_id": String}
)
_exact_fulfillment_scalars = scalar_properties(
    ExactFulfillment, SCHEMA_MI_FULFILLMENT_EXACT, exclude=("exact_fulfillment_id",)
)
model.define(
    ExactFulfillment.new(exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id)
)
bind_scalars(
    ExactFulfillment,
    MI_FULFILLMENT_EXACT,
    {"exact_fulfillment_id": MI_FULFILLMENT_EXACT.exact_fulfillment_id},
    _exact_fulfillment_scalars,
)

ExactFulfillment.actual_flight = model.Property(
    f"{ExactFulfillment:fulfillment} confirms leg {AircraftFlight:actual_flight}"
)
ExactFulfillment.passenger_flight = model.Property(
    f"{ExactFulfillment:fulfillment} confirms plan {PassengerFlight:passenger_flight}"
)
model.define(
    ExactFulfillment.lookup(
        exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id
    ).actual_flight(AircraftFlight.lookup(flight_id=MI_FULFILLMENT_EXACT.actual_flight_id))
)
model.define(
    ExactFulfillment.lookup(
        exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id
    ).passenger_flight(
        PassengerFlight.lookup(
            passenger_flight_key=MI_FULFILLMENT_EXACT.passenger_flight_key
        )
    )
)

FulfillmentCandidate = model.Concept(
    "FulfillmentCandidate", identify_by={"candidate_id": String}
)
_fulfillment_candidate_scalars = scalar_properties(
    FulfillmentCandidate,
    SCHEMA_MI_FULFILLMENT_CANDIDATE,
    exclude=("fulfillment_candidate_id",),
)
model.define(
    FulfillmentCandidate.new(
        candidate_id=MI_FULFILLMENT_CANDIDATE.fulfillment_candidate_id
    )
)
bind_scalars(
    FulfillmentCandidate,
    MI_FULFILLMENT_CANDIDATE,
    {"candidate_id": MI_FULFILLMENT_CANDIDATE.fulfillment_candidate_id},
    _fulfillment_candidate_scalars,
)

# D-0020 A6: unmatched actual and passenger observations live here at member grain with a NULL
# group id, because that contract row is where "unmatched observations retain a deterministic
# identity plus reason" is written. ``FULFILLMENT_GROUP_ID`` is non-null on only 3 of 23,887
# rows, so the identity is the member id and the group link is an optional Property.
FulfillmentGroupMember = model.Concept(
    "FulfillmentGroupMember", identify_by={"member_id": String}
)
_fulfillment_member_scalars = scalar_properties(
    FulfillmentGroupMember,
    SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP,
    exclude=("fulfillment_group_member_id",),
)
model.define(
    FulfillmentGroupMember.new(
        member_id=MI_FULFILLMENT_AMBIGUOUS_GROUP.fulfillment_group_member_id
    )
)
bind_scalars(
    FulfillmentGroupMember,
    MI_FULFILLMENT_AMBIGUOUS_GROUP,
    {"member_id": MI_FULFILLMENT_AMBIGUOUS_GROUP.fulfillment_group_member_id},
    _fulfillment_member_scalars,
)

# --- The asymmetric fulfillment link ----------------------------------------------
#
# Derived from ``ExactFulfillment`` only. ``FulfillmentCandidate`` never feeds it: that is the
# exact/heuristic separation, made structural rather than documented.

AircraftFlight.fulfils = model.Property(
    f"{AircraftFlight:leg} fulfilled {PassengerFlight:plan}"
)
model.define(AircraftFlight.fulfils(PassengerFlight)).where(
    ExactFulfillment.actual_flight == AircraftFlight,
    ExactFulfillment.passenger_flight == PassengerFlight,
)
PassengerFlight.fulfilled_by = AircraftFlight.fulfils.alt(
    f"{PassengerFlight:plan} was fulfilled by {AircraftFlight:leg}"
)
