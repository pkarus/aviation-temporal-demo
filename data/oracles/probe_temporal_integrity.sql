-- ============================================================================
-- Adversarial probe: aircraft temporal integrity and the frozen semantic
-- invariants (half-open intervals, sentinels, event ordering, A -> B -> A,
-- same-day audit preservation, EOL exclusivity, left preservation).
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, overlap_check AS (
    SELECT a.dimension, a.aircraft_id, COUNT(*) AS overlaps
    FROM daily_assignment a
    JOIN daily_assignment b
      ON b.dimension = a.dimension AND b.aircraft_id = a.aircraft_id
     AND b.valid_from > a.valid_from
     AND b.valid_from < a.valid_to
    GROUP BY 1, 2
),
status_1001 AS (
    SELECT lifecycle_status, start_event_date, row_sequence_number, aircraft_history_id
    FROM audit_assignment WHERE dimension = 'aircraft_status' AND aircraft_id = 1001
)
SELECT 'HALF_OPEN_NO_OVERLAPPING_DAILY_ASSIGNMENTS' AS check_id,
       IFF(COUNT(*) = 0, 'PASS', 'FAIL') AS verdict,
       COUNT(*)::VARCHAR || ' (dimension, aircraft) pairs have overlapping daily assignments' AS detail,
       OBJECT_CONSTRUCT('overlapping_pairs', COUNT(*))::VARCHAR AS evidence
