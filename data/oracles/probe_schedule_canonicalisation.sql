-- ============================================================================
-- Adversarial probe: schedule canonicalisation and no-change semantics.
--   HT-16  itinerary variant + byte-identical semantic duplicate collapse to
--          exactly one canonical (SS-01, SS-03) observation, and the low-rank
--          V02 variant never wins.
--   HT-17  a repeated unchanged eligible observation contributes lineage but
--          mints no new knowledge state.
--   HT-19  a key-preserving content change opens a new state on the same key.
-- ============================================================================
WITH
{{SCHEDULE_TEMPORAL}}
SELECT 'NF_S01_THREE_RAW_OCCURRENCES_EXIST' AS check_id,
       IFF(COUNT(*) = 3, 'PASS', 'FAIL') AS verdict,
       COUNT(*)::VARCHAR || ' raw SYN-SK-BASE_100 rows at 2026-08-03 (V01 + V02 + DUP)' AS detail,
       OBJECT_CONSTRUCT('raw_rows', COUNT(*),
                        'itinerary_variants', ARRAY_AGG(itinerary_variation_identifier)
                            WITHIN GROUP (ORDER BY itinerary_variation_identifier),
                        'distinct_row_hashes', COUNT(DISTINCT normalized_row_hash))::VARCHAR AS evidence
FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT
WHERE schedule_key = 'SYN-SK-BASE_100' AND publish_date = DATE '2026-08-03'
UNION ALL
SELECT 'NF_S01_SEMANTIC_DUPLICATE_COLLAPSES_TO_ONE',
       IFF(COUNT(*) = 1, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' canonical observation for SYN-SK-BASE_100 at 2026-08-03',
       OBJECT_CONSTRUCT('canonical_rows', COUNT(*),
                        'weekly_frequency', MIN(weekly_frequency),
                        'total_seats', MIN(total_seats))::VARCHAR
FROM observation_signed
WHERE schedule_key = 'SYN-SK-BASE_100' AND publish_date = DATE '2026-08-03'
UNION ALL
SELECT 'NF_S01_LOW_RANK_VARIANT_NEVER_SELECTED',
       IFF(MIN(weekly_frequency) = 1 AND MIN(total_seats) = 180, 'PASS', 'FAIL'),
       'selected canonical row has weekly_frequency=' || MIN(weekly_frequency)::VARCHAR
           || ' total_seats=' || MIN(total_seats)::VARCHAR
           || ' (V02 has weekly_frequency=0 and must lose the deterministic rank)',
       OBJECT_CONSTRUCT('weekly_frequency', MIN(weekly_frequency), 'total_seats', MIN(total_seats))::VARCHAR
FROM observation_signed
WHERE schedule_key = 'SYN-SK-BASE_100' AND publish_date = DATE '2026-08-03'
UNION ALL
SELECT 'CANONICAL_GRAIN_IS_ONE_ROW_PER_KEY_AND_DATE',
       IFF(COUNT(*) = 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' (schedule_key, publish_date) pairs have more than one canonical row',
       OBJECT_CONSTRUCT('violations', COUNT(*))::VARCHAR
FROM (SELECT schedule_key, publish_date FROM observation_signed
      GROUP BY schedule_key, publish_date HAVING COUNT(*) > 1)
UNION ALL
SELECT 'NF_S02_UNCHANGED_OBSERVATION_MINTS_NO_STATE',
       IFF(COUNT(*) = 1 AND MIN(knowledge_valid_from) = DATE '2026-08-03', 'PASS', 'FAIL'),
       'SYN-SK-STABLE_010 is observed unchanged at all five August snapshots and yields '
           || COUNT(*)::VARCHAR || ' knowledge state(s) opening at '
           || COALESCE(MIN(knowledge_valid_from)::VARCHAR, '<none>'),
       OBJECT_CONSTRUCT('states', COUNT(*),
                        'from', MIN(knowledge_valid_from)::VARCHAR,
                        'to', MIN(knowledge_valid_to)::VARCHAR)::VARCHAR
FROM route_state WHERE schedule_key = 'SYN-SK-STABLE_010'
UNION ALL
SELECT 'NF_S02_LINEAGE_STILL_RETAINED',
       IFF(COUNT(*) = 5, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' contributing eligible observations retained for SYN-SK-STABLE_010',
       OBJECT_CONSTRUCT('observations', COUNT(*))::VARCHAR
FROM observation_signed WHERE schedule_key = 'SYN-SK-STABLE_010'
UNION ALL
SELECT 'KEY_PRESERVING_CHANGE_OPENS_NEW_STATE_ON_SAME_KEY',
       IFF(COUNT(*) = 3, 'PASS', 'FAIL'),
       'SYN-SK-BASE_100 has ' || COUNT(*)::VARCHAR
           || ' knowledge states (expected 3: open, seats change 2026-08-10, terminal change 2026-08-31)',
       OBJECT_CONSTRUCT('states',
           ARRAY_AGG(knowledge_valid_from::VARCHAR || '..' || knowledge_valid_to::VARCHAR)
           WITHIN GROUP (ORDER BY knowledge_valid_from))::VARCHAR
FROM route_state WHERE schedule_key = 'SYN-SK-BASE_100'
UNION ALL
SELECT 'INVALID_ROUTE_KEY_COUNTED_BUT_NOT_A_ROUTE',
       IFF(SUM(IFF(route_valid, 0, 1)) > 0, 'PASS', 'FAIL'),
       SUM(IFF(route_valid, 0, 1))::VARCHAR || ' SYN-SK-CLOCK_BOUNDARY_001 states carry a null route '
           || 'component: still counted as schedule observations, never as a Route',
       OBJECT_CONSTRUCT('states', COUNT(*), 'invalid_route_states', SUM(IFF(route_valid, 0, 1)))::VARCHAR
FROM route_state WHERE schedule_key = 'SYN-SK-CLOCK_BOUNDARY_001'
ORDER BY check_id
