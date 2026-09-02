"""computed_aircraft.py - the reusable derived layer over UC1. This is where the RAI content is.

Everything above this file is plumbing: identity, source binding, and two half-open ``Date``
columns. Everything the demo actually argues about lives here.

Six groups of rules:

1. **Dimension subtypes.** One physical assignment table with a ``dimension`` discriminator
   becomes four named streams. ``identity_includes_type`` stays ``False``, so the subtype
   instance *is* its parent entity - one assignment, viewed through its dimension. This buys two
   things. The four independent clocks in Q01 become four visibly independent joins in the query
   code, which is the point of the demo. And Q02 can rank status observations ``.per(Aircraft)``
   instead of ``.per(Aircraft, dimension)``.
1b. **Four dimension-scoped edges off ``Aircraft`` plus three direct one-hop readings**, so the
   supplied Neo4j edge structure is visible on the concept rather than recoverable only through a
   subtype predicate (FIDELITY-01 A2 / A3).
2. **The dense ordinals** that turn "the previous assignment" and "the next qualifying
   assignment" from a four-column lexicographic comparison into one integer comparison.
3. **Q04's reconciliation properties**, ``previous_definition_id`` and the three-valued
   ``is_type_change``.
4. **Q03's month-end rule** - the demo's headline reusable temporal rule, where the type clock
   and the status clock are two independent half-open joins in one rule, visibly not aligned.
5. **Two integrity guards** that RAI cannot declare, so it derives them and the gate asserts
   they are empty.

One thing that is deliberately *not* here: the four-value DV-33 as-of status is not a
materialized property, because it is a function of a date and ``Date`` has an unbounded
extension. ``DIMENSION_QUERY_STATUS`` on the row already decides the two present-row values
(measured live: exactly ``OK`` 97,975 and ``UNKNOWN_STATE`` 4), and ``temporal.dv33_branches``
owns the two absence values. See that function's docstring for why section 5.3's ``|`` chain
could not be used.
"""

from relationalai.semantics import Bool, Date, Integer, String
from relationalai.semantics.std import aggregates as aggs

from .calendar_dates import MonthEnd
from .constants import (
    DIM_AIRCRAFT_STATE,
    DIM_AIRCRAFT_STATUS,
    DIM_AIRCRAFT_TYPE,
    DIM_ENGINE_TYPE,
    SOURCE_UNKNOWN_FUTURE,
    STATUS_IN_SERVICE,
)
from .core_aircraft import (
    Aircraft,
    AircraftConfiguration,
    AircraftStatus,
    AircraftType,
    AuditAssignment,
    DailyAssignment,
    EngineType,
)
from .model import model

# --- 1. Dimension subtypes --------------------------------------------------------

AircraftStateDaily = model.Concept("AircraftStateDailyAssignment", extends=[DailyAssignment])
AircraftTypeDaily = model.Concept("AircraftTypeDailyAssignment", extends=[DailyAssignment])
EngineTypeDaily = model.Concept("EngineTypeDailyAssignment", extends=[DailyAssignment])
AircraftStatusDaily = model.Concept("AircraftStatusDailyAssignment", extends=[DailyAssignment])

model.define(AircraftStateDaily(DailyAssignment)).where(
    DailyAssignment.dimension == DIM_AIRCRAFT_STATE
)
model.define(AircraftTypeDaily(DailyAssignment)).where(
    DailyAssignment.dimension == DIM_AIRCRAFT_TYPE
)
model.define(EngineTypeDaily(DailyAssignment)).where(
    DailyAssignment.dimension == DIM_ENGINE_TYPE
)
model.define(AircraftStatusDaily(DailyAssignment)).where(
    DailyAssignment.dimension == DIM_AIRCRAFT_STATUS
)

AircraftStateAudit = model.Concept("AircraftStateAuditAssignment", extends=[AuditAssignment])
AircraftTypeAudit = model.Concept("AircraftTypeAuditAssignment", extends=[AuditAssignment])
EngineTypeAudit = model.Concept("EngineTypeAuditAssignment", extends=[AuditAssignment])
AircraftStatusAudit = model.Concept("AircraftStatusAuditAssignment", extends=[AuditAssignment])

model.define(AircraftStateAudit(AuditAssignment)).where(
    AuditAssignment.dimension == DIM_AIRCRAFT_STATE
)
model.define(AircraftTypeAudit(AuditAssignment)).where(
    AuditAssignment.dimension == DIM_AIRCRAFT_TYPE
)
model.define(EngineTypeAudit(AuditAssignment)).where(
    AuditAssignment.dimension == DIM_ENGINE_TYPE
)
model.define(AircraftStatusAudit(AuditAssignment)).where(
    AuditAssignment.dimension == DIM_AIRCRAFT_STATUS
)

