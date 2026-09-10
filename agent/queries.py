"""agent/queries.py - the curated Cortex catalog for the eight golden questions.

Every entry in :data:`CATALOG` delegates to a function in ``rai_code/queries`` that already
answers live against the ``aviation_temporal`` ontology and is graded against the frozen
``EXPECTED_ANSWERS.yaml`` manifest. Nothing in this file computes an answer, derives a
temporal predicate, or reshapes a result beyond dropping the supplied ``row_id`` manifest
label and coercing dates to ISO strings so the envelope is JSON-safe.

Four rules this file exists to enforce, all of them from ``AGENTS.md`` semantic invariants and
``CLAIMS_AUDIT.md``.

1. **Two schedule clocks, never one.** ``knowledge_date`` is when the schedule was known;
   ``operating_date`` is when it operates. Q07 requires both, Q05 and Q06 use the knowledge
   clock only, and no function here supplies a default for either. A caller that has not
   stated a clock gets a refusal telling it to ask, not a guess.
2. **Marketing and operating carriers are separate dimensions.** ``carrier_role`` is required
   with no default in Q06 and Q07. The operating role counts only a physical base
   representative, so it can visibly undercount codeshare-only service. That is contracted
   behaviour and must be narrated, not explained away.
3. **Exact and candidate change classes are never merged.** Q05 emits exact additions,
   removals and key-preserving modifications as ``EXACT``, and reports key-shifting amendments
   separately as ``CANDIDATE_UNIQUE`` / ``AMBIGUOUS_CANDIDATE_GROUP`` / ``UNPAIRED_*``. A
   candidate is never asserted as an exact match.
4. **The exact mixed-engine set is not derivable from the supplied schema.** Q01 and Q04 carry
   one reported engine definition plus a count and a ``mixed_engine_set_complete`` flag. There
   is no per-position engine fitment anywhere in the source, and no catalog entry may invent
   one. :func:`demo_scope_and_limits` states this so a refusal is tool-grounded rather than
   improvised.

Two operational facts that shaped the code.

* **The shared named model takes a write lock on import.** A second process reading while a
  first indexes fails with ``prepareIndex: model is currently locked`` rather than waiting.
  :func:`_load_query_modules` therefore imports all three query modules once, together, behind
  :func:`_retry_on_model_lock`. Inside a stored procedure that serialises the whole catalog
  into a single model build per sproc process.
* **Refusals are returned, results are returned, faults are raised.** A contracted refusal
  (typed parameter error, ineligible snapshot endpoint, ``NO_ACTUAL_FLIGHTS``) comes back as a
  structured payload carrying the manifest's own ``invocation_status`` and ``error_code``, so
  the agent can tell "the answer is legitimately empty" apart from "I could not run this".
  Anything else propagates and lands in the tool-result envelope as an error. Nothing is
  swallowed.

``row_id`` is dropped from every payload on purpose. ``DEMO_QUESTIONS.md`` under D-0018 records
that it is a supplied manifest label rather than a derived value, and the independent SQL
oracles do not emit it either.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

# ---------------------------------------------------------------------------------
# Model-lock aware lazy loading
# ---------------------------------------------------------------------------------

_MODEL_LOCK_MARKERS = ("model is currently locked", "prepareindex")
_LOCK_ATTEMPTS = 8
_LOCK_BACKOFF_SECONDS = 20.0

_MODULES: dict[str, Any] | None = None


def _is_model_lock_error(error: BaseException) -> bool:
    """True when ``error`` or anything it wraps is the shared-model write lock."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = f"{type(current).__name__}: {current}".lower()
        if any(marker in text for marker in _MODEL_LOCK_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


def _retry_on_model_lock(call: Callable[[], Any]) -> Any:
    """Run ``call()``, retrying only while a sibling process holds the model write lock.

    Deliberately narrow. Any exception that is not the lock propagates on the first attempt,
    because a retry loop that swallows a real query fault turns a bug into a slow bug.
    """
    for attempt in range(1, _LOCK_ATTEMPTS + 1):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - re-raised unless it is the lock
            if attempt == _LOCK_ATTEMPTS or not _is_model_lock_error(error):
                raise
            time.sleep(_LOCK_BACKOFF_SECONDS)
    raise AssertionError("unreachable")


def _load_query_modules() -> dict[str, Any]:
    """Import the three query modules once per process, together, behind the lock retry.

    Importing ``queries.uc1`` imports ``aviation_model``, which is a write transaction on the
    shared named model. Doing all three imports in one guarded call means one model build per
    process and one place where a concurrent gate run is waited out.
    """
    global _MODULES
    if _MODULES is None:

        def _do_import() -> dict[str, Any]:
            from queries import rotation, uc1, uc2  # noqa: PLC0415 - deliberately lazy

            return {"uc1": uc1, "uc2": uc2, "rotation": rotation}

        _MODULES = _retry_on_model_lock(_do_import)
    return _MODULES


def model_package() -> Any:
    """The loaded ``aviation_model`` package, for ``init_tools`` to hand to the ToolRegistry."""
    _load_query_modules()
    import aviation_model  # noqa: PLC0415 - after _load_query_modules has taken the lock hit

    return aviation_model


# ---------------------------------------------------------------------------------
# Payload shaping
# ---------------------------------------------------------------------------------

_DROPPED_COLUMNS = ("row_id",)


def _scalar(value: Any) -> Any:
    """One cell as a JSON-native value. Dates and timestamps become ISO strings."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, dt.datetime):
        return value.isoformat(sep="T", timespec="seconds")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _ok(
    question: str,
    frame: pd.DataFrame,
    applied_parameters: Mapping[str, Any],
    *,
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    """A successful result: the true row count first, then the rows.

    ``row_count`` is stated separately from ``rows`` because the response envelope trims a
    structured payload by dropping list items from the tail. When that happens the agent still
    sees how many rows the query actually produced and that the payload was truncated, so a
    partial table can never be reported as a complete one.
    """
    columns = [name for name in frame.columns if name not in _DROPPED_COLUMNS]
    rows = [
        {name: _scalar(record.get(name)) for name in columns}
        for record in frame.to_dict("records")
    ]
    payload: dict[str, Any] = {
        "invocation_status": "OK",
        "question": question,
        "applied_parameters": dict(applied_parameters),
        "row_count": len(rows),
        "columns": columns,
        "rows": rows,
    }
    if notes:
        payload["notes"] = list(notes)
    return payload


def _refusal(
    question: str,
    invocation_status: str,
    error_code: str,
    message: str,
    *,
    ask_the_user: str | None = None,
) -> dict[str, Any]:
    """A contracted refusal, carrying the manifest's own two-level outcome.

    ``invocation_status`` distinguishes a refusal from an answer that is legitimately empty.
    ``ask_the_user`` is set when the correct next move is a clarifying question rather than a
    retry: the caller must put that question to the user and must not choose a value itself.
    """
    payload = {
        "invocation_status": invocation_status,
        "question": question,
        "error_code": error_code,
        "row_count": 0,
        "rows": [],
        "message": message,
    }
    if ask_the_user:
        payload["ask_the_user"] = ask_the_user
        payload["do_not"] = (
            "Do not choose a value on the user's behalf and do not answer from a different "
            "parameter set. Ask the question above and stop."
        )
    return payload


def _typed_errors() -> tuple[type, ...]:
    """The three modules' contracted refusal exception types."""
    modules = _load_query_modules()
    return (
        modules["uc1"].QueryParameterError,
        modules["uc2"].Uc2InvocationError,
        modules["rotation"].RotationQueryError,
    )


def _status_of(error: BaseException) -> str:
    """``invocation_status`` off the instance if present, else off the class."""
    return getattr(error, "invocation_status", None) or type(error).invocation_status


# ---------------------------------------------------------------------------------
# Q01 - aircraft_as_of
# ---------------------------------------------------------------------------------


def aircraft_as_of(aircraft_id: int = None, as_of_date: str = None) -> Any:
    """Q01. Reconstruct one aircraft as of one calendar date: type, reported engine, lifecycle
    status, registration and base, each resolved on its own independent daily clock, plus a
    per-dimension resolution status and an is_complete flag. Both aircraft_id (positive
    integer) and as_of_date (ISO date) are required and have no default; if either is missing
    ask the user for it. Absence of a covering interval is reported as a status
    (NO_RECORDED_STATE, UNKNOWN_STATE, OUTSIDE_EXISTENCE), never backfilled from a master or
    current field. engine_type plus engine_count is the reported engine only: the exact
    mixed-engine set is not derivable from the supplied schema and must never be invented.

    Statuses per dimension are one of OK, NO_RECORDED_STATE, UNKNOWN_STATE or
    OUTSIDE_EXISTENCE. ``is_complete`` is true only when all four dimensions resolved to OK.

    Intervals are half-open, ``valid_from <= as_of_date < valid_to``, so a date that is the
    exclusive end of one assignment and the inclusive start of the next resolves to the next.

    Refusals: ``PARAMETER_ERROR`` / ``INVALID_AIRCRAFT_ID`` for a non-integer, non-positive or
    null aircraft id, and ``PARAMETER_ERROR`` / ``INVALID_DATE`` for a date that is not a real
    calendar date. A refusal returns zero rows and is not an answer.
    """
    modules = _load_query_modules()
    uc1 = modules["uc1"]
    if aircraft_id is None or as_of_date is None:
        return _refusal(
            "Q01",
            "PARAMETER_ERROR",
            "MISSING_PARAMETER",
            "aircraft_as_of requires both aircraft_id and as_of_date; neither has a default.",
            ask_the_user="Which aircraft id, and as of which calendar date?",
        )
    try:
        frame = _retry_on_model_lock(
            lambda: uc1.aircraft_as_of(aircraft_id, as_of_date)
        )
    except _typed_errors() as error:
        return _refusal("Q01", _status_of(error), error.error_code, str(error))
    return _ok(
        "Q01",
        frame,
        {"aircraft_id": aircraft_id, "as_of_date": str(as_of_date)},
        notes=(
            "engine_type is the reported engine definition plus engine_count; the exact "
            "mixed-engine set is unsupported by the source schema.",
        ),
    )


# ---------------------------------------------------------------------------------
# Q02 - status_reversion_spells
# ---------------------------------------------------------------------------------


def status_reversion_spells(aircraft_id: int = None) -> Any:
    """Q02. Every In Service to Storage to In Service reversion spell for one aircraft, taken
    from the ordered audit stream rather than a daily projection, with the storage and return
    event ids, their same-day source sequences, the storage duration in calendar days and a
    same_day flag. aircraft_id is required and has no default. Zero rows is a real answer here
    and means the aircraft has no reversion spell; it is not an error and must not be reported
    as one. A -> B -> A is preserved as three assignments, so a later reversion is never
    collapsed into an earlier one.

    Ordering is by ``storage_start_date``, ``storage_start_sequence``, ``storage_event_id``,
    ``return_event_id``. Same-day zero-duration spells are retained: they are exactly what a
    coarse aircraft-plus-date state key loses, and the audit stream keeps them.

    Dates plus source sequence establish audit order. They do not establish intraday elapsed
    time, so ``storage_days`` is a calendar-day difference and nothing finer.

    Refusal: ``PARAMETER_ERROR`` / ``INVALID_AIRCRAFT_ID``.
    """
    modules = _load_query_modules()
    uc1 = modules["uc1"]
    if aircraft_id is None:
        return _refusal(
            "Q02",
            "PARAMETER_ERROR",
            "MISSING_PARAMETER",
            "status_reversion_spells requires aircraft_id; it has no default.",
            ask_the_user="Which aircraft id?",
        )
    try:
        frame = _retry_on_model_lock(lambda: uc1.status_reversion_spells(aircraft_id))
    except _typed_errors() as error:
        return _refusal("Q02", _status_of(error), error.error_code, str(error))
    return _ok("Q02", frame, {"aircraft_id": aircraft_id})


# ---------------------------------------------------------------------------------
# Q02F - fleet_storage_spell_distribution
# ---------------------------------------------------------------------------------


def fleet_storage_spell_distribution(aircraft_scope: str = "FLEET") -> Any:
    """Q02F. The same storage-spell derivation as Q02 with the per-aircraft filter removed,
    bucketed by duration over the whole fleet: spell_count, distinct aircraft_count and the
    observed minimum and maximum storage days in each bucket. The only supported
    aircraft_scope is FLEET; any other value is refused rather than reinterpreted.
    spell_count and aircraft_count differ where one aircraft contributes several spells to one
    bucket, and that difference is deliberate, not a duplicate.

    Buckets are ZERO_DAYS, DAYS_1_TO_7, DAYS_8_TO_30, DAYS_31_TO_90, DAYS_91_TO_365,
    DAYS_366_TO_730 and DAYS_OVER_730, inclusive at both ends and tiling the non-negative
    integers with no gap and no overlap. An empty bucket drops out rather than reporting zero,
    because the frozen answer records observed buckets, not a completed grid.

    Refusal: ``PARAMETER_ERROR`` / ``INVALID_AIRCRAFT_SCOPE``.
    """
    modules = _load_query_modules()
    uc1 = modules["uc1"]
    try:
        frame = _retry_on_model_lock(
            lambda: uc1.fleet_storage_spell_distribution(aircraft_scope)
        )
    except _typed_errors() as error:
        return _refusal("Q02F", _status_of(error), error.error_code, str(error))
    return _ok("Q02F", frame, {"aircraft_scope": aircraft_scope})


# ---------------------------------------------------------------------------------
# Q03 - month_end_fleet_composition
# ---------------------------------------------------------------------------------


def month_end_fleet_composition(
    start_month_end: str = None,
    end_month_end: str = None,
    status: str = "In Service",
) -> Any:
    """Q03. In-service aircraft count per exact aircraft type at every calendar month end
    between start_month_end and end_month_end inclusive. Both bounds are required ISO dates
    with no default and both must be actual month-end dates. The only supported status is
    'In Service'. Types with a zero count at a month end are omitted rather than emitted as
    zero rows, so the row count is smaller than months multiplied by types. A ten-year window
    returns more rows than one tool result can carry: prefer
    month_end_fleet_composition_summary for a whole decade and use this entry for a window
    you intend to read row by row.

    Both the existence bounds and the daily type and status assignments are applied as
    half-open point predicates at each month end, from the same shared temporal layer every
    other question uses.

    Refusals: ``PARAMETER_ERROR`` with ``INVALID_MONTH_END`` or ``INVALID_STATUS``.
    """
    modules = _load_query_modules()
    uc1 = modules["uc1"]
    if start_month_end is None or end_month_end is None:
        return _refusal(
            "Q03",
            "PARAMETER_ERROR",
            "MISSING_PARAMETER",
            "month_end_fleet_composition requires start_month_end and end_month_end.",
            ask_the_user="Which month-end window, from which month end to which month end?",
        )
    try:
        frame = _retry_on_model_lock(
            lambda: uc1.month_end_fleet_composition(start_month_end, end_month_end, status)
        )
    except _typed_errors() as error:
        return _refusal("Q03", _status_of(error), error.error_code, str(error))
    return _ok(
        "Q03",
        frame,
        {
            "start_month_end": str(start_month_end),
            "end_month_end": str(end_month_end),
            "status": status,
        },
    )


def month_end_fleet_composition_summary(
    start_month_end: str = None,
    end_month_end: str = None,
    status: str = "In Service",
) -> Any:
    """Q03 compact. The same month-end fleet composition reduced to one row per aircraft type
    over the whole window, so a ten-year question fits in a single tool result: months present,
    minimum and maximum in-service count, and the first and last month end at which the type
    appears. Same required parameters and same refusals as month_end_fleet_composition, and
    the header reports the total number of distinct month ends and the total number of nonzero
    month-end-by-type rows the full query returns. Use this to state totals; use
    month_end_fleet_composition when the user wants the individual points.

    Nothing is recomputed here: this reduces the identical result frame in pandas after the
    query has run in PyRel.
    """
    detail = month_end_fleet_composition(start_month_end, end_month_end, status)
    if detail.get("invocation_status") != "OK":
        return detail
    rows = detail["rows"]
    per_type: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        per_type.setdefault(
            (row["aircraft_type_id"], row["aircraft_type"]), []
        ).append(row)
    summary = []
    for (type_id, type_label), group in sorted(per_type.items()):
        counts = [row["in_service_aircraft_count"] for row in group]
        month_ends = [row["month_end"] for row in group]
        summary.append(
            {
                "aircraft_type_id": type_id,
                "aircraft_type": type_label,
                "month_ends_present": len(group),
                "minimum_in_service_aircraft_count": min(counts),
                "maximum_in_service_aircraft_count": max(counts),
                "first_month_end": min(month_ends),
                "last_month_end": max(month_ends),
            }
        )
    return {
        "invocation_status": "OK",
        "question": "Q03",
        "applied_parameters": detail["applied_parameters"],
        "distinct_month_ends": len({row["month_end"] for row in rows}),
        "nonzero_month_end_type_rows": detail["row_count"],
        "row_count": len(summary),
        "columns": [
            "aircraft_type_id",
            "aircraft_type",
            "month_ends_present",
            "minimum_in_service_aircraft_count",
            "maximum_in_service_aircraft_count",
            "first_month_end",
            "last_month_end",
        ],
        "rows": summary,
    }


# ---------------------------------------------------------------------------------
# Q04 - type_engine_histories
# ---------------------------------------------------------------------------------


def type_engine_histories(aircraft_id: int = None) -> Any:
    """Q04. The aircraft-type assignment history and the engine-type assignment history for one
    aircraft, side by side as two independently clocked streams that are never boundary
    aligned, with a three-valued is_type_change flag derived only inside the type stream.
    aircraft_id is required and has no default. Rows on the engine dimension carry a null
    is_type_change because the flag is not defined there; that null is meaningful and must not
    be rendered as false. engine_count with mixed_engine_set_complete is the reported engine
    configuration only: a complete per-position mixed-engine set is not derivable from the
    supplied schema and must never be invented.

    ``valid_to`` of ``9999-01-01`` is the model's open-interval sentinel and means the
    assignment is still current, distinct from the source's ``9999-12-31`` unknown future.

    Ordering is ``dimension`` ascending (aircraft_type before engine_type), then ``valid_from``,
    then ``assignment_id``.

    Refusal: ``PARAMETER_ERROR`` / ``INVALID_AIRCRAFT_ID``.
    """
    modules = _load_query_modules()
    uc1 = modules["uc1"]
    if aircraft_id is None:
        return _refusal(
            "Q04",
            "PARAMETER_ERROR",
            "MISSING_PARAMETER",
            "type_engine_histories requires aircraft_id; it has no default.",
            ask_the_user="Which aircraft id?",
        )
    try:
        frame = _retry_on_model_lock(lambda: uc1.type_engine_histories(aircraft_id))
    except _typed_errors() as error:
        return _refusal("Q04", _status_of(error), error.error_code, str(error))
    return _ok(
        "Q04",
        frame,
        {"aircraft_id": aircraft_id},
        notes=(
            "is_type_change is null on engine_type rows by design; the flag is defined only "
            "within the type stream.",
        ),
    )


# ---------------------------------------------------------------------------------
# Q05 - schedule_four_week_changes
# ---------------------------------------------------------------------------------


def schedule_four_week_changes(
    start_knowledge_date: str = None,
    end_knowledge_date: str = None,
    cadence_days: int = None,
) -> Any:
    """Q05. Schedule additions, removals and modifications across consecutive complete weekly
    publish snapshots on the KNOWLEDGE clock only; there is no operating date in this question.
    All three parameters are required with no default. Exact facts and amendment evidence are
    two separate, labelled classes and are never merged: EXACT_ADDITION, EXACT_REMOVAL and
    EXACT_KEY_PRESERVING_MODIFICATION carry exactness EXACT, while a key-shifting amendment is
    reported only as CANDIDATE_UNIQUE, AMBIGUOUS_CANDIDATE_GROUP with its members, or
    UNPAIRED_ADDITION / UNPAIRED_REMOVAL. A candidate is never asserted as an exact match and
    the exact add and remove rows behind a candidate always remain visible. If either endpoint
    is not an eligible complete snapshot the query refuses with ENDPOINT_MISSING and returns
    zero rows rather than substituting a nearby date.

    Snapshot eligibility is ``is_present AND is_complete`` and nothing else. An absent or
    incomplete snapshot never manufactures a removal.

    ``schedule_key`` hashes the effective and discontinue dates, so shifting either date mints
    a new key: presence comparison then sees one removal plus one unrelated addition, and the
    relationship between them is the separately reported candidate. Where one removal is
    compatible with two additions the answer is an ambiguous group with no pair chosen.

    ``row_id`` and the five declared ``event_id`` mnemonics in the frozen manifest are supplied
    labels rather than derived values (D-0018); ``row_id`` is dropped from this payload and
    ``event_id`` is returned as the module computes it.

    Refusals: ``ENDPOINT_MISSING``, and ``PARAMETER_ERROR`` with ``INVALID_DATE``,
    ``MISSING_CADENCE_DAYS`` or ``INVALID_CADENCE_DAYS``.
    """
    modules = _load_query_modules()
    uc2 = modules["uc2"]
    missing = [
        name
        for name, value in (
            ("start_knowledge_date", start_knowledge_date),
            ("end_knowledge_date", end_knowledge_date),
            ("cadence_days", cadence_days),
        )
        if value is None
    ]
    if missing:
        return _refusal(
            "Q05",
            "PARAMETER_ERROR",
            "MISSING_PARAMETER",
            f"schedule_four_week_changes requires {', '.join(missing)}; none has a default.",
            ask_the_user=(
                "Over which knowledge-date window, and at what snapshot cadence in days?"
            ),
        )
    try:
        frame = _retry_on_model_lock(
            lambda: uc2.schedule_four_week_changes(
                start_knowledge_date, end_knowledge_date, cadence_days
            )
        )
    except _typed_errors() as error:
        return _refusal("Q05", _status_of(error), error.error_code, str(error))
    return _ok(
        "Q05",
        frame,
        {
            "clock": "knowledge",
            "start_knowledge_date": str(start_knowledge_date),
            "end_knowledge_date": str(end_knowledge_date),
            "cadence_days": cadence_days,
        },
        notes=(
            "EXACT rows are asserted facts; CANDIDATE, AMBIGUOUS and UNPAIRED rows are "
            "evidence about key-shifting amendments and are never asserted as exact.",
            "event_id is the derived semantic identity "
            "UNLABELLED|comparison_date|event_class|schedule_key|field_name. The UNLABELLED "
            "prefix marks it as computed here rather than taken from a supplied label table; "
            "it is not an error and not a missing value.",
        ),
    )


def schedule_change_class_summary(
    start_knowledge_date: str = None,
    end_knowledge_date: str = None,
    cadence_days: int = None,
) -> Any:
    """Q05 compact. The same knowledge-clock schedule-change classification reduced to counts
    per comparison date and event class, plus totals by exactness, so a long window fits in one
    tool result. Same required parameters and same ENDPOINT_MISSING refusal as
    schedule_four_week_changes. The exactness totals are the point of this entry: they show how
    many rows are asserted EXACT facts versus how many are CANDIDATE, AMBIGUOUS or UNPAIRED
    amendment evidence, and those groups must be reported separately and never added together
    into one 'changes' number.

    Nothing is recomputed here: this reduces the identical result frame in pandas after the
    query has run in PyRel.
    """
    detail = schedule_four_week_changes(
        start_knowledge_date, end_knowledge_date, cadence_days
    )
    if detail.get("invocation_status") != "OK":
        return detail
    rows = detail["rows"]
    per_class: dict[tuple[str, str], int] = {}
    by_exactness: dict[str, int] = {}
    for row in rows:
        key = (row["comparison_date"], row["event_class"])
        per_class[key] = per_class.get(key, 0) + 1
        by_exactness[row["exactness"]] = by_exactness.get(row["exactness"], 0) + 1
    summary = [
        {"comparison_date": date, "event_class": klass, "event_count": count}
        for (date, klass), count in sorted(per_class.items())
    ]
    return {
        "invocation_status": "OK",
        "question": "Q05",
        "applied_parameters": detail["applied_parameters"],
        "total_events": detail["row_count"],
        "comparison_dates": sorted({row["comparison_date"] for row in rows}),
        "events_by_exactness": dict(sorted(by_exactness.items())),
        "row_count": len(summary),
        "columns": ["comparison_date", "event_class", "event_count"],
        "rows": summary,
    }


# ---------------------------------------------------------------------------------
# Q06 - market_latest_vs_seven_days
# ---------------------------------------------------------------------------------


def market_latest_vs_seven_days(
    latest_knowledge_date: str = None,
    comparison_knowledge_date: str = None,
    carrier_role: str = None,
) -> Any:
    """Q06. Airline-and-route markets that were entered or exited between two exact complete
    snapshots on the KNOWLEDGE clock; there is no operating date in this question. carrier_role
    is required and must be either 'marketing' or 'operating'; the two are separate carrier
    dimensions and answer different questions, so if the user has not said which one they mean,
    ask rather than choosing. Both knowledge dates are required with no default and neither is
    ever substituted: if either endpoint is missing or incomplete the query refuses with
    ENDPOINT_MISSING or ENDPOINT_INCOMPLETE and returns zero rows. ENTRY is a zero-to-positive
    schedule-key count and EXIT is positive-to-zero; a one-to-two or two-to-one change is
    deliberately not an event.

    Grain is ``(carrier_role, exact resolved airline, directional route)``. Unresolved or
    ambiguous airline codes cannot yield an exact airline-level market and are therefore not
    reported as one.

    This question says when knowledge changed. It does not say which service operates on any
    particular date; that is Q07's operating clock.

    Refusals: ``ENDPOINT_MISSING``, ``ENDPOINT_INCOMPLETE``, and ``PARAMETER_ERROR`` with
    ``MISSING_CARRIER_ROLE``, ``INVALID_CARRIER_ROLE`` or ``INVALID_DATE``.
    """
    modules = _load_query_modules()
    uc2 = modules["uc2"]
    if carrier_role is None:
        return _refusal(
            "Q06",
            "PARAMETER_ERROR",
            "MISSING_CARRIER_ROLE",
            "carrier_role is required and has no default. Marketing and operating are "
            "separate carrier dimensions and give different answers.",
            ask_the_user=(
                "Do you mean the marketing carrier or the operating carrier? "
                "The two are separate dimensions here and I will not pick one for you."
            ),
        )
    if latest_knowledge_date is None or comparison_knowledge_date is None:
        return _refusal(
            "Q06",
            "PARAMETER_ERROR",
            "MISSING_PARAMETER",
            "Both latest_knowledge_date and comparison_knowledge_date are required.",
            ask_the_user=(
                "Which two knowledge dates should I compare? Both endpoints are required "
                "and neither is substituted."
            ),
        )
    try:
        frame = _retry_on_model_lock(
            lambda: uc2.market_latest_vs_seven_days(
                latest_knowledge_date, comparison_knowledge_date, carrier_role
            )
        )
    except _typed_errors() as error:
        return _refusal("Q06", _status_of(error), error.error_code, str(error))
    return _ok(
        "Q06",
        frame,
        {
            "clock": "knowledge",
            "latest_knowledge_date": str(latest_knowledge_date),
            "comparison_knowledge_date": str(comparison_knowledge_date),
            "carrier_role": carrier_role,
        },
    )


# ---------------------------------------------------------------------------------
# Q07 - route_capacity_two_clocks
# ---------------------------------------------------------------------------------


def route_capacity_two_clocks(
    knowledge_date: str = None,
    operating_date: str = None,
    carrier_role: str = None,
) -> Any:
    """Q07. Weekly route frequency and cabin capacity per airline and route, using BOTH schedule
    clocks at once: knowledge_date is when the schedule was known (half-open validity) and
    operating_date is when it operates (inclusive bounds plus weekday). Both clocks are
    required, they are not interchangeable, and neither has a default. carrier_role is also
    required and must be 'marketing' or 'operating'. If the user has named only one date, or
    has not said which carrier role they mean, ask which is meant and do not choose. Under the
    operating role only a physical base representative is counted, so codeshare-only service
    appears as UNRESOLVED_PHYSICAL_SERVICE with null measures and the operating total can
    visibly undercount marketing; that is contracted behaviour, not a defect, and should be
    stated rather than explained away.

    ``result_status`` is COUNTED for a resolved row and UNRESOLVED_PHYSICAL_SERVICE for a
    codeshare-only service with no stable service-group id. Unresolved rows are emitted with
    null measures rather than dropped or double counted.

    Changing only the knowledge date, only the operating date, or only the carrier role each
    changes the answer independently, which is the whole point of keeping the two clocks and
    the two carrier dimensions separate.

    Refusals: ``PARAMETER_ERROR`` with ``MISSING_KNOWLEDGE_DATE``, ``MISSING_OPERATING_DATE``,
    ``MISSING_CARRIER_ROLE``, ``INVALID_CARRIER_ROLE`` or ``INVALID_DATE``. Zero rows with
    status OK is a real answer and means nothing was visible at that pair of clocks.
    """
    modules = _load_query_modules()
    uc2 = modules["uc2"]
    if knowledge_date is None or operating_date is None:
        missing = "knowledge_date" if knowledge_date is None else "operating_date"
        return _refusal(
            "Q07",
            "PARAMETER_ERROR",
            "MISSING_KNOWLEDGE_DATE" if knowledge_date is None else "MISSING_OPERATING_DATE",
            f"{missing} is required. Q07 uses both schedule clocks and one cannot stand in "
            "for the other.",
            ask_the_user=(
                "This question needs both clocks. As of which knowledge date should I read "
                "the schedule, and for which operating date should I count it?"
            ),
        )
    if carrier_role is None:
        return _refusal(
            "Q07",
            "PARAMETER_ERROR",
            "MISSING_CARRIER_ROLE",
            "carrier_role is required and has no default. Marketing and operating are "
            "separate carrier dimensions and give different answers.",
            ask_the_user=(
                "Do you mean the marketing carrier or the operating carrier? "
                "The two are separate dimensions here and I will not pick one for you."
            ),
        )
    try:
        frame = _retry_on_model_lock(
            lambda: uc2.route_capacity_two_clocks(
                knowledge_date, operating_date, carrier_role
            )
        )
    except _typed_errors() as error:
        return _refusal("Q07", _status_of(error), error.error_code, str(error))
    return _ok(
        "Q07",
        frame,
        {
            "knowledge_date": str(knowledge_date),
            "operating_date": str(operating_date),
            "carrier_role": carrier_role,
            "clocks_applied": "knowledge (half-open) and operating (inclusive plus weekday)",
        },
        notes=(
            "Under carrier_role=operating only a physical base representative is counted, so "
            "the operating total can legitimately undercount marketing.",
        ),
    )


# ---------------------------------------------------------------------------------
# Q08 - actual_rotation_enriched
# ---------------------------------------------------------------------------------


def actual_rotation_enriched(
    aircraft_id: int = None, flight_departure_date: str = None
) -> Any:
    """Q08. The validated ordered chain of actual legs one aircraft flew on one source-local
    departure date, each leg carrying its actual origin, destination and UTC times, and
    enriched with the aircraft type and engine type that were independently date-visible for
    that leg. Both aircraft_id and flight_departure_date are required with no default. Actual
    endpoints and times never borrow planned values, and actual airports are internal SYN-AP
    identifiers rather than public IATA labels. Legs that fail validation are returned as
    typed ANOMALY rows beside the accepted LEG rows and are never silently dropped. If the
    aircraft flew nothing on that date the answer is NOT_FOUND / NO_ACTUAL_FLIGHTS with zero
    rows, which is a refusal to report a rotation, not an empty rotation.

    ``row_kind`` is LEG or ANOMALY. ``link_outcome`` records why a link was accepted or why a
    chain terminated. A cycle is emitted as one CYCLE anomaly row per component at its minimum
    flight id, so the same component cannot produce duplicate anomalies.

    ``flight_departure_date`` is the source-local departure date (AF-06), which is not the same
    as the UTC departure date: a leg departing late local time can carry a UTC date one day
    later, and both appear in the output.

    This is a bounded rotation reconstruction over the source self-reference. It is not
    arbitrary network path analytics and must not be described as such.

    Refusals: ``PARAMETER_ERROR`` with ``MISSING_AIRCRAFT_ID``, ``INVALID_AIRCRAFT_ID``,
    ``MISSING_FLIGHT_DEPARTURE_DATE`` or ``INVALID_DATE``; ``NOT_FOUND`` with
    ``NO_ACTUAL_FLIGHTS``.
    """
    modules = _load_query_modules()
    rotation = modules["rotation"]
    if aircraft_id is None or flight_departure_date is None:
        return _refusal(
            "Q08",
            "PARAMETER_ERROR",
            "MISSING_PARAMETER",
            "actual_rotation_enriched requires aircraft_id and flight_departure_date.",
            ask_the_user="Which aircraft id, and which source-local departure date?",
        )
    outcome = _retry_on_model_lock(
        lambda: rotation.invoke(aircraft_id, flight_departure_date)
    )
    applied = {
        "aircraft_id": aircraft_id,
        "flight_departure_date": str(flight_departure_date),
        "departure_date_basis": "source-local (AF-06), not the UTC departure date",
    }
    if outcome.invocation_status != "OK":
        return _refusal(
            "Q08",
            outcome.invocation_status,
            outcome.error_code or "ERROR",
            f"Q08 returned {outcome.invocation_status} / {outcome.error_code} for "
            f"aircraft {aircraft_id} on {flight_departure_date}.",
        )
    return _ok(
        "Q08",
        outcome.rows,
        applied,
        notes=(
            "row_kind LEG rows are the accepted chain; row_kind ANOMALY rows are legs that "
            "failed validation and are reported rather than dropped.",
        ),
    )


# ---------------------------------------------------------------------------------
# Scope statement
# ---------------------------------------------------------------------------------

_SUPPORTED = (
    ("Q01", "aircraft_as_of", "aircraft_id, as_of_date"),
    ("Q02", "status_reversion_spells", "aircraft_id"),
    ("Q02F", "fleet_storage_spell_distribution", "aircraft_scope (FLEET only)"),
    (
        "Q03",
        "month_end_fleet_composition / month_end_fleet_composition_summary",
        "start_month_end, end_month_end, status ('In Service' only)",
    ),
    ("Q04", "type_engine_histories", "aircraft_id"),
    (
        "Q05",
        "schedule_four_week_changes / schedule_change_class_summary",
        "start_knowledge_date, end_knowledge_date, cadence_days",
    ),
    (
        "Q06",
        "market_latest_vs_seven_days",
        "latest_knowledge_date, comparison_knowledge_date, carrier_role",
    ),
    (
        "Q07",
        "route_capacity_two_clocks",
        "knowledge_date, operating_date, carrier_role",
    ),
    ("Q08", "actual_rotation_enriched", "aircraft_id, flight_departure_date"),
)

_UNSUPPORTED = (
    {
        "request": "The exact mixed-engine set fitted to an aircraft, per engine position.",
        "why": (
            "The supplied source schema carries one reported engine definition, an engine "
            "count and a mixed_engine_set_complete flag. There is no per-position fitment "
            "anywhere in it."
        ),
        "response": (
            "Decline. Report engine_type, engine_count and mixed_engine_set_complete from Q01 "
            "or Q04 and say the exact set is unavailable. Never construct one."
        ),
    },
    {
        "request": "Optimization: what should be scheduled, assigned, retired or re-routed.",
        "why": (
            "This demo has no prescriptive reasoner and no decision problem was defined. "
            "The eight questions ask what is true of known facts."
        ),
        "response": "Decline and say no optimization capability is deployed here.",
    },
    {
        "request": "Prediction or forecasting of any future value.",
        "why": "No predictive model is deployed and no prediction target was defined.",
        "response": "Decline and say no predictive capability is deployed here.",
    },
    {
        "request": (
            "Performance, cost, scalability or security comparisons against another database."
        ),
        "why": (
            "Every figure here comes from deterministic synthetic fixtures on one "
            "HIGHMEM_X64_S engine. Nothing measured here supports a production-scale, "
            "performance, cost or security claim."
        ),
        "response": "Decline and say the fixtures do not support that claim.",
    },
    {
        "request": "Any question about data outside the eight catalog entries above.",
        "why": (
            "This is a curated catalog. There is no ad-hoc query path and no arbitrary "
            "analytical surface."
        ),
        "response": (
            "Say plainly that the question does not match a curated query, name what is "
            "missing, and stop. Do not substitute a nearby answer."
        ),
    },
)


def demo_scope_and_limits() -> Any:
    """Scope statement. The exact list of questions this curated catalog can answer, the
    parameters each one requires, and the requests that must be declined rather than answered:
    the exact mixed-engine set (unsupported by the source schema and never to be fabricated),
    optimization, prediction, and performance or cost comparisons. Call this before declining
    anything, and before answering a question you are not certain maps to a catalog entry, so
    the refusal is grounded in the deployed contract rather than improvised. No parameter in
    any catalog entry has a default: a missing clock, date, carrier role or identifier is a
    question to put back to the user, never a value to choose.

    The two schedule clocks and the two carrier dimensions are the two places where a wrong
    silent choice is most likely, so they are restated here.
    """
    return {
        "invocation_status": "OK",
        "question": "SCOPE",
        "supported_questions": [
            {"question_id": qid, "catalog_entry": entry, "required_parameters": params}
            for qid, entry, params in _SUPPORTED
        ],
        "two_schedule_clocks": (
            "knowledge_date is when the schedule was known and uses half-open validity. "
            "operating_date is when the schedule operates and uses inclusive bounds plus a "
            "weekday test. Q07 requires both. Q05 and Q06 use the knowledge clock only. "
            "Never substitute one for the other and never default either."
        ),
        "two_carrier_dimensions": (
            "marketing and operating are separate carrier roles that give different answers. "
            "carrier_role is required in Q06 and Q07. If the user has not said which they "
            "mean, ask."
        ),
        "exact_versus_candidate": (
            "Q05 reports exact schedule changes and key-shifting amendment candidates as "
            "separate labelled classes. A candidate is never asserted as an exact match."
        ),
        "empty_versus_refusal": (
            "invocation_status OK with zero rows is a real answer. A refusal carries a "
            "different invocation_status and an error_code, and must not be narrated as an "
            "empty result."
        ),
        "unsupported_requests": list(_UNSUPPORTED),
    }


# ---------------------------------------------------------------------------------
# The catalog, in the order the demo tells it
# ---------------------------------------------------------------------------------

CATALOG: tuple[Callable[..., Any], ...] = (
    aircraft_as_of,
    status_reversion_spells,
    fleet_storage_spell_distribution,
    month_end_fleet_composition,
    month_end_fleet_composition_summary,
    type_engine_histories,
    schedule_four_week_changes,
    schedule_change_class_summary,
    market_latest_vs_seven_days,
    route_capacity_two_clocks,
    actual_rotation_enriched,
    demo_scope_and_limits,
)

MODEL_DESCRIPTION = (
    "Temporal aviation fleet, schedule and flight-operations intelligence for the Cirium "
    "parity demo, powered by RelationalAI over Snowflake-resident data in "
    "PK_AVIATION_TEMPORAL. The ontology covers aircraft identity and four independently "
    "clocked aircraft dimensions (state, type, engine, status), the schedule surface "
    "(schedules, route states, airlines by carrier role, cabin capacity, weekly publish "
    "snapshots) and actual flight operations (actual legs, rotations, passenger flights and "
    "their optional fulfilment). Access is through a fixed curated catalog of pre-defined "
    "queries, one per golden question, listed in the catalog section below. There is no "
    "ad-hoc query surface.\n\n"
    "Five rules bind every answer.\n"
    "1. TWO SCHEDULE CLOCKS. knowledge_date is when a schedule was known (half-open "
    "validity); operating_date is when it operates (inclusive bounds plus weekday). Q07 "
    "requires both; Q05 and Q06 use the knowledge clock only. Never substitute one for the "
    "other and never default either.\n"
    "2. TWO CARRIER DIMENSIONS. marketing and operating are separate carrier roles that give "
    "different answers; carrier_role is required in Q06 and Q07. Under the operating role "
    "only a physical base representative is counted, so the operating figure can legitimately "
    "undercount marketing.\n"
    "3. EXACT VERSUS CANDIDATE. Q05 reports exact schedule changes and key-shifting amendment "
    "candidates as separate labelled classes. A candidate is never asserted as exact and the "
    "two counts are never added together.\n"
    "4. THE EXACT MIXED-ENGINE SET IS UNSUPPORTED. The source schema carries one reported "
    "engine definition, a count and a completeness flag, and no per-position fitment. If a "
    "user asks which engines are fitted in which position, decline and say so. Never "
    "construct one.\n"
    "5. NO DEFAULTS AND NO SUBSTITUTION. No parameter in any catalog entry has a default. A "
    "missing clock, date, carrier role or identifier is a clarifying question to put back to "
    "the user. An ineligible snapshot endpoint is refused, never replaced by a nearby date. "
    "invocation_status OK with zero rows is a real answer; a refusal carries a different "
    "invocation_status plus an error_code and must not be narrated as an empty result.\n\n"
    "There is no optimization and no prediction here, and the fixtures are deterministic "
    "synthetic data on a single small engine, so no performance, cost, scale or security "
    "comparison is supported. Call demo_scope_and_limits before declining anything."
)
