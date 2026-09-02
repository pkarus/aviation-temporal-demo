"""rotation.py - Q08 ``actual_rotation_enriched``, the demo's closing beat.

One aircraft, one **source-local** departure date (AF-06), and the answer is the ordered chain of
legs the aircraft actually operated that day: where each leg started and ended, when it actually
left and arrived, whether the link to the next leg was accepted or refused and why, and what
aircraft type and engine the *independent* aircraft-history streams say the airframe carried on
that date. It is the only question that crosses both use cases: ``AIRCRAFT_FLIGHT.aircraft_id`` is
the same identity as UC1's ``Aircraft``, so "what type was that aircraft on that date, and what
engines was it fitted with" is one query here rather than a join across two graphs.

**Why this is a traversal and not a filter plus a sort.** Each leg ends where the next begins, so
``leg_order`` is a property of the link structure, not of the clock. This module derives it as
``1 + the number of accepted-chain predecessors``, read out of ``rotation_leg_distance``, the
transitive closure over ``AircraftFlight.accepted_next_flight`` authored in
``aviation_model.computed_rotation``. Sorting the day's legs by
``actual_gate_departure_time_utc`` and numbering them reproduces the canonical answer on this
fixture and is an explicit fail: it would also silently "repair" the diversion case below.

**The traps this module is written against**, each one a real row in the shipped fixtures:

* *A stopover is one passenger flight but two aircraft flights.* Legs are never de-duplicated
  against the plan, so a rotation legitimately holds more legs than the published schedule
  suggests. Nothing here reads the plan side at all.
* *A DIVERTED flight ends somewhere other than its planned destination.* Continuity is on the
  **actual** arrival airport (AF-09 = DV-45) and the **actual** gate times (AF-13 / AF-14), never
  on a scheduled arrival and never on AF-10. There is no scheduled-arrival column anywhere in
  this file. Flight 7200 is the live proof: it planned SFO to LAX, actually landed at LAS, and
  aircraft 1100's leg 5103 departs from LAX at exactly 7200's arrival minute. A chain built on the
  planned endpoint would link them; the actual chain leaves both as singleton segments.
* *Enriching on the UTC date.* All three canonical legs carry AF-06 2026-08-31 while AF-07 is
  2026-09-01 and the UTC gate departures fall on 2026-09-01. Day selection and enrichment both use
  AF-06. ``TT-US-CLOCK-AUTHORITY`` row ``TTUS-R05`` freezes that assertion, and
  ``flight_departure_date_utc`` is never read by this module.
* *Suppressing the type discrepancy.* AF-17 is discrepancy evidence and never aircraft-history
  authority. ``Q08-R002`` reports ``as_of_aircraft_type_id = SYN-TYPE-B`` from history next to
  ``actual_source_aircraft_type = "Synthetic narrowbody A"`` with ``type_discrepancy = true``. The
  disagreement is reported, never reconciled.
* *Cycle duplication.* Flights 8102 and 8103 form a cycle. Exactly one ``CYCLE`` row is emitted
  per component, anchored at its minimum ``flight_id``, while every member stays queryable as
  evidence (see :func:`rotation_anomaly_evidence`). Emitting one row per member would give 12
  anomaly rows instead of 11.
* *Losing excluded legs.* ``CANCELLED``, ``MISSING_TIME`` and
  ``UNKNOWN_OR_INVALID_CANCELLATION_FLAG`` are ``EXCLUDED`` from the operated chain and still
  visible as anomaly rows.
* *A twelfth anomaly class arriving unannounced.* ``MODEL_INPUT`` also emits
  ``TARGET_NOT_OPERATED`` (D-0020 A5) - a link whose target is itself cancelled, invalid-flagged
  or missing an arrival time. It is outside the eleven-class DV-25 vocabulary the manifest
  declares and the independent SQL oracle has no branch for it, so a conformance harness would
  diverge the first time a selected rotation hit one. It is emitted, because ``is_accepted_link``
  is false and suppressing the row would delete a leg from the chain with no stated reason - and
  every invocation reports it separately through
  :attr:`RotationResult.beyond_manifest_anomaly_classes`. Four legs in the enriched universe carry
  it (5310, 5470, 6190, 6345); none is in a frozen Q08 result set.

**Nothing semantic is recomputed here.** The per-edge acceptance conjunction, the DV-25 anomaly
classification and its precedence, the cycle component and its representative, the transitive
closure, and the as-of type and engine resolution on AF-06 all live in the ontology
(``aviation_model.computed_rotation``, which resolves the same daily-assignment intervals Q01
resolves, scoped per dimension). This module contributes the three things
``QUERY_ROUTING.md`` marks as catalog-layer rather than semantic: parameter validation and typed
error codes, the manifest's ``SYN-ROT`` / ``SYN-ANOM`` presentation labels (kept out of the PyRel
model per the D-0018 / D-0021 bindings), and the frozen output ordering.

**Path reasoner.** Not used, and the verdict is now *measured against the live engine* rather than
cited. ``build/design/QUERY_ROUTING.md`` sets five pass conditions plus a value bar for the
optional ``relationalai.semantics.std.path`` implementation. It was built and run::

    p = path(AircraftFlight.accepted_next_flight).repeat(min=1, max=32).all_paths()
    model.select((idx + 1).alias("leg_order"), node.flight_id, src.flight_id).where(
        p.nodes(0, src), p.nodes(p.length, dst), p.nodes(idx, node),
        src.aircraft == Aircraft, Aircraft.id == aircraft_id,
        src.flight_departure_date == day, RotationSegmentHead(src),
        hval.flight == src, model.not_(hval.rotation_anomaly_class),
        model.not_(dst.accepted_next_flight(out)),
    )

Conditions 1 to 4 pass: it executes on 1.20.1, returns exactly ``[8001, 8002, 8003]`` for
``Q08-CANONICAL`` (and the 5-leg and 4-leg enriched chains), returns nothing for the anomaly-only
aircraft, terminates under the ``repeat`` bound, and the per-leg enrichment joins on without
tripping the interior-binder hook. Condition 5 passes too: 3.4 to 3.6s warm against the baseline's
4.4 to 4.6s.

It still does not ship, on the value bar and on one correctness finding:

* ``repeat(min=1, ...)`` requires at least one edge, so a **single-leg rotation segment is not a
  path**. Aircraft 1225 on 2027-06-24 has two segments - ``5309 -> 5310`` and the singleton
  ``5312`` - and the path implementation returns two rows where the closure baseline returns
  three. ``repeat(min=0, ...)`` is the obvious repair and it raises
  ``[PathUngroundedPatternError] Pattern potentially admits an infinite number of single-node
  paths``. Recovering the singleton therefore needs a union with a separate no-edge branch, which
  is more code and a second correctness surface, not less.
* The maximal-chain filter (``not_`` inbound, ``not_`` outbound) is still needed, so the path adds
  a ``repeat`` bound constant without removing the head and terminal predicates.
* It is a query-level construct and cannot be materialised as an ontology property, so every
  consumer would restate the pattern - the opposite of the one-reusable-semantic-model claim.
* ``shortest_paths()``, ``undirected()`` and ``reverse()`` all raise ``NotImplementedError`` at
  1.20.1, and every ``path()`` call emits a spurious ``RuleLoopWarning``. (Three transient
  ``SnowflakeTableObjectsException``\\ s during the experiment turned out **not** to be the path
  library: they were the shared-model write lock a sibling agent was holding. See
  :func:`retry_on_model_lock`.)

Ordinary typed self-reference is the supported baseline and is what ships.

Run the frozen result sets::

    PYTHONPATH=rai_code .venv/bin/python rai_code/queries/rotation.py
"""

