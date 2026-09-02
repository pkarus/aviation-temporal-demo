"""computed_schedule.py - the reusable derived layer over UC2.

Five things, each of which would otherwise get retyped in a query module:

1. **The weekday predicate**, as a multi-valued relationship rather than a seven-branch match.
2. **The physical-service representative flag** (D-0007), so the codeshare de-duplication rule
   lives in the ontology instead of in eight query functions.
3. **The cabin-derivation cross-check**, which proves DV-26 in RAI without moving authority for
   it out of Snowflake.
4. **A route-state snapshot-gap flag**, lifted so Q05's ``crosses_snapshot_gap`` is queryable.
5. **The Neo4j ``SCHEDULES`` edge**, the only supplied edge that has to be derived rather than
   loaded, from the P0-08 two-clock conjunction.

Both schedule clocks stay separately queryable and their two interval conventions never merge:
knowledge is half-open (DV-14 inclusive, DV-15 **exclusive**), operating is inclusive on both
ends (SS-08 and SS-09 both included). The helpers that apply them are
``temporal.known_on`` and ``temporal.operates_on`` and they are deliberately two functions.
"""

from relationalai.semantics import Integer
from relationalai.semantics.std.datetime import date as std_date

from .constants import (
    PHYSICAL_SERVICE_UNRESOLVED,
    WEEKDAY_FLAG_COLUMNS,
)
from .core_flight import PassengerFlight
from .core_schedule import Route, RouteState, Schedule  # noqa: F401
from .model import model

# --- 1. The weekday predicate -----------------------------------------------------
#
# Up to seven values per state, so a real multi-valued ``Relationship``. Deriving it from the
# seven SS-14..SS-20 booleans turns ``operates_on`` into one join instead of a seven-branch
# match, while the raw booleans stay bound and untouched - Q05 must emit each of them field by
# field with old and new values, so both forms are needed and neither is redundant.
#
# ISO numbering, 1 = Monday. The query side computes the integer in Python from
# ``operating_date.isoweekday()`` rather than from a RAI date-part function, which removes any
# doubt about the day-numbering convention.
#
# The loop is over seven items, not rows. PyRel warns past fifty ``define()`` calls from one
# call site; seven is fine, and the alternative - seven hand-copied blocks - would be the same
# rules with more chances to transpose a day.

RouteStateOperatesOnWeekday = model.Relationship(
    f"{RouteState:state} operates on weekday {Integer:weekday}"
)

for _weekday, _flag_column in WEEKDAY_FLAG_COLUMNS:
    model.define(RouteStateOperatesOnWeekday(RouteState, _weekday)).where(
        getattr(RouteState, _flag_column) == True  # noqa: E712
    )

# --- 2. The D-0007 physical-service representative --------------------------------
#
# For the operating carrier role, only a base-representative state may be counted: not a
# codeshare, and marketing and operating carriers resolving to the same airline. Everything else
# is ``UNRESOLVED_PHYSICAL_SERVICE`` and must be *emitted as visibly unresolved*, never excluded
# and never guessed into a number - ``Q07-R004`` freezes exactly that row.
#
# DATA-04 already classifies this as ``PHYSICAL_SERVICE_STATUS`` (measured live: 4 rows
# ``PHYSICAL_SERVICE_REPRESENTATIVE``, 12,026 ``UNRESOLVED_PHYSICAL_SERVICE``). The flag is
# derived from that column rather than recomputed, keeping one authority - and
# ``PhysicalServiceDisagreement`` below re-derives the rule independently in RAI and asserts the
# two agree, which is the honest way to have both.

RouteStateIsPhysicalRepresentative = model.Relationship(
    f"{RouteState:state} is the physical service representative"
)
model.define(RouteStateIsPhysicalRepresentative(RouteState)).where(
    RouteState.physical_service_status != PHYSICAL_SERVICE_UNRESOLVED
)

# The independent RAI re-derivation of D-0007, used only as a guard. A state qualifies when it
# is not a codeshare and its two carrier roles resolve to the same airline. Any row where the
# Snowflake classification and this rule disagree is surfaced; the gate asserts the flag is
# empty.
PhysicalServiceDisagreement = model.Relationship(
    f"{RouteState:state} disagrees with the derived physical-service rule"
)
model.define(PhysicalServiceDisagreement(RouteState)).where(
    RouteState.physical_service_status != PHYSICAL_SERVICE_UNRESOLVED,
    RouteState.is_codeshare == True,  # noqa: E712
)
model.define(PhysicalServiceDisagreement(RouteState)).where(
    RouteState.physical_service_status != PHYSICAL_SERVICE_UNRESOLVED,
    RouteState.marketing_airline != RouteState.operating_airline,
)

