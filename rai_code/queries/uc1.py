"""uc1.py - Q01 to Q04 of the aviation temporal demo, as live PyRel queries.

Five questions over the aircraft surface, all of them answered by the *same* shared temporal
predicate layer in ``aviation_model.temporal``:

* **Q01** ``aircraft_as_of`` - reconstruct one aircraft at one instant across four
  independently clocked dimensions, each carrying its own DV-33 status.
* **Q02** ``status_reversion_spells`` - every ``In Service -> Storage -> In Service`` spell on
  the *audit* stream, including the same-day zero-day spell the daily projection loses.
* **Q02F** ``fleet_storage_spell_distribution`` - the same spell derivation with the
  per-aircraft filter removed, bucketed by duration against a joined bucket dimension (D-0026,
  manifest v1.2.0).
* **Q03** ``month_end_fleet_composition`` - in-service count per exact aircraft type at every
  month end over ten years, from **one** query joined against a materialized calendar.
* **Q04** ``type_engine_histories`` - the type stream and the engine stream side by side,
  never boundary-aligned, plus the three-valued ``is_type_change``.

Three rules this module holds to, each of which cost somebody a live failure to learn.

1. **Nothing temporal is retyped here.** Every interval conjunction comes from
   ``aviation_model.temporal`` - :func:`~aviation_model.temporal.within_existence`,
   :func:`~aviation_model.temporal.visible_on` and
   :func:`~aviation_model.temporal.dv33_branches` - and Q03's calendar join comes from the
   ``InServiceOnMonthEnd`` model rule. ``NEO4J_PARITY_MATRIX.md`` sells "one reusable semantic
   model for the eight bounded workloads instead of query-local temporal rules"; a copy of
   ``valid_from <= d < valid_to`` in this file would make that claim false and would give each
   question its own chance to put the exclusive bound on the wrong side.
2. **The filtering, joining and aggregation happen in PyRel.** pandas is used for exactly three
   things: naming and ordering the frozen output columns, normalising RAI's pandas dtypes back
   to Python scalars (RAI ``Date`` arrives as ``Timestamp``, integer aggregates as
   ``Int128Array``), and stamping the manifest ``row_id`` label. No filter, no join, no group-by
   is performed on a DataFrame.
3. **Parameters are validated before any query is sent.** ``EXPECTED_ANSWERS.yaml``'s
   ``canonicalization`` section is explicit: "validation returns error_code before query
   execution and rows remain empty". :class:`QueryParameterError` carries the frozen
   ``error_code``.

``row_id`` is in every frozen ``output_schema`` but is a *supplied manifest label*, not a
derived value - ``DEMO_QUESTIONS.md`` says so under D-0018, and the independent SQL oracles do
not emit it either. Each function therefore takes ``row_id_start`` and stamps
``<QID>-R<n:03d>`` in the frozen ``order_by`` order. ``main()`` and ``tests/test_uc1.py`` pass
the base declared by the manifest and separately assert the frozen labels are exactly that
contiguous run, so the numbering is checked rather than assumed.

Run it::

    PYTHONPATH=rai_code .venv/bin/python rai_code/queries/uc1.py

The first query in a fresh interpreter pays a roughly 130 second full-model sync; warm queries
are 3 to 9 seconds. Only ever build one ``Model`` per process - a second one makes the free
``distinct(...)`` raise ``[Ambiguous model]`` (PROBE N-02) - which is why this module imports
the package's single ``aviation_model.model`` and never constructs its own.

Do not run two query modules against this model concurrently. Building the model is a write
transaction and a concurrent reader **errors** rather than waiting, with
``prepareIndex: model is currently locked``. :func:`warm_model` retries through it; ``main()``
calls it first.
"""

from __future__ import annotations

import datetime as dt
import itertools
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

if __name__ == "__main__" and __package__ in (None, ""):  # pragma: no cover - script entry
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import aviation_model as am
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import datetime as rdt

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "EXPECTED_ANSWERS.yaml"


# ---------------------------------------------------------------------------------
# Model warm-up, and the concurrency hazard it exists for
# ---------------------------------------------------------------------------------

_LOCK_MARKERS = ("model is currently locked", "prepareindex")


def warm_model(*, attempts: int = 8, delay: float = 30.0) -> float:
    """Pay the one-off model sync up front, retrying while another process holds the lock.

    Two facts, both measured rather than assumed, and both of which look like the other one if
    you only see a stalled terminal:

    * **The sync is about 130 seconds, not ten minutes.** Measured here at 122.8s on an already
      ``READY`` engine and independently at 133.5s by the UC2 agent. PROBE U-12's 631s figure
      includes nine minutes of engine *provisioning* from ``SUSPENDED``; once the engine is up,
      the model sync alone is roughly two minutes. Warm queries are 3 to 9 seconds.
    * **Building the model is a write transaction, and a concurrent reader errors rather than
      waiting.** Importing ``aviation_model`` in a second process while a first is still
      indexing fails with ``prepareIndex: model is currently locked``. UC2 lost two runs to this
      and spent the time debugging a query that was fine. If you see that message it is another
      process, not your query.

    Returns the elapsed seconds so a caller can report cold versus warm honestly.
    """
    import time

    started = time.time()
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            am.model.select(aggs.count(am.Aircraft).alias("n")).to_df()
            return time.time() - started
        except Exception as exc:  # noqa: BLE001 - re-raised below unless it is the lock
            message = str(exc).lower()
            if not any(marker in message for marker in _LOCK_MARKERS):
                raise
            last = exc
            print(
                f"model locked by another process, retry {attempt + 1}/{attempts} "
                f"in {delay:.0f}s",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError(
        f"model still locked after {attempts} attempts over "
        f"{time.time() - started:.0f}s"
    ) from last


# ---------------------------------------------------------------------------------
# Typed parameter validation
# ---------------------------------------------------------------------------------


class QueryParameterError(ValueError):
    """A typed parameter violation, raised *before* any query reaches the engine.

    ``invocation_status`` is always ``PARAMETER_ERROR`` and ``error_code`` is the frozen token.
    ``Q01-INVALID-AIRCRAFT-ID`` is the only parameter-error result set among Q01 to Q04, and it
    freezes ``INVALID_AIRCRAFT_ID`` for ``aircraft_id = -1``: an out-of-domain identifier, so
    the check is on the domain and not on whether the row happens to exist.
    """

    invocation_status = "PARAMETER_ERROR"

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code


def _require_aircraft_id(value: Any) -> int:
    """``NUMBER(38,0)``, not null, in domain. Aircraft identifiers are positive integers."""
    if value is None or isinstance(value, bool):
        raise QueryParameterError("INVALID_AIRCRAFT_ID", f"aircraft_id must not be {value!r}")
    try:
        aircraft_id = int(value)
    except (TypeError, ValueError):
        raise QueryParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id {value!r} is not an integer"
        ) from None
    if isinstance(value, float) and aircraft_id != value:
        raise QueryParameterError("INVALID_AIRCRAFT_ID", f"aircraft_id {value!r} is not integral")
    if aircraft_id <= 0:
        raise QueryParameterError(
            "INVALID_AIRCRAFT_ID", f"aircraft_id {aircraft_id} is out of domain"
        )
    return aircraft_id