from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from relationalai.semantics.std import aggregates as aggs

QUESTION_ID = "Q08"
CATALOG_ID = "actual_rotation_enriched"

#: The frozen ``output_schema`` column order. ``to_df()`` follows ``select()`` argument order and
#: silently appends ``_2`` on a name collision, so every column is aliased at every call site and
#: the assembled frame is reindexed onto this tuple before it is returned.
OUTPUT_COLUMNS: tuple[str, ...] = (
    "row_id",
    "row_kind",
    "segment_id",
    "leg_order",
    "flight_id",
    "actual_origin",
    "actual_destination",
    "actual_departure_utc",
    "actual_arrival_utc",
    "next_flight_id",
    "link_outcome",
    "anomaly_code",
    "as_of_aircraft_type_id",
    "as_of_engine_type_id",
    "actual_source_aircraft_type",
    "type_discrepancy",
)

#: ``row_kind DESC`` in the frozen ``order_by`` puts ``LEG`` before ``ANOMALY``. Ascending would
#: invert it. Within one result set the two kinds never share a ``segment_id`` because their
#: templates differ, so the leading ``segment_id ASC`` key settles the block order on its own:
#: ``SYN-ANOM-*`` sorts before ``SYN-ROT-*``.
ROW_KIND_LEG = "LEG"
ROW_KIND_ANOMALY = "ANOMALY"

#: DV-25 class whose output rows are collapsed to one per component. The precedence itself, and
#: which member is the representative, are the ontology's answer and are not re-derived here.
CYCLE_ANOMALY_CLASS = "CYCLE"

#: The eleven classes the frozen manifest declares at
#: ``scope.rotation_anomaly_support.anomaly_precedence``. Listed here as a *vocabulary* only - the
#: order in that array is the one D-0021 rejects (it puts ``DIVERSION_ENDPOINT_CONFLICT`` sixth,
#: while ``ATTRIBUTE_AUTHORITY.md:338`` DV-25 puts it eighth and the manifest's own rows follow
#: DV-25). Nothing in this module orders anomalies by class, so the contradiction is inert here;
#: the classification and its precedence are ``MODEL_INPUT``'s answer, read through
#: ``RotationLinkValidation``.
MANIFEST_ANOMALY_CLASSES: frozenset[str] = frozenset(
    {
        "SELF_LOOP",
        CYCLE_ANOMALY_CLASS,
        "MISSING_TARGET",
        "DIFFERENT_AIRCRAFT",
        "OUTSIDE_SELECTED_DAY",
        "BACKWARD_TIME",
        "BROKEN_CONTINUITY",
        "DIVERSION_ENDPOINT_CONFLICT",
        "CANCELLED",
        "MISSING_TIME",
        "UNKNOWN_OR_INVALID_CANCELLATION_FLAG",
    }
)

#: ``TARGET_NOT_OPERATED`` (D-0020 A5) is a twelfth class that ``MODEL_INPUT`` emits for a link
#: whose *target* is cancelled, carries an invalid cancellation flag, or has no actual arrival
#: time. It is outside the DV-25 vocabulary, it is absent from
#: :data:`MANIFEST_ANOMALY_CLASSES`, and - the part that matters - the independent SQL oracle in
#: ``data/oracles/q08_actual_rotation_enriched.sql`` has no branch for it, so a conformance
#: harness diverges the first time a selected rotation hits one. D-0021 records this against A5,
#: which was written when the class had zero rows; the enriched universe has four (flights 5310,
#: 5470, 6190, 6345, none of them in a frozen Q08 result set).
#:
#: The row is **emitted**, not suppressed. ``is_accepted_link`` is false for it, so the chain
#: genuinely stops there; hiding the anomaly would delete a leg from the answer with no stated
#: reason, which is the exact failure mode "losing excluded legs" warns about. Instead every
#: invocation reports which beyond-vocabulary classes it emitted
#: (:attr:`RotationResult.beyond_manifest_anomaly_classes`) so the divergence is loud.
BEYOND_MANIFEST_ANOMALY_CLASS = "TARGET_NOT_OPERATED"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_PATH = _REPO_ROOT / "EXPECTED_ANSWERS.yaml"


