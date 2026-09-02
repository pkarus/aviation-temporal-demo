"""aviation_temporal.py - the standalone RelationalAI ontology for the aviation temporal demo.

DO NOT EDIT. GENERATED from ``rai_code/aviation_model/`` by
``python -m aviation_model._gen_standalone``. Edit the package and regenerate; a hand edit here
silently forks the ontology, and ``tests/test_model.py::test_standalone_file_matches_the_package``
will fail on the next run.

This is the artifact you upload to a Snowflake stage and import from a Snowsight notebook or a
Workspace. It is self-contained: no relative imports, no ``raiconfig.yaml``, and no credentials.
``_build_config()`` detects the runtime - ``ConfigFromActiveSession`` when a Snowpark session
exists (Snowsight notebook, Workspace, stored procedure), ``create_config()`` otherwise (local
Python, auto-discovering ``~/.snowflake``). Both branches set strict mode
(``implicit_properties: False``) and pin the warm ``aviation_temporal_logic_s`` reasoner, which
is the difference between a 2.5-6s warm query and a 631s cold start.

Reading order, and it is also the load order: sentinels and tokens; the runtime config; the one
``Model``; the ``model.Table()`` bindings with their explicit ``schema=`` dicts; the reference,
aircraft, schedule and flight concepts; the shared temporal predicates; and finally the derived
rule layer, which is where the demo's actual content lives.
"""

from __future__ import annotations

import json
import datetime as dt

from pathlib import Path
from typing import Any, Iterable, Mapping

from relationalai.semantics import Bool, Date, DateTime, Float, Integer, Model, Number, String, inspect
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.constraints import unique
from relationalai.semantics.std.datetime import date as std_date


# ================================================================================================
# constants.py
# ================================================================================================
# constants.py - sentinels, tokens and the one database path string.
#
# Nothing here touches the network. ``DB`` is the single string MODEL-02's standalone
# generation has to rewrite, which is why every ``model.Table()`` path in ``sources.py``
# interpolates it rather than spelling the database out.



# --- Snowflake location -----------------------------------------------------------

DB = "PK_AVIATION_TEMPORAL"
SOURCE_SCHEMA = "SOURCE"
MODEL_INPUT_SCHEMA = "MODEL_INPUT"

MODEL_NAME = "aviation_temporal"
LOGIC_REASONER = "aviation_temporal_logic_s"

# --- Interval sentinels -----------------------------------------------------------
#
# BRIEF.md non-negotiable: source ``9999-12-31`` (unknown future) and model ``9999-01-01``
# (open interval) are different facts and never collapse. DATA-04 normalises the source
# sentinel away before RAI sees it, replacing it with NULL plus a companion
# ``*_IS_UNKNOWN_FUTURE`` boolean, so ``SOURCE_UNKNOWN_FUTURE`` must never appear in any
# bound date column. ``computed_aircraft.SentinelLeak`` is the zero-count guard that proves it.

MODEL_OPEN_INTERVAL = dt.date(9999, 1, 1)
SOURCE_UNKNOWN_FUTURE = dt.date(9999, 12, 31)

# --- Dimension discriminators (DV-04 / DV-05 ``dimension`` column) -----------------

DIM_AIRCRAFT_STATE = "aircraft_state"
DIM_AIRCRAFT_TYPE = "aircraft_type"
DIM_ENGINE_TYPE = "engine_type"
DIM_AIRCRAFT_STATUS = "aircraft_status"

DIMENSIONS = (
    DIM_AIRCRAFT_STATE,
    DIM_AIRCRAFT_TYPE,
    DIM_ENGINE_TYPE,
    DIM_AIRCRAFT_STATUS,
)

# --- DV-33 dimension query status -------------------------------------------------
#
# Four mutually exclusive outcomes, in the strict order SOURCE_CONTRACT.md fixes. Two are
# the presence of a covering daily assignment (``OK``, ``UNKNOWN_STATE``) and are carried on
# the row by DATA-04; two are the absence of one (``NO_RECORDED_STATE``, ``OUTSIDE_EXISTENCE``)
# and can only be decided against a date, so they are produced by ``temporal.dv33_branches``.

DV33_OK = "OK"
DV33_UNKNOWN_STATE = "UNKNOWN_STATE"
DV33_NO_RECORDED_STATE = "NO_RECORDED_STATE"
DV33_OUTSIDE_EXISTENCE = "OUTSIDE_EXISTENCE"

# --- Carrier roles (DV-29) --------------------------------------------------------

CARRIER_ROLE_MARKETING = "marketing"
CARRIER_ROLE_OPERATING = "operating"
CARRIER_ROLES = (CARRIER_ROLE_MARKETING, CARRIER_ROLE_OPERATING)

# --- Status tokens used by model rules --------------------------------------------
#
# Exact raw AH-09 values. NEO4J_RAI_MAPPING.md forbids trimming or case folding, so these
# are the literal strings and not a normalised form.

STATUS_IN_SERVICE = "In Service"
STATUS_STORAGE = "Storage"

# --- Resolution / physical-service tokens -----------------------------------------

RESOLUTION_EXACT = "EXACT"
PHYSICAL_SERVICE_COUNTED = "COUNTED"
PHYSICAL_SERVICE_UNRESOLVED = "UNRESOLVED_PHYSICAL_SERVICE"

# --- Rotation ---------------------------------------------------------------------

ROTATION_NO_TARGET_TOKEN = "NO_TARGET"

# --- ISO weekday numbering (1 = Monday), paired with the seven SS-14..SS-20 flags ---

WEEKDAY_FLAG_COLUMNS = (
    (1, "is_operating_monday"),
    (2, "is_operating_tuesday"),
    (3, "is_operating_wednesday"),
    (4, "is_operating_thursday"),
    (5, "is_operating_friday"),
    (6, "is_operating_saturday"),
    (7, "is_operating_sunday"),
)


# ================================================================================================
# config.py
# ================================================================================================
# config.py - one ``_build_config()`` that works locally and inside Snowflake.
#
# Two runtimes, one function:
#
# * **Local Python.** ``create_config(...)`` merges the programmatic keys over the
#   auto-discovered ``~/.snowflake/connections.toml`` profile. PROBE-01 confirmed the merge
#   works without passing ``connections`` explicitly, even though the docstring implies it is
#   required.
# * **Snowsight / Workspace / stored procedure.** There is no discoverable ``raiconfig.yaml``,
#   so ``ConfigFromActiveSession`` is used when a Snowpark session exists.
#
# Both branches set the same two things, and both matter:
#
# * ``model.implicit_properties = False`` (strict mode). The field defaults to ``True``, so it
#   has to be set explicitly. Strict mode does *not* protect a ``model.Table()`` from a column
#   typo (PROBE U-01) - ``sources.py``'s explicit ``schema=`` dicts do that - but it does stop
#   an undeclared Concept property from being invented silently.
# * ``reasoners.logic.name = "aviation_temporal_logic_s"``. Pinning the named engine is the
#   difference between a 2.5-6s warm query and a 631s cold start (PROBE U-12). Note the ``_s``
#   suffix: SDK 1.20.1 refuses ``HIGHMEM_X64_XS`` for Logic reasoners, so the locked ``_xs``
#   name in BRIEF.md does not exist and must not be used.






def _active_snowpark_session() -> Any | None:
    """Return the ambient Snowpark session, or ``None`` when running locally."""
    try:
        from snowflake.snowpark.context import get_active_session
    except Exception:
        return None
    try:
        return get_active_session()
    except Exception:
        return None


def in_snowflake_runtime() -> bool:
    """True when an ambient Snowpark session exists (Snowsight, Workspace, sproc)."""
    return _active_snowpark_session() is not None


def _build_config(**overrides: Any):
    """Strict-mode config pinned to the warm logic reasoner, for either runtime."""
    from relationalai.config.config import ConfigFromActiveSession, create_config

    settings: dict[str, Any] = {
        "model": {"implicit_properties": False},
        "reasoners": {"logic": {"name": LOGIC_REASONER}},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key] = {**settings[key], **value}
        else:
            settings[key] = value

    session = _active_snowpark_session()
    if session is not None:
        return ConfigFromActiveSession(**settings)
    return create_config(**settings)


# ================================================================================================
# model.py
# ================================================================================================
# model.py - the single ``Model`` instance.
#
# Kept in its own module so that ``sources.py`` and every ``core_*`` / ``computed_*`` module can
# import it without a circular import, and so there is exactly one ``Model`` per process. The
# free ``distinct(...)`` raises ``[Ambiguous model]`` the moment a second ``Model`` exists in the
# same interpreter (PROBE N-02), so a second instance is never created here.




model = Model(MODEL_NAME, config=_build_config())


# ================================================================================================
# _binding.py
# ================================================================================================
# _binding.py - the two helpers every ``core_*`` module uses to lift a table onto a Concept.
#
# Why helpers rather than 700 hand-written lines. The bound tables carry 748 contracted columns
# and ``SOURCE_CONTRACT.md`` requires every modelled field to trace to a documented source
# column. Writing each ``Property`` by hand would be 700 chances to mistype a column name, and
# PROBE U-01 proved a mistyped column binds *silently* as an ``Any``-typed relation. Driving the
# declarations off ``sources.py``'s explicit ``schema=`` dict makes the typo structurally
# impossible: the only column names in the system come from ``INFORMATION_SCHEMA``.
#
# Two live findings shape the implementation.
#
# * **Batched ``define()`` preserves sparse facts.** ``ONTOLOGY_DESIGN.md`` R2 warns that all
#   columns passed to ``.new()`` in one call are required, so a null drops the row. That is true
#   of ``.new()`` and is why identity is minted separately. It is *not* true of several
#   ``entity.prop(column)`` statements batched into one ``define()``: measured live against
#   ``MODEL_INPUT.AIRCRAFT_ELIGIBLE`` (999 rows, ``AIRCRAFT_END_OF_LIFE_DATE`` non-null on
#   exactly one), the batched and the one-define-per-column forms both returned
#   ``rows=999 eol_nn=1``. Absence of a value stays absence of a fact, which is P0-02.8.
# * **One ``define()`` call site per concept.** PyRel warns after 50 ``define()`` calls from the
#   same bytecode offset. Batching keeps every concept to a single call from
#   ``bind_scalars``, so the whole model makes roughly forty rule-emitting calls in total.
#
# Identity properties are never re-declared here: ``identify_by`` creates them, and declaring a
# second ``Property`` for the same name is a duplicate. Every caller passes those column names in
# ``exclude``.






def scalar_properties(
    concept,
    schema: Mapping[str, Any],
    *,
    exclude: Iterable[str] = (),
    rename: Mapping[str, str] | None = None,
    reading: str = "has",
) -> dict[str, str]:
    """Declare one ``Property`` per source column and attach it to ``concept``.

    ``schema`` is the ``SCHEMA_*`` dict from ``sources.py``, so the column names and RAI types
    are the ones ``INFORMATION_SCHEMA`` reported. Returns the ``{attribute: column}`` map that
    :func:`bind_scalars` consumes.

    The anti-bundle rule holds: every scalar becomes its own ``Property``, never a multi-field
    ``Relationship``, so each one is independently filterable and aggregatable.
    """
    rename = dict(rename or {})
    skip = set(exclude)
    mapping: dict[str, str] = {}
    for column, rai_type in schema.items():
        if column in skip:
            continue
        attr = rename.get(column, column)
        prop = model.Property(f"{concept} {reading} {rai_type:{attr}}")
        setattr(concept, attr, prop)
        mapping[attr] = column
    return mapping


def bind_scalars(concept, table, key: Mapping[str, Any], mapping: Mapping[str, str]) -> None:
    """Bind every scalar in ``mapping`` from ``table`` in a single ``define()``.

    ``key`` is the ``Concept.lookup(...)`` keyword mapping that re-finds the entity minted by
    the caller's ``.new()``. ``lookup`` supersedes the deprecated ``filter_by`` used throughout
    ``ONTOLOGY_DESIGN.md``; a key that resolves to no entity yields no fact and no error, which
    is the quarantine semantics section 1.3 depends on and the reason ``inventory.py`` asserts
    a per-concept count against SQL.
    """
    entity = concept.lookup(**key)
    statements = [getattr(entity, attr)(getattr(table, column)) for attr, column in mapping.items()]
    model.define(entity, *statements)


# ================================================================================================
# sources.py
# ================================================================================================
# sources.py - every ``model.Table()`` binding, with an explicit ``schema=`` dict.
#
# GENERATED from ``PK_AVIATION_TEMPORAL.INFORMATION_SCHEMA.COLUMNS``, then checked in.
# Regenerate with ``python -m aviation_model._regen_sources``;
# ``tests/test_model.py::test_declared_types_match_information_schema`` re-derives the mapping
# live and fails on any drift.
#
# Three rules this file exists to enforce, all from ``build/design/PROBE_RESULTS.md``:
#
# * **R1 - an explicit ``schema=`` dict everywhere.** Strict mode gives *zero* typo protection
#   on a ``model.Table()`` (PROBE U-01): a misspelled column binds silently as an ``Any``-typed
#   relation and produces an empty or NaN result later. The dict is the only defence, and
#   ``inventory.py`` asserts that no discovered column is ``Any``.
# * **U-03 - the 26 Snowflake ``TIME`` columns are declared ``String``.** Discovered *or*
#   explicitly declared as ``DateTime`` they come back 100% NULL with no error. Declared
#   ``String`` the value is byte-identical to ``TO_VARCHAR(t, 'HH24:MI:SS.FF3')``, so every
#   time-of-day literal must be written ``'HH:MM:SS.mmm'``; ``'16:00:00'`` matches zero rows.
# * **U-02 - a wrong declared type is a silent all-NaN column, not a ``TyperError``.** Types are
#   therefore derived from ``INFORMATION_SCHEMA`` rather than eyeballed, and the integer mapping
#   mirrors the SDK's own CDC bucketing rather than the column's declared precision:
#   ``NUMBER(p,0)`` with ``p <= 18`` is ``Number.size(18, 0)`` and with ``19 <= p <= 38`` is
#   ``Integer``. Declaring the faithful ``Number.size(19, 0)`` for a ``NUMBER(19,0)`` column
#   returned 600 rows and 0 non-null values, silently - see :func:`derive_type`. The MODEL-01
#   gate asserts per-column non-null counts against SQL, not just row counts, which is the only
#   check that catches it.
#
# D-0027 SUPERSEDES D-0019 here: the row-scoped ``CODE_RESOLUTION`` (784,140 rows),
# ``CODE_RESOLUTION_CANDIDATE`` (627,424) and ``CODE_RESOLUTION_INPUT`` (784,140) ARE now bound.
# D-0019 excluded them on a performance premise that measurement refuted: binding all three cost
# 0.18s on first query and no measurable warm delta. The distinct-code projection
# ``CODE_RESOLUTION_CODE`` (660 rows) is retained for link semantics, and every other
# MODEL_INPUT object already carries its own resolved target id plus resolution status. The
# timed experiment that settled it is recorded in ``build/task_reports/MODEL-01.json``; the
# tables stay materialized and reachable from SQL.




SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR = {
    "expected_publish_date": Date,
    "is_present": Bool,
    "is_complete": Bool,
    "source_lineage_id": String,
    "observed_row_count": Integer,
    "validation_status": String,
}

SRC_SCHEDULE_SNAPSHOT_CALENDAR = model.Table(f"{DB}.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR", schema=SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR)

SCHEMA_SRC_AIRCRAFT_CONFIGURATION = {
    "aircraft_configuration_id": Integer,
    "aircraft_family": String,
    "aircraft_type": String,
    "aircraft_series": String,
    "aircraft_subseries": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "engine_count": Integer,
    "has_multiple_engine_types": Bool,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type": String,
    "engine_series": String,
    "engine_subseries": String,
    "engine_propulsion_type": String,
    "publish_date": Date,
}

SRC_AIRCRAFT_CONFIGURATION = model.Table(f"{DB}.SOURCE.AIRCRAFT_CONFIGURATION", schema=SCHEMA_SRC_AIRCRAFT_CONFIGURATION)

SCHEMA_MI_AIRCRAFT_ELIGIBLE = {
    "aircraft_id": Integer,
    "aircraft_serial_number": String,
    "aircraft_line_number": String,
    "aircraft_order_date": Date,
    "aircraft_order_date_is_unknown_future": Bool,
    "aircraft_build_date": Date,
    "aircraft_build_date_is_unknown_future": Bool,
    "aircraft_delivery_date": Date,
    "aircraft_delivery_date_is_unknown_future": Bool,
    "aircraft_roll_out_date": Date,
    "aircraft_roll_out_date_is_unknown_future": Bool,
    "aircraft_first_flight_date": Date,
    "aircraft_first_flight_date_is_unknown_future": Bool,
    "aircraft_start_of_life_date": Date,
    "aircraft_start_of_life_date_is_unknown_future": Bool,
    "aircraft_end_of_life_date": Date,
    "aircraft_end_of_life_date_is_unknown_future": Bool,
    "existence_from": Date,
    "existence_to": Date,
    "has_finite_end_of_life": Bool,
    "existence_from_basis": String,
    "aircraft_build_airport_code_iata": String,
    "aircraft_build_airport": String,
    "original_delivery_operator": String,
    "original_delivery_operator_category": String,
    "master_current_only_apu_type": String,
    "master_current_only_aircraft_width_m": Float,
    "master_current_only_operating_maximum_takeoff_weight_lb": Integer,
    "master_current_only_certified_maximum_takeoff_weight_lb": Integer,
    "not_for_use": Bool,
    "first_eligible_event_date": Date,
}

