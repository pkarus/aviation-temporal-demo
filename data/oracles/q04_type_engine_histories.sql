-- ============================================================================
-- Q04 type_engine_histories -- independent SQL oracle over SOURCE
--
-- Parameters: aircraft_id (NUMBER(38,0))
-- Order by  : dimension ASC, valid_from ASC, assignment_id ASC
--
-- The two streams are derived independently and are never boundary-aligned.
-- is_type_change is computed only inside the aircraft_type stream (null in the
-- engine stream). Open intervals use the derived model sentinel 9999-01-01,
-- which stays distinct from source unknown-future 9999-12-31.
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, params AS (
    SELECT {{aircraft_id}}::NUMBER(38,0) AS p_aircraft_id
),
stream AS (
    SELECT d.*
    FROM daily_assignment d
    JOIN params p ON p.p_aircraft_id = d.aircraft_id
    WHERE d.dimension IN ('aircraft_type', 'engine_type')
),
with_previous AS (
    SELECT
        s.*,
        LAG(s.definition_id) OVER (
            PARTITION BY s.dimension, s.aircraft_id ORDER BY s.valid_from) AS previous_definition_id
    FROM stream s
)
SELECT
    aircraft_id::NUMBER(38,0)                     AS aircraft_id,
    dimension,
    assignment_id,
    TO_VARCHAR(valid_from, 'YYYY-MM-DD')          AS valid_from,
    TO_VARCHAR(valid_to,   'YYYY-MM-DD')          AS valid_to,
    definition_id                                 AS definition_id,
    definition_label                              AS definition_label,
    engine_count::NUMBER(38,0)                    AS engine_count,
    mixed_engine_set_complete,
    previous_definition_id,
    IFF(dimension = 'aircraft_type',
        COALESCE(previous_definition_id IS DISTINCT FROM definition_id AND previous_definition_id IS NOT NULL, FALSE),
        NULL)                                     AS is_type_change
FROM with_previous
ORDER BY dimension, valid_from, assignment_id
