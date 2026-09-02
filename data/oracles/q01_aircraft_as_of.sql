-- ============================================================================
-- Q01 aircraft_as_of -- independent SQL oracle over PK_AVIATION_TEMPORAL.SOURCE
--
-- Parameters: aircraft_id (NUMBER(38,0)), as_of_date (DATE)
-- Order by  : aircraft_id ASC, as_of_date ASC
--
-- DV-33 per-dimension as-of status (SOURCE_CONTRACT.md):
--   OUTSIDE_EXISTENCE  as_of < existence_from OR as_of >= existence_to
--   NO_RECORDED_STATE  inside existence, before the first daily assignment
--   UNKNOWN_STATE      covered by a daily assignment whose dimension is
--                      null/unresolved (explicit gap; never backfilled)
--   OK                 covered by an exactly resolved daily assignment
-- Master-only AM-11..AM-14 are CURRENT_ONLY under D-0005 and are never used to
-- backfill a historical reconstruction.
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, params AS (
    SELECT {{aircraft_id}}::NUMBER(38,0) AS p_aircraft_id,
           '{{as_of_date}}'::DATE        AS p_as_of_date
),
subject AS (
    SELECT p.p_aircraft_id, p.p_as_of_date, e.existence_from, e.existence_to
    FROM params p
    LEFT JOIN aircraft_existence e ON e.aircraft_id = p.p_aircraft_id
),
visible AS (
    SELECT s.p_aircraft_id, s.p_as_of_date, d.*
    FROM subject s
    JOIN daily_assignment d
      ON d.aircraft_id = s.p_aircraft_id
     AND d.valid_from <= s.p_as_of_date
     AND s.p_as_of_date < d.valid_to
),
first_assignment AS (
    SELECT dimension, aircraft_id, MIN(valid_from) AS first_valid_from
    FROM daily_assignment
    GROUP BY dimension, aircraft_id
),
dims AS (
    SELECT 'aircraft_state' AS dimension UNION ALL
    SELECT 'aircraft_type'  UNION ALL
    SELECT 'engine_type'    UNION ALL
    SELECT 'aircraft_status'
),
per_dimension AS (
    SELECT
        s.p_aircraft_id, s.p_as_of_date, x.dimension,
        CASE
            WHEN s.existence_from IS NULL                       THEN 'OUTSIDE_EXISTENCE'
            WHEN s.p_as_of_date <  s.existence_from             THEN 'OUTSIDE_EXISTENCE'
            WHEN s.p_as_of_date >= s.existence_to               THEN 'OUTSIDE_EXISTENCE'
            WHEN v.dimension IS NULL                            THEN 'NO_RECORDED_STATE'
            WHEN NOT v.is_resolved                              THEN 'UNKNOWN_STATE'
            ELSE 'OK'
        END AS dim_status,
        v.definition_id, v.definition_label, v.engine_count, v.mixed_engine_set_complete,
        v.registration_number, v.base_airport_code_iata, v.lifecycle_status
    FROM subject s
    CROSS JOIN dims x
    LEFT JOIN visible v
           ON v.dimension = x.dimension
    LEFT JOIN first_assignment fa
           ON fa.dimension = x.dimension AND fa.aircraft_id = s.p_aircraft_id
),
pivoted AS (
    SELECT
        p_aircraft_id AS aircraft_id,
        p_as_of_date  AS as_of_date,
        MAX(IFF(dimension = 'aircraft_state',   dim_status, NULL)) AS aircraft_state_status,
        MAX(IFF(dimension = 'aircraft_type',    dim_status, NULL)) AS aircraft_type_status,
        MAX(IFF(dimension = 'engine_type',      dim_status, NULL)) AS engine_type_status,
        MAX(IFF(dimension = 'aircraft_status',  dim_status, NULL)) AS aircraft_status_status,
        MAX(IFF(dimension = 'aircraft_type'   AND dim_status = 'OK', definition_id,    NULL)) AS aircraft_type_id,
        MAX(IFF(dimension = 'aircraft_type'   AND dim_status = 'OK', definition_label, NULL)) AS aircraft_type,
        MAX(IFF(dimension = 'engine_type'     AND dim_status = 'OK', definition_id,    NULL)) AS engine_type_id,
        MAX(IFF(dimension = 'engine_type'     AND dim_status = 'OK', definition_label, NULL)) AS engine_type,
        MAX(IFF(dimension = 'engine_type'     AND dim_status = 'OK', engine_count,     NULL)) AS engine_count,
        MAX(IFF(dimension = 'engine_type'     AND dim_status = 'OK',
                IFF(mixed_engine_set_complete, 1, 0), NULL))                                 AS mixed_flag,
        MAX(IFF(dimension = 'aircraft_status' AND dim_status = 'OK', lifecycle_status, NULL)) AS lifecycle_status,
        MAX(IFF(dimension = 'aircraft_state'  AND dim_status = 'OK', registration_number, NULL))    AS registration_number,
        MAX(IFF(dimension = 'aircraft_state'  AND dim_status = 'OK', base_airport_code_iata, NULL)) AS base_airport_code_iata
    FROM per_dimension
    GROUP BY 1, 2
)
SELECT
    aircraft_id::NUMBER(38,0)                        AS aircraft_id,
    TO_VARCHAR(as_of_date, 'YYYY-MM-DD')             AS as_of_date,
    (aircraft_state_status  = 'OK'
     AND aircraft_type_status = 'OK'
     AND engine_type_status   = 'OK'
     AND aircraft_status_status = 'OK')              AS is_complete,
    aircraft_state_status,
    aircraft_type_status,
    engine_type_status,
    aircraft_status_status,
    aircraft_type_id,
    aircraft_type,
    engine_type_id,
    engine_type,
    engine_count::NUMBER(38,0)                       AS engine_count,
    IFF(mixed_flag IS NULL, NULL, mixed_flag = 1)    AS mixed_engine_set_complete,
    lifecycle_status,
    registration_number,
    base_airport_code_iata
FROM pivoted
ORDER BY aircraft_id, as_of_date
