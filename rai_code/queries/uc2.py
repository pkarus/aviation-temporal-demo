"""uc2.py - QUERY-UC2. Q05, Q06 and Q07 as live PyRel queries over ``aviation_temporal``.

Three schedule questions, one shared temporal predicate layer:

* **Q06** ``market_latest_vs_seven_days`` - market entries and exits between two exact
  knowledge endpoints. Knowledge clock **only**; there is no operating date and no weekday
  predicate anywhere in this question.
* **Q07** ``route_capacity_two_clocks`` - weekly frequency and cabin capacity as understood on
  a past knowledge date for one operating date. **Both** clocks, with their two different
  interval conventions.
* **Q05** ``schedule_four_week_changes`` - additions, removals, key-preserving modifications
  and conservative amendment evidence across consecutive eligible publish snapshots.

Build order was Q06, then Q07, then Q05, per ``build/design/QUERY_ROUTING.md``. That inverts
the numeric order deliberately: Q06 is the cheapest possible proof that snapshot eligibility,
route-state knowledge validity and exact carrier resolution all work, Q07 adds the second clock
and the capacity derivations to a surface Q06 has already proven, and Q05's amendment
classifier is the last thing to debug rather than the first.

Non-negotiables encoded here, each of which cost a real failure somewhere in this project:

1. **Two interval conventions, never one helper.** Knowledge validity is half-open
   (``valid_from <= d < valid_to``, ``aviation_model.known_on``); the operating window is
   inclusive at both ends (``effective_date <= d <= discontinue_date``,
   ``aviation_model.operates_on``). Both appear in the same ``where()`` in Q07. A single
   generic helper would silently make the operating upper bound exclusive, lose the last
   operating day, and break nine rows of ``TT-BOTH-CLOCKS`` while still looking plausible.
   Nothing in this module retypes either conjunction: they come from ``temporal.py``.
2. **Boolean properties are always compared.** ``where(RouteState.is_codeshare)`` matches all
   12,030 route states because a bare property reference *binds* the value instead of testing
   it (MODEL-01 finding M-01). Every boolean filter reached from here goes through a named
   model relationship (``RouteStateIsPhysicalRepresentative``,
   ``RouteStateOperatesOnWeekday``) or is written ``== True``.
3. **RAI ``Date`` values arrive as pandas ``Timestamp``.** Comparing one to
   ``datetime.date(...)`` matches nothing and passes vacuously (MODEL-01 finding M-02). Every
   cell leaving this module is normalised to a Python native by :func:`_cell`, so the frames
   compare against ``EXPECTED_ANSWERS.yaml`` by value.
4. **An empty RAI result is a zero-*column* DataFrame**, not a zero-row frame with the
   expected columns (PROBE D11). Every function assembles its own column list, so
   ``Q07-KNOWLEDGE-END-EMPTY`` returns a correctly shaped empty frame with
   ``invocation_status = OK``.
5. **Marketing and operating are separate carrier dimensions.** ``carrier_role`` is required
   with no default in both Q06 and Q07. For the operating role, Q07 counts only a D-0007
   physical base representative, so a codeshare-only service is emitted as visibly
   ``UNRESOLVED_PHYSICAL_SERVICE`` with every measure null rather than double counted or
   silently dropped. Physical capacity may therefore visibly *undercount* codeshare-only
   service; that is the contracted behaviour, not a defect.
6. **An incomplete or missing snapshot never manufactures a removal.** Eligibility is
   ``is_present AND is_complete`` and nothing else. Q05 and Q06 share the definition and
   differ only in their refusal policy: Q06 requires both *exact* endpoints to be eligible and
   refuses rather than falling back to the previous eligible date.
7. **A key-shifting amendment is never asserted as an exact modification.** ``schedule_key``
   hashes the effective and discontinue dates, so shifting either date mints a new key and
   presence comparison sees one removal plus one unrelated addition. Those two exact rows
   survive, and the relationship between them is reported separately as ``CANDIDATE_UNIQUE``
   at ``CANDIDATE`` exactness and ``MEDIUM`` confidence. Where one removal is compatible with
   two additions the answer is an ``AMBIGUOUS_CANDIDATE_GROUP`` plus its members at ``LOW``
   confidence with no pair chosen.

Where the query logic lives
---------------------------

Filtering, joining and aggregation happen in PyRel. What this module does in Python is
parameter validation, the typed error codes, the normalised union of the Q05 branches, the
frozen row ordering, and the supplied-label layer below. ``QUERY_ROUTING.md`` assigns exactly
those to the catalog layer.

Two acknowledged gaps against ``QUERY_ROUTING.md``, both consequences of file ownership rather
than of taste:

* Q05's normalised ``ScheduleChangeEvent`` view is *preferred* in the ontology. This module may
  not write the ontology package, so the five branches are unioned here, each branch emitting
  the full 16-column schema with explicit nulls. RAI 1.20.1 has no fragment union either
  (``model.union(a, b).to_df()`` raises ``[Missing arg]``, PROBE D5/D6), so even inside the
  ontology this would be a set of ``define`` rules rather than one query.
* ``event_class_rank`` is likewise preferred on the concept. It is a module constant here,
  taken from the manifest's ``enum_sort_ranks.Q05_event_class``.

Supplied manifest labels (D-0018)
---------------------------------

``row_id`` in all three questions, and Q05's ``event_id`` for its five declared classes, are
**not derivable**. D-0018 proved this twice: the Q05 mnemonics follow no generative rule
(``SYN-SK-BASE_100`` maps to ``BASE`` while ``SYN-SK-PHY_BASE_700`` maps to ``CAP-700`` under
one event class and one field name), and the declared row sequence is separately unrecoverable
because on 2026-08-31 the ``EXACT_ADDITION`` block orders ``[MKT_ENTRY_714, UNPAIR_NEW]`` while
the ``UNPAIRED_ADDITION`` block orders the identical pair inverted. The contracted identities
are SHA-256 digests (measured: ``728f067e...`` for the one amendment candidate), not mnemonics.

D-0018's QUERY-UC2 binding is therefore honoured literally: the label map is **not** in the
ontology and **not** hard-coded here. Every query function takes an optional
:class:`LabelSource`; without one, ``row_id`` and the declared ``event_id`` values render as
visible ``UNLABELLED|...`` tokens so a missing, extra or misclassified event cannot be masked.
:func:`manifest_label_source` builds a :class:`LabelSource` from ``EXPECTED_ANSWERS.yaml`` and
joins it on the *independently computed* semantic identity, which is what the conformance
harness in :func:`main` and ``tests/test_uc2.py`` uses. The three candidate/group/member
``event_id`` values are computed here from the manifest-adopted string templates
``SYN-CAND-<YYYYMMDD>-NN``, ``SYN-AMB-<YYYYMMDD>-NN`` and ``<group_id>-M<k>``, with their
ordinals ranked **in PyRel**.

Running
-------

    .venv/bin/rai reasoners resume --type Logic --name aviation_temporal_logic_s --wait
    PYTHONPATH=rai_code .venv/bin/python rai_code/queries/uc2.py

Cold start was measured at 631s, so a first run against a suspended engine looks like a hang
for ten minutes. Warm queries are 2.5-6s; the engine is shared, so queueing is not failure.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ANSWERS = REPO_ROOT / "EXPECTED_ANSWERS.yaml"

CARRIER_ROLE_MARKETING = "marketing"
CARRIER_ROLE_OPERATING = "operating"
CARRIER_ROLES = (CARRIER_ROLE_MARKETING, CARRIER_ROLE_OPERATING)

# --- frozen output schemas ---------------------------------------------------------
#
# Column lists are spelled out rather than read from EXPECTED_ANSWERS.yaml so that a
# manifest edit cannot silently reshape a query result, and so an empty result still has
# the right columns (PROBE D11: an empty RAI frame has none at all).

Q05_COLUMNS: tuple[str, ...] = (
    "row_id",
    "comparison_date",
    "previous_knowledge_date",
    "event_id",
    "event_class",
    "exactness",
    "confidence",
    "schedule_key",
    "related_schedule_key",
    "field_name",
    "old_value",
    "new_value",
    "group_id",
    "member_side",
    "member_schedule_key",
    "crosses_snapshot_gap",
)

Q06_COLUMNS: tuple[str, ...] = (
    "row_id",
    "carrier_role",
    "airline_id",
    "route_id",
    "change_kind",
    "before_schedule_count",
    "after_schedule_count",
    "comparison_knowledge_date",
    "latest_knowledge_date",
)

Q07_COLUMNS: tuple[str, ...] = (
    "row_id",
    "result_status",
    "carrier_role",
    "airline_id",
    "route_id",
    "knowledge_date",
    "operating_date",
    "active_schedule_count",
    "weekly_frequency",
    "weekly_total_seats",
    "weekly_first_seats",
    "weekly_business_seats",
    "weekly_premium_economy_seats",
    "weekly_economy_excluding_premium_seats",
    "cabin_quality",
    "unresolved_service_key",
)

# --- Q05 semantic enums -----------------------------------------------------------
#
# The frozen order is by this rank, not alphabetical: sorting on the class name would put
# AMBIGUOUS_* first and fail the declared sequence. Taken verbatim from
# EXPECTED_ANSWERS.yaml canonicalization.enum_sort_ranks.Q05_event_class.

EVENT_CLASS_RANK: Mapping[str, int] = {
    "EXACT_KEY_PRESERVING_MODIFICATION": 10,
    "EXACT_ADDITION": 20,
    "EXACT_REMOVAL": 30,
    "CANDIDATE_UNIQUE": 40,
    "AMBIGUOUS_CANDIDATE_GROUP": 50,
    "AMBIGUOUS_GROUP_MEMBER": 60,
    "UNPAIRED_ADDITION": 70,
    "UNPAIRED_REMOVAL": 80,
}

# Exactness and confidence for the three exact classes. The other five classes carry these
# as bound MODEL_INPUT columns and are read from the model, never mapped here.
EXACT_EXACTNESS = "EXACT"
EXACT_CONFIDENCE = "EXACT"
EXACT_CLASSES = (
    "EXACT_KEY_PRESERVING_MODIFICATION",
    "EXACT_ADDITION",
    "EXACT_REMOVAL",
)
DECLARED_LABEL_CLASSES = EXACT_CLASSES + ("UNPAIRED_ADDITION", "UNPAIRED_REMOVAL")
AMBIGUOUS_MEMBER_CLASS = "AMBIGUOUS_GROUP_MEMBER"
AMBIGUOUS_GROUP_CLASS = "AMBIGUOUS_CANDIDATE_GROUP"
CANDIDATE_UNIQUE_CLASS = "CANDIDATE_UNIQUE"

# DV-37 side enumeration. REMOVED sorts before ADDED in the ``-Mk`` member ordinal, which is
# the manifest-adopted rule and not alphabetical.
SIDE_REMOVED = "REMOVED"
SIDE_ADDED = "ADDED"

PRESENCE_FIELD = "__presence__"
RESULT_COUNTED = "COUNTED"
RESULT_UNRESOLVED = "UNRESOLVED_PHYSICAL_SERVICE"
CABIN_RECONCILED = "RECONCILED"
CABIN_UNRECONCILED = "UNRECONCILED"
CABIN_NOT_COUNTED = "NOT_COUNTED"

_UNLABELLED = "UNLABELLED"


# --------------------------------------------------------------------------- errors


class Uc2InvocationError(RuntimeError):
    """A refusal that carries the frozen ``invocation_status`` and ``error_code``.

    ``EXPECTED_ANSWERS.yaml`` distinguishes three kinds of zero-row answer and the catalog
    layer must be able to tell them apart: a ``PARAMETER_ERROR`` raised before any query runs,
    an endpoint refusal (``ENDPOINT_MISSING`` / ``ENDPOINT_INCOMPLETE``) where the query is
    deliberately not run, and a legitimately empty ``OK`` result. The third is a DataFrame,
    not an exception - ``Q07-KNOWLEDGE-END-EMPTY`` is zero rows with status ``OK``.
    """

    def __init__(self, invocation_status: str, error_code: str, message: str) -> None:
        super().__init__(f"{error_code}: {message}")
        self.invocation_status = invocation_status
        self.error_code = error_code


class ParameterError(Uc2InvocationError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__("PARAMETER_ERROR", error_code, message)


class EndpointError(Uc2InvocationError):
    """``invocation_status`` equals the ``error_code`` for the two endpoint refusals."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(error_code, error_code, message)


