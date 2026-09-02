"""temporal.py - the shared temporal predicate layer. Pure; no model rules of its own.

**This module is the demo's central differentiation claim.** ``NEO4J_PARITY_MATRIX.md`` sells
"one reusable semantic model for the eight bounded workloads instead of query-local temporal
rules". If any of the predicates below get retyped inside ``uc1.py``, ``uc2.py`` or
``rotation.py``, that claim stops being true, and the four questions that resolve the same
as-of instant (Q01 at a parameter date, Q03 at 120 month ends, Q04 across the whole stream, Q08
at each leg's AF-06) get four independent chances to put the exclusive bound on the wrong side.

RAI 1.20.1 has **no temporal support at all**. A search of the whole ``semantics`` tree for
``valid_from``, ``bitemporal``, ``as_of``, ``effective_from`` and ``interval`` returns nothing:
no interval type, no validity-annotated relationship, no as-of operator. Every predicate here is
therefore a hand-written conjunction over two ``Date`` properties. That is honest parity with a
property graph, which has none either - and it is the reason nothing in the API holds a
"one open version per parent" assumption that would have to be relaxed for the multi-open route
case (see ``core_schedule.py``).

The functions return **tuples of conditions**, spread into ``model.where(*...)``. They are
deliberately Python helpers and not model relationships: a materialized
``visible_on(assignment, Date)`` rule would range over the unbounded extension of the ``Date``
core concept and either fail to ground or explode. The two places where the date set *is*
bounded by an entity - Q03's ``MonthEnd`` and Q08's ``AircraftFlight`` - do get real
materialized model rules, in ``computed_aircraft.py`` and ``computed_rotation.py``.

The two interval conventions are NOT interchangeable and must never share one helper:

* **knowledge / validity is half-open**: ``valid_from <= d < valid_to``.
* **operating is inclusive at both ends**: ``effective_date <= d <= discontinue_date``.

``SEMANTIC_DECISIONS.md``: "Knowledge ``valid_to`` is excluded; source operating
``discontinue_date`` is included." A single generic helper applied to both would silently make
the operating upper bound exclusive, lose the last operating day, and break nine rows of the
frozen ``TT-BOTH-CLOCKS`` truth table while still returning a plausible answer. Hence
:func:`visible_on` / :func:`known_on` (half-open) and :func:`operates_on` (inclusive) are
separate functions with deliberately different names.
"""

from __future__ import annotations

import datetime as dt

from .constants import (
    DV33_NO_RECORDED_STATE,
    DV33_OK,
    DV33_OUTSIDE_EXISTENCE,
    DV33_UNKNOWN_STATE,
)

# --- Half-open predicates ---------------------------------------------------------


def visible_on(assignment, d):
    """``valid_from <= d < valid_to`` on a daily assignment. P0-02.1 / BRIEF.md.

    Safe without a null guard on the upper bound because DATA-04 guarantees ``VALID_TO`` is
    never NULL: the open case is written as the model sentinel ``9999-01-01``, never as NULL.
    Verified live - zero rows in ``AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT`` carry the *source*
    sentinel ``9999-12-31``, and ``computed_aircraft.SentinelLeak`` keeps proving it.
    """
    return (assignment.valid_from <= d, d < assignment.valid_to)


def within_existence(aircraft, d):
    """``existence_from <= d < existence_to``. D-0003 makes the finite EOL bound exclusive.

    ``Q01-EOL-BOUNDARY`` (aircraft 1002 at 2024-07-01) is the frozen test: all four dimensions
    must come back ``OUTSIDE_EXISTENCE``, which only happens with ``<`` and not ``<=``.
    """
    return (aircraft.existence_from <= d, d < aircraft.existence_to)


def known_on(state, knowledge_date):
    """``knowledge_valid_from <= k < knowledge_valid_to`` on a route state. DV-14 / DV-15.

    Shared derived predicate #4 in ``QUERY_ROUTING.md``: Q05 compares presence across adjacent
    eligible dates, Q06 compares counts seven days apart, Q07 uses it as one half of the
    two-clock filter. The half-open convention has to be byte-identical in all three or Q06's
    zero-crossings and Q07's ``active_schedule_count`` disagree about the same schedule.

    Note ``AT_END`` is ineligible: the knowledge bound is exclusive at the top, which is why
    three of the nine ``TT-BOTH-CLOCKS`` rows fail on this clause alone.
    """
    return (
        state.knowledge_valid_from <= knowledge_date,
        knowledge_date < state.knowledge_valid_to,
    )


# --- Inclusive predicate, plus the weekday join -----------------------------------


def operates_on(state, operating_date: dt.date, weekday_relationship=None):
    """``effective_date <= o <= discontinue_date`` **and** the weekday flag for ``o``.

    Inclusive on BOTH ends, deliberately - SS-09 ``discontinue_date`` is the last operating
    day, not the first excluded one. The ``<=`` on the second clause is the single most
    load-bearing character in this file.

    The weekday integer is computed in Python from the query parameter
    (``operating_date.isoweekday()``, ISO numbering, 1 = Monday) rather than from a RAI date
    part function. That removes any doubt about the day-numbering convention, and
    ``operating_date`` is a required typed parameter anyway (P0-08.3).
    """
    conditions = [
        state.operating_effective_date <= operating_date,
        operating_date <= state.operating_discontinue_date,
    ]
    if weekday_relationship is not None:
        conditions.append(weekday_relationship(state, operating_date.isoweekday()))
    return tuple(conditions)


