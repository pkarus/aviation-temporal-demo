-- DATA-04a: aircraft identity, existence bounds, eligible events and event quarantine.
--
-- D-0003: a real AM-08 end-of-life date is an EXCLUSIVE existence upper bound.
-- DV-01 existence_from = normalized AM-07, else the first eligible AH-05.
-- DV-02 existence_to   = normalized AM-08, else the model open sentinel 9999-01-01.
-- The DV-01 fallback deliberately reads the required-field-eligible event set BEFORE the existence
-- filter below, so the bound is well defined and the derivation is not circular.

CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_ELIGIBLE
  COMMENT = 'One row per eligible physical aircraft (AM-01, not_for_use = false). Carries master facts with source unknown-future sentinel normalization plus DV-01/DV-02 existence bounds. Duplicate AM-01 is a hard source gate failure proven by --verify.'
AS
WITH first_event AS (
  SELECT h.aircraft_id, MIN(h.start_event_date) AS first_eligible_event_date
  FROM SOURCE.AIRCRAFT_HISTORY h
  WHERE h.aircraft_history_id IS NOT NULL
    AND h.aircraft_id IS NOT NULL
    AND h.start_event_date IS NOT NULL
    AND h.start_event_date <> DATE '9999-12-31'
    AND h.row_sequence_number IS NOT NULL
    AND h.not_for_use = FALSE
  GROUP BY h.aircraft_id
)
SELECT
  m.aircraft_id,
  m.aircraft_serial_number,
  m.aircraft_line_number,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_order_date)          AS aircraft_order_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(m.aircraft_order_date)              AS aircraft_order_date_is_unknown_future,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_build_date)          AS aircraft_build_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(m.aircraft_build_date)              AS aircraft_build_date_is_unknown_future,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_delivery_date)       AS aircraft_delivery_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(m.aircraft_delivery_date)           AS aircraft_delivery_date_is_unknown_future,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_roll_out_date)       AS aircraft_roll_out_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(m.aircraft_roll_out_date)           AS aircraft_roll_out_date_is_unknown_future,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_first_flight_date)   AS aircraft_first_flight_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(m.aircraft_first_flight_date)       AS aircraft_first_flight_date_is_unknown_future,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_start_of_life_date)  AS aircraft_start_of_life_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(m.aircraft_start_of_life_date)      AS aircraft_start_of_life_date_is_unknown_future,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_end_of_life_date)    AS aircraft_end_of_life_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(m.aircraft_end_of_life_date)        AS aircraft_end_of_life_date_is_unknown_future,
  COALESCE(MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_start_of_life_date),
           f.first_eligible_event_date)                             AS existence_from,
  COALESCE(MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_end_of_life_date),
           DATE '9999-01-01')                                       AS existence_to,
  (MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_end_of_life_date) IS NOT NULL)
                                                                    AS has_finite_end_of_life,
  CASE WHEN MODEL_INPUT.NORMALIZE_SOURCE_DATE(m.aircraft_start_of_life_date) IS NOT NULL
       THEN 'AM_07_START_OF_LIFE'
       WHEN f.first_eligible_event_date IS NOT NULL THEN 'FIRST_ELIGIBLE_EVENT_DATE'
       ELSE 'UNBOUNDED' END::VARCHAR                                AS existence_from_basis,
  m.aircraft_build_airport_code_iata,
  m.aircraft_build_airport,
  m.original_delivery_operator,
  m.original_delivery_operator_category,
  m.apu_type                                     AS master_current_only_apu_type,
  m.aircraft_width_m                             AS master_current_only_aircraft_width_m,
  m.operating_maximum_takeoff_weight_lb          AS master_current_only_operating_maximum_takeoff_weight_lb,
  m.certified_maximum_takeoff_weight_lb          AS master_current_only_certified_maximum_takeoff_weight_lb,
  m.not_for_use,
  f.first_eligible_event_date
FROM SOURCE.AIRCRAFT_MASTER m
LEFT JOIN first_event f ON f.aircraft_id = m.aircraft_id
WHERE m.aircraft_id IS NOT NULL
  AND m.not_for_use = FALSE;