# --------------------------------------------------------------- parameter validation


def _coerce_date(value: Any, missing_code: str, name: str) -> dt.date:
    """A required ``DATE`` parameter, with the two frozen failure modes kept apart.

    ``Q06-INVALID-DATE`` passes the string ``2026-02-30``, which is uncastable rather than
    absent, and freezes ``INVALID_DATE``. A null parameter is a different fault and gets its
    own code. Both are raised before any query is sent.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParameterError(missing_code, f"{name} is required and has no default")
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ParameterError(
                "INVALID_DATE", f"{name}={value!r} is not a valid calendar date ({exc})"
            ) from exc
    raise ParameterError("INVALID_DATE", f"{name}={value!r} is not a date")


def _coerce_carrier_role(value: Any) -> str:
    """``carrier_role`` is required with no default in both Q06 and Q07.

    Marketing and operating are separate carrier dimensions and never collapse, so a null is
    a clarification state at the API boundary rather than an opportunity to pick one.
    ``Q06-MISSING-CARRIER-ROLE`` and ``Q07-MISSING-CARRIER-ROLE`` both freeze
    ``MISSING_CARRIER_ROLE``.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParameterError(
            "MISSING_CARRIER_ROLE",
            "carrier_role is required and has no default; marketing and operating are "
            "separate carrier dimensions",
        )
    role = str(value).strip()
    if role not in CARRIER_ROLES:
        raise ParameterError(
            "INVALID_CARRIER_ROLE",
            f"carrier_role={value!r} is not one of {CARRIER_ROLES}",
        )
    return role


def _coerce_cadence_days(value: Any) -> int:
    """``cadence_days`` is validated and then does not filter, exactly as the SQL oracle does.

    ``parameter_schema`` declares it non-nullable with ``minimum: 1``, and the independent
    oracle binds it in its ``params`` CTE and never references it again: the Q05 window is
    ``eligible_dates BETWEEN start AND end`` plus adjacency, which is already the cadence the
    snapshot calendar publishes. Filtering on it would silently drop the 21- and 28-day
    October comparisons from any wider window, so it stays a declared, validated,
    non-filtering parameter and this docstring is the disclosure.
    """
    if value is None:
        raise ParameterError("MISSING_CADENCE_DAYS", "cadence_days is required")
    try:
        cadence = int(value)
    except (TypeError, ValueError) as exc:
        raise ParameterError(
            "INVALID_CADENCE_DAYS", f"cadence_days={value!r} is not an integer"
        ) from exc
    if cadence < 1:
        raise ParameterError(
            "INVALID_CADENCE_DAYS", f"cadence_days={cadence} violates minimum 1"
        )
    return cadence


# ------------------------------------------------------------------- the loaded model


_MODEL_PACKAGE: Any = None


def model_package() -> Any:
    """The loaded ``aviation_model`` package, imported once per interpreter.

    ``aviation_model.model`` is a module-level singleton on purpose: the free
    ``distinct(...)`` raises ``[Ambiguous model]`` the moment a second ``Model`` exists in the
    same process (PROBE N-02), and every fresh ``Model`` pays 25-100s of indexing before its
    first query.
    """
    global _MODEL_PACKAGE
    if _MODEL_PACKAGE is None:
        rai_code = str(REPO_ROOT / "rai_code")
        if rai_code not in sys.path:
            sys.path.insert(0, rai_code)
        import aviation_model  # noqa: PLC0415 - deliberately lazy; the import loads the model

        _MODEL_PACKAGE = aviation_model
    return _MODEL_PACKAGE


def _weekday_relationship() -> Any:
    from aviation_model.computed_schedule import (  # noqa: PLC0415
        RouteStateOperatesOnWeekday,
    )

    return RouteStateOperatesOnWeekday


def _physical_representative() -> Any:
    from aviation_model.computed_schedule import (  # noqa: PLC0415
        RouteStateIsPhysicalRepresentative,
    )

    return RouteStateIsPhysicalRepresentative


