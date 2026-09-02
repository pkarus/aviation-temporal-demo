"""core_aircraft.py - UC1: aircraft identity, events, definitions and both assignment layers.

This module is the reduced-demo fallback (AGENTS.md: "UC1 is the independently runnable
fallback"). It plus ``temporal.py``, ``calendar.py`` and ``computed_aircraft.py`` answers Q01
through Q04 on its own, with no schedule or flight surface at all.

The shape that matters, and the reason it is not obvious:

* **Identity never carries state.** ``Aircraft`` is ``AM-01`` alone. Registration, type, engine
  and status are all versioned assignments hanging off it, never properties of it (P0-01.1).
* **Two assignment layers, not one.** The *audit* stream is the ordered same-day truth and
  carries **no** date interval, ever. The *daily* projection carries the half-open interval and
  keeps only the final relevant observation per aircraft/dimension/date. Q02's same-day
  ``Storage -> In Service`` spell exists only on the audit stream; reading the daily stream
  loses it silently. Keeping them as two concepts makes that impossible to conflate by accident.
* **Compound identity makes the same-day rule structural.** BRIEF.md: "Order aircraft events by
  date and sequence; do not identify a version by date alone." Putting ``event_date``,
  ``row_sequence`` and ``event`` into ``identify_by`` means two same-day observations are two
  entities permanently, and no downstream rule can collapse them. PROBE U-08 confirmed
  Concept-valued identity components load from a Snowflake table, that an identical re-define
  mints zero new entities, and that a row whose parent does not resolve produces no assignment
  *and no error* - which is why ``inventory.py`` asserts a count per association.
* **The DV-05 string key is carried as a non-identity property.** ``EXPECTED_ANSWERS.yaml``
  freezes the literal ``assignment_id`` spelling, so RAI reads it rather than re-deriving it.

Multiplicity: every ``assignment -> parent`` link is a functional ``Property``, and every
``parent -> assignments`` link is unconstrained. Where the forward link is a Property this
module declares, the inverse is an ``.alt()`` *reading* over the same fields, which adds a name
and no FD. Where the forward link is an *identity component* (``assignment.aircraft``,
``assignment.event``) the inverse is an explicit multi-valued ``Relationship`` instead, because
``identify_by`` names the owner slot after the lowercased concept and an ``.alt()`` reading
would have to spell ``aircraftdimensionauditassignment`` to match. Both forms leave the
one-to-many direction unconstrained, which is what SOURCE_CONTRACT.md requires: "Aircraft to
audit assignments, one-to-many, association concept; never a functional property".
"""

from relationalai.semantics import Date, Integer, String

from ._binding import bind_scalars, scalar_properties
from .model import model
from .sources import (
    MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT,
    MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT,
    MI_AIRCRAFT_ELIGIBLE,
    MI_AIRCRAFT_EVENT_ELIGIBLE,
    MI_AIRCRAFT_EVENT_QUARANTINE,
    MI_AIRCRAFT_TYPE_DEFINITION,
    MI_ENGINE_TYPE_DEFINITION,
    SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT,
    SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT,
    SCHEMA_MI_AIRCRAFT_ELIGIBLE,
    SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE,
    SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE,
    SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION,
    SCHEMA_MI_ENGINE_TYPE_DEFINITION,
    SCHEMA_SRC_AIRCRAFT_CONFIGURATION,
    SRC_AIRCRAFT_CONFIGURATION,
)

# --- Aircraft (AM-01) -------------------------------------------------------------

Aircraft = model.Concept("Aircraft", identify_by={"id": Integer})

_aircraft_scalars = scalar_properties(
    Aircraft, SCHEMA_MI_AIRCRAFT_ELIGIBLE, exclude=("aircraft_id",)
)
model.define(Aircraft.new(id=MI_AIRCRAFT_ELIGIBLE.aircraft_id))
bind_scalars(
    Aircraft,
    MI_AIRCRAFT_ELIGIBLE,
    {"id": MI_AIRCRAFT_ELIGIBLE.aircraft_id},
    _aircraft_scalars,
)

# --- AircraftConfiguration (AC-01) ------------------------------------------------
#
# A join target only. It left-preserves every event: an assignment whose configuration does not
# resolve keeps its identity and simply has no configuration fact (P0-12.3).

AircraftConfiguration = model.Concept("AircraftConfiguration", identify_by={"id": Integer})

