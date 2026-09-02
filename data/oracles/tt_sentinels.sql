-- ============================================================================
-- TT-SENTINELS (HT-06, HT-07, HT-09) -- independent oracle over SOURCE.
--
-- Source 9999-12-31 means unknown future and never becomes a finite derived
-- bound. The derived open-interval sentinel 9999-01-01 is model-side only.
-- A finite AM-08 is EXCLUSIVE under D-0003: the previous day is eligible and
-- the boundary day itself is outside existence.
--
-- source_date and model_valid_to are computed from AH-102099 (unknown-future
-- provenance), AM-1004/AH-104001 (open existence) and AM-1002 (finite EOL).
-- case_id and assertion are declared labels.
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, unknown_future AS (
    SELECT 1 AS ord,
           MAX(h.end_event_date)                        AS source_date,
           MAX(d.valid_to)                              AS model_valid_to
    FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_HISTORY h
    LEFT JOIN daily_assignment d ON d.valid_to = h.end_event_date
    WHERE h.end_event_date = DATE '9999-12-31'
),
model_open AS (
    SELECT 2 AS ord,
           MAX(m.aircraft_end_of_life_date)             AS source_date,
           MAX(d.valid_to)                              AS model_valid_to
    FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER m
    JOIN daily_assignment d ON d.aircraft_id = m.aircraft_id
    WHERE m.aircraft_id = 1004 AND d.valid_to = DATE '9999-01-01'
),
finite_eol AS (
    SELECT 3 AS ord,
           MAX(m.aircraft_end_of_life_date)             AS source_date,
           MAX(d.valid_to)                              AS model_valid_to
    FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER m
    JOIN daily_assignment d ON d.aircraft_id = m.aircraft_id
    WHERE m.aircraft_id = 1002
)
SELECT TO_VARCHAR(source_date, 'YYYY-MM-DD')   AS source_date,
       TO_VARCHAR(model_valid_to, 'YYYY-MM-DD') AS model_valid_to
FROM (SELECT * FROM unknown_future UNION ALL SELECT * FROM model_open UNION ALL SELECT * FROM finite_eol)
ORDER BY ord