# ------------------------------------------------------------------ cell normalisation


def _cell(value: Any) -> Any:
    """One RAI cell as a Python native, or ``None``.

    RAI ``Date`` properties arrive as pandas ``Timestamp`` and integer aggregates as
    ``Int128``; comparing either to a frozen ``datetime.date`` or ``int`` fails or, worse,
    passes vacuously (MODEL-01 finding M-02). Absence arrives as ``NaN`` in a ``StringDtype``
    column (PROBE D1), which is the frozen ``null``.
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, dt.datetime):
        return value.date()
    return value


def _as_date(value: Any) -> dt.date | None:
    cell = _cell(value)
    if cell is None:
        return None
    if isinstance(cell, dt.date):
        return cell
    return dt.date.fromisoformat(str(cell))


def _as_int(value: Any) -> int | None:
    cell = _cell(value)
    return None if cell is None else int(cell)


def _as_float(value: Any) -> float | None:
    cell = _cell(value)
    return None if cell is None else float(cell)


def _as_bool(value: Any) -> bool | None:
    cell = _cell(value)
    return None if cell is None else bool(cell)


def _as_str(value: Any) -> str | None:
    cell = _cell(value)
    return None if cell is None else str(cell)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Rows of a RAI frame as dicts, tolerating the zero-column empty frame (PROBE D11)."""
    if df.shape[1] == 0 or df.shape[0] == 0:
        return []
    return df.to_dict("records")


# ------------------------------------------------------------------- supplied labels


@dataclass(frozen=True)
class LabelSource:
    """The supplied manifest labels, joined on an independently computed semantic identity.

    ``row_ids`` is keyed on the question's derived identity tuple; ``event_ids`` is Q05 only
    and is keyed on ``(comparison_date, event_class, schedule_key, field_name)`` exactly as
    ``data/oracles/q05_event_labels.sql`` is, which D-0018's reviewer proved collision-free
    over the five declared classes. Every value in both maps is *supplied*, not derived; the
    fourteen other Q05 columns and every Q06/Q07 measure are computed from the model.
    """

    row_ids: Mapping[tuple, str] = field(default_factory=dict)
    event_ids: Mapping[tuple, str] = field(default_factory=dict)

    def row_id(self, identity: tuple, fallback_kind: str) -> str:
        supplied = self.row_ids.get(identity)
        if supplied is not None:
            return supplied
        return _unlabelled(fallback_kind, identity)

    def event_id(self, identity: tuple) -> str:
        supplied = self.event_ids.get(identity)
        if supplied is not None:
            return supplied
        return _unlabelled("EVENT", identity)


EMPTY_LABELS = LabelSource()


def _unlabelled(kind: str, identity: Sequence[Any]) -> str:
    """A visible fail-loud token.

    D-0018: an event the query computes that the label table does not carry must render as a
    diagnostic string, never as a plausible-looking valid label, so the label join cannot mask
    an extra, missing or misclassified event.
    """
    parts = "|".join("" if p is None else str(p) for p in identity)
    return f"{_UNLABELLED}|{kind}|{parts}"


def _q05_row_identity(row: Mapping[str, Any]) -> tuple:
    return (
        row["comparison_date"],
        row["event_class"],
        row["schedule_key"],
        row["related_schedule_key"],
        row["field_name"],
        row["group_id"],
        row["member_side"],
        row["member_schedule_key"],
    )


def _q05_label_identity(row: Mapping[str, Any]) -> tuple:
    """The ``q05_event_labels`` key: field_name is '' for the two unpaired classes."""
    return (
        row["comparison_date"],
        row["event_class"],
        row["schedule_key"],
        row["field_name"] or "",
    )


def _q06_row_identity(row: Mapping[str, Any]) -> tuple:
    return (row["carrier_role"], row["change_kind"], row["airline_id"], row["route_id"])


def _q07_row_identity(row: Mapping[str, Any]) -> tuple:
    return (row["result_status"], row["carrier_role"], row["airline_id"], row["route_id"])


_ROW_IDENTITY: Mapping[str, Callable[[Mapping[str, Any]], tuple]] = {
    "Q05": _q05_row_identity,
    "Q06": _q06_row_identity,
    "Q07": _q07_row_identity,
}


def _load_manifest() -> Mapping[str, Any]:
    import yaml  # noqa: PLC0415

    with EXPECTED_ANSWERS.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def manifest_label_source(question_id: str, manifest: Mapping[str, Any] | None = None) -> LabelSource:
    """Build a :class:`LabelSource` from the frozen manifest. Conformance harness only.

    This is the D-0018 "shared conformance harness" seam. The label *values* live in
    ``EXPECTED_ANSWERS.yaml`` and are read at comparison time; they are not embedded in the
    ontology (which would put the frozen answer inside the artifact whose independence the
    demo asserts) and they are not literals in this file. The join key is computed from the
    query's own output columns, so supplying labels cannot change any derived cell.
    """
    manifest = manifest or _load_manifest()
    identity = _ROW_IDENTITY[question_id]
    row_ids: dict[tuple, str] = {}
    event_ids: dict[tuple, str] = {}
    for question in manifest["questions"]:
        if question["question_id"] != question_id:
            continue
        for result_set in question["result_sets"]:
            for raw in result_set.get("rows") or ():
                row = _manifest_row(raw)
                row_ids[identity(row)] = row["row_id"]
                if question_id == "Q05" and row["event_class"] in DECLARED_LABEL_CLASSES:
                    event_ids[_q05_label_identity(row)] = row["event_id"]
    return LabelSource(row_ids=row_ids, event_ids=event_ids)


_DATE_COLUMNS = frozenset(
    {
        "comparison_date",
        "previous_knowledge_date",
        "comparison_knowledge_date",
        "latest_knowledge_date",
        "knowledge_date",
        "operating_date",
    }
)


def _manifest_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    """One frozen row with its declared representations applied.

    ``canonicalization.date_representation`` is "quoted ISO YYYY-MM-DD, cast to DATE before
    comparison", so the quoted scalars become ``datetime.date`` here rather than being
    string-compared against a normalised query cell.
    """
    row = dict(raw)
    for column in _DATE_COLUMNS & set(row):
        if row[column] is not None:
            row[column] = dt.date.fromisoformat(str(row[column]))
    return row


# ------------------------------------------------------------- snapshot eligibility


_SNAPSHOT_CALENDAR: dict[dt.date, tuple[bool, bool]] | None = None


def snapshot_calendar(refresh: bool = False) -> Mapping[dt.date, tuple[bool, bool]]:
    """``{expected_publish_date: (is_present, is_complete)}`` from the live model.

    The eligibility control is a separate small query that runs *before* the change or market
    query, which is what makes an endpoint refusal distinguishable from a natural empty
    result. Eligibility is ``is_present AND is_complete`` and nothing else: SC-05 observed row
    counts are validation evidence, never a completeness test - note 2026-10-26 is complete
    with an observed row count of zero, and 2026-10-19 is present with 9,917 rows and
    incomplete.
    """
    global _SNAPSHOT_CALENDAR
    if _SNAPSHOT_CALENDAR is not None and not refresh:
        return _SNAPSHOT_CALENDAR
    am = model_package()
    df = am.model.select(
        am.SnapshotDate.expected_publish_date.alias("expected_publish_date"),
        am.SnapshotDate.is_present.alias("is_present"),
        am.SnapshotDate.is_complete.alias("is_complete"),
    ).to_df()
    calendar: dict[dt.date, tuple[bool, bool]] = {}
    for row in _records(df):
        day = _as_date(row["expected_publish_date"])
        if day is None:
            continue
        calendar[day] = (bool(_as_bool(row["is_present"])), bool(_as_bool(row["is_complete"])))
    _SNAPSHOT_CALENDAR = calendar
    return calendar