_configuration_scalars = scalar_properties(
    AircraftConfiguration,
    SCHEMA_SRC_AIRCRAFT_CONFIGURATION,
    exclude=("aircraft_configuration_id",),
)
model.define(
    AircraftConfiguration.new(id=SRC_AIRCRAFT_CONFIGURATION.aircraft_configuration_id)
)
bind_scalars(
    AircraftConfiguration,
    SRC_AIRCRAFT_CONFIGURATION,
    {"id": SRC_AIRCRAFT_CONFIGURATION.aircraft_configuration_id},
    _configuration_scalars,
)

# --- AircraftType (AC-05) and EngineType (AC-14) ----------------------------------
#
# Definition attributes only, and only because PROBE G-01 / G-02 measured zero violating keys.
# AC-08 ``engine_count`` and AC-09 ``has_multiple_engine_types`` deliberately do NOT live on
# ``EngineType``: they are ENGINE_ASSIGNMENT_ATTRIBUTEs per ATTRIBUTE_AUTHORITY.md, they are
# functional on the subseries in this fixture only by accident of a near-bijective generator,
# and asserting one engine count per engine-subseries identity would be wrong in the domain.
# They are bound on the assignment instead, below.

AircraftType = model.Concept("AircraftType", identify_by={"subseries": String})

_aircraft_type_scalars = scalar_properties(
    AircraftType, SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION, exclude=("aircraft_subseries",)
)
model.define(AircraftType.new(subseries=MI_AIRCRAFT_TYPE_DEFINITION.aircraft_subseries))
bind_scalars(
    AircraftType,
    MI_AIRCRAFT_TYPE_DEFINITION,
    {"subseries": MI_AIRCRAFT_TYPE_DEFINITION.aircraft_subseries},
    _aircraft_type_scalars,
)

EngineType = model.Concept("EngineType", identify_by={"subseries": String})

_engine_type_scalars = scalar_properties(
    EngineType, SCHEMA_MI_ENGINE_TYPE_DEFINITION, exclude=("engine_subseries",)
)
model.define(EngineType.new(subseries=MI_ENGINE_TYPE_DEFINITION.engine_subseries))
bind_scalars(
    EngineType,
    MI_ENGINE_TYPE_DEFINITION,
    {"subseries": MI_ENGINE_TYPE_DEFINITION.engine_subseries},
    _engine_type_scalars,
)

# --- AircraftStatus (AH-09) -------------------------------------------------------
#
# G-07: no attributes at all, ever. The identity is the raw AH-09 string with no trim and no
# case fold (NEO4J_RAI_MAPPING.md), and adding a "display label" would be the first step toward
# the normalisation the contract forbids. Minted from the observed audit values, so the
# vocabulary is whatever the source actually contains rather than a hard-coded enum.

AircraftStatus = model.Concept("AircraftStatus", identify_by={"code": String})

model.define(
    AircraftStatus.new(code=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_status_code)
)

# --- AircraftEvent (AH-01) --------------------------------------------------------
#
# An ordered fact. It never carries a date interval (P0-01.4); ``END_EVENT_DATE`` is retained
# as provenance and takes part in no validity predicate.

AircraftEvent = model.Concept("AircraftEvent", identify_by={"id": Integer})

_event_scalars = scalar_properties(
    AircraftEvent,
    SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE,
    exclude=("aircraft_history_id", "aircraft_id"),
)
model.define(AircraftEvent.new(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id))
bind_scalars(
    AircraftEvent,
    MI_AIRCRAFT_EVENT_ELIGIBLE,
    {"id": MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id},
    _event_scalars,
)

AircraftEvent.aircraft = model.Property(
    f"{AircraftEvent:event} observed on {Aircraft:aircraft}"
)
model.define(
    AircraftEvent.lookup(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id).aircraft(
        Aircraft.lookup(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_id)
    )
)
Aircraft.events = AircraftEvent.aircraft.alt(
    f"{Aircraft:aircraft} has event {AircraftEvent:event}"
)

# --- AircraftEventQuarantine (DV-44) ----------------------------------------------

AircraftEventQuarantine = model.Concept(
    "AircraftEventQuarantine", identify_by={"quarantine_id": String}
)
_event_quarantine_scalars = scalar_properties(
    AircraftEventQuarantine,
    SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE,
    exclude=("quarantine_id",),
)
model.define(
    AircraftEventQuarantine.new(quarantine_id=MI_AIRCRAFT_EVENT_QUARANTINE.quarantine_id)
)
bind_scalars(
    AircraftEventQuarantine,
    MI_AIRCRAFT_EVENT_QUARANTINE,
    {"quarantine_id": MI_AIRCRAFT_EVENT_QUARANTINE.quarantine_id},
    _event_quarantine_scalars,
)

