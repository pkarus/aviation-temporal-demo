-- DATA-04a: actual flown legs and rotation self-reference validation.
--
-- Actual facts never overwrite plan facts and the plan never repairs actual continuity.
-- DV-45 actual_continuity_arrival_code is exactly AF-09.  AF-10 and DV-53 are reconciliation
-- evidence only: a non-null AF-10 that disagrees with AF-09 emits DIVERSION_ENDPOINT_CONFLICT and
-- terminates continuity regardless of the diversion flag, and never repairs AF-09.
-- DV-52/DV-53 map integer 0 to false and 1 to true; null or any other value is
-- UNKNOWN_OR_INVALID and excludes the leg from the strict operated chain while staying visible.
-- DV-38 trims AF-05, accepts ASCII digits only and casts to NUMBER(38,0); every other form keeps
-- the raw AF-05, emits INVALID_FLIGHT_NUMBER and is ineligible for exact or heuristic matching.

CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_FLIGHT
  COMMENT = 'Actual flown-leg observation. Grain AF-01. Carries AF-01..AF-20 as actual facts, DV-38 normalized flight number, DV-45 continuity arrival code, DV-52/DV-53 normalized flags, optional exact aircraft/airport/airline links, their resolution statuses and the raw codes. AF-06 is the source-local selected-day basis; AF-07 is UTC lineage and never substitutes for it.'
AS
SELECT
  a.flight_id,
  a.aircraft_id,
  ae.aircraft_id IS NOT NULL                             AS aircraft_link_exists,
  a.operating_carrier_code,
  a.marketing_carrier_code,
  a.flight_number                                        AS raw_flight_number,
  IFF(REGEXP_LIKE(TRIM(a.flight_number), '^[0-9]+$'),
      CAST(TRIM(a.flight_number) AS NUMBER(38,0)), NULL) AS normalized_flight_number,
  IFF(REGEXP_LIKE(TRIM(a.flight_number), '^[0-9]+$'),
      'NORMALIZED', 'INVALID_FLIGHT_NUMBER')::VARCHAR    AS flight_number_status,
  a.flight_departure_date,
  a.flight_departure_date_utc,
  a.departure_airport_code,
  a.arrival_airport_code,
  a.arrival_airport_code                                 AS actual_continuity_arrival_code,
  a.diverted_airport_code,
  a.is_cancelled                                         AS raw_is_cancelled,
  CASE WHEN a.is_cancelled = 0 THEN FALSE WHEN a.is_cancelled = 1 THEN TRUE END
                                                         AS is_cancelled_boolean,
  IFF(a.is_cancelled IN (0, 1), 'NORMALIZED',
      'UNKNOWN_OR_INVALID_CANCELLATION_FLAG')::VARCHAR   AS cancellation_flag_status,
  a.is_diverted                                          AS raw_is_diverted,
  CASE WHEN a.is_diverted = 0 THEN FALSE WHEN a.is_diverted = 1 THEN TRUE END
                                                         AS is_diverted_boolean,
  IFF(a.is_diverted IN (0, 1), 'NORMALIZED',
      'UNKNOWN_OR_INVALID_DIVERSION_FLAG')::VARCHAR      AS diversion_flag_status,
  (a.diverted_airport_code IS NOT NULL
   AND NOT EQUAL_NULL(a.diverted_airport_code, a.arrival_airport_code))
                                                         AS diversion_endpoint_conflict,
  a.actual_gate_departure_time_utc,
  a.actual_gate_arrival_time_utc,
  a.actual_gate_departure_time_local,
  a.actual_gate_arrival_time_local,
  a.aircraft_type                                        AS actual_source_aircraft_type,
  a.aircraft_code_iata                                   AS actual_source_aircraft_code_iata,
  a.aircraft_family                                      AS actual_source_aircraft_family,
  a.next_flight_id,
  dep.single_candidate_id                                AS actual_origin_airport_id,
  CASE WHEN a.departure_airport_code IS NULL THEN 'INVALID_INPUT'
       WHEN dep.raw_code IS NULL THEN 'UNRESOLVED' ELSE dep.resolution_status END::VARCHAR
                                                         AS actual_origin_airport_resolution_status,
  arr.single_candidate_id                                AS actual_destination_airport_id,
  CASE WHEN a.arrival_airport_code IS NULL THEN 'INVALID_INPUT'
       WHEN arr.raw_code IS NULL THEN 'UNRESOLVED' ELSE arr.resolution_status END::VARCHAR
                                                         AS actual_destination_airport_resolution_status,
  div.single_candidate_id                                AS diverted_airport_id,
  CASE WHEN a.diverted_airport_code IS NULL THEN 'INVALID_INPUT'
       WHEN div.raw_code IS NULL THEN 'UNRESOLVED' ELSE div.resolution_status END::VARCHAR
                                                         AS diverted_airport_resolution_status,
  opc.single_candidate_id                                AS operating_airline_id,
  CASE WHEN a.operating_carrier_code IS NULL THEN 'INVALID_INPUT'
       WHEN opc.raw_code IS NULL THEN 'UNRESOLVED' ELSE opc.resolution_status END::VARCHAR
                                                         AS operating_airline_resolution_status,
  mkc.single_candidate_id                                AS marketing_airline_id,
  CASE WHEN a.marketing_carrier_code IS NULL THEN 'INVALID_INPUT'
       WHEN mkc.raw_code IS NULL THEN 'UNRESOLVED' ELSE mkc.resolution_status END::VARCHAR
                                                         AS marketing_airline_resolution_status
