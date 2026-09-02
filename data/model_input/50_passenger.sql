-- DATA-04a: canonical passenger flights, source lineage, invalid observations and quarantine.
--
-- P0-10.2 / P0-10.3:
--   * PassengerFlight is a typed canonical union, not an untyped append.  Historical wins a
--     canonical-key overlap and BOTH lineages are retained;
--   * within a side, deterministic reduction is publish date descending, stable source row ID
--     ascending, then DV-43 typed normalized-row hash ascending;
--   * forward-only historical fields stay null rather than fabricated;
--   * a null key component creates INVALID_PASSENGER_KEY audit evidence identified by
--     (source_system, stable_source_row_id) and no PassengerFlight;
--   * missing both the canonical identity and the stable row ID is quarantined on the
--     deterministic semantic key, never on an invented identity.

CREATE OR REPLACE TABLE MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL
  COMMENT = 'Canonical passenger flight plan. Grain DV-20 passenger_flight_key = typed marketing carrier, flight number, planned origin, planned destination and operating date joined by ''|''. Historical wins a canonical-key overlap under DV-21 source precedence; plan fields only, never actual facts.'
AS
WITH valid AS (
  SELECT
    p.*,
    IFF(p.source_system = 'HISTORICAL', 0, 1) AS source_precedence_rank
  FROM MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION p
  WHERE p.passenger_key_status = 'VALID'
), ranked AS (
  SELECT
    v.*,
    ROW_NUMBER() OVER (
      PARTITION BY v.passenger_flight_key
      ORDER BY v.source_precedence_rank ASC,
               v.publish_date DESC NULLS LAST,
               v.stable_source_row_id ASC NULLS LAST,
               v.typed_normalized_row_hash ASC
    ) AS selection_rank,
    COUNT(*) OVER (PARTITION BY v.passenger_flight_key) AS lineage_observation_count,
    MAX(IFF(v.source_system = 'HISTORICAL', 1, 0)) OVER (PARTITION BY v.passenger_flight_key) = 1
                                                        AS historical_lineage_retained,
    MAX(IFF(v.source_system = 'FORWARD', 1, 0))    OVER (PARTITION BY v.passenger_flight_key) = 1
                                                        AS forward_lineage_retained
  FROM valid v
)
SELECT
  r.passenger_flight_key,
  r.key_marketing_carrier_internal       AS marketing_carrier_internal,
  r.key_flight_number                    AS flight_number,
  r.key_departure_station_code_iata      AS planned_origin_station_code_iata,
  r.key_arrival_station_code_iata        AS planned_destination_station_code_iata,
  r.key_operating_date                   AS operating_date,
  r.source_system                        AS selected_source_system,
  r.source_row_token                     AS selected_source_row_token,
  r.source_row_token_basis               AS selected_source_row_token_basis,
  r.stable_source_row_id                 AS selected_stable_source_row_id,
  r.typed_normalized_row_hash            AS selected_typed_normalized_row_hash,
  'HISTORICAL_OVER_FORWARD'::VARCHAR     AS source_precedence_rule,
  r.lineage_observation_count,
  r.historical_lineage_retained,
  r.forward_lineage_retained,
  -- plan facts from the selected observation
  r.operating_carrier_internal,
  r.publish_date,
  r.service_type_iata,
  r.equipment_subtype_code_iata,
  r.total_seats,
  r.is_codeshare,
  r.number_of_intermediate_stops,
  r.intermediate_stop_station_codes_iata,
  r.arrival_day_indicator,
  r.plan_departure_local_timestamp,
  r.plan_arrival_local_timestamp,
  r.plan_departure_utc_timestamp,
  r.plan_arrival_utc_timestamp,
  r.utc_date_status,
  -- historical-only plan facts; deliberately null when a forward row wins
  r.schedule_key,
  r.historical_effective_date,
  r.passenger_departure_local_time,
  r.passenger_arrival_local_time,
  r.passenger_departure_utc_time,
  r.passenger_arrival_utc_time,
  r.departure_utc_offset_minutes,
  r.arrival_utc_offset_minutes,
  -- resolved roles; marketing and operating stay separate
  mkt.single_candidate_id                AS marketing_airline_id,
  CASE WHEN r.key_marketing_carrier_internal IS NULL THEN 'INVALID_INPUT'
       WHEN mkt.raw_code IS NULL THEN 'UNRESOLVED' ELSE mkt.resolution_status END::VARCHAR
                                         AS marketing_airline_resolution_status,
  op.single_candidate_id                 AS operating_airline_id,
  CASE WHEN r.operating_carrier_internal IS NULL THEN 'INVALID_INPUT'
       WHEN op.raw_code IS NULL THEN 'UNRESOLVED' ELSE op.resolution_status END::VARCHAR
                                         AS operating_airline_resolution_status,
  orig.single_candidate_id               AS planned_origin_airport_id,
  CASE WHEN r.key_departure_station_code_iata IS NULL THEN 'INVALID_INPUT'
       WHEN orig.raw_code IS NULL THEN 'UNRESOLVED' ELSE orig.resolution_status END::VARCHAR
                                         AS planned_origin_airport_resolution_status,
  dest.single_candidate_id               AS planned_destination_airport_id,
  CASE WHEN r.key_arrival_station_code_iata IS NULL THEN 'INVALID_INPUT'
       WHEN dest.raw_code IS NULL THEN 'UNRESOLVED' ELSE dest.resolution_status END::VARCHAR
                                         AS planned_destination_airport_resolution_status
