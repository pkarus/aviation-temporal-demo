-- ============================================================================
-- Q07 route_capacity_two_clocks -- independent SQL oracle over SOURCE
--
-- Parameters: knowledge_date (DATE), operating_date (DATE),
--             carrier_role ('marketing'|'operating')
-- Order by  : result_status ASC, airline_id ASC, route_id ASC
--
-- Two explicit clocks, never conflated:
--   knowledge clock  half-open  RouteState.valid_from <= knowledge_date < valid_to
--   operating clock  inclusive  SS-08 <= operating_date <= SS-09 AND the
--                               operating weekday flag for that calendar day
--
-- Carrier roles stay separate. Marketing counts distinct eligible schedule
-- states under the marketing role. Operating counts only an unambiguous
-- physical base representative: marketing and operating carriers resolve to the
-- same airline and the row is not a codeshare, so physical capacity is never
-- double counted. An operating market with no base representative is
-- UNRESOLVED_PHYSICAL_SERVICE and is excluded, never guessed.
--
-- Cabin reconciliation keeps raw SS-30..SS-34. Premium economy is a subset of
-- economy, so the exclusive economy bucket is economy - premium. A null,
-- negative or non-reconciling cabin vector is flagged and cannot contribute to
-- an evidence-backed reconciled total.
-- ============================================================================
WITH
{{SCHEDULE_TEMPORAL}}
, params AS (
    SELECT '{{knowledge_date}}'::DATE  AS p_knowledge_date,
           '{{operating_date}}'::DATE  AS p_operating_date,
           '{{carrier_role}}'          AS p_carrier_role
),
knowledge_visible AS (
    SELECT r.*
    FROM route_state r, params p
    WHERE r.knowledge_valid_from <= p.p_knowledge_date
      AND p.p_knowledge_date < r.knowledge_valid_to
),
operating_eligible AS (
    SELECT k.*
    FROM knowledge_visible k, params p
    WHERE k.route_valid
      AND k.effective_date   IS NOT NULL
      AND k.discontinue_date IS NOT NULL
      AND k.effective_date <= p.p_operating_date
      AND p.p_operating_date <= k.discontinue_date
      AND CASE DAYOFWEEKISO(p.p_operating_date)
              WHEN 1 THEN COALESCE(k.is_operating_monday,    FALSE)
              WHEN 2 THEN COALESCE(k.is_operating_tuesday,   FALSE)
              WHEN 3 THEN COALESCE(k.is_operating_wednesday, FALSE)
              WHEN 4 THEN COALESCE(k.is_operating_thursday,  FALSE)
              WHEN 5 THEN COALESCE(k.is_operating_friday,    FALSE)
              WHEN 6 THEN COALESCE(k.is_operating_saturday,  FALSE)
              ELSE        COALESCE(k.is_operating_sunday,    FALSE)
          END
),
airline_resolution AS (
    SELECT raw_code, MIN(airline_id) AS airline_id
    FROM (
        SELECT DISTINCT c.raw_code, a.airline_id
        FROM (
            SELECT DISTINCT marketing_carrier_internal AS raw_code FROM operating_eligible WHERE marketing_carrier_internal IS NOT NULL
            UNION
            SELECT DISTINCT operating_carrier_internal FROM operating_eligible WHERE operating_carrier_internal IS NOT NULL
        ) c
        JOIN PK_AVIATION_TEMPORAL.SOURCE.AIRLINE_REFERENCE a
          ON c.raw_code = a.airline_id
          OR c.raw_code = a.carrier_code_iata
          OR c.raw_code = a.carrier_code_icao
    )
    GROUP BY raw_code
    HAVING COUNT(DISTINCT airline_id) = 1
),
priced AS (
    SELECT
        o.schedule_key, o.route_id,
        mr.airline_id AS marketing_airline_id,
        opr.airline_id AS operating_airline_id,
        COALESCE(o.is_codeshare, FALSE) AS is_codeshare,
        o.weekly_frequency,
        o.total_seats, o.first_class_seats, o.business_class_seats,
        o.premium_economy_seats, o.economy_class_seats,
        (o.economy_class_seats - o.premium_economy_seats) AS economy_excluding_premium_seats,
        CASE
            WHEN o.total_seats IS NULL OR o.first_class_seats IS NULL
              OR o.business_class_seats IS NULL OR o.premium_economy_seats IS NULL
              OR o.economy_class_seats IS NULL                                   THEN 'NULL_CABIN_VALUE'
            WHEN o.total_seats < 0 OR o.first_class_seats < 0
              OR o.business_class_seats < 0 OR o.premium_economy_seats < 0
              OR o.economy_class_seats < 0                                       THEN 'NEGATIVE_CABIN_VALUE'
            WHEN o.premium_economy_seats > o.economy_class_seats                 THEN 'PREMIUM_EXCEEDS_ECONOMY'
            WHEN (o.first_class_seats + o.business_class_seats + o.economy_class_seats)
                 <> o.total_seats                                                THEN 'TOTAL_MISMATCH'
            ELSE 'RECONCILED'
        END AS cabin_quality,
        -- physical base representative: same resolved airline in both roles and
        -- not a codeshare copy of somebody else's metal.
        (mr.airline_id IS NOT NULL
         AND opr.airline_id IS NOT NULL
         AND mr.airline_id = opr.airline_id
         AND NOT COALESCE(o.is_codeshare, FALSE)) AS is_physical_base_representative
    FROM operating_eligible o
    LEFT JOIN airline_resolution mr  ON mr.raw_code  = o.marketing_carrier_internal
    LEFT JOIN airline_resolution opr ON opr.raw_code = o.operating_carrier_internal
),
roled AS (
    SELECT p.*,
           (SELECT p_carrier_role FROM params) AS carrier_role,
           IFF((SELECT p_carrier_role FROM params) = 'marketing',
               p.marketing_airline_id, p.operating_airline_id) AS airline_id,
           IFF((SELECT p_carrier_role FROM params) = 'marketing',
               TRUE, p.is_physical_base_representative)        AS counts_towards_capacity
    FROM priced p
    WHERE IFF((SELECT p_carrier_role FROM params) = 'marketing',
              p.marketing_airline_id, p.operating_airline_id) IS NOT NULL
),
market AS (
    SELECT
        carrier_role, airline_id, route_id,
        COUNT_IF(counts_towards_capacity)                                      AS counted_states,
        COUNT(*)                                                               AS total_states,
        SUM(IFF(counts_towards_capacity, weekly_frequency, 0))                 AS weekly_frequency,
        SUM(IFF(counts_towards_capacity, weekly_frequency * total_seats, 0))               AS weekly_total_seats,
        SUM(IFF(counts_towards_capacity, weekly_frequency * first_class_seats, 0))         AS weekly_first_seats,
        SUM(IFF(counts_towards_capacity, weekly_frequency * business_class_seats, 0))      AS weekly_business_seats,
        SUM(IFF(counts_towards_capacity, weekly_frequency * premium_economy_seats, 0))     AS weekly_premium_economy_seats,
        SUM(IFF(counts_towards_capacity, weekly_frequency * economy_excluding_premium_seats, 0))
                                                                                           AS weekly_economy_excluding_premium_seats,
        BOOLAND_AGG(IFF(counts_towards_capacity, cabin_quality = 'RECONCILED', TRUE))      AS all_reconciled,
        MIN(IFF(NOT counts_towards_capacity, schedule_key, NULL))                          AS unresolved_service_key
    FROM roled
    GROUP BY carrier_role, airline_id, route_id
)
SELECT
    IFF(counted_states > 0, 'COUNTED', 'UNRESOLVED_PHYSICAL_SERVICE')  AS result_status,
    carrier_role,
    airline_id,
    route_id,
    TO_VARCHAR((SELECT p_knowledge_date FROM params), 'YYYY-MM-DD')    AS knowledge_date,
    TO_VARCHAR((SELECT p_operating_date FROM params), 'YYYY-MM-DD')    AS operating_date,
    IFF(counted_states > 0, counted_states::NUMBER(38,0), NULL)        AS active_schedule_count,
    IFF(counted_states > 0, weekly_frequency::NUMBER(38,0), NULL)      AS weekly_frequency,
    IFF(counted_states > 0, weekly_total_seats::FLOAT, NULL)           AS weekly_total_seats,
    IFF(counted_states > 0, weekly_first_seats::FLOAT, NULL)           AS weekly_first_seats,
    IFF(counted_states > 0, weekly_business_seats::FLOAT, NULL)        AS weekly_business_seats,
    IFF(counted_states > 0, weekly_premium_economy_seats::FLOAT, NULL) AS weekly_premium_economy_seats,
    IFF(counted_states > 0, weekly_economy_excluding_premium_seats::FLOAT, NULL)
                                                                       AS weekly_economy_excluding_premium_seats,
    CASE WHEN counted_states = 0 THEN 'NOT_COUNTED'
         WHEN all_reconciled     THEN 'RECONCILED'
         ELSE 'UNRECONCILED' END                                       AS cabin_quality,
    IFF(counted_states > 0, NULL, unresolved_service_key)              AS unresolved_service_key
FROM market
ORDER BY result_status, airline_id, route_id