# --- AircraftDimensionAuditAssignment (DV-04) -------------------------------------
#
# Identity = (dimension, aircraft, event_date, row_sequence, event). Verified live: 97,983 rows,
# 97,983 distinct tuples. No interval here by construction - the audit stream is order, not
# duration.

_AUDIT_IDENTITY_COLUMNS = (
    "dimension",
    "aircraft_id",
    "event_date",
    "row_sequence_number",
    "aircraft_history_id",
)

AircraftDimensionAuditAssignment = model.Concept(
    "AircraftDimensionAuditAssignment",
    identify_by={
        "dimension": String,
        "aircraft": Aircraft,
        "event_date": Date,
        "row_sequence": Integer,
        "event": AircraftEvent,
    },
)
AuditAssignment = AircraftDimensionAuditAssignment  # readable alias for rule modules

_audit_scalars = scalar_properties(
    AuditAssignment,
    SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT,
    exclude=_AUDIT_IDENTITY_COLUMNS,
)

def _audit_key() -> dict:
    """A *fresh* identity-key mapping for each rule.

    ``lookup()`` returns a new reference every call and two references are never unified
    implicitly, so a single shared key object reused across several ``define()`` calls would
    risk one rule's binding leaking into another. Building it per rule costs nothing and
    removes the question.
    """
    return {
        "dimension": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.dimension,
        "aircraft": Aircraft.lookup(id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_id),
        "event_date": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.event_date,
        "row_sequence": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.row_sequence_number,
        "event": AircraftEvent.lookup(
            id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_history_id
        ),
    }


model.define(AuditAssignment.new(**_audit_key()))
bind_scalars(
    AuditAssignment,
    MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT,
    _audit_key(),
    _audit_scalars,
)

# The inverses of the two *identity* components are declared as explicit multi-valued
# ``Relationship``s rather than as ``.alt()`` readings. ``.alt()`` is the cheaper construct and
# is used everywhere else in this file, but it requires the new reading to reuse the underlying
# relationship's field names, and ``identify_by`` names an entity component's owner slot after
# the lowercased concept - here ``aircraftdimensionauditassignment``. An inverse reading forced
# to spell that would be unreadable in the ontology inventory a customer sees. A
# ``Relationship`` adds no functional dependency either, so the "one aircraft, many
# assignments" direction stays unconstrained exactly as SOURCE_CONTRACT.md requires.
Aircraft.audit_assignments = model.Relationship(
    f"{Aircraft:aircraft} has audit assignment {AuditAssignment:assignment}"
)
model.define(Aircraft.audit_assignments(AuditAssignment)).where(
    AuditAssignment.aircraft == Aircraft
)
AircraftEvent.audit_assignments = model.Relationship(
    f"{AircraftEvent:event} minted audit assignment {AuditAssignment:assignment}"
)
model.define(AircraftEvent.audit_assignments(AuditAssignment)).where(
    AuditAssignment.event == AircraftEvent
)

# --- AircraftDimensionDailyAssignment (DV-05) -------------------------------------
#
# Identity = (dimension, aircraft, valid_from, event). Verified live: 97,979 rows, 97,979
# distinct tuples, and the same count for the DV-05 string key. The half-open interval
# DV-06/DV-07 lives here as two functional ``Date`` properties, because 1.20.1 has no interval
# type at all - which is honest parity with Neo4j, and is also why nothing in the API holds a
# one-open-version-per-parent assumption on our behalf.

_DAILY_IDENTITY_COLUMNS = (
    "dimension",
    "aircraft_id",
    "valid_from",
    "aircraft_history_id",
)

AircraftDimensionDailyAssignment = model.Concept(
    "AircraftDimensionDailyAssignment",
    identify_by={
        "dimension": String,
        "aircraft": Aircraft,
        "valid_from": Date,
        "event": AircraftEvent,
    },
)
DailyAssignment = AircraftDimensionDailyAssignment  # readable alias for rule modules

_daily_scalars = scalar_properties(
    DailyAssignment,
    SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT,
    exclude=_DAILY_IDENTITY_COLUMNS,
)