MI_AIRCRAFT_ELIGIBLE = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_ELIGIBLE", schema=SCHEMA_MI_AIRCRAFT_ELIGIBLE)

SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE = {
    "aircraft_history_id": Integer,
    "aircraft_id": Integer,
    "row_sequence_number": Integer,
    "event_sequence_number": Integer,
    "start_event_date": Date,
    "end_event_date": Date,
    "end_event_date_is_unknown_future": Bool,
    "is_current": Bool,
    "start_event": String,
    "start_aircraft_status": String,
    "end_event": String,
    "end_aircraft_status": String,
    "event_source": String,
    "aircraft_configuration_id": Integer,
    "aircraft_code_iata": String,
    "aircraft_code_icao": String,
    "aircraft_value_sub_series": String,
    "aircraft_registration_number": String,
    "aircraft_transponder_code": String,
    "aircraft_registration_country_code_iso": String,
    "aircraft_registration_region": String,
    "aircraft_cargo": String,
    "storage_location": String,
    "storage_airport_code_iata": String,
    "base_airport": String,
    "base_airport_code_iata": String,
    "base_city": String,
    "base_country": String,
    "apu_type": String,
    "aircraft_width_m": Float,
    "operating_maximum_takeoff_weight_lb": Integer,
    "certified_maximum_takeoff_weight_lb": Integer,
    "base_state": String,
    "base_region": String,
    "storage_location_type": String,
    "noise_certification": String,
    "has_winglets": Bool,
    "aircraft_registration_country": String,
    "transponder_miscode": Bool,
    "maximum_landing_weight_lb": Integer,
    "operating_empty_weight_lb": Integer,
    "not_for_use": Bool,
    "publish_date": Date,
    "publish_date_is_unknown_future": Bool,
    "existence_from": Date,
    "existence_to": Date,
    "event_order_rank": Number.size(18, 0),
    "configuration_resolved": Bool,
    "aircraft_family": String,
    "aircraft_type": String,
    "aircraft_series": String,
    "aircraft_subseries": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "engine_count": Integer,
    "has_multiple_engine_types": Bool,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type": String,
    "engine_series": String,
    "engine_subseries": String,
    "engine_propulsion_type": String,
    "configuration_publish_date": Date,
    "type_resolution_status": String,
    "engine_resolution_status": String,
    "mixed_engine_set_complete": Bool,
    "would_be_lost_by_inner_join": Bool,
}

MI_AIRCRAFT_EVENT_ELIGIBLE = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE", schema=SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE)

SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE = {
    "quarantine_id": String,
    "source_object": String,
    "quarantine_reason": String,
    "raw_aircraft_history_id": Integer,
    "raw_aircraft_id": Integer,
    "raw_row_sequence_number": Integer,
    "raw_event_sequence_number": Integer,
    "raw_start_event_date": Date,
    "typed_normalized_row_hash": String,
    "quarantine_key_basis": String,
    "missing_required_fields": String,
    "occurrence_count": Number.size(18, 0),
}

MI_AIRCRAFT_EVENT_QUARANTINE = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_EVENT_QUARANTINE", schema=SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE)

SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT = {
    "audit_assignment_id": String,
    "dimension": String,
    "aircraft_id": Integer,
    "event_date": Date,
    "row_sequence_number": Integer,
    "event_sequence_number": Integer,
    "aircraft_history_id": Integer,
    "event_order_rank": Number.size(18, 0),
    "dimension_sequence": Number.size(18, 0),
    "is_final_relevant_observation_of_day": Bool,
    "watched_signature": String,
    "previous_watched_signature": String,
    "dimension_resolution_status": String,
    "end_event_date": Date,
    "end_event_date_is_unknown_future": Bool,
    "start_event": String,
    "event_source": String,
    "aircraft_configuration_id": Integer,
    "aircraft_registration_number": String,
    "aircraft_transponder_code": String,
    "aircraft_registration_country_code_iso": String,
    "aircraft_registration_region": String,
    "aircraft_cargo": String,
    "storage_location": String,
    "storage_airport_code_iata": String,
    "base_airport": String,
    "base_airport_code_iata": String,
    "base_city": String,
    "base_country": String,
    "apu_type": String,
    "aircraft_width_m": Float,
    "operating_maximum_takeoff_weight_lb": Integer,
    "certified_maximum_takeoff_weight_lb": Integer,
    "base_state": String,
    "base_region": String,
    "storage_location_type": String,
    "noise_certification": String,
    "has_winglets": Bool,
    "aircraft_registration_country": String,
    "transponder_miscode": Bool,
    "maximum_landing_weight_lb": Integer,
    "operating_empty_weight_lb": Integer,
    "aircraft_status_code": String,
    "aircraft_code_iata": String,
    "aircraft_code_icao": String,
    "aircraft_value_sub_series": String,
    "aircraft_type_subseries": String,
    "exact_aircraft_type_subseries": String,
    "aircraft_family": String,
    "aircraft_type_label": String,
    "aircraft_series": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "engine_type_subseries": String,
    "exact_engine_type_subseries": String,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type_label": String,
    "engine_series": String,
    "engine_propulsion_type": String,
    "engine_count": Integer,
    "has_multiple_engine_types": Bool,
    "mixed_engine_set_complete": Bool,
}

MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT", schema=SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT)

SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT = {
    "daily_assignment_id": String,
    "audit_assignment_id": String,
    "dimension": String,
    "aircraft_id": Integer,
    "valid_from": Date,
    "valid_to": Date,
    "next_assignment_date": Date,
    "existence_from": Date,
    "existence_to": Date,
    "valid_to_clipped_to_existence": Bool,
    "aircraft_history_id": Integer,
    "row_sequence_number": Integer,
    "event_sequence_number": Integer,
    "event_order_rank": Number.size(18, 0),
    "dimension_resolution_status": String,
    "dimension_query_status": String,
    "end_event_date": Date,
    "end_event_date_is_unknown_future": Bool,
    "end_event_date_disagrees_with_valid_to": Bool,
    "start_event": String,
    "event_source": String,
    "aircraft_configuration_id": Integer,
    "aircraft_registration_number": String,
    "aircraft_transponder_code": String,
    "aircraft_registration_country_code_iso": String,
    "aircraft_registration_region": String,
    "aircraft_cargo": String,
    "storage_location": String,
    "storage_airport_code_iata": String,
    "base_airport": String,
    "base_airport_code_iata": String,
    "base_city": String,
    "base_country": String,
    "apu_type": String,
    "aircraft_width_m": Float,
    "operating_maximum_takeoff_weight_lb": Integer,
    "certified_maximum_takeoff_weight_lb": Integer,
    "base_state": String,
    "base_region": String,
    "storage_location_type": String,
    "noise_certification": String,
    "has_winglets": Bool,
    "aircraft_registration_country": String,
    "transponder_miscode": Bool,
    "maximum_landing_weight_lb": Integer,
    "operating_empty_weight_lb": Integer,
    "aircraft_status_code": String,
    "aircraft_code_iata": String,
    "aircraft_code_icao": String,
    "aircraft_value_sub_series": String,
    "aircraft_type_subseries": String,
    "exact_aircraft_type_subseries": String,
    "aircraft_family": String,
    "aircraft_type_label": String,
    "aircraft_series": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "engine_type_subseries": String,
    "exact_engine_type_subseries": String,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type_label": String,
    "engine_series": String,
    "engine_propulsion_type": String,
    "engine_count": Integer,
    "has_multiple_engine_types": Bool,
    "mixed_engine_set_complete": Bool,
}

MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT", schema=SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT)

SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION = {
    "aircraft_subseries": String,
    "aircraft_family": String,
    "aircraft_type": String,
    "aircraft_series": String,
    "aircraft_manufacturer": String,
    "aircraft_design_class": String,
    "definition_variant_count": Number.size(18, 0),
    "source_configuration_count": Number.size(18, 0),
    "definition_status": String,
}

MI_AIRCRAFT_TYPE_DEFINITION = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION", schema=SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION)

SCHEMA_MI_ENGINE_TYPE_DEFINITION = {
    "engine_subseries": String,
    "engine_manufacturer": String,
    "engine_family": String,
    "engine_type": String,
    "engine_series": String,
    "engine_propulsion_type": String,
    "definition_variant_count": Number.size(18, 0),
    "source_configuration_count": Number.size(18, 0),
    "definition_status": String,
}

MI_ENGINE_TYPE_DEFINITION = model.Table(f"{DB}.MODEL_INPUT.ENGINE_TYPE_DEFINITION", schema=SCHEMA_MI_ENGINE_TYPE_DEFINITION)

SCHEMA_MI_AIRPORT_CURRENT = {
    "airport_id": String,
    "selected_effective_start_date": Date,
    "selected_effective_end_date": Date,
    "airport_code_iata": String,
    "airport_code_icao": String,
    "airport_name": String,
    "is_active": Bool,
    "is_current": Bool,
    "time_zone_name": String,
    "reference_period_count": Number.size(18, 0),
    "projection_rule": String,
}

MI_AIRPORT_CURRENT = model.Table(f"{DB}.MODEL_INPUT.AIRPORT_CURRENT", schema=SCHEMA_MI_AIRPORT_CURRENT)

SCHEMA_MI_AIRLINE_CURRENT = {
    "airline_id": String,
    "selected_effective_start_date": Date,
    "selected_effective_end_date": Date,
    "carrier_code_iata": String,
    "carrier_code_icao": String,
    "carrier_short_name": String,
    "carrier_full_name": String,
    "is_iata_controlled_duplicate": Bool,
    "is_active": Bool,
    "is_current": Bool,
    "reference_period_count": Number.size(18, 0),
    "projection_rule": String,
}

MI_AIRLINE_CURRENT = model.Table(f"{DB}.MODEL_INPUT.AIRLINE_CURRENT", schema=SCHEMA_MI_AIRLINE_CURRENT)

SCHEMA_MI_CODE_RESOLUTION_CODE = {
    "domain": String,
    "method": String,
    "raw_code": String,
    "candidate_count": Number.size(18, 0),
    "single_candidate_id": String,
    "resolution_status": String,
    "matched_code_systems": String,
}

MI_CODE_RESOLUTION_CODE = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION_CODE", schema=SCHEMA_MI_CODE_RESOLUTION_CODE)

SCHEMA_MI_CODE_RESOLUTION_CODE_CANDIDATE = {
    "domain": String,
    "method": String,
    "raw_code": String,
    "candidate_id": String,
    "matched_code_systems": String,
}

MI_CODE_RESOLUTION_CODE_CANDIDATE = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION_CODE_CANDIDATE", schema=SCHEMA_MI_CODE_RESOLUTION_CODE_CANDIDATE)

SCHEMA_MI_CODE_RESOLUTION_INPUT = {
    "domain": String,
    "source_object": String,
    "source_row_token": String,
    "field_role": String,
    "raw_field_id": String,
    "raw_code": String,
    "method": String,
    "source_occurrence_count": Number.size(18, 0),
}

MI_CODE_RESOLUTION_INPUT = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION_INPUT", schema=SCHEMA_MI_CODE_RESOLUTION_INPUT)

SCHEMA_MI_CODE_RESOLUTION = {
    "resolution_id": String,
    "domain": String,
    "source_object": String,
    "source_row_token": String,
    "field_role": String,
    "raw_field_id": String,
    "raw_code": String,
    "method": String,
    "source_occurrence_count": Number.size(18, 0),
    "candidate_count": Number.size(18, 0),
    "resolution_status": String,
    "resolved_identity_id": String,
    "matched_code_systems": String,
}

MI_CODE_RESOLUTION = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION", schema=SCHEMA_MI_CODE_RESOLUTION)

SCHEMA_MI_CODE_RESOLUTION_CANDIDATE = {
    "resolution_id": String,
    "candidate_id": String,
    "domain": String,
    "method": String,
    "raw_code": String,
    "matched_code_systems": String,
    "candidate_count": Number.size(18, 0),
    "resolution_status": String,
}

MI_CODE_RESOLUTION_CANDIDATE = model.Table(f"{DB}.MODEL_INPUT.CODE_RESOLUTION_CANDIDATE", schema=SCHEMA_MI_CODE_RESOLUTION_CANDIDATE)

SCHEMA_MI_MONTH_END_CALENDAR = {
    "month_end": Date,
    "month_start": Date,
    "calendar_year": Number.size(18, 0),
    "calendar_month": Number.size(18, 0),
    "month_index": Integer,
}

MI_MONTH_END_CALENDAR = model.Table(f"{DB}.MODEL_INPUT.MONTH_END_CALENDAR", schema=SCHEMA_MI_MONTH_END_CALENDAR)

SCHEMA_MI_ROUTE = {
    "route_id": String,
    "origin_station_code_iata": String,
    "destination_station_code_iata": String,
    "origin_airport_id": String,
    "origin_airport_resolution_status": String,
    "destination_airport_id": String,
    "destination_airport_resolution_status": String,
    "canonical_observation_count": Number.size(18, 0),
    "distinct_schedule_key_count": Number.size(18, 0),
}

MI_ROUTE = model.Table(f"{DB}.MODEL_INPUT.ROUTE", schema=SCHEMA_MI_ROUTE)

SCHEMA_MI_ROUTE_STATE = {
    "route_state_key": String,
    "schedule_key": String,
    "route_id": String,
    "knowledge_valid_from": Date,
    "knowledge_valid_to": Date,
    "is_open_state": Bool,
    "segment_open_kind": String,
    "is_reappearance": Bool,
    "closing_reason": String,
    "previous_eligible_publish_date_at_open": Date,
    "open_crosses_snapshot_gap": Bool,
    "open_skipped_calendar_dates": String,
    "close_crosses_snapshot_gap": Bool,
    "close_skipped_calendar_dates": String,
    "contributing_snapshot_count": Number.size(18, 0),
    "normalized_row_hash": String,
    "schedule_key_readable": String,
    "itinerary_variation_identifier": Integer,
    "marketing_carrier_internal": String,
    "operating_carrier_internal": String,
    "flight_number": Integer,
    "service_type_iata": String,
    "operating_effective_date": Date,
    "operating_discontinue_date": Date,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "departure_terminal": String,
    "arrival_terminal": String,
    "is_operating_monday": Bool,
    "is_operating_tuesday": Bool,
    "is_operating_wednesday": Bool,
    "is_operating_thursday": Bool,
    "is_operating_friday": Bool,
    "is_operating_saturday": Bool,
    "is_operating_sunday": Bool,
    "days_pattern": String,
    "weekly_frequency": Integer,
    "passenger_departure_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_departure_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_local_time": String,  # TIME -> String (PROBE U-03)
    "arrival_day_indicator": Integer,
    "scheduled_block_minutes": Integer,
    "equipment_subtype_code_iata": String,
    "total_seats": Float,
    "first_class_seats": Float,
    "business_class_seats": Float,
    "premium_economy_seats": Float,
    "economy_class_seats": Float,
    "is_codeshare": Bool,
    "codeshare_carrier_internal": String,
    "number_of_intermediate_stops": Integer,
    "intermediate_stop_station_codes_iata": String,
    "watched_content_signature": String,
    "economy_excluding_premium": Float,
    "exclusive_cabin_sum": Float,
    "cabin_quality_status": String,
    "marketing_airline_id": String,
    "marketing_airline_resolution_status": String,
    "operating_airline_id": String,
    "operating_airline_resolution_status": String,
    "codeshare_airline_id": String,
    "codeshare_airline_resolution_status": String,
    "origin_airport_id": String,
    "origin_airport_resolution_status": String,
    "destination_airport_id": String,
    "destination_airport_resolution_status": String,
    "physical_service_status": String,
    "utc_date_status": String,
}

MI_ROUTE_STATE = model.Table(f"{DB}.MODEL_INPUT.ROUTE_STATE", schema=SCHEMA_MI_ROUTE_STATE)

SCHEMA_MI_ROUTE_STATE_LINEAGE = {
    "route_state_key": String,
    "schedule_key": String,
    "publish_date": Date,
    "normalized_row_hash": String,
    "itinerary_variation_identifier": Integer,
    "raw_observation_count": Number.size(18, 0),
    "semantic_duplicate_count": Number.size(18, 0),
    "watched_content_signature": String,
    "is_segment_opening_observation": Bool,
    "snapshot_source_lineage_id": String,
    "snapshot_validation_status": String,
}

MI_ROUTE_STATE_LINEAGE = model.Table(f"{DB}.MODEL_INPUT.ROUTE_STATE_LINEAGE", schema=SCHEMA_MI_ROUTE_STATE_LINEAGE)

SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION = {
    "schedule_key": String,
    "publish_date": Date,
    "schedule_key_readable": String,
    "normalized_row_hash": String,
    "itinerary_variation_identifier": Integer,
    "raw_observation_count": Number.size(18, 0),
    "semantic_duplicate_count": Number.size(18, 0),
    "selection_rule": String,
    "snapshot_is_present": Bool,
    "snapshot_is_complete": Bool,
    "is_eligible_snapshot": Bool,
    "snapshot_validation_status": String,
    "snapshot_source_lineage_id": String,
    "marketing_carrier_internal": String,
    "operating_carrier_internal": String,
    "flight_number": Integer,
    "service_type_iata": String,
    "effective_date": Date,
    "discontinue_date": Date,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "departure_terminal": String,
    "arrival_terminal": String,
    "is_operating_monday": Bool,
    "is_operating_tuesday": Bool,
    "is_operating_wednesday": Bool,
    "is_operating_thursday": Bool,
    "is_operating_friday": Bool,
    "is_operating_saturday": Bool,
    "is_operating_sunday": Bool,
    "days_pattern": String,
    "weekly_frequency": Integer,
    "passenger_departure_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_departure_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_local_time": String,  # TIME -> String (PROBE U-03)
    "arrival_day_indicator": Integer,
    "scheduled_block_minutes": Integer,
    "equipment_subtype_code_iata": String,
    "total_seats": Float,
    "first_class_seats": Float,
    "business_class_seats": Float,
    "premium_economy_seats": Float,
    "economy_class_seats": Float,
    "is_codeshare": Bool,
    "codeshare_carrier_internal": String,
    "number_of_intermediate_stops": Integer,
    "intermediate_stop_station_codes_iata": String,
    "route_id": String,
    "route_key_status": String,
    "watched_content_signature": String,
    "economy_excluding_premium": Float,
    "exclusive_cabin_sum": Float,
    "cabin_quality_status": String,
    "marketing_airline_id": String,
    "marketing_airline_resolution_status": String,
    "operating_airline_id": String,
    "operating_airline_resolution_status": String,
    "codeshare_airline_id": String,
    "codeshare_airline_resolution_status": String,
    "origin_airport_id": String,
    "origin_airport_resolution_status": String,
    "destination_airport_id": String,
    "destination_airport_resolution_status": String,
    "physical_service_status": String,
    "utc_date_status": String,
}

MI_SCHEDULE_CANONICAL_OBSERVATION = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION", schema=SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION)

SCHEMA_MI_SCHEDULE_COMPARISON = {
    "comparison_id": String,
    "previous_knowledge_date": Date,
    "comparison_date": Date,
    "previous_eligible_rank": Number.size(18, 0),
    "comparison_eligible_rank": Number.size(18, 0),
    "calendar_day_span": Number.size(18, 0),
    "skipped_calendar_date_count": Number.size(18, 0),
    "crosses_snapshot_gap": Bool,
    "skipped_calendar_dates": String,
    "comparison_kind": String,
}

MI_SCHEDULE_COMPARISON = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_COMPARISON", schema=SCHEMA_MI_SCHEDULE_COMPARISON)

SCHEMA_MI_SCHEDULE_EXACT_CHANGE = {
    "comparison_id": String,
    "previous_knowledge_date": Date,
    "comparison_date": Date,
    "crosses_snapshot_gap": Bool,
    "skipped_calendar_dates": String,
    "schedule_key": String,
    "change_kind": String,
    "field_name": String,
    "old_value": String,
    "new_value": String,
    "is_reappearance": Bool,
}

MI_SCHEDULE_EXACT_CHANGE = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_EXACT_CHANGE", schema=SCHEMA_MI_SCHEDULE_EXACT_CHANGE)

SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE = {
    "comparison_id": String,
    "previous_knowledge_date": Date,
    "comparison_date": Date,
    "schedule_key": String,
    "side": String,
    "marketing_carrier_internal": String,
    "flight_number": Integer,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "effective_date": Date,
    "discontinue_date": Date,
    "operating_carrier_internal": String,
    "days_pattern": String,
    "weekly_frequency": Integer,
    "equipment_subtype_code_iata": String,
    "total_seats": Float,
    "passenger_departure_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_local_time": String,  # TIME -> String (PROBE U-03)
    "candidate_eligible": Bool,
    "ineligibility_reason": String,
    "candidate_signature": String,
}

MI_SCHEDULE_AMENDMENT_SIDE = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE", schema=SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE)

SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE = {
    "amendment_candidate_id": String,
    "comparison_id": String,
    "removed_schedule_key": String,
    "added_schedule_key": String,
    "amendment_candidate_class": String,
    "amendment_confidence": String,
    "exactness": String,
    "candidate_signature": String,
    "marketing_carrier_internal": String,
    "flight_number": Integer,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "removed_effective_date": Date,
    "removed_discontinue_date": Date,
    "added_effective_date": Date,
    "added_discontinue_date": Date,
    "removed_operating_carrier_internal": String,
    "added_operating_carrier_internal": String,
    "removed_days_pattern": String,
    "added_days_pattern": String,
    "removed_weekly_frequency": Integer,
    "added_weekly_frequency": Integer,
    "removed_equipment_subtype_code_iata": String,
    "added_equipment_subtype_code_iata": String,
    "removed_total_seats": Float,
    "added_total_seats": Float,
}

MI_SCHEDULE_AMENDMENT_CANDIDATE = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_AMENDMENT_CANDIDATE", schema=SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE)

SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP = {
    "amendment_group_id": String,
    "comparison_id": String,
    "candidate_signature": String,
    "marketing_carrier_internal": String,
    "flight_number": Integer,
    "departure_station_code_iata": String,
    "arrival_station_code_iata": String,
    "removed_member_count": Number.size(18, 0),
    "added_member_count": Number.size(18, 0),
    "removed_schedule_keys": String,
    "added_schedule_keys": String,
    "amendment_candidate_class": String,
    "amendment_confidence": String,
    "exactness": String,
}

MI_SCHEDULE_AMENDMENT_GROUP = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP", schema=SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP)

SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER = {
    "amendment_group_member_id": String,
    "amendment_group_id": String,
    "comparison_id": String,
    "side": String,
    "member_schedule_key": String,
    "member_class": String,
    "amendment_confidence": String,
    "exactness": String,
    "candidate_signature": String,
    "unpaired_reason": String,
}

MI_SCHEDULE_AMENDMENT_GROUP_MEMBER = model.Table(f"{DB}.MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP_MEMBER", schema=SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER)

SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL = {
    "passenger_flight_key": String,
    "marketing_carrier_internal": String,
    "flight_number": Integer,
    "planned_origin_station_code_iata": String,
    "planned_destination_station_code_iata": String,
    "operating_date": Date,
    "selected_source_system": String,
    "selected_source_row_token": String,
    "selected_source_row_token_basis": String,
    "selected_stable_source_row_id": Integer,
    "selected_typed_normalized_row_hash": String,
    "source_precedence_rule": String,
    "lineage_observation_count": Number.size(18, 0),
    "historical_lineage_retained": Bool,
    "forward_lineage_retained": Bool,
    "operating_carrier_internal": String,
    "publish_date": Date,
    "service_type_iata": String,
    "equipment_subtype_code_iata": String,
    "total_seats": Float,
    "is_codeshare": Bool,
    "number_of_intermediate_stops": Integer,
    "intermediate_stop_station_codes_iata": String,
    "arrival_day_indicator": Integer,
    "plan_departure_local_timestamp": DateTime,
    "plan_arrival_local_timestamp": DateTime,
    "plan_departure_utc_timestamp": DateTime,
    "plan_arrival_utc_timestamp": DateTime,
    "utc_date_status": String,
    "schedule_key": String,
    "historical_effective_date": Date,
    "passenger_departure_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_local_time": String,  # TIME -> String (PROBE U-03)
    "passenger_departure_utc_time": String,  # TIME -> String (PROBE U-03)
    "passenger_arrival_utc_time": String,  # TIME -> String (PROBE U-03)
    "departure_utc_offset_minutes": Float,
    "arrival_utc_offset_minutes": Float,
    "marketing_airline_id": String,
    "marketing_airline_resolution_status": String,
    "operating_airline_id": String,
    "operating_airline_resolution_status": String,
    "planned_origin_airport_id": String,
    "planned_origin_airport_resolution_status": String,
    "planned_destination_airport_id": String,
    "planned_destination_airport_resolution_status": String,
}

MI_PASSENGER_FLIGHT_CANONICAL = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL", schema=SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL)

SCHEMA_MI_PASSENGER_FLIGHT_INVALID = {
    "source_system": String,
    "stable_source_row_id": Integer,
    "source_row_token": String,
    "typed_normalized_row_hash": String,
    "passenger_key_status": String,
    "invalid_reason": String,
    "missing_key_components": String,
    "raw_marketing_carrier_internal": String,
    "raw_flight_number": Integer,
    "raw_departure_station_code_iata": String,
    "raw_arrival_station_code_iata": String,
    "raw_operating_date": Date,
    "publish_date": Date,
}

MI_PASSENGER_FLIGHT_INVALID = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_FLIGHT_INVALID", schema=SCHEMA_MI_PASSENGER_FLIGHT_INVALID)

SCHEMA_MI_PASSENGER_SOURCE_LINEAGE = {
    "passenger_flight_key": String,
    "source_system": String,
    "source_row_token": String,
    "source_row_token_basis": String,
    "stable_source_row_id": Integer,
    "typed_normalized_row_hash": String,
    "publish_date": Date,
    "source_precedence_rank": Number.size(18, 0),
    "selection_rank": Number.size(18, 0),
    "is_selected_observation": Bool,
    "schedule_key": String,
    "operating_carrier_internal": String,
    "total_seats": Float,
    "is_codeshare": Bool,
    "number_of_intermediate_stops": Integer,
    "intermediate_stop_station_codes_iata": String,
    "utc_date_status": String,
}

MI_PASSENGER_SOURCE_LINEAGE = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_SOURCE_LINEAGE", schema=SCHEMA_MI_PASSENGER_SOURCE_LINEAGE)

SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE = {
    "quarantine_id": String,
    "source_object": String,
    "quarantine_reason": String,
    "typed_normalized_row_hash": String,
    "quarantine_key_basis": String,
    "missing_key_components": String,
    "raw_flight_number": Integer,
    "raw_departure_station_code_iata": String,
    "raw_arrival_station_code_iata": String,
    "raw_operating_date": Date,
    "occurrence_count": Number.size(18, 0),
}

MI_PASSENGER_SOURCE_QUARANTINE = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_SOURCE_QUARANTINE", schema=SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE)

SCHEMA_MI_PASSENGER_PLANNED_LEG = {
    "passenger_flight_key": String,
    "leg_index": Integer,
    "from_station_code_iata": String,
    "to_station_code_iata": String,
    "station_count": Number.size(18, 0),
    "from_airport_id": String,
    "from_airport_resolution_status": String,
    "to_airport_id": String,
    "to_airport_resolution_status": String,
}

MI_PASSENGER_PLANNED_LEG = model.Table(f"{DB}.MODEL_INPUT.PASSENGER_PLANNED_LEG", schema=SCHEMA_MI_PASSENGER_PLANNED_LEG)

SCHEMA_MI_AIRCRAFT_FLIGHT = {
    "flight_id": Integer,
    "aircraft_id": Integer,
    "aircraft_link_exists": Bool,
    "operating_carrier_code": String,
    "marketing_carrier_code": String,
    "raw_flight_number": String,
    "normalized_flight_number": Integer,
    "flight_number_status": String,
    "flight_departure_date": Date,
    "flight_departure_date_utc": Date,
    "departure_airport_code": String,
    "arrival_airport_code": String,
    "actual_continuity_arrival_code": String,
    "diverted_airport_code": String,
    "raw_is_cancelled": Integer,
    "is_cancelled_boolean": Bool,
    "cancellation_flag_status": String,
    "raw_is_diverted": Integer,
    "is_diverted_boolean": Bool,
    "diversion_flag_status": String,
    "diversion_endpoint_conflict": Bool,
    "actual_gate_departure_time_utc": DateTime,
    "actual_gate_arrival_time_utc": DateTime,
    "actual_gate_departure_time_local": DateTime,
    "actual_gate_arrival_time_local": DateTime,
    "actual_source_aircraft_type": String,
    "actual_source_aircraft_code_iata": String,
    "actual_source_aircraft_family": String,
    "next_flight_id": Integer,
    "actual_origin_airport_id": String,
    "actual_origin_airport_resolution_status": String,
    "actual_destination_airport_id": String,
    "actual_destination_airport_resolution_status": String,
    "diverted_airport_id": String,
    "diverted_airport_resolution_status": String,
    "operating_airline_id": String,
    "operating_airline_resolution_status": String,
    "marketing_airline_id": String,
    "marketing_airline_resolution_status": String,
}

MI_AIRCRAFT_FLIGHT = model.Table(f"{DB}.MODEL_INPUT.AIRCRAFT_FLIGHT", schema=SCHEMA_MI_AIRCRAFT_FLIGHT)

SCHEMA_MI_ROTATION_LINK_VALIDATION = {
    "flight_id": Integer,
    "target_token": String,
    "next_flight_id": Integer,
    "aircraft_id": Integer,
    "selected_local_date": Date,
    "selected_date_basis": String,
    "rotation_link_status": String,
    "rotation_anomaly_class": String,
    "is_accepted_link": Bool,
    "cycle_component_id": Integer,
    "is_cycle_representative": Bool,
    "is_self_loop_link": Bool,
    "actual_origin_code": String,
    "actual_continuity_arrival_code": String,
    "diverted_airport_code": String,
    "diversion_endpoint_conflict": Bool,
    "actual_gate_departure_time_utc": DateTime,
    "actual_gate_arrival_time_utc": DateTime,
    "is_cancelled_boolean": Bool,
    "cancellation_flag_status": String,
    "is_diverted_boolean": Bool,
    "diversion_flag_status": String,
    "target_flight_id": Integer,
    "target_aircraft_id": Integer,
    "target_selected_local_date": Date,
    "target_departure_time_utc": DateTime,
    "target_origin_code": String,
    "target_is_cancelled_boolean": Bool,
}

MI_ROTATION_LINK_VALIDATION = model.Table(f"{DB}.MODEL_INPUT.ROTATION_LINK_VALIDATION", schema=SCHEMA_MI_ROTATION_LINK_VALIDATION)

SCHEMA_MI_FULFILLMENT_EXACT = {
    "exact_fulfillment_id": String,
    "actual_flight_id": Integer,
    "passenger_flight_key": String,
    "passenger_source_system": String,
    "passenger_source_row_token": String,
    "passenger_stable_source_row_id": Integer,
    "fulfillment_class": String,
    "exactness": String,
    "exact_link_basis": String,
    "confirmed_link": Bool,
    "actual_operating_date": Date,
    "planned_operating_date": Date,
    "actual_marketing_airline_id": String,
    "planned_marketing_airline_id": String,
    "actual_operating_airline_id": String,
    "planned_operating_airline_id": String,
    "normalized_flight_number": Integer,
    "planned_flight_number": Integer,
    "actual_origin_airport_id": String,
    "actual_destination_airport_id": String,
}

MI_FULFILLMENT_EXACT = model.Table(f"{DB}.MODEL_INPUT.FULFILLMENT_EXACT", schema=SCHEMA_MI_FULFILLMENT_EXACT)

SCHEMA_MI_FULFILLMENT_CANDIDATE = {
    "fulfillment_candidate_id": String,
    "actual_flight_id": Integer,
    "passenger_flight_key": String,
    "fulfillment_class": String,
    "exactness": String,
    "confidence": String,
    "confirmed_link": Bool,
    "marketing_role_agrees": Bool,
    "operating_role_agrees": Bool,
    "normalized_flight_number": Integer,
    "actual_operating_date": Date,
    "leg_index": Integer,
    "station_count": Number.size(18, 0),
    "planned_service_has_stopovers": Bool,
    "actual_origin_airport_id": String,
    "actual_destination_airport_id": String,
}

MI_FULFILLMENT_CANDIDATE = model.Table(f"{DB}.MODEL_INPUT.FULFILLMENT_CANDIDATE", schema=SCHEMA_MI_FULFILLMENT_CANDIDATE)

SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP = {
    "fulfillment_group_member_id": String,
    "fulfillment_group_id": String,
    "side": String,
    "member_identity": String,
    "member_class": String,
    "exactness": String,
    "confidence": String,
    "confirmed_link": Bool,
    "actual_member_count": Integer,
    "passenger_member_count": Integer,
    "unmatched_reason": String,
}

MI_FULFILLMENT_AMBIGUOUS_GROUP = model.Table(f"{DB}.MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP", schema=SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP)


