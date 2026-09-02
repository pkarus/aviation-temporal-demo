"""sources.py - every ``model.Table()`` binding, with an explicit ``schema=`` dict.

GENERATED from ``PK_AVIATION_TEMPORAL.INFORMATION_SCHEMA.COLUMNS``, then checked in.
Regenerate with ``python -m aviation_model._regen_sources``;
``tests/test_model.py::test_declared_types_match_information_schema`` re-derives the mapping
live and fails on any drift.

Three rules this file exists to enforce, all from ``build/design/PROBE_RESULTS.md``:

* **R1 - an explicit ``schema=`` dict everywhere.** Strict mode gives *zero* typo protection
  on a ``model.Table()`` (PROBE U-01): a misspelled column binds silently as an ``Any``-typed
  relation and produces an empty or NaN result later. The dict is the only defence, and
  ``inventory.py`` asserts that no discovered column is ``Any``.
* **U-03 - the 26 Snowflake ``TIME`` columns are declared ``String``.** Discovered *or*
  explicitly declared as ``DateTime`` they come back 100% NULL with no error. Declared
  ``String`` the value is byte-identical to ``TO_VARCHAR(t, 'HH24:MI:SS.FF3')``, so every
  time-of-day literal must be written ``'HH:MM:SS.mmm'``; ``'16:00:00'`` matches zero rows.
* **U-02 - a wrong declared type is a silent all-NaN column, not a ``TyperError``.** Types are
  therefore derived from ``INFORMATION_SCHEMA`` rather than eyeballed, and the integer mapping
  mirrors the SDK's own CDC bucketing rather than the column's declared precision:
  ``NUMBER(p,0)`` with ``p <= 18`` is ``Number.size(18, 0)`` and with ``19 <= p <= 38`` is
  ``Integer``. Declaring the faithful ``Number.size(19, 0)`` for a ``NUMBER(19,0)`` column
  returned 600 rows and 0 non-null values, silently - see :func:`derive_type`. The MODEL-01
  gate asserts per-column non-null counts against SQL, not just row counts, which is the only
  check that catches it.

D-0027 SUPERSEDES D-0019 here: the row-scoped ``CODE_RESOLUTION`` (784,140 rows),
``CODE_RESOLUTION_CANDIDATE`` (627,424) and ``CODE_RESOLUTION_INPUT`` (784,140) ARE now bound.
D-0019 excluded them on a performance premise that measurement refuted: binding all three cost
0.18s on first query and no measurable warm delta. The distinct-code projection
``CODE_RESOLUTION_CODE`` (660 rows) is retained for link semantics, and every other
MODEL_INPUT object already carries its own resolved target id plus resolution status. The
timed experiment that settled it is recorded in ``build/task_reports/MODEL-01.json``; the
tables stay materialized and reachable from SQL.
"""

from relationalai.semantics import (
    Bool,
    Date,
    DateTime,
    Float,
    Integer,
    Number,
    String,
)

from .constants import DB
from .model import model

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
