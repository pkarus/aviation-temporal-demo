-- DATA-04a: typed passenger source normalization (declared derivation, build base).
--
-- Produces one row per raw PF / PH observation carrying:
--   * DV-43 typed normalized row hash under D-0012 `dv43-lp-v1`, source-system prefixed
--     (`FORWARD` for PF-01..PF-19, `HISTORICAL` for PH-01..PH-23);
--   * DV-46 source_row_token = source system, then the stable source row ID when present,
--     otherwise the source-system-prefixed DV-43.  Never built from an unqualified nullable ID;
--   * the typed canonical key components and DV-20 when every component is non-null;
--   * DV-22 passenger_key_status and, for historical rows, DV-47..DV-51 clock derivations.
--
-- No identity is invented here.  A row with a null key component and a null stable source row ID
-- gets no DV-20 and no invalid-observation identity: it is quarantined in 50_passenger.sql on the
-- deterministic semantic key (source system, DV-43, reason).

CREATE OR REPLACE TABLE MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION
  COMMENT = 'Typed union of every raw PASSENGER_FORWARD and PASSENGER_HISTORICAL observation with DV-43, DV-46, canonical key components, DV-22 key status and DV-47..DV-51 clock derivations. Declared derivation feeding PASSENGER_FLIGHT_CANONICAL, PASSENGER_SOURCE_LINEAGE, PASSENGER_FLIGHT_INVALID and PASSENGER_SOURCE_QUARANTINE.'
