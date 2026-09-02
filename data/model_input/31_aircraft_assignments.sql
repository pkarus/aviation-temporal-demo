-- DATA-04a: per-dimension aircraft assignments.
--
-- D-0004 / P0-01.5-01.7 split two different products:
--   * AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT keeps EVERY relevant same-day observation in source
--     order and carries NO date interval;
--   * AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT keeps the FINAL relevant observation per
--     (aircraft, dimension, event date) and owns the half-open interval.
--
-- Change detection is per dimension and null-safe.  The watched signature is a SHA-256 over the
-- D-0012 length-prefixed typed encoding of that dimension's watched value set, so a NULL is
-- distinguishable from every value.  Consecutive equality is suppressed; global equality is not,
-- so A -> B -> A stays three assignments.
--
-- Watched sets (SOURCE_CONTRACT.md):
--   aircraft_state  : AH-17 .. AH-31
--   aircraft_type   : AH-14 .. AH-16 + AC-02 .. AC-07 + the AH-13 type-resolution outcome
--   engine_type     : AC-08 .. AC-15 + the AH-13 engine-resolution outcome
--   aircraft_status : AH-09  (AH-08 and AH-12 stay provenance)
-- Raw AH-13 itself is provenance, never a watched business value.

CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT
  COMMENT = 'Ordered per-dimension aircraft assignment observations. Grain DV-04 = (dimension, AH-02, AH-05, AH-03, AH-01). Deliberately carries no valid_from/valid_to: same-day order is the source ordering tuple, not a zero-width interval. Every null-to-value and value-to-null watched transition is retained; an irrelevant event mints no row.'