# alias -> (Table, "SCHEMA.TABLE", declared column -> RAI type)
TABLE_INVENTORY = {
    "SRC_SCHEDULE_SNAPSHOT_CALENDAR": (SRC_SCHEDULE_SNAPSHOT_CALENDAR, "SOURCE.SCHEDULE_SNAPSHOT_CALENDAR", SCHEMA_SRC_SCHEDULE_SNAPSHOT_CALENDAR),
    "SRC_AIRCRAFT_CONFIGURATION": (SRC_AIRCRAFT_CONFIGURATION, "SOURCE.AIRCRAFT_CONFIGURATION", SCHEMA_SRC_AIRCRAFT_CONFIGURATION),
    "MI_AIRCRAFT_ELIGIBLE": (MI_AIRCRAFT_ELIGIBLE, "MODEL_INPUT.AIRCRAFT_ELIGIBLE", SCHEMA_MI_AIRCRAFT_ELIGIBLE),
    "MI_AIRCRAFT_EVENT_ELIGIBLE": (MI_AIRCRAFT_EVENT_ELIGIBLE, "MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE", SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE),
    "MI_AIRCRAFT_EVENT_QUARANTINE": (MI_AIRCRAFT_EVENT_QUARANTINE, "MODEL_INPUT.AIRCRAFT_EVENT_QUARANTINE", SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE),
    "MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT": (MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT, "MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT", SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT),
    "MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT": (MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT, "MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT", SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT),
    "MI_AIRCRAFT_TYPE_DEFINITION": (MI_AIRCRAFT_TYPE_DEFINITION, "MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION", SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION),
    "MI_ENGINE_TYPE_DEFINITION": (MI_ENGINE_TYPE_DEFINITION, "MODEL_INPUT.ENGINE_TYPE_DEFINITION", SCHEMA_MI_ENGINE_TYPE_DEFINITION),
    "MI_AIRPORT_CURRENT": (MI_AIRPORT_CURRENT, "MODEL_INPUT.AIRPORT_CURRENT", SCHEMA_MI_AIRPORT_CURRENT),
    "MI_AIRLINE_CURRENT": (MI_AIRLINE_CURRENT, "MODEL_INPUT.AIRLINE_CURRENT", SCHEMA_MI_AIRLINE_CURRENT),
    "MI_CODE_RESOLUTION_CODE": (MI_CODE_RESOLUTION_CODE, "MODEL_INPUT.CODE_RESOLUTION_CODE", SCHEMA_MI_CODE_RESOLUTION_CODE),
    "MI_CODE_RESOLUTION_CODE_CANDIDATE": (MI_CODE_RESOLUTION_CODE_CANDIDATE, "MODEL_INPUT.CODE_RESOLUTION_CODE_CANDIDATE", SCHEMA_MI_CODE_RESOLUTION_CODE_CANDIDATE),
    "MI_CODE_RESOLUTION_INPUT": (MI_CODE_RESOLUTION_INPUT, "MODEL_INPUT.CODE_RESOLUTION_INPUT", SCHEMA_MI_CODE_RESOLUTION_INPUT),
    "MI_CODE_RESOLUTION": (MI_CODE_RESOLUTION, "MODEL_INPUT.CODE_RESOLUTION", SCHEMA_MI_CODE_RESOLUTION),
    "MI_CODE_RESOLUTION_CANDIDATE": (MI_CODE_RESOLUTION_CANDIDATE, "MODEL_INPUT.CODE_RESOLUTION_CANDIDATE", SCHEMA_MI_CODE_RESOLUTION_CANDIDATE),
    "MI_MONTH_END_CALENDAR": (MI_MONTH_END_CALENDAR, "MODEL_INPUT.MONTH_END_CALENDAR", SCHEMA_MI_MONTH_END_CALENDAR),
    "MI_ROUTE": (MI_ROUTE, "MODEL_INPUT.ROUTE", SCHEMA_MI_ROUTE),
    "MI_ROUTE_STATE": (MI_ROUTE_STATE, "MODEL_INPUT.ROUTE_STATE", SCHEMA_MI_ROUTE_STATE),
    "MI_ROUTE_STATE_LINEAGE": (MI_ROUTE_STATE_LINEAGE, "MODEL_INPUT.ROUTE_STATE_LINEAGE", SCHEMA_MI_ROUTE_STATE_LINEAGE),
    "MI_SCHEDULE_CANONICAL_OBSERVATION": (MI_SCHEDULE_CANONICAL_OBSERVATION, "MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION", SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION),
    "MI_SCHEDULE_COMPARISON": (MI_SCHEDULE_COMPARISON, "MODEL_INPUT.SCHEDULE_COMPARISON", SCHEMA_MI_SCHEDULE_COMPARISON),
    "MI_SCHEDULE_EXACT_CHANGE": (MI_SCHEDULE_EXACT_CHANGE, "MODEL_INPUT.SCHEDULE_EXACT_CHANGE", SCHEMA_MI_SCHEDULE_EXACT_CHANGE),
    "MI_SCHEDULE_AMENDMENT_SIDE": (MI_SCHEDULE_AMENDMENT_SIDE, "MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE", SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE),
    "MI_SCHEDULE_AMENDMENT_CANDIDATE": (MI_SCHEDULE_AMENDMENT_CANDIDATE, "MODEL_INPUT.SCHEDULE_AMENDMENT_CANDIDATE", SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE),
    "MI_SCHEDULE_AMENDMENT_GROUP": (MI_SCHEDULE_AMENDMENT_GROUP, "MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP", SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP),
    "MI_SCHEDULE_AMENDMENT_GROUP_MEMBER": (MI_SCHEDULE_AMENDMENT_GROUP_MEMBER, "MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP_MEMBER", SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER),
    "MI_PASSENGER_FLIGHT_CANONICAL": (MI_PASSENGER_FLIGHT_CANONICAL, "MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL", SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL),
    "MI_PASSENGER_FLIGHT_INVALID": (MI_PASSENGER_FLIGHT_INVALID, "MODEL_INPUT.PASSENGER_FLIGHT_INVALID", SCHEMA_MI_PASSENGER_FLIGHT_INVALID),
    "MI_PASSENGER_SOURCE_LINEAGE": (MI_PASSENGER_SOURCE_LINEAGE, "MODEL_INPUT.PASSENGER_SOURCE_LINEAGE", SCHEMA_MI_PASSENGER_SOURCE_LINEAGE),
    "MI_PASSENGER_SOURCE_QUARANTINE": (MI_PASSENGER_SOURCE_QUARANTINE, "MODEL_INPUT.PASSENGER_SOURCE_QUARANTINE", SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE),
    "MI_PASSENGER_PLANNED_LEG": (MI_PASSENGER_PLANNED_LEG, "MODEL_INPUT.PASSENGER_PLANNED_LEG", SCHEMA_MI_PASSENGER_PLANNED_LEG),
    "MI_AIRCRAFT_FLIGHT": (MI_AIRCRAFT_FLIGHT, "MODEL_INPUT.AIRCRAFT_FLIGHT", SCHEMA_MI_AIRCRAFT_FLIGHT),
    "MI_ROTATION_LINK_VALIDATION": (MI_ROTATION_LINK_VALIDATION, "MODEL_INPUT.ROTATION_LINK_VALIDATION", SCHEMA_MI_ROTATION_LINK_VALIDATION),
    "MI_FULFILLMENT_EXACT": (MI_FULFILLMENT_EXACT, "MODEL_INPUT.FULFILLMENT_EXACT", SCHEMA_MI_FULFILLMENT_EXACT),
    "MI_FULFILLMENT_CANDIDATE": (MI_FULFILLMENT_CANDIDATE, "MODEL_INPUT.FULFILLMENT_CANDIDATE", SCHEMA_MI_FULFILLMENT_CANDIDATE),
    "MI_FULFILLMENT_AMBIGUOUS_GROUP": (MI_FULFILLMENT_AMBIGUOUS_GROUP, "MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP", SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP),
}


# ================================================================================================
# core_reference.py
# ================================================================================================
# core_reference.py - reference entities every other module links to.
#
# Loaded before ``core_aircraft`` / ``core_schedule`` / ``core_flight`` because Python needs the
# Concept objects to exist before their reading f-strings interpolate them.
#
# ``Airport`` and ``Airline`` bind from the ``MODEL_INPUT.*_CURRENT`` projections rather than from
# ``SOURCE.*_REFERENCE``. PROBE G-03 / G-04 showed the raw source is *already* one effective
# period per entity, so binding ``SOURCE`` directly would not have raised - but the projections
# carry a ``PROJECTION_RULE`` column recording the declared deterministic order, which is exactly
# what ``ATTRIBUTE_AUTHORITY.md`` demands instead of relying on ``WHERE is_current``. Using them
# puts the choice of winner in the data instead of in a query. ``REFERENCE_PERIOD_COUNT`` is
# carried so a future multi-period fixture is visible rather than silent.
#
# ``CodeResolutionCode`` is the D-0019 substitution for the row-scoped ``CODE_RESOLUTION``: link
# semantics only ever need "does this raw code resolve to exactly one identity", which is a
# property of the code, not of the row that mentioned it.




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


# ================================================================================================
# core_aircraft.py
# ================================================================================================
# core_aircraft.py - UC1: aircraft identity, events, definitions and both assignment layers.
#
# This module is the reduced-demo fallback (AGENTS.md: "UC1 is the independently runnable
# fallback"). It plus ``temporal.py``, ``calendar.py`` and ``computed_aircraft.py`` answers Q01
# through Q04 on its own, with no schedule or flight surface at all.
#
# The shape that matters, and the reason it is not obvious:
#
# * **Identity never carries state.** ``Aircraft`` is ``AM-01`` alone. Registration, type, engine
#   and status are all versioned assignments hanging off it, never properties of it (P0-01.1).
# * **Two assignment layers, not one.** The *audit* stream is the ordered same-day truth and
#   carries **no** date interval, ever. The *daily* projection carries the half-open interval and
#   keeps only the final relevant observation per aircraft/dimension/date. Q02's same-day
#   ``Storage -> In Service`` spell exists only on the audit stream; reading the daily stream
#   loses it silently. Keeping them as two concepts makes that impossible to conflate by accident.
# * **Compound identity makes the same-day rule structural.** BRIEF.md: "Order aircraft events by
#   date and sequence; do not identify a version by date alone." Putting ``event_date``,
#   ``row_sequence`` and ``event`` into ``identify_by`` means two same-day observations are two
#   entities permanently, and no downstream rule can collapse them. PROBE U-08 confirmed
#   Concept-valued identity components load from a Snowflake table, that an identical re-define
#   mints zero new entities, and that a row whose parent does not resolve produces no assignment
#   *and no error* - which is why ``inventory.py`` asserts a count per association.
# * **The DV-05 string key is carried as a non-identity property.** ``EXPECTED_ANSWERS.yaml``
#   freezes the literal ``assignment_id`` spelling, so RAI reads it rather than re-deriving it.
#
# Multiplicity: every ``assignment -> parent`` link is a functional ``Property``, and every
# ``parent -> assignments`` link is unconstrained. Where the forward link is a Property this
# module declares, the inverse is an ``.alt()`` *reading* over the same fields, which adds a name
# and no FD. Where the forward link is an *identity component* (``assignment.aircraft``,
# ``assignment.event``) the inverse is an explicit multi-valued ``Relationship`` instead, because
# ``identify_by`` names the owner slot after the lowercased concept and an ``.alt()`` reading
# would have to spell ``aircraftdimensionauditassignment`` to match. Both forms leave the
# one-to-many direction unconstrained, which is what SOURCE_CONTRACT.md requires: "Aircraft to
# audit assignments, one-to-many, association concept; never a functional property".




# --- Aircraft (AM-01) -------------------------------------------------------------

Aircraft = model.Concept("Aircraft", identify_by={"id": Integer})

_aircraft_scalars = scalar_properties(
    Aircraft, SCHEMA_MI_AIRCRAFT_ELIGIBLE, exclude=("aircraft_id",)
)
model.define(Aircraft.new(id=MI_AIRCRAFT_ELIGIBLE.aircraft_id))
bind_scalars(
    Aircraft,
    MI_AIRCRAFT_ELIGIBLE,
    {"id": MI_AIRCRAFT_ELIGIBLE.aircraft_id},
    _aircraft_scalars,
)

# --- AircraftConfiguration (AC-01) ------------------------------------------------
#
# A join target only. It left-preserves every event: an assignment whose configuration does not
# resolve keeps its identity and simply has no configuration fact (P0-12.3).

AircraftConfiguration = model.Concept("AircraftConfiguration", identify_by={"id": Integer})

_configuration_scalars = scalar_properties(
    AircraftConfiguration,
    SCHEMA_SRC_AIRCRAFT_CONFIGURATION,
    exclude=("aircraft_configuration_id",),
)
model.define(
    AircraftConfiguration.new(id=SRC_AIRCRAFT_CONFIGURATION.aircraft_configuration_id)
)
bind_scalars(
    AircraftConfiguration,
    SRC_AIRCRAFT_CONFIGURATION,
    {"id": SRC_AIRCRAFT_CONFIGURATION.aircraft_configuration_id},
    _configuration_scalars,
)

# --- AircraftType (AC-05) and EngineType (AC-14) ----------------------------------
#
# Definition attributes only, and only because PROBE G-01 / G-02 measured zero violating keys.
# AC-08 ``engine_count`` and AC-09 ``has_multiple_engine_types`` deliberately do NOT live on
# ``EngineType``: they are ENGINE_ASSIGNMENT_ATTRIBUTEs per ATTRIBUTE_AUTHORITY.md, they are
# functional on the subseries in this fixture only by accident of a near-bijective generator,
# and asserting one engine count per engine-subseries identity would be wrong in the domain.
# They are bound on the assignment instead, below.

AircraftType = model.Concept("AircraftType", identify_by={"subseries": String})

_aircraft_type_scalars = scalar_properties(
    AircraftType, SCHEMA_MI_AIRCRAFT_TYPE_DEFINITION, exclude=("aircraft_subseries",)
)
model.define(AircraftType.new(subseries=MI_AIRCRAFT_TYPE_DEFINITION.aircraft_subseries))
bind_scalars(
    AircraftType,
    MI_AIRCRAFT_TYPE_DEFINITION,
    {"subseries": MI_AIRCRAFT_TYPE_DEFINITION.aircraft_subseries},
    _aircraft_type_scalars,
)

EngineType = model.Concept("EngineType", identify_by={"subseries": String})

_engine_type_scalars = scalar_properties(
    EngineType, SCHEMA_MI_ENGINE_TYPE_DEFINITION, exclude=("engine_subseries",)
)
model.define(EngineType.new(subseries=MI_ENGINE_TYPE_DEFINITION.engine_subseries))
bind_scalars(
    EngineType,
    MI_ENGINE_TYPE_DEFINITION,
    {"subseries": MI_ENGINE_TYPE_DEFINITION.engine_subseries},
    _engine_type_scalars,
)

# --- AircraftStatus (AH-09) -------------------------------------------------------
#
# G-07: no attributes at all, ever. The identity is the raw AH-09 string with no trim and no
# case fold (NEO4J_RAI_MAPPING.md), and adding a "display label" would be the first step toward
# the normalisation the contract forbids. Minted from the observed audit values, so the
# vocabulary is whatever the source actually contains rather than a hard-coded enum.

AircraftStatus = model.Concept("AircraftStatus", identify_by={"code": String})

model.define(
    AircraftStatus.new(code=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_status_code)
)

# --- AircraftEvent (AH-01) --------------------------------------------------------
#
# An ordered fact. It never carries a date interval (P0-01.4); ``END_EVENT_DATE`` is retained
# as provenance and takes part in no validity predicate.

AircraftEvent = model.Concept("AircraftEvent", identify_by={"id": Integer})

_event_scalars = scalar_properties(
    AircraftEvent,
    SCHEMA_MI_AIRCRAFT_EVENT_ELIGIBLE,
    exclude=("aircraft_history_id", "aircraft_id"),
)
model.define(AircraftEvent.new(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id))
bind_scalars(
    AircraftEvent,
    MI_AIRCRAFT_EVENT_ELIGIBLE,
    {"id": MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id},
    _event_scalars,
)

AircraftEvent.aircraft = model.Property(
    f"{AircraftEvent:event} observed on {Aircraft:aircraft}"
)
model.define(
    AircraftEvent.lookup(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_history_id).aircraft(
        Aircraft.lookup(id=MI_AIRCRAFT_EVENT_ELIGIBLE.aircraft_id)
    )
)
Aircraft.events = AircraftEvent.aircraft.alt(
    f"{Aircraft:aircraft} has event {AircraftEvent:event}"
)

# --- AircraftEventQuarantine (DV-44) ----------------------------------------------

AircraftEventQuarantine = model.Concept(
    "AircraftEventQuarantine", identify_by={"quarantine_id": String}
)
_event_quarantine_scalars = scalar_properties(
    AircraftEventQuarantine,
    SCHEMA_MI_AIRCRAFT_EVENT_QUARANTINE,
    exclude=("quarantine_id",),
)
model.define(
    AircraftEventQuarantine.new(quarantine_id=MI_AIRCRAFT_EVENT_QUARANTINE.quarantine_id)
)
bind_scalars(
    AircraftEventQuarantine,
    MI_AIRCRAFT_EVENT_QUARANTINE,
    {"quarantine_id": MI_AIRCRAFT_EVENT_QUARANTINE.quarantine_id},
    _event_quarantine_scalars,
)

# --- AircraftDimensionAuditAssignment (DV-04) -------------------------------------
#
# Identity = (dimension, aircraft, event_date, row_sequence, event). Verified live: 97,983 rows,
# 97,983 distinct tuples. No interval here by construction - the audit stream is order, not
# duration.

_AUDIT_IDENTITY_COLUMNS = (
    "dimension",
    "aircraft_id",
    "event_date",
    "row_sequence_number",
    "aircraft_history_id",
)