# --- 1b. Neo4j edge fidelity: four scoped edges and three direct one-hop readings --
#
# FIDELITY-01 findings A2 and A3. The supplied Neo4j model has **four independently clocked
# edges** off ``AIRCRAFT`` - ``HAS``, ``CONFORMED``, ``EQUIPPED``, ``ASSIGNED`` - and in Cypher
# the edge *type* is the dimension scope, so their query cannot make the mistake ours can. Ours
# already did: aircraft 1001 at 2022-05-15 reported both ``OK`` and ``UNKNOWN_STATE`` because an
# unscoped assignment ref ranged over all four dimensions. The ``scope`` parameter on
# ``temporal.dv33_branches`` is a guard rail; these four relationships are the modelling answer,
# so ``Aircraft`` has four visibly distinct outbound edges rather than one plus a predicate.
#
# Additive on purpose. ``Aircraft.daily_assignments`` and ``Aircraft.audit_assignments`` stay for
# the general case, the underlying assignment concept is untouched, and every existing query
# keeps working.

Aircraft.state_assignments = model.Relationship(
    f"{Aircraft:aircraft} has state {DailyAssignment:assignment}"
)
Aircraft.type_assignments = model.Relationship(
    f"{Aircraft:aircraft} has type assignment {DailyAssignment:assignment}"
)
Aircraft.engine_assignments = model.Relationship(
    f"{Aircraft:aircraft} has engine assignment {DailyAssignment:assignment}"
)
Aircraft.status_assignments = model.Relationship(
    f"{Aircraft:aircraft} has status assignment {DailyAssignment:assignment}"
)

model.define(Aircraft.state_assignments(DailyAssignment)).where(
    AircraftStateDaily(DailyAssignment), DailyAssignment.aircraft == Aircraft
)
model.define(Aircraft.type_assignments(DailyAssignment)).where(
    AircraftTypeDaily(DailyAssignment), DailyAssignment.aircraft == Aircraft
)
model.define(Aircraft.engine_assignments(DailyAssignment)).where(
    EngineTypeDaily(DailyAssignment), DailyAssignment.aircraft == Aircraft
)
model.define(Aircraft.status_assignments(DailyAssignment)).where(
    AircraftStatusDaily(DailyAssignment), DailyAssignment.aircraft == Aircraft
)

# The direct one-hop edges, carrying the two Neo4j edge properties. This is the closest possible
# match to ``(AIRCRAFT)-[:CONFORMED]->(AIRCRAFT_TYPE) {valid_from, valid_to}``: one hop from
# ``Aircraft`` to the definition node with the validity interval on the edge itself, exactly
# where a Cypher-literate reviewer looks for it. Without these, every one-hop pattern on
# ``CONFORMED`` / ``EQUIPPED`` / ``ASSIGNED`` costs two hops plus a dimension predicate.
#
# ``Relationship`` and not ``Property``: an aircraft conforms to many types over time, so no
# direction is functional. Four fields is one more than the reading-quality guidance likes, and
# that is the deliberate trade - the fields are the supplied edge's own payload, and the
# two-hop path through the assignment remains available for everything else the assignment
# carries. Consumers should run ``inspect.fields()`` before binding, as for any multi-field
# relationship.

Aircraft.conformed_to = model.Relationship(
    f"{Aircraft:aircraft} conformed to {AircraftType:aircraft_type} "
    f"from {Date:valid_from} until {Date:valid_to}"
)
Aircraft.equipped_with = model.Relationship(
    f"{Aircraft:aircraft} equipped with {EngineType:engine_type} "
    f"from {Date:valid_from} until {Date:valid_to}"
)
Aircraft.assigned_status = model.Relationship(
    f"{Aircraft:aircraft} assigned status {AircraftStatus:status} "
    f"from {Date:valid_from} until {Date:valid_to}"
)

model.define(
    Aircraft.conformed_to(
        Aircraft, AircraftType, DailyAssignment.valid_from, DailyAssignment.valid_to
    )
).where(
    AircraftTypeDaily(DailyAssignment),
    DailyAssignment.aircraft == Aircraft,
    DailyAssignment.aircraft_type == AircraftType,
)
model.define(
    Aircraft.equipped_with(
        Aircraft, EngineType, DailyAssignment.valid_from, DailyAssignment.valid_to
    )
).where(
    EngineTypeDaily(DailyAssignment),
    DailyAssignment.aircraft == Aircraft,
    DailyAssignment.engine_type == EngineType,
)
model.define(
    Aircraft.assigned_status(
        Aircraft, AircraftStatus, DailyAssignment.valid_from, DailyAssignment.valid_to
    )
).where(
    AircraftStatusDaily(DailyAssignment),
    DailyAssignment.aircraft == Aircraft,
    DailyAssignment.status == AircraftStatus,
)