-- ---------------------------------------------------------------------------------------------
-- Event eligibility, configuration resolution and the canonical order tuple.
-- A history event is left-preserved across configuration resolution: failure to resolve AC-01
-- never drops AH-01, it opens a dimension-specific unresolved gap.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_EVENT_ELIGIBLE
  COMMENT = 'One row per eligible source aircraft event (AH-01). Retains AH-01..AH-33 after eligibility and unknown-future normalization, the canonical order tuple (AH-05, AH-03, AH-04, AH-01) and its DV-03 rank, plus per-dimension configuration resolution outcomes and the measured would-be inner-join loss.'
AS
WITH classified AS (
  SELECT
    h.*,
    a.aircraft_id                             AS eligible_aircraft_id,
    a.existence_from,
    a.existence_to,
    a.has_finite_end_of_life,
    CASE
      WHEN h.aircraft_history_id IS NULL OR h.aircraft_id IS NULL
        OR h.start_event_date IS NULL OR h.row_sequence_number IS NULL THEN 'MISSING_REQUIRED_FIELD'
      WHEN h.start_event_date = DATE '9999-12-31'                      THEN 'UNKNOWN_FUTURE_EVENT_DATE'
      WHEN h.not_for_use IS NULL                                       THEN 'UNKNOWN_ELIGIBILITY_FLAG'
      WHEN h.not_for_use                                               THEN 'NOT_FOR_USE_EVENT'
      WHEN a.aircraft_id IS NULL                                       THEN 'INELIGIBLE_OR_UNKNOWN_AIRCRAFT'
      WHEN h.start_event_date < a.existence_from                       THEN 'EVENT_BEFORE_EXISTENCE'
      WHEN a.has_finite_end_of_life AND h.start_event_date >= a.existence_to
                                                                       THEN 'EVENT_ON_OR_AFTER_END_OF_LIFE'
      ELSE NULL
    END::VARCHAR                              AS ineligibility_reason
  FROM SOURCE.AIRCRAFT_HISTORY h
  LEFT JOIN MODEL_INPUT.AIRCRAFT_ELIGIBLE a ON a.aircraft_id = h.aircraft_id
)
SELECT
  c.aircraft_history_id,
  c.aircraft_id,
  c.row_sequence_number,
  c.event_sequence_number,
  c.start_event_date,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(c.end_event_date)          AS end_event_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(c.end_event_date)              AS end_event_date_is_unknown_future,
  c.is_current,
  c.start_event,
  c.start_aircraft_status,
  c.end_event,
  c.end_aircraft_status,
  c.event_source,
  c.aircraft_configuration_id,
  c.aircraft_code_iata,
  c.aircraft_code_icao,
  c.aircraft_value_sub_series,
  c.aircraft_registration_number,
  c.aircraft_transponder_code,
  c.aircraft_registration_country_code_iso,
  c.aircraft_registration_region,
  c.aircraft_cargo,
  c.storage_location,
  c.storage_airport_code_iata,
  c.base_airport,
  c.base_airport_code_iata,
  c.base_city,
  c.base_country,
  c.apu_type,
  c.aircraft_width_m,
  c.operating_maximum_takeoff_weight_lb,
  c.certified_maximum_takeoff_weight_lb,
  c.base_state,
  c.base_region,
  c.storage_location_type,
  c.noise_certification,
  c.has_winglets,
  c.aircraft_registration_country,
  c.transponder_miscode,
  c.maximum_landing_weight_lb,
  c.operating_empty_weight_lb,
  c.not_for_use,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(c.publish_date)            AS publish_date,
  MODEL_INPUT.IS_UNKNOWN_FUTURE(c.publish_date)                AS publish_date_is_unknown_future,
  c.existence_from,
  c.existence_to,
  -- Canonical order: (AH-05, AH-03, AH-04, AH-01); the last two are deterministic fallbacks only.
  ROW_NUMBER() OVER (PARTITION BY c.aircraft_id
                     ORDER BY c.start_event_date, c.row_sequence_number,
                              c.event_sequence_number NULLS LAST, c.aircraft_history_id)
                                                               AS event_order_rank,
  -- Configuration resolution (AH-13).  Raw AH-13 is provenance; the resolved dimension is watched.
  cfg.aircraft_configuration_id IS NOT NULL                    AS configuration_resolved,
  cfg.aircraft_family,
  cfg.aircraft_type,
  cfg.aircraft_series,
  cfg.aircraft_subseries,
  cfg.aircraft_manufacturer,
  cfg.aircraft_design_class,
  cfg.engine_count,
  cfg.has_multiple_engine_types,
  cfg.engine_manufacturer,
  cfg.engine_family,
  cfg.engine_type,
  cfg.engine_series,
  cfg.engine_subseries,
  cfg.engine_propulsion_type,
  MODEL_INPUT.NORMALIZE_SOURCE_DATE(cfg.publish_date)          AS configuration_publish_date,
  CASE
    WHEN c.aircraft_configuration_id IS NULL              THEN 'UNRESOLVED_NULL_CONFIGURATION'
    WHEN cfg.aircraft_configuration_id IS NULL            THEN 'UNRESOLVED_MISSING_CONFIGURATION'
    WHEN cfg.aircraft_subseries IS NULL                   THEN 'UNRESOLVED_NULL_TYPE_KEY'
    WHEN td.definition_status = 'AMBIGUOUS_DEFINITION'    THEN 'AMBIGUOUS_TYPE_DEFINITION'
    WHEN td.aircraft_subseries IS NULL                    THEN 'UNRESOLVED_MISSING_TYPE_DEFINITION'
    ELSE 'EXACT'
  END::VARCHAR                                                 AS type_resolution_status,
  CASE
    WHEN c.aircraft_configuration_id IS NULL              THEN 'UNRESOLVED_NULL_CONFIGURATION'
    WHEN cfg.aircraft_configuration_id IS NULL            THEN 'UNRESOLVED_MISSING_CONFIGURATION'
    WHEN cfg.engine_subseries IS NULL                     THEN 'UNRESOLVED_NULL_ENGINE_KEY'
    WHEN ed.definition_status = 'AMBIGUOUS_DEFINITION'    THEN 'AMBIGUOUS_ENGINE_DEFINITION'
    WHEN ed.engine_subseries IS NULL                      THEN 'UNRESOLVED_MISSING_ENGINE_DEFINITION'
    ELSE 'EXACT'
  END::VARCHAR                                                 AS engine_resolution_status,
  -- DV-09: complete only when the source does not report multiple engine types.
  CASE WHEN cfg.aircraft_configuration_id IS NULL THEN NULL
       WHEN cfg.has_multiple_engine_types IS NULL THEN NULL
       ELSE NOT cfg.has_multiple_engine_types END              AS mixed_engine_set_complete,
  -- P0-12.4: how many rows a source-style inner join on the configuration would have lost.
  (c.aircraft_configuration_id IS NULL OR cfg.aircraft_configuration_id IS NULL)
                                                               AS would_be_lost_by_inner_join
