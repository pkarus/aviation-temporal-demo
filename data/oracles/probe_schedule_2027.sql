-- ============================================================================
-- Adversarial probe: the D-0025 2027 knowledge block.
--
-- Asserts specification 2.0.0 section 12.2 items 17 and 18: the eligible-date
-- and adjacent-pair structure of the second knowledge block, that the
-- incomplete date is physically retained but semantically inert, that the
-- missing date carries nothing at all, and that no 2027 key can reach into the
-- frozen 2026 window that Q05, Q06 and Q07 read.
-- ============================================================================
WITH
{{SCHEDULE_TEMPORAL}}
, calendar_2027 AS (
    SELECT * FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR
    WHERE YEAR(expected_publish_date) = 2027
),
raw_2027 AS (
    SELECT * FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT
    WHERE schedule_key LIKE 'SYN-SK-W27-%'
),
eligible_2027 AS (
    SELECT pd, ROW_NUMBER() OVER (ORDER BY pd) AS ordinal
    FROM eligible_dates WHERE YEAR(pd) = 2027
),
pairs_2027 AS (
    SELECT a.pd AS previous_knowledge_date, b.pd AS comparison_date,
           (SELECT COUNT(*) FROM snapshot_calendar c
            WHERE c.pd > a.pd AND c.pd < b.pd AND NOT c.is_eligible) AS skipped
    FROM eligible_2027 a JOIN eligible_2027 b ON b.ordinal = a.ordinal + 1
)
SELECT 'CALENDAR_2027_HAS_24_ELIGIBLE_DATES' AS check_id,
       IFF(COUNT(*) = 26 AND SUM(IFF(is_present AND is_complete, 1, 0)) = 24
           AND SUM(IFF(is_present AND NOT is_complete, 1, 0)) = 1
           AND SUM(IFF(NOT is_present, 1, 0)) = 1, 'PASS', 'FAIL') AS verdict,
       COUNT(*)::VARCHAR || ' 2027 calendar dates, '
           || SUM(IFF(is_present AND is_complete, 1, 0))::VARCHAR || ' eligible complete' AS detail,
       OBJECT_CONSTRUCT('dates', COUNT(*),
                        'eligible_complete', SUM(IFF(is_present AND is_complete, 1, 0)),
                        'incomplete', SUM(IFF(is_present AND NOT is_complete, 1, 0)),
                        'missing', SUM(IFF(NOT is_present, 1, 0)))::VARCHAR AS evidence
FROM calendar_2027

UNION ALL
SELECT 'ADJACENT_PAIRS_IN_2027_ARE_23',
       IFF(COUNT(*) = 23, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' adjacent eligible comparisons inside 2027',
       OBJECT_CONSTRUCT('pairs', COUNT(*))::VARCHAR
FROM pairs_2027

UNION ALL
SELECT 'EXACTLY_TWO_GAP_CROSSING_PAIRS_IN_2027',
       IFF(COUNT(*) = 2, 'PASS', 'FAIL'),
       'gap-crossing comparisons at '
           || LISTAGG(TO_VARCHAR(comparison_date), ', ') WITHIN GROUP (ORDER BY comparison_date),
       OBJECT_CONSTRUCT('comparison_dates',
                        ARRAY_AGG(TO_VARCHAR(comparison_date)) WITHIN GROUP (ORDER BY comparison_date))::VARCHAR
FROM pairs_2027 WHERE skipped > 0

UNION ALL
SELECT 'INCOMPLETE_DATE_IS_PHYSICALLY_RETAINED',
       IFF(COUNT(*) = 2301, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' raw 2027 rows sit at the incomplete date 2027-03-15',
       OBJECT_CONSTRUCT('rows', COUNT(*))::VARCHAR
FROM raw_2027 WHERE publish_date = DATE '2027-03-15'

UNION ALL
SELECT 'INCOMPLETE_DATE_IS_SEMANTICALLY_INERT',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' canonical observations derive from the incomplete date',
       OBJECT_CONSTRUCT('canonical_observations', COUNT(*))::VARCHAR
FROM schedule_observation WHERE publish_date = DATE '2027-03-15'

UNION ALL
SELECT 'MISSING_DATE_CARRIES_NOTHING',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' raw rows sit at the missing date 2027-04-19',
       OBJECT_CONSTRUCT('rows', COUNT(*))::VARCHAR
FROM raw_2027 WHERE publish_date = DATE '2027-04-19'

UNION ALL
SELECT 'INERT_COHORT_DERIVES_NO_ROUTE_STATE',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' RouteStates derive from the INERT cohort',
       OBJECT_CONSTRUCT('route_states', COUNT(*))::VARCHAR
FROM route_state WHERE schedule_key LIKE 'SYN-SK-W27-INERT-%'

UNION ALL
SELECT 'NO_2027_KEY_REACHES_THE_FROZEN_2026_WINDOW',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' 2027 keys are observed at a snapshot date outside 2027',
       OBJECT_CONSTRUCT('rows', COUNT(*))::VARCHAR
FROM raw_2027 WHERE YEAR(publish_date) <> 2027
ORDER BY check_id