AircraftDimensionAuditAssignment = model.Concept(
    "AircraftDimensionAuditAssignment",
    identify_by={
        "dimension": String,
        "aircraft": Aircraft,
        "event_date": Date,
        "row_sequence": Integer,
        "event": AircraftEvent,
    },
)
AuditAssignment = AircraftDimensionAuditAssignment  # readable alias for rule modules

_audit_scalars = scalar_properties(
    AuditAssignment,
    SCHEMA_MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT,
    exclude=_AUDIT_IDENTITY_COLUMNS,
)

def _audit_key() -> dict:
    """A *fresh* identity-key mapping for each rule.

    ``lookup()`` returns a new reference every call and two references are never unified
    implicitly, so a single shared key object reused across several ``define()`` calls would
    risk one rule's binding leaking into another. Building it per rule costs nothing and
    removes the question.
    """
    return {
        "dimension": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.dimension,
        "aircraft": Aircraft.lookup(id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_id),
        "event_date": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.event_date,
        "row_sequence": MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.row_sequence_number,
        "event": AircraftEvent.lookup(
            id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_history_id
        ),
    }


model.define(AuditAssignment.new(**_audit_key()))
bind_scalars(
    AuditAssignment,
    MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT,
    _audit_key(),
    _audit_scalars,
)

# The inverses of the two *identity* components are declared as explicit multi-valued
# ``Relationship``s rather than as ``.alt()`` readings. ``.alt()`` is the cheaper construct and
# is used everywhere else in this file, but it requires the new reading to reuse the underlying
# relationship's field names, and ``identify_by`` names an entity component's owner slot after
# the lowercased concept - here ``aircraftdimensionauditassignment``. An inverse reading forced
# to spell that would be unreadable in the ontology inventory a customer sees. A
# ``Relationship`` adds no functional dependency either, so the "one aircraft, many
# assignments" direction stays unconstrained exactly as SOURCE_CONTRACT.md requires.
Aircraft.audit_assignments = model.Relationship(
    f"{Aircraft:aircraft} has audit assignment {AuditAssignment:assignment}"
)
model.define(Aircraft.audit_assignments(AuditAssignment)).where(
    AuditAssignment.aircraft == Aircraft
)
AircraftEvent.audit_assignments = model.Relationship(
    f"{AircraftEvent:event} minted audit assignment {AuditAssignment:assignment}"
)
model.define(AircraftEvent.audit_assignments(AuditAssignment)).where(
    AuditAssignment.event == AircraftEvent
)

# --- AircraftDimensionDailyAssignment (DV-05) -------------------------------------
#
# Identity = (dimension, aircraft, valid_from, event). Verified live: 97,979 rows, 97,979
# distinct tuples, and the same count for the DV-05 string key. The half-open interval
# DV-06/DV-07 lives here as two functional ``Date`` properties, because 1.20.1 has no interval
# type at all - which is honest parity with Neo4j, and is also why nothing in the API holds a
# one-open-version-per-parent assumption on our behalf.

_DAILY_IDENTITY_COLUMNS = (
    "dimension",
    "aircraft_id",
    "valid_from",
    "aircraft_history_id",
)

AircraftDimensionDailyAssignment = model.Concept(
    "AircraftDimensionDailyAssignment",
    identify_by={
        "dimension": String,
        "aircraft": Aircraft,
        "valid_from": Date,
        "event": AircraftEvent,
    },
)
DailyAssignment = AircraftDimensionDailyAssignment  # readable alias for rule modules

_daily_scalars = scalar_properties(
    DailyAssignment,
    SCHEMA_MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT,
    exclude=_DAILY_IDENTITY_COLUMNS,
)

def _daily_key() -> dict:
    """A fresh identity-key mapping for each rule; see :func:`_audit_key`."""
    return {
        "dimension": MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.dimension,
        "aircraft": Aircraft.lookup(id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_id),
        "valid_from": MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.valid_from,
        "event": AircraftEvent.lookup(
            id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_history_id
        ),
    }


model.define(DailyAssignment.new(**_daily_key()))
bind_scalars(
    DailyAssignment,
    MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT,
    _daily_key(),
    _daily_scalars,
)

Aircraft.daily_assignments = model.Relationship(
    f"{Aircraft:aircraft} has daily assignment {DailyAssignment:assignment}"
)
model.define(Aircraft.daily_assignments(DailyAssignment)).where(
    DailyAssignment.aircraft == Aircraft
)

# --- Exact links out of the assignments -------------------------------------------
#
# All four are ``Property``: at most one exact target per assignment, never exactly one
# (SOURCE_CONTRACT.md "zero-or-one exact target per dimension"). An unresolved reference is
# therefore the absence of a fact rather than a fabricated node, which is precisely the
# ``UNKNOWN_STATE`` gap P0-02.8 wants and what makes the DV-33 classification expressible.
# Verified live: zero orphan ``EXACT_AIRCRAFT_TYPE_SUBSERIES`` and zero orphan
# ``EXACT_ENGINE_TYPE_SUBSERIES`` over 47,984 non-null values each.

DailyAssignment.aircraft_type = model.Property(
    f"{DailyAssignment:assignment} conformed to {AircraftType:aircraft_type}"
)
DailyAssignment.engine_type = model.Property(
    f"{DailyAssignment:assignment} equipped with {EngineType:engine_type}"
)
DailyAssignment.status = model.Property(
    f"{DailyAssignment:assignment} assigned status {AircraftStatus:status}"
)
DailyAssignment.configuration = model.Property(
    f"{DailyAssignment:assignment} read configuration {AircraftConfiguration:configuration}"
)

model.define(
    DailyAssignment.lookup(**_daily_key()).aircraft_type(
        AircraftType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.exact_aircraft_type_subseries
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).engine_type(
        EngineType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.exact_engine_type_subseries
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).status(
        AircraftStatus.lookup(
            code=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_status_code
        )
    )
)
model.define(
    DailyAssignment.lookup(**_daily_key()).configuration(
        AircraftConfiguration.lookup(
            id=MI_AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT.aircraft_configuration_id
        )
    )
)

AuditAssignment.aircraft_type = model.Property(
    f"{AuditAssignment:assignment} observed type {AircraftType:aircraft_type}"
)
AuditAssignment.engine_type = model.Property(
    f"{AuditAssignment:assignment} observed engine {EngineType:engine_type}"
)
AuditAssignment.status = model.Property(
    f"{AuditAssignment:assignment} observed status {AircraftStatus:status}"
)
AuditAssignment.configuration = model.Property(
    f"{AuditAssignment:assignment} observed configuration {AircraftConfiguration:configuration}"
)

model.define(
    AuditAssignment.lookup(**_audit_key()).aircraft_type(
        AircraftType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.exact_aircraft_type_subseries
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).engine_type(
        EngineType.lookup(
            subseries=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.exact_engine_type_subseries
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).status(
        AircraftStatus.lookup(
            code=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_status_code
        )
    )
)
model.define(
    AuditAssignment.lookup(**_audit_key()).configuration(
        AircraftConfiguration.lookup(
            id=MI_AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT.aircraft_configuration_id
        )
    )
)

AircraftType.daily_assignments = DailyAssignment.aircraft_type.alt(
    f"{AircraftType:aircraft_type} assigned by {DailyAssignment:assignment}"
)
EngineType.daily_assignments = DailyAssignment.engine_type.alt(
    f"{EngineType:engine_type} fitted by {DailyAssignment:assignment}"
)

# --- No resolved base-airport link, deliberately ----------------------------------
#
# Tempting, and wrong. AH-24 ``BASE_AIRPORT`` is a descriptive label ("Synthetic base"), not an
# internal airport id, and AH-25 ``BASE_AIRPORT_CODE_IATA`` is a public IATA code that
# ``AIRPORT_CURRENT`` does not key on. DATA-04 emits no resolved ``BASE_AIRPORT_ID`` column for
# the aircraft dimension, so there is no exact resolution to bind and inventing one by joining
# on the IATA code would assert a link the contract never resolved. Both raw values stay bound
# as plain strings (SOURCE_CONTRACT.md: a failed resolution must still show the code), and Q01
# emits ``base_airport_code_iata`` from the string, not from an ``Airport`` entity.


# ================================================================================================
# calendar_dates.py
# ================================================================================================
# calendar_dates.py - the ``MonthEnd`` concept behind Q03.
#
# Named ``calendar_dates`` rather than ``calendar`` so it cannot shadow the Python standard
# library module of that name for any consumer of this package.
#
# Why a materialized concept rather than a Python range. Q03's whole point is that the
# interval-to-calendar inequality join replaces a 120-iteration parameter sweep, and that the same
# query works for an irregular calendar. That only holds if the calendar is a *joined dimension*
# inside the model. PROBE U-05 separately confirmed ``std.datetime.date.range(freq="M")`` produces
# exactly the right 120 month ends, so the notebook keeps it as an independent cross-check - but
# the query joins the table, not the range.




MonthEnd = model.Concept("MonthEnd", identify_by={"month_end": Date})

_month_end_scalars = scalar_properties(
    MonthEnd, SCHEMA_MI_MONTH_END_CALENDAR, exclude=("month_end",)
)
model.define(MonthEnd.new(month_end=MI_MONTH_END_CALENDAR.month_end))
bind_scalars(
    MonthEnd,
    MI_MONTH_END_CALENDAR,
    {"month_end": MI_MONTH_END_CALENDAR.month_end},
    _month_end_scalars,
)


# ================================================================================================
# core_schedule.py
# ================================================================================================
# core_schedule.py - UC2: schedules, routes, route states and the change/amendment evidence.
#
# **This module contains the demo's central semantic beat, and it is one line long.**
#
# The customer's Neo4j model versions state by ``(schedule_key, valid_from)`` but hangs it off
# ``ROUTE`` via ``(ROUTE)-[:HAS]->(ROUTE_STATE)``. A generic SCD Type 2 builder has exactly one
# structural assumption - at most one open ``valid_to`` per parent key - so their builder has to be
# told, per relationship, that the partition is ``schedule_key`` and not the parent ``route``.
# Nothing in the graph schema records that. Get it wrong and you either close states that should
# stay open or you raise an integrity error on a route that legitimately has hundreds of
# concurrent open schedules.
#
# In RAI there is nothing to relax, because there was never a constraint to relax:
#
# .. code-block:: python
#
#     RouteState = model.Concept("RouteState", identify_by={"route_state_key": String})
#
# ``Route`` does not appear in that identity. The versioning partition is therefore a structural,
# readable property of the ontology sitting in one line a reviewer can check, rather than a
# parameter passed to a builder. And because cardinality in RAI is declared per relationship and
# points one way, ``Route.states`` - an ``.alt()`` reading over the same fields as
# ``RouteState.route`` - carries no cardinality claim at all. Multi-open is the default; single-open
# is what you would have to opt into.
#
# Measured, live: at knowledge date 2026-08-31 the route ``SFO->LAX`` has **1,339 concurrent open
# route states**, and one query returns them without error. The mirror-image mistake is one
# reversed arrow away and fails loudly - ``Route.current_state = model.Property(...)`` raises
# ``FDError: Found non-unique values`` naming the offending relation and printing the two
# conflicting hashes. Note for the talk track: it fails at the **first evaluation** of the
# relation, after 13-19 seconds of engine work, not at define time. Saying "define time" on stage
# would be a factual error the audience can check on screen.
#
# One honest limitation, stated because the credibility of the limitations list matters: RAI
# cannot *express* "this route may have many concurrent open states" as a positive assertion.
# ``SD/std/constraints.py`` offers ``unique``, ``exclusive``, ``anyof`` and ``oneof`` and nothing
# else - there is no minimum-cardinality or negative-constraint vocabulary. The property is proved
# by a query returning ``open_states > 1``, which is what HT-18 asks for, not by a declaration.
#
# ``Schedule`` is identity-only, deliberately. SS-02 ``schedule_key_readable`` is tempting to hang
# on it and is per-*observation* lineage that can legitimately differ across snapshots for the
# same key, so a ``Property`` on ``Schedule`` would ``FDError``. It lives on ``RouteState`` and on
# ``ScheduleObservation`` instead.




# --- Schedule (SS-01) - identity only ---------------------------------------------

Schedule = model.Concept("Schedule", identify_by={"schedule_key": String})

model.define(Schedule.new(schedule_key=MI_SCHEDULE_CANONICAL_OBSERVATION.schedule_key))
model.define(Schedule.new(schedule_key=MI_ROUTE_STATE.schedule_key))

# --- Route (DV-12) - carrier-agnostic and directional ------------------------------

Route = model.Concept("Route", identify_by={"route_id": String})

_route_scalars = scalar_properties(Route, SCHEMA_MI_ROUTE, exclude=("route_id",))
model.define(Route.new(route_id=MI_ROUTE.route_id))
bind_scalars(Route, MI_ROUTE, {"route_id": MI_ROUTE.route_id}, _route_scalars)

# Two same-type slots, so two separately role-labelled Properties rather than one two-slot
# Relationship. With a single Relationship, ``define(...)`` silently binds both slots to
# whichever column is listed first, collapsing origin and destination into the same entity.
Route.origin_airport = model.Property(f"{Route:route} starts at {Airport:origin_airport}")
Route.destination_airport = model.Property(
    f"{Route:route} ends at {Airport:destination_airport}"
)
model.define(
    Route.lookup(route_id=MI_ROUTE.route_id).origin_airport(
        Airport.lookup(airport_id=MI_ROUTE.origin_airport_id)
    )
).where(MI_ROUTE.origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    Route.lookup(route_id=MI_ROUTE.route_id).destination_airport(
        Airport.lookup(airport_id=MI_ROUTE.destination_airport_id)
    )
).where(MI_ROUTE.destination_airport_resolution_status == RESOLUTION_EXACT)

# --- RouteState (DV-13) - the multi-open case -------------------------------------

RouteState = model.Concept("RouteState", identify_by={"route_state_key": String})

_route_state_scalars = scalar_properties(
    RouteState, SCHEMA_MI_ROUTE_STATE, exclude=("route_state_key",)
)
model.define(RouteState.new(route_state_key=MI_ROUTE_STATE.route_state_key))
bind_scalars(
    RouteState,
    MI_ROUTE_STATE,
    {"route_state_key": MI_ROUTE_STATE.route_state_key},
    _route_state_scalars,
)

# The FD points from the state to its parents, which is the functional direction. Each state has
# exactly one route and one schedule; a route has as many concurrent states as the source says.
RouteState.route = model.Property(f"{RouteState:state} covers {Route:route}")
RouteState.schedule = model.Property(f"{RouteState:state} versions {Schedule:schedule}")

model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).route(
        Route.lookup(route_id=MI_ROUTE_STATE.route_id)
    )
)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).schedule(
        Schedule.lookup(schedule_key=MI_ROUTE_STATE.schedule_key)
    )
)

# The Neo4j ``HAS`` edge, recovered exactly. An ``.alt()`` reading refers to the *same*
# underlying relationship fields under a different name, so it adds a name and never an inverse
# FD. This is the line that makes multi-open free.
Route.states = RouteState.route.alt(f"{Route:route} has state {RouteState:state}")
Schedule.states = RouteState.schedule.alt(
    f"{Schedule:schedule} has version {RouteState:state}"
)

# DELIBERATELY ABSENT, and this comment must survive every refactor:
#   there is no ``unique(...)`` over the Route slot of ``Route.states``, and no
#   ``Route.current_state`` Property. SOURCE_CONTRACT.md: the one-open-per-route constraint is
#   *prohibited*. See constraints.py, where the absence is recorded next to the assertions that
#   are present.

# --- Carrier roles: two Properties, never one generic ``airline`` -----------------
#
# ATTRIBUTE_AUTHORITY.md: "SS-04 and SS-05 are separate carrier roles. No generic airline owner
# exists." The ``carrier_role`` query parameter selects which Property a query traverses, and a
# missing role is a clarification state at the API boundary (P0-09.1), never a default.
#
# Only an EXACT cardinality-one resolution creates the link. An ambiguous or unresolved carrier
# code cannot produce an airline-level market at all, and the raw code stays bound as a string so
# a failed resolution still shows the code rather than vanishing.

RouteState.marketing_airline = model.Property(
    f"{RouteState:state} marketed by {Airline:marketing_airline}"
)
RouteState.operating_airline = model.Property(
    f"{RouteState:state} operated by {Airline:operating_airline}"
)
RouteState.codeshare_airline = model.Property(
    f"{RouteState:state} codeshared with {Airline:codeshare_airline}"
)

model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).marketing_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.marketing_airline_id)
    )
).where(MI_ROUTE_STATE.marketing_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).operating_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.operating_airline_id)
    )
).where(MI_ROUTE_STATE.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).codeshare_airline(
        Airline.lookup(airline_id=MI_ROUTE_STATE.codeshare_airline_id)
    )
).where(MI_ROUTE_STATE.codeshare_airline_resolution_status == RESOLUTION_EXACT)

Airline.commercializes = RouteState.marketing_airline.alt(
    f"{Airline:marketing_airline} commercializes {RouteState:state}"
)
Airline.operates = RouteState.operating_airline.alt(
    f"{Airline:operating_airline} operates {RouteState:state}"
)