def _require_date(value: Any, name: str, error_code: str) -> dt.date:
    """``DATE``, not null, castable. A ``datetime`` is narrowed; a string must be ISO."""
    if value is None:
        raise QueryParameterError(error_code, f"{name} must not be null")
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            raise QueryParameterError(
                error_code, f"{name} {value!r} is not an ISO date"
            ) from None
    raise QueryParameterError(error_code, f"{name} {value!r} is not castable to DATE")


def _require_enum(value: Any, name: str, allowed: Sequence[str], error_code: str) -> str:
    if value is None:
        raise QueryParameterError(error_code, f"{name} must not be null")
    if value not in allowed:
        raise QueryParameterError(
            error_code, f"{name} {value!r} is not one of {list(allowed)}"
        )
    return str(value)


# ---------------------------------------------------------------------------------
# pandas-side normalisation (dtype only - never filtering, joining or aggregation)
# ---------------------------------------------------------------------------------


def _is_missing(value: Any) -> bool:
    """True for ``None`` / ``NaN`` / ``NaT`` / ``pd.NA``.

    Checked before any ``isinstance`` test because ``pd.NaT`` *is* a ``datetime`` instance, so
    an ``isinstance(value, dt.date)`` branch would happily return it.
    """
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _to_date(value: Any) -> dt.date | None:
    """RAI ``Date`` to ``datetime.date``.

    MODEL-01 finding M-02: RAI ``Date`` properties arrive as pandas ``Timestamp``, so a naive
    ``df["d"] == dt.date(...)`` matches nothing and passes vacuously. Normalising element-wise
    rather than through ``pd.to_datetime`` also survives the ``9999-01-01`` open-interval
    sentinel, which is past ``Timestamp.max`` (2262-04-11) and would overflow a vectorised cast.
    """
    if _is_missing(value):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _to_int(value: Any) -> int | None:
    """RAI ``Integer`` / ``Int128Array`` cell to ``int``. Pandas reductions on Int128 raise."""
    return None if _is_missing(value) else int(value)


def _to_bool(value: Any) -> bool | None:
    """RAI ``Bool`` to ``bool``. Absence stays ``None``; Q04's flag is three-valued."""
    return None if _is_missing(value) else bool(value)


def _to_str(value: Any) -> str | None:
    return None if _is_missing(value) else str(value)


_NORMALISERS: Mapping[str, Callable[[Any], Any]] = {
    # Q01
    "aircraft_id": _to_int,
    "as_of_date": _to_date,
    "is_complete": _to_bool,
    "aircraft_state_status": _to_str,
    "aircraft_type_status": _to_str,
    "engine_type_status": _to_str,
    "aircraft_status_status": _to_str,
    "aircraft_type_id": _to_str,
    "aircraft_type": _to_str,
    "engine_type_id": _to_str,
    "engine_type": _to_str,
    "engine_count": _to_int,
    "mixed_engine_set_complete": _to_bool,
    "lifecycle_status": _to_str,
    "registration_number": _to_str,
    "base_airport_code_iata": _to_str,
    # Q02
    "storage_event_id": _to_int,
    "storage_start_date": _to_date,
    "storage_start_sequence": _to_int,
    "return_event_id": _to_int,
    "return_date": _to_date,
    "return_sequence": _to_int,
    "storage_days": _to_int,
    "same_day": _to_bool,
    # Q02F
    "bucket_order": _to_int,
    "duration_bucket": _to_str,
    "spell_count": _to_int,
    "aircraft_count": _to_int,
    "minimum_storage_days": _to_int,
    "maximum_storage_days": _to_int,
    # Q03
    "month_end": _to_date,
    "in_service_aircraft_count": _to_int,
    # Q04
    "dimension": _to_str,
    "assignment_id": _to_str,
    "valid_from": _to_date,
    "valid_to": _to_date,
    "definition_id": _to_str,
    "definition_label": _to_str,
    "previous_definition_id": _to_str,
    "is_type_change": _to_bool,
}


def _records(df: pd.DataFrame, columns: Sequence[str]) -> list[dict[str, Any]]:
    """One normalised dict per RAI row, restricted to ``columns``.

    An empty RAI result is a **zero-column** DataFrame (PROBE D11), not a zero-row frame with
    the expected columns, so the column list is supplied by the caller and never read off the
    returned frame.
    """
    if df.shape[1] == 0 or df.shape[0] == 0:
        return []
    return [
        {name: _NORMALISERS[name](row.get(name)) for name in columns}
        for row in df.to_dict("records")
    ]


def _finalise(
    rows: Iterable[Mapping[str, Any]],
    *,
    columns: Sequence[str],
    order_by: Sequence[str],
    question_id: str,
    row_id_start: int,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
) -> pd.DataFrame:
    """The frozen columns, in the frozen order, with the manifest ``row_id`` stamped last.

    ``na_position="last"`` implements the canonicalization rule "Nulls sort last in every
    nullable order key"; ``kind="stable"`` keeps the sort deterministic when the declared keys
    do not fully order the rows. Row order out of ``to_df()`` is explicitly not guaranteed, so
    ordering here is mandatory rather than cosmetic.

    ``dtype=object`` is load-bearing, not defensive. Left to infer, pandas turns a nullable
    integer column such as Q04's ``engine_count`` (``[None, None, 2, 2]``) into ``float64`` and
    the frozen ``null`` cells silently become ``NaN`` floats, so a null and a zero-ish float
    stop being distinguishable and ``2`` is reported as ``2.0``. Keeping Python scalars means
    the frame compares against the YAML exactly as parsed.

    ``row_id_prefix`` and ``row_id_width`` exist because the manifest labels two generations of
    result set differently: the v1.1.1 sets are ``<QID>-R<nnn>`` (``Q01-R001``) while every
    v1.2.0 set is ``<RESULT_SET_ID>-R<nnnn>`` (``Q01-ENRICHED-MID-STORAGE-R0001``). ``row_id`` is
    a supplied manifest label rather than a derived value, so the caller states the convention
    and the comparison then checks it rather than assuming it.
    """
    payload_columns = [name for name in columns if name != "row_id"]
    frame = pd.DataFrame(list(rows), columns=payload_columns, dtype=object)
    if len(frame):
        frame = frame.sort_values(
            list(order_by), kind="stable", na_position="last"
        ).reset_index(drop=True)
    prefix = row_id_prefix or question_id
    frame.insert(
        0,
        "row_id",
        [f"{prefix}-R{row_id_start + i:0{row_id_width}d}" for i in range(len(frame))],
    )
    return frame[list(columns)]


# ---------------------------------------------------------------------------------
# Frozen output schemas (asserted against EXPECTED_ANSWERS.yaml in tests/test_uc1.py)
# ---------------------------------------------------------------------------------

