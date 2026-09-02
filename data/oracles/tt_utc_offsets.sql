-- ============================================================================
-- TT-UTC-OFFSETS (HT-25, D-0008) -- independent oracle over SOURCE.
--
-- Three distinct clock authorities, in precedence order:
--   1. PF-12/PF-13 source-expanded timestamps win outright: EXPLICIT_EXPANDED,
--      never recomputed, and AP-09 does not override them.
--   2. PH explicit offsets under D-0008 (offset_minutes = local - UTC):
--        DV-47 = PH-04 + PH-12
--        DV-48 = PH-04 + PH-18 calendar days + PH-13
--        DV-49 = DV-47 - PH-16 minutes
--        DV-50 = DV-48 - PH-17 minutes
--      Spring-forward, fall-back, a Phoenix no-DST control and a local->UTC
--      next-day crossing are all supplied by explicit source offsets; no DST
--      rule is inferred from AP-09.
--   3. Schedule SS-23/SS-24 are UTC TIME without any date or offset evidence,
--      so they stay UNRESOLVED_UTC_DATE. AP-09 must not repair them.
-- ============================================================================
WITH historical AS (
    SELECT
        historical_source_row_id AS ord_id,
        operating_date, passenger_departure_local_time, passenger_arrival_local_time,
        arrival_day_indicator, departure_utc_offset_minutes, arrival_utc_offset_minutes
    FROM PK_AVIATION_TEMPORAL.SOURCE.PASSENGER_HISTORICAL
    WHERE historical_source_row_id IN (7301, 7302, 7303, 7304, 7305, 7306, 7309, 7310)
),
ph_rows AS (
    SELECT
        CASE ord_id WHEN 7301 THEN 1 WHEN 7302 THEN 2 WHEN 7303 THEN 3 WHEN 7304 THEN 4
                    WHEN 7305 THEN 5 WHEN 7306 THEN 6 WHEN 7309 THEN 9 ELSE 10 END AS ord,
        IFF(ord_id IN (7309, 7310), 'NON_OPERATIONAL_NORMALIZER_UNIT_CASE', 'SYNTHETIC_US_FLIGHT') AS case_scope,
        TIMESTAMP_NTZ_FROM_PARTS(operating_date, passenger_departure_local_time) AS local_departure,
        TIMESTAMP_NTZ_FROM_PARTS(DATEADD('day', COALESCE(arrival_day_indicator, 0), operating_date),
                                 passenger_arrival_local_time)                   AS local_arrival,
        departure_utc_offset_minutes AS departure_offset_minutes,
        arrival_utc_offset_minutes   AS arrival_offset_minutes,
        IFF(departure_utc_offset_minutes IS NULL, NULL,
            DATEADD('minute', -departure_utc_offset_minutes::NUMBER(38,0),
                    TIMESTAMP_NTZ_FROM_PARTS(operating_date, passenger_departure_local_time))) AS utc_departure,
        IFF(arrival_utc_offset_minutes IS NULL, NULL,
            DATEADD('minute', -arrival_utc_offset_minutes::NUMBER(38,0),
                    TIMESTAMP_NTZ_FROM_PARTS(DATEADD('day', COALESCE(arrival_day_indicator, 0), operating_date),
                                             passenger_arrival_local_time)))                   AS utc_arrival,
        IFF(departure_utc_offset_minutes IS NULL OR arrival_utc_offset_minutes IS NULL,
            'UNRESOLVED_UTC_DATE', 'OFFSET_DERIVED')                                           AS resolution_status
    FROM historical
),
pf_rows AS (
    SELECT 7 AS ord, 'SYNTHETIC_US_FLIGHT' AS case_scope,
           passenger_departure_time_local AS local_departure,
           passenger_arrival_time_local   AS local_arrival,
           NULL::FLOAT AS departure_offset_minutes,
           NULL::FLOAT AS arrival_offset_minutes,
           passenger_departure_time_utc   AS utc_departure,
           passenger_arrival_time_utc     AS utc_arrival,
           'EXPLICIT_EXPANDED'            AS resolution_status
    FROM PK_AVIATION_TEMPORAL.SOURCE.PASSENGER_FORWARD
    WHERE forward_source_row_id = 6201
),
ss_rows AS (
    -- SS-23/SS-24 remain TIME-only lineage. The fixture supplies 2026-09-07 as
    -- the separate operating date used to build local timestamps; the source
    -- still supplies no UTC date, expanded timestamp or offset.
    SELECT 8 AS ord, 'SYNTHETIC_US_FLIGHT' AS case_scope,
           TIMESTAMP_NTZ_FROM_PARTS(DATE '2026-09-07', passenger_departure_local_time) AS local_departure,
           TIMESTAMP_NTZ_FROM_PARTS(DATEADD('day', COALESCE(arrival_day_indicator, 0), DATE '2026-09-07'),
                                    passenger_arrival_local_time)                      AS local_arrival,
           NULL::FLOAT AS departure_offset_minutes,
           NULL::FLOAT AS arrival_offset_minutes,
           NULL::TIMESTAMP_NTZ AS utc_departure,
           NULL::TIMESTAMP_NTZ AS utc_arrival,
           'UNRESOLVED_UTC_DATE' AS resolution_status
    FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT
    WHERE schedule_key = 'SYN-SK-UTC-UNRESOLVED' AND publish_date = DATE '2026-10-19'
),
combined AS (
    SELECT * FROM ph_rows UNION ALL SELECT * FROM pf_rows UNION ALL SELECT * FROM ss_rows
)
SELECT
    case_scope,
    TO_VARCHAR(local_departure, 'YYYY-MM-DD"T"HH24:MI:SS') AS local_departure,
    TO_VARCHAR(local_arrival,   'YYYY-MM-DD"T"HH24:MI:SS') AS local_arrival,
    departure_offset_minutes::FLOAT                        AS departure_offset_minutes,
    arrival_offset_minutes::FLOAT                          AS arrival_offset_minutes,
    TO_VARCHAR(utc_departure, 'YYYY-MM-DD"T"HH24:MI:SS')   AS utc_departure,
    TO_VARCHAR(utc_arrival,   'YYYY-MM-DD"T"HH24:MI:SS')   AS utc_arrival,
    resolution_status
FROM combined
ORDER BY ord
