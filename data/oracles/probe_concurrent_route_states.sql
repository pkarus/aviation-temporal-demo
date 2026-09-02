-- ============================================================================
-- Adversarial probe: concurrent open RouteStates on one route are preserved.
--
-- Schedule knowledge versioning is partitioned by SS-01 schedule identity and
-- never by route, so a single directional Route may carry many concurrently
-- open RouteStates. A "one open state per route" constraint is prohibited.
-- ============================================================================
WITH
{{SCHEDULE_TEMPORAL}}
, probe_date AS (SELECT DATE '2026-08-31' AS knowledge_date),
open_states AS (
    SELECT r.*
    FROM route_state r, probe_date d
    WHERE r.route_valid
      AND r.knowledge_valid_from <= d.knowledge_date
      AND d.knowledge_date < r.knowledge_valid_to
),
per_route AS (
    SELECT route_id,
           COUNT(*)                         AS open_state_count,
           COUNT(DISTINCT schedule_key)     AS distinct_schedule_keys,
           COUNT(DISTINCT route_state_key)  AS distinct_route_state_keys
    FROM open_states
    GROUP BY route_id
)
SELECT 'CONCURRENT_STATES_ON_SFO_LAX' AS check_id,
       IFF(open_state_count >= 3, 'PASS', 'FAIL') AS verdict,
       'route SFO->LAX carries ' || open_state_count::VARCHAR
           || ' concurrently open knowledge states at 2026-08-31' AS detail,
       OBJECT_CONSTRUCT('route_id', route_id, 'open_state_count', open_state_count,
                        'distinct_schedule_keys', distinct_schedule_keys)::VARCHAR AS evidence
FROM per_route WHERE route_id = 'SFO->LAX'
UNION ALL
SELECT 'ROUTE_STATE_PARTITIONED_BY_SCHEDULE_KEY',
       IFF(SUM(IFF(open_state_count = distinct_schedule_keys, 0, 1)) = 0, 'PASS', 'FAIL'),
       'every route has exactly one open state per schedule key, over '
           || COUNT(*)::VARCHAR || ' routes',
       OBJECT_CONSTRUCT('routes', COUNT(*),
                        'routes_with_multiple_open_states', SUM(IFF(open_state_count > 1, 1, 0)))::VARCHAR
FROM per_route
UNION ALL
SELECT 'MULTI_OPEN_ROUTES_EXIST',
       IFF(COUNT(*) > 0, 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' distinct routes carry more than one concurrently open state',
       OBJECT_CONSTRUCT('multi_open_routes', COUNT(*))::VARCHAR
FROM per_route WHERE open_state_count > 1
UNION ALL
SELECT 'NAMED_CONCURRENT_CAPACITY_KEYS_ALL_OPEN',
       IFF(COUNT(*) = 3, 'PASS', 'FAIL'),
       'PHY_BASE_700 / PHY_BASE_701 / MKT_COPY_702 all open on SFO->LAX at 2026-08-31: '
           || COUNT(*)::VARCHAR || ' of 3',
       OBJECT_CONSTRUCT('keys', ARRAY_AGG(schedule_key) WITHIN GROUP (ORDER BY schedule_key))::VARCHAR
FROM open_states
WHERE route_id = 'SFO->LAX'
  AND schedule_key IN ('SYN-SK-PHY_BASE_700', 'SYN-SK-PHY_BASE_701', 'SYN-SK-MKT_COPY_702')
UNION ALL
SELECT 'ROUTE_STATE_KEY_UNIQUE',
       IFF(COUNT(*) = COUNT(DISTINCT route_state_key), 'PASS', 'FAIL'),
       COUNT(*)::VARCHAR || ' route states, ' || COUNT(DISTINCT route_state_key)::VARCHAR || ' distinct keys',
       OBJECT_CONSTRUCT('rows', COUNT(*), 'distinct_keys', COUNT(DISTINCT route_state_key))::VARCHAR
FROM route_state
ORDER BY check_id