RouteState.origin_airport = model.Property(
    f"{RouteState:state} departs {Airport:origin_airport}"
)
RouteState.destination_airport = model.Property(
    f"{RouteState:state} arrives {Airport:destination_airport}"
)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).origin_airport(
        Airport.lookup(airport_id=MI_ROUTE_STATE.origin_airport_id)
    )
).where(MI_ROUTE_STATE.origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    RouteState.lookup(route_state_key=MI_ROUTE_STATE.route_state_key).destination_airport(
        Airport.lookup(airport_id=MI_ROUTE_STATE.destination_airport_id)
    )
).where(MI_ROUTE_STATE.destination_airport_resolution_status == RESOLUTION_EXACT)

# --- RouteStateSnapshotLineage ----------------------------------------------------
#
# Many contributing snapshots coalesce into one route state, so this is an association concept
# with its own identity rather than a property. Grain verified live: 60,076 rows, 60,076 distinct
# (route_state_key, publish_date, normalized_row_hash) tuples.

RouteStateSnapshotLineage = model.Concept(
    "RouteStateSnapshotLineage",
    identify_by={"route_state": RouteState, "publish_date": Date, "row_hash": String},
)

_rs_lineage_scalars = scalar_properties(
    RouteStateSnapshotLineage,
    SCHEMA_MI_ROUTE_STATE_LINEAGE,
    exclude=("route_state_key", "publish_date", "normalized_row_hash"),
)


def _rs_lineage_key() -> dict:
    return {
        "route_state": RouteState.lookup(
            route_state_key=MI_ROUTE_STATE_LINEAGE.route_state_key
        ),
        "publish_date": MI_ROUTE_STATE_LINEAGE.publish_date,
        "row_hash": MI_ROUTE_STATE_LINEAGE.normalized_row_hash,
    }


model.define(RouteStateSnapshotLineage.new(**_rs_lineage_key()))
bind_scalars(
    RouteStateSnapshotLineage,
    MI_ROUTE_STATE_LINEAGE,
    _rs_lineage_key(),
    _rs_lineage_scalars,
)

RouteState.lineage = model.Relationship(
    f"{RouteState:state} was contributed by {RouteStateSnapshotLineage:lineage}"
)
model.define(RouteState.lineage(RouteStateSnapshotLineage)).where(
    RouteStateSnapshotLineage.route_state == RouteState
)

# --- ScheduleObservation (SS-01, SS-03) -------------------------------------------
#
# The canonical per-snapshot observation with the watched SS-04..SS-38 payload. Grain verified
# live: 69,998 rows, 69,998 distinct (schedule_key, publish_date). This is the concept Q05
# compares across adjacent eligible snapshot dates.

ScheduleObservation = model.Concept(
    "ScheduleObservation", identify_by={"schedule": Schedule, "publish_date": Date}
)

_observation_scalars = scalar_properties(
    ScheduleObservation,
    SCHEMA_MI_SCHEDULE_CANONICAL_OBSERVATION,
    exclude=("schedule_key", "publish_date"),
)


def _observation_key() -> dict:
    return {
        "schedule": Schedule.lookup(
            schedule_key=MI_SCHEDULE_CANONICAL_OBSERVATION.schedule_key
        ),
        "publish_date": MI_SCHEDULE_CANONICAL_OBSERVATION.publish_date,
    }


model.define(ScheduleObservation.new(**_observation_key()))
bind_scalars(
    ScheduleObservation,
    MI_SCHEDULE_CANONICAL_OBSERVATION,
    _observation_key(),
    _observation_scalars,
)

Schedule.observations = model.Relationship(
    f"{Schedule:schedule} was observed as {ScheduleObservation:observation}"
)
model.define(Schedule.observations(ScheduleObservation)).where(
    ScheduleObservation.schedule == Schedule
)

# ROUTE_ID is non-null on 69,993 of 69,998 observations; the five without one keep their identity
# and simply carry no route fact, which is the left-preserving behaviour P0-12.3 requires.
ScheduleObservation.route = model.Property(
    f"{ScheduleObservation:observation} covers {Route:route}"
)
model.define(
    ScheduleObservation.lookup(**_observation_key()).route(
        Route.lookup(route_id=MI_SCHEDULE_CANONICAL_OBSERVATION.route_id)
    )
)

ScheduleObservation.snapshot = model.Property(
    f"{ScheduleObservation:observation} was published on {SnapshotDate:snapshot}"
)
model.define(
    ScheduleObservation.lookup(**_observation_key()).snapshot(
        SnapshotDate.lookup(
            expected_publish_date=MI_SCHEDULE_CANONICAL_OBSERVATION.publish_date
        )
    )
)

# --- ScheduleComparison (DV-34) ---------------------------------------------------
#
# A Concept and not a per-invocation parameter, because Q05 must emit ``comparison_date``,
# ``previous_knowledge_date`` and ``crosses_snapshot_gap`` per comparison, and those are facts
# derived from the eligible ``SnapshotDate`` sequence rather than inputs supplied by the caller.
# Seven comparisons exist in the fixture.

ScheduleComparison = model.Concept("ScheduleComparison", identify_by={"comparison_id": String})

_comparison_scalars = scalar_properties(
    ScheduleComparison, SCHEMA_MI_SCHEDULE_COMPARISON, exclude=("comparison_id",)
)
model.define(ScheduleComparison.new(comparison_id=MI_SCHEDULE_COMPARISON.comparison_id))
bind_scalars(
    ScheduleComparison,
    MI_SCHEDULE_COMPARISON,
    {"comparison_id": MI_SCHEDULE_COMPARISON.comparison_id},
    _comparison_scalars,
)

ScheduleComparison.comparison_snapshot = model.Property(
    f"{ScheduleComparison:comparison} compares {SnapshotDate:comparison_snapshot}"
)
ScheduleComparison.previous_snapshot = model.Property(
    f"{ScheduleComparison:comparison} against {SnapshotDate:previous_snapshot}"
)
model.define(
    ScheduleComparison.lookup(
        comparison_id=MI_SCHEDULE_COMPARISON.comparison_id
    ).comparison_snapshot(
        SnapshotDate.lookup(expected_publish_date=MI_SCHEDULE_COMPARISON.comparison_date)
    )
)
model.define(
    ScheduleComparison.lookup(
        comparison_id=MI_SCHEDULE_COMPARISON.comparison_id
    ).previous_snapshot(
        SnapshotDate.lookup(
            expected_publish_date=MI_SCHEDULE_COMPARISON.previous_knowledge_date
        )
    )
)

# --- ScheduleExactChange ----------------------------------------------------------
#
# Exact presence-and-content facts. They stand on their own and are never consumed or replaced
# by the conservative amendment evidence below - NEO4J_PARITY_MATRIX.md lists "a candidate key
# shift is an exact schedule amendment" as a prohibited statement.
#
# Identity is the full four-tuple. FIELD_NAME is 100% non-null across all 12,040 rows (measured;
# a nullable identity component would silently drop the row - PROBE E3f took 48,000 rows down to
# 1 that way), and the tuple is unique.

ScheduleExactChange = model.Concept(
    "ScheduleExactChange",
    identify_by={
        "comparison": ScheduleComparison,
        "schedule_key": String,
        "change_kind": String,
        "field_name": String,
    },
)

_exact_change_scalars = scalar_properties(
    ScheduleExactChange,
    SCHEMA_MI_SCHEDULE_EXACT_CHANGE,
    exclude=("comparison_id", "schedule_key", "change_kind", "field_name"),
)


def _exact_change_key() -> dict:
    return {
        "comparison": ScheduleComparison.lookup(
            comparison_id=MI_SCHEDULE_EXACT_CHANGE.comparison_id
        ),
        "schedule_key": MI_SCHEDULE_EXACT_CHANGE.schedule_key,
        "change_kind": MI_SCHEDULE_EXACT_CHANGE.change_kind,
        "field_name": MI_SCHEDULE_EXACT_CHANGE.field_name,
    }


model.define(ScheduleExactChange.new(**_exact_change_key()))
bind_scalars(
    ScheduleExactChange,
    MI_SCHEDULE_EXACT_CHANGE,
    _exact_change_key(),
    _exact_change_scalars,
)

ScheduleExactChange.schedule = model.Property(
    f"{ScheduleExactChange:change} changed {Schedule:schedule}"
)
model.define(
    ScheduleExactChange.lookup(**_exact_change_key()).schedule(
        Schedule.lookup(schedule_key=MI_SCHEDULE_EXACT_CHANGE.schedule_key)
    )
)

# --- Amendment evidence (DV-35, DV-36, DV-37) -------------------------------------
#
# Kept structurally separate from the exact changes. A key-shift pair is reported as
# ``CANDIDATE_UNIQUE`` with ``exactness = CANDIDATE``, never promoted to a modification; where
# one removal is compatible with two additions the answer is an ambiguous group plus its members
# at LOW confidence with no pair chosen. Picking a winner by any tie-break is wrong.
#
# ``AMENDMENT_GROUP_ID`` is non-null on only 3 of 12,029 member rows (unpaired evidence carries
# none, per D-0020 A6), so the member identity is its own id column and the group link is an
# optional Property.

ScheduleAmendmentSide = model.Concept(
    "ScheduleAmendmentSide",
    identify_by={"comparison": ScheduleComparison, "schedule_key": String, "side": String},
)

_amendment_side_scalars = scalar_properties(
    ScheduleAmendmentSide,
    SCHEMA_MI_SCHEDULE_AMENDMENT_SIDE,
    exclude=("comparison_id", "schedule_key", "side"),
)


def _amendment_side_key() -> dict:
    return {
        "comparison": ScheduleComparison.lookup(
            comparison_id=MI_SCHEDULE_AMENDMENT_SIDE.comparison_id
        ),
        "schedule_key": MI_SCHEDULE_AMENDMENT_SIDE.schedule_key,
        "side": MI_SCHEDULE_AMENDMENT_SIDE.side,
    }


model.define(ScheduleAmendmentSide.new(**_amendment_side_key()))
bind_scalars(
    ScheduleAmendmentSide,
    MI_SCHEDULE_AMENDMENT_SIDE,
    _amendment_side_key(),
    _amendment_side_scalars,
)

ScheduleAmendmentCandidate = model.Concept(
    "ScheduleAmendmentCandidate", identify_by={"candidate_id": String}
)
_amendment_candidate_scalars = scalar_properties(
    ScheduleAmendmentCandidate,
    SCHEMA_MI_SCHEDULE_AMENDMENT_CANDIDATE,
    exclude=("amendment_candidate_id",),
)
model.define(
    ScheduleAmendmentCandidate.new(
        candidate_id=MI_SCHEDULE_AMENDMENT_CANDIDATE.amendment_candidate_id
    )
)
bind_scalars(
    ScheduleAmendmentCandidate,
    MI_SCHEDULE_AMENDMENT_CANDIDATE,
    {"candidate_id": MI_SCHEDULE_AMENDMENT_CANDIDATE.amendment_candidate_id},
    _amendment_candidate_scalars,
)

ScheduleAmendmentGroup = model.Concept(
    "ScheduleAmendmentGroup", identify_by={"group_id": String}
)
_amendment_group_scalars = scalar_properties(
    ScheduleAmendmentGroup,
    SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP,
    exclude=("amendment_group_id",),
)
model.define(
    ScheduleAmendmentGroup.new(group_id=MI_SCHEDULE_AMENDMENT_GROUP.amendment_group_id)
)
bind_scalars(
    ScheduleAmendmentGroup,
    MI_SCHEDULE_AMENDMENT_GROUP,
    {"group_id": MI_SCHEDULE_AMENDMENT_GROUP.amendment_group_id},
    _amendment_group_scalars,
)

ScheduleAmendmentGroupMember = model.Concept(
    "ScheduleAmendmentGroupMember", identify_by={"member_id": String}
)
_amendment_member_scalars = scalar_properties(
    ScheduleAmendmentGroupMember,
    SCHEMA_MI_SCHEDULE_AMENDMENT_GROUP_MEMBER,
    exclude=("amendment_group_member_id",),
)
model.define(
    ScheduleAmendmentGroupMember.new(
        member_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id
    )
)
bind_scalars(
    ScheduleAmendmentGroupMember,
    MI_SCHEDULE_AMENDMENT_GROUP_MEMBER,
    {"member_id": MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id},
    _amendment_member_scalars,
)

ScheduleAmendmentGroupMember.group = model.Property(
    f"{ScheduleAmendmentGroupMember:member} belongs to {ScheduleAmendmentGroup:group}"
)
model.define(
    ScheduleAmendmentGroupMember.lookup(
        member_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_member_id
    ).group(
        ScheduleAmendmentGroup.lookup(
            group_id=MI_SCHEDULE_AMENDMENT_GROUP_MEMBER.amendment_group_id
        )
    )
)
ScheduleAmendmentGroup.members = model.Relationship(
    f"{ScheduleAmendmentGroup:group} has member {ScheduleAmendmentGroupMember:member}"
)
model.define(ScheduleAmendmentGroup.members(ScheduleAmendmentGroupMember)).where(
    ScheduleAmendmentGroupMember.group == ScheduleAmendmentGroup
)


# ================================================================================================
# core_flight.py
# ================================================================================================
# core_flight.py - the plan side, the actual side, and the optional bridge between them.
#
# Passenger flights and aircraft flights are **separate** and stay separate (BRIEF.md
# non-negotiable). Fulfillment is optional and asymmetric, and that asymmetry is the single
# cleanest demonstration in the whole model of what a directed ``Property`` plus an ``.alt()``
# inverse buys you:
#
# * ``AircraftFlight.fulfils`` is a ``Property``. The FD ``leg -> plan`` is enforced: one actual
#   leg fulfils at most one planned service.
# * ``PassengerFlight.fulfilled_by`` is the ``.alt()`` inverse over the *same* fields, so it
#   carries no FD. The stopover case - one planned passenger service fulfilled by several actual
#   legs - loads without error.
#
# A property-graph edge cannot express that pair without an out-of-band constraint.
#
# ``ExactFulfillment`` stays a separate association concept even though ``fulfils`` exists,
# because P0-10.6 requires candidates to be stored separately from confirmed fulfillment and the
# association carries DV-39, the evidence and the sanity-check outcome. ``fulfils`` is derived
# from ``ExactFulfillment`` **only**; ``FulfillmentCandidate`` never feeds it. That makes the
# exact/heuristic separation structural rather than a convention.
#
# Two code systems that must not be joined to each other: actual endpoints are ``SYN-AP-*``
# internal ids resolved against AP-01, planned endpoints are public IATA labels resolved against
# AP-04. Joining actual legs on IATA silently returns nothing.




# --- PassengerFlight (DV-20) - the plan side --------------------------------------

PassengerFlight = model.Concept(
    "PassengerFlight", identify_by={"passenger_flight_key": String}
)

_passenger_scalars = scalar_properties(
    PassengerFlight,
    SCHEMA_MI_PASSENGER_FLIGHT_CANONICAL,
    exclude=("passenger_flight_key",),
)
model.define(
    PassengerFlight.new(
        passenger_flight_key=MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key
    )
)
bind_scalars(
    PassengerFlight,
    MI_PASSENGER_FLIGHT_CANONICAL,
    {"passenger_flight_key": MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key},
    _passenger_scalars,
)

# PH-02 ``schedule_key`` is bound as a ``Property`` from the canonical row, which by
# construction carries the DV-21 precedence-winning lineage observation's value. PROBE G-05
# passed only *vacuously* against the raw lineage - the one coalescing DV-20 key that absorbs
# two lineage rows has NULL PH-02 on both - so relying on that pass would have been relying on a
# fixture accident. Binding from the winner makes the functional dependency true by
# construction, which is what P0-10.3 requires anyway. Non-null on 7,951 of 19,446 canonical
# rows after the D-0023 enrichment; it was 1 of 19,996 before, which is why the binding had to
# be true by construction rather than by fixture accident.
PassengerFlight.schedule = model.Property(
    f"{PassengerFlight:plan} realises {Schedule:schedule}"
)
model.define(
    PassengerFlight.lookup(
        passenger_flight_key=MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key
    ).schedule(Schedule.lookup(schedule_key=MI_PASSENGER_FLIGHT_CANONICAL.schedule_key))
)

PassengerFlight.marketing_airline = model.Property(
    f"{PassengerFlight:plan} marketed by {Airline:marketing_airline}"
)
PassengerFlight.operating_airline = model.Property(
    f"{PassengerFlight:plan} operated by {Airline:operating_airline}"
)
PassengerFlight.planned_origin_airport = model.Property(
    f"{PassengerFlight:plan} planned from {Airport:planned_origin_airport}"
)
PassengerFlight.planned_destination_airport = model.Property(
    f"{PassengerFlight:plan} planned to {Airport:planned_destination_airport}"
)


def _plan_key() -> dict:
    return {"passenger_flight_key": MI_PASSENGER_FLIGHT_CANONICAL.passenger_flight_key}


