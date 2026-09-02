"""aviation_model - the canonical modular ontology for the aviation temporal demo.

Import order is load order and is not cosmetic: Python needs each Concept object to exist
before a later module's reading f-string interpolates it. ``core_reference`` first because
``Airport`` and ``Airline`` are link targets for three other modules; ``core_schedule`` before
``core_flight`` because ``PassengerFlight`` links to ``Schedule`` through PH-02.

The directory is ``aviation_model/`` and not ``model/`` on purpose: the ``Model`` variable is
also called ``model``, and a directory of that name would shadow it on ``import model.core``.
"""

from . import sources  # noqa: F401
from . import core_reference  # noqa: F401
from . import core_aircraft  # noqa: F401
from . import calendar_dates  # noqa: F401
from . import core_schedule  # noqa: F401
from . import core_flight  # noqa: F401
from . import temporal  # noqa: F401
from . import computed_aircraft  # noqa: F401
from . import computed_schedule  # noqa: F401
from . import computed_rotation  # noqa: F401
from . import constraints  # noqa: F401
from . import inventory  # noqa: F401
from .calendar_dates import MonthEnd
from .constants import (
    CARRIER_ROLE_MARKETING,
    CARRIER_ROLE_OPERATING,
    DIM_AIRCRAFT_STATE,
    DIM_AIRCRAFT_STATUS,
    DIM_AIRCRAFT_TYPE,
    DIM_ENGINE_TYPE,
    DV33_NO_RECORDED_STATE,
    DV33_OK,
    DV33_OUTSIDE_EXISTENCE,
    DV33_UNKNOWN_STATE,
    MODEL_OPEN_INTERVAL,
    SOURCE_UNKNOWN_FUTURE,
    STATUS_IN_SERVICE,
    STATUS_STORAGE,
)
from .computed_aircraft import (
    AircraftStateAudit,
    AircraftStateDaily,
    AircraftStatusAudit,
    AircraftStatusDaily,
    AircraftTypeAudit,
    AircraftTypeDaily,
    EndEventDisagreement,
    EngineTypeAudit,
    EngineTypeDaily,
    InServiceOnMonthEnd,
    SentinelLeak,
)
from .computed_rotation import (
    RotationSegmentHead,
    rotation_leg_distance,
)
from .computed_schedule import (
    CabinDerivationDisagreement,
    RouteStateSchedules,
    PhysicalServiceDisagreement,
    RouteStateCloseCrossesGap,
    RouteStateIsPhysicalRepresentative,
    RouteStateOpenCrossesGap,
    RouteStateOperatesOnWeekday,
)
from .core_aircraft import (
    Aircraft,
    AircraftConfiguration,
    AircraftDimensionAuditAssignment,
    AircraftDimensionDailyAssignment,
    AircraftEvent,
    AircraftEventQuarantine,
    AircraftStatus,
    AircraftType,
    AuditAssignment,
    DailyAssignment,
    EngineType,
)
from .core_flight import (
    AircraftFlight,
    ExactFulfillment,
    FulfillmentCandidate,
    FulfillmentGroupMember,
    InvalidPassengerObservation,
    PassengerFlight,
    PassengerPlannedLeg,
    PassengerSourceLineage,
    PassengerSourceQuarantine,
    RotationLinkValidation,
)
from .core_reference import (
    Airline,
    Airport,
    CodeResolutionCode,
    CodeResolutionCodeCandidate,
    SnapshotDate,
)
from .core_schedule import (
    Route,
    RouteState,
    RouteStateSnapshotLineage,
    Schedule,
    ScheduleAmendmentCandidate,
    ScheduleAmendmentGroup,
    ScheduleAmendmentGroupMember,
    ScheduleAmendmentSide,
    ScheduleComparison,
    ScheduleExactChange,
    ScheduleObservation,
)
from .model import model
from .temporal import (
    dv33_branches,
    iso_weekday,
    known_on,
    operates_on,
    visible_on,
    within_existence,
)

__all__ = [
    "model",
    # constants the query modules must not re-spell
    "MODEL_OPEN_INTERVAL",
    "SOURCE_UNKNOWN_FUTURE",
    "DIM_AIRCRAFT_STATE",
    "DIM_AIRCRAFT_TYPE",
    "DIM_ENGINE_TYPE",
    "DIM_AIRCRAFT_STATUS",
    "DV33_OK",
    "DV33_UNKNOWN_STATE",
    "DV33_NO_RECORDED_STATE",
    "DV33_OUTSIDE_EXISTENCE",
    "CARRIER_ROLE_MARKETING",
    "CARRIER_ROLE_OPERATING",
    "STATUS_IN_SERVICE",
    "STATUS_STORAGE",
    # reference
    "Airport",
    "Airline",
    "CodeResolutionCode",
    "CodeResolutionCodeCandidate",
    "SnapshotDate",
    # aircraft
    "Aircraft",
    "AircraftConfiguration",
    "AircraftEvent",
    "AircraftEventQuarantine",
    "AircraftType",
    "EngineType",
    "AircraftStatus",
    "AircraftDimensionAuditAssignment",
    "AircraftDimensionDailyAssignment",
    "AuditAssignment",
    "DailyAssignment",
    "AircraftStateDaily",
    "AircraftTypeDaily",
    "EngineTypeDaily",
    "AircraftStatusDaily",
    "AircraftStateAudit",
    "AircraftTypeAudit",
    "EngineTypeAudit",
    "AircraftStatusAudit",
    "InServiceOnMonthEnd",
    "SentinelLeak",
    "EndEventDisagreement",
    # calendar
    "MonthEnd",
    # schedule
    "Schedule",
    "ScheduleObservation",
    "Route",
    "RouteState",
    "RouteStateSnapshotLineage",
    "ScheduleComparison",
    "ScheduleExactChange",
    "ScheduleAmendmentSide",
    "ScheduleAmendmentCandidate",
    "ScheduleAmendmentGroup",
    "ScheduleAmendmentGroupMember",
    "RouteStateOperatesOnWeekday",
    "RouteStateIsPhysicalRepresentative",
    "RouteStateOpenCrossesGap",
    "RouteStateCloseCrossesGap",
    "CabinDerivationDisagreement",
    "PhysicalServiceDisagreement",
    "RouteStateSchedules",
    # flight
    "PassengerFlight",
    "PassengerSourceLineage",
    "PassengerPlannedLeg",
    "InvalidPassengerObservation",
    "PassengerSourceQuarantine",
    "AircraftFlight",
    "ExactFulfillment",
    "FulfillmentCandidate",
    "FulfillmentGroupMember",
    "RotationLinkValidation",
    "RotationSegmentHead",
    "rotation_leg_distance",
    # temporal predicates
    "visible_on",
    "within_existence",
    "known_on",
    "operates_on",
    "iso_weekday",
    "dv33_branches",
]