def _require_eligible_endpoints(endpoints: Sequence[tuple[str, dt.date]]) -> None:
    """Refuse an ineligible endpoint. Missing takes precedence over incomplete.

    Both Q05 and Q06 require *exact* endpoints. Falling back to the previous eligible date
    would answer a different question: ``Q06-INCOMPLETE-ENDPOINT`` compares 2026-10-26 with
    2026-10-19, and the previous eligible complete snapshot before 2026-10-19 is 2026-10-05.
    Returning that comparison's rows is wrong, not lenient.
    """
    calendar = snapshot_calendar()
    absent = [
        (name, day)
        for name, day in endpoints
        if day not in calendar or not calendar[day][0]
    ]
    if absent:
        detail = ", ".join(f"{name}={day.isoformat()}" for name, day in absent)
        raise EndpointError(
            "ENDPOINT_MISSING",
            f"snapshot not present for {detail}; an absent snapshot cannot be substituted "
            "and never manufactures a change",
        )
    incomplete = [(name, day) for name, day in endpoints if not calendar[day][1]]
    if incomplete:
        detail = ", ".join(f"{name}={day.isoformat()}" for name, day in incomplete)
        raise EndpointError(
            "ENDPOINT_INCOMPLETE",
            f"snapshot present but incomplete for {detail}; an incomplete snapshot is not "
            "an eligible endpoint and is never silently replaced by an earlier one",
        )


# ------------------------------------------------------------------------- ordering


def _sort_key(row: Mapping[str, Any], keys: Sequence[str]) -> tuple:
    """Frozen ``order_by`` with nulls last in every nullable key.

    ``canonicalization.object_rules``: "Nulls sort last in every nullable order key". A plain
    tuple sort would raise on ``None`` against ``str``, so each key becomes
    ``(is_null, value)``.
    """
    out: list[tuple[int, Any]] = []
    for key in keys:
        value = row[key]
        out.append((1, "") if value is None else (0, value))
    return tuple(out)