AS
WITH per_dimension AS (
  -- aircraft_state
  SELECT
    'aircraft_state'::VARCHAR AS dimension, e.aircraft_id, e.start_event_date, e.row_sequence_number,
    e.event_sequence_number, e.aircraft_history_id, e.event_order_rank,
    e.end_event_date, e.end_event_date_is_unknown_future, e.start_event, e.event_source,
    e.aircraft_configuration_id,
    SHA2(
        MODEL_INPUT.DV43_FIELD('AH-17','VARCHAR',      e.aircraft_registration_number)
     || MODEL_INPUT.DV43_FIELD('AH-18','VARCHAR',      e.aircraft_transponder_code)
     || MODEL_INPUT.DV43_FIELD('AH-19','VARCHAR',      e.aircraft_registration_country_code_iso)
     || MODEL_INPUT.DV43_FIELD('AH-20','VARCHAR',      e.aircraft_registration_region)
     || MODEL_INPUT.DV43_FIELD('AH-21','VARCHAR',      e.aircraft_cargo)
     || MODEL_INPUT.DV43_FIELD('AH-22','VARCHAR',      e.storage_location)
     || MODEL_INPUT.DV43_FIELD('AH-23','VARCHAR',      e.storage_airport_code_iata)
     || MODEL_INPUT.DV43_FIELD('AH-24','VARCHAR',      e.base_airport)
     || MODEL_INPUT.DV43_FIELD('AH-25','VARCHAR',      e.base_airport_code_iata)
     || MODEL_INPUT.DV43_FIELD('AH-26','VARCHAR',      e.base_city)
     || MODEL_INPUT.DV43_FIELD('AH-27','VARCHAR',      e.base_country)
     || MODEL_INPUT.DV43_FIELD('AH-28','VARCHAR',      e.apu_type)
     || MODEL_INPUT.DV43_FIELD('AH-29','FLOAT',        MODEL_INPUT.CANON_FLOAT(e.aircraft_width_m))
     || MODEL_INPUT.DV43_FIELD('AH-30','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(e.operating_maximum_takeoff_weight_lb))
     || MODEL_INPUT.DV43_FIELD('AH-31','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(e.certified_maximum_takeoff_weight_lb))
    , 256) AS watched_signature,
    IFF(COALESCE(e.aircraft_registration_number, e.aircraft_transponder_code,
                 e.aircraft_registration_country_code_iso, e.aircraft_registration_region,
                 e.aircraft_cargo, e.storage_location, e.storage_airport_code_iata,
                 e.base_airport, e.base_airport_code_iata, e.base_city, e.base_country,
                 e.apu_type, TO_VARCHAR(e.aircraft_width_m),
                 TO_VARCHAR(e.operating_maximum_takeoff_weight_lb),
                 TO_VARCHAR(e.certified_maximum_takeoff_weight_lb)) IS NULL,
        'UNRESOLVED_NULL_VALUE', 'EXACT')::VARCHAR AS dimension_resolution_status,
    e.aircraft_registration_number, e.aircraft_transponder_code,
    e.aircraft_registration_country_code_iso, e.aircraft_registration_region, e.aircraft_cargo,
    e.storage_location, e.storage_airport_code_iata, e.base_airport, e.base_airport_code_iata,
    e.base_city, e.base_country, e.apu_type, e.aircraft_width_m,
    e.operating_maximum_takeoff_weight_lb, e.certified_maximum_takeoff_weight_lb,
    NULL::VARCHAR AS aircraft_status_code,
    NULL::VARCHAR AS aircraft_code_iata, NULL::VARCHAR AS aircraft_code_icao,
    NULL::VARCHAR AS aircraft_value_sub_series,
    NULL::VARCHAR AS aircraft_type_subseries, NULL::VARCHAR AS exact_aircraft_type_subseries,
    NULL::VARCHAR AS aircraft_family, NULL::VARCHAR AS aircraft_type_label,
    NULL::VARCHAR AS aircraft_series, NULL::VARCHAR AS aircraft_manufacturer,
    NULL::VARCHAR AS aircraft_design_class,
    NULL::VARCHAR AS engine_type_subseries, NULL::VARCHAR AS exact_engine_type_subseries,
    NULL::VARCHAR AS engine_manufacturer, NULL::VARCHAR AS engine_family,
    NULL::VARCHAR AS engine_type_label, NULL::VARCHAR AS engine_series,
    NULL::VARCHAR AS engine_propulsion_type,
    NULL::NUMBER(38,0) AS engine_count, NULL::BOOLEAN AS has_multiple_engine_types,
    NULL::BOOLEAN AS mixed_engine_set_complete
  FROM MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE e

  UNION ALL
  -- aircraft_type
  SELECT
    'aircraft_type', e.aircraft_id, e.start_event_date, e.row_sequence_number,
    e.event_sequence_number, e.aircraft_history_id, e.event_order_rank,
    e.end_event_date, e.end_event_date_is_unknown_future, e.start_event, e.event_source,
    e.aircraft_configuration_id,
    SHA2(
        MODEL_INPUT.DV43_FIELD('AH-14','VARCHAR', e.aircraft_code_iata)
     || MODEL_INPUT.DV43_FIELD('AH-15','VARCHAR', e.aircraft_code_icao)
     || MODEL_INPUT.DV43_FIELD('AH-16','VARCHAR', e.aircraft_value_sub_series)
     || MODEL_INPUT.DV43_FIELD('AC-02','VARCHAR', e.aircraft_family)
     || MODEL_INPUT.DV43_FIELD('AC-03','VARCHAR', e.aircraft_type)
     || MODEL_INPUT.DV43_FIELD('AC-04','VARCHAR', e.aircraft_series)
     || MODEL_INPUT.DV43_FIELD('AC-05','VARCHAR', e.aircraft_subseries)
     || MODEL_INPUT.DV43_FIELD('AC-06','VARCHAR', e.aircraft_manufacturer)
     || MODEL_INPUT.DV43_FIELD('AC-07','VARCHAR', e.aircraft_design_class)
     || MODEL_INPUT.DV43_FIELD('DV-08','VARCHAR', e.type_resolution_status)
    , 256),
    e.type_resolution_status,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL,
    e.aircraft_code_iata, e.aircraft_code_icao, e.aircraft_value_sub_series,
    e.aircraft_subseries, IFF(e.type_resolution_status = 'EXACT', e.aircraft_subseries, NULL),
    e.aircraft_family, e.aircraft_type, e.aircraft_series, e.aircraft_manufacturer,
    e.aircraft_design_class,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL
  FROM MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE e

  UNION ALL
  -- engine_type
  SELECT
    'engine_type', e.aircraft_id, e.start_event_date, e.row_sequence_number,
    e.event_sequence_number, e.aircraft_history_id, e.event_order_rank,
    e.end_event_date, e.end_event_date_is_unknown_future, e.start_event, e.event_source,
    e.aircraft_configuration_id,
    SHA2(
        MODEL_INPUT.DV43_FIELD('AC-08','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(e.engine_count))
     || MODEL_INPUT.DV43_FIELD('AC-09','BOOLEAN',      MODEL_INPUT.CANON_BOOL(e.has_multiple_engine_types))
     || MODEL_INPUT.DV43_FIELD('AC-10','VARCHAR',      e.engine_manufacturer)
     || MODEL_INPUT.DV43_FIELD('AC-11','VARCHAR',      e.engine_family)
     || MODEL_INPUT.DV43_FIELD('AC-12','VARCHAR',      e.engine_type)
     || MODEL_INPUT.DV43_FIELD('AC-13','VARCHAR',      e.engine_series)
     || MODEL_INPUT.DV43_FIELD('AC-14','VARCHAR',      e.engine_subseries)
     || MODEL_INPUT.DV43_FIELD('AC-15','VARCHAR',      e.engine_propulsion_type)
     || MODEL_INPUT.DV43_FIELD('DV-08','VARCHAR',      e.engine_resolution_status)
    , 256),
    e.engine_resolution_status,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL,
    NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    e.engine_subseries, IFF(e.engine_resolution_status = 'EXACT', e.engine_subseries, NULL),
    e.engine_manufacturer, e.engine_family, e.engine_type, e.engine_series,
    e.engine_propulsion_type,
    e.engine_count, e.has_multiple_engine_types, e.mixed_engine_set_complete
  FROM MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE e

  UNION ALL
  -- aircraft_status
  SELECT
    'aircraft_status', e.aircraft_id, e.start_event_date, e.row_sequence_number,
    e.event_sequence_number, e.aircraft_history_id, e.event_order_rank,
    e.end_event_date, e.end_event_date_is_unknown_future, e.start_event, e.event_source,
    e.aircraft_configuration_id,
    SHA2(MODEL_INPUT.DV43_FIELD('AH-09','VARCHAR', e.start_aircraft_status), 256),
    IFF(e.start_aircraft_status IS NULL, 'UNRESOLVED_NULL_VALUE', 'EXACT'),
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    e.start_aircraft_status,
    NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL
  FROM MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE e
), delta AS (
  SELECT
    p.*,
    LAG(p.watched_signature) OVER (
      PARTITION BY p.dimension, p.aircraft_id ORDER BY p.event_order_rank
    ) AS previous_watched_signature
  FROM per_dimension p
), relevant AS (
  SELECT d.*
  FROM delta d
  WHERE d.previous_watched_signature IS NULL
     OR d.watched_signature <> d.previous_watched_signature
)
SELECT
  r.dimension || '|' || TO_VARCHAR(r.aircraft_id) || '|'
    || MODEL_INPUT.CANON_DATE(r.start_event_date) || '|'
    || TO_VARCHAR(r.row_sequence_number) || '|' || TO_VARCHAR(r.aircraft_history_id)
                                                             AS audit_assignment_id,
  r.dimension,
  r.aircraft_id,
  r.start_event_date                                         AS event_date,
  r.row_sequence_number,
  r.event_sequence_number,
  r.aircraft_history_id,
  r.event_order_rank,
  ROW_NUMBER() OVER (PARTITION BY r.dimension, r.aircraft_id ORDER BY r.event_order_rank)
                                                             AS dimension_sequence,
  (r.event_order_rank = MAX(r.event_order_rank) OVER (
      PARTITION BY r.dimension, r.aircraft_id, r.start_event_date))
                                                             AS is_final_relevant_observation_of_day,
  r.watched_signature,
  r.previous_watched_signature,
  r.dimension_resolution_status,
  -- provenance, never interval authority
  r.end_event_date,
  r.end_event_date_is_unknown_future,
  r.start_event,
  r.event_source,
  r.aircraft_configuration_id,
  -- aircraft_state payload
  r.aircraft_registration_number,
  r.aircraft_transponder_code,
  r.aircraft_registration_country_code_iso,
  r.aircraft_registration_region,
  r.aircraft_cargo,
  r.storage_location,
  r.storage_airport_code_iata,
  r.base_airport,
  r.base_airport_code_iata,
  r.base_city,
  r.base_country,
  r.apu_type,
  r.aircraft_width_m,
  r.operating_maximum_takeoff_weight_lb,
  r.certified_maximum_takeoff_weight_lb,
  -- aircraft_status payload
  r.aircraft_status_code,
  -- aircraft_type payload
  r.aircraft_code_iata,
  r.aircraft_code_icao,
  r.aircraft_value_sub_series,
  r.aircraft_type_subseries,
  r.exact_aircraft_type_subseries,
  r.aircraft_family,
  r.aircraft_type_label,
  r.aircraft_series,
  r.aircraft_manufacturer,
  r.aircraft_design_class,
  -- engine_type payload
  r.engine_type_subseries,
  r.exact_engine_type_subseries,
  r.engine_manufacturer,
  r.engine_family,
  r.engine_type_label,
  r.engine_series,
  r.engine_propulsion_type,
  r.engine_count,
  r.has_multiple_engine_types,
  r.mixed_engine_set_complete
FROM relevant r;

-- ---------------------------------------------------------------------------------------------
-- Daily projection: the final relevant observation of each (dimension, aircraft, event date).
-- valid_from = AH-05 of that observation.
-- valid_to   = the next distinct daily assignment date for the same aircraft and dimension,
--              clipped to DV-02 existence_to; the last assignment closes at existence_to, which is
--              the model open sentinel 9999-01-01 when end of life is unknown.
-- An intraday null followed by a same-day resolvable observation stays in the audit sequence but
-- does NOT invent a calendar-date unknown gap, because only the final relevant observation of the
-- day is projected here.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT
  COMMENT = 'Date-visible per-dimension aircraft state. Grain DV-05 = (dimension, AH-02, AH-05, AH-01) after final-per-day selection. Owns the half-open interval DV-06 valid_from <= d < DV-07 valid_to, clipped to aircraft existence. DV-33 dimension_query_status is OK or UNKNOWN_STATE inside the interval; OUTSIDE_EXISTENCE and NO_RECORDED_STATE are evaluated at query time against DV-01/DV-02.'
AS
WITH final_per_day AS (
  SELECT a.*
  FROM MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT a
  WHERE a.is_final_relevant_observation_of_day
), bounded AS (
  SELECT
    f.*,
    e.existence_from,
    e.existence_to,
    LEAD(f.event_date) OVER (PARTITION BY f.dimension, f.aircraft_id ORDER BY f.event_date)
      AS next_assignment_date
  FROM final_per_day f
  JOIN MODEL_INPUT.AIRCRAFT_ELIGIBLE e ON e.aircraft_id = f.aircraft_id
)
SELECT
  b.dimension || '|' || TO_VARCHAR(b.aircraft_id) || '|'
    || MODEL_INPUT.CANON_DATE(b.event_date) || '|' || TO_VARCHAR(b.aircraft_history_id)
                                                             AS daily_assignment_id,
  b.audit_assignment_id,
  b.dimension,
  b.aircraft_id,
  b.event_date                                               AS valid_from,
  LEAST(COALESCE(b.next_assignment_date, b.existence_to), b.existence_to)
                                                             AS valid_to,
  b.next_assignment_date,
  b.existence_from,
  b.existence_to,
  (COALESCE(b.next_assignment_date, b.existence_to) > b.existence_to)
                                                             AS valid_to_clipped_to_existence,
  b.aircraft_history_id,
  b.row_sequence_number,
  b.event_sequence_number,
  b.event_order_rank,
  b.dimension_resolution_status,
  CASE
    WHEN b.dimension = 'aircraft_type'   AND b.dimension_resolution_status = 'EXACT' THEN 'OK'
    WHEN b.dimension = 'engine_type'     AND b.dimension_resolution_status = 'EXACT' THEN 'OK'
    WHEN b.dimension = 'aircraft_status' AND b.dimension_resolution_status = 'EXACT' THEN 'OK'
    WHEN b.dimension = 'aircraft_state'  AND b.dimension_resolution_status = 'EXACT' THEN 'OK'
    ELSE 'UNKNOWN_STATE'
  END::VARCHAR                                               AS dimension_query_status,
  -- provenance retained; AH-06 is never the authority for valid_to
  b.end_event_date,
  b.end_event_date_is_unknown_future,
  (b.end_event_date IS NOT NULL
   AND b.end_event_date <> LEAST(COALESCE(b.next_assignment_date, b.existence_to), b.existence_to))
                                                             AS end_event_date_disagrees_with_valid_to,
  b.start_event,
  b.event_source,
  b.aircraft_configuration_id,
  b.aircraft_registration_number,
  b.aircraft_transponder_code,
  b.aircraft_registration_country_code_iso,
  b.aircraft_registration_region,
  b.aircraft_cargo,
  b.storage_location,
  b.storage_airport_code_iata,
  b.base_airport,
  b.base_airport_code_iata,
  b.base_city,
  b.base_country,
  b.apu_type,
  b.aircraft_width_m,
  b.operating_maximum_takeoff_weight_lb,
  b.certified_maximum_takeoff_weight_lb,
  b.aircraft_status_code,
  b.aircraft_code_iata,
  b.aircraft_code_icao,
  b.aircraft_value_sub_series,
  b.aircraft_type_subseries,
  b.exact_aircraft_type_subseries,
  b.aircraft_family,
  b.aircraft_type_label,
  b.aircraft_series,
  b.aircraft_manufacturer,
  b.aircraft_design_class,
  b.engine_type_subseries,
  b.exact_engine_type_subseries,
  b.engine_manufacturer,
  b.engine_family,
  b.engine_type_label,
  b.engine_series,
  b.engine_propulsion_type,
  b.engine_count,
  b.has_multiple_engine_types,
  b.mixed_engine_set_complete
FROM bounded b;