# --------------------------------------------------------------------------- errors


class RotationQueryError(Exception):
    """Base for every non-``OK`` invocation of Q08.

    Carries the manifest's two-level outcome: an ``invocation_status`` and an ``error_code``.
    ``EXPECTED_ANSWERS.yaml`` freezes zero rows for these, and the manifest's own object rules
    require a caller to be able to tell a refusal apart from a legitimately empty answer, so the
    refusal is raised rather than returned as an empty frame.
    """

    invocation_status = "ERROR"
    error_code = "ERROR"

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class RotationParameterError(RotationQueryError):
    """A typed parameter violates ``parameter_schema``. No query is executed."""

    invocation_status = "PARAMETER_ERROR"


class RotationNotFound(RotationQueryError):
    """The parameters are well formed and the selection is empty.

    ``Q08-NOT-FOUND`` freezes this for aircraft 1999 on 2026-08-31: the aircraft exists and has
    three actual flights, all in 2040, so the selected day holds none. "Empty is an answer" does
    not apply here - the manifest gives this scenario ``NOT_FOUND`` / ``NO_ACTUAL_FLIGHTS`` rather
    than ``OK`` with zero rows.
    """

    invocation_status = "NOT_FOUND"


class RotationInvariantError(RuntimeError):
    """A structural impossibility in the reconstructed chain.

    Raised rather than returned, because every one of these means the emitted ``leg_order`` would
    be a plausible but wrong sequence. ``accepted_next_flight`` is a ``Property`` so out-degree is
    at most one; a leg reachable from two segment heads (in-degree above one) would double-count,
    and a gap in ``leg_order`` would mean the closure and the head set disagree.
    """


@dataclass(frozen=True)
class RotationResult:
    """A catalog-shaped invocation outcome: status, error code, rows.

    ``QUERY-INT`` owns the catalog layer, so :func:`invoke` exists to hand it the frozen triple
    without making it catch exceptions. The raising form (:func:`actual_rotation_enriched`) stays
    the primary entry point.

    ``beyond_manifest_anomaly_classes`` is the fence around
    :data:`BEYOND_MANIFEST_ANOMALY_CLASS`: any emitted anomaly class outside the manifest's
    eleven-class vocabulary, sorted. Empty for all six frozen Q08 result sets. Non-empty means the
    answer is still the model's truth but the independent SQL oracle will disagree, so a
    conformance harness must report the divergence rather than absorb it.
    """

    invocation_status: str
    error_code: str | None
    rows: pd.DataFrame
    beyond_manifest_anomaly_classes: tuple[str, ...] = ()


# ----------------------------------------------------------------- parameter validation


def _coerce_aircraft_id(value: Any) -> int:
    """AM-01 identity, ``NUMBER(38,0)``, not nullable.

    ``bool`` is rejected explicitly: it is an ``int`` subclass in Python, and ``True`` would
    silently select aircraft 1.
    """
    if value is None:
        raise RotationParameterError(
            "MISSING_AIRCRAFT_ID", "aircraft_id is required and must not be null"
        )
    if isinstance(value, bool):
        raise RotationParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id must be an integer, got {value!r}"
        )
    try:
        aircraft_id = int(value)
    except (TypeError, ValueError):
        raise RotationParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id must be an integer, got {value!r}"
        ) from None
    if aircraft_id != value and not isinstance(value, str):
        raise RotationParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id must be integral, got {value!r}"
        )
    if aircraft_id <= 0:
        raise RotationParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id is out of domain: {value!r}"
        )
    return aircraft_id


def _coerce_departure_date(value: Any) -> dt.date:
    """AF-06, the **source-local** departure date. Never AF-07 and never derived from AF-13.

    A ``datetime`` is narrowed to its date part; an ISO string is parsed. An uncastable string
    such as ``2026-02-30`` is ``INVALID_DATE``, matching the manifest's naming for Q06.
    """
    if value is None:
        raise RotationParameterError(
            "MISSING_FLIGHT_DEPARTURE_DATE",
            "flight_departure_date is required and must not be null",
        )
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            raise RotationParameterError(
                "INVALID_DATE", f"flight_departure_date is not a valid date: {value!r}"
            ) from None
    raise RotationParameterError(
        "INVALID_DATE", f"flight_departure_date must be a DATE, got {value!r}"
    )


# ------------------------------------------------------------------------- pandas helpers
#
# Every cell that leaves RAI goes through one of these. Integer aggregates come back as an
# ``Int128Array`` whose missing element is ``pd.NA``, a sparse property renders as ``NaN`` in an
# object or ``StringDtype`` column, and a missing ``DateTime`` renders as ``NaT``. All three mean
# "no fact" and all three must become ``None`` before they are compared against the manifest's
# YAML nulls.


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _int_or_none(value: Any) -> int | None:
    return None if _is_missing(value) else int(value)


def _str_or_none(value: Any) -> str | None:
    return None if _is_missing(value) else str(value)


def _bool_or_none(value: Any) -> bool | None:
    return None if _is_missing(value) else bool(value)


def _datetime_or_none(value: Any) -> dt.datetime | None:
    if _is_missing(value):
        return None
    stamp = pd.Timestamp(value)
    return stamp.to_pydatetime()


# ------------------------------------------------------------------------------ queries


def _default_package():
    """Import the ontology package lazily.

    ``aviation_model`` constructs the single ``Model`` at import time and a second ``Model`` in
    one interpreter makes the free ``distinct(...)`` raise ``[Ambiguous model]`` (PROBE N-02), so
    importing this module must not build one. Callers that already hold the package pass it in.
    """
    import aviation_model

    return aviation_model