def iso_weekday(operating_date: dt.date) -> int:
    """ISO weekday of a query parameter, 1 = Monday. Paired with SS-14..SS-20."""
    return operating_date.isoweekday()


# --- DV-33, the four-value as-of dimension status ---------------------------------


def dv33_branches(model, aircraft, assignment, d, *, scope=(), exact_target=None):
    """The four mutually exclusive DV-33 branch condition sets, for one dimension at one date.

    ``scope`` is **required in practice** and is the clauses that restrict ``assignment`` to a
    single dimension - either ``(assignment.dimension == DIM_AIRCRAFT_TYPE,)`` or the subtype
    membership ``(AircraftTypeDaily(assignment),)``. Omitting it is a silent wrong answer, not
    an error, and it cost a live test failure to find: ``AircraftDimensionDailyAssignment`` is
    one physical concept with a ``dimension`` discriminator, so an unscoped ``assignment`` ranges
    over all four dimensions. Aircraft 1001 at 2022-05-15 then reported both ``OK`` (its
    ``aircraft_type`` assignment resolves to ``SYN-TYPE-B``) *and* ``UNKNOWN_STATE`` (its
    ``aircraft_state`` assignment covers the same date and has no ``aircraft_type`` value).
    P0-01.5 makes change detection per dimension; this parameter is where that becomes real.

    The scope is folded into the covering clauses, so it applies inside the negations too - a
    ``NO_RECORDED_STATE`` that ignored the dimension would be answering a different question.

    ``exact_target`` is the optional-target **property chain itself** - for example
    ``typ.aircraft_type`` - and not a comparison. That distinction is the difference between a
    correct classification and a silently overlapping one, and it cost a live test failure to
    find:

    ``model.not_(typ.aircraft_type == AircraftType)`` reads as "there exists some ``AircraftType``
    that this assignment's type is not equal to", which is true for **every** assignment as soon
    as the model holds two aircraft types. Measured: aircraft 1001 at 2022-05-15 fired both
    ``OK`` and ``UNKNOWN_STATE``. The correct negation is over the property's *existence* -
    ``model.not_(typ.aircraft_type)`` - which is the documented shape for "entities without this
    relationship". Binding the bare chain in ``where()`` conversely requires a value to exist,
    so the positive branch is just the chain.

    Returns ``[(status_token, (conditions...)), ...]`` in the contract's strict order. The
    caller spreads each condition tuple into its own ``model.where(...)`` and tags the result
    with the token, which keeps the classification defined exactly once for Q01, Q03, Q04 and
    Q08. A caller that also needs the resolved target in its projection adds its own
    ``assignment.aircraft_type == AircraftType`` clause to the ``OK`` branch.

    Why this is a builder and not an ordered ``|`` fallback, which is what
    ``ONTOLOGY_DESIGN.md`` section 5.3 specified: **the written form does not compile.** PROBE
    D7 ran section 5.3's exact shape and it raised ``[Unground Variable] Variable 'ty' is
    unground`` - ``|`` requires every branch to ground the same variables, and these four
    branches deliberately do not. PROBE D10 then confirmed the same four outcomes are correct
    and stable when authored as mutually exclusive conditions. Separately, ``| None`` raises
    outright (``AttributeError`` inside ``front_compiler``), so the frozen ``null`` cells in
    ``EXPECTED_ANSWERS.yaml`` come from a plain dot-chain rendering absence as ``NaN``, never
    from a ``None`` fallback.

    Mutual exclusivity is structural, not incidental - ``<`` on one boundary and ``>=`` on the
    other - because overlapping conditions on a single derived ``Property`` are an ``FDError``.

    Two of the four values are the presence of a covering assignment and DATA-04 already
    decides between them on the row (``DIMENSION_QUERY_STATUS``, measured live: exactly two
    distinct values, ``OK`` and ``UNKNOWN_STATE``). The other two are the *absence* of a
    covering assignment and can only be decided against a date, which is why they cannot be
    materialized on any row and why this function exists.
    """
    inside = within_existence(aircraft, d)
    covers = (*scope, assignment.aircraft == aircraft, *visible_on(assignment, d))
    covered = (*inside, *covers)

    branches = [(DV33_OUTSIDE_EXISTENCE, (model.not_(*inside),))]
    if exact_target is not None:
        branches.append((DV33_OK, (*covered, exact_target)))
        branches.append((DV33_UNKNOWN_STATE, (*covered, model.not_(exact_target))))
    else:
        branches.append((DV33_OK, covered))
    # ``not_(A, B, C)`` is NOT(A AND B AND C), and ``assignment`` appears nowhere else in this
    # branch, so this reads as "no assignment covers the date" - which is exactly
    # NO_RECORDED_STATE: inside existence, before the first assignment or in a real gap.
    branches.append((DV33_NO_RECORDED_STATE, (*inside, model.not_(*covers))))
    return branches