def _frame(rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> pd.DataFrame:
    """An ``object``-dtype frame with exactly the frozen columns.

    ``object`` dtype is deliberate: it keeps ``None`` as ``None`` rather than promoting an
    integer column with a null into ``float`` and turning the frozen ``null`` into ``NaN``,
    which is what ``Q07-R004``'s seven null measures need.
    """
    materialised = [dict(row) for row in rows]
    frame = pd.DataFrame(materialised, columns=list(columns), dtype=object)
    return frame.reset_index(drop=True)


# ============================================================================== Q06


def _q06_carrier_link(state: Any, airline: Any, role: str) -> Any:
    """The role-specific exact carrier link.

    Only an ``EXACT`` cardinality-one resolution creates the link in the ontology, so an
    ambiguous or unresolved carrier code cannot produce an airline-level market at all. The
    raw code stays bound as a string on the state; it is never substituted for an identity.
    """
    am = model_package()
    if role == CARRIER_ROLE_MARKETING:
        return state.marketing_airline == airline
    return state.operating_airline == airline


def _q06_side(
    role: str,
    live_on: dt.date,
    absent_on: dt.date,
) -> list[tuple[str, str, int]]:
    """Markets live at ``live_on`` with no state at ``absent_on``, and their key counts.

    A correlated NOT EXISTS: the inner ``where`` is a subquery with its own fresh
    ``RouteState`` ref, correlated to the outer query through the shared ``Airline`` and
    ``Route`` entities. ``model.not_(A, B)`` is ``NOT (A AND B)``, so both clock clauses and
    both link clauses belong inside **one** ``not_(where(...))`` - "there is no state that is
    both this market and live at the other endpoint", not "no state for this market" AND "no
    state live at the other endpoint".

    Knowledge clock only. There is no operating date and no weekday predicate in Q06: the
    question is when knowledge changed, not which service operates on some other date, and
    adding an operating filter is a category error rather than a refinement.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    live = am.RouteState.ref("live")
    other = am.RouteState.ref("other")
    df = am.model.select(
        distinct(
            am.Airline.airline_id.alias("airline_id"),
            am.Route.route_id.alias("route_id"),
            aggs.count(am.Schedule).per(am.Airline, am.Route).alias("schedule_count"),
        )
    ).where(
        *am.known_on(live, live_on),
        _q06_carrier_link(live, am.Airline, role),
        live.route == am.Route,
        live.schedule == am.Schedule,
        am.model.not_(
            am.model.where(
                *am.known_on(other, absent_on),
                _q06_carrier_link(other, am.Airline, role),
                other.route == am.Route,
            )
        ),
    ).to_df()
    return [
        (str(row["airline_id"]), str(row["route_id"]), int(_as_int(row["schedule_count"]) or 0))
        for row in _records(df)
    ]


def market_latest_vs_seven_days(
    latest_knowledge_date: dt.date | str | None,
    comparison_knowledge_date: dt.date | str | None,
    carrier_role: str | None,
    *,
    labels: LabelSource | None = None,
) -> pd.DataFrame:
    """Q06 - market entries and exits between two exact knowledge endpoints.

    Grain is ``(carrier_role, exact resolved airline, directional route)`` and the measure is
    the count of distinct eligible schedule keys. ``ENTRY`` is zero to positive, ``EXIT`` is
    positive to zero; every other transition (1 to 2, 2 to 1) is deliberately not an event,
    which is what the stable positive market shadows in the universe exercise. If more than
    two rows come back on the canonical parameters the cause is almost certainly a clock
    predicate that is too narrow, not a missing filter.

    Both endpoints must be eligible complete snapshots and neither is ever substituted.
    """
    latest = _coerce_date(
        latest_knowledge_date, "MISSING_LATEST_KNOWLEDGE_DATE", "latest_knowledge_date"
    )
    comparison = _coerce_date(
        comparison_knowledge_date,
        "MISSING_COMPARISON_KNOWLEDGE_DATE",
        "comparison_knowledge_date",
    )
    role = _coerce_carrier_role(carrier_role)
    label_source = labels or EMPTY_LABELS

    _require_eligible_endpoints(
        (("comparison_knowledge_date", comparison), ("latest_knowledge_date", latest))
    )

    rows: list[dict[str, Any]] = []
    for airline_id, route_id, after_count in _q06_side(role, latest, comparison):
        rows.append(
            {
                "carrier_role": role,
                "airline_id": airline_id,
                "route_id": route_id,
                "change_kind": "ENTRY",
                "before_schedule_count": 0,
                "after_schedule_count": after_count,
                "comparison_knowledge_date": comparison,
                "latest_knowledge_date": latest,
            }
        )
    for airline_id, route_id, before_count in _q06_side(role, comparison, latest):
        rows.append(
            {
                "carrier_role": role,
                "airline_id": airline_id,
                "route_id": route_id,
                "change_kind": "EXIT",
                "before_schedule_count": before_count,
                "after_schedule_count": 0,
                "comparison_knowledge_date": comparison,
                "latest_knowledge_date": latest,
            }
        )

    rows.sort(key=lambda row: _sort_key(row, ("change_kind", "airline_id", "route_id")))
    for row in rows:
        row["row_id"] = label_source.row_id(_q06_row_identity(row), "Q06")
    return _frame(rows, Q06_COLUMNS)


def market_count_at(knowledge_date: dt.date, carrier_role: str) -> int:
    """Distinct ``(airline, route)`` markets live at one knowledge date.

    Exists for the entries/exits partition check: ``n_latest - entries`` and
    ``n_comparison - exits`` must both equal the intersection. If they disagree the
    correlation in :func:`_q06_side` is not binding and the ``not_()`` is testing "no such
    state anywhere" rather than "no such state for this market", which is the classic failure
    of the correlated anti-join.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    role = _coerce_carrier_role(carrier_role)
    df = am.model.select(
        aggs.count(distinct(am.Airline.airline_id, am.Route.route_id)).alias("n")
    ).where(
        *am.known_on(am.RouteState, knowledge_date),
        _q06_carrier_link(am.RouteState, am.Airline, role),
        am.RouteState.route == am.Route,
    ).to_df()
    records = _records(df)
    return 0 if not records else int(_as_int(records[0]["n"]) or 0)


# ============================================================================== Q07


def _q07_counted(role: str, knowledge_date: dt.date, operating_date: dt.date) -> list[dict[str, Any]]:
    """Weekly measures over the states that count towards capacity for this role.

    Both clocks are in the same ``where()`` with their two different conventions, and the
    weekday flag for the operating date joins as a named relationship rather than a
    seven-branch match. For the operating role the D-0007 physical base representative gate is
    added: only a state that is not a codeshare and whose marketing and operating carriers
    resolve to the same airline may contribute physical capacity. For the marketing role every
    eligible state with a resolved marketing airline counts.

    Weekly measures are per-flight seats multiplied by ``weekly_frequency``, summed over the
    active states in the group - so a route with two concurrently open states sums both.
    ``active_schedule_count`` counts distinct schedules, not lineage contributions.
    Premium economy is a subset of economy, so the exclusive bucket is the bound DV-26
    ``economy_excluding_premium`` and the four cabin buckets sum to the per-flight total.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    state = am.RouteState
    gate: tuple[Any, ...] = ()
    if role == CARRIER_ROLE_OPERATING:
        gate = (_physical_representative()(state),)

    df = am.model.select(
        distinct(
            am.Airline.airline_id.alias("airline_id"),
            am.Route.route_id.alias("route_id"),
            aggs.count(am.Schedule).per(am.Airline, am.Route).alias("active_schedule_count"),
            aggs.sum(state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_frequency"),
            aggs.sum(state.total_seats * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_total_seats"),
            aggs.sum(state.first_class_seats * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_first_seats"),
            aggs.sum(state.business_class_seats * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_business_seats"),
            aggs.sum(state.premium_economy_seats * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_premium_economy_seats"),
            aggs.sum(state.economy_excluding_premium * state.weekly_frequency)
            .per(am.Airline, am.Route)
            .alias("weekly_economy_excluding_premium_seats"),
            (
                aggs.count(state)
                .per(am.Airline, am.Route)
                .where(state.cabin_quality_status != CABIN_RECONCILED)
                | 0
            ).alias("unreconciled_states"),
        )
    ).where(
        *am.known_on(state, knowledge_date),
        *am.operates_on(state, operating_date, _weekday_relationship()),
        *gate,
        _q06_carrier_link(state, am.Airline, role),
        state.route == am.Route,
        state.schedule == am.Schedule,
    ).to_df()

    rows: list[dict[str, Any]] = []
    for row in _records(df):
        unreconciled = _as_int(row["unreconciled_states"]) or 0
        rows.append(
            {
                "result_status": RESULT_COUNTED,
                "carrier_role": role,
                "airline_id": _as_str(row["airline_id"]),
                "route_id": _as_str(row["route_id"]),
                "knowledge_date": knowledge_date,
                "operating_date": operating_date,
                "active_schedule_count": _as_int(row["active_schedule_count"]),
                "weekly_frequency": _as_int(row["weekly_frequency"]),
                "weekly_total_seats": _as_float(row["weekly_total_seats"]),
                "weekly_first_seats": _as_float(row["weekly_first_seats"]),
                "weekly_business_seats": _as_float(row["weekly_business_seats"]),
                "weekly_premium_economy_seats": _as_float(row["weekly_premium_economy_seats"]),
                "weekly_economy_excluding_premium_seats": _as_float(
                    row["weekly_economy_excluding_premium_seats"]
                ),
                "cabin_quality": CABIN_RECONCILED if unreconciled == 0 else CABIN_UNRECONCILED,
                "unresolved_service_key": None,
            }
        )
    return rows


def _q07_unresolved(
    role: str, knowledge_date: dt.date, operating_date: dt.date
) -> list[dict[str, Any]]:
    """Markets that are eligible on both clocks but have no state that counts for this role.

    ``Q07-R004`` freezes exactly this row: ``SYN-OP-X`` on ``SFO->SEA`` at
    ``UNRESOLVED_PHYSICAL_SERVICE`` with every measure null, ``cabin_quality = NOT_COUNTED``
    and ``unresolved_service_key = SYN-SK-CSH_ONLY_900``. Codeshare-only service must be
    emitted as visibly unresolved, never excluded and never guessed into a number: its absence
    would be a two-row answer where three rows are expected, and its inclusion as a number
    would double count somebody else's metal.

    For the marketing role the counting gate is vacuously true, so this branch is
    structurally empty rather than special-cased away. It still runs, because "the marketing
    role can never be unresolved" is a claim worth having a query behind.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    any_state = am.RouteState.ref("any_state")
    counting = am.RouteState.ref("counting")
    inner: list[Any] = [
        *am.known_on(counting, knowledge_date),
        *am.operates_on(counting, operating_date, _weekday_relationship()),
        _q06_carrier_link(counting, am.Airline, role),
        counting.route == am.Route,
    ]
    if role == CARRIER_ROLE_OPERATING:
        inner.append(_physical_representative()(counting))

    df = am.model.select(
        distinct(
            am.Airline.airline_id.alias("airline_id"),
            am.Route.route_id.alias("route_id"),
            aggs.min(any_state.schedule_key)
            .per(am.Airline, am.Route)
            .alias("unresolved_service_key"),
        )
    ).where(
        *am.known_on(any_state, knowledge_date),
        *am.operates_on(any_state, operating_date, _weekday_relationship()),
        _q06_carrier_link(any_state, am.Airline, role),
        any_state.route == am.Route,
        am.model.not_(am.model.where(*inner)),
    ).to_df()

    return [
        {
            "result_status": RESULT_UNRESOLVED,
            "carrier_role": role,
            "airline_id": _as_str(row["airline_id"]),
            "route_id": _as_str(row["route_id"]),
            "knowledge_date": knowledge_date,
            "operating_date": operating_date,
            "active_schedule_count": None,
            "weekly_frequency": None,
            "weekly_total_seats": None,
            "weekly_first_seats": None,
            "weekly_business_seats": None,
            "weekly_premium_economy_seats": None,
            "weekly_economy_excluding_premium_seats": None,
            "cabin_quality": CABIN_NOT_COUNTED,
            "unresolved_service_key": _as_str(row["unresolved_service_key"]),
        }
        for row in _records(df)
    ]


def route_capacity_two_clocks(
    knowledge_date: dt.date | str | None,
    operating_date: dt.date | str | None,
    carrier_role: str | None,
    *,
    labels: LabelSource | None = None,
) -> pd.DataFrame:
    """Q07 - weekly route frequency and cabin capacity under both clocks.

    Knowledge validity is half-open and the operating window is inclusive at both ends. Both
    matter and dropping either fails quietly: filtering on knowledge alone returns states that
    are known but not operating on the operating date, and filtering on operating alone
    returns states as understood today rather than as understood on the knowledge date. Both
    give a plausible, well-formed, wrong answer, which is what the nine-row ``TT-BOTH-CLOCKS``
    truth table exists to catch - and note that ``knowledge_position = AT_END`` is ineligible
    in all three of its rows because the knowledge bound is exclusive at the top.

    One route may carry many concurrently open states, because schedule versioning partitions
    by schedule identity and never by route. ``SYN-OP-A`` on ``SFO->LAX`` has
    ``active_schedule_count = 2``; any "latest state per route" or unique-state assumption
    collapses that row, and the parity matrix prohibits a one-open-per-route constraint.

    An empty answer is an answer: ``Q07-KNOWLEDGE-END-EMPTY`` is zero rows with
    ``invocation_status = OK``, which is a different outcome from the three parameter errors.
    """
    knowledge = _coerce_date(knowledge_date, "MISSING_KNOWLEDGE_DATE", "knowledge_date")
    operating = _coerce_date(operating_date, "MISSING_OPERATING_DATE", "operating_date")
    role = _coerce_carrier_role(carrier_role)
    label_source = labels or EMPTY_LABELS

    rows = _q07_counted(role, knowledge, operating) + _q07_unresolved(role, knowledge, operating)
    rows.sort(key=lambda row: _sort_key(row, ("result_status", "airline_id", "route_id")))
    for row in rows:
        row["row_id"] = label_source.row_id(_q07_row_identity(row), "Q07")
    return _frame(rows, Q07_COLUMNS)


def both_clocks_truth_table(
    schedule_key: str = "SYN-SK-CLOCK_BOUNDARY_001",
) -> pd.DataFrame:
    """``TT-BOTH-CLOCKS`` evaluated by the same two predicates Q07 uses.

    Nine ``(knowledge_date, operating_date)`` combinations against one fixture state whose
    knowledge interval is ``[2026-08-24, 2026-08-31)`` and whose operating window is
    ``[2026-09-01, 2026-09-07]`` with all seven weekday flags true. Exactly two combinations
    are eligible. This is the test that catches the two errors the frozen table was written
    for: dropping a clock, and mixing the two interval conventions. Applying half-open
    semantics to the operating upper bound would make ``TT23-R06`` ineligible; applying
    inclusive semantics to the knowledge upper bound would make ``TT23-R07`` through
    ``TT23-R09`` eligible.
    """
    am = model_package()
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415

    positions = [
        ("TT23-R01", "BEFORE", dt.date(2026, 8, 23), "BEFORE", dt.date(2026, 8, 31)),
        ("TT23-R02", "BEFORE", dt.date(2026, 8, 23), "INSIDE", dt.date(2026, 9, 1)),
        ("TT23-R03", "BEFORE", dt.date(2026, 8, 23), "AT_END", dt.date(2026, 9, 7)),
        ("TT23-R04", "INSIDE", dt.date(2026, 8, 24), "BEFORE", dt.date(2026, 8, 31)),
        ("TT23-R05", "INSIDE", dt.date(2026, 8, 24), "INSIDE", dt.date(2026, 9, 1)),
        ("TT23-R06", "INSIDE", dt.date(2026, 8, 24), "AT_END", dt.date(2026, 9, 7)),
        ("TT23-R07", "AT_END", dt.date(2026, 8, 31), "BEFORE", dt.date(2026, 8, 31)),
        ("TT23-R08", "AT_END", dt.date(2026, 8, 31), "INSIDE", dt.date(2026, 9, 1)),
        ("TT23-R09", "AT_END", dt.date(2026, 8, 31), "AT_END", dt.date(2026, 9, 7)),
    ]
    rows: list[dict[str, Any]] = []
    for row_id, k_pos, k_date, o_pos, o_date in positions:
        df = am.model.select(aggs.count(am.RouteState).alias("n")).where(
            am.RouteState.schedule_key == schedule_key,
            *am.known_on(am.RouteState, k_date),
            *am.operates_on(am.RouteState, o_date, _weekday_relationship()),
        ).to_df()
        records = _records(df)
        matched = 0 if not records else (_as_int(records[0]["n"]) or 0)
        rows.append(
            {
                "row_id": row_id,
                "knowledge_position": k_pos,
                "knowledge_date": k_date,
                "operating_position": o_pos,
                "operating_date": o_date,
                "eligible": matched > 0,
            }
        )
    return _frame(
        rows,
        (
            "row_id",
            "knowledge_position",
            "knowledge_date",
            "operating_position",
            "operating_date",
            "eligible",
        ),
    )


# ============================================================================== Q05


def _q05_window(start: dt.date, end: dt.date) -> tuple[Any, ...]:
    """The adjacent-eligible comparisons that lie inside ``[start, end]``.

    ``ScheduleComparison`` is the contracted DV-34 adjacency over the whole eligible snapshot
    sequence, so each comparison already pairs a date with the *previous eligible* date rather
    than the previous calendar date. Restricting a contiguous window to
    ``previous >= start AND comparison <= end`` therefore yields exactly the window-local
    adjacent pairs - for the canonical window, the four pairs
    ``q05_window_assertions.adjacent_pairs`` names and no others.
    """
    am = model_package()
    return (
        am.ScheduleComparison.previous_knowledge_date >= start,
        am.ScheduleComparison.comparison_date <= end,
    )


def _q05_exact(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """The exact layer: key-preserving modifications and presence additions/removals.

    These stand on their own and are never consumed, replaced or suppressed by the
    conservative amendment evidence below. ``SYN-SK-SHIFT_OLD`` and ``SYN-SK-SHIFT_NEW``
    appear here as an exact removal and an exact addition *and* separately as a candidate
    pair; ``SYN-SK-MKT_ENTRY_714`` and ``SYN-SK-MKT_EXIT_715`` exist for Q06 and still appear
    here, four rows in total, because D-0010/D-0011 forbid a question-private fixture filter.
    ``SYN-SK-REAPPEAR_400`` is an exact removal on 2026-08-10 followed by an exact addition on
    2026-08-17, not a no-op and not a modification.

    ``old_value`` and ``new_value`` are legitimately null on the two ``arrival_station_code_iata``
    transitions (null to ``PHX`` and back), and a repeated unchanged eligible observation
    contributes lineage without minting a change event.
    """
    am = model_package()
    change = am.ScheduleExactChange
    comparison = am.ScheduleComparison
    df = am.model.select(
        comparison.comparison_date.alias("comparison_date"),
        comparison.previous_knowledge_date.alias("previous_knowledge_date"),
        comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
        change.change_kind.alias("event_class"),
        change.schedule_key.alias("schedule_key"),
        change.field_name.alias("field_name"),
        change.old_value.alias("old_value"),
        change.new_value.alias("new_value"),
    ).where(change.comparison == comparison, *_q05_window(start, end)).to_df()

    return [
        {
            "comparison_date": _as_date(row["comparison_date"]),
            "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
            "event_class": _as_str(row["event_class"]),
            "exactness": EXACT_EXACTNESS,
            "confidence": EXACT_CONFIDENCE,
            "schedule_key": _as_str(row["schedule_key"]),
            "related_schedule_key": None,
            "field_name": _as_str(row["field_name"]),
            "old_value": _as_str(row["old_value"]),
            "new_value": _as_str(row["new_value"]),
            "group_id": None,
            "member_side": None,
            "member_schedule_key": None,
            "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
            "_ordinal": None,
        }
        for row in _records(df)
    ]


def _q05_candidates(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """``CANDIDATE_UNIQUE``: one removal and one addition compatible on the typed signature.

    The signature is ``(marketing carrier, flight number, origin, destination)`` with
    **overlapping** inclusive operating ranges and every component plus both bounds non-null.
    The pair is reported at ``CANDIDATE`` exactness and ``MEDIUM`` confidence and is never
    promoted to a modification: ``NEO4J_PARITY_MATRIX.md`` lists "a candidate key shift is an
    exact schedule amendment" as a prohibited statement. Both ``schedule_key`` (the removed
    side) and ``related_schedule_key`` (the added side) are populated so the evidence is
    legible, and both exact presence rows survive alongside it.

    The ``NN`` ordinal is ranked in PyRel over ``candidate_signature`` within the comparison,
    per the manifest-adopted ``SYN-CAND-<YYYYMMDD>-NN`` template.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415
    from relationalai.semantics.std.aggregates import asc  # noqa: PLC0415

    candidate = am.ScheduleAmendmentCandidate
    comparison = am.ScheduleComparison
    df = am.model.select(
        distinct(
            comparison.comparison_date.alias("comparison_date"),
            comparison.previous_knowledge_date.alias("previous_knowledge_date"),
            comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
            candidate.amendment_candidate_class.alias("event_class"),
            candidate.exactness.alias("exactness"),
            candidate.amendment_confidence.alias("confidence"),
            candidate.removed_schedule_key.alias("schedule_key"),
            candidate.added_schedule_key.alias("related_schedule_key"),
            aggs.rank(asc(candidate.candidate_signature)).per(comparison).alias("ordinal"),
        )
    ).where(
        comparison.comparison_id == candidate.comparison_id, *_q05_window(start, end)
    ).to_df()

    return [
        {
            "comparison_date": _as_date(row["comparison_date"]),
            "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
            "event_class": _as_str(row["event_class"]),
            "exactness": _as_str(row["exactness"]),
            "confidence": _as_str(row["confidence"]),
            "schedule_key": _as_str(row["schedule_key"]),
            "related_schedule_key": _as_str(row["related_schedule_key"]),
            "field_name": None,
            "old_value": None,
            "new_value": None,
            "group_id": None,
            "member_side": None,
            "member_schedule_key": None,
            "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
            "_ordinal": _as_int(row["ordinal"]),
        }
        for row in _records(df)
    ]


def _q05_groups(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """``AMBIGUOUS_CANDIDATE_GROUP``: one removal compatible with more than one addition.

    ``schedule_key`` and ``related_schedule_key`` are both null and no pair is chosen. Picking
    a winner by any tie-break is wrong, which is the whole point of the class existing.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415
    from relationalai.semantics.std.aggregates import asc  # noqa: PLC0415

    group = am.ScheduleAmendmentGroup
    comparison = am.ScheduleComparison
    df = am.model.select(
        distinct(
            comparison.comparison_date.alias("comparison_date"),
            comparison.previous_knowledge_date.alias("previous_knowledge_date"),
            comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
            group.amendment_candidate_class.alias("event_class"),
            group.exactness.alias("exactness"),
            group.amendment_confidence.alias("confidence"),
            group.group_id.alias("group_hash"),
            aggs.rank(asc(group.candidate_signature)).per(comparison).alias("ordinal"),
        )
    ).where(comparison.comparison_id == group.comparison_id, *_q05_window(start, end)).to_df()

    return [
        {
            "comparison_date": _as_date(row["comparison_date"]),
            "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
            "event_class": _as_str(row["event_class"]),
            "exactness": _as_str(row["exactness"]),
            "confidence": _as_str(row["confidence"]),
            "schedule_key": None,
            "related_schedule_key": None,
            "field_name": None,
            "old_value": None,
            "new_value": None,
            "group_id": None,
            "member_side": None,
            "member_schedule_key": None,
            "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
            "_group_hash": _as_str(row["group_hash"]),
            "_ordinal": _as_int(row["ordinal"]),
        }
        for row in _records(df)
    ]


def _q05_ambiguous_members(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """``AMBIGUOUS_GROUP_MEMBER``: every schedule key the ambiguous group touches.

    ``schedule_key`` and ``related_schedule_key`` stay null; the key is carried in
    ``member_schedule_key`` with its ``member_side``, so a reader can see the whole
    compatibility component without any pair being asserted.

    The ``-Mk`` ordinal is the manifest-adopted rule ``REMOVED`` before ``ADDED``, then
    schedule key ascending (the natural alternative, ``(schedule_key, side)``, produces a
    different and failing answer). It is composed from two single-ordering aggregates rather
    than one two-key rank, because ``rank(desc(side), asc(key))`` raises
    ``Mixed orderings in rank/cumsum are not supported yet`` in 1.20.1 - measured, not
    guessed. So the rank runs *within* a side, the removed side's cardinality is counted per
    group, and the added side is offset by it. Both halves are computed in PyRel; only the
    integer addition and the string template are Python, which is where the D-0018
    presentation layer belongs.
    """
    am = model_package()
    from relationalai.semantics import distinct  # noqa: PLC0415
    from relationalai.semantics.std import aggregates as aggs  # noqa: PLC0415
    from relationalai.semantics.std.aggregates import asc  # noqa: PLC0415

    member = am.ScheduleAmendmentGroupMember
    group = am.ScheduleAmendmentGroup
    comparison = am.ScheduleComparison
    df = am.model.select(
        distinct(
            comparison.comparison_date.alias("comparison_date"),
            comparison.previous_knowledge_date.alias("previous_knowledge_date"),
            comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
            member.member_class.alias("event_class"),
            member.exactness.alias("exactness"),
            member.amendment_confidence.alias("confidence"),
            group.group_id.alias("group_hash"),
            member.side.alias("member_side"),
            member.member_schedule_key.alias("member_schedule_key"),
            aggs.rank(asc(member.member_schedule_key))
            .per(group, member.side)
            .alias("rank_within_side"),
            (
                aggs.count(member).per(group).where(member.side == SIDE_REMOVED) | 0
            ).alias("removed_count"),
        )
    ).where(
        member.member_class == AMBIGUOUS_MEMBER_CLASS,
        member.group == group,
        comparison.comparison_id == member.comparison_id,
        *_q05_window(start, end),
    ).to_df()

    rows: list[dict[str, Any]] = []
    for row in _records(df):
        side = _as_str(row["member_side"])
        within = _as_int(row["rank_within_side"]) or 0
        removed = _as_int(row["removed_count"]) or 0
        ordinal = within if side == SIDE_REMOVED else removed + within
        rows.append(
            {
                "comparison_date": _as_date(row["comparison_date"]),
                "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
                "event_class": _as_str(row["event_class"]),
                "exactness": _as_str(row["exactness"]),
                "confidence": _as_str(row["confidence"]),
                "schedule_key": None,
                "related_schedule_key": None,
                "field_name": None,
                "old_value": None,
                "new_value": None,
                "group_id": None,
                "member_side": side,
                "member_schedule_key": _as_str(row["member_schedule_key"]),
                "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
                "_group_hash": _as_str(row["group_hash"]),
                "_ordinal": ordinal,
            }
        )
    return rows


def _q05_unpaired(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """``UNPAIRED_ADDITION`` / ``UNPAIRED_REMOVAL``: exact presence with no eligible partner.

    Every exact addition or removal that no candidate and no ambiguous group consumes gets
    exactly one unpaired evidence row with matching comparison date, side and schedule key,
    and no exact presence row is ever both partnered and unpaired. Confidence is ``NONE`` and
    exactness is ``UNPAIRED``: this is the honest answer when the key hash has destroyed the
    link and nothing in the data restores it.
    """
    am = model_package()
    member = am.ScheduleAmendmentGroupMember
    comparison = am.ScheduleComparison
    df = am.model.select(
        comparison.comparison_date.alias("comparison_date"),
        comparison.previous_knowledge_date.alias("previous_knowledge_date"),
        comparison.crosses_snapshot_gap.alias("crosses_snapshot_gap"),
        member.member_class.alias("event_class"),
        member.exactness.alias("exactness"),
        member.amendment_confidence.alias("confidence"),
        member.side.alias("member_side"),
        member.member_schedule_key.alias("member_schedule_key"),
    ).where(
        member.member_class != AMBIGUOUS_MEMBER_CLASS,
        comparison.comparison_id == member.comparison_id,
        *_q05_window(start, end),
    ).to_df()

    return [
        {
            "comparison_date": _as_date(row["comparison_date"]),
            "previous_knowledge_date": _as_date(row["previous_knowledge_date"]),
            "event_class": _as_str(row["event_class"]),
            "exactness": _as_str(row["exactness"]),
            "confidence": _as_str(row["confidence"]),
            "schedule_key": _as_str(row["member_schedule_key"]),
            "related_schedule_key": None,
            "field_name": None,
            "old_value": None,
            "new_value": None,
            "group_id": None,
            "member_side": _as_str(row["member_side"]),
            "member_schedule_key": _as_str(row["member_schedule_key"]),
            "crosses_snapshot_gap": bool(_as_bool(row["crosses_snapshot_gap"])),
            "_ordinal": None,
        }
        for row in _records(df)
    ]


def _q05_apply_labels(
    rows: list[dict[str, Any]], label_source: LabelSource
) -> list[dict[str, Any]]:
    """Attach ``event_id`` and ``group_id``, then ``row_id``. Presentation layer only.

    Three of the eight classes get a computed id from a manifest-adopted string template; the
    other five get a supplied mnemonic or a fail-loud ``UNLABELLED|...`` token. Nothing here
    touches a derived cell.
    """
    group_label_by_hash: dict[str, str] = {}
    for row in rows:
        if row["event_class"] == AMBIGUOUS_GROUP_CLASS:
            label = f"SYN-AMB-{row['comparison_date']:%Y%m%d}-{row['_ordinal']:02d}"
            row["group_id"] = label
            row["event_id"] = label
            group_hash = row.get("_group_hash")
            if group_hash:
                group_label_by_hash[group_hash] = label

    for row in rows:
        event_class = row["event_class"]
        if event_class == AMBIGUOUS_GROUP_CLASS:
            continue
        if event_class == CANDIDATE_UNIQUE_CLASS:
            row["event_id"] = f"SYN-CAND-{row['comparison_date']:%Y%m%d}-{row['_ordinal']:02d}"
        elif event_class == AMBIGUOUS_MEMBER_CLASS:
            group_hash = row.get("_group_hash")
            group_label = group_label_by_hash.get(
                group_hash or "", _unlabelled("GROUP", (group_hash,))
            )
            row["group_id"] = group_label
            row["event_id"] = f"{group_label}-M{row['_ordinal']}"
        else:
            row["event_id"] = label_source.event_id(_q05_label_identity(row))

    for row in rows:
        row.pop("_ordinal", None)
        row.pop("_group_hash", None)
        row["row_id"] = label_source.row_id(_q05_row_identity(row), "Q05")
    return rows


def schedule_four_week_changes(
    start_knowledge_date: dt.date | str | None,
    end_knowledge_date: dt.date | str | None,
    cadence_days: int | None,
    *,
    labels: LabelSource | None = None,
) -> pd.DataFrame:
    """Q05 - classify schedule changes across consecutive eligible publish snapshots.

    Eight visibly separate event classes, in two strictly separated layers. The exact layer
    (``EXACT_KEY_PRESERVING_MODIFICATION``, ``EXACT_ADDITION``, ``EXACT_REMOVAL``) is a
    presence-and-content fact set that stands on its own. The evidence layer
    (``CANDIDATE_UNIQUE``, ``AMBIGUOUS_CANDIDATE_GROUP``, ``AMBIGUOUS_GROUP_MEMBER``,
    ``UNPAIRED_ADDITION``, ``UNPAIRED_REMOVAL``) says what the exact layer cannot: which
    removal/addition pairs *might* be one carrier amending one service.

    **The trap this question exists for.** ``schedule_key`` hashes the effective and
    discontinue dates, so a carrier shifting either date mints a new key and one amendment
    looks like a removal plus an unrelated addition. That is not a bug to be fixed by
    rewriting the key: it is what the source does. Recognising the pair needs a match on
    ``(carrier, flight_number, origin, destination)`` with overlapping date ranges, and such a
    pair is reported as a **candidate** carrying confidence and evidence - never silently
    asserted as an exact modification, and never allowed to consume the two exact rows.

    An incomplete or missing snapshot never manufactures a removal. Both endpoints must be
    eligible; ``Q05-INELIGIBLE-ENDPOINT`` (2026-10-12 to 2026-10-19) is zero rows with
    ``ENDPOINT_MISSING`` because 2026-10-12 is absent and 2026-10-19 is present but
    incomplete, and the previous eligible complete snapshot, 2026-10-05, is not substituted
    for either.
    """
    start = _coerce_date(
        start_knowledge_date, "MISSING_START_KNOWLEDGE_DATE", "start_knowledge_date"
    )
    end = _coerce_date(end_knowledge_date, "MISSING_END_KNOWLEDGE_DATE", "end_knowledge_date")
    _coerce_cadence_days(cadence_days)
    label_source = labels or EMPTY_LABELS

    _require_eligible_endpoints(
        (("start_knowledge_date", start), ("end_knowledge_date", end))
    )

    rows = (
        _q05_exact(start, end)
        + _q05_candidates(start, end)
        + _q05_groups(start, end)
        + _q05_ambiguous_members(start, end)
        + _q05_unpaired(start, end)
    )
    rows = _q05_apply_labels(rows, label_source)
    rows.sort(
        key=lambda row: (
            (0, row["comparison_date"]),
            (0, EVENT_CLASS_RANK.get(row["event_class"], 999)),
            *_sort_key(row, ("event_id", "member_side", "member_schedule_key")),
        )
    )
    return _frame(rows, Q05_COLUMNS)


# =============================================================== conformance harness


QUESTION_FUNCTIONS: Mapping[str, Callable[..., pd.DataFrame]] = {
    "Q05": schedule_four_week_changes,
    "Q06": market_latest_vs_seven_days,
    "Q07": route_capacity_two_clocks,
}

_PARAMETER_ORDER: Mapping[str, tuple[str, ...]] = {
    "Q05": ("start_knowledge_date", "end_knowledge_date", "cadence_days"),
    "Q06": ("latest_knowledge_date", "comparison_knowledge_date", "carrier_role"),
    "Q07": ("knowledge_date", "operating_date", "carrier_role"),
}

_QUESTION_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "Q05": Q05_COLUMNS,
    "Q06": Q06_COLUMNS,
    "Q07": Q07_COLUMNS,
}


def invoke_result_set(
    question_id: str,
    result_set: Mapping[str, Any],
    labels: LabelSource | None = None,
) -> tuple[str, str | None, pd.DataFrame]:
    """Run one frozen result set. Returns ``(invocation_status, error_code, frame)``.

    A refusal yields a correctly shaped **empty** frame plus its status, so the three kinds of
    zero-row answer stay distinguishable: ``PARAMETER_ERROR`` before execution, an endpoint
    refusal, and a legitimately empty ``OK`` result.
    """
    function = QUESTION_FUNCTIONS[question_id]
    parameters = result_set["parameters"]
    args = [parameters.get(name) for name in _PARAMETER_ORDER[question_id]]
    try:
        return "OK", None, function(*args, labels=labels)
    except Uc2InvocationError as exc:
        return (
            exc.invocation_status,
            exc.error_code,
            _frame((), _QUESTION_COLUMNS[question_id]),
        )


def compare_rows(
    got: pd.DataFrame, expected: Sequence[Mapping[str, Any]], columns: Sequence[str]
) -> list[str]:
    """Complete ordered-sequence comparison. Missing and extra columns fail."""
    diffs: list[str] = []
    if list(got.columns) != list(columns):
        diffs.append(f"columns {list(got.columns)} != {list(columns)}")
        return diffs
    if len(got) != len(expected):
        diffs.append(f"cardinality {len(got)} != {len(expected)}")
    for index in range(max(len(got), len(expected))):
        if index >= len(got):
            diffs.append(f"row {index}: missing {expected[index].get('row_id')}")
            continue
        if index >= len(expected):
            diffs.append(f"row {index}: unexpected {got.iloc[index].get('row_id')}")
            continue
        actual = got.iloc[index]
        wanted = expected[index]
        for column in columns:
            left = actual[column]
            right = wanted.get(column)
            if not _cells_equal(left, right):
                diffs.append(
                    f"row {index} ({wanted.get('row_id')}) {column}: {left!r} != {right!r}"
                )
    return diffs


def _cells_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) is bool(right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)
    return left == right


def main(argv: Sequence[str] | None = None) -> int:
    """Run every frozen UC2 result set plus ``TT-BOTH-CLOCKS`` and print a pass/fail summary."""
    manifest = _load_manifest()
    questions = {q["question_id"]: q for q in manifest["questions"]}
    truth_tables = {t["truth_table_id"]: t for t in manifest["contract_truth_tables"]}

    results: list[tuple[str, bool, str]] = []
    for question_id in ("Q06", "Q07", "Q05"):
        question = questions[question_id]
        labels = manifest_label_source(question_id, manifest)
        columns = _QUESTION_COLUMNS[question_id]
        for result_set in question["result_sets"]:
            name = result_set["result_set_id"]
            status, error_code, frame = invoke_result_set(question_id, result_set, labels)
            expected_status = result_set["invocation_status"]
            expected_code = result_set.get("error_code")
            expected_rows = [
                _manifest_row(row) for row in (result_set.get("rows") or ())
            ]
            diffs: list[str] = []
            if status != expected_status:
                diffs.append(f"invocation_status {status!r} != {expected_status!r}")
            if expected_code is not None and error_code != expected_code:
                diffs.append(f"error_code {error_code!r} != {expected_code!r}")
            diffs += compare_rows(frame, expected_rows, columns)
            results.append((name, not diffs, "; ".join(diffs[:4])))

    table = truth_tables["TT-BOTH-CLOCKS"]
    got = both_clocks_truth_table()
    expected_tt = [_manifest_row(row) for row in table["rows"]]
    tt_diffs = compare_rows(got, expected_tt, tuple(got.columns))
    results.append(("TT-BOTH-CLOCKS", not tt_diffs, "; ".join(tt_diffs[:4])))

    width = max(len(name) for name, _, _ in results)
    failures = 0
    print()
    print("QUERY-UC2 conformance against EXPECTED_ANSWERS.yaml")
    print("-" * (width + 12))
    for name, ok, detail in results:
        if not ok:
            failures += 1
        print(f"{name.ljust(width)}  {'PASS' if ok else 'FAIL'}  {detail}")
    print("-" * (width + 12))
    print(f"{len(results) - failures}/{len(results)} result sets pass")
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
