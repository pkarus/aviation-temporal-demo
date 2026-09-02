"""core_reference.py - reference entities every other module links to.

Loaded before ``core_aircraft`` / ``core_schedule`` / ``core_flight`` because Python needs the
Concept objects to exist before their reading f-strings interpolate them.

``Airport`` and ``Airline`` bind from the ``MODEL_INPUT.*_CURRENT`` projections rather than from
``SOURCE.*_REFERENCE``. PROBE G-03 / G-04 showed the raw source is *already* one effective
period per entity, so binding ``SOURCE`` directly would not have raised - but the projections
carry a ``PROJECTION_RULE`` column recording the declared deterministic order, which is exactly
what ``ATTRIBUTE_AUTHORITY.md`` demands instead of relying on ``WHERE is_current``. Using them
puts the choice of winner in the data instead of in a query. ``REFERENCE_PERIOD_COUNT`` is
carried so a future multi-period fixture is visible rather than silent.

``CodeResolutionCode`` is the D-0019 substitution for the row-scoped ``CODE_RESOLUTION``: link
semantics only ever need "does this raw code resolve to exactly one identity", which is a
property of the code, not of the row that mentioned it.
"""

from relationalai.semantics import Date, String

from ._binding import bind_scalars, scalar_properties
from .model import model
from .sources import (
    MI_AIRLINE_CURRENT,
    MI_AIRPORT_CURRENT,
    MI_CODE_RESOLUTION,
    MI_CODE_RESOLUTION_CANDIDATE,
    MI_CODE_RESOLUTION_CODE,
    MI_CODE_RESOLUTION_CODE_CANDIDATE,
    SCHEMA_MI_AIRLINE_CURRENT,
    SCHEMA_MI_AIRPORT_CURRENT,
    SCHEMA_MI_CODE_RESOLUTION,
    SCHEMA_MI_CODE_RESOLUTION_CANDIDATE,
    SCHEMA_MI_CODE_RESOLUTION_CODE,
    SCHEMA_MI_CODE_RESOLUTION_CODE_CANDIDATE,
    SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR,
    SRC_SCHEDULE_SNAPSHOT_CALENDAR,
)

# --- Airport (AP-01) --------------------------------------------------------------

Airport = model.Concept("Airport", identify_by={"airport_id": String})

_airport_scalars = scalar_properties(
    Airport, SCHEMA_MI_AIRPORT_CURRENT, exclude=("airport_id",)
)
model.define(Airport.new(airport_id=MI_AIRPORT_CURRENT.airport_id))
bind_scalars(
    Airport,
    MI_AIRPORT_CURRENT,
    {"airport_id": MI_AIRPORT_CURRENT.airport_id},
    _airport_scalars,
)

# --- Airline (AL-01) --------------------------------------------------------------

Airline = model.Concept("Airline", identify_by={"airline_id": String})

_airline_scalars = scalar_properties(
    Airline, SCHEMA_MI_AIRLINE_CURRENT, exclude=("airline_id",)
)
model.define(Airline.new(airline_id=MI_AIRLINE_CURRENT.airline_id))
bind_scalars(
    Airline,
    MI_AIRLINE_CURRENT,
    {"airline_id": MI_AIRLINE_CURRENT.airline_id},
    _airline_scalars,
)

# --- Code resolution, at code grain (D-0019) --------------------------------------

CodeResolutionCode = model.Concept(
    "CodeResolutionCode",
    identify_by={"domain": String, "method": String, "raw_code": String},
)

_code_resolution_scalars = scalar_properties(
    CodeResolutionCode,
    SCHEMA_MI_CODE_RESOLUTION_CODE,
    exclude=("domain", "method", "raw_code"),
)
model.define(
    CodeResolutionCode.new(
        domain=MI_CODE_RESOLUTION_CODE.domain,
        method=MI_CODE_RESOLUTION_CODE.method,
        raw_code=MI_CODE_RESOLUTION_CODE.raw_code,
    )
)
bind_scalars(
    CodeResolutionCode,
    MI_CODE_RESOLUTION_CODE,
    {
        "domain": MI_CODE_RESOLUTION_CODE.domain,
        "method": MI_CODE_RESOLUTION_CODE.method,
        "raw_code": MI_CODE_RESOLUTION_CODE.raw_code,
    },
    _code_resolution_scalars,
)

CodeResolutionCodeCandidate = model.Concept(
    "CodeResolutionCodeCandidate",
    identify_by={"resolution": CodeResolutionCode, "candidate_id": String},
)

CodeResolutionCodeCandidate.matched_code_systems = model.Property(
    f"{CodeResolutionCodeCandidate} matched {String:matched_code_systems}"
)

_candidate_resolution_key = {
    "domain": MI_CODE_RESOLUTION_CODE_CANDIDATE.domain,
    "method": MI_CODE_RESOLUTION_CODE_CANDIDATE.method,
    "raw_code": MI_CODE_RESOLUTION_CODE_CANDIDATE.raw_code,
}
model.define(
    CodeResolutionCodeCandidate.new(
        resolution=CodeResolutionCode.lookup(**_candidate_resolution_key),
        candidate_id=MI_CODE_RESOLUTION_CODE_CANDIDATE.candidate_id,
    )
)
model.define(
    CodeResolutionCodeCandidate.lookup(
        resolution=CodeResolutionCode.lookup(**_candidate_resolution_key),
        candidate_id=MI_CODE_RESOLUTION_CODE_CANDIDATE.candidate_id,
    ).matched_code_systems(MI_CODE_RESOLUTION_CODE_CANDIDATE.matched_code_systems)
)