model.define(
    PassengerFlight.lookup(**_plan_key()).marketing_airline(
        Airline.lookup(airline_id=MI_PASSENGER_FLIGHT_CANONICAL.marketing_airline_id)
    )
).where(MI_PASSENGER_FLIGHT_CANONICAL.marketing_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    PassengerFlight.lookup(**_plan_key()).operating_airline(
        Airline.lookup(airline_id=MI_PASSENGER_FLIGHT_CANONICAL.operating_airline_id)
    )
).where(MI_PASSENGER_FLIGHT_CANONICAL.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    PassengerFlight.lookup(**_plan_key()).planned_origin_airport(
        Airport.lookup(airport_id=MI_PASSENGER_FLIGHT_CANONICAL.planned_origin_airport_id)
    )
).where(
    MI_PASSENGER_FLIGHT_CANONICAL.planned_origin_airport_resolution_status
    == RESOLUTION_EXACT
)
model.define(
    PassengerFlight.lookup(**_plan_key()).planned_destination_airport(
        Airport.lookup(
            airport_id=MI_PASSENGER_FLIGHT_CANONICAL.planned_destination_airport_id
        )
    )
).where(
    MI_PASSENGER_FLIGHT_CANONICAL.planned_destination_airport_resolution_status
    == RESOLUTION_EXACT
)

# --- PassengerSourceLineage -------------------------------------------------------
#
# Historical and forward lineage are BOTH retained (SOURCE_CONTRACT.md), which is why this is an
# association concept rather than a set of columns on the flight. ``IS_SELECTED_OBSERVATION``,
# ``SOURCE_PRECEDENCE_RANK`` and ``SELECTION_RANK`` are carried so the union precedence is
# auditable rather than implicit. Grain verified live: 19,998 rows, 19,998 distinct tuples.

PassengerSourceLineage = model.Concept(
    "PassengerSourceLineage",
    identify_by={
        "passenger_flight": PassengerFlight,
        "source_system": String,
        "source_row_token": String,
    },
)

_lineage_scalars = scalar_properties(
    PassengerSourceLineage,
    SCHEMA_MI_PASSENGER_SOURCE_LINEAGE,
    exclude=("passenger_flight_key", "source_system", "source_row_token"),
)


def _lineage_key() -> dict:
    return {
        "passenger_flight": PassengerFlight.lookup(
            passenger_flight_key=MI_PASSENGER_SOURCE_LINEAGE.passenger_flight_key
        ),
        "source_system": MI_PASSENGER_SOURCE_LINEAGE.source_system,
        "source_row_token": MI_PASSENGER_SOURCE_LINEAGE.source_row_token,
    }


model.define(PassengerSourceLineage.new(**_lineage_key()))
bind_scalars(
    PassengerSourceLineage,
    MI_PASSENGER_SOURCE_LINEAGE,
    _lineage_key(),
    _lineage_scalars,
)

PassengerFlight.lineage = model.Relationship(
    f"{PassengerFlight:plan} was observed as {PassengerSourceLineage:lineage}"
)
model.define(PassengerFlight.lineage(PassengerSourceLineage)).where(
    PassengerSourceLineage.passenger_flight == PassengerFlight
)

# --- PassengerPlannedLeg ----------------------------------------------------------
#
# The ordered planned station sequence. A single planned service with intermediate stops has
# several legs, which is what makes the stopover fulfillment case real.
#
# ``LEG_INDEX`` is ``NUMBER(9,0)`` and is declared ``Number.size(18, 0)``, not ``Integer`` and
# not ``Number.size(9, 0)``. The SDK buckets integer precision by bit width, so every
# ``NUMBER(p,0)`` with ``p <= 18`` discovers as ``Decimal(18,0)``; declaring the column's own
# precision instead relies on an undocumented leniency, and declaring ``Integer``
# (``Number.size(38, 0)``) would be a silent all-NaN column. See ``_regen_sources.derive_type``
# for the ``NUMBER(19,0)`` case where getting this wrong cost 600 values.

PassengerPlannedLeg = model.Concept(
    "PassengerPlannedLeg",
    identify_by={"passenger_flight": PassengerFlight, "leg_index": Number.size(18, 0)},
)

_planned_leg_scalars = scalar_properties(
    PassengerPlannedLeg,
    SCHEMA_MI_PASSENGER_PLANNED_LEG,
    exclude=("passenger_flight_key", "leg_index"),
)


def _planned_leg_key() -> dict:
    return {
        "passenger_flight": PassengerFlight.lookup(
            passenger_flight_key=MI_PASSENGER_PLANNED_LEG.passenger_flight_key
        ),
        "leg_index": MI_PASSENGER_PLANNED_LEG.leg_index,
    }


model.define(PassengerPlannedLeg.new(**_planned_leg_key()))
bind_scalars(
    PassengerPlannedLeg,
    MI_PASSENGER_PLANNED_LEG,
    _planned_leg_key(),
    _planned_leg_scalars,
)

PassengerFlight.planned_legs = model.Relationship(
    f"{PassengerFlight:plan} has planned leg {PassengerPlannedLeg:leg}"
)
model.define(PassengerFlight.planned_legs(PassengerPlannedLeg)).where(
    PassengerPlannedLeg.passenger_flight == PassengerFlight
)

# --- Invalid and quarantined passenger observations -------------------------------
#
# Retained with a deterministic identity plus a reason, never dropped. An observation that
# cannot form a DV-20 key is a fact about the source, not an absence.

InvalidPassengerObservation = model.Concept(
    "InvalidPassengerObservation",
    identify_by={"source_system": String, "stable_source_row_id": Integer},
)
_invalid_scalars = scalar_properties(
    InvalidPassengerObservation,
    SCHEMA_MI_PASSENGER_FLIGHT_INVALID,
    exclude=("source_system", "stable_source_row_id"),
)
model.define(
    InvalidPassengerObservation.new(
        source_system=MI_PASSENGER_FLIGHT_INVALID.source_system,
        stable_source_row_id=MI_PASSENGER_FLIGHT_INVALID.stable_source_row_id,
    )
)
bind_scalars(
    InvalidPassengerObservation,
    MI_PASSENGER_FLIGHT_INVALID,
    {
        "source_system": MI_PASSENGER_FLIGHT_INVALID.source_system,
        "stable_source_row_id": MI_PASSENGER_FLIGHT_INVALID.stable_source_row_id,
    },
    _invalid_scalars,
)

PassengerSourceQuarantine = model.Concept(
    "PassengerSourceQuarantine", identify_by={"quarantine_id": String}
)
_passenger_quarantine_scalars = scalar_properties(
    PassengerSourceQuarantine,
    SCHEMA_MI_PASSENGER_SOURCE_QUARANTINE,
    exclude=("quarantine_id",),
)
model.define(
    PassengerSourceQuarantine.new(
        quarantine_id=MI_PASSENGER_SOURCE_QUARANTINE.quarantine_id
    )
)
bind_scalars(
    PassengerSourceQuarantine,
    MI_PASSENGER_SOURCE_QUARANTINE,
    {"quarantine_id": MI_PASSENGER_SOURCE_QUARANTINE.quarantine_id},
    _passenger_quarantine_scalars,
)

# --- AircraftFlight (AF-01) - the actual side -------------------------------------

AircraftFlight = model.Concept("AircraftFlight", identify_by={"flight_id": Integer})

_flight_scalars = scalar_properties(
    AircraftFlight, SCHEMA_MI_AIRCRAFT_FLIGHT, exclude=("flight_id",)
)
model.define(AircraftFlight.new(flight_id=MI_AIRCRAFT_FLIGHT.flight_id))
bind_scalars(
    AircraftFlight,
    MI_AIRCRAFT_FLIGHT,
    {"flight_id": MI_AIRCRAFT_FLIGHT.flight_id},
    _flight_scalars,
)


def _leg_key() -> dict:
    return {"flight_id": MI_AIRCRAFT_FLIGHT.flight_id}


# PROBE G-06: ``AircraftFlight.aircraft`` is functional (zero violating flight ids) but the
# inverse is 1..13 flights per aircraft, so the inverse must be multi-valued. Easy to get
# backwards, and a ``Property`` on the inverse would FDError on the first aircraft with two legs.
AircraftFlight.aircraft = model.Property(f"{AircraftFlight:leg} was flown by {Aircraft:aircraft}")
model.define(
    AircraftFlight.lookup(**_leg_key()).aircraft(
        Aircraft.lookup(id=MI_AIRCRAFT_FLIGHT.aircraft_id)
    )
)
Aircraft.actual_flights = AircraftFlight.aircraft.alt(
    f"{Aircraft:aircraft} flew {AircraftFlight:leg}"
)

# Two same-type slots again, so two role-labelled Properties. AF-09 ``actual`` arrival is
# DV-45 and is the continuity endpoint; AF-10 ``diverted`` never repairs it.
AircraftFlight.actual_origin = model.Property(
    f"{AircraftFlight:leg} started at {Airport:actual_origin}"
)
AircraftFlight.actual_destination = model.Property(
    f"{AircraftFlight:leg} ended at {Airport:actual_destination}"
)
AircraftFlight.diverted_airport = model.Property(
    f"{AircraftFlight:leg} diverted to {Airport:diverted_airport}"
)
model.define(
    AircraftFlight.lookup(**_leg_key()).actual_origin(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.actual_origin_airport_id)
    )
).where(MI_AIRCRAFT_FLIGHT.actual_origin_airport_resolution_status == RESOLUTION_EXACT)
model.define(
    AircraftFlight.lookup(**_leg_key()).actual_destination(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.actual_destination_airport_id)
    )
).where(
    MI_AIRCRAFT_FLIGHT.actual_destination_airport_resolution_status == RESOLUTION_EXACT
)
model.define(
    AircraftFlight.lookup(**_leg_key()).diverted_airport(
        Airport.lookup(airport_id=MI_AIRCRAFT_FLIGHT.diverted_airport_id)
    )
).where(MI_AIRCRAFT_FLIGHT.diverted_airport_resolution_status == RESOLUTION_EXACT)

AircraftFlight.operating_airline = model.Property(
    f"{AircraftFlight:leg} was operated by {Airline:operating_airline}"
)
AircraftFlight.marketing_airline = model.Property(
    f"{AircraftFlight:leg} was marketed by {Airline:marketing_airline}"
)
model.define(
    AircraftFlight.lookup(**_leg_key()).operating_airline(
        Airline.lookup(airline_id=MI_AIRCRAFT_FLIGHT.operating_airline_id)
    )
).where(MI_AIRCRAFT_FLIGHT.operating_airline_resolution_status == RESOLUTION_EXACT)
model.define(
    AircraftFlight.lookup(**_leg_key()).marketing_airline(
        Airline.lookup(airline_id=MI_AIRCRAFT_FLIGHT.marketing_airline_id)
    )
).where(MI_AIRCRAFT_FLIGHT.marketing_airline_resolution_status == RESOLUTION_EXACT)

# The raw AF-20 self-reference, chained through a lookup on both ends so the target must already
# exist. PROBE G-06 found exactly one dangling ``NEXT_FLIGHT_ID`` in the fixture - the
# ``MISSING_TARGET`` anomaly - and this binding silently produces no fact for it, which is the
# intended behaviour. ``RotationLinkValidation`` is the thing that surfaces it.
AircraftFlight.next_flight_raw = model.Property(
    f"{AircraftFlight:leg} points to next {AircraftFlight:next_leg_raw}"
)
model.define(
    AircraftFlight.lookup(flight_id=MI_AIRCRAFT_FLIGHT.flight_id).next_flight_raw(
        AircraftFlight.lookup(flight_id=MI_AIRCRAFT_FLIGHT.next_flight_id)
    )
)

# --- RotationLinkValidation (DV-24, DV-25) ----------------------------------------
#
# One row per candidate edge, plus a terminal row per leg whose target token is the literal
# ``NO_TARGET``. Grain verified live: 3,900 rows, 3,900 distinct (flight_id, target_token), of
# which 2 are ``ACCEPTED``, 3 ``EXCLUDED``, 9 ``REJECTED`` and 3,886 ``TERMINAL_NO_TARGET``.

RotationLinkValidation = model.Concept(
    "RotationLinkValidation",
    identify_by={"flight": AircraftFlight, "target_token": String},
)

_rotation_scalars = scalar_properties(
    RotationLinkValidation,
    SCHEMA_MI_ROTATION_LINK_VALIDATION,
    exclude=("flight_id", "target_token"),
)


def _rotation_key() -> dict:
    return {
        "flight": AircraftFlight.lookup(flight_id=MI_ROTATION_LINK_VALIDATION.flight_id),
        "target_token": MI_ROTATION_LINK_VALIDATION.target_token,
    }


model.define(RotationLinkValidation.new(**_rotation_key()))
bind_scalars(
    RotationLinkValidation,
    MI_ROTATION_LINK_VALIDATION,
    _rotation_key(),
    _rotation_scalars,
)

RotationLinkValidation.target_flight = model.Property(
    f"{RotationLinkValidation:validation} validates target {AircraftFlight:target_flight}"
)
model.define(
    RotationLinkValidation.lookup(**_rotation_key()).target_flight(
        AircraftFlight.lookup(flight_id=MI_ROTATION_LINK_VALIDATION.target_flight_id)
    )
)

AircraftFlight.rotation_validations = model.Relationship(
    f"{AircraftFlight:leg} was validated by {RotationLinkValidation:validation}"
)
model.define(AircraftFlight.rotation_validations(RotationLinkValidation)).where(
    RotationLinkValidation.flight == AircraftFlight
)

# --- Fulfillment: exact, candidate, and ambiguous ---------------------------------

ExactFulfillment = model.Concept(
    "ExactFulfillment", identify_by={"exact_fulfillment_id": String}
)
_exact_fulfillment_scalars = scalar_properties(
    ExactFulfillment, SCHEMA_MI_FULFILLMENT_EXACT, exclude=("exact_fulfillment_id",)
)
model.define(
    ExactFulfillment.new(exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id)
)
bind_scalars(
    ExactFulfillment,
    MI_FULFILLMENT_EXACT,
    {"exact_fulfillment_id": MI_FULFILLMENT_EXACT.exact_fulfillment_id},
    _exact_fulfillment_scalars,
)

ExactFulfillment.actual_flight = model.Property(
    f"{ExactFulfillment:fulfillment} confirms leg {AircraftFlight:actual_flight}"
)
ExactFulfillment.passenger_flight = model.Property(
    f"{ExactFulfillment:fulfillment} confirms plan {PassengerFlight:passenger_flight}"
)
model.define(
    ExactFulfillment.lookup(
        exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id
    ).actual_flight(AircraftFlight.lookup(flight_id=MI_FULFILLMENT_EXACT.actual_flight_id))
)
model.define(
    ExactFulfillment.lookup(
        exact_fulfillment_id=MI_FULFILLMENT_EXACT.exact_fulfillment_id
    ).passenger_flight(
        PassengerFlight.lookup(
            passenger_flight_key=MI_FULFILLMENT_EXACT.passenger_flight_key
        )
    )
)

FulfillmentCandidate = model.Concept(
    "FulfillmentCandidate", identify_by={"candidate_id": String}
)
_fulfillment_candidate_scalars = scalar_properties(
    FulfillmentCandidate,
    SCHEMA_MI_FULFILLMENT_CANDIDATE,
    exclude=("fulfillment_candidate_id",),
)
model.define(
    FulfillmentCandidate.new(
        candidate_id=MI_FULFILLMENT_CANDIDATE.fulfillment_candidate_id
    )
)
bind_scalars(
    FulfillmentCandidate,
    MI_FULFILLMENT_CANDIDATE,
    {"candidate_id": MI_FULFILLMENT_CANDIDATE.fulfillment_candidate_id},
    _fulfillment_candidate_scalars,
)

# D-0020 A6: unmatched actual and passenger observations live here at member grain with a NULL
# group id, because that contract row is where "unmatched observations retain a deterministic
# identity plus reason" is written. ``FULFILLMENT_GROUP_ID`` is non-null on only 3 of 23,887
# rows, so the identity is the member id and the group link is an optional Property.
FulfillmentGroupMember = model.Concept(
    "FulfillmentGroupMember", identify_by={"member_id": String}
)
_fulfillment_member_scalars = scalar_properties(
    FulfillmentGroupMember,
    SCHEMA_MI_FULFILLMENT_AMBIGUOUS_GROUP,
    exclude=("fulfillment_group_member_id",),
)
model.define(
    FulfillmentGroupMember.new(
        member_id=MI_FULFILLMENT_AMBIGUOUS_GROUP.fulfillment_group_member_id
    )
)
bind_scalars(
    FulfillmentGroupMember,
    MI_FULFILLMENT_AMBIGUOUS_GROUP,
    {"member_id": MI_FULFILLMENT_AMBIGUOUS_GROUP.fulfillment_group_member_id},
    _fulfillment_member_scalars,
)

# --- The asymmetric fulfillment link ----------------------------------------------
#
# Derived from ``ExactFulfillment`` only. ``FulfillmentCandidate`` never feeds it: that is the
# exact/heuristic separation, made structural rather than documented.

AircraftFlight.fulfils = model.Property(
    f"{AircraftFlight:leg} fulfilled {PassengerFlight:plan}"
)
model.define(AircraftFlight.fulfils(PassengerFlight)).where(
    ExactFulfillment.actual_flight == AircraftFlight,
    ExactFulfillment.passenger_flight == PassengerFlight,
)
PassengerFlight.fulfilled_by = AircraftFlight.fulfils.alt(
    f"{PassengerFlight:plan} was fulfilled by {AircraftFlight:leg}"
)


