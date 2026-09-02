-- ============================================================================
-- Q06 market_latest_vs_seven_days -- independent SQL oracle over SOURCE
--
-- Parameters: latest_knowledge_date, comparison_knowledge_date (DATE),
--             carrier_role ('marketing'|'operating')
-- Order by  : change_kind ASC, airline_id ASC, route_id ASC
--
-- Both endpoints must be eligible complete snapshots; the runner refuses an
-- ineligible endpoint with ENDPOINT_MISSING / ENDPOINT_INCOMPLETE before this
-- query runs, so an incomplete snapshot can never manufacture an exit.
--
-- Market grain is (carrier_role, exact resolved airline, directional route).
-- The measure is the count of distinct eligible schedule keys, taken over the
-- whole unfiltered SYN-SCHEDULE-UNIVERSE-01. ENTRY is 0 -> positive, EXIT is
-- positive -> 0; any other transition (1 -> 2, 2 -> 1) is deliberately not an
-- event, which is what the market-shadow fixtures exercise.
-- Marketing and operating roles are separate carrier dimensions and are never
-- merged. A null route component yields no Route and therefore no market row.
-- ============================================================================
WITH
{{SCHEDULE_TEMPORAL}}
, params AS (
    SELECT '{{latest_knowledge_date}}'::DATE      AS p_latest,
           '{{comparison_knowledge_date}}'::DATE  AS p_comparison,
           '{{carrier_role}}'                     AS p_carrier_role
),
state_at_endpoint AS (
    SELECT
        e.endpoint_kind,
        p.p_carrier_role AS carrier_role,
        IFF(p.p_carrier_role = 'marketing', g.marketing_carrier_internal, g.operating_carrier_internal) AS raw_airline_code,
        g.route_id,
        g.schedule_key
    FROM params p
    CROSS JOIN (SELECT 'BEFORE' AS endpoint_kind UNION ALL SELECT 'AFTER') e
    JOIN presence_grid g
      ON g.pd = IFF(e.endpoint_kind = 'BEFORE', p.p_comparison, p.p_latest)
    WHERE g.is_present_at_date
      AND g.route_valid
),
resolved AS (
    -- Exact carrier resolution: AIRLINE_ALIAS_UNION_EXACT over AL-01/AL-04/AL-05
    -- with candidate cardinality exactly one. An unresolved or ambiguous code
    -- cannot yield an exact airline-level market.
    SELECT s.*, r.airline_id
    FROM state_at_endpoint s
    JOIN (
        SELECT raw_code, MIN(airline_id) AS airline_id
        FROM (
            SELECT DISTINCT c.raw_code, a.airline_id
            FROM (SELECT DISTINCT raw_airline_code AS raw_code FROM state_at_endpoint WHERE raw_airline_code IS NOT NULL) c
            JOIN PK_AVIATION_TEMPORAL.SOURCE.AIRLINE_REFERENCE a
              ON c.raw_code = a.airline_id
              OR c.raw_code = a.carrier_code_iata
              OR c.raw_code = a.carrier_code_icao
        )
        GROUP BY raw_code
        HAVING COUNT(DISTINCT airline_id) = 1
    ) r ON r.raw_code = s.raw_airline_code
),
market_counts AS (
    SELECT
        carrier_role, airline_id, route_id,
        COUNT(DISTINCT IFF(endpoint_kind = 'BEFORE', schedule_key, NULL)) AS before_schedule_count,
        COUNT(DISTINCT IFF(endpoint_kind = 'AFTER',  schedule_key, NULL)) AS after_schedule_count
    FROM resolved
    GROUP BY carrier_role, airline_id, route_id
)
SELECT
    m.carrier_role,
    m.airline_id,
    m.route_id,
    IFF(m.before_schedule_count = 0, 'ENTRY', 'EXIT')          AS change_kind,
    m.before_schedule_count::NUMBER(38,0)                      AS before_schedule_count,
    m.after_schedule_count::NUMBER(38,0)                       AS after_schedule_count,
    TO_VARCHAR((SELECT p_comparison FROM params), 'YYYY-MM-DD') AS comparison_knowledge_date,
    TO_VARCHAR((SELECT p_latest FROM params), 'YYYY-MM-DD')     AS latest_knowledge_date
FROM market_counts m
WHERE (m.before_schedule_count = 0 AND m.after_schedule_count > 0)
   OR (m.before_schedule_count > 0 AND m.after_schedule_count = 0)
ORDER BY change_kind, m.airline_id, m.route_id