# ``candidates`` carries no cardinality claim: a raw code may resolve to zero, one or many
# candidates (SOURCE_CONTRACT.md multiplicity gate), and only a cardinality-one EXACT
# resolution is ever allowed to create a concept link elsewhere in the model. It is declared as
# a ``Relationship`` rather than as an ``.alt()`` reading over ``candidate.resolution`` because
# ``resolution`` is an *identity* component, and ``identify_by`` names an entity component's
# owner slot after the lowercased concept - an inverse reading would have to spell
# ``coderesolutioncodecandidate``. A ``Relationship`` adds no functional dependency either.
CodeResolutionCode.candidates = model.Relationship(
    f"{CodeResolutionCode:resolution} has candidate {CodeResolutionCodeCandidate:candidate}"
)
model.define(CodeResolutionCode.candidates(CodeResolutionCodeCandidate)).where(
    CodeResolutionCodeCandidate.resolution == CodeResolutionCode
)

# --- Code resolution, at row grain (D-0027) ---------------------------------------
#
# D-0019 excluded the row-scoped resolution on a suspicion about sync and cold-start cost and
# gated the exclusion on one measurement. The measurement came back at 0.18 seconds against an
# 18-second first query, inside the warm-query noise band, so the premise is refuted and the
# exclusion does not stand. ``CodeResolutionCode`` above remains the grain link semantics read;
# ``CodeResolution`` adds the provenance grain, which is the one question the code grain cannot
# answer: which source object, row and field role mentioned a given raw code.

CodeResolution = model.Concept("CodeResolution", identify_by={"resolution_id": String})

_row_resolution_scalars = scalar_properties(
    CodeResolution, SCHEMA_MI_CODE_RESOLUTION, exclude=("resolution_id",)
)
model.define(CodeResolution.new(resolution_id=MI_CODE_RESOLUTION.resolution_id))
bind_scalars(
    CodeResolution,
    MI_CODE_RESOLUTION,
    {"resolution_id": MI_CODE_RESOLUTION.resolution_id},
    _row_resolution_scalars,
)

CodeResolutionCandidate = model.Concept(
    "CodeResolutionCandidate",
    identify_by={"resolution": CodeResolution, "candidate_id": String},
)

_row_candidate_scalars = scalar_properties(
    CodeResolutionCandidate,
    SCHEMA_MI_CODE_RESOLUTION_CANDIDATE,
    exclude=("resolution_id", "candidate_id"),
)
_row_candidate_key = {
    "resolution": CodeResolution.lookup(
        resolution_id=MI_CODE_RESOLUTION_CANDIDATE.resolution_id
    ),
    "candidate_id": MI_CODE_RESOLUTION_CANDIDATE.candidate_id,
}
model.define(CodeResolutionCandidate.new(**_row_candidate_key))
bind_scalars(
    CodeResolutionCandidate,
    MI_CODE_RESOLUTION_CANDIDATE,
    _row_candidate_key,
    _row_candidate_scalars,
)

# Same reasoning as the code-grain relationship: zero, one or many candidates are all legal and
# only a cardinality-one EXACT resolution ever creates a link, so this carries no functional
# dependency.
CodeResolution.candidates = model.Relationship(
    f"{CodeResolution:resolution} has row candidate {CodeResolutionCandidate:candidate}"
)
model.define(CodeResolution.candidates(CodeResolutionCandidate)).where(
    CodeResolutionCandidate.resolution == CodeResolution
)

# --- SnapshotDate (SC-01) ---------------------------------------------------------
#
# The eligibility control for Q05 and Q06. P0-05.1: a snapshot is usable only when it is both
# present and complete; SC-05 observed row counts are validation evidence and never a
# completeness test on their own.

SnapshotDate = model.Concept("SnapshotDate", identify_by={"expected_publish_date": Date})

_snapshot_scalars = scalar_properties(
    SnapshotDate,
    SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR,
    exclude=("expected_publish_date",),
)
model.define(
    SnapshotDate.new(
        expected_publish_date=SRC_SCHEDULE_SNAPSHOT_CALENDAR.expected_publish_date
    )
)
bind_scalars(
    SnapshotDate,
    SRC_SCHEDULE_SNAPSHOT_CALENDAR,
    {"expected_publish_date": SRC_SCHEDULE_SNAPSHOT_CALENDAR.expected_publish_date},
    _snapshot_scalars,
)

# Shared derived property #3 in QUERY_ROUTING.md: one definition, two consumers with different
# refusal behaviour. Q05 walks adjacent eligible dates; Q06 requires both exact endpoints to be
# eligible and refuses rather than falling back. The definition is shared; the refusal is not.
SnapshotDate.is_eligible = model.Relationship(f"{SnapshotDate} is an eligible snapshot")
model.define(SnapshotDate.is_eligible()).where(
    SnapshotDate.is_present == True,  # noqa: E712 - RAI equality, not Python truthiness
    SnapshotDate.is_complete == True,  # noqa: E712
)