# ================================================================================================
# temporal.py
# ================================================================================================
# temporal.py - the shared temporal predicate layer. Pure; no model rules of its own.
#
# **This module is the demo's central differentiation claim.** ``NEO4J_PARITY_MATRIX.md`` sells
# "one reusable semantic model for the eight bounded workloads instead of query-local temporal
# rules". If any of the predicates below get retyped inside ``uc1.py``, ``uc2.py`` or
# ``rotation.py``, that claim stops being true, and the four questions that resolve the same
# as-of instant (Q01 at a parameter date, Q03 at 120 month ends, Q04 across the whole stream, Q08
# at each leg's AF-06) get four independent chances to put the exclusive bound on the wrong side.
#
# RAI 1.20.1 has **no temporal support at all**. A search of the whole ``semantics`` tree for
# ``valid_from``, ``bitemporal``, ``as_of``, ``effective_from`` and ``interval`` returns nothing:
# no interval type, no validity-annotated relationship, no as-of operator. Every predicate here is
# therefore a hand-written conjunction over two ``Date`` properties. That is honest parity with a
# property graph, which has none either - and it is the reason nothing in the API holds a
# "one open version per parent" assumption that would have to be relaxed for the multi-open route
# case (see ``core_schedule.py``).
#
# The functions return **tuples of conditions**, spread into ``model.where(*...)``. They are
# deliberately Python helpers and not model relationships: a materialized
# ``visible_on(assignment, Date)`` rule would range over the unbounded extension of the ``Date``
# core concept and either fail to ground or explode. The two places where the date set *is*
# bounded by an entity - Q03's ``MonthEnd`` and Q08's ``AircraftFlight`` - do get real
# materialized model rules, in ``computed_aircraft.py`` and ``computed_rotation.py``.
#
# The two interval conventions are NOT interchangeable and must never share one helper:
#
# * **knowledge / validity is half-open**: ``valid_from <= d < valid_to``.
# * **operating is inclusive at both ends**: ``effective_date <= d <= discontinue_date``.
#
# ``SEMANTIC_DECISIONS.md``: "Knowledge ``valid_to`` is excluded; source operating
# ``discontinue_date`` is included." A single generic helper applied to both would silently make
# the operating upper bound exclusive, lose the last operating day, and break nine rows of the
# frozen ``TT-BOTH-CLOCKS`` truth table while still returning a plausible answer. Hence
# :func:`visible_on` / :func:`known_on` (half-open) and :func:`operates_on` (inclusive) are
# separate functions with deliberately different names.





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


# ================================================================================================
# computed_aircraft.py
# ================================================================================================
# computed_aircraft.py - the reusable derived layer over UC1. This is where the RAI content is.
#
# Everything above this file is plumbing: identity, source binding, and two half-open ``Date``
# columns. Everything the demo actually argues about lives here.
#
# Six groups of rules:
#
# 1. **Dimension subtypes.** One physical assignment table with a ``dimension`` discriminator
#    becomes four named streams. ``identity_includes_type`` stays ``False``, so the subtype
#    instance *is* its parent entity - one assignment, viewed through its dimension. This buys two
#    things. The four independent clocks in Q01 become four visibly independent joins in the query
#    code, which is the point of the demo. And Q02 can rank status observations ``.per(Aircraft)``
#    instead of ``.per(Aircraft, dimension)``.
# 1b. **Four dimension-scoped edges off ``Aircraft`` plus three direct one-hop readings**, so the
#    supplied Neo4j edge structure is visible on the concept rather than recoverable only through a
#    subtype predicate (FIDELITY-01 A2 / A3).
# 2. **The dense ordinals** that turn "the previous assignment" and "the next qualifying
#    assignment" from a four-column lexicographic comparison into one integer comparison.
# 3. **Q04's reconciliation properties**, ``previous_definition_id`` and the three-valued
#    ``is_type_change``.
# 4. **Q03's month-end rule** - the demo's headline reusable temporal rule, where the type clock
#    and the status clock are two independent half-open joins in one rule, visibly not aligned.
# 5. **Two integrity guards** that RAI cannot declare, so it derives them and the gate asserts
#    they are empty.
#
# One thing that is deliberately *not* here: the four-value DV-33 as-of status is not a
# materialized property, because it is a function of a date and ``Date`` has an unbounded
# extension. ``DIMENSION_QUERY_STATUS`` on the row already decides the two present-row values
# (measured live: exactly ``OK`` 97,975 and ``UNKNOWN_STATE`` 4), and ``temporal.dv33_branches``
# owns the two absence values. See that function's docstring for why section 5.3's ``|`` chain
# could not be used.




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


# ================================================================================================
# computed_schedule.py
# ================================================================================================
# computed_schedule.py - the reusable derived layer over UC2.
#
# Five things, each of which would otherwise get retyped in a query module:
#
# 1. **The weekday predicate**, as a multi-valued relationship rather than a seven-branch match.
# 2. **The physical-service representative flag** (D-0007), so the codeshare de-duplication rule
#    lives in the ontology instead of in eight query functions.
# 3. **The cabin-derivation cross-check**, which proves DV-26 in RAI without moving authority for
#    it out of Snowflake.
# 4. **A route-state snapshot-gap flag**, lifted so Q05's ``crosses_snapshot_gap`` is queryable.
# 5. **The Neo4j ``SCHEDULES`` edge**, the only supplied edge that has to be derived rather than
#    loaded, from the P0-08 two-clock conjunction.
#
# Both schedule clocks stay separately queryable and their two interval conventions never merge:
# knowledge is half-open (DV-14 inclusive, DV-15 **exclusive**), operating is inclusive on both
# ends (SS-08 and SS-09 both included). The helpers that apply them are
# ``temporal.known_on`` and ``temporal.operates_on`` and they are deliberately two functions.




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


# ================================================================================================
# computed_rotation.py
# ================================================================================================
# computed_rotation.py - the accepted rotation edge, its transitive closure, and Q08 enrichment.
#
# The accepted-rotation-link relationship is one of the five things MODEL-01 owes the ontology,
# and it is the one where authoring it once matters most: the ordered traversal, the anomaly
# query, and any future path experiment must all walk an **identical** edge set, or the demo can
# be shown two different rotations for the same aircraft.
#
# Q08 is an ordinary typed self-reference, not a graph-reasoner question, and that verdict is
# evidence-based rather than a preference. Every algorithm in the graph-analysis catalogue returns
# an unordered or scalar result - reachability gives ``(source, target)``, distance gives
# ``(start, end, length)``, WCC gives ``(node, component)``, centrality gives ``(node, score)`` -
# while Q08's output is sixteen columns of which twelve are per-leg payload and one is a position
# within a path. None of those algorithms produces a position or carries edge payload, so each
# would have to be joined back to ``AircraftFlight`` anyway, which is the self-join the baseline
# already does.
#
# ``leg_order`` therefore comes from the link structure: ``1 + the number of accepted-chain
# predecessors``. Sorting the day's legs by departure time and numbering them reproduces the
# canonical answer on this fixture and is an explicit fail.
#
# PROBE U-07 settled the termination question. The 1.2.2 ``union`` + ``per(u, v).min(...)``
# recursion idiom compiles unchanged on 1.20.1 and produces a complete, correct, finite closure on
# a deliberately cyclic edge set in 3.6 seconds, with no visited set and no step bound - because
# ``min`` over the ``u == v`` base case caps every self-distance at 0 and the lattice is finite.
# There is no step-bound parameter in the 1.20.1 API and none is needed. P0-11.5 asks for a
# visited set and a finite step bound; the guard here is a different and stronger mechanism -
# cycles are excluded at the acceptance rule itself - and that difference is a note, not a risk.




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


# ================================================================================================
# constraints.py
# ================================================================================================
# constraints.py - the multiplicity gates, and one deliberate absence.
#
# **Read this before believing anything in this file is enforced.**
#
# PROBE U-04 ran a deliberately violated ``require(unique(...))`` against the live engine, with
# and without ``reasoners.logic.emit_constraints: True``. In both configurations the require
# returned normally, the following query returned normally, and the violating data was still
# there. **``require(unique(...))`` is a silent no-op in SDK 1.20.1.** The corroborating source is
# ``backends/legacy_lqp/rewrite/annotate_constraints.py``: by default all constraints are
# discharged and removed from the IR in a later pass, and even with the flag on
# ``_should_declare_constraint`` additionally requires a non-structural functional dependency, so
# a structural FD is never declared as a runtime constraint.
#
# The calls below are therefore kept as **documentation only**. They put the multiplicity gate
# from ``SOURCE_CONTRACT.md`` into the model where a reviewer sees it, next to the one that is
# deliberately absent. They must not be presented to anyone as live checks.
#
# The real enforcement is two mechanisms, both of which do work:
#
# 1. **``Property`` itself.** The compiler-enforced functional dependency on every ``Property``
#    raises ``FDError: Found non-unique values`` naming the offending relation and printing the
#    two conflicting hashes. It fires at the **first evaluation** of the relation - measured at
#    13-19 seconds of engine work - not at define time. The design brief said "define time"; that
#    is wrong and saying it on stage would be a factual error the audience can check on screen.
# 2. **Zero-count assertion queries** in ``tests/test_model.py`` and in the Phase 8 gate, for
#    every claim a ``Property`` cannot express: the sentinel-leak guard, the end-event
#    disagreement, the cabin derivation, the physical-service re-derivation, and the G-01..G-06
#    functional-dependency probes.




# --- Present, and true ------------------------------------------------------------
#
# A route state has exactly one route and one schedule; its two carrier roles are zero-or-one
# EXACT resolutions. All four are already enforced by the ``Property`` declarations in
# ``core_schedule.py``; these restate them where the contract's reader looks for them.

model.require(unique(RouteState.route[RouteState]))
model.require(unique(RouteState.schedule[RouteState]))
model.require(unique(RouteState.marketing_airline[RouteState]))
model.require(unique(RouteState.operating_airline[RouteState]))

# One actual leg fulfils at most one planned service. The *inverse* is deliberately
# unconstrained, which is what makes the stopover case load: one planned passenger service may
# be fulfilled by several actual legs.
model.require(unique(AircraftFlight.fulfils[AircraftFlight]))

# --- Deliberately absent, and this comment is the point ---------------------------
#
#   There is NO unique(...) over the Route slot of ``Route.states``.
#   There is NO ``Route.current_state`` Property.
#
# SOURCE_CONTRACT.md: the one-open-per-route constraint is *prohibited*. Route-state versioning
# partitions by schedule identity, never by route, and a route legitimately has many concurrent
# open states - 1,339 of them on ``SFO->LAX`` at knowledge date 2026-08-31, measured live.
#
# The absent constraint is as informative as the present ones, and RAI cannot state the positive
# form: ``SD/std/constraints.py`` offers ``unique``, ``exclusive``, ``anyof`` and ``oneof`` and
# has no minimum-cardinality or negative-constraint vocabulary. "This route may have many
# concurrent open states" is provable by query and not declarable. Say that plainly rather than
# implying RAI declares something a property graph cannot.


# ================================================================================================
# inventory.py
# ================================================================================================
# inventory.py - ``inspect.schema(model)`` dumped to JSON, plus the two assertions that matter.
#
# Two jobs:
#
# * **MODEL-01's exit artifact.** ``build/design/ontology_inventory.json`` is what the gate, the
#   runbook and the notebook read to describe the ontology, and it is what MODEL-02's parity test
#   diffs the standalone file against.
# * **The only defence against two silent failure modes**, both measured live by PROBE-01 and
#   neither of which raises anything:
#
#   1. ``no_any_columns`` - a mistyped column in a ``model.Table()`` ``schema=`` dict binds
#      *silently* as an ``Any``-typed relation (U-01). Strict mode does not stop it. It then
#      produces an empty or NaN result in a query three phases later. One assertion over
#      ``inspect.schema(model).tables`` catches every column typo in ``sources.py`` and costs
#      nothing.
#   2. ``per_column_non_null`` - a *wrongly declared type* yields an all-NaN column rather than a
#      ``TyperError`` (U-02). A row-count check passes happily. So the gate compares the non-null
#      count of every bound column against ``COUNT(<col>)`` in SQL.
#
# ``inspect.schema`` is also the "here is what actually registered" artifact, which is a different
# thing from "here is what I intended to build" - the second assertion exists because the two
# diverged silently in the probe run.






def default_inventory_path() -> Path:
    """Repo-relative artifact path, resolved lazily.

    Lazily because MODEL-02's standalone file has to import cleanly inside a Snowsight or
    Workspace runtime where ``__file__`` may not point anywhere useful and where there is no
    repo to write into. Nothing here touches the filesystem at import time.
    """
    return Path(__file__).resolve().parents[2] / "build" / "design" / "ontology_inventory.json"


INVENTORY_PATH = default_inventory_path()


def _rel(info: Any) -> dict[str, Any]:
    return {
        "name": info.name,
        "type_name": info.type_name,
        "reading": info.reading,
        "is_property": info.is_property,
        "is_identity": info.is_identity,
        "fields": [{"name": f.name, "type_name": f.type_name} for f in info.fields],
        "alt_readings": sorted(info.alt_readings),
    }


def build_inventory() -> dict[str, Any]:
    """Serialise ``inspect.schema(model)`` into a stable, diffable JSON structure.

    Sorted everywhere. ``inspect.schema`` guarantees deterministic *declaration* order, which
    is not the same as being stable across two differently-organised programs - the MODEL-02
    standalone file concatenates the package's modules and so declares in a different order.
    Sorting makes the parity diff compare content rather than sequence.

    Rule texts are excluded on purpose: they embed frontend object ids that differ between
    processes, so including them would make an identical model look different.
    """
    schema = inspect.schema(model)

    concepts = {
        c.name: {
            "extends": sorted(c.extends),
            "identify_by": [_rel(p) for p in c.identify_by],
            "properties": sorted((_rel(p) for p in c.properties), key=lambda d: d["name"]),
            "relationships": sorted(
                (_rel(r) for r in c.relationships), key=lambda d: (d["name"], d["reading"])
            ),
            "data_sources": sorted(c.data_sources),
        }
        for c in schema.concepts
    }

    tables = {
        t.name: {
            "columns": sorted(
                ({"name": col.name, "type_name": col.type_name} for col in t.columns),
                key=lambda d: d["name"],
            ),
            "loads": sorted(t.loads),
        }
        for t in schema.tables
    }

    bare = sorted(
        (_rel(r) for r in schema.bare_relationships), key=lambda d: (d["name"], d["reading"])
    )

    declared = {
        alias: {"object": qualified, "columns": {c: str(t) for c, t in cols.items()}}
        for alias, (_tbl, qualified, cols) in TABLE_INVENTORY.items()
    }

    return {
        "model": schema.name,
        "sdk_version": _sdk_version(),
        "concept_count": len(concepts),
        "table_count": len(tables),
        "property_count": sum(len(v["properties"]) + len(v["identify_by"]) for v in concepts.values()),
        "relationship_count": sum(len(v["relationships"]) for v in concepts.values()),
        "bare_relationship_count": len(bare),
        "define_rule_count": len(schema.defines),
        "require_rule_count": len(schema.requires),
        "declared_source_count": len(declared),
        "declared_column_count": sum(len(v["columns"]) for v in declared.values()),
        "concepts": dict(sorted(concepts.items())),
        "tables": dict(sorted(tables.items())),
        "bare_relationships": bare,
        "declared_sources": dict(sorted(declared.items())),
    }


def _sdk_version() -> str:
    try:
        import relationalai

        return getattr(relationalai, "__version__", "unknown")
    except Exception:  # pragma: no cover - version reporting must never break the dump
        return "unknown"


def assert_no_any_columns(inventory: dict[str, Any]) -> list[str]:
    """Every discovered table column must have a concrete type. Returns the offenders.

    An ``Any`` here means a column name in a ``sources.py`` ``schema=`` dict does not exist in
    Snowflake. PROBE U-01: ``t.no_such_column`` binds without error and shows up as
    ``FieldInfo(name='no_such_column', type_name='Any')``.
    """
    offenders = []
    for table_name, table in inventory["tables"].items():
        for column in table["columns"]:
            if column["type_name"] == "Any":
                offenders.append(f"{table_name}.{column['name']}")
    return sorted(offenders)


def write_inventory(path: Path | None = None) -> dict[str, Any]:
    """Build the inventory, assert no ``Any`` column, and write the JSON artifact."""
    inventory = build_inventory()
    offenders = assert_no_any_columns(inventory)
    if offenders:
        raise AssertionError(
            "Any-typed table columns found, which means a column name in sources.py does not "
            f"exist in Snowflake: {offenders}"
        )
    target = path or INVENTORY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(inventory, indent=1, sort_keys=True, default=str) + "\n")
    return inventory


if __name__ == "__main__":  # pragma: no cover - operational entry point
    inv = write_inventory()
    print(
        f"wrote {INVENTORY_PATH} - {inv['concept_count']} concepts, "
        f"{inv['table_count']} tables, {inv['declared_column_count']} declared columns"
    )