# --- 3. The DV-26 cabin-derivation cross-check ------------------------------------
#
# ``ECONOMY_EXCLUDING_PREMIUM`` is DV-26: premium economy is a subset of economy, so the
# exclusive bucket is SS-34 minus SS-33 and the four cabin buckets must sum to the per-flight
# total. Q07 double-counts economy the moment someone forgets that.
#
# Authority stays with the MODEL_INPUT column - two competing definitions of one number is worse
# than one - but the arithmetic is asserted *in RAI* so the semantic is visible in the ontology
# and a Snowflake regression cannot pass silently. Measured live: zero disagreements over 12,030
# route states. Raw SS-30..SS-34 stay bound and are never overwritten (P0-09.6).

CabinDerivationDisagreement = model.Relationship(
    f"{RouteState:state} disagrees with the DV-26 economy-excluding-premium derivation"
)
model.define(CabinDerivationDisagreement(RouteState)).where(
    RouteState.economy_excluding_premium
    != RouteState.economy_class_seats - RouteState.premium_economy_seats
)

# --- 4. Snapshot-gap visibility ---------------------------------------------------
#
# A route-state segment that opened or closed across a missing or incomplete snapshot is
# evidence Q05 must carry, and an incomplete snapshot must never be read as a removal. The two
# flags are lifted from the DV-16 columns so the query layer joins a named flag rather than
# re-deriving the gap arithmetic.

RouteStateOpenCrossesGap = model.Relationship(
    f"{RouteState:state} opened across a snapshot gap"
)
model.define(RouteStateOpenCrossesGap(RouteState)).where(
    RouteState.open_crosses_snapshot_gap == True  # noqa: E712
)

RouteStateCloseCrossesGap = model.Relationship(
    f"{RouteState:state} closed across a snapshot gap"
)
model.define(RouteStateCloseCrossesGap(RouteState)).where(
    RouteState.close_crosses_snapshot_gap == True  # noqa: E712
)

# --- 5. The Neo4j SCHEDULES edge --------------------------------------------------
#
# ``(ROUTE_STATE)-[:SCHEDULES]->(PASSENGER_FLIGHT)`` is the one supplied edge that is derived
# rather than loaded, and it is a real ``Relationship`` and not a ``Property``:
# NEO4J_RAI_MAPPING.md calls it "potential one-to-many; no functional claim". One route state
# schedules many operating dates, and one passenger flight is reachable from more than one
# knowledge version of the same schedule key, so neither direction is functional and a
# ``Property`` here would ``FDError``.
#
# It is *derived*, not imported, from the P0-08 conjunction, one clause per line:
#
#   1. exact schedule identity - PH-02 equals SS-01, expressed as both sides resolving to the
#      same ``Schedule`` entity. Only the DV-21 precedence-winning lineage row supplies PH-02,
#      so this is exact by construction rather than by a fixture accident;
#   2. the passenger publish date lies inside the state's half-open knowledge interval;
#   3. the passenger operating date lies inside the state's **inclusive** SS-08/SS-09 operating
#      interval - inclusive on both ends, unlike the knowledge clock; and
#   4. the operating date's ISO weekday is one the state actually operates.
#
# Anything failing the conjunction stays unlinked and visible, which is the point: a missing
# schedule identity or a failed clock applicability is a fact about the source, not a gap to be
# bridged. Both clocks appear in the same rule with their two different conventions, which is
# the same asymmetry Q07 turns on.

RouteStateSchedules = model.Relationship(
    f"{RouteState:state} schedules {PassengerFlight:flight}"
)
RouteState.schedules = RouteStateSchedules

model.define(RouteStateSchedules(RouteState, PassengerFlight)).where(
    RouteState.schedule == PassengerFlight.schedule,
    RouteState.knowledge_valid_from <= PassengerFlight.publish_date,
    PassengerFlight.publish_date < RouteState.knowledge_valid_to,
    RouteState.operating_effective_date <= PassengerFlight.operating_date,
    PassengerFlight.operating_date <= RouteState.operating_discontinue_date,
    RouteStateOperatesOnWeekday(
        RouteState, std_date.isoweekday(PassengerFlight.operating_date)
    ),
)

PassengerFlight.scheduled_by = RouteStateSchedules.alt(
    f"{PassengerFlight:flight} is scheduled by {RouteState:state}"
)