def _daily_key() -> dict:
    """A fresh identity-key mapping for each rule; see :func:`_audit_key`."""
    return {
        "dimension": MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.dimension,
        "aircraft": Aircraft.lookup(id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_id),
        "valid_from": MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.valid_from,
        "event": AircraftEvent.lookup(
            id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_history_id
        ),
    }


model.define(DailyAssignment.new(**_daily_key()))
bind_scalars(
    DailyAssignment,
    MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT,
    _daily_key(),
    _daily_scalars,
)

Aircraft.daily_assignments = model.Relationship(
    f"{Aircraft:aircraft} has daily assignment {DailyAssignment:assignment}"
)
model.define(Aircraft.daily_assignments(DailyAssignment)).where(
    DailyAssignment.aircraft == Aircraft
)

# --- Exact links out of the assignments -------------------------------------------
#
# All four are ``Property``: at most one exact target per assignment, never exactly one
# (SOURCE_CONTRACT.md "zero-or-one exact target per dimension"). An unresolved reference is
# therefore the absence of a fact rather than a fabricated node, which is precisely the
# ``UNKNOWN_STATE`` gap P0-02.8 wants and what makes the DV-33 classification expressible.
# Verified live: zero orphan ``EXACT_AIRCRAFT_TYPE_SUBSERIES`` and zero orphan
# ``EXACT_ENGINE_TYPE_SUBSERIES`` over 47,984 non-null values each.

DailyAssignment.aircraft_type = model.Property(
    f"{DailyAssignment:assignment} conformed to {AircraftType:aircraft_type}"
)
DailyAssignment.engine_type = model.Property(
    f"{DailyAssignment:assignment} equipped with {EngineType:engine_type}"
)
DailyAssignment.status = model.Property(
    f"{DailyAssignment:assignment} assigned status {AircraftStatus:status}"
)
DailyAssignment.configuration = model.Property(
    f"{DailyAssignment:assignment} read configuration {AircraftConfiguration:configuration}"
)

model.define(
    DailyAssignment.lookup(**_daily_key()).aircraft_type(
        AircraftType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.exact_aircraft_type_subseries
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).engine_type(
        EngineType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.exact_engine_type_subseries
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).status(
        AircraftStatus.lookup(
            code=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_status_code
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).configuration(
        AircraftConfiguration.lookup(
            id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_configuration_id
        )
    )
)

AuditAssignment.aircraft_type = model.Property(
    f"{AuditAssignment:assignment} observed type {AircraftType:aircraft_type}"
)
AuditAssignment.engine_type = model.Property(
    f"{AuditAssignment:assignment} observed engine {EngineType:engine_type}"
)
AuditAssignment.status = model.Property(
    f"{AuditAssignment:assignment} observed status {AircraftStatus:status}"
)
AuditAssignment.configuration = model.Property(
    f"{AuditAssignment:assignment} observed configuration {AircraftConfiguration:configuration}"
)

model.define(
    AuditAssignment.lookup(**_audit_key()).aircraft_type(
        AircraftType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.exact_aircraft_type_subseries
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).engine_type(
        EngineType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.exact_engine_type_subseries
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).status(
        AircraftStatus.lookup(
            code=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_status_code
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).configuration(
        AircraftConfiguration.lookup(
            id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_configuration_id
        )
    )
)

AircraftType.daily_assignments = DailyAssignment.aircraft_type.alt(
    f"{AircraftType:aircraft_type} assigned by {DailyAssignment:assignment}"
)
EngineType.daily_assignments = DailyAssignment.engine_type.alt(
    f"{EngineType:engine_type} fitted by {DailyAssignment:assignment}"
)

# --- No resolved base-airport link, deliberately ----------------------------------
#
# Tempting, and wrong. AH-24 ``BASE_AIRPORT`` is a descriptive label ("Synthetic base"), not an
# internal airport id, and AH-25 ``BASE_AIRPORT_CODE_IATA`` is a public IATA code that
# ``AIRPORT_CURRENT`` does not key on. DATA-04 emits no resolved ``BASE_AIRPORT_ID`` column for
# the aircraft dimension, so there is no exact resolution to bind and inventing one by joining
# on the IATA code would assert a link the contract never resolved. Both raw values stay bound
# as plain strings (SOURCE_CONTRACT.md: a failed resolution must still show the code), and Q01
# emits ``base_airport_code_iata`` from the string, not from an ``Airport`` entity.
