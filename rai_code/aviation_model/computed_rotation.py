"""computed_rotation.py - the accepted rotation edge, its transitive closure, and Q08 enrichment.

The accepted-rotation-link relationship is one of the five things MODEL-01 owes the ontology,
and it is the one where authoring it once matters most: the ordered traversal, the anomaly
query, and any future path experiment must all walk an **identical** edge set, or the demo can
be shown two different rotations for the same aircraft.

Q08 is an ordinary typed self-reference, not a graph-reasoner question, and that verdict is
evidence-based rather than a preference. Every algorithm in the graph-analysis catalogue returns
an unordered or scalar result - reachability gives ``(source, target)``, distance gives
``(start, end, length)``, WCC gives ``(node, component)``, centrality gives ``(node, score)`` -
while Q08's output is sixteen columns of which twelve are per-leg payload and one is a position
within a path. None of those algorithms produces a position or carries edge payload, so each
would have to be joined back to ``AircraftFlight`` anyway, which is the self-join the baseline
already does.

``leg_order`` therefore comes from the link structure: ``1 + the number of accepted-chain
predecessors``. Sorting the day's legs by departure time and numbering them reproduces the
canonical answer on this fixture and is an explicit fail.

PROBE U-07 settled the termination question. The 1.2.2 ``union`` + ``per(u, v).min(...)``
recursion idiom compiles unchanged on 1.20.1 and produces a complete, correct, finite closure on
a deliberately cyclic edge set in 3.6 seconds, with no visited set and no step bound - because
``min`` over the ``u == v`` base case caps every self-distance at 0 and the lattice is finite.
There is no step-bound parameter in the 1.20.1 API and none is needed. P0-11.5 asks for a
visited set and a finite step bound; the guard here is a different and stronger mechanism -
cycles are excluded at the acceptance rule itself - and that difference is a note, not a risk.
"""

from relationalai.semantics import Bool, Integer
from relationalai.semantics.std import aggregates as aggs

from .constants import DIM_AIRCRAFT_TYPE, DIM_ENGINE_TYPE
from .core_aircraft import Aircraft, AircraftType, DailyAssignment, EngineType
from .core_flight import AircraftFlight, RotationLinkValidation
from .model import model

# --- The accepted rotation edge ---------------------------------------------------
#
# ``Property``, because SOURCE_CONTRACT.md gives "actual flight to next actual flight:
# zero-or-one raw reference" and the accepted link is a subset of the raw one. In a
# ``Property`` all fields except the last are keys, so the FD is ``leg -> next_leg``, which is
# exactly what is wanted. Both same-type slots are role-labelled; without labels ``define()``
# would silently bind both to whichever column is listed first.
#
# The full P0-11.4 acceptance conjunction - target exists, is a different flight, shares the
# aircraft and the AF-06 local date, departs no earlier than the current actual arrival, departs
# *from* the current actual arrival airport (DV-45 = AF-09), and neither leg cancelled - is
# evaluated by DATA-04 and lands as ``IS_ACCEPTED_LINK`` / ``ROTATION_LINK_STATUS`` on
# ``ROTATION_LINK_VALIDATION``. Recomputing it here would put two competing definitions of the
# rotation in the system, which is the failure this module exists to prevent. What RAI owns is
# the *relationship*: one named edge set that every consumer traverses.

AircraftFlight.accepted_next_flight = model.Property(
    f"{AircraftFlight:leg} continues to {AircraftFlight:accepted_next_leg}"
)

_accepted_target = AircraftFlight.ref("accepted_target")
model.define(AircraftFlight.accepted_next_flight(_accepted_target)).where(
    RotationLinkValidation.flight == AircraftFlight,
    RotationLinkValidation.is_accepted_link == True,  # noqa: E712
    RotationLinkValidation.target_flight == _accepted_target,
)

# --- Segment heads ----------------------------------------------------------------
#
# A segment head is a leg with no accepted *inbound* edge. ``model.not_()`` over a ref is the
# documented way to ask for entities without a relationship; a bare ``not_`` on the property
# would not bind the variable.

RotationSegmentHead = model.Relationship(
    f"{AircraftFlight:leg} starts a rotation segment"
)
_inbound = AircraftFlight.ref("inbound")
model.define(RotationSegmentHead(AircraftFlight)).where(
    model.not_(_inbound.accepted_next_flight == AircraftFlight)
)

# --- Transitive position over the accepted edge -----------------------------------
#
# ``rotation_leg_distance(u, v)`` is the minimum number of accepted hops from ``u`` to ``v``,
# with ``0`` for ``u == v``. ``leg_order`` is then ``1 + distance(head, leg)`` and
# ``segment_id`` anchors on the head's ``flight_id``. A cycle is exactly "a node that reaches
# itself at a non-zero distance" in this same closure, so no separate cycle algorithm is needed
# - and the accepted-edge rule already excludes cycles, so the fixture's 8102/8103 pair surfaces
# through ``RotationLinkValidation`` evidence rather than through the chain.