FROM ranked r
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE mkt
  ON mkt.method = 'AIRLINE_ALIAS_UNION_EXACT' AND mkt.raw_code = r.key_marketing_carrier_internal
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE op
  ON op.method  = 'AIRLINE_ALIAS_UNION_EXACT' AND op.raw_code  = r.operating_carrier_internal
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE orig
  ON orig.method = 'AIRPORT_IATA_EXACT' AND orig.raw_code = r.key_departure_station_code_iata
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE dest
  ON dest.method = 'AIRPORT_IATA_EXACT' AND dest.raw_code = r.key_arrival_station_code_iata
WHERE r.selection_rank = 1;

CREATE OR REPLACE TABLE MODEL_INPUT.PASSENGER_SOURCE_LINEAGE
  COMMENT = 'Every contributing PF/PH observation for a canonical passenger flight, including non-selected overlap and duplicate evidence. Grain (DV-20, source_system, DV-46 source_row_token) with the DV-43 typed hash and the DV-21 precedence rank.'
AS
WITH valid AS (
  SELECT p.*, IFF(p.source_system = 'HISTORICAL', 0, 1) AS source_precedence_rank
  FROM MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION p
  WHERE p.passenger_key_status = 'VALID'
), ranked AS (
  SELECT
    v.*,
    ROW_NUMBER() OVER (
      PARTITION BY v.passenger_flight_key
      ORDER BY v.source_precedence_rank ASC,
               v.publish_date DESC NULLS LAST,
               v.stable_source_row_id ASC NULLS LAST,
               v.typed_normalized_row_hash ASC
    ) AS selection_rank
  FROM valid v
)
SELECT
  r.passenger_flight_key,
  r.source_system,
  r.source_row_token,
  r.source_row_token_basis,
  r.stable_source_row_id,
  r.typed_normalized_row_hash,
  r.publish_date,
  r.source_precedence_rank,
  r.selection_rank,
  (r.selection_rank = 1)                 AS is_selected_observation,
  r.schedule_key,
  r.operating_carrier_internal,
  r.total_seats,
  r.is_codeshare,
  r.number_of_intermediate_stops,
  r.intermediate_stop_station_codes_iata,
  r.utc_date_status
FROM ranked r;

CREATE OR REPLACE TABLE MODEL_INPUT.PASSENGER_FLIGHT_INVALID
  COMMENT = 'Passenger source observations with a null canonical-key component but a retained stable source row ID. Grain (source_system, stable_source_row_id). Creates no PassengerFlight identity.'
AS
SELECT
  p.source_system,
  p.stable_source_row_id,
  p.source_row_token,
  p.typed_normalized_row_hash,
  p.passenger_key_status,
  'INVALID_PASSENGER_KEY'::VARCHAR       AS invalid_reason,
  p.missing_key_components,
  p.key_marketing_carrier_internal       AS raw_marketing_carrier_internal,
  p.key_flight_number                    AS raw_flight_number,
  p.key_departure_station_code_iata      AS raw_departure_station_code_iata,
  p.key_arrival_station_code_iata        AS raw_arrival_station_code_iata,
  p.key_operating_date                   AS raw_operating_date,
  p.publish_date
FROM MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION p
WHERE p.passenger_key_status = 'INVALID_PASSENGER_KEY';

CREATE OR REPLACE TABLE MODEL_INPUT.PASSENGER_SOURCE_QUARANTINE
  COMMENT = 'Passenger source observations missing both a canonical-key component and a stable source row ID. Grain DV-44 = SHA-256 over source system, DV-43 typed hash and the closed reason code, with an occurrence count. No passenger or invalid-observation identity is guessed.'
AS
SELECT
  SHA2(MODEL_INPUT.LP(p.source_system) || MODEL_INPUT.LP(p.typed_normalized_row_hash)
       || MODEL_INPUT.LP('MISSING_CANONICAL_KEY_AND_SOURCE_ROW_ID'), 256) AS quarantine_id,
  p.source_system                                                          AS source_object,
  'MISSING_CANONICAL_KEY_AND_SOURCE_ROW_ID'::VARCHAR                       AS quarantine_reason,
  p.typed_normalized_row_hash,
  'DV43_HASH_FALLBACK'::VARCHAR                                            AS quarantine_key_basis,
  MAX(p.missing_key_components)                                            AS missing_key_components,
  MAX(p.key_flight_number)                                                 AS raw_flight_number,
  MAX(p.key_departure_station_code_iata)                                   AS raw_departure_station_code_iata,
  MAX(p.key_arrival_station_code_iata)                                     AS raw_arrival_station_code_iata,
  MAX(p.key_operating_date)                                                AS raw_operating_date,
  COUNT(*)                                                                 AS occurrence_count
FROM MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION p
WHERE p.passenger_key_status = 'QUARANTINED'
GROUP BY 1, 2, 3, 4, 5;
