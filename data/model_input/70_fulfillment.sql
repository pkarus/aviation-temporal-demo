-- DATA-04a: optional plan-to-actual fulfillment evidence.
--
-- P0-10.4 - P0-10.6:
--   * fulfillment is optional in both directions and may be one passenger flight to many actual
--     legs; unmatched passenger and actual rows stay first-class results;
--   * EXACT_FULFILLMENT requires the non-null direct shared source ID (PH-01 = AF-01 in this
--     reduced contract) plus operating-date and resolved-carrier sanity checks;
--   * a heuristic composite is NEVER labelled exact and candidate links are stored separately
--     from confirmed fulfillment;
--   * an actual leg with exactly one compatible PassengerFlight is HEURISTIC_CANDIDATE; a
--     connected component in which any actual leg has multiple compatible passenger candidates is
--     ambiguous with all members retained and no chosen link.

CREATE OR REPLACE TABLE MODEL_INPUT.FULFILLMENT_EXACT
  COMMENT = 'Confirmed plan-to-actual fulfillment. Grain DV-39 = SHA-256 over AF-01, DV-20 and the literal EXACT. Requires the direct shared historical-flight ID (PH-01 = AF-01) plus operating-date and exact resolved carrier-role agreement. Several historical lineage rows coalescing to one DV-20 legitimately confirm one passenger service to many actual legs.'
AS
SELECT
  SHA2(MODEL_INPUT.LP(TO_VARCHAR(af.flight_id)) || MODEL_INPUT.LP(l.passenger_flight_key)
       || MODEL_INPUT.LP('EXACT'), 256)                       AS exact_fulfillment_id,
  af.flight_id                                                AS actual_flight_id,
  l.passenger_flight_key,
  l.source_system                                             AS passenger_source_system,
  l.source_row_token                                          AS passenger_source_row_token,
  l.stable_source_row_id                                      AS passenger_stable_source_row_id,
  'EXACT_FULFILLMENT'::VARCHAR                                AS fulfillment_class,
  'EXACT'::VARCHAR                                            AS exactness,
  'DIRECT_SHARED_HISTORICAL_FLIGHT_ID'::VARCHAR               AS exact_link_basis,
  TRUE                                                        AS confirmed_link,
  af.flight_departure_date                                    AS actual_operating_date,
  pfc.operating_date                                          AS planned_operating_date,
  af.marketing_airline_id                                     AS actual_marketing_airline_id,
  pfc.marketing_airline_id                                    AS planned_marketing_airline_id,
  af.operating_airline_id                                     AS actual_operating_airline_id,
  pfc.operating_airline_id                                    AS planned_operating_airline_id,
  af.normalized_flight_number,
  pfc.flight_number                                           AS planned_flight_number,
  af.actual_origin_airport_id,
  af.actual_destination_airport_id
FROM MODEL_INPUT.PASSENGER_SOURCE_LINEAGE l
JOIN MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL pfc ON pfc.passenger_flight_key = l.passenger_flight_key
JOIN MODEL_INPUT.AIRCRAFT_FLIGHT af ON af.flight_id = l.stable_source_row_id
WHERE l.source_system = 'HISTORICAL'
  AND l.stable_source_row_id IS NOT NULL
  AND af.flight_departure_date = pfc.operating_date
  AND af.marketing_airline_resolution_status = 'EXACT'
  AND pfc.marketing_airline_resolution_status = 'EXACT'
  AND af.marketing_airline_id = pfc.marketing_airline_id
  AND af.operating_airline_resolution_status = 'EXACT'
  AND pfc.operating_airline_resolution_status = 'EXACT'
  AND af.operating_airline_id = pfc.operating_airline_id;

-- ---------------------------------------------------------------------------------------------
-- Compatibility graph.  The ordered planned station sequence is `origin, intermediate stops,
-- destination`, parsed in the contracted source order and never sorted.  An actual leg must
-- occupy a valid consecutive leg of that sequence, compared through resolved airport identities
-- because planned endpoints are IATA codes and actual endpoints are internal IDs.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.PASSENGER_PLANNED_LEG
  COMMENT = 'Declared derivation: each consecutive leg of a canonical passenger flight ordered station sequence (planned origin, contracted intermediate stops in source order, planned destination), with resolved airport identities.'
