-- ============================================================================
-- Adversarial probe: the D-0023 enriched fleet lifecycle.
--
-- Asserts specification 2.0.0 section 12.2 items 11 through 14 against the
-- live population, so the enrichment's headline claims are measured rather
-- than asserted. The 993 filler aircraft are 1000..1999 minus 1003 and minus
-- the six anchored aircraft; the anchors are excluded so the filler measures
-- stay comparable to the specification's own predictions.
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, filler AS (
    SELECT DISTINCT aircraft_id
    FROM audit_assignment
    WHERE aircraft_id NOT IN (1001, 1002, 1004, 1005, 1098, 1099)
),
versions AS (
    SELECT a.dimension, a.aircraft_id, COUNT(*) AS n
    FROM audit_assignment a
    JOIN filler f ON f.aircraft_id = a.aircraft_id
    GROUP BY 1, 2
),
status_audit AS (
    SELECT
        a.aircraft_id, a.start_event_date, a.lifecycle_status,
        ROW_NUMBER() OVER (
            PARTITION BY a.aircraft_id
            ORDER BY a.start_event_date, a.row_sequence_number,
                     a.event_sequence_number, a.aircraft_history_id) AS ordinal
    FROM audit_assignment a
    JOIN filler f ON f.aircraft_id = a.aircraft_id
    WHERE a.dimension = 'aircraft_status'
),
windowed AS (
    SELECT s.*,
           LAG(s.lifecycle_status)  OVER (PARTITION BY s.aircraft_id ORDER BY s.ordinal) AS prev_status,
           LEAD(s.lifecycle_status) OVER (PARTITION BY s.aircraft_id ORDER BY s.ordinal) AS next_status,
           LEAD(s.start_event_date) OVER (PARTITION BY s.aircraft_id ORDER BY s.ordinal) AS next_date
    FROM status_audit s
),
spells AS (
    SELECT aircraft_id, DATEDIFF('day', start_event_date, next_date) AS storage_days
    FROM windowed
    WHERE prev_status = 'In Service' AND lifecycle_status = 'Storage' AND next_status = 'In Service'
),
per_aircraft AS (
    SELECT f.aircraft_id, COALESCE(COUNT(s.storage_days), 0) AS spell_count
    FROM filler f LEFT JOIN spells s ON s.aircraft_id = f.aircraft_id
    GROUP BY 1
),
observations AS (
    SELECT a.lifecycle_status, COUNT(*) AS n
    FROM audit_assignment a JOIN filler f ON f.aircraft_id = a.aircraft_id
    WHERE a.dimension = 'aircraft_status'
    GROUP BY 1
),
raw_status AS (
    SELECT e.start_aircraft_status AS lifecycle_status, COUNT(*) AS n
    FROM ah_eligible e
    WHERE e.aircraft_id NOT IN (1001, 1002, 1004, 1005, 1098, 1099)
    GROUP BY 1
)
-- 12.2.11 version means, one row per dimension
SELECT 'VERSIONS_PER_AIRCRAFT_' || UPPER(dimension) AS check_id,
       IFF(COUNT(*) = 993, 'PASS', 'FAIL')          AS verdict,
       dimension || ' averages ' || ROUND(AVG(n), 3)::VARCHAR
           || ' versions over ' || COUNT(*)::VARCHAR || ' filler aircraft' AS detail,
       OBJECT_CONSTRUCT('dimension', dimension, 'aircraft', COUNT(*),
                        'mean_versions', ROUND(AVG(n), 3), 'max_versions', MAX(n),
                        'above_one', SUM(IFF(n > 1, 1, 0)))::VARCHAR AS evidence
FROM versions GROUP BY dimension

UNION ALL
-- 12.2.12 exactly three observed status values, no fourth invented
SELECT 'STATUS_VOCABULARY_IS_EXACTLY_THREE',
       IFF(COUNT(*) = 3
           AND BOOLAND_AGG(lifecycle_status IN ('In Service', 'Storage', 'Maintenance')), 'PASS', 'FAIL'),
       'filler status observations use ' || COUNT(*)::VARCHAR || ' distinct values',
       OBJECT_CONSTRUCT('values', ARRAY_AGG(lifecycle_status || '=' || n::VARCHAR))::VARCHAR
FROM raw_status

UNION ALL
-- 12.2.13 closed spell population and its shape
SELECT 'CLOSED_STORAGE_SPELL_POPULATION',
       IFF(COUNT(*) >= 400, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' closed In Service -> Storage -> In Service spells over '
           || COUNT(DISTINCT aircraft_id)::VARCHAR || ' filler aircraft',
       OBJECT_CONSTRUCT('spells', COUNT(*), 'aircraft', COUNT(DISTINCT aircraft_id),
                        'minimum_days', MIN(storage_days), 'median_days', MEDIAN(storage_days),
                        'maximum_days', MAX(storage_days))::VARCHAR
FROM spells

UNION ALL
SELECT 'SPELL_DURATION_BUCKETS_ALL_POPULATED',
       IFF(COUNT(DISTINCT bucket) = 7, 'PASS', 'FAIL'),
       COUNT(DISTINCT bucket)::VARCHAR || ' of 7 duration buckets carry at least one spell',
       OBJECT_CONSTRUCT('buckets', ARRAY_AGG(DISTINCT bucket))::VARCHAR
FROM (SELECT CASE WHEN storage_days = 0 THEN 'ZERO'
                  WHEN storage_days <= 7 THEN 'D1_7'
                  WHEN storage_days <= 30 THEN 'D8_30'
                  WHEN storage_days <= 90 THEN 'D31_90'
                  WHEN storage_days <= 365 THEN 'D91_365'
                  WHEN storage_days <= 730 THEN 'D366_730'
                  ELSE 'OVER_730' END AS bucket
      FROM spells)

UNION ALL
SELECT 'AIRCRAFT_WITHOUT_ANY_SPELL_IS_A_REAL_POPULATION',
       IFF(SUM(IFF(spell_count = 0, 1, 0)) > 500, 'PASS', 'FAIL'),
       SUM(IFF(spell_count = 0, 1, 0))::VARCHAR || ' filler aircraft deliberately have no spell',
       OBJECT_CONSTRUCT('zero', SUM(IFF(spell_count = 0, 1, 0)), 'one', SUM(IFF(spell_count = 1, 1, 0)),
                        'two', SUM(IFF(spell_count = 2, 1, 0)),
                        'three_or_more', SUM(IFF(spell_count >= 3, 1, 0)))::VARCHAR
FROM per_aircraft

UNION ALL
-- 12.2.14 no Storage observation nested inside an unclosed spell, which is the
-- same statement as "the consecutive-status-compressed sequence never repeats"
SELECT 'NO_STORAGE_NESTED_INSIDE_AN_OPEN_SPELL',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' consecutive same-status pairs survive compression',
       OBJECT_CONSTRUCT('violations', COUNT(*))::VARCHAR
FROM windowed
WHERE prev_status = lifecycle_status
ORDER BY check_id