# The two missing inverses (A3). Without these, "which aircraft were ever in Storage" cannot be
# entered from the status node the way it can in Cypher - ``AircraftStatus`` had zero
# relationships in the inventory. ``AircraftConfiguration`` had none either.
AircraftStatus.daily_assignments = model.Relationship(
    f"{AircraftStatus:status} was assigned by {DailyAssignment:assignment}"
)
model.define(AircraftStatus.daily_assignments(DailyAssignment)).where(
    DailyAssignment.status == AircraftStatus
)

AircraftConfiguration.daily_assignments = model.Relationship(
    f"{AircraftConfiguration:configuration} was read by {DailyAssignment:assignment}"
)
model.define(AircraftConfiguration.daily_assignments(DailyAssignment)).where(
    DailyAssignment.configuration == AircraftConfiguration
)

# --- 2. The dense ordinals (shared derivation #2 in QUERY_ROUTING.md) -------------
#
# Audit stream: DATA-04 already materializes the DV-03 dense ordinal over the canonical order
# tuple (AH-05 event_date, AH-03 row_sequence, AH-04 event_sequence, AH-01 event id) as
# ``DIMENSION_SEQUENCE``. Verified live: 3,996 (aircraft, dimension) groups, every one dense
# 1..n, zero violations. The MODEL_INPUT boundary says do not recompute a heavy derivation that
# Snowflake already owns, so ``event_ordinal`` is an alias that gives the ontology the
# vocabulary QUERY_ROUTING.md uses rather than a second window function.
#
# Do NOT substitute ``EVENT_ORDER_RANK``: it is dense per aircraft across all four dimensions
# on the audit stream (999 groups, 1 violation) and is *not* dense per (aircraft, dimension) on
# the daily stream (6 of 3,996 groups violate). Measured, not assumed.

AuditAssignment.event_ordinal = model.Property(
    f"{AuditAssignment:assignment} is at ordinal {Integer:event_ordinal}"
)
model.define(AuditAssignment.event_ordinal(AuditAssignment.dimension_sequence))

# Daily stream: there is no dense ordinal in MODEL_INPUT, so this one is a real PyRel rule.
# ``VALID_FROM`` is unique per (aircraft, dimension) - verified live, zero violations over all
# 3,996 groups - so ranking on it alone is total and deterministic. PROBE U-10 proved
# ``aggs.rank`` with ordering keys plus ``.per()`` materializes correctly as a ``Property``.
DailyAssignment.daily_ordinal = model.Property(
    f"{DailyAssignment:assignment} is at daily ordinal {Integer:daily_ordinal}"
)
model.define(
    DailyAssignment.daily_ordinal(
        aggs.rank(aggs.asc(DailyAssignment.valid_from)).per(
            DailyAssignment.aircraft, DailyAssignment.dimension
        )
    )
)

# --- 3. Q04 reconciliation: previous definition and the three-valued type change ---
#
# Two independently clocked streams placed side by side and never aligned to each other. The
# derivation is strictly *within* one stream: the previous assignment is the one at
# ``daily_ordinal - 1`` for the same aircraft *and the same dimension*, which is why the
# ordinal is partitioned by both.

DailyAssignment.previous_definition_id = model.Property(
    f"{DailyAssignment:assignment} follows definition {String:previous_definition_id}"
)

_prev_type = DailyAssignment.ref("prev_type")
model.define(
    DailyAssignment.previous_definition_id(_prev_type.exact_aircraft_type_subseries)
).where(
    AircraftTypeDaily(DailyAssignment),
    AircraftTypeDaily(_prev_type),
    _prev_type.aircraft == DailyAssignment.aircraft,
    _prev_type.daily_ordinal == DailyAssignment.daily_ordinal - 1,
)

_prev_engine = DailyAssignment.ref("prev_engine")
model.define(
    DailyAssignment.previous_definition_id(_prev_engine.exact_engine_type_subseries)
).where(
    EngineTypeDaily(DailyAssignment),
    EngineTypeDaily(_prev_engine),
    _prev_engine.aircraft == DailyAssignment.aircraft,
    _prev_engine.daily_ordinal == DailyAssignment.daily_ordinal - 1,
)