AS
WITH stations AS (
  SELECT
    p.passenger_flight_key,
    ARRAY_CAT(
      ARRAY_CAT(
        ARRAY_CONSTRUCT(p.planned_origin_station_code_iata),
        IFF(p.intermediate_stop_station_codes_iata IS NULL
            OR TRIM(p.intermediate_stop_station_codes_iata) = '',
            ARRAY_CONSTRUCT(),
            SPLIT(p.intermediate_stop_station_codes_iata, ','))
      ),
      ARRAY_CONSTRUCT(p.planned_destination_station_code_iata)
    ) AS station_sequence
  FROM MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL p
), legs AS (
  SELECT
    s.passenger_flight_key,
    f.INDEX                                             AS leg_index,
    TRIM(f.VALUE::VARCHAR)                              AS from_station_code_iata,
    TRIM(GET(s.station_sequence, f.INDEX + 1)::VARCHAR) AS to_station_code_iata,
    ARRAY_SIZE(s.station_sequence)                      AS station_count
  FROM stations s, LATERAL FLATTEN(INPUT => s.station_sequence) f
  WHERE f.INDEX < ARRAY_SIZE(s.station_sequence) - 1
)
SELECT
  l.passenger_flight_key,
  l.leg_index,
  l.from_station_code_iata,
  l.to_station_code_iata,
  l.station_count,
  fr.single_candidate_id                                AS from_airport_id,
  COALESCE(fr.resolution_status, 'UNRESOLVED')::VARCHAR AS from_airport_resolution_status,
  toa.single_candidate_id                               AS to_airport_id,
  COALESCE(toa.resolution_status, 'UNRESOLVED')::VARCHAR AS to_airport_resolution_status
FROM legs l
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE fr
  ON fr.method = 'AIRPORT_IATA_EXACT' AND fr.raw_code = l.from_station_code_iata
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE toa
  ON toa.method = 'AIRPORT_IATA_EXACT' AND toa.raw_code = l.to_station_code_iata;

CREATE OR REPLACE TABLE MODEL_INPUT.FULFILLMENT_COMPATIBILITY
  COMMENT = 'Declared derivation: the bipartite actual-leg to passenger-flight compatibility graph. Requires exact resolved carrier-role agreement in at least one role, DV-38 equal to the planned flight number, AF-06 equal to the planned operating date, and actual endpoints occupying a valid consecutive planned leg. Actual legs already carrying an exact fulfillment are excluded.'
AS
SELECT DISTINCT
  af.flight_id                                          AS actual_flight_id,
  pl.passenger_flight_key,
  pl.leg_index,
  pl.station_count,
  (af.marketing_airline_resolution_status = 'EXACT'
   AND p.marketing_airline_resolution_status = 'EXACT'
   AND af.marketing_airline_id = p.marketing_airline_id) AS marketing_role_agrees,
  (af.operating_airline_resolution_status = 'EXACT'
   AND p.operating_airline_resolution_status = 'EXACT'
   AND af.operating_airline_id = p.operating_airline_id) AS operating_role_agrees,
  af.normalized_flight_number,
  af.flight_departure_date                              AS actual_operating_date,
  af.actual_origin_airport_id,
  af.actual_destination_airport_id
FROM MODEL_INPUT.AIRCRAFT_FLIGHT af
JOIN MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL p
  ON p.operating_date = af.flight_departure_date
 AND p.flight_number = af.normalized_flight_number
JOIN MODEL_INPUT.PASSENGER_PLANNED_LEG pl
  ON pl.passenger_flight_key = p.passenger_flight_key
 AND pl.from_airport_id = af.actual_origin_airport_id
 AND pl.to_airport_id   = af.actual_destination_airport_id
WHERE af.flight_number_status = 'NORMALIZED'
  AND af.actual_origin_airport_resolution_status = 'EXACT'
  AND af.actual_destination_airport_resolution_status = 'EXACT'
  AND pl.from_airport_resolution_status = 'EXACT'
  AND pl.to_airport_resolution_status = 'EXACT'
  AND ((af.marketing_airline_resolution_status = 'EXACT'
        AND p.marketing_airline_resolution_status = 'EXACT'
        AND af.marketing_airline_id = p.marketing_airline_id)
    OR (af.operating_airline_resolution_status = 'EXACT'
        AND p.operating_airline_resolution_status = 'EXACT'
        AND af.operating_airline_id = p.operating_airline_id))
  AND NOT EXISTS (SELECT 1 FROM MODEL_INPUT.FULFILLMENT_EXACT fe
                  WHERE fe.actual_flight_id = af.flight_id);

CREATE OR REPLACE TABLE MODEL_INPUT.FULFILLMENT_CANDIDATE
  COMMENT = 'Heuristic plan-to-actual candidate. Grain DV-40 = SHA-256 over AF-01, DV-20 and the literal HEURISTIC. Emitted only when the actual leg has exactly one compatible PassengerFlight; many actual legs may independently share the same unique passenger candidate, preserving the one-to-many stopover shape. Never exact and never promoted.'
