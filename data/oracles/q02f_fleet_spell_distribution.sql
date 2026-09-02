-- ============================================================================
-- Q02F fleet_storage_spell_distribution -- independent SQL oracle over SOURCE
--
-- D-0026.  Q02's frozen parameter schema takes a non-nullable aircraft_id and
-- may not be widened, so the fleet-wide spell distribution ships as a separate
-- question with its own parameter shape: aircraft_scope is 'FLEET' for the
-- whole population.  Every frozen Q02 result set and its non-nullable contract
-- are untouched.
--
-- Parameters: aircraft_scope (VARCHAR, 'FLEET')
-- Order by  : bucket_order
--
-- The spell derivation is byte-for-byte the Q02 derivation with the
-- per-aircraft filter removed, so the two answers cannot disagree about what a
-- spell is.  Buckets are the specification 12.2 item 13 duration buckets.
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, scope AS (
    SELECT '{{aircraft_scope}}'::VARCHAR AS p_scope
),
status_audit AS (
    SELECT
        a.aircraft_id, a.aircraft_history_id, a.start_event_date,
        a.row_sequence_number, a.event_sequence_number, a.lifecycle_status,
        ROW_NUMBER() OVER (
            PARTITION BY a.aircraft_id
            ORDER BY a.start_event_date, a.row_sequence_number,
                     a.event_sequence_number, a.aircraft_history_id) AS audit_ordinal
    FROM audit_assignment a
    CROSS JOIN scope s
    WHERE a.dimension = 'aircraft_status'
      AND s.p_scope = 'FLEET'
),
windowed AS (
    SELECT
        s.*,
        LAG(s.lifecycle_status)  OVER (PARTITION BY s.aircraft_id ORDER BY s.audit_ordinal) AS prev_status,
        LEAD(s.lifecycle_status) OVER (PARTITION BY s.aircraft_id ORDER BY s.audit_ordinal) AS next_status,
        LEAD(s.start_event_date) OVER (PARTITION BY s.aircraft_id ORDER BY s.audit_ordinal) AS next_date
    FROM status_audit s
),
spells AS (
    SELECT
        aircraft_id,
        DATEDIFF('day', start_event_date, next_date)::NUMBER(38,0) AS storage_days
    FROM windowed
    WHERE prev_status      = 'In Service'
      AND lifecycle_status = 'Storage'
      AND next_status      = 'In Service'
),
bucketed AS (
    SELECT
        aircraft_id,
        storage_days,
        CASE
            WHEN storage_days = 0                        THEN 1
            WHEN storage_days BETWEEN 1   AND 7          THEN 2
            WHEN storage_days BETWEEN 8   AND 30         THEN 3
            WHEN storage_days BETWEEN 31  AND 90         THEN 4
            WHEN storage_days BETWEEN 91  AND 365        THEN 5
            WHEN storage_days BETWEEN 366 AND 730        THEN 6
            ELSE 7
        END::NUMBER(38,0) AS bucket_order
    FROM spells
),
labels AS (
    SELECT 1 AS bucket_order, 'ZERO_DAYS'         AS duration_bucket UNION ALL
    SELECT 2, 'DAYS_1_TO_7'                              UNION ALL
    SELECT 3, 'DAYS_8_TO_30'                             UNION ALL
    SELECT 4, 'DAYS_31_TO_90'                            UNION ALL
    SELECT 5, 'DAYS_91_TO_365'                           UNION ALL
    SELECT 6, 'DAYS_366_TO_730'                          UNION ALL
    SELECT 7, 'DAYS_OVER_730'
)
SELECT
    l.bucket_order::NUMBER(38,0)                             AS bucket_order,
    l.duration_bucket::VARCHAR                               AS duration_bucket,
    COUNT(b.storage_days)::NUMBER(38,0)                      AS spell_count,
    COUNT(DISTINCT b.aircraft_id)::NUMBER(38,0)              AS aircraft_count,
    MIN(b.storage_days)::NUMBER(38,0)                        AS minimum_storage_days,
    MAX(b.storage_days)::NUMBER(38,0)                        AS maximum_storage_days
FROM labels l
LEFT JOIN bucketed b ON b.bucket_order = l.bucket_order
GROUP BY l.bucket_order, l.duration_bucket
ORDER BY bucket_order