FROM SOURCE.AIRCRAFT_FLIGHT a
LEFT JOIN MODEL_INPUT.AIRCRAFT_ELIGIBLE ae ON ae.aircraft_id = a.aircraft_id
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE dep
  ON dep.method = 'AIRPORT_INTERNAL_ID_EXACT' AND dep.raw_code = a.departure_airport_code
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE arr
  ON arr.method = 'AIRPORT_INTERNAL_ID_EXACT' AND arr.raw_code = a.arrival_airport_code
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE div
  ON div.method = 'AIRPORT_INTERNAL_ID_EXACT' AND div.raw_code = a.diverted_airport_code
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE opc
  ON opc.method = 'AIRLINE_INTERNAL_ID_EXACT' AND opc.raw_code = a.operating_carrier_code
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE mkc
  ON mkc.method = 'AIRLINE_INTERNAL_ID_EXACT' AND mkc.raw_code = a.marketing_carrier_code
WHERE a.flight_id IS NOT NULL;

-- ---------------------------------------------------------------------------------------------
-- ROTATION_LINK_VALIDATION.
-- A null next link is a terminal fact, not a nullable identity, so target_token is the literal
-- NO_TARGET.  Anomaly precedence, highest first:
--   leg level : UNKNOWN_OR_INVALID_CANCELLATION_FLAG, CANCELLED, MISSING_TIME  (link_outcome EXCLUDED)
--               DIVERSION_ENDPOINT_CONFLICT                                    (link_outcome REJECTED)
--   link level: SELF_LOOP, CYCLE, MISSING_TARGET, DIFFERENT_AIRCRAFT,
--               OUTSIDE_SELECTED_DAY, BACKWARD_TIME, BROKEN_CONTINUITY,
--               TARGET_NOT_OPERATED                                            (link_outcome REJECTED)
-- CYCLE outranks BACKWARD_TIME and BROKEN_CONTINUITY so both members of a cycle carry the same
-- class; all member evidence is retained and is_cycle_representative marks the minimum flight_id
-- so a consumer can emit exactly one component-level row.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.ROTATION_LINK_VALIDATION
  COMMENT = 'Validated actual rotation self-reference. Grain (AF-01, target_token) where target_token is AF-20 rendered as text or the literal NO_TARGET. Carries DV-24 link status, DV-25 anomaly class, the selected local date basis AF-06 and actual endpoint/time evidence only. Planned values are never used.'
