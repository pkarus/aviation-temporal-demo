-- ============================================================================
-- Adversarial probe: an absent or incomplete snapshot never manufactures a
-- removal, an exit, or any absence-derived event (HT-12, HT-13, HT-15).
--
-- 2026-10-12 is MISSING, 2026-10-19 is PRESENT_INCOMPLETE and physically holds
-- thousands of retained diagnostic rows. Neither may close a segment. The next
-- eligible complete date, 2026-10-26, observes the exact removal against the
-- previous eligible complete date 2026-10-05 and exposes the gap.
-- ============================================================================
WITH
{{SCHEDULE_TEMPORAL}}
, raw_by_date AS (
    SELECT publish_date, COUNT(*) AS raw_rows
    FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT
    GROUP BY publish_date
),
canonical_by_date AS (
    SELECT pd, COUNT(*) AS canonical_rows
    FROM presence_grid WHERE is_present_at_date GROUP BY pd
),
closures AS (
    SELECT pd, COUNT(*) AS closing_segments
    FROM presence_boundary WHERE closes_segment GROUP BY pd
),
opens AS (
    SELECT pd, COUNT(*) AS opening_segments
    FROM presence_boundary WHERE opens_segment GROUP BY pd
)
SELECT 'MISSING_SNAPSHOT_20261012_NOT_ELIGIBLE' AS check_id,
       IFF(NOT is_present AND NOT is_eligible, 'PASS', 'FAIL') AS verdict,
       'is_present=' || is_present::VARCHAR || ' is_complete=' || is_complete::VARCHAR AS detail,
       OBJECT_CONSTRUCT('pd', pd::VARCHAR, 'eligible', is_eligible)::VARCHAR AS evidence
FROM snapshot_calendar WHERE pd = DATE '2026-10-12'
UNION ALL
SELECT 'INCOMPLETE_SNAPSHOT_20261019_NOT_ELIGIBLE',
       IFF(is_present AND NOT is_complete AND NOT is_eligible, 'PASS', 'FAIL'),
       'is_present=' || is_present::VARCHAR || ' is_complete=' || is_complete::VARCHAR,
       OBJECT_CONSTRUCT('pd', pd::VARCHAR, 'eligible', is_eligible)::VARCHAR
FROM snapshot_calendar WHERE pd = DATE '2026-10-19'
UNION ALL
SELECT 'INCOMPLETE_20261019_ROWS_RETAINED_BUT_INERT',
       IFF(r.raw_rows > 0 AND COALESCE(c.canonical_rows, 0) = 0, 'PASS', 'FAIL'),
       r.raw_rows::VARCHAR || ' raw rows physically retained at 2026-10-19, '
           || COALESCE(c.canonical_rows, 0)::VARCHAR || ' canonical observations',
       OBJECT_CONSTRUCT('raw_rows', r.raw_rows, 'canonical_rows', COALESCE(c.canonical_rows, 0))::VARCHAR
FROM raw_by_date r LEFT JOIN canonical_by_date c ON c.pd = r.publish_date
WHERE r.publish_date = DATE '2026-10-19'
UNION ALL
SELECT 'NO_SEGMENT_BOUNDARY_ON_INELIGIBLE_DATES',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' segment boundaries fall on an ineligible snapshot date',
       OBJECT_CONSTRUCT('boundaries_on_ineligible_dates', COUNT(*))::VARCHAR
FROM presence_boundary b
JOIN snapshot_calendar c ON c.pd = b.pd AND NOT c.is_eligible
WHERE b.opens_segment OR b.closes_segment
UNION ALL
SELECT 'NO_CLOSURE_AT_20261012_OR_20261019',
       IFF(COALESCE(SUM(closing_segments), 0) = 0, 'PASS', 'FAIL'),
       COALESCE(SUM(closing_segments), 0)::VARCHAR || ' closures derived at the missing/incomplete dates',
       OBJECT_CONSTRUCT('closures', COALESCE(SUM(closing_segments), 0))::VARCHAR
FROM closures WHERE pd IN (DATE '2026-10-12', DATE '2026-10-19')
UNION ALL
SELECT 'NO_OPENING_AT_20261012_OR_20261019',
       IFF(COALESCE(SUM(opening_segments), 0) = 0, 'PASS', 'FAIL'),
       COALESCE(SUM(opening_segments), 0)::VARCHAR || ' openings derived at the missing/incomplete dates',
       OBJECT_CONSTRUCT('openings', COALESCE(SUM(opening_segments), 0))::VARCHAR
FROM opens WHERE pd IN (DATE '2026-10-12', DATE '2026-10-19')
UNION ALL
SELECT 'GAP_CONTROL_CLOSES_ONLY_AT_20261026',
       IFF(COUNT(*) = 1 AND MIN(pd) = DATE '2026-10-26', 'PASS', 'FAIL'),
       'SYN-SK-GAP_CONTROL_001 closes at ' || COALESCE(MIN(pd)::VARCHAR, '<none>'),
       OBJECT_CONSTRUCT('closures', COUNT(*), 'closing_date', MIN(pd)::VARCHAR)::VARCHAR
FROM presence_boundary
WHERE schedule_key = 'SYN-SK-GAP_CONTROL_001' AND closes_segment
UNION ALL
SELECT 'GAP_CONTROL_PREVIOUS_ELIGIBLE_IS_20261005',
       IFF(MIN(prev_eligible_pd) = DATE '2026-10-05', 'PASS', 'FAIL'),
       'previous eligible complete date before the 2026-10-26 closure is '
           || COALESCE(MIN(prev_eligible_pd)::VARCHAR, '<none>'),
       OBJECT_CONSTRUCT('previous_eligible', MIN(prev_eligible_pd)::VARCHAR)::VARCHAR
FROM presence_boundary
WHERE schedule_key = 'SYN-SK-GAP_CONTROL_001' AND pd = DATE '2026-10-26'
UNION ALL
SELECT 'GAP_CONTROL_OPEN_INTERVAL_IS_20261005_TO_20261026',
       IFF(COUNT(*) = 1
           AND MIN(knowledge_valid_from) = DATE '2026-10-05'
           AND MIN(knowledge_valid_to)   = DATE '2026-10-26', 'PASS', 'FAIL'),
       'route state ' || COALESCE(MIN(knowledge_valid_from)::VARCHAR, '?') || ' -> '
           || COALESCE(MIN(knowledge_valid_to)::VARCHAR, '?'),
       OBJECT_CONSTRUCT('states', COUNT(*), 'from', MIN(knowledge_valid_from)::VARCHAR,
                        'to', MIN(knowledge_valid_to)::VARCHAR)::VARCHAR
FROM route_state WHERE schedule_key = 'SYN-SK-GAP_CONTROL_001'
UNION ALL
SELECT 'REAPPEARANCE_OPENS_A_NEW_SEGMENT',
       IFF(COUNT(*) = 2, 'PASS', 'FAIL'),
       'SYN-SK-REAPPEAR_400 has ' || COUNT(*)::VARCHAR || ' knowledge segments (expected 2)',
       OBJECT_CONSTRUCT('segments',
           ARRAY_AGG(knowledge_valid_from::VARCHAR || '..' || knowledge_valid_to::VARCHAR)
           WITHIN GROUP (ORDER BY knowledge_valid_from))::VARCHAR
FROM route_state WHERE schedule_key = 'SYN-SK-REAPPEAR_400'
ORDER BY check_id