# ``is_type_change`` is three-valued, which is exactly why it is a rule and not a ``select``
# expression: ``false`` on the first assignment of the type stream, ``true`` on a real change,
# and *absent* (rendering as null) on every engine row. The three conditions are mutually
# exclusive by construction - first-of-stream has no previous value to compare, so the two
# comparison rules cannot reach it - and overlapping conditions on one derived ``Property``
# would be an ``FDError``.
DailyAssignment.is_type_change = model.Property(
    f"{DailyAssignment:assignment} changed type {Bool:is_type_change}"
)
model.define(DailyAssignment.is_type_change(False)).where(
    AircraftTypeDaily(DailyAssignment),
    DailyAssignment.daily_ordinal == 1,
)
model.define(DailyAssignment.is_type_change(True)).where(
    AircraftTypeDaily(DailyAssignment),
    DailyAssignment.previous_definition_id
    != DailyAssignment.exact_aircraft_type_subseries,
)
model.define(DailyAssignment.is_type_change(False)).where(
    AircraftTypeDaily(DailyAssignment),
    DailyAssignment.previous_definition_id
    == DailyAssignment.exact_aircraft_type_subseries,
)

# --- 4. Q03: the bounded as-of rule that SHOULD be a model rule -------------------
#
# The demo's headline reusable temporal rule. The type clock and the status clock are two
# independent half-open joins in one rule, visibly not aligned to each other, and the calendar
# is a joined dimension rather than a parameter sweep - so the identical rule works for an
# irregular set of dates. Q03 is then a single ``count(Aircraft).per(MonthEnd, AircraftType)``
# over this relationship, not 120 queries.
#
# A ``Relationship``, not a ``Property``: the triple (aircraft, month end, type) is the fact,
# and one aircraft is in service on many month ends.

InServiceOnMonthEnd = model.Relationship(
    f"{Aircraft:aircraft} is in service on {MonthEnd:month_end} as {AircraftType:aircraft_type}"
)

_status_at_month_end = DailyAssignment.ref("status_at_month_end")
_type_at_month_end = DailyAssignment.ref("type_at_month_end")

model.define(InServiceOnMonthEnd(Aircraft, MonthEnd, AircraftType)).where(
    # existence, half-open, EOL exclusive (D-0003)
    Aircraft.existence_from <= MonthEnd.month_end,
    MonthEnd.month_end < Aircraft.existence_to,
    # the status clock
    AircraftStatusDaily(_status_at_month_end),
    _status_at_month_end.aircraft == Aircraft,
    _status_at_month_end.valid_from <= MonthEnd.month_end,
    MonthEnd.month_end < _status_at_month_end.valid_to,
    _status_at_month_end.aircraft_status_code == STATUS_IN_SERVICE,
    # the type clock, independently
    AircraftTypeDaily(_type_at_month_end),
    _type_at_month_end.aircraft == Aircraft,
    _type_at_month_end.valid_from <= MonthEnd.month_end,
    MonthEnd.month_end < _type_at_month_end.valid_to,
    _type_at_month_end.aircraft_type == AircraftType,
)

# --- 5. Integrity guards RAI cannot declare ---------------------------------------
#
# ``SD/std/constraints.py`` offers ``unique``, ``exclusive``, ``anyof`` and ``oneof`` and
# nothing else: there is no negative-constraint or minimum-cardinality vocabulary. And PROBE
# U-04 showed ``require(unique(...))`` is a silent no-op in 1.20.1 with *and* without
# ``emit_constraints: True``. So a real guard is a derived flag plus a zero-count assertion in
# the gate, which is what these two are.

# HT-06: the source "unknown future" sentinel must never reach the model. DATA-04 normalises
# 9999-12-31 to NULL plus a companion ``*_IS_UNKNOWN_FUTURE`` boolean, so "unknown future" in
# RAI is the absence of a value plus a flag, never a magic date. Measured live: zero rows.
SentinelLeak = model.Relationship(
    f"{DailyAssignment:assignment} leaked the source unknown-future sentinel"
)
model.define(SentinelLeak(DailyAssignment)).where(
    DailyAssignment.valid_to == SOURCE_UNKNOWN_FUTURE
)

# HT-07: AH-06 ``END_EVENT_DATE`` is provenance only and takes part in no interval predicate.
# Where it disagrees with the derived ``VALID_TO`` the disagreement is surfaced, never
# reconciled. DATA-04 already computes the comparison; this lifts it into a queryable flag so
# the notebook can show the count without re-deriving the rule.
EndEventDisagreement = model.Relationship(
    f"{DailyAssignment:assignment} disagrees with its source end date"
)
model.define(EndEventDisagreement(DailyAssignment)).where(
    DailyAssignment.end_event_date_disagrees_with_valid_to == True  # noqa: E712
)
