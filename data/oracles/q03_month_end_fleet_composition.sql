-- ============================================================================
-- Q03 month_end_fleet_composition -- independent SQL oracle over SOURCE
--
-- Parameters: start_month_end (DATE), end_month_end (DATE), status (VARCHAR)
-- Order by  : month_end ASC, aircraft_type_id ASC
--
-- A calendar of month ends is generated independently of the data, then each
-- month end is tested against the aircraft existence window and BOTH
-- independent half-open daily assignments (status and type). Zero-count
-- (month_end, type) pairs are omitted.
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, params AS (
    SELECT '{{start_month_end}}'::DATE AS p_start,
           '{{end_month_end}}'::DATE   AS p_end,
           '{{status}}'                AS p_status
),
month_calendar AS (
    SELECT month_end FROM (
        SELECT LAST_DAY(DATEADD('month', SEQ4(), DATE_TRUNC('month', p.p_start))) AS month_end,
               p.p_start, p.p_end
        FROM params p, TABLE(GENERATOR(ROWCOUNT => 2400))
    )
    WHERE month_end BETWEEN p_start AND p_end
),
status_visible AS (
    SELECT c.month_end, d.aircraft_id
    FROM month_calendar c
    JOIN daily_assignment d
      ON d.dimension = 'aircraft_status'
     AND d.valid_from <= c.month_end AND c.month_end < d.valid_to
     AND c.month_end >= d.existence_from AND c.month_end < d.existence_to
    WHERE d.is_resolved
      AND d.lifecycle_status = (SELECT p_status FROM params)
),
type_visible AS (
    SELECT c.month_end, d.aircraft_id, d.definition_id, d.definition_label
    FROM month_calendar c
    JOIN daily_assignment d
      ON d.dimension = 'aircraft_type'
     AND d.valid_from <= c.month_end AND c.month_end < d.valid_to
     AND c.month_end >= d.existence_from AND c.month_end < d.existence_to
    WHERE d.is_resolved
)
SELECT
    TO_VARCHAR(s.month_end, 'YYYY-MM-DD')             AS month_end,
    t.definition_id                                   AS aircraft_type_id,
    t.definition_label                                AS aircraft_type,
    COUNT(DISTINCT s.aircraft_id)::NUMBER(38,0)       AS in_service_aircraft_count
FROM status_visible s
JOIN type_visible  t ON t.month_end = s.month_end AND t.aircraft_id = s.aircraft_id
GROUP BY s.month_end, t.definition_id, t.definition_label
HAVING COUNT(DISTINCT s.aircraft_id) > 0
ORDER BY s.month_end, t.definition_id