FROM classified c
LEFT JOIN SOURCE.AIRCRAFT_CONFIGURATION cfg
  ON cfg.aircraft_configuration_id = c.aircraft_configuration_id
LEFT JOIN MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION td
  ON td.aircraft_subseries = cfg.aircraft_subseries
LEFT JOIN MODEL_INPUT.ENGINE_TYPE_DEFINITION ed
  ON ed.engine_subseries = cfg.engine_subseries
WHERE c.ineligibility_reason IS NULL;

-- ---------------------------------------------------------------------------------------------
-- Quarantine.  No aircraft or event identity is guessed.  Rows that retain AH-01 key on it;
-- rows without it key on the deterministic semantic key (source object, DV-43, reason) and keep
-- an occurrence count instead of an unstable row ordinal.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_EVENT_QUARANTINE
  COMMENT = 'Ineligible source aircraft events. Grain DV-44 = SHA-256 over source object, stable AH-01 when present else DV-43, and the closed reason code. Retains raw lineage, the missing required-field list and an occurrence count; invents no aircraft or event identity.'
AS
WITH classified AS (
  SELECT
    h.*,
    a.aircraft_id       AS eligible_aircraft_id,
    a.existence_from,
    a.existence_to,
    a.has_finite_end_of_life,
    CASE
      WHEN h.aircraft_history_id IS NULL OR h.aircraft_id IS NULL
        OR h.start_event_date IS NULL OR h.row_sequence_number IS NULL THEN 'MISSING_REQUIRED_FIELD'
      WHEN h.start_event_date = DATE '9999-12-31'                      THEN 'UNKNOWN_FUTURE_EVENT_DATE'
      WHEN h.not_for_use IS NULL                                       THEN 'UNKNOWN_ELIGIBILITY_FLAG'
      WHEN h.not_for_use                                               THEN 'NOT_FOR_USE_EVENT'
      WHEN a.aircraft_id IS NULL                                       THEN 'INELIGIBLE_OR_UNKNOWN_AIRCRAFT'
      WHEN h.start_event_date < a.existence_from                       THEN 'EVENT_BEFORE_EXISTENCE'
      WHEN a.has_finite_end_of_life AND h.start_event_date >= a.existence_to
                                                                       THEN 'EVENT_ON_OR_AFTER_END_OF_LIFE'
      ELSE NULL
    END::VARCHAR AS quarantine_reason
  FROM SOURCE.AIRCRAFT_HISTORY h
  LEFT JOIN MODEL_INPUT.AIRCRAFT_ELIGIBLE a ON a.aircraft_id = h.aircraft_id
), hashed AS (
  SELECT
    c.*,
    SHA2(
      MODEL_INPUT.DV43_FIELD('AH-01','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.aircraft_history_id))
      || MODEL_INPUT.DV43_FIELD('AH-02','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.aircraft_id))
      || MODEL_INPUT.DV43_FIELD('AH-03','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.row_sequence_number))
      || MODEL_INPUT.DV43_FIELD('AH-04','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.event_sequence_number))
      || MODEL_INPUT.DV43_FIELD('AH-05','DATE',         MODEL_INPUT.CANON_DATE(c.start_event_date))
      || MODEL_INPUT.DV43_FIELD('AH-06','DATE',         MODEL_INPUT.CANON_DATE(c.end_event_date))
      || MODEL_INPUT.DV43_FIELD('AH-07','BOOLEAN',      MODEL_INPUT.CANON_BOOL(c.is_current))
      || MODEL_INPUT.DV43_FIELD('AH-08','VARCHAR',      c.start_event)
      || MODEL_INPUT.DV43_FIELD('AH-09','VARCHAR',      c.start_aircraft_status)
      || MODEL_INPUT.DV43_FIELD('AH-10','VARCHAR',      c.end_event)
      || MODEL_INPUT.DV43_FIELD('AH-11','VARCHAR',      c.end_aircraft_status)
      || MODEL_INPUT.DV43_FIELD('AH-12','VARCHAR',      c.event_source)
      || MODEL_INPUT.DV43_FIELD('AH-13','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.aircraft_configuration_id))
      || MODEL_INPUT.DV43_FIELD('AH-14','VARCHAR',      c.aircraft_code_iata)
      || MODEL_INPUT.DV43_FIELD('AH-15','VARCHAR',      c.aircraft_code_icao)
      || MODEL_INPUT.DV43_FIELD('AH-16','VARCHAR',      c.aircraft_value_sub_series)
      || MODEL_INPUT.DV43_FIELD('AH-17','VARCHAR',      c.aircraft_registration_number)
      || MODEL_INPUT.DV43_FIELD('AH-18','VARCHAR',      c.aircraft_transponder_code)
      || MODEL_INPUT.DV43_FIELD('AH-19','VARCHAR',      c.aircraft_registration_country_code_iso)
      || MODEL_INPUT.DV43_FIELD('AH-20','VARCHAR',      c.aircraft_registration_region)
      || MODEL_INPUT.DV43_FIELD('AH-21','VARCHAR',      c.aircraft_cargo)
      || MODEL_INPUT.DV43_FIELD('AH-22','VARCHAR',      c.storage_location)
      || MODEL_INPUT.DV43_FIELD('AH-23','VARCHAR',      c.storage_airport_code_iata)
      || MODEL_INPUT.DV43_FIELD('AH-24','VARCHAR',      c.base_airport)
      || MODEL_INPUT.DV43_FIELD('AH-25','VARCHAR',      c.base_airport_code_iata)
      || MODEL_INPUT.DV43_FIELD('AH-26','VARCHAR',      c.base_city)
      || MODEL_INPUT.DV43_FIELD('AH-27','VARCHAR',      c.base_country)
      || MODEL_INPUT.DV43_FIELD('AH-28','VARCHAR',      c.apu_type)
      || MODEL_INPUT.DV43_FIELD('AH-29','FLOAT',        MODEL_INPUT.CANON_FLOAT(c.aircraft_width_m))
      || MODEL_INPUT.DV43_FIELD('AH-30','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.operating_maximum_takeoff_weight_lb))
      || MODEL_INPUT.DV43_FIELD('AH-31','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.certified_maximum_takeoff_weight_lb))
      || MODEL_INPUT.DV43_FIELD('AH-32','BOOLEAN',      MODEL_INPUT.CANON_BOOL(c.not_for_use))
      || MODEL_INPUT.DV43_FIELD('AH-33','DATE',         MODEL_INPUT.CANON_DATE(c.publish_date))
      || MODEL_INPUT.DV43_FIELD('AH-34','VARCHAR', c.base_state)
      || MODEL_INPUT.DV43_FIELD('AH-35','VARCHAR', c.base_region)
      || MODEL_INPUT.DV43_FIELD('AH-36','VARCHAR', c.storage_location_type)
      || MODEL_INPUT.DV43_FIELD('AH-37','VARCHAR', c.noise_certification)
      || MODEL_INPUT.DV43_FIELD('AH-38','BOOLEAN', MODEL_INPUT.CANON_BOOL(c.has_winglets))
      || MODEL_INPUT.DV43_FIELD('AH-39','VARCHAR', c.aircraft_registration_country)
      || MODEL_INPUT.DV43_FIELD('AH-40','BOOLEAN', MODEL_INPUT.CANON_BOOL(c.transponder_miscode))
      || MODEL_INPUT.DV43_FIELD('AH-41','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.maximum_landing_weight_lb))
      || MODEL_INPUT.DV43_FIELD('AH-42','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(c.operating_empty_weight_lb))
    , 256) AS typed_normalized_row_hash
  FROM classified c
  WHERE c.quarantine_reason IS NOT NULL
)
SELECT
  SHA2(
    MODEL_INPUT.LP('AIRCRAFT_HISTORY')
    || MODEL_INPUT.LP(COALESCE(TO_VARCHAR(h.aircraft_history_id), h.typed_normalized_row_hash))
    || MODEL_INPUT.LP(h.quarantine_reason)
  , 256)                                                            AS quarantine_id,
  'AIRCRAFT_HISTORY'::VARCHAR                                       AS source_object,
  h.quarantine_reason,
  MAX(h.aircraft_history_id)                                        AS raw_aircraft_history_id,
  MAX(h.aircraft_id)                                                AS raw_aircraft_id,
  MAX(h.row_sequence_number)                                        AS raw_row_sequence_number,
  MAX(h.event_sequence_number)                                      AS raw_event_sequence_number,
  MAX(h.start_event_date)                                           AS raw_start_event_date,
  MAX(h.typed_normalized_row_hash)                                  AS typed_normalized_row_hash,
  IFF(MAX(h.aircraft_history_id) IS NOT NULL, 'STABLE_SOURCE_ROW_ID', 'DV43_HASH_FALLBACK')::VARCHAR
                                                                    AS quarantine_key_basis,
  MAX(ARRAY_TO_STRING(ARRAY_COMPACT(ARRAY_CONSTRUCT(
    IFF(h.aircraft_history_id IS NULL, 'aircraft_history_id', NULL),
    IFF(h.aircraft_id IS NULL, 'aircraft_id', NULL),
    IFF(h.start_event_date IS NULL, 'start_event_date', NULL),
    IFF(h.row_sequence_number IS NULL, 'row_sequence_number', NULL)
  )), ','))                                                         AS missing_required_fields,
  COUNT(*)                                                          AS occurrence_count
FROM hashed h
GROUP BY 1, 2, 3;