# ------------------------------------------------------------------ concurrency: the model lock
#
# Importing any query module installs the ontology, which is a **write transaction** on the shared
# `aviation_temporal` model. While it is open, another process's read does not queue - it fails,
# and the failure surfaces two levels away from its cause: the SDK reports
# ``SnowflakeTableObjectsException: Getting the following table failed with the error in
# Snowflake``, and only the debug span carries the real text, ``model is currently locked by
# active write transaction(s)``. Measured here: three of four path-experiment invocations in one
# process, and one of forty-one test cases, all while a sibling query agent was installing its own
# module. Retrying is correct; debugging the query is not.

#: Substrings that identify a lock collision rather than a defect. Matched against the whole
#: exception chain because the informative text is nested inside the SDK's wrapper.
_MODEL_LOCK_MARKERS = (
    "model is currently locked",
    "Getting the following table failed with the error in Snowflake",
)

MODEL_LOCK_ATTEMPTS = 6
MODEL_LOCK_BACKOFF_SECONDS = 20.0


def is_model_lock_error(error: BaseException) -> bool:
    """True when an exception (or anything it wraps) is the shared-model write lock."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = f"{type(current).__name__}: {current}"
        if any(marker in text for marker in _MODEL_LOCK_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


def retry_on_model_lock(
    call,
    *,
    attempts: int = MODEL_LOCK_ATTEMPTS,
    backoff_seconds: float = MODEL_LOCK_BACKOFF_SECONDS,
    on_retry=None,
):
    """Run ``call()``, retrying only while a sibling holds the model's write lock.

    Deliberately narrow. Any exception that is not :func:`is_model_lock_error` propagates on the
    first attempt, because a retry loop that swallows a real ``TyperError`` or an empty-frame
    ``KeyError`` would turn a query bug into a slow query bug.
    """
    import time

    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - re-raised unless it is the lock
            if attempt == attempts or not is_model_lock_error(error):
                raise
            if on_retry is not None:
                on_retry(attempt, error)
            time.sleep(backoff_seconds)
    raise AssertionError("unreachable")


def warm_model(am=None, **retry_kwargs):
    """Take the model lock hit once, up front, on a query too small to be anything else.

    Call this before a timed run or a test session so a sibling's install shows up here rather
    than as a failure attributed to whichever result set happened to be first.
    """
    package = am if am is not None else _default_package()
    retry_on_model_lock(
        lambda: package.model.select(aggs.count(package.AircraftFlight).alias("n")).to_df(),
        **retry_kwargs,
    )
    return package


def selected_leg_count(am, aircraft_id: int, day: dt.date) -> int:
    """How many actual legs the aircraft flew on the selected AF-06 date.

    This is the ``NOT_FOUND`` gate and it is deliberately its own query: it separates "this
    aircraft did not fly that day" from "it flew and every link was refused", which are different
    answers with the same row count in the anomaly-only case.

    An empty RAI result is a **zero-column** DataFrame rather than a zero-row frame with the
    expected columns (PROBE D11), so the shape is checked before any cell is read.
    """
    df = (
        am.model.select(aggs.count(am.AircraftFlight).alias("n"))
        .where(
            am.AircraftFlight.aircraft == am.Aircraft,
            am.Aircraft.id == aircraft_id,
            am.AircraftFlight.flight_departure_date == day,
        )
        .to_df()
    )
    if df.shape[0] == 0 or df.shape[1] == 0:
        return 0
    return _int_or_none(df.iloc[0, 0]) or 0


def chain_legs(am, aircraft_id: int, day: dt.date) -> pd.DataFrame:
    """The operated chain: one row per leg, with its segment head and its traversal position.

    The whole question is in the ``where`` clause, so it is worth reading slowly.

    * ``RotationSegmentHead(head)`` is a leg with no accepted **inbound** edge, authored in the
      ontology as ``not_(inbound.accepted_next_flight == leg)``.
    * ``model.not_(head_val.rotation_anomaly_class)`` requires the head's own validated link to
      carry no DV-25 anomaly class. It is a negation over the property's *existence*: writing
      ``not_(head_val.rotation_anomaly_class == "CYCLE")`` would ask "is there some class this is
      not equal to", which is true for nearly every row. Filtering the **head** alone is
      sufficient and is exactly the independent oracle's ``chain_start`` predicate, because an
      accepted edge can only leave an anomaly-free leg; a leg whose own outgoing link is
      anomalous can therefore still be a chain member (reached by an accepted edge) while also
      appearing as an anomaly row. No shipped fixture exercises that overlap, and it is the
      oracle's behaviour too.
    * ``rotation_leg_distance(head, leg)`` is the transitive closure over the accepted edge,
      appearing twice on purpose: once in ``where`` so a pair with no path is excluded rather than
      rendered as ``NaN``, and once in ``select`` where ``+ 1`` turns "hops from the head" into
      ``leg_order``. That is the *only* source of ordering in this module.
    * ``leg_val.flight == leg`` reads DV-24 for the leg's own link, which is the ``link_outcome``.
      Exactly one ``RotationLinkValidation`` row exists per flight (3,900 of 3,900), the terminal
      one carrying the literal ``NO_TARGET`` token, so this cannot inflate.

    Endpoints are read through the resolved ``Airport`` entity, so the ``SYN-AP-*`` internal-ID
    code system is honoured structurally. Planned endpoints are public IATA labels resolved
    against a different field and are never joined here.
    """
    head = am.AircraftFlight.ref("rotation_head")
    head_val = am.RotationLinkValidation.ref("rotation_head_validation")
    leg_val = am.RotationLinkValidation.ref("rotation_leg_validation")
    leg = am.AircraftFlight
    return (
        am.model.select(
            head.flight_id.alias("segment_head_flight_id"),
            (am.rotation_leg_distance(head, leg) + 1).alias("leg_order"),
            leg.flight_id.alias("flight_id"),
            leg.actual_origin.airport_id.alias("actual_origin"),
            leg.actual_destination.airport_id.alias("actual_destination"),
            leg.actual_gate_departure_time_utc.alias("actual_departure_utc"),
            leg.actual_gate_arrival_time_utc.alias("actual_arrival_utc"),
            leg.next_flight_id.alias("next_flight_id"),
            leg_val.rotation_link_status.alias("link_outcome"),
            leg.as_of_aircraft_type.subseries.alias("as_of_aircraft_type_id"),
            leg.as_of_engine_type.subseries.alias("as_of_engine_type_id"),
            leg.actual_source_aircraft_type.alias("actual_source_aircraft_type"),
            leg.type_discrepancy.alias("type_discrepancy"),
        )
        .where(
            leg.aircraft == am.Aircraft,
            am.Aircraft.id == aircraft_id,
            leg.flight_departure_date == day,
            am.RotationSegmentHead(head),
            head_val.flight == head,
            am.model.not_(head_val.rotation_anomaly_class),
            am.rotation_leg_distance(head, leg),
            leg_val.flight == leg,
        )
        .to_df()
    )


def rotation_anomalies(am, aircraft_id: int, day: dt.date, *, deduplicate_cycles: bool = True) -> pd.DataFrame:
    """The typed anomaly companion set: one row per refused or excluded leg.

    ``where(val.rotation_anomaly_class)`` binds the bare property, which requires a value to
    exist, so an anomaly-free leg does not appear. The DV-25 class and its precedence are the
    ontology's answer; nothing is reclassified here.

    ``deduplicate_cycles`` applies the presentation rule from ``DEMO_QUESTIONS.md``: one ``CYCLE``
    row per component, anchored at its minimum ``flight_id``. It is expressed as
    ``not_(class == CYCLE, is_cycle_representative == False)``, which is ``NOT(A AND B)`` over two
    literal comparisons on an already-bound reference. Note ``== False`` rather than a bare
    property reference: ``where(Concept.bool_property)`` matches every entity that *has* the
    property regardless of value. Pass ``False`` to see the retained evidence, which is what
    :func:`rotation_anomaly_evidence` does.
    """
    val = am.RotationLinkValidation.ref("rotation_anomaly_validation")
    leg = am.AircraftFlight
    conditions = [
        leg.aircraft == am.Aircraft,
        am.Aircraft.id == aircraft_id,
        leg.flight_departure_date == day,
        val.flight == leg,
        val.rotation_anomaly_class,
    ]
    if deduplicate_cycles:
        conditions.append(
            am.model.not_(
                val.rotation_anomaly_class == CYCLE_ANOMALY_CLASS,
                val.is_cycle_representative == False,  # noqa: E712
            )
        )
    return (
        am.model.select(
            leg.flight_id.alias("flight_id"),
            leg.actual_origin.airport_id.alias("actual_origin"),
            leg.actual_destination.airport_id.alias("actual_destination"),
            leg.actual_gate_departure_time_utc.alias("actual_departure_utc"),
            leg.actual_gate_arrival_time_utc.alias("actual_arrival_utc"),
            leg.next_flight_id.alias("next_flight_id"),
            val.rotation_link_status.alias("link_outcome"),
            val.rotation_anomaly_class.alias("anomaly_code"),
            val.cycle_component_id.alias("cycle_component_id"),
            val.is_cycle_representative.alias("is_cycle_representative"),
        )
        .where(*conditions)
        .to_df()
    )


def rotation_anomaly_evidence(am, aircraft_id: int, day: dt.date) -> pd.DataFrame:
    """Every anomaly row including the cycle members the output collapses.

    The contract is "retain all member and link evidence, emit one row per component". This is the
    retained half, and it is what makes the collapse auditable rather than a silent drop: flight
    8103 is here and is not in the answer.
    """
    return rotation_anomalies(am, aircraft_id, day, deduplicate_cycles=False)


# ---------------------------------------------------------------------------- assembly


def _segment_id(aircraft_id: int, day: dt.date, ordinal: int) -> str:
    """``SYN-ROT-<aircraft>-<YYYYMMDD>-<NN>``.

    A manifest-adopted presentation label (D-0021 reclassified Q08's 14 ``segment_id`` cells as
    exactly that), deliberately assembled here and not in the PyRel model, per the D-0018
    binding that keeps output templates out of the ontology.
    """
    return f"SYN-ROT-{aircraft_id}-{day.strftime('%Y%m%d')}-{ordinal:02d}"


def _anomaly_segment_id(ordinal: int) -> str:
    """``SYN-ANOM-<NN>``, ordinal by ``flight_id`` ascending. Also manifest-adopted."""
    return f"SYN-ANOM-{ordinal:02d}"


def _leg_record(row: pd.Series, segment_id: str) -> dict[str, Any]:
    return {
        "row_kind": ROW_KIND_LEG,
        "segment_id": segment_id,
        "leg_order": _int_or_none(row["leg_order"]),
        "flight_id": _int_or_none(row["flight_id"]),
        "actual_origin": _str_or_none(row["actual_origin"]),
        "actual_destination": _str_or_none(row["actual_destination"]),
        "actual_departure_utc": _datetime_or_none(row["actual_departure_utc"]),
        "actual_arrival_utc": _datetime_or_none(row["actual_arrival_utc"]),
        "next_flight_id": _int_or_none(row["next_flight_id"]),
        "link_outcome": _str_or_none(row["link_outcome"]),
        # A LEG row never carries an anomaly code. The refusal that ended the chain, if there was
        # one, is reported on its own ANOMALY row.
        "anomaly_code": None,
        "as_of_aircraft_type_id": _str_or_none(row["as_of_aircraft_type_id"]),
        "as_of_engine_type_id": _str_or_none(row["as_of_engine_type_id"]),
        "actual_source_aircraft_type": _str_or_none(row["actual_source_aircraft_type"]),
        "type_discrepancy": _bool_or_none(row["type_discrepancy"]),
    }


def _anomaly_record(row: pd.Series, segment_id: str) -> dict[str, Any]:
    return {
        "row_kind": ROW_KIND_ANOMALY,
        "segment_id": segment_id,
        # An anomaly has no position in the operated chain, so leg_order and all four enrichment
        # columns are null. Filling them in would imply the leg was operated in sequence.
        "leg_order": None,
        "flight_id": _int_or_none(row["flight_id"]),
        "actual_origin": _str_or_none(row["actual_origin"]),
        "actual_destination": _str_or_none(row["actual_destination"]),
        "actual_departure_utc": _datetime_or_none(row["actual_departure_utc"]),
        "actual_arrival_utc": _datetime_or_none(row["actual_arrival_utc"]),
        "next_flight_id": _int_or_none(row["next_flight_id"]),
        "link_outcome": _str_or_none(row["link_outcome"]),
        "anomaly_code": _str_or_none(row["anomaly_code"]),
        "as_of_aircraft_type_id": None,
        "as_of_engine_type_id": None,
        "actual_source_aircraft_type": None,
        "type_discrepancy": None,
    }


#: Default ``row_id`` label shape, the one the v1.1.1 result sets use (``Q08-R001``). The v1.2.0
#: result sets label their rows ``Q08-ENRICHED-ROTATION-R0001`` instead - a different prefix and a
#: different zero-pad width. ``row_id`` is a *supplied* manifest label (D-0021 counts Q08's 14
#: ``row_id`` cells as supplied, not derived), so reproducing either shape is a caller's choice and
#: not a semantic claim; :func:`row_id_label_format` recovers it from the manifest.
DEFAULT_ROW_ID_PREFIX = f"{QUESTION_ID}-R"
DEFAULT_ROW_ID_WIDTH = 3


def _assemble(
    leg_rows: pd.DataFrame,
    anomaly_rows: pd.DataFrame,
    aircraft_id: int,
    day: dt.date,
    row_id_start: int,
    row_id_prefix: str,
    row_id_width: int,
) -> pd.DataFrame:
    """Build the frozen frame in the frozen order, without re-deriving any order.

    The sequence is constructed rather than sorted into place:

    * ``SYN-ANOM-*`` blocks come first because ``segment_id ASC`` is the leading order key and
      ``A`` precedes ``R``. Within them the ordinal, and therefore the order, is ``flight_id``
      ascending, which is the manifest's presentation rule for the anomaly companion set.
    * ``SYN-ROT-*`` segments follow, numbered by their head's ``flight_id`` ascending, and inside
      each segment the rows are placed by ``leg_order`` - the value the traversal produced. No
      time column is ever an ordering key.
    """
    records: list[dict[str, Any]] = []

    if anomaly_rows.shape[1] > 0 and not anomaly_rows.empty:
        ordered_anomalies = anomaly_rows.sort_values("flight_id", kind="stable")
        for ordinal, (_, row) in enumerate(ordered_anomalies.iterrows(), start=1):
            records.append(_anomaly_record(row, _anomaly_segment_id(ordinal)))

    if leg_rows.shape[1] > 0 and not leg_rows.empty:
        heads = sorted({_int_or_none(v) for v in leg_rows["segment_head_flight_id"]})
        seen: set[int] = set()
        for ordinal, head_flight_id in enumerate(heads, start=1):
            segment = leg_rows[
                leg_rows["segment_head_flight_id"].map(_int_or_none) == head_flight_id
            ]
            positions = [_int_or_none(v) for v in segment["leg_order"]]
            if sorted(positions) != list(range(1, len(positions) + 1)):
                raise RotationInvariantError(
                    f"segment anchored at flight {head_flight_id} has leg_order {sorted(positions)}, "
                    f"expected 1..{len(positions)}"
                )
            segment_id = _segment_id(aircraft_id, day, ordinal)
            for _, row in segment.sort_values("leg_order", kind="stable").iterrows():
                flight_id = _int_or_none(row["flight_id"])
                if flight_id in seen:
                    raise RotationInvariantError(
                        f"flight {flight_id} is reachable from more than one segment head; "
                        "the accepted edge set is not a set of disjoint chains"
                    )
                seen.add(flight_id)
                records.append(_leg_record(row, segment_id))

    row_ids = itertools.count(row_id_start)
    for record in records:
        record["row_id"] = f"{row_id_prefix}{next(row_ids):0{row_id_width}d}"

    frame = pd.DataFrame.from_records(records, columns=list(OUTPUT_COLUMNS))
    return _typed(frame)


def _typed(frame: pd.DataFrame) -> pd.DataFrame:
    """Give the frame the frozen ``output_schema`` types.

    ``NUMBER(38,0)`` nullable columns become pandas nullable ``Int64`` rather than ``float64``, so
    a flight id never comes back as ``8002.0``; ``BOOLEAN`` nullable becomes ``boolean`` so the
    third state stays ``NA`` instead of collapsing to ``False``; and the two ``TIMESTAMP_NTZ``
    columns become ``datetime64[ns]`` so a missing gate time is ``NaT``.
    """
    frame = frame.copy()
    for column in ("leg_order", "flight_id", "next_flight_id"):
        frame[column] = pd.array(
            [_int_or_none(v) for v in frame[column]], dtype="Int64"
        )
    for column in ("actual_departure_utc", "actual_arrival_utc"):
        frame[column] = pd.to_datetime(
            pd.Series([_datetime_or_none(v) for v in frame[column]], dtype="object"),
            errors="raise",
        )
    frame["type_discrepancy"] = pd.array(
        [_bool_or_none(v) for v in frame["type_discrepancy"]], dtype="boolean"
    )
    for column in (
        "row_id",
        "row_kind",
        "segment_id",
        "actual_origin",
        "actual_destination",
        "link_outcome",
        "anomaly_code",
        "as_of_aircraft_type_id",
        "as_of_engine_type_id",
        "actual_source_aircraft_type",
    ):
        frame[column] = pd.Series(
            [_str_or_none(v) for v in frame[column]], dtype="object"
        )
    return frame.reset_index(drop=True)


# ------------------------------------------------------------------------- entry points


def actual_rotation_enriched(
    aircraft_id: Any,
    flight_departure_date: Any,
    *,
    am=None,
    row_id_start: int = 1,
    row_id_prefix: str = DEFAULT_ROW_ID_PREFIX,
    row_id_width: int = DEFAULT_ROW_ID_WIDTH,
) -> pd.DataFrame:
    """Q08. The validated, ordered, enriched actual rotation of one aircraft on one local day.

    Parameters
    ----------
    aircraft_id:
        AM-01 identity, ``NUMBER(38,0)``, required.
    flight_departure_date:
        AF-06, the source-local departure date, ``DATE``, required. A ``date``, a ``datetime`` or
        an ISO string.
    am:
        The loaded ``aviation_model`` package. Imported on demand when omitted; pass it in to
        keep one ``Model`` per process.
    row_id_start:
        First ``row_id`` ordinal. ``row_id`` is a *supplied* manifest label rather than a derived
        value (D-0021 counts Q08's 14 ``row_id`` cells as supplied), and the manifest numbers it
        continuously across result sets, so the offset is a caller's choice:
        ``Q08-CANONICAL`` starts at 1 and ``Q08-ANOMALIES`` at 4.
    row_id_prefix, row_id_width:
        The rest of the label shape, for the same reason. v1.1.1 uses ``Q08-R`` and 3 digits;
        the v1.2.0 result sets use their own ``Q08-<SET>-R`` prefix and 4 digits.
        :func:`row_id_label_format` reads both off the manifest.

    Returns
    -------
    A DataFrame with exactly :data:`OUTPUT_COLUMNS`, in the frozen ``order_by`` sequence.

    Raises
    ------
    RotationParameterError
        A typed parameter is null or out of domain. No query runs.
    RotationNotFound
        ``NO_ACTUAL_FLIGHTS``: the aircraft flew no leg on that AF-06 date.
    """
    aircraft = _coerce_aircraft_id(aircraft_id)
    day = _coerce_departure_date(flight_departure_date)
    package = am if am is not None else _default_package()

    if selected_leg_count(package, aircraft, day) == 0:
        raise RotationNotFound(
            "NO_ACTUAL_FLIGHTS",
            f"aircraft {aircraft} operated no actual flight on {day.isoformat()}",
        )

    legs = chain_legs(package, aircraft, day)
    anomalies = rotation_anomalies(package, aircraft, day)
    return _assemble(
        legs, anomalies, aircraft, day, row_id_start, row_id_prefix, row_id_width
    )


def beyond_manifest_anomaly_classes(frame: pd.DataFrame) -> tuple[str, ...]:
    """Emitted anomaly classes outside the manifest's eleven-class DV-25 vocabulary.

    Today that is only :data:`BEYOND_MANIFEST_ANOMALY_CLASS`, but the check is written against
    the vocabulary rather than against that one literal, so a future ``MODEL_INPUT`` class is
    caught the same way instead of arriving unannounced.
    """
    if frame.shape[1] == 0 or frame.empty:
        return ()
    emitted = {
        _str_or_none(value)
        for value in frame["anomaly_code"]
        if _str_or_none(value) is not None
    }
    return tuple(sorted(emitted - MANIFEST_ANOMALY_CLASSES))


def invoke(
    aircraft_id: Any,
    flight_departure_date: Any,
    *,
    am=None,
    row_id_start: int = 1,
    row_id_prefix: str = DEFAULT_ROW_ID_PREFIX,
    row_id_width: int = DEFAULT_ROW_ID_WIDTH,
) -> RotationResult:
    """:func:`actual_rotation_enriched` as a catalog triple instead of an exception."""
    try:
        rows = actual_rotation_enriched(
            aircraft_id,
            flight_departure_date,
            am=am,
            row_id_start=row_id_start,
            row_id_prefix=row_id_prefix,
            row_id_width=row_id_width,
        )
    except RotationQueryError as error:
        empty = _typed(pd.DataFrame(columns=list(OUTPUT_COLUMNS)))
        return RotationResult(type(error).invocation_status, error.error_code, empty)
    return RotationResult("OK", None, rows, beyond_manifest_anomaly_classes(rows))


# --------------------------------------------------------------- frozen-answer comparison


def canonical_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """One canonical dict per row, in row order, for comparison against the manifest.

    Absence is ``None`` whichever way pandas rendered it (``NA``, ``NaN``, ``NaT``), integers are
    ``int`` rather than ``Int64`` scalars, and timestamps are naive ``datetime`` objects, which is
    what the manifest's ``timestamp_representation`` ("cast to TIMESTAMP_NTZ before comparison")
    asks for.
    """
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "row_id": _str_or_none(row["row_id"]),
                "row_kind": _str_or_none(row["row_kind"]),
                "segment_id": _str_or_none(row["segment_id"]),
                "leg_order": _int_or_none(row["leg_order"]),
                "flight_id": _int_or_none(row["flight_id"]),
                "actual_origin": _str_or_none(row["actual_origin"]),
                "actual_destination": _str_or_none(row["actual_destination"]),
                "actual_departure_utc": _datetime_or_none(row["actual_departure_utc"]),
                "actual_arrival_utc": _datetime_or_none(row["actual_arrival_utc"]),
                "next_flight_id": _int_or_none(row["next_flight_id"]),
                "link_outcome": _str_or_none(row["link_outcome"]),
                "anomaly_code": _str_or_none(row["anomaly_code"]),
                "as_of_aircraft_type_id": _str_or_none(row["as_of_aircraft_type_id"]),
                "as_of_engine_type_id": _str_or_none(row["as_of_engine_type_id"]),
                "actual_source_aircraft_type": _str_or_none(
                    row["actual_source_aircraft_type"]
                ),
                "type_discrepancy": _bool_or_none(row["type_discrepancy"]),
            }
        )
    return rows


def _canonical_frozen_cell(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column in ("actual_departure_utc", "actual_arrival_utc"):
        return dt.datetime.fromisoformat(str(value))
    if column in ("leg_order", "flight_id", "next_flight_id"):
        return int(value)
    if column == "type_discrepancy":
        return bool(value)
    return str(value)


def frozen_result_sets() -> list[dict[str, Any]]:
    """Parse Q08 out of ``EXPECTED_ANSWERS.yaml``. The manifest is FROZEN and read-only here."""
    import yaml

    with _MANIFEST_PATH.open() as handle:
        manifest = yaml.safe_load(handle)
    question = next(q for q in manifest["questions"] if q["question_id"] == QUESTION_ID)
    result_sets: list[dict[str, Any]] = []
    for raw in question["result_sets"]:
        rows = [
            {
                column: _canonical_frozen_cell(column, row.get(column))
                for column in OUTPUT_COLUMNS
            }
            for row in raw.get("rows") or []
        ]
        result_sets.append(
            {
                "result_set_id": raw["result_set_id"],
                "manifest_version": raw.get("manifest_version"),
                "parameters": raw["parameters"],
                "invocation_status": raw["invocation_status"],
                "error_code": raw.get("error_code"),
                "expected_cardinality": raw["expected_cardinality"],
                "rows": rows,
            }
        )
    return result_sets


def diff_rows(
    actual: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]
) -> list[str]:
    """Human-readable differences between two canonical row sequences, or an empty list."""
    problems: list[str] = []
    if len(actual) != len(expected):
        problems.append(f"cardinality: got {len(actual)}, expected {len(expected)}")
    for index, (got, want) in enumerate(zip(actual, expected)):
        for column in OUTPUT_COLUMNS:
            if got[column] != want[column]:
                problems.append(
                    f"row {index} ({want.get('row_id')}) {column}: "
                    f"got {got[column]!r}, expected {want[column]!r}"
                )
    return problems


# ------------------------------------------------------------------------------- main


def row_id_label_format(result_set: dict[str, Any]) -> tuple[str, int, int]:
    """Recover ``(prefix, width, start)`` for one result set's ``row_id`` labels.

    The manifest uses two shapes and neither is derivable from the data:

    * v1.1.1 numbers continuously across result sets in one ``Q08-R<3 digits>`` series -
      ``Q08-CANONICAL`` starts at ``Q08-R001`` and ``Q08-ANOMALIES`` resumes at ``Q08-R004``.
    * v1.2.0 restarts at 1 inside a per-result-set prefix with four digits, for example
      ``Q08-ENRICHED-ANOMALIES-R0001``.

    Reading the shape off the expected rows is honest precisely because ``row_id`` is a supplied
    label: D-0021 counts Q08's 14 ``row_id`` cells as supplied rather than derived, so this
    reproduces a presentation convention and asserts nothing about the answer. Every other column
    is compared against the manifest without being told anything.
    """
    rows = result_set["rows"]
    if not rows:
        return DEFAULT_ROW_ID_PREFIX, DEFAULT_ROW_ID_WIDTH, 1
    label = str(rows[0]["row_id"])
    head, _, digits = label.rpartition("R")
    if not digits.isdigit():
        return DEFAULT_ROW_ID_PREFIX, DEFAULT_ROW_ID_WIDTH, 1
    return f"{head}R", len(digits), int(digits)


def main() -> int:
    """Run every frozen Q08 result set against the live model and report pass or fail."""
    import time

    def note_retry(attempt: int, _error: BaseException) -> None:
        print(f"           (model locked by a sibling write; retry {attempt})")

    warm_started = time.time()
    am = warm_model(on_retry=note_retry)
    warm_elapsed = time.time() - warm_started

    result_sets = frozen_result_sets()
    failures = 0

    print(
        f"{QUESTION_ID} {CATALOG_ID}: {len(result_sets)} frozen result sets "
        f"(model install + warm {warm_elapsed:.1f}s)"
    )
    for result_set in result_sets:
        name = result_set["result_set_id"]
        parameters = result_set["parameters"]
        prefix, width, start = row_id_label_format(result_set)
        started = time.time()
        outcome = retry_on_model_lock(
            lambda: invoke(
                parameters["aircraft_id"],
                parameters["flight_departure_date"],
                am=am,
                row_id_start=start,
                row_id_prefix=prefix,
                row_id_width=width,
            ),
            on_retry=note_retry,
        )
        elapsed = time.time() - started

        problems: list[str] = []
        if outcome.invocation_status != result_set["invocation_status"]:
            problems.append(
                f"invocation_status: got {outcome.invocation_status}, "
                f"expected {result_set['invocation_status']}"
            )
        if outcome.error_code != result_set["error_code"]:
            problems.append(
                f"error_code: got {outcome.error_code}, expected {result_set['error_code']}"
            )
        if list(outcome.rows.columns) != list(OUTPUT_COLUMNS):
            problems.append(f"columns: got {list(outcome.rows.columns)}")
        problems.extend(diff_rows(canonical_rows(outcome.rows), result_set["rows"]))

        status = "PASS" if not problems else "FAIL"
        failures += bool(problems)
        version = result_set.get("manifest_version") or "1.1.1"
        print(
            f"  [{status}] {name:<28} v{version}  {len(outcome.rows):>3} rows "
            f"({result_set['expected_cardinality']} expected)  "
            f"{outcome.invocation_status}/{outcome.error_code}  {elapsed:5.1f}s"
        )
        # Never silent: an anomaly class outside the manifest vocabulary is stated even when the
        # result set still matches, because the SQL oracle has no branch for it (D-0020 A5).
        if outcome.beyond_manifest_anomaly_classes:
            print(
                "           NOTE beyond-manifest anomaly class(es) emitted: "
                + ", ".join(outcome.beyond_manifest_anomaly_classes)
            )
        for problem in problems:
            print(f"           {problem}")

    print("ALL FROZEN Q08 RESULT SETS PASS" if not failures else f"{failures} RESULT SET(S) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