# A ``Property`` and not a ``Relationship``: the *minimum* number of hops is functional per
# (from_leg, to_leg), so the FD is correct and the two-argument call form
# ``rotation_leg_distance(u, n)`` reads the value back inside the recursive step.
rotation_leg_distance = model.Property(
    f"{AircraftFlight:from_leg} reaches {AircraftFlight:to_leg} in {Integer:hops}"
)

_u = AircraftFlight.ref("dist_u")
_v = AircraftFlight.ref("dist_v")
_n = AircraftFlight.ref("dist_n")

model.define(
    rotation_leg_distance(
        _u,
        _v,
        aggs.per(_u, _v).min(
            model.union(
                model.select(0).where(_u == _v),
                model.select(rotation_leg_distance(_u, _n) + 1).where(
                    _n.accepted_next_flight == _v
                ),
            )
        ),
    )
)

# --- Q08 enrichment: the as-of type and engine on the LOCAL date ------------------
#
# The single sharpest trap in Q08. All three canonical legs have AF-06 = 2026-08-31 while
# AF-07 = 2026-09-01 and their UTC departure timestamps fall on 2026-09-01. Enrichment and day
# selection use **AF-06**, the local selected-day basis. Using AF-07, or deriving the date from
# AF-13, shifts the as-of instant by a day and can silently pick the wrong type or engine
# interval. ``TT-US-CLOCK-AUTHORITY`` freezes that assertion.
#
# This is the second of the two places where a materialized as-of rule is correct rather than a
# query-time predicate: the date set is bounded by the ``AircraftFlight`` rows themselves, so no
# calendar is needed and no cross product is possible.
#
# Declared ``Property`` because the value is functional per leg - one leg, one local date, one
# aircraft, one type. If it ever FDErrors, the daily assignments overlap and the model has just
# found a DATA-04 bug for us, which is a feature.

AircraftFlight.as_of_aircraft_type = model.Property(
    f"{AircraftFlight:leg} was of type {AircraftType:as_of_aircraft_type}"
)
AircraftFlight.as_of_engine_type = model.Property(
    f"{AircraftFlight:leg} was fitted with {EngineType:as_of_engine_type}"
)

_type_at_leg = DailyAssignment.ref("type_at_leg")
model.define(AircraftFlight.as_of_aircraft_type(AircraftType)).where(
    AircraftFlight.aircraft == Aircraft,
    _type_at_leg.aircraft == Aircraft,
    _type_at_leg.dimension == DIM_AIRCRAFT_TYPE,
    _type_at_leg.valid_from <= AircraftFlight.flight_departure_date,
    AircraftFlight.flight_departure_date < _type_at_leg.valid_to,
    _type_at_leg.aircraft_type == AircraftType,
)

_engine_at_leg = DailyAssignment.ref("engine_at_leg")
model.define(AircraftFlight.as_of_engine_type(EngineType)).where(
    AircraftFlight.aircraft == Aircraft,
    _engine_at_leg.aircraft == Aircraft,
    _engine_at_leg.dimension == DIM_ENGINE_TYPE,
    _engine_at_leg.valid_from <= AircraftFlight.flight_departure_date,
    AircraftFlight.flight_departure_date < _engine_at_leg.valid_to,
    _engine_at_leg.engine_type == EngineType,
)

# --- DV-32 type discrepancy -------------------------------------------------------
#
# AF-17 ``ACTUAL_SOURCE_AIRCRAFT_TYPE`` is discrepancy *evidence* and is never aircraft-history
# authority (ATTRIBUTE_AUTHORITY.md). The disagreement is reported, never reconciled, and the
# source value is never overwritten. ``Q08-R002`` freezes a ``true`` here: the as-of type is
# ``SYN-TYPE-B`` from history while the actual source reads "Synthetic narrowbody A".
#
# Three-valued in the output - absent where there is no as-of type to compare - so it is a rule
# and not a ``select`` expression, and the two conditions are mutually exclusive.

AircraftFlight.type_discrepancy = model.Property(
    f"{AircraftFlight:leg} disagrees on type {Bool:type_discrepancy}"
)
model.define(AircraftFlight.type_discrepancy(True)).where(
    AircraftFlight.as_of_aircraft_type == AircraftType,
    AircraftType.aircraft_type != AircraftFlight.actual_source_aircraft_type,
)
model.define(AircraftFlight.type_discrepancy(False)).where(
    AircraftFlight.as_of_aircraft_type == AircraftType,
    AircraftType.aircraft_type == AircraftFlight.actual_source_aircraft_type,
)
