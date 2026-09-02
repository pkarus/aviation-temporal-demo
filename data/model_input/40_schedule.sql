-- DATA-04a: schedule canonical observations, routes and route states.
--
-- P0-05 / P0-06:
--   * only SC dates with is_present = true AND is_complete = true drive presence or change
--     inference; incomplete and missing dates are retained as diagnostics and can never create a
--     removal, addition, closure or market exit;
--   * itinerary variants are reduced deterministically inside (SS-01, SS-03);
--   * knowledge versioning is partitioned by SS-01, never by route, so one Route may carry many
--     concurrently open RouteState rows.  No one-open-per-route constraint exists anywhere here;
--   * a repeated unchanged eligible observation contributes lineage but mints no state.

CREATE OR REPLACE TABLE MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION
  COMMENT = 'At most one deterministically selected schedule observation per (SS-01, SS-03). Ranked by SS-22 desc, SS-30 desc, SS-39 asc, SS-40 asc with business nulls last; reordering raw input cannot change the selection. Carries snapshot eligibility (SC-02/SC-03), the DV-12 route key status, the watched-content signature over SS-04..SS-38, and DV-26/DV-27 cabin derivations for retained diagnostics.'
AS
WITH raw_ranked AS (
  SELECT
    s.*,
    COUNT(*)      OVER (PARTITION BY s.schedule_key, s.publish_date) AS raw_observation_count,
    COUNT(*)      OVER (PARTITION BY s.schedule_key, s.publish_date, s.normalized_row_hash)
                                                                     AS semantic_duplicate_count,
    ROW_NUMBER()  OVER (
      PARTITION BY s.schedule_key, s.publish_date
      ORDER BY s.weekly_frequency DESC NULLS LAST,
               s.total_seats DESC NULLS LAST,
               s.itinerary_variation_identifier ASC NULLS LAST,
               s.normalized_row_hash ASC
    )                                                                AS selection_rank
  FROM SOURCE.SCHEDULE_SNAPSHOT s
  WHERE s.schedule_key IS NOT NULL AND s.publish_date IS NOT NULL
), selected AS (
  SELECT * FROM raw_ranked WHERE selection_rank = 1
)
SELECT
  x.schedule_key,
  x.publish_date,
  x.schedule_key_readable,
  x.normalized_row_hash,
  x.itinerary_variation_identifier,
  x.raw_observation_count,
  x.semantic_duplicate_count,
  'WEEKLY_FREQ_DESC,TOTAL_SEATS_DESC,ITIN_VAR_ASC,ROW_HASH_ASC'::VARCHAR AS selection_rule,
  cal.is_present                                            AS snapshot_is_present,
  cal.is_complete                                           AS snapshot_is_complete,
  COALESCE(cal.is_present, FALSE) AND COALESCE(cal.is_complete, FALSE)
                                                            AS is_eligible_snapshot,
  cal.validation_status                                     AS snapshot_validation_status,
  cal.source_lineage_id                                     AS snapshot_source_lineage_id,
  -- watched schedule content SS-04 .. SS-38
  x.marketing_carrier_internal,
  x.operating_carrier_internal,
  x.flight_number,
  x.service_type_iata,
  x.effective_date,
  x.discontinue_date,
  x.departure_station_code_iata,
  x.arrival_station_code_iata,
  x.departure_terminal,
  x.arrival_terminal,
  x.is_operating_monday,
  x.is_operating_tuesday,
  x.is_operating_wednesday,
  x.is_operating_thursday,
  x.is_operating_friday,
  x.is_operating_saturday,
  x.is_operating_sunday,
  x.days_pattern,
  x.weekly_frequency,
  x.passenger_departure_utc_time,
  x.passenger_arrival_utc_time,
  x.passenger_departure_local_time,
  x.passenger_arrival_local_time,
  x.arrival_day_indicator,
  x.scheduled_block_minutes,
  x.equipment_subtype_code_iata,
  x.total_seats,
  x.first_class_seats,
  x.business_class_seats,
  x.premium_economy_seats,
  x.economy_class_seats,
  x.is_codeshare,
  x.codeshare_carrier_internal,
  x.number_of_intermediate_stops,
  x.intermediate_stop_station_codes_iata,
  -- DV-12 route key.  A null component yields INVALID_ROUTE_KEY evidence and no Route identity,
  -- while the raw observation stays counted and can still produce exact schedule-key changes.
  CASE WHEN x.departure_station_code_iata IS NOT NULL AND x.arrival_station_code_iata IS NOT NULL
       THEN x.departure_station_code_iata || '->' || x.arrival_station_code_iata END AS route_id,
  IFF(x.departure_station_code_iata IS NOT NULL AND x.arrival_station_code_iata IS NOT NULL,
      'VALID', 'INVALID_ROUTE_KEY')::VARCHAR                 AS route_key_status,
  -- null-safe watched-content signature over SS-04 .. SS-38
  SHA2(
      MODEL_INPUT.DV43_FIELD('SS-04','VARCHAR',      x.marketing_carrier_internal)
   || MODEL_INPUT.DV43_FIELD('SS-05','VARCHAR',      x.operating_carrier_internal)
   || MODEL_INPUT.DV43_FIELD('SS-06','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(x.flight_number))
   || MODEL_INPUT.DV43_FIELD('SS-07','VARCHAR',      x.service_type_iata)
   || MODEL_INPUT.DV43_FIELD('SS-08','DATE',         MODEL_INPUT.CANON_DATE(x.effective_date))
   || MODEL_INPUT.DV43_FIELD('SS-09','DATE',         MODEL_INPUT.CANON_DATE(x.discontinue_date))
   || MODEL_INPUT.DV43_FIELD('SS-10','VARCHAR',      x.departure_station_code_iata)
   || MODEL_INPUT.DV43_FIELD('SS-11','VARCHAR',      x.arrival_station_code_iata)
   || MODEL_INPUT.DV43_FIELD('SS-12','VARCHAR',      x.departure_terminal)
   || MODEL_INPUT.DV43_FIELD('SS-13','VARCHAR',      x.arrival_terminal)
   || MODEL_INPUT.DV43_FIELD('SS-14','BOOLEAN',      MODEL_INPUT.CANON_BOOL(x.is_operating_monday))
   || MODEL_INPUT.DV43_FIELD('SS-15','BOOLEAN',      MODEL_INPUT.CANON_BOOL(x.is_operating_tuesday))
   || MODEL_INPUT.DV43_FIELD('SS-16','BOOLEAN',      MODEL_INPUT.CANON_BOOL(x.is_operating_wednesday))
   || MODEL_INPUT.DV43_FIELD('SS-17','BOOLEAN',      MODEL_INPUT.CANON_BOOL(x.is_operating_thursday))
   || MODEL_INPUT.DV43_FIELD('SS-18','BOOLEAN',      MODEL_INPUT.CANON_BOOL(x.is_operating_friday))
   || MODEL_INPUT.DV43_FIELD('SS-19','BOOLEAN',      MODEL_INPUT.CANON_BOOL(x.is_operating_saturday))
   || MODEL_INPUT.DV43_FIELD('SS-20','BOOLEAN',      MODEL_INPUT.CANON_BOOL(x.is_operating_sunday))
   || MODEL_INPUT.DV43_FIELD('SS-21','VARCHAR',      x.days_pattern)
   || MODEL_INPUT.DV43_FIELD('SS-22','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(x.weekly_frequency))
   || MODEL_INPUT.DV43_FIELD('SS-23','TIME',         MODEL_INPUT.CANON_TIME(x.passenger_departure_utc_time))
   || MODEL_INPUT.DV43_FIELD('SS-24','TIME',         MODEL_INPUT.CANON_TIME(x.passenger_arrival_utc_time))
   || MODEL_INPUT.DV43_FIELD('SS-25','TIME',         MODEL_INPUT.CANON_TIME(x.passenger_departure_local_time))
   || MODEL_INPUT.DV43_FIELD('SS-26','TIME',         MODEL_INPUT.CANON_TIME(x.passenger_arrival_local_time))
   || MODEL_INPUT.DV43_FIELD('SS-27','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(x.arrival_day_indicator))
   || MODEL_INPUT.DV43_FIELD('SS-28','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(x.scheduled_block_minutes))
   || MODEL_INPUT.DV43_FIELD('SS-29','VARCHAR',      x.equipment_subtype_code_iata)
   || MODEL_INPUT.DV43_FIELD('SS-30','FLOAT',        MODEL_INPUT.CANON_FLOAT(x.total_seats))
   || MODEL_INPUT.DV43_FIELD('SS-31','FLOAT',        MODEL_INPUT.CANON_FLOAT(x.first_class_seats))
   || MODEL_INPUT.DV43_FIELD('SS-32','FLOAT',        MODEL_INPUT.CANON_FLOAT(x.business_class_seats))
   || MODEL_INPUT.DV43_FIELD('SS-33','FLOAT',        MODEL_INPUT.CANON_FLOAT(x.premium_economy_seats))
   || MODEL_INPUT.DV43_FIELD('SS-34','FLOAT',        MODEL_INPUT.CANON_FLOAT(x.economy_class_seats))
   || MODEL_INPUT.DV43_FIELD('SS-35','BOOLEAN',      MODEL_INPUT.CANON_BOOL(x.is_codeshare))
   || MODEL_INPUT.DV43_FIELD('SS-36','VARCHAR',      x.codeshare_carrier_internal)
   || MODEL_INPUT.DV43_FIELD('SS-37','NUMBER(38,0)', MODEL_INPUT.CANON_NUM(x.number_of_intermediate_stops))
   || MODEL_INPUT.DV43_FIELD('SS-38','VARCHAR',      x.intermediate_stop_station_codes_iata)
  , 256)                                                    AS watched_content_signature,
  -- DV-26 / DV-27 cabin reconciliation.  Raw SS-30..SS-34 are never overwritten.
  (x.economy_class_seats - x.premium_economy_seats)         AS economy_excluding_premium,
  CASE
    WHEN x.total_seats IS NULL OR x.first_class_seats IS NULL OR x.business_class_seats IS NULL
      OR x.premium_economy_seats IS NULL OR x.economy_class_seats IS NULL   THEN NULL
    WHEN x.total_seats < 0 OR x.first_class_seats < 0 OR x.business_class_seats < 0
      OR x.premium_economy_seats < 0 OR x.economy_class_seats < 0           THEN NULL
    WHEN x.premium_economy_seats > x.economy_class_seats                    THEN NULL
    ELSE x.first_class_seats + x.business_class_seats + x.premium_economy_seats
         + (x.economy_class_seats - x.premium_economy_seats)
  END                                                       AS exclusive_cabin_sum,
  CASE
    WHEN x.total_seats IS NULL OR x.first_class_seats IS NULL OR x.business_class_seats IS NULL
      OR x.premium_economy_seats IS NULL OR x.economy_class_seats IS NULL   THEN 'NULL_CABIN_VALUE'
    WHEN x.total_seats < 0 OR x.first_class_seats < 0 OR x.business_class_seats < 0
      OR x.premium_economy_seats < 0 OR x.economy_class_seats < 0           THEN 'NEGATIVE_CABIN_VALUE'
    WHEN x.premium_economy_seats > x.economy_class_seats                    THEN 'PREMIUM_EXCEEDS_ECONOMY'
    WHEN (x.first_class_seats + x.business_class_seats + x.premium_economy_seats
          + (x.economy_class_seats - x.premium_economy_seats)) <> x.total_seats
                                                                            THEN 'TOTAL_MISMATCH'
    ELSE 'RECONCILED'
  END::VARCHAR                                              AS cabin_quality_status,
  -- resolved carrier roles.  Marketing and operating stay separate; no generic airline owner.
  mkt.single_candidate_id                                   AS marketing_airline_id,
  CASE WHEN x.marketing_carrier_internal IS NULL THEN 'INVALID_INPUT'
       WHEN mkt.raw_code IS NULL THEN 'UNRESOLVED' ELSE mkt.resolution_status END::VARCHAR
                                                            AS marketing_airline_resolution_status,
  op.single_candidate_id                                    AS operating_airline_id,
  CASE WHEN x.operating_carrier_internal IS NULL THEN 'INVALID_INPUT'
       WHEN op.raw_code IS NULL THEN 'UNRESOLVED' ELSE op.resolution_status END::VARCHAR
                                                            AS operating_airline_resolution_status,
  csh.single_candidate_id                                   AS codeshare_airline_id,
  CASE WHEN x.codeshare_carrier_internal IS NULL THEN 'INVALID_INPUT'
       WHEN csh.raw_code IS NULL THEN 'UNRESOLVED' ELSE csh.resolution_status END::VARCHAR
                                                            AS codeshare_airline_resolution_status,
  orig.single_candidate_id                                  AS origin_airport_id,
  CASE WHEN x.departure_station_code_iata IS NULL THEN 'INVALID_INPUT'
       WHEN orig.raw_code IS NULL THEN 'UNRESOLVED' ELSE orig.resolution_status END::VARCHAR
                                                            AS origin_airport_resolution_status,
  dest.single_candidate_id                                  AS destination_airport_id,
  CASE WHEN x.arrival_station_code_iata IS NULL THEN 'INVALID_INPUT'
       WHEN dest.raw_code IS NULL THEN 'UNRESOLVED' ELSE dest.resolution_status END::VARCHAR
                                                            AS destination_airport_resolution_status,
  -- DV-28 under D-0007: only an unambiguous non-codeshare base row whose marketing and operating
  -- carriers resolve to the same airline is the physical-service representative.
  CASE
    WHEN x.is_codeshare IS NULL                                       THEN 'UNRESOLVED_PHYSICAL_SERVICE'
    WHEN x.is_codeshare                                               THEN 'UNRESOLVED_PHYSICAL_SERVICE'
    WHEN mkt.resolution_status IS DISTINCT FROM 'EXACT'               THEN 'UNRESOLVED_PHYSICAL_SERVICE'
    WHEN op.resolution_status IS DISTINCT FROM 'EXACT'                THEN 'UNRESOLVED_PHYSICAL_SERVICE'
    WHEN mkt.single_candidate_id IS DISTINCT FROM op.single_candidate_id
                                                                      THEN 'UNRESOLVED_PHYSICAL_SERVICE'
    ELSE 'PHYSICAL_SERVICE_REPRESENTATIVE'
  END::VARCHAR                                              AS physical_service_status,
  -- SS-23/SS-24 remain UTC TIME lineage; no UTC date is inferred from clock ordering.
  'UNRESOLVED_UTC_DATE'::VARCHAR                            AS utc_date_status
FROM selected x
LEFT JOIN SOURCE.SCHEDULE_SNAPSHOT_CALENDAR cal ON cal.expected_publish_date = x.publish_date
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE mkt
  ON mkt.method = 'AIRLINE_ALIAS_UNION_EXACT' AND mkt.raw_code = x.marketing_carrier_internal
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE op
  ON op.method  = 'AIRLINE_ALIAS_UNION_EXACT' AND op.raw_code  = x.operating_carrier_internal
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE csh
  ON csh.method = 'AIRLINE_ALIAS_UNION_EXACT' AND csh.raw_code = x.codeshare_carrier_internal
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE orig
  ON orig.method = 'AIRPORT_IATA_EXACT' AND orig.raw_code = x.departure_station_code_iata
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE dest
  ON dest.method = 'AIRPORT_IATA_EXACT' AND dest.raw_code = x.arrival_station_code_iata;

-- ---------------------------------------------------------------------------------------------
-- ROUTE: directional, carrier-agnostic, both components non-null.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.ROUTE
  COMMENT = 'Directional carrier-agnostic route identity DV-12 = SS-10 || ''->'' || SS-11, both components non-null. Raw planned codes are always retained; the airport links exist only for EXACT cardinality-one resolutions.'
AS
SELECT
  o.route_id,
  o.departure_station_code_iata                     AS origin_station_code_iata,
  o.arrival_station_code_iata                       AS destination_station_code_iata,
  MAX(o.origin_airport_id)                          AS origin_airport_id,
  MAX(o.origin_airport_resolution_status)           AS origin_airport_resolution_status,
  MAX(o.destination_airport_id)                     AS destination_airport_id,
  MAX(o.destination_airport_resolution_status)      AS destination_airport_resolution_status,
  COUNT(*)                                          AS canonical_observation_count,
  COUNT(DISTINCT o.schedule_key)                    AS distinct_schedule_key_count
FROM MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION o
WHERE o.route_key_status = 'VALID'
GROUP BY o.route_id, o.departure_station_code_iata, o.arrival_station_code_iata;

-- ---------------------------------------------------------------------------------------------
-- ROUTE_STATE: knowledge-clock segments partitioned by SS-01.
--   valid_from = the eligible SS-03 that opened the presence/content segment;
--   valid_to   = the next eligible SS-03 that proves a content change or an absence, else the
--                model open sentinel 9999-01-01.
-- Many concurrently open states on one route are valid and are deliberately NOT collapsed.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.ROUTE_STATE
  COMMENT = 'Schedule knowledge version. Grain DV-13 route_state_key = SS-01 || ''|'' || valid_from. Half-open knowledge interval DV-14/DV-15 partitioned by SS-01, never by route: one Route may have many concurrently open states and no uniqueness constraint over the route slot exists. Operating bounds SS-08/SS-09 stay inclusive. INVALID_ROUTE_KEY observations are excluded here but remain counted diagnostics on SCHEDULE_CANONICAL_OBSERVATION.'
AS
WITH eligible_dates AS (
  SELECT expected_publish_date AS publish_date,
         ROW_NUMBER() OVER (ORDER BY expected_publish_date) AS eligible_rank
  FROM SOURCE.SCHEDULE_SNAPSHOT_CALENDAR
  WHERE is_present AND is_complete
), previous_eligible AS (
  SELECT d.eligible_rank, d.publish_date,
         LAG(d.publish_date) OVER (ORDER BY d.eligible_rank) AS previous_eligible_publish_date
  FROM eligible_dates d
), gap AS (
  SELECT
    p.eligible_rank,
    p.publish_date,
    p.previous_eligible_publish_date,
    COUNT(c.expected_publish_date)                            AS skipped_calendar_date_count,
    LISTAGG(MODEL_INPUT.CANON_DATE(c.expected_publish_date), ',')
      WITHIN GROUP (ORDER BY c.expected_publish_date)         AS skipped_calendar_dates
  FROM previous_eligible p
  LEFT JOIN SOURCE.SCHEDULE_SNAPSHOT_CALENDAR c
    ON c.expected_publish_date > p.previous_eligible_publish_date
   AND c.expected_publish_date < p.publish_date
  GROUP BY p.eligible_rank, p.publish_date, p.previous_eligible_publish_date
), present AS (
  SELECT o.*, e.eligible_rank
  FROM MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION o
  JOIN eligible_dates e ON e.publish_date = o.publish_date
  WHERE o.is_eligible_snapshot AND o.route_key_status = 'VALID'
), sequenced AS (
  SELECT
    p.*,
    LAG(p.eligible_rank) OVER (PARTITION BY p.schedule_key ORDER BY p.eligible_rank)
                                                                     AS previous_eligible_rank,
    LAG(p.watched_content_signature) OVER (PARTITION BY p.schedule_key ORDER BY p.eligible_rank)
                                                                     AS previous_watched_content_signature
  FROM present p
), opened AS (
  SELECT
    s.*,
    CASE
      WHEN s.previous_eligible_rank IS NULL                                     THEN 'INITIAL'
      WHEN s.previous_eligible_rank <> s.eligible_rank - 1                      THEN 'REAPPEARANCE'
      WHEN s.previous_watched_content_signature <> s.watched_content_signature  THEN 'CONTENT_CHANGE'
      ELSE NULL
    END::VARCHAR AS segment_open_kind
  FROM sequenced s
), segmented AS (
  SELECT
    o.*,
    MAX(IFF(o.segment_open_kind IS NOT NULL, o.eligible_rank, NULL)) OVER (
      PARTITION BY o.schedule_key ORDER BY o.eligible_rank
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)              AS segment_open_rank
  FROM opened o
), agg AS (
  SELECT
    schedule_key,
    segment_open_rank,
    MIN(eligible_rank)                                               AS first_rank,
    MAX(eligible_rank)                                               AS last_rank,
    COUNT(*)                                                         AS contributing_snapshot_count
  FROM segmented
  GROUP BY schedule_key, segment_open_rank
)
SELECT
  seg.schedule_key || '|' || MODEL_INPUT.CANON_DATE(seg.publish_date)   AS route_state_key,
  seg.schedule_key,
  seg.route_id,
  seg.publish_date                                                     AS knowledge_valid_from,
  COALESCE(nxt.publish_date, DATE '9999-01-01')                        AS knowledge_valid_to,
  (nxt.publish_date IS NULL)                                           AS is_open_state,
  seg.segment_open_kind,
  (seg.segment_open_kind = 'REAPPEARANCE')                             AS is_reappearance,
  CASE WHEN nxt.publish_date IS NULL THEN NULL
       WHEN nxt_present.schedule_key IS NOT NULL THEN 'CONTENT_CHANGE'
       ELSE 'ABSENCE' END::VARCHAR                                     AS closing_reason,
  opengap.previous_eligible_publish_date                               AS previous_eligible_publish_date_at_open,
  COALESCE(opengap.skipped_calendar_date_count, 0) > 0                 AS open_crosses_snapshot_gap,
  opengap.skipped_calendar_dates                                       AS open_skipped_calendar_dates,
  COALESCE(closegap.skipped_calendar_date_count, 0) > 0                AS close_crosses_snapshot_gap,
  closegap.skipped_calendar_dates                                      AS close_skipped_calendar_dates,
  a.contributing_snapshot_count,
  seg.normalized_row_hash,
  seg.schedule_key_readable,
  seg.itinerary_variation_identifier,
  -- watched schedule content of the segment-opening observation (identical across the segment)
  seg.marketing_carrier_internal,
  seg.operating_carrier_internal,
  seg.flight_number,
  seg.service_type_iata,
  seg.effective_date                                                   AS operating_effective_date,
  seg.discontinue_date                                                 AS operating_discontinue_date,
  seg.departure_station_code_iata,
  seg.arrival_station_code_iata,
  seg.departure_terminal,
  seg.arrival_terminal,
  seg.is_operating_monday,
  seg.is_operating_tuesday,
  seg.is_operating_wednesday,
  seg.is_operating_thursday,
  seg.is_operating_friday,
  seg.is_operating_saturday,
  seg.is_operating_sunday,
  seg.days_pattern,
  seg.weekly_frequency,
  seg.passenger_departure_utc_time,
  seg.passenger_arrival_utc_time,
  seg.passenger_departure_local_time,
  seg.passenger_arrival_local_time,
  seg.arrival_day_indicator,
  seg.scheduled_block_minutes,
  seg.equipment_subtype_code_iata,
  seg.total_seats,
  seg.first_class_seats,
  seg.business_class_seats,
  seg.premium_economy_seats,
  seg.economy_class_seats,
  seg.is_codeshare,
  seg.codeshare_carrier_internal,
  seg.number_of_intermediate_stops,
  seg.intermediate_stop_station_codes_iata,
  seg.watched_content_signature,
  seg.economy_excluding_premium,
  seg.exclusive_cabin_sum,
  seg.cabin_quality_status,
  seg.marketing_airline_id,
  seg.marketing_airline_resolution_status,
  seg.operating_airline_id,
  seg.operating_airline_resolution_status,
  seg.codeshare_airline_id,
  seg.codeshare_airline_resolution_status,
  seg.origin_airport_id,
  seg.origin_airport_resolution_status,
  seg.destination_airport_id,
  seg.destination_airport_resolution_status,
  seg.physical_service_status,
  seg.utc_date_status
FROM agg a
JOIN segmented seg
  ON seg.schedule_key = a.schedule_key AND seg.eligible_rank = a.segment_open_rank
LEFT JOIN eligible_dates nxt ON nxt.eligible_rank = a.last_rank + 1
LEFT JOIN present nxt_present
  ON nxt_present.schedule_key = a.schedule_key AND nxt_present.eligible_rank = a.last_rank + 1
LEFT JOIN gap opengap  ON opengap.eligible_rank  = a.segment_open_rank
LEFT JOIN gap closegap ON closegap.eligible_rank = a.last_rank + 1;

CREATE OR REPLACE TABLE MODEL_INPUT.ROUTE_STATE_LINEAGE
  COMMENT = 'Every complete eligible snapshot observation that contributed to a coalesced RouteState, with the selected itinerary variant evidence. Grain (route_state_key, SS-03, SS-40).'
AS
WITH eligible_dates AS (
  SELECT expected_publish_date AS publish_date,
         ROW_NUMBER() OVER (ORDER BY expected_publish_date) AS eligible_rank
  FROM SOURCE.SCHEDULE_SNAPSHOT_CALENDAR
  WHERE is_present AND is_complete
), present AS (
  SELECT o.*, e.eligible_rank
  FROM MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION o
  JOIN eligible_dates e ON e.publish_date = o.publish_date
  WHERE o.is_eligible_snapshot AND o.route_key_status = 'VALID'
), sequenced AS (
  SELECT
    p.*,
    LAG(p.eligible_rank) OVER (PARTITION BY p.schedule_key ORDER BY p.eligible_rank)
                                                                     AS previous_eligible_rank,
    LAG(p.watched_content_signature) OVER (PARTITION BY p.schedule_key ORDER BY p.eligible_rank)
                                                                     AS previous_watched_content_signature
  FROM present p
), opened AS (
  SELECT
    s.*,
    CASE
      WHEN s.previous_eligible_rank IS NULL                                     THEN 'INITIAL'
      WHEN s.previous_eligible_rank <> s.eligible_rank - 1                      THEN 'REAPPEARANCE'
      WHEN s.previous_watched_content_signature <> s.watched_content_signature  THEN 'CONTENT_CHANGE'
      ELSE NULL
    END::VARCHAR AS segment_open_kind
  FROM sequenced s
), segmented AS (
  SELECT
    o.*,
    MAX(IFF(o.segment_open_kind IS NOT NULL, o.eligible_rank, NULL)) OVER (
      PARTITION BY o.schedule_key ORDER BY o.eligible_rank
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)              AS segment_open_rank
  FROM opened o
), opening_date AS (
  SELECT DISTINCT schedule_key, eligible_rank AS segment_open_rank, publish_date AS segment_open_date
  FROM segmented WHERE segment_open_kind IS NOT NULL
)
SELECT
  s.schedule_key || '|' || MODEL_INPUT.CANON_DATE(od.segment_open_date) AS route_state_key,
  s.schedule_key,
  s.publish_date,
  s.normalized_row_hash,
  s.itinerary_variation_identifier,
  s.raw_observation_count,
  s.semantic_duplicate_count,
  s.watched_content_signature,
  (s.eligible_rank = s.segment_open_rank)                              AS is_segment_opening_observation,
  s.snapshot_source_lineage_id,
  s.snapshot_validation_status
FROM segmented s
JOIN opening_date od
  ON od.schedule_key = s.schedule_key AND od.segment_open_rank = s.segment_open_rank;