AS
WITH degree AS (
  SELECT actual_flight_id, COUNT(DISTINCT passenger_flight_key) AS passenger_candidate_count
  FROM MODEL_INPUT.FULFILLMENT_COMPATIBILITY GROUP BY actual_flight_id
), unique_actual AS (
  SELECT actual_flight_id FROM degree WHERE passenger_candidate_count = 1
)
SELECT
  SHA2(MODEL_INPUT.LP(TO_VARCHAR(c.actual_flight_id)) || MODEL_INPUT.LP(c.passenger_flight_key)
       || MODEL_INPUT.LP('HEURISTIC'), 256)                    AS fulfillment_candidate_id,
  c.actual_flight_id,
  c.passenger_flight_key,
  'HEURISTIC_CANDIDATE'::VARCHAR                               AS fulfillment_class,
  'CANDIDATE'::VARCHAR                                         AS exactness,
  'MEDIUM'::VARCHAR                                            AS confidence,
  FALSE                                                        AS confirmed_link,
  c.marketing_role_agrees,
  c.operating_role_agrees,
  c.normalized_flight_number,
  c.actual_operating_date,
  c.leg_index,
  c.station_count,
  (c.station_count > 2)                                        AS planned_service_has_stopovers,
  c.actual_origin_airport_id,
  c.actual_destination_airport_id
FROM MODEL_INPUT.FULFILLMENT_COMPATIBILITY c
JOIN unique_actual u ON u.actual_flight_id = c.actual_flight_id;

CREATE OR REPLACE TABLE MODEL_INPUT.FULFILLMENT_AMBIGUOUS_GROUP
  COMMENT = 'Member-grain table for ambiguous fulfillment components and for unmatched observations. Grain DV-42 member_id; DV-41 group_id is SHA-256 over the sorted actual IDs and passenger keys of a connected component in which at least one actual leg has multiple compatible passenger candidates. Unmatched actual and passenger observations carry a deterministic source/business identity, a null group and a reason; no link is ever chosen here.'