Q01_COLUMNS = (
    "row_id",
    "aircraft_id",
    "as_of_date",
    "is_complete",
    "aircraft_state_status",
    "aircraft_type_status",
    "engine_type_status",
    "aircraft_status_status",
    "aircraft_type_id",
    "aircraft_type",
    "engine_type_id",
    "engine_type",
    "engine_count",
    "mixed_engine_set_complete",
    "lifecycle_status",
    "registration_number",
    "base_airport_code_iata",
)
Q01_ORDER_BY = ("aircraft_id", "as_of_date")

Q02_COLUMNS = (
    "row_id",
    "aircraft_id",
    "storage_event_id",
    "storage_start_date",
    "storage_start_sequence",
    "return_event_id",
    "return_date",
    "return_sequence",
    "storage_days",
    "same_day",
)
Q02_ORDER_BY = (
    "storage_start_date",
    "storage_start_sequence",
    "storage_event_id",
    "return_event_id",
)

Q02F_COLUMNS = (
    "row_id",
    "bucket_order",
    "duration_bucket",
    "spell_count",
    "aircraft_count",
    "minimum_storage_days",
    "maximum_storage_days",
)
Q02F_ORDER_BY = ("bucket_order",)
Q02F_SCOPE_ENUM = ("FLEET",)

Q03_COLUMNS = (
    "row_id",
    "month_end",
    "aircraft_type_id",
    "aircraft_type",
    "in_service_aircraft_count",
)
Q03_ORDER_BY = ("month_end", "aircraft_type_id")

Q04_COLUMNS = (
    "row_id",
    "aircraft_id",
    "dimension",
    "assignment_id",
    "valid_from",
    "valid_to",
    "definition_id",
    "definition_label",
    "engine_count",
    "mixed_engine_set_complete",
    "previous_definition_id",
    "is_type_change",
)
Q04_ORDER_BY = ("dimension", "valid_from", "assignment_id")

Q03_STATUS_ENUM = (am.STATUS_IN_SERVICE,)


# ---------------------------------------------------------------------------------
# Q01 - aircraft_as_of
# ---------------------------------------------------------------------------------

_ref_counter = itertools.count(1)


@dataclass(frozen=True, eq=False)
class _Dimension:
    """One of Q01's four independently clocked dimension streams.

    ``scope`` is what restricts the shared ``AircraftDimensionDailyAssignment`` ref to a single
    dimension and is **not optional**: the concept is one physical table with a ``dimension``
    discriminator, so an unscoped ref ranges over all four and returns a silently wrong answer
    rather than an error. Aircraft 1001 at 2022-05-15 reported both ``OK`` and
    ``UNKNOWN_STATE`` before the scope existed.

    ``exact_target`` is the optional-target property *chain itself*, never a comparison:
    ``model.not_(ref.aircraft_type == AircraftType)`` reads as "there exists some type this is
    not equal to", true for nearly everything once two types exist. ``dv33_branches`` negates
    the chain's existence instead.

    ``ok_bindings`` are the extra clauses that bind the resolved definition entity so the
    projection can read its identity and label off the definition concept rather than off the
    assignment payload. They are added to the ``OK`` branch only.
    """

    name: str
    ref: Any
    scope: tuple
    exact_target: Any
    ok_bindings: tuple
    payload: Mapping[str, Any] = field(default_factory=dict)


def _q01_dimensions(tag: str) -> tuple[_Dimension, ...]:
    """Four separately named refs. One shared ref would unify the four dimensions into one.

    ``aircraft_state`` gets no ``exact_target``: its payload is plain strings (AH-17 / AH-25)
    with no exact resolution to a definition entity, and ``MODEL_INPUT`` confirms it live -
    ``DIMENSION_QUERY_STATUS`` is ``OK`` on all 1,004 state rows and all 1,003 status rows,
    with ``UNKNOWN_STATE`` occurring only on ``aircraft_type`` and ``engine_type``. Note there
    is deliberately no resolved ``Airport`` link for AH-25: the contract never resolved one, so
    the raw IATA code is emitted as a string.
    """
    state = am.DailyAssignment.ref(f"q01_state_{tag}")
    typ = am.DailyAssignment.ref(f"q01_type_{tag}")
    eng = am.DailyAssignment.ref(f"q01_engine_{tag}")
    sta = am.DailyAssignment.ref(f"q01_status_{tag}")
    return (
        _Dimension(
            name=am.DIM_AIRCRAFT_STATE,
            ref=state,
            scope=(state.dimension == am.DIM_AIRCRAFT_STATE,),
            exact_target=None,
            ok_bindings=(),
            payload={
                "registration_number": state.aircraft_registration_number,
                "base_airport_code_iata": state.base_airport_code_iata,
            },
        ),
        _Dimension(
            name=am.DIM_AIRCRAFT_TYPE,
            ref=typ,
            scope=(typ.dimension == am.DIM_AIRCRAFT_TYPE,),
            exact_target=typ.aircraft_type,
            ok_bindings=(typ.aircraft_type == am.AircraftType,),
            payload={
                "aircraft_type_id": am.AircraftType.subseries,
                "aircraft_type": am.AircraftType.aircraft_type,
            },
        ),
        _Dimension(
            name=am.DIM_ENGINE_TYPE,
            ref=eng,
            scope=(eng.dimension == am.DIM_ENGINE_TYPE,),
            exact_target=eng.engine_type,
            ok_bindings=(eng.engine_type == am.EngineType,),
            payload={
                "engine_type_id": am.EngineType.subseries,
                "engine_type": am.EngineType.engine_type,
                # AC-08 and DV-09 belong to the assignment, not to the EngineType identity:
                # asserting one engine count per engine subseries would be wrong in the domain.
                "engine_count": eng.engine_count,
                "mixed_engine_set_complete": eng.mixed_engine_set_complete,
            },
        ),
        _Dimension(
            name=am.DIM_AIRCRAFT_STATUS,
            ref=sta,
            scope=(sta.dimension == am.DIM_AIRCRAFT_STATUS,),
            exact_target=sta.status,
            ok_bindings=(sta.status == am.AircraftStatus,),
            payload={"lifecycle_status": am.AircraftStatus.code},
        ),
    )


_Q01_STATUS_COLUMN = {
    am.DIM_AIRCRAFT_STATE: "aircraft_state_status",
    am.DIM_AIRCRAFT_TYPE: "aircraft_type_status",
    am.DIM_ENGINE_TYPE: "engine_type_status",
    am.DIM_AIRCRAFT_STATUS: "aircraft_status_status",
}

_Q01_PAYLOAD_COLUMNS = (
    "aircraft_type_id",
    "aircraft_type",
    "engine_type_id",
    "engine_type",
    "engine_count",
    "mixed_engine_set_complete",
    "lifecycle_status",
    "registration_number",
    "base_airport_code_iata",
)


def _dv33_branches(dimension: _Dimension, as_of: dt.date) -> list[tuple[str, tuple]]:
    """The four DV-33 branches for one dimension at one date, from the shared builder."""
    return am.dv33_branches(
        am.model,
        am.Aircraft,
        dimension.ref,
        as_of,
        scope=dimension.scope,
        exact_target=dimension.exact_target,
    )