AS
WITH forward_typed AS (
  SELECT
    'FORWARD'::VARCHAR                          AS source_system,
    f.forward_source_row_id                     AS stable_source_row_id,
    f.marketing_carrier_internal                AS key_marketing_carrier_internal,
    f.flight_number                             AS key_flight_number,
    f.departure_station_code_iata               AS key_departure_station_code_iata,
    f.arrival_station_code_iata                 AS key_arrival_station_code_iata,
    f.operating_date                            AS key_operating_date,
    f.operating_carrier_internal,
    f.publish_date,
    f.service_type_iata,
    f.equipment_subtype_code_iata,
    CAST(f.total_seats AS FLOAT)                AS total_seats,
    f.is_codeshare,
    f.number_of_intermediate_stops,
    f.intermediate_stop_station_codes_iata,
    f.arrival_day_indicator,
    f.passenger_departure_time_local            AS plan_departure_local_timestamp,
    f.passenger_arrival_time_local              AS plan_arrival_local_timestamp,
    f.passenger_departure_time_utc              AS plan_departure_utc_timestamp,
    f.passenger_arrival_time_utc                AS plan_arrival_utc_timestamp,
    NULL::VARCHAR                               AS schedule_key,
    NULL::DATE                                  AS historical_effective_date,
    NULL::TIME                                  AS passenger_departure_local_time,
    NULL::TIME                                  AS passenger_arrival_local_time,
    NULL::TIME                                  AS passenger_departure_utc_time,
    NULL::TIME                                  AS passenger_arrival_utc_time,
    NULL::FLOAT                                 AS departure_utc_offset_minutes,
    NULL::FLOAT                                 AS arrival_utc_offset_minutes,
    CASE WHEN f.passenger_departure_time_utc IS NOT NULL AND f.passenger_arrival_time_utc IS NOT NULL
         THEN 'EXPLICIT_EXPANDED' ELSE 'UNRESOLVED_UTC_DATE' END::VARCHAR AS utc_date_status,
    SHA2(
      MODEL_INPUT.LP('FORWARD')
      || MODEL_INPUT.DV43_FIELD('PF-01','NUMBER(38,0)',  MODEL_INPUT.CANON_NUM(f.forward_source_row_id))
      || MODEL_INPUT.DV43_FIELD('PF-02','VARCHAR',       f.marketing_carrier_internal)
      || MODEL_INPUT.DV43_FIELD('PF-03','VARCHAR',       f.operating_carrier_internal)
      || MODEL_INPUT.DV43_FIELD('PF-04','NUMBER(38,0)',  MODEL_INPUT.CANON_NUM(f.flight_number))
      || MODEL_INPUT.DV43_FIELD('PF-05','DATE',          MODEL_INPUT.CANON_DATE(f.operating_date))
      || MODEL_INPUT.DV43_FIELD('PF-06','DATE',          MODEL_INPUT.CANON_DATE(f.publish_date))
      || MODEL_INPUT.DV43_FIELD('PF-07','VARCHAR',       f.service_type_iata)
      || MODEL_INPUT.DV43_FIELD('PF-08','VARCHAR',       f.departure_station_code_iata)
      || MODEL_INPUT.DV43_FIELD('PF-09','VARCHAR',       f.arrival_station_code_iata)
      || MODEL_INPUT.DV43_FIELD('PF-10','TIMESTAMP_NTZ', MODEL_INPUT.CANON_TS(f.passenger_departure_time_local))
      || MODEL_INPUT.DV43_FIELD('PF-11','TIMESTAMP_NTZ', MODEL_INPUT.CANON_TS(f.passenger_arrival_time_local))
      || MODEL_INPUT.DV43_FIELD('PF-12','TIMESTAMP_NTZ', MODEL_INPUT.CANON_TS(f.passenger_departure_time_utc))
      || MODEL_INPUT.DV43_FIELD('PF-13','TIMESTAMP_NTZ', MODEL_INPUT.CANON_TS(f.passenger_arrival_time_utc))
      || MODEL_INPUT.DV43_FIELD('PF-14','NUMBER(38,0)',  MODEL_INPUT.CANON_NUM(f.arrival_day_indicator))
      || MODEL_INPUT.DV43_FIELD('PF-15','VARCHAR',       f.equipment_subtype_code_iata)
      || MODEL_INPUT.DV43_FIELD('PF-16','NUMBER(38,0)',  MODEL_INPUT.CANON_NUM(f.total_seats))
      || MODEL_INPUT.DV43_FIELD('PF-17','BOOLEAN',       MODEL_INPUT.CANON_BOOL(f.is_codeshare))
      || MODEL_INPUT.DV43_FIELD('PF-18','NUMBER(38,0)',  MODEL_INPUT.CANON_NUM(f.number_of_intermediate_stops))
      || MODEL_INPUT.DV43_FIELD('PF-19','VARCHAR',       f.intermediate_stop_station_codes_iata)
    , 256)                                      AS typed_normalized_row_hash
  FROM SOURCE.PASSENGER_FORWARD f
), historical_typed AS (
  SELECT
    'HISTORICAL'::VARCHAR                       AS source_system,
    h.historical_source_row_id                  AS stable_source_row_id,
    h.marketing_carrier_internal                AS key_marketing_carrier_internal,
    h.flight_number                             AS key_flight_number,
    h.departure_station_code_iata               AS key_departure_station_code_iata,
    h.arrival_station_code_iata                 AS key_arrival_station_code_iata,
    h.operating_date                            AS key_operating_date,
    h.operating_carrier_internal,
    h.publish_date,
    h.service_type_iata,
    h.equipment_subtype_code_iata,
    h.total_seats,
    h.is_codeshare,
    h.number_of_intermediate_stops,
    h.intermediate_stop_station_codes_iata,
    h.arrival_day_indicator,
    -- DV-47 / DV-48 local plan instants.
    TIMESTAMP_NTZ_FROM_PARTS(h.operating_date, h.passenger_departure_local_time)
                                                AS plan_departure_local_timestamp,
    TIMESTAMP_NTZ_FROM_PARTS(DATEADD(DAY, COALESCE(h.arrival_day_indicator, 0), h.operating_date),
                             h.passenger_arrival_local_time)
                                                AS plan_arrival_local_timestamp,
    -- DV-49 / DV-50 under binding provisional D-0008: offset_minutes = local - UTC, so subtract.
    CASE WHEN h.departure_utc_offset_minutes IS NOT NULL
           AND h.departure_utc_offset_minutes = h.departure_utc_offset_minutes
           AND ABS(h.departure_utc_offset_minutes) < 1e15
         THEN DATEADD(MINUTE, -CAST(h.departure_utc_offset_minutes AS NUMBER(38,0)),
                      TIMESTAMP_NTZ_FROM_PARTS(h.operating_date, h.passenger_departure_local_time))
    END                                         AS plan_departure_utc_timestamp,
    CASE WHEN h.arrival_utc_offset_minutes IS NOT NULL
           AND h.arrival_utc_offset_minutes = h.arrival_utc_offset_minutes
           AND ABS(h.arrival_utc_offset_minutes) < 1e15
         THEN DATEADD(MINUTE, -CAST(h.arrival_utc_offset_minutes AS NUMBER(38,0)),
                      TIMESTAMP_NTZ_FROM_PARTS(DATEADD(DAY, COALESCE(h.arrival_day_indicator, 0), h.operating_date),
                                               h.passenger_arrival_local_time))
    END                                         AS plan_arrival_utc_timestamp,
    h.schedule_key,
    h.effective_date                            AS historical_effective_date,
    h.passenger_departure_local_time,
    h.passenger_arrival_local_time,
    h.passenger_departure_utc_time,
    h.passenger_arrival_utc_time,
    h.departure_utc_offset_minutes,
    h.arrival_utc_offset_minutes,
    CASE WHEN h.departure_utc_offset_minutes IS NOT NULL
           AND h.departure_utc_offset_minutes = h.departure_utc_offset_minutes
           AND ABS(h.departure_utc_offset_minutes) < 1e15
           AND h.arrival_utc_offset_minutes IS NOT NULL
           AND h.arrival_utc_offset_minutes = h.arrival_utc_offset_minutes
           AND ABS(h.arrival_utc_offset_minutes) < 1e15
           AND h.passenger_departure_local_time IS NOT NULL
           AND h.passenger_arrival_local_time IS NOT NULL
           AND h.operating_date IS NOT NULL
         THEN 'OFFSET_DERIVED' ELSE 'UNRESOLVED_UTC_DATE' END::VARCHAR AS utc_date_status,
    SHA2(
      MODEL_INPUT.LP('HISTORICAL')
      || MODEL_INPUT.DV43_FIELD('PH-01','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(h.historical_source_row_id))
      || MODEL_INPUT.DV43_FIELD('PH-02','VARCHAR',      h.schedule_key)
      || MODEL_INPUT.DV43_FIELD('PH-03','DATE',         MODEL_INPUT.CANON_DATE(h.publish_date))
      || MODEL_INPUT.DV43_FIELD('PH-04','DATE',         MODEL_INPUT.CANON_DATE(h.operating_date))
      || MODEL_INPUT.DV43_FIELD('PH-05','VARCHAR',      h.marketing_carrier_internal)
      || MODEL_INPUT.DV43_FIELD('PH-06','VARCHAR',      h.operating_carrier_internal)
      || MODEL_INPUT.DV43_FIELD('PH-07','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(h.flight_number))
      || MODEL_INPUT.DV43_FIELD('PH-08','VARCHAR',      h.service_type_iata)
      || MODEL_INPUT.DV43_FIELD('PH-09','DATE',         MODEL_INPUT.CANON_DATE(h.effective_date))
      || MODEL_INPUT.DV43_FIELD('PH-10','VARCHAR',      h.departure_station_code_iata)
      || MODEL_INPUT.DV43_FIELD('PH-11','VARCHAR',      h.arrival_station_code_iata)
      || MODEL_INPUT.DV43_FIELD('PH-12','TIME',         MODEL_INPUT.CANON_TIME(h.passenger_departure_local_time))
      || MODEL_INPUT.DV43_FIELD('PH-13','TIME',         MODEL_INPUT.CANON_TIME(h.passenger_arrival_local_time))
      || MODEL_INPUT.DV43_FIELD('PH-14','TIME',         MODEL_INPUT.CANON_TIME(h.passenger_departure_utc_time))
      || MODEL_INPUT.DV43_FIELD('PH-15','TIME',         MODEL_INPUT.CANON_TIME(h.passenger_arrival_utc_time))
      || MODEL_INPUT.DV43_FIELD('PH-16','FLOAT',        MODEL_INPUT.CANON_FLOAT(h.departure_utc_offset_minutes))
      || MODEL_INPUT.DV43_FIELD('PH-17','FLOAT',        MODEL_INPUT.CANON_FLOAT(h.arrival_utc_offset_minutes))
      || MODEL_INPUT.DV43_FIELD('PH-18','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(h.arrival_day_indicator))
      || MODEL_INPUT.DV43_FIELD('PH-19','VARCHAR',      h.equipment_subtype_code_iata)
      || MODEL_INPUT.DV43_FIELD('PH-20','FLOAT',        MODEL_INPUT.CANON_FLOAT(h.total_seats))
      || MODEL_INPUT.DV43_FIELD('PH-21','BOOLEAN',      MODEL_INPUT.CANON_BOOL(h.is_codeshare))
      || MODEL_INPUT.DV43_FIELD('PH-22','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(h.number_of_intermediate_stops))
      || MODEL_INPUT.DV43_FIELD('PH-23','VARCHAR',      h.intermediate_stop_station_codes_iata)
    , 256)                                      AS typed_normalized_row_hash
  FROM SOURCE.PASSENGER_HISTORICAL h
), unioned AS (
  SELECT * FROM forward_typed
  UNION ALL
  SELECT * FROM historical_typed
)
SELECT
  u.source_system,
  u.stable_source_row_id,
  u.typed_normalized_row_hash,
  u.source_system || '|' ||
    COALESCE(TO_VARCHAR(u.stable_source_row_id), u.typed_normalized_row_hash) AS source_row_token,
  IFF(u.stable_source_row_id IS NOT NULL, 'STABLE_SOURCE_ROW_ID', 'DV43_HASH_FALLBACK')::VARCHAR
                                                                              AS source_row_token_basis,
  u.key_marketing_carrier_internal,
  u.key_flight_number,
  u.key_departure_station_code_iata,
  u.key_arrival_station_code_iata,
  u.key_operating_date,
  CASE WHEN u.key_marketing_carrier_internal IS NOT NULL
        AND u.key_flight_number IS NOT NULL
        AND u.key_departure_station_code_iata IS NOT NULL
        AND u.key_arrival_station_code_iata IS NOT NULL
        AND u.key_operating_date IS NOT NULL
       THEN u.key_marketing_carrier_internal || '|' || TO_VARCHAR(u.key_flight_number) || '|'
            || u.key_departure_station_code_iata || '|' || u.key_arrival_station_code_iata || '|'
            || MODEL_INPUT.CANON_DATE(u.key_operating_date)
  END                                                                         AS passenger_flight_key,
  ARRAY_TO_STRING(ARRAY_COMPACT(ARRAY_CONSTRUCT(
    IFF(u.key_marketing_carrier_internal IS NULL, 'marketing_carrier_internal', NULL),
    IFF(u.key_flight_number IS NULL, 'flight_number', NULL),
    IFF(u.key_departure_station_code_iata IS NULL, 'departure_station_code_iata', NULL),
    IFF(u.key_arrival_station_code_iata IS NULL, 'arrival_station_code_iata', NULL),
    IFF(u.key_operating_date IS NULL, 'operating_date', NULL)
  )), ',')                                                                    AS missing_key_components,
  CASE
    WHEN u.key_marketing_carrier_internal IS NOT NULL
     AND u.key_flight_number IS NOT NULL
     AND u.key_departure_station_code_iata IS NOT NULL
     AND u.key_arrival_station_code_iata IS NOT NULL
     AND u.key_operating_date IS NOT NULL                       THEN 'VALID'
    WHEN u.stable_source_row_id IS NOT NULL                     THEN 'INVALID_PASSENGER_KEY'
    ELSE 'QUARANTINED'
  END::VARCHAR                                                                AS passenger_key_status,
  u.operating_carrier_internal,
  u.publish_date,
  u.service_type_iata,
  u.equipment_subtype_code_iata,
  u.total_seats,
  u.is_codeshare,
  u.number_of_intermediate_stops,
  u.intermediate_stop_station_codes_iata,
  u.arrival_day_indicator,
  u.plan_departure_local_timestamp,
  u.plan_arrival_local_timestamp,
  u.plan_departure_utc_timestamp,
  u.plan_arrival_utc_timestamp,
  u.utc_date_status,
  u.schedule_key,
  u.historical_effective_date,
  u.passenger_departure_local_time,
  u.passenger_arrival_local_time,
  u.passenger_departure_utc_time,
  u.passenger_arrival_utc_time,
  u.departure_utc_offset_minutes,
  u.arrival_utc_offset_minutes
FROM unioned u;