FROM overlap_check
UNION ALL
SELECT 'SOURCE_UNKNOWN_FUTURE_SENTINEL_PRESENT_IN_SOURCE',
       IFF(COUNT(*) > 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' AH rows carry source unknown-future end_event_date 9999-12-31',
       OBJECT_CONSTRUCT('rows', COUNT(*),
                        'aircraft_history_ids', ARRAY_AGG(aircraft_history_id) WITHIN GROUP (ORDER BY aircraft_history_id))::VARCHAR
FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_HISTORY WHERE end_event_date = DATE '9999-12-31'
UNION ALL
SELECT 'DERIVED_BOUNDS_NEVER_USE_SOURCE_SENTINEL_99991231',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' derived valid_to values equal the source sentinel 9999-12-31',
       OBJECT_CONSTRUCT('rows', COUNT(*))::VARCHAR
FROM daily_assignment WHERE valid_to = DATE '9999-12-31'
UNION ALL
SELECT 'OPEN_INTERVALS_USE_MODEL_SENTINEL_99990101',
       IFF(COUNT(*) > 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' open daily assignments carry the derived model sentinel 9999-01-01',
       OBJECT_CONSTRUCT('rows', COUNT(*))::VARCHAR
FROM daily_assignment WHERE valid_to = DATE '9999-01-01'
UNION ALL
SELECT 'AH06_SENTINEL_EVENT_MINTS_NO_ASSIGNMENT',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       'AH-102099 (end_event_date 9999-12-31, watched values unchanged) mints '
           || COUNT(*)::VARCHAR || ' daily assignments (expected 0)',
       OBJECT_CONSTRUCT('assignments', COUNT(*))::VARCHAR
FROM daily_assignment WHERE aircraft_history_id = 102099
UNION ALL
SELECT 'END_EVENT_DATE_NEVER_CLOSES_A_DERIVED_INTERVAL',
       IFF(COUNT(*) = 1 AND MIN(valid_to) = DATE '2024-07-01', 'PASS', 'FAIL'),
       'the aircraft 1002 status assignment covering 2023-01-01 (the AH-102099 sentinel date) '
           || 'closes at ' || COALESCE(MIN(valid_to)::VARCHAR, '<none>')
           || ', taken from AM-08 existence, never from AH-06',
       OBJECT_CONSTRUCT('assignments', COUNT(*), 'valid_to', MIN(valid_to)::VARCHAR,
                        'opened_by', MIN(aircraft_history_id))::VARCHAR
FROM daily_assignment
WHERE dimension = 'aircraft_status' AND aircraft_id = 1002
  AND valid_from <= DATE '2023-01-01' AND DATE '2023-01-01' < valid_to
UNION ALL
SELECT 'EOL_EXCLUSIVE_PREVIOUS_DAY_ELIGIBLE',
       IFF(COUNT(*) = 4, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' of 4 dimensions are date-visible for aircraft 1002 on 2024-06-30',
       OBJECT_CONSTRUCT('dimensions', COUNT(*))::VARCHAR
FROM daily_assignment
WHERE aircraft_id = 1002 AND valid_from <= DATE '2024-06-30' AND DATE '2024-06-30' < valid_to
UNION ALL
SELECT 'EOL_EXCLUSIVE_BOUNDARY_DAY_EXCLUDED',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' dimensions are date-visible for aircraft 1002 on its EOL date 2024-07-01',
       OBJECT_CONSTRUCT('dimensions', COUNT(*))::VARCHAR
FROM daily_assignment
WHERE aircraft_id = 1002 AND valid_from <= DATE '2024-07-01' AND DATE '2024-07-01' < valid_to
UNION ALL
SELECT 'A_TO_B_TO_A_PRESERVED_AS_THREE_ASSIGNMENTS',
       IFF(COUNT(*) = 7, 'PASS', 'FAIL'),
       'aircraft 1001 retains ' || COUNT(*)::VARCHAR
           || ' status audit assignments after consecutive-equality suppression (expected 7)',
       OBJECT_CONSTRUCT('sequence',
           ARRAY_AGG(lifecycle_status) WITHIN GROUP (ORDER BY start_event_date, row_sequence_number))::VARCHAR
FROM status_1001
UNION ALL
SELECT 'REPEATED_STATUS_NOT_GLOBALLY_DEDUPLICATED',
       IFF(COUNT(*) = 2, 'PASS', 'FAIL'),
       'Storage occurs ' || COUNT(*)::VARCHAR || ' separate times for aircraft 1001 (expected 2)',
       OBJECT_CONSTRUCT('storage_occurrences', COUNT(*))::VARCHAR
FROM status_1001 WHERE lifecycle_status = 'Storage'
UNION ALL
SELECT 'SAME_DAY_AUDIT_SEQUENCE_PRESERVED',
       IFF(COUNT(*) = 4, 'PASS', 'FAIL'),
       'aircraft 1001 keeps ' || COUNT(*)::VARCHAR
           || ' distinct status audit observations on 2020-06-01 (expected 4 of the 5 raw rows;'
           || ' the seq-40 repeat is consecutive-equal)',
       OBJECT_CONSTRUCT('sequences', ARRAY_AGG(row_sequence_number) WITHIN GROUP (ORDER BY row_sequence_number),
                        'statuses', ARRAY_AGG(lifecycle_status) WITHIN GROUP (ORDER BY row_sequence_number))::VARCHAR
FROM status_1001 WHERE start_event_date = DATE '2020-06-01'
UNION ALL
SELECT 'SAME_DAY_DATE_VISIBLE_STATE_IS_FINAL_OBSERVATION',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' daily assignments were minted on 2020-06-01 for aircraft 1001 status'
           || ' (expected 0: the final seq-40 In Service equals the prior date-visible value)',
       OBJECT_CONSTRUCT('daily_assignments_on_2020_06_01', COUNT(*))::VARCHAR
FROM daily_assignment
WHERE dimension = 'aircraft_status' AND aircraft_id = 1001 AND valid_from = DATE '2020-06-01'
UNION ALL
SELECT 'NO_ASSIGNMENT_STARTS_BEFORE_EXISTENCE',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' daily assignments start before their aircraft existence_from',
       OBJECT_CONSTRUCT('rows', COUNT(*))::VARCHAR
FROM daily_assignment WHERE valid_from < existence_from
UNION ALL
SELECT 'AIRCRAFT_MASTER_KEY_UNIQUE',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' duplicate AM-01 identities',
       OBJECT_CONSTRUCT('duplicates', COUNT(*))::VARCHAR
FROM (SELECT aircraft_id FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER
      GROUP BY aircraft_id HAVING COUNT(*) > 1)
UNION ALL
SELECT 'UNRESOLVED_CONFIGURATION_LEFT_PRESERVED',
       IFF(COUNT(*) = 2, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' of 2 unresolved-configuration events (102004 null, 102005 missing 999999)'
           || ' survive resolution rather than being inner-join dropped',
       OBJECT_CONSTRUCT('events', ARRAY_AGG(aircraft_history_id) WITHIN GROUP (ORDER BY aircraft_history_id))::VARCHAR
FROM ah_resolved WHERE aircraft_history_id IN (102004, 102005)
UNION ALL
SELECT 'UNRESOLVED_CONFIGURATION_OPENS_ONE_GAP_NOT_TWO',
       IFF(COUNT(*) = 1, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' unresolved aircraft_type gaps for aircraft 1002 (expected 1:'
           || ' null config and missing definition resolve identically, so no false second assignment)',
       OBJECT_CONSTRUCT('gaps',
           ARRAY_AGG(valid_from::VARCHAR || '..' || valid_to::VARCHAR) WITHIN GROUP (ORDER BY valid_from))::VARCHAR
FROM daily_assignment
WHERE dimension = 'aircraft_type' AND aircraft_id = 1002 AND NOT is_resolved
UNION ALL
SELECT 'MIXED_ENGINE_SET_INCOMPLETE_NOT_FABRICATED',
       IFF(COUNT(*) = 1 AND BOOLAND_AGG(mixed_engine_set_complete = FALSE), 'PASS', 'FAIL'),
       'aircraft 1005 reports one engine definition with mixed_engine_set_complete=false',
       OBJECT_CONSTRUCT('definition_id', MIN(definition_id), 'engine_count', MIN(engine_count),
                        'complete', BOOLAND_AGG(mixed_engine_set_complete))::VARCHAR
FROM daily_assignment WHERE dimension = 'engine_type' AND aircraft_id = 1005
ORDER BY check_id