def _run_branch(
    aircraft_id: int, dimension: _Dimension, token: str, conditions: tuple
) -> pd.DataFrame:
    """Evaluate one DV-33 branch. Non-empty means the branch fired.

    The ``OK`` branch also projects the payload; every other branch projects the identity only,
    because the frozen answer's payload cells are null wherever the dimension is not ``OK``.
    The nulls come from that structural absence, never from a ``| None`` fallback - ``| None``
    raises inside ``front_compiler`` before a query is even sent (PROBE U-09).
    """
    projection = [am.Aircraft.id.alias("aircraft_id")]
    extra: tuple = ()
    if token == am.DV33_OK:
        extra = dimension.ok_bindings
        projection += [expr.alias(name) for name, expr in dimension.payload.items()]
    return (
        am.model.where(am.Aircraft.id == aircraft_id, *conditions, *extra)
        .select(*projection)
        .to_df()
    )


def _fired(df: pd.DataFrame) -> bool:
    """PROBE D11: an empty RAI result has no columns at all, so check both dimensions."""
    return bool(df.shape[1]) and bool(len(df))


def _resolve_dimension(
    aircraft_id: int, dimension: _Dimension, as_of: dt.date, *, strict: bool = False
) -> tuple[str | None, dict[str, Any]]:
    """The DV-33 status and payload for one dimension.

    ``OUTSIDE_EXISTENCE`` is skipped here and evaluated once for the whole row: its condition
    set is ``not_(existence_from <= d, d < existence_to)`` and mentions no assignment at all,
    so it is dimension-independent by construction and running it four times would be four
    identical queries.

    ``strict=True`` evaluates every remaining branch and raises if more than one fires. The
    branches are mutually exclusive structurally (``<`` on one boundary, ``>=`` on the other),
    so the default short-circuits at the first hit and saves up to two queries per dimension;
    ``tests/test_uc1.py`` runs the strict form over the frozen cases to keep that honest.
    """
    fired: list[tuple[str, pd.DataFrame]] = []
    for token, conditions in _dv33_branches(dimension, as_of):
        if token == am.DV33_OUTSIDE_EXISTENCE:
            continue
        frame = _run_branch(aircraft_id, dimension, token, conditions)
        if _fired(frame):
            fired.append((token, frame))
            if not strict:
                break
    if not fired:
        return None, {}
    if len(fired) > 1:
        raise AssertionError(
            f"DV-33 branches overlapped for aircraft {aircraft_id} "
            f"dimension {dimension.name} at {as_of}: {[token for token, _ in fired]}"
        )
    token, frame = fired[0]
    if len(frame) != 1:
        raise AssertionError(
            f"dimension {dimension.name} resolved to {len(frame)} rows for aircraft "
            f"{aircraft_id} at {as_of}; the multiplicity gate guarantees zero or one"
        )
    payload = {
        name: _NORMALISERS[name](frame.iloc[0][name])
        for name in dimension.payload
        if name in frame.columns
    }
    return token, payload