AS
WITH edges AS (
  SELECT f.flight_id AS src, f.next_flight_id AS dst
  FROM MODEL_INPUT.AIRCRAFT_FLIGHT f
  JOIN MODEL_INPUT.AIRCRAFT_FLIGHT t ON t.flight_id = f.next_flight_id
  WHERE f.next_flight_id IS NOT NULL
), reach (src, dst, depth) AS (
  SELECT e.src, e.dst, 1 FROM edges e
  UNION ALL
  SELECT r.src, e.dst, r.depth + 1
  FROM reach r JOIN edges e ON e.src = r.dst
  WHERE r.depth < 32
), cycle_component AS (
  SELECT r1.src AS flight_id, MIN(r1.dst) AS cycle_component_id
  FROM reach r1
  JOIN reach r2 ON r2.src = r1.dst AND r2.dst = r1.src
  WHERE EXISTS (SELECT 1 FROM reach rs WHERE rs.src = r1.src AND rs.dst = r1.src)
  GROUP BY r1.src
), validated AS (
  SELECT
    f.flight_id,
    COALESCE(TO_VARCHAR(f.next_flight_id), 'NO_TARGET')          AS target_token,
    f.next_flight_id,
    f.aircraft_id,
    f.flight_departure_date                                      AS selected_local_date,
    f.actual_gate_departure_time_utc,
    f.actual_gate_arrival_time_utc,
    f.departure_airport_code                                     AS actual_origin_code,
    f.actual_continuity_arrival_code,
    f.diverted_airport_code,
    f.is_cancelled_boolean,
    f.cancellation_flag_status,
    f.is_diverted_boolean,
    f.diversion_flag_status,
    f.diversion_endpoint_conflict,
    t.flight_id                                                  AS target_flight_id,
    t.aircraft_id                                                AS target_aircraft_id,
    t.flight_departure_date                                      AS target_selected_local_date,
    t.actual_gate_departure_time_utc                             AS target_departure_time_utc,
    t.departure_airport_code                                     AS target_origin_code,
    t.is_cancelled_boolean                                       AS target_is_cancelled_boolean,
    t.cancellation_flag_status                                   AS target_cancellation_flag_status,
    cc.cycle_component_id,
    CASE
      -- leg-level exclusions: the leg is retained but never joins a strict operated chain
      WHEN f.cancellation_flag_status = 'UNKNOWN_OR_INVALID_CANCELLATION_FLAG'
                                                       THEN 'UNKNOWN_OR_INVALID_CANCELLATION_FLAG'
      WHEN f.is_cancelled_boolean                      THEN 'CANCELLED'
      WHEN f.actual_gate_departure_time_utc IS NULL
        OR f.actual_gate_arrival_time_utc IS NULL      THEN 'MISSING_TIME'
      -- leg-level reconciliation failure terminates continuity
      WHEN f.diversion_endpoint_conflict               THEN 'DIVERSION_ENDPOINT_CONFLICT'
      -- link-level
      WHEN f.next_flight_id IS NULL                    THEN NULL
      WHEN f.next_flight_id = f.flight_id              THEN 'SELF_LOOP'
      WHEN cc.cycle_component_id IS NOT NULL           THEN 'CYCLE'
      WHEN t.flight_id IS NULL                         THEN 'MISSING_TARGET'
      WHEN f.aircraft_id IS NULL OR t.aircraft_id IS NULL
        OR t.aircraft_id <> f.aircraft_id              THEN 'DIFFERENT_AIRCRAFT'
      WHEN NOT EQUAL_NULL(t.flight_departure_date, f.flight_departure_date)
                                                       THEN 'OUTSIDE_SELECTED_DAY'
      WHEN t.actual_gate_departure_time_utc IS NULL
        OR t.actual_gate_departure_time_utc < f.actual_gate_arrival_time_utc
                                                       THEN 'BACKWARD_TIME'
      WHEN f.actual_continuity_arrival_code IS NULL
        OR t.departure_airport_code IS NULL
        OR t.departure_airport_code <> f.actual_continuity_arrival_code
                                                       THEN 'BROKEN_CONTINUITY'
      WHEN t.cancellation_flag_status <> 'NORMALIZED'
        OR t.is_cancelled_boolean
        OR t.actual_gate_arrival_time_utc IS NULL      THEN 'TARGET_NOT_OPERATED'
      ELSE NULL
    END::VARCHAR                                                 AS rotation_anomaly_class
  FROM MODEL_INPUT.AIRCRAFT_FLIGHT f
  LEFT JOIN MODEL_INPUT.AIRCRAFT_FLIGHT t ON t.flight_id = f.next_flight_id
  LEFT JOIN cycle_component cc ON cc.flight_id = f.flight_id
)
SELECT
  v.flight_id,
  v.target_token,
  v.next_flight_id,
  v.aircraft_id,
  v.selected_local_date,
  'AF_06_SOURCE_LOCAL_DEPARTURE_DATE'::VARCHAR                   AS selected_date_basis,
  CASE
    WHEN v.rotation_anomaly_class IN ('UNKNOWN_OR_INVALID_CANCELLATION_FLAG', 'CANCELLED', 'MISSING_TIME')
                                                       THEN 'EXCLUDED'
    WHEN v.rotation_anomaly_class IS NOT NULL          THEN 'REJECTED'
    WHEN v.next_flight_id IS NULL                      THEN 'TERMINAL_NO_TARGET'
    ELSE 'ACCEPTED'
  END::VARCHAR                                                   AS rotation_link_status,
  v.rotation_anomaly_class,
  (v.rotation_anomaly_class IS NULL AND v.next_flight_id IS NOT NULL) AS is_accepted_link,
  v.cycle_component_id,
  (v.cycle_component_id IS NOT NULL AND v.cycle_component_id = v.flight_id)
                                                                 AS is_cycle_representative,
  v.actual_origin_code,
  v.actual_continuity_arrival_code,
  v.diverted_airport_code,
  v.diversion_endpoint_conflict,
  v.actual_gate_departure_time_utc,
  v.actual_gate_arrival_time_utc,
  v.is_cancelled_boolean,
  v.cancellation_flag_status,
  v.is_diverted_boolean,
  v.diversion_flag_status,
  v.target_flight_id,
  v.target_aircraft_id,
  v.target_selected_local_date,
  v.target_departure_time_utc,
  v.target_origin_code,
  v.target_is_cancelled_boolean
FROM validated v;