AS
WITH edges AS (
  SELECT DISTINCT 'A|' || TO_VARCHAR(actual_flight_id) AS a_node,
                  'P|' || passenger_flight_key         AS p_node,
                  actual_flight_id, passenger_flight_key
  FROM MODEL_INPUT.FULFILLMENT_COMPATIBILITY
), undirected AS (
  SELECT a_node AS src, p_node AS dst FROM edges
  UNION
  SELECT p_node, a_node FROM edges
), closure (src, dst, depth) AS (
  SELECT u.src, u.dst, 1 FROM undirected u
  UNION ALL
  SELECT c.src, u.dst, c.depth + 1
  FROM closure c JOIN undirected u ON u.src = c.dst
  WHERE c.depth < 8
), node_component AS (
  SELECT src AS node, LEAST(MIN(dst), src) AS component_root
  FROM closure GROUP BY src
), actual_degree AS (
  SELECT actual_flight_id, COUNT(DISTINCT passenger_flight_key) AS passenger_candidate_count
  FROM MODEL_INPUT.FULFILLMENT_COMPATIBILITY GROUP BY actual_flight_id
), component_members AS (
  SELECT
    nc.component_root,
    nc.node,
    IFF(LEFT(nc.node, 2) = 'A|', 'ACTUAL', 'PASSENGER')::VARCHAR AS side,
    SUBSTR(nc.node, 3)                                           AS member_identity
  FROM node_component nc
), ambiguous_component AS (
  SELECT DISTINCT cm.component_root
  FROM component_members cm
  JOIN actual_degree d ON cm.side = 'ACTUAL' AND TO_VARCHAR(d.actual_flight_id) = cm.member_identity
  WHERE d.passenger_candidate_count > 1
), component_identity AS (
  SELECT
    cm.component_root,
    SHA2(MODEL_INPUT.LP(LISTAGG(DISTINCT IFF(cm.side = 'ACTUAL', cm.member_identity, NULL), ',')
                          WITHIN GROUP (ORDER BY IFF(cm.side = 'ACTUAL', cm.member_identity, NULL)))
         || MODEL_INPUT.LP(LISTAGG(DISTINCT IFF(cm.side = 'PASSENGER', cm.member_identity, NULL), ',')
                          WITHIN GROUP (ORDER BY IFF(cm.side = 'PASSENGER', cm.member_identity, NULL))), 256)
                                                                 AS fulfillment_group_id,
    COUNT(DISTINCT IFF(cm.side = 'ACTUAL', cm.member_identity, NULL))    AS actual_member_count,
    COUNT(DISTINCT IFF(cm.side = 'PASSENGER', cm.member_identity, NULL)) AS passenger_member_count
  FROM component_members cm
  JOIN ambiguous_component ac ON ac.component_root = cm.component_root
  GROUP BY cm.component_root
), ambiguous_rows AS (
  SELECT
    SHA2(MODEL_INPUT.LP(ci.fulfillment_group_id) || MODEL_INPUT.LP(cm.side)
         || MODEL_INPUT.LP(cm.member_identity), 256)             AS fulfillment_group_member_id,
    ci.fulfillment_group_id,
    cm.side,
    cm.member_identity,
    'AMBIGUOUS_GROUP_MEMBER'::VARCHAR                            AS member_class,
    'AMBIGUOUS'::VARCHAR                                         AS exactness,
    'LOW'::VARCHAR                                               AS confidence,
    FALSE                                                        AS confirmed_link,
    ci.actual_member_count,
    ci.passenger_member_count,
    NULL::VARCHAR                                                AS unmatched_reason
  FROM component_members cm
  JOIN component_identity ci ON ci.component_root = cm.component_root
), unmatched_actual AS (
  SELECT
    SHA2(MODEL_INPUT.LP('UNMATCHED') || MODEL_INPUT.LP('ACTUAL')
         || MODEL_INPUT.LP(TO_VARCHAR(af.flight_id)), 256)       AS fulfillment_group_member_id,
    NULL::VARCHAR                                                AS fulfillment_group_id,
    'ACTUAL'::VARCHAR                                            AS side,
    TO_VARCHAR(af.flight_id)                                     AS member_identity,
    'UNMATCHED_ACTUAL'::VARCHAR                                  AS member_class,
    'UNMATCHED'::VARCHAR                                         AS exactness,
    'NONE'::VARCHAR                                              AS confidence,
    FALSE                                                        AS confirmed_link,
    NULL::NUMBER(38,0)                                           AS actual_member_count,
    NULL::NUMBER(38,0)                                           AS passenger_member_count,
    CASE WHEN af.flight_number_status <> 'NORMALIZED' THEN 'INVALID_FLIGHT_NUMBER'
         WHEN af.actual_origin_airport_resolution_status <> 'EXACT'
           OR af.actual_destination_airport_resolution_status <> 'EXACT'
                                                      THEN 'UNRESOLVED_ACTUAL_ENDPOINT'
         ELSE 'NO_COMPATIBLE_PASSENGER_FLIGHT' END::VARCHAR      AS unmatched_reason
  FROM MODEL_INPUT.AIRCRAFT_FLIGHT af
  WHERE NOT EXISTS (SELECT 1 FROM MODEL_INPUT.FULFILLMENT_EXACT fe WHERE fe.actual_flight_id = af.flight_id)
    AND NOT EXISTS (SELECT 1 FROM MODEL_INPUT.FULFILLMENT_COMPATIBILITY fc WHERE fc.actual_flight_id = af.flight_id)
), unmatched_passenger AS (
  SELECT
    SHA2(MODEL_INPUT.LP('UNMATCHED') || MODEL_INPUT.LP('PASSENGER')
         || MODEL_INPUT.LP(p.passenger_flight_key), 256)         AS fulfillment_group_member_id,
    NULL::VARCHAR                                                AS fulfillment_group_id,
    'PASSENGER'::VARCHAR                                         AS side,
    p.passenger_flight_key                                       AS member_identity,
    'UNMATCHED_PASSENGER'::VARCHAR                               AS member_class,
    'UNMATCHED'::VARCHAR                                         AS exactness,
    'NONE'::VARCHAR                                              AS confidence,
    FALSE                                                        AS confirmed_link,
    NULL::NUMBER(38,0)                                           AS actual_member_count,
    NULL::NUMBER(38,0)                                           AS passenger_member_count,
    'NO_COMPATIBLE_ACTUAL_FLIGHT'::VARCHAR                       AS unmatched_reason
  FROM MODEL_INPUT.PASSENGER_FLIGHT_CANONICAL p
  WHERE NOT EXISTS (SELECT 1 FROM MODEL_INPUT.FULFILLMENT_EXACT fe WHERE fe.passenger_flight_key = p.passenger_flight_key)
    AND NOT EXISTS (SELECT 1 FROM MODEL_INPUT.FULFILLMENT_COMPATIBILITY fc WHERE fc.passenger_flight_key = p.passenger_flight_key)
)
SELECT * FROM ambiguous_rows
UNION ALL SELECT * FROM unmatched_actual
UNION ALL SELECT * FROM unmatched_passenger;