def aircraft_as_of(
    aircraft_id: int,
    as_of_date: dt.date | str,
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
    strict: bool = False,
) -> pd.DataFrame:
    """Q01 - reconstruct one aircraft at one instant. Exactly one row, always.

    Four dimension streams are resolved independently against the same scalar date; no interval
    is ever intersected with another interval, which is why the misaligned type and engine
    boundaries are irrelevant here. Each dimension carries its own DV-33 status and
    ``is_complete`` is the validation overlay: true only when all four are ``OK``.

    The four absence cases are genuinely different facts and collapsing any two of them fails a
    frozen result set:

    * ``OUTSIDE_EXISTENCE`` - ``Q01-EOL-BOUNDARY``, aircraft 1002 at 2024-07-01. Its
      ``existence_to`` *is* 2024-07-01 and D-0003 makes the finite end-of-life bound exclusive,
      so all four dimensions are outside. ``<=`` instead of ``<`` returns ``OK`` here.
    * ``NO_RECORDED_STATE`` - ``Q01-BEFORE-FIRST``, aircraft 1004 at 2019-06-30. Inside
      existence (from 2019-01-01) but before its first assignment (2020-01-01).
    * ``UNKNOWN_STATE`` - ``Q01-UNKNOWN-GAP``, aircraft 1002 at 2022-05-15. A covering
      assignment exists but resolves to no definition, so type and engine are ``UNKNOWN_STATE``
      while state and status are ``OK``. This is an explicit recorded gap, never backfilled:
      AM-11 through AM-14 are ``CURRENT_ONLY`` under D-0005 and a query that coalesced the
      historical null to the master value would look more complete and be wrong.
    * an aircraft the model does not hold at all - not a frozen case. Reported as four
      ``OUTSIDE_EXISTENCE`` statuses, matching ``q01_aircraft_as_of.sql``'s
      ``existence_from IS NULL`` branch, so the RAI answer and the SQL oracle stay aligned.
    """
    aircraft_id = _require_aircraft_id(aircraft_id)
    as_of = _require_date(as_of_date, "as_of_date", "INVALID_AS_OF_DATE")

    dimensions = _q01_dimensions(f"{next(_ref_counter)}")

    # OUTSIDE_EXISTENCE once, from the shared builder, for the whole row.
    outside_conditions = next(
        conditions
        for token, conditions in _dv33_branches(dimensions[0], as_of)
        if token == am.DV33_OUTSIDE_EXISTENCE
    )
    outside = _fired(
        am.model.where(am.Aircraft.id == aircraft_id, *outside_conditions)
        .select(am.Aircraft.id.alias("aircraft_id"))
        .to_df()
    )

    statuses: dict[str, str] = {}
    payload: dict[str, Any] = {name: None for name in _Q01_PAYLOAD_COLUMNS}
    if outside:
        statuses = {dim.name: am.DV33_OUTSIDE_EXISTENCE for dim in dimensions}
    else:
        for dimension in dimensions:
            token, values = _resolve_dimension(
                aircraft_id, dimension, as_of, strict=strict
            )
            statuses[dimension.name] = token or am.DV33_OUTSIDE_EXISTENCE
            payload.update(values)

    row: dict[str, Any] = {"aircraft_id": aircraft_id, "as_of_date": as_of}
    row.update(
        {
            _Q01_STATUS_COLUMN[name]: status
            for name, status in statuses.items()
        }
    )
    row["is_complete"] = all(status == am.DV33_OK for status in statuses.values())
    row.update(payload)
    return _finalise(
        [row],
        columns=Q01_COLUMNS,
        order_by=Q01_ORDER_BY,
        question_id="Q01",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# Q02 / Q02F - the shared storage-spell derivation
# ---------------------------------------------------------------------------------


def _spell_bindings(tag_prefix: str) -> tuple[Any, Any, tuple]:
    """The ``In Service -> Storage -> In Service`` spell, bound once for Q02 and Q02F.

    Returns ``(storage_ref, return_ref, conditions)``. The caller adds its own scope - Q02 a
    single ``Aircraft.id`` equality, Q02F nothing at all - and its own projection. Factoring it
    here is not tidiness: ``data/oracles/q02f_fleet_spell_distribution.sql`` states that the
    fleet derivation is "byte-for-byte the Q02 derivation with the per-aircraft filter removed,
    so the two answers cannot disagree about what a spell is", and two copies of these clauses
    would put that guarantee at the mercy of a future edit to one of them.

    Three separately named refs over ``AircraftStatusAudit``, the **audit** stream and never the
    daily projection. The daily stream keeps only the final relevant observation per aircraft,
    dimension and date, so aircraft 1001's four same-day observations on 2020-06-01 (row
    sequences 5, 10, 20, 30 -> Maintenance, In Service, Storage, In Service) collapse to one and
    the zero-day spell at sequences 20 and 30 disappears with no error at all.

    ``event_ordinal`` is the shared dense DV-03 ordinal per (aircraft, dimension) over
    ``(AH-05, AH-03, AH-04, AH-01)``, which reduces "the previous assignment" and "the next
    qualifying assignment" from a four-column lexicographic comparison to one integer
    comparison.

    The return leg is the **minimal** later In Service, bound with the HAVING-style ``:=``
    pattern. The SQL oracle instead takes the immediate successor and requires it to be In
    Service; the two definitions differ only when a Storage is followed by some third status
    before service resumes. Measured live over the whole fleet they agree exactly - 439 spells
    either way, out of 442 Storage observations that follow an In Service - so the frozen
    answers do not discriminate between them. The minimal-successor form is kept because it is
    the one that cannot pair a Storage with a later spell's return, which is what holds Q02
    down to two rows for aircraft 1001.
    """
    tag = f"{tag_prefix}_{next(_ref_counter)}"
    storage = am.AuditAssignment.ref(f"{tag}_storage")
    prior = am.AuditAssignment.ref(f"{tag}_prior")
    ret = am.AuditAssignment.ref(f"{tag}_return")

    first_return = aggs.min(ret.event_ordinal).per(storage)

    conditions = (
        # the Storage observation
        am.AircraftStatusAudit(storage),
        storage.aircraft == am.Aircraft,
        storage.aircraft_status_code == am.STATUS_STORAGE,
        # its immediate predecessor must be In Service
        am.AircraftStatusAudit(prior),
        prior.aircraft == am.Aircraft,
        prior.aircraft_status_code == am.STATUS_IN_SERVICE,
        prior.event_ordinal == storage.event_ordinal - 1,
        # the minimal later In Service observation
        am.AircraftStatusAudit(ret),
        ret.aircraft == am.Aircraft,
        ret.aircraft_status_code == am.STATUS_IN_SERVICE,
        ret.event_ordinal > storage.event_ordinal,
        return_ordinal := first_return,
        ret.event_ordinal == return_ordinal,
    )
    return storage, ret, conditions


# ---------------------------------------------------------------------------------
# Q02 - status_reversion_spells
# ---------------------------------------------------------------------------------


def status_reversion_spells(
    aircraft_id: int,
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
) -> pd.DataFrame:
    """Q02 - every ``In Service -> Storage -> In Service`` spell, on the **audit** stream.

    Reading the daily projection here is the fatal mistake. The daily stream keeps only the
    final relevant observation per aircraft, dimension and date, so aircraft 1001's four
    same-day observations on 2020-06-01 (row sequences 5, 10, 20, 30 -> Maintenance,
    In Service, Storage, In Service) collapse to one and the zero-day spell at sequences 20 and
    30 disappears without any error. ``NEO4J_PARITY_MATRIX.md`` sells exactly that row as the
    differentiator over a coarse aircraft-plus-date state key.

    Three separately named refs over ``AircraftStatusAuditAssignment``:

    * ``storage`` - the Storage observation,
    * ``prior`` - its immediate predecessor, which must be In Service, at
      ``event_ordinal - 1``,
    * ``ret`` - the *minimal* later In Service observation, bound with the HAVING-style
      ``:=`` pattern so the aggregate can be compared inside ``where()``.

    ``event_ordinal`` is the shared dense DV-03 ordinal per (aircraft, dimension) over
    ``(AH-05, AH-03, AH-04, AH-01)``, which is what reduces "the next qualifying assignment"
    from a four-column lexicographic comparison to one integer comparison. Pairing with the
    *minimal* later In Service rather than any later one is what stops the first Storage from
    also pairing with the second spell's return.

    Nothing here de-duplicates on the watched status value. Consecutive equality is suppressed
    upstream but global equality is not, so ``In Service -> Storage -> In Service`` stays three
    assignments; a ``distinct()`` over the status would delete the second In Service and with it
    the spell. ``distinct()`` appears nowhere in this query.

    ``storage_days`` is a calendar-day difference and is 0 for the same-day spell. The audit
    stream carries no timestamps, so intraday elapsed time does not exist to be derived.
    """
    aircraft_id = _require_aircraft_id(aircraft_id)
    storage, ret, spell = _spell_bindings("q02")

    frame = (
        am.model.select(
            am.Aircraft.id.alias("aircraft_id"),
            storage.event.id.alias("storage_event_id"),
            storage.event_date.alias("storage_start_date"),
            storage.row_sequence.alias("storage_start_sequence"),
            ret.event.id.alias("return_event_id"),
            ret.event_date.alias("return_date"),
            ret.row_sequence.alias("return_sequence"),
            rdt.date.diff("day", storage.event_date, ret.event_date).alias("storage_days"),
            (storage.event_date == ret.event_date).alias("same_day"),
        )
        .where(am.Aircraft.id == aircraft_id, *spell)
        .to_df()
    )

    payload_columns = [name for name in Q02_COLUMNS if name != "row_id"]
    return _finalise(
        _records(frame, payload_columns),
        columns=Q02_COLUMNS,
        order_by=Q02_ORDER_BY,
        question_id="Q02",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# Q02F - fleet_storage_spell_distribution
# ---------------------------------------------------------------------------------

# (bucket_order, duration_bucket, minimum_days, maximum_days). The bounds are the
# specification 12.2 item 13 duration buckets, inclusive at both ends, and they tile the
# non-negative integers with no gap and no overlap. The open top bucket is closed at ten
# thousand years of storage rather than left unbounded, because a bucket dimension has to be a
# finite set of rows to be joinable and because the maximum spell in the fixture is 1,091 days.
_Q02F_BUCKETS: tuple[tuple[int, str, int, int], ...] = (
    (1, "ZERO_DAYS", 0, 0),
    (2, "DAYS_1_TO_7", 1, 7),
    (3, "DAYS_8_TO_30", 8, 30),
    (4, "DAYS_31_TO_90", 31, 90),
    (5, "DAYS_91_TO_365", 91, 365),
    (6, "DAYS_366_TO_730", 366, 730),
    (7, "DAYS_OVER_730", 731, 3_652_500),
)

_bucket_concept: Any = None


def storage_spell_bucket() -> Any:
    """The Q02F duration bucket, as a materialized joinable dimension. Built once per process.

    This deliberately mirrors Q03's ``MonthEnd``. Q03's frozen trap is "an approach that only
    works because the interval is regular"; the bucket bounds here are *deliberately* irregular
    (0, 1-7, 8-30, 31-90, 91-365, 366-730, 731+), which is precisely why they cannot be a
    computed step function and have to be data. Making them a concept turns the classification
    into a single inequality join - ``minimum_days <= storage_days <= maximum_days`` - so the
    whole distribution is one query rather than seven bucket-shaped queries, and the same query
    would answer a completely different set of buckets.

    It lives in this module rather than in ``aviation_model`` because it is question-private
    presentation: ``QUERY_ROUTING.md`` puts "the per-question output column names" and the
    result-set ordering on the catalog side of the boundary, and a storage-duration bucket
    label is the same kind of thing. Nothing temporal is defined here - the spell itself comes
    from :func:`_spell_bindings`, which is shared with Q02.

    Construction is lazy so that importing this module for Q01, Q03 or Q04 does not pay the
    re-index cost of a concept those questions never read. ``model.data`` drops any row with a
    null or an empty string anywhere in the frame (PROBE N-01), so the frame is built from the
    literal tuple above and is null-free by construction; the row count is asserted after the
    define for exactly that reason.
    """
    global _bucket_concept
    if _bucket_concept is not None:
        return _bucket_concept

    from relationalai.semantics import Integer, String

    bucket = am.model.Concept(
        "Q02FStorageSpellBucket", identify_by={"bucket_order": Integer}
    )
    bucket.duration_bucket = am.model.Property(
        f"{bucket} is labelled {String:duration_bucket}"
    )
    bucket.minimum_days = am.model.Property(f"{bucket} starts at {Integer:minimum_days}")
    bucket.maximum_days = am.model.Property(f"{bucket} ends at {Integer:maximum_days}")

    rows = am.model.data(
        pd.DataFrame(
            list(_Q02F_BUCKETS),
            columns=["bucket_order", "duration_bucket", "minimum_days", "maximum_days"],
        )
    )
    am.model.define(
        entry := bucket.new(bucket_order=rows.bucket_order),
        entry.duration_bucket(rows.duration_bucket),
        entry.minimum_days(rows.minimum_days),
        entry.maximum_days(rows.maximum_days),
    )

    _bucket_concept = bucket
    _assert_buckets_present(bucket)
    return bucket


def _assert_buckets_present(bucket: Any) -> None:
    """Fail loudly if the bucket dimension is not there, because the failure mode is silence.

    Two separate ways it can be missing, and both give an empty Q02F rather than an error:

    * ``model.data`` drops every row with a null or an empty string anywhere in the frame
      (PROBE N-01). The frame here is null-free by construction, so this is the cheap regression
      guard on that.
    * **A sibling process rebuilt the model.** This concept is added to the shared named model
      by a query module rather than by ``aviation_model``, so a concurrent process that imports
      ``aviation_model`` alone rewrites the model definition without it. Observed live: Q02F
      returned seven correct rows and then, later in the same pytest session, an empty frame,
      while a sibling query agent was running. The proper fix is for the bucket dimension to
      live in ``aviation_model``; until it does, this check turns a silently empty answer into a
      named one.
    """
    loaded = am.model.select(aggs.count(bucket).alias("n")).to_df()
    found = int(loaded.iloc[0]["n"]) if len(loaded) and loaded.shape[1] else 0
    if found != len(_Q02F_BUCKETS):
        raise AssertionError(
            f"Q02F bucket dimension holds {found} rows, expected {len(_Q02F_BUCKETS)}. "
            "Either model.data() dropped rows, or another process rebuilt the shared model "
            "without this query-module-local concept. Re-run this module alone."
        )


def fleet_storage_spell_distribution(
    aircraft_scope: str = "FLEET",
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 4,
) -> pd.DataFrame:
    """Q02F - the storage-spell duration distribution over the whole fleet. One query.

    D-0026: Q02's frozen parameter schema takes a non-nullable ``aircraft_id`` and may not be
    widened, so the fleet-wide view ships as its own question with its own parameter shape. The
    spell derivation is the identical :func:`_spell_bindings` with the per-aircraft filter
    simply not applied, so Q02 and Q02F cannot disagree about what a spell is.

    ``spell_count`` counts spells and ``aircraft_count`` counts *distinct aircraft*, and they
    differ in three of the seven buckets (38 vs 35, 89 vs 86, 163 vs 160) because one aircraft
    can contribute several spells to one bucket. That difference is the built-in check on
    Silent Corruption #4: an ``aircraft_count`` equal to ``spell_count`` in every bucket means
    the distinct wrapper was lost and the aggregate is counting spell tuples, not aircraft.

    Every bucket in the frozen answer is non-empty, so the inner join is not hiding an empty
    one. Were a bucket ever to go empty it would drop out rather than report zero, which is the
    right behaviour here for the same reason it is in Q03: the manifest freezes observed
    buckets, not a completed grid.
    """
    _require_enum(aircraft_scope, "aircraft_scope", Q02F_SCOPE_ENUM, "INVALID_AIRCRAFT_SCOPE")

    from relationalai.semantics.std import numbers

    bucket = storage_spell_bucket()
    _assert_buckets_present(bucket)
    storage, ret, spell = _spell_bindings("q02f")
    # ``date.diff`` yields the runtime's narrow INT while ``min``/``max`` declare their output
    # as the core ``Integer`` (INT128), and ``model2lqp._translate_aggregate`` asserts the two
    # are the same type. Measured live: ``min(TypeName.INT) had output type of
    # TypeName.INT128``, raised at compile time and not silently. ``numbers.integer`` widens the
    # input to match. ``count`` is exempt from that assertion, which is why ``spell_count``
    # never hit it.
    storage_days = numbers.integer(
        rdt.date.diff("day", storage.event_date, ret.event_date)
    )

    frame = (
        am.model.select(
            bucket.bucket_order.alias("bucket_order"),
            bucket.duration_bucket.alias("duration_bucket"),
            aggs.count(storage).per(bucket).alias("spell_count"),
            aggs.count(am.model.distinct(am.Aircraft)).per(bucket).alias("aircraft_count"),
            aggs.min(storage_days).per(bucket).alias("minimum_storage_days"),
            aggs.max(storage_days).per(bucket).alias("maximum_storage_days"),
        )
        .where(
            *spell,
            bucket.minimum_days <= storage_days,
            storage_days <= bucket.maximum_days,
        )
        .to_df()
    )

    payload_columns = [name for name in Q02F_COLUMNS if name != "row_id"]
    return _finalise(
        _records(frame, payload_columns),
        columns=Q02F_COLUMNS,
        order_by=Q02F_ORDER_BY,
        question_id="Q02F",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# Q03 - month_end_fleet_composition
# ---------------------------------------------------------------------------------


def month_end_fleet_composition(
    start_month_end: dt.date | str,
    end_month_end: dt.date | str,
    status: str = am.STATUS_IN_SERVICE,
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
) -> pd.DataFrame:
    """Q03 - in-service count per exact type at every month end. **One** query, not 120.

    The calendar is a joined dimension, not a parameter sweep. ``MonthEnd`` is a materialized
    concept over ``MODEL_INPUT.MONTH_END_CALENDAR``, and the join predicate is a pure
    inequality, so the identical query answers an irregular set of dates. Nothing here adds 30
    or 31 days, steps a month, or generates a series: writing the query 120 times and writing
    one that only works because the interval is regular are both explicit customer fails, and
    the second is the subtler of the two.

    The aggregation reads ``InServiceOnMonthEnd``, the shared model rule in
    ``computed_aircraft.py`` where the status clock and the type clock are two *independent*
    half-open joins against the same month end - visibly not aligned to each other - plus the
    half-open existence bound. Q01 and Q03 therefore cannot drift on the boundary semantics,
    which they would if this file restated the predicate.

    ``.per(MonthEnd, AircraftType)`` groups on the bare concepts. ``.per(...aircraft_type)``
    on the property instead would introduce a second anonymous iterator and cartesian-multiply
    the rows, and ``distinct()`` does not repair that one.

    The 120 month ends and two types give 240 possible cells but only 132 are nonzero, and the
    inner-join semantics already omit the rest. No ``| 0``, no completed grid, no filler rows.

    ``status`` is a validated single-value enum. The In Service predicate lives in the model
    rule, where it is shared, rather than being re-spelled per query; the frozen
    ``parameter_schema`` admits exactly one value, so validation is the whole of the parameter's
    job.
    """
    start = _require_date(start_month_end, "start_month_end", "INVALID_MONTH_END")
    end = _require_date(end_month_end, "end_month_end", "INVALID_MONTH_END")
    _require_enum(status, "status", Q03_STATUS_ENUM, "INVALID_STATUS")
    if start > end:
        raise QueryParameterError(
            "INVALID_MONTH_END_RANGE",
            f"start_month_end {start} is after end_month_end {end}",
        )

    frame = (
        am.model.select(
            am.MonthEnd.month_end.alias("month_end"),
            am.AircraftType.subseries.alias("aircraft_type_id"),
            am.AircraftType.aircraft_type.alias("aircraft_type"),
            aggs.count(am.Aircraft)
            .per(am.MonthEnd, am.AircraftType)
            .alias("in_service_aircraft_count"),
        )
        .where(
            am.InServiceOnMonthEnd(am.Aircraft, am.MonthEnd, am.AircraftType),
            am.MonthEnd.month_end >= start,
            am.MonthEnd.month_end <= end,
        )
        .to_df()
    )

    payload_columns = [name for name in Q03_COLUMNS if name != "row_id"]
    return _finalise(
        _records(frame, payload_columns),
        columns=Q03_COLUMNS,
        order_by=Q03_ORDER_BY,
        question_id="Q03",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# Q04 - type_engine_histories
# ---------------------------------------------------------------------------------


def type_engine_histories(
    aircraft_id: int,
    *,
    row_id_start: int = 1,
    row_id_prefix: str | None = None,
    row_id_width: int = 3,
) -> pd.DataFrame:
    """Q04 - the type stream and the engine stream side by side, never aligned.

    One concept plus a ``dimension`` discriminator, filtered - not two concepts unioned. The
    contract keys the daily assignment by ``(dimension, AH-02, AH-05, AH-01)``, so type and
    engine are two slices of one relation and ``model.union()`` would only invite divergent
    payload handling between the branches.

    The independence is the answer, and it is visible in the frozen rows: aircraft 1001's type
    stream breaks at 2019-01-01 and its engine stream at 2021-07-01, and neither boundary
    appears in the other. Any join of the two streams on overlapping validity, any merged
    timeline, any "as-of both" reconstruction returns more or fewer than four rows.

    ``definition_id`` and ``definition_label`` are one column each across both dimensions, so
    the two dimension-scoped payload columns are coalesced with the ``|`` fallback operator
    *inside* the query. The payload is already dimension-scoped in ``MODEL_INPUT`` - a type row
    carries no engine columns and vice versa - so the fallback is unambiguous.

    ``engine_count`` (AC-08) and ``mixed_engine_set_complete`` (DV-09) sit on the assignment,
    not on the ``EngineType`` identity, and type rows carry null in both. ``is_type_change`` is
    three-valued and comes from the shared derived property: ``false`` on the first type
    assignment, ``true`` on a real change, and *absent* on every engine row. Absence renders as
    null through the plain dot-chain; ``| None`` raises and ``| False`` would turn Q04's four
    frozen nulls into four wrong ``false`` cells.
    """
    aircraft_id = _require_aircraft_id(aircraft_id)
    tag = f"{next(_ref_counter)}"
    asgn = am.DailyAssignment.ref(f"q04_asgn_{tag}")

    frame = (
        am.model.select(
            am.Aircraft.id.alias("aircraft_id"),
            asgn.dimension.alias("dimension"),
            asgn.daily_assignment_id.alias("assignment_id"),
            asgn.valid_from.alias("valid_from"),
            asgn.valid_to.alias("valid_to"),
            (
                asgn.exact_aircraft_type_subseries | asgn.exact_engine_type_subseries
            ).alias("definition_id"),
            (asgn.aircraft_type_label | asgn.engine_type_label).alias("definition_label"),
            asgn.engine_count.alias("engine_count"),
            asgn.mixed_engine_set_complete.alias("mixed_engine_set_complete"),
            asgn.previous_definition_id.alias("previous_definition_id"),
            asgn.is_type_change.alias("is_type_change"),
        )
        .where(
            am.Aircraft.id == aircraft_id,
            asgn.aircraft == am.Aircraft,
            asgn.dimension.in_([am.DIM_AIRCRAFT_TYPE, am.DIM_ENGINE_TYPE]),
        )
        .to_df()
    )

    payload_columns = [name for name in Q04_COLUMNS if name != "row_id"]
    return _finalise(
        _records(frame, payload_columns),
        columns=Q04_COLUMNS,
        order_by=Q04_ORDER_BY,
        question_id="Q04",
        row_id_start=row_id_start,
        row_id_prefix=row_id_prefix,
        row_id_width=row_id_width,
    )


# ---------------------------------------------------------------------------------
# The frozen manifest, the nine invocations, and the comparison
# ---------------------------------------------------------------------------------

CATALOG: Mapping[str, dict[str, Any]] = {
    "Q01": {
        "callable": aircraft_as_of,
        "columns": Q01_COLUMNS,
        "order_by": Q01_ORDER_BY,
        "parameters": ("aircraft_id", "as_of_date"),
    },
    "Q02": {
        "callable": status_reversion_spells,
        "columns": Q02_COLUMNS,
        "order_by": Q02_ORDER_BY,
        "parameters": ("aircraft_id",),
    },
    "Q02F": {
        "callable": fleet_storage_spell_distribution,
        "columns": Q02F_COLUMNS,
        "order_by": Q02F_ORDER_BY,
        "parameters": ("aircraft_scope",),
    },
    "Q03": {
        "callable": month_end_fleet_composition,
        "columns": Q03_COLUMNS,
        "order_by": Q03_ORDER_BY,
        "parameters": ("start_month_end", "end_month_end", "status"),
    },
    "Q04": {
        "callable": type_engine_histories,
        "columns": Q04_COLUMNS,
        "order_by": Q04_ORDER_BY,
        "parameters": ("aircraft_id",),
    },
}

# Q02F is the v1.2.0 fleet-wide sibling of Q02 (D-0026). It is an aircraft-history question
# with no owner in QUERY_ROUTING.md, which was written against manifest v1.1.1 and predates it;
# UC2 owns Q05 to Q07 and ROT owns Q08, so it belongs here.
UC1_QUESTION_IDS = ("Q01", "Q02", "Q02F", "Q03", "Q04")


def load_manifest() -> dict[str, Any]:
    """``EXPECTED_ANSWERS.yaml``, parsed. FROZEN - read only, never written."""
    import yaml

    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def frozen_questions(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or load_manifest()
    return {
        question["question_id"]: question
        for question in manifest["questions"]
        if question["question_id"] in UC1_QUESTION_IDS
    }


def expected_frame(question_id: str, result_set: Mapping[str, Any]) -> pd.DataFrame:
    """The frozen rows as a DataFrame with the frozen columns and the frozen dtypes.

    Built from the manifest's own column list rather than from whatever the query returned, so
    a zero-row result still compares against the full declared schema.
    """
    columns = CATALOG[question_id]["columns"]
    rows = [
        {name: _NORMALISERS[name](row.get(name)) for name in columns if name != "row_id"}
        | {"row_id": row["row_id"]}
        for row in (result_set.get("rows") or [])
    ]
    frame = pd.DataFrame(rows, columns=list(columns), dtype=object)
    return frame[list(columns)]


def row_id_base(result_set: Mapping[str, Any], question_id: str) -> int:
    """The manifest's own ``row_id`` base for a result set, defaulting to 1 when empty."""
    return row_id_convention(result_set, question_id)[0]


def row_id_convention(
    result_set: Mapping[str, Any], question_id: str
) -> tuple[int, str, int]:
    """``(start, prefix, width)`` read off the manifest's own first ``row_id``.

    Two conventions are live at once. The v1.1.1 result sets label rows ``<QID>-R<nnn>``
    (``Q01-R001``, ``Q03-R132``) and every v1.2.0 result set labels them
    ``<RESULT_SET_ID>-R<nnnn>`` (``Q01-ENRICHED-MID-STORAGE-R0001``). ``row_id`` is a supplied
    manifest label, not a derived value - ``DEMO_QUESTIONS.md`` says so under D-0018 and the
    independent SQL oracles do not emit it either - so the convention is read from the frozen
    answer and then reproduced, and the cell-by-cell comparison is what checks it. A zero-row
    result set has no label to read and no rows to stamp.
    """
    rows = result_set.get("rows") or []
    if not rows:
        return 1, question_id, 3
    label, digits = str(rows[0]["row_id"]).rsplit("-R", 1)
    return int(digits), label, len(digits)


def compare(actual: pd.DataFrame, expected: pd.DataFrame) -> list[str]:
    """Complete cell-by-cell comparison after the declared order. Returns the diffs."""
    problems: list[str] = []
    if list(actual.columns) != list(expected.columns):
        problems.append(
            f"columns differ: got {list(actual.columns)} want {list(expected.columns)}"
        )
        return problems
    if len(actual) != len(expected):
        problems.append(f"row count differs: got {len(actual)} want {len(expected)}")
    for index in range(min(len(actual), len(expected))):
        for column in expected.columns:
            got, want = actual.iloc[index][column], expected.iloc[index][column]
            got = None if _is_missing(got) else got
            want = None if _is_missing(want) else want
            if got != want:
                problems.append(
                    f"row {index} column {column}: got {got!r} ({type(got).__name__}) "
                    f"want {want!r} ({type(want).__name__})"
                )
    return problems


def run_result_set(question_id: str, result_set: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Invoke one frozen result set and compare. Returns ``(verdict, problems)``."""
    entry = CATALOG[question_id]
    parameters = dict(result_set.get("parameters") or {})
    kwargs = {name: parameters[name] for name in entry["parameters"] if name in parameters}
    start, prefix, width = row_id_convention(result_set, question_id)
    kwargs["row_id_start"] = start
    kwargs["row_id_prefix"] = prefix
    kwargs["row_id_width"] = width
    expected_status = result_set.get("invocation_status")
    expected_code = result_set.get("error_code")

    try:
        actual = entry["callable"](**kwargs)
    except QueryParameterError as exc:
        if expected_status != "PARAMETER_ERROR":
            return "FAIL", [f"unexpected {exc.error_code} for an {expected_status} result set"]
        if exc.error_code != expected_code:
            return "FAIL", [f"error_code {exc.error_code} != frozen {expected_code}"]
        if result_set.get("rows"):
            return "FAIL", ["a PARAMETER_ERROR result set must freeze zero rows"]
        return "PASS", []

    if expected_status != "OK":
        return "FAIL", [
            f"expected {expected_status} / {expected_code} but the query returned "
            f"{len(actual)} rows"
        ]
    problems = compare(actual, expected_frame(question_id, result_set))
    cardinality = result_set.get("expected_cardinality")
    if cardinality is not None and len(actual) != cardinality:
        problems.append(f"cardinality {len(actual)} != frozen {cardinality}")
    distinct_month_ends = result_set.get("expected_distinct_month_ends")
    if distinct_month_ends is not None:
        observed = actual["month_end"].nunique()
        if observed != distinct_month_ends:
            problems.append(
                f"distinct month ends {observed} != frozen {distinct_month_ends}"
            )
    return ("PASS" if not problems else "FAIL"), problems


def main() -> int:
    """Run every frozen UC1 result set against the live engine and print a summary."""
    import time

    cold = warm_model()
    print(f"model sync {cold:.1f}s", flush=True)

    questions = frozen_questions()
    verdicts: list[tuple[str, str, int, float, list[str]]] = []
    for question_id in UC1_QUESTION_IDS:
        question = questions[question_id]
        for result_set in question["result_sets"]:
            started = time.time()
            try:
                verdict, problems = run_result_set(question_id, result_set)
            except Exception as exc:  # pragma: no cover - surfaced, never swallowed
                verdict, problems = "ERROR", [f"{type(exc).__name__}: {exc}"]
            verdicts.append(
                (
                    result_set["result_set_id"],
                    verdict,
                    int(result_set.get("expected_cardinality") or 0),
                    time.time() - started,
                    problems,
                )
            )

    width = max(len(name) for name, *_ in verdicts)
    print()
    print("QUERY-UC1 against the live aviation_temporal model")
    print("-" * (width + 34))
    for name, verdict, cardinality, elapsed, problems in verdicts:
        print(f"{name:<{width}}  {verdict:<5}  rows={cardinality:<4} {elapsed:6.1f}s")
        for problem in problems[:8]:
            print(f"{'':<{width}}         {problem}")
        if len(problems) > 8:
            print(f"{'':<{width}}         ... {len(problems) - 8} more")
    passed = sum(1 for _, verdict, *_ in verdicts if verdict == "PASS")
    print("-" * (width + 34))
    print(f"{passed}/{len(verdicts)} frozen result sets reproduced exactly")
    return 0 if passed == len(verdicts) else 1


if __name__ == "__main__":  # pragma: no cover - script entry
    raise SystemExit(main())
