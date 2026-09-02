-- ============================================================================
-- Q08 actual_rotation_enriched -- independent SQL oracle over SOURCE
--
-- Parameters: aircraft_id (NUMBER(38,0)), flight_departure_date (DATE)
-- Order by  : segment_id, row_kind DESC, leg_order NULLS LAST, flight_id,
--             anomaly_code NULLS LAST
--
-- Rotation is the validated AF-20 self-reference. Selection uses the AF-06
-- source-local departure date, never AF-07 UTC lineage (TTUS-R05). Continuity
-- uses ACTUAL endpoints (AF-08 origin, DV-45 = AF-09 arrival) and ACTUAL gate
-- times (AF-13/AF-14). No scheduled arrival, planned station or IATA label is
-- ever substituted; actual endpoints are SYN-AP-* internal IDs.
--
-- A link is accepted only when the target exists, is a different flight, has
-- the same aircraft and the same AF-06, departs no earlier than the current
-- actual arrival, and departs from the current actual arrival airport.
-- Every failure stays visible as a typed anomaly, in the frozen precedence
-- SELF_LOOP, CYCLE, MISSING_TARGET, DIFFERENT_AIRCRAFT, OUTSIDE_SELECTED_DAY,
-- DIVERSION_ENDPOINT_CONFLICT, BACKWARD_TIME, BROKEN_CONTINUITY, CANCELLED,
-- MISSING_TIME, UNKNOWN_OR_INVALID_CANCELLATION_FLAG. Exactly one CYCLE row is
-- emitted per cycle component, anchored at its minimum flight_id.
--
-- Enrichment joins the independent daily type/engine assignments at AF-06;
-- AF-17 remains actual-source descriptive evidence and only sets
-- type_discrepancy, it never becomes aircraft-history authority.
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, params AS (
    SELECT {{aircraft_id}}::NUMBER(38,0)   AS p_aircraft_id,
           '{{flight_departure_date}}'::DATE AS p_departure_date
),
selected_leg AS (
    SELECT f.*
    FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_FLIGHT f, params p
    WHERE f.flight_id IS NOT NULL
      AND f.aircraft_id = p.p_aircraft_id
      AND f.flight_departure_date = p.p_departure_date
),
normalised AS (
    SELECT
        l.*,
        CASE WHEN l.is_cancelled = 0 THEN FALSE WHEN l.is_cancelled = 1 THEN TRUE ELSE NULL END AS cancel_flag,
        (l.is_cancelled IS NULL OR l.is_cancelled NOT IN (0, 1))                                AS cancel_flag_invalid,
        (l.actual_gate_departure_time_utc IS NULL OR l.actual_gate_arrival_time_utc IS NULL)    AS missing_time
    FROM selected_leg l
),
link_target AS (
    SELECT flight_id, aircraft_id, flight_departure_date,
           departure_airport_code, actual_gate_departure_time_utc
    FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_FLIGHT
    WHERE flight_id IS NOT NULL
),
linked AS (
    SELECT n.*,
           t.flight_id                     AS target_flight_id,
           t.aircraft_id                   AS target_aircraft_id,
           t.flight_departure_date         AS target_departure_date,
           t.departure_airport_code        AS target_origin,
           t.actual_gate_departure_time_utc AS target_departure_utc
    FROM normalised n
    LEFT JOIN link_target t ON t.flight_id = n.next_flight_id
),
graph_edge AS (
    SELECT n.flight_id AS src_id, n.next_flight_id AS dst_id
    FROM normalised n
    JOIN selected_leg s ON s.flight_id = n.next_flight_id
    WHERE n.next_flight_id IS NOT NULL
      AND n.next_flight_id <> n.flight_id
),
reachable (start_id, node_id, depth) AS (
    SELECT src_id, dst_id, 1 FROM graph_edge
    UNION ALL
    SELECT r.start_id, e.dst_id, r.depth + 1
    FROM reachable r JOIN graph_edge e ON e.src_id = r.node_id
    WHERE r.depth < 32
),
cycle_node AS (
    SELECT DISTINCT start_id AS flight_id FROM reachable WHERE node_id = start_id
),
mutual_reach AS (
    SELECT flight_id AS a_id, flight_id AS b_id FROM cycle_node
    UNION
    SELECT r1.start_id, r1.node_id
    FROM reachable r1
    JOIN reachable r2 ON r2.start_id = r1.node_id AND r2.node_id = r1.start_id
    WHERE r1.start_id IN (SELECT flight_id FROM cycle_node)
),
cycle_component AS (
    SELECT a_id AS flight_id, MIN(b_id) AS component_anchor
    FROM mutual_reach GROUP BY a_id
),
classified AS (
    SELECT
        l.*,
        cc.component_anchor,
        CASE
            WHEN l.next_flight_id = l.flight_id                                          THEN 'SELF_LOOP'
            WHEN cc.component_anchor IS NOT NULL                                         THEN 'CYCLE'
            WHEN l.next_flight_id IS NOT NULL AND l.target_flight_id IS NULL             THEN 'MISSING_TARGET'
            WHEN l.target_flight_id IS NOT NULL
                 AND l.target_aircraft_id IS DISTINCT FROM l.aircraft_id                 THEN 'DIFFERENT_AIRCRAFT'
            WHEN l.target_flight_id IS NOT NULL
                 AND l.target_departure_date IS DISTINCT FROM l.flight_departure_date    THEN 'OUTSIDE_SELECTED_DAY'
            WHEN l.diverted_airport_code IS NOT NULL
                 AND l.diverted_airport_code IS DISTINCT FROM l.arrival_airport_code     THEN 'DIVERSION_ENDPOINT_CONFLICT'
            WHEN l.target_flight_id IS NOT NULL
                 AND l.target_departure_utc < l.actual_gate_arrival_time_utc             THEN 'BACKWARD_TIME'
            WHEN l.target_flight_id IS NOT NULL
                 AND l.target_origin IS DISTINCT FROM l.arrival_airport_code             THEN 'BROKEN_CONTINUITY'
            WHEN l.cancel_flag                                                           THEN 'CANCELLED'
            WHEN l.missing_time                                                          THEN 'MISSING_TIME'
            WHEN l.cancel_flag_invalid                                                   THEN 'UNKNOWN_OR_INVALID_CANCELLATION_FLAG'
            ELSE NULL
        END AS anomaly_code
    FROM linked l
    LEFT JOIN cycle_component cc ON cc.flight_id = l.flight_id
),
accepted_link AS (
    SELECT flight_id, next_flight_id AS target_flight_id
    FROM classified
    WHERE anomaly_code IS NULL AND next_flight_id IS NOT NULL
),
chain_start AS (
    SELECT c.flight_id
    FROM classified c
    LEFT JOIN accepted_link a ON a.target_flight_id = c.flight_id
    WHERE c.anomaly_code IS NULL AND a.target_flight_id IS NULL
),
chain (root_id, flight_id, leg_order) AS (
    SELECT flight_id, flight_id, 1 FROM chain_start
    UNION ALL
    SELECT c.root_id, a.target_flight_id, c.leg_order + 1
    FROM chain c JOIN accepted_link a ON a.flight_id = c.flight_id
    WHERE c.leg_order < 64
),
segment_number AS (
    SELECT root_id, ROW_NUMBER() OVER (ORDER BY root_id) AS segment_ordinal
    FROM (SELECT DISTINCT root_id FROM chain)
),
anomaly_row AS (
    SELECT c.*,
           ROW_NUMBER() OVER (ORDER BY c.flight_id) AS anomaly_ordinal
    FROM classified c
    WHERE c.anomaly_code IS NOT NULL
      AND (c.anomaly_code <> 'CYCLE' OR c.component_anchor = c.flight_id)
),
type_at_date AS (
    SELECT d.aircraft_id, d.definition_id, d.definition_label, d.valid_from, d.valid_to
    FROM daily_assignment d WHERE d.dimension = 'aircraft_type' AND d.is_resolved
),
engine_at_date AS (
    SELECT d.aircraft_id, d.definition_id, d.valid_from, d.valid_to
    FROM daily_assignment d WHERE d.dimension = 'engine_type' AND d.is_resolved
),
leg_rows AS (
    SELECT
        'LEG'                                                        AS row_kind,
        'SYN-ROT-' || c.aircraft_id::VARCHAR || '-'
            || TO_VARCHAR(c.flight_departure_date, 'YYYYMMDD') || '-'
            || LPAD(s.segment_ordinal::VARCHAR, 2, '0')              AS segment_id,
        ch.leg_order::NUMBER(38,0)                                   AS leg_order,
        c.flight_id::NUMBER(38,0)                                    AS flight_id,
        c.departure_airport_code                                     AS actual_origin,
        c.arrival_airport_code                                       AS actual_destination,
        TO_VARCHAR(c.actual_gate_departure_time_utc, 'YYYY-MM-DD"T"HH24:MI:SS') AS actual_departure_utc,
        TO_VARCHAR(c.actual_gate_arrival_time_utc,   'YYYY-MM-DD"T"HH24:MI:SS') AS actual_arrival_utc,
        c.next_flight_id::NUMBER(38,0)                               AS next_flight_id,
        IFF(c.next_flight_id IS NULL, 'TERMINAL_NO_TARGET', 'ACCEPTED') AS link_outcome,
        NULL::VARCHAR                                                AS anomaly_code,
        t.definition_id                                              AS as_of_aircraft_type_id,
        e.definition_id                                              AS as_of_engine_type_id,
        c.aircraft_type                                              AS actual_source_aircraft_type,
        (c.aircraft_type IS DISTINCT FROM t.definition_label)        AS type_discrepancy
    FROM chain ch
    JOIN classified c        ON c.flight_id = ch.flight_id
    JOIN segment_number s    ON s.root_id = ch.root_id
    LEFT JOIN type_at_date t ON t.aircraft_id = c.aircraft_id
                            AND t.valid_from <= c.flight_departure_date
                            AND c.flight_departure_date < t.valid_to
    LEFT JOIN engine_at_date e ON e.aircraft_id = c.aircraft_id
                              AND e.valid_from <= c.flight_departure_date
                              AND c.flight_departure_date < e.valid_to
),
anomaly_rows AS (
    SELECT
        'ANOMALY'                                                    AS row_kind,
        'SYN-ANOM-' || LPAD(a.anomaly_ordinal::VARCHAR, 2, '0')      AS segment_id,
        NULL::NUMBER(38,0)                                           AS leg_order,
        a.flight_id::NUMBER(38,0)                                    AS flight_id,
        a.departure_airport_code                                     AS actual_origin,
        a.arrival_airport_code                                       AS actual_destination,
        TO_VARCHAR(a.actual_gate_departure_time_utc, 'YYYY-MM-DD"T"HH24:MI:SS') AS actual_departure_utc,
        TO_VARCHAR(a.actual_gate_arrival_time_utc,   'YYYY-MM-DD"T"HH24:MI:SS') AS actual_arrival_utc,
        a.next_flight_id::NUMBER(38,0)                               AS next_flight_id,
        IFF(a.anomaly_code IN ('CANCELLED', 'MISSING_TIME', 'UNKNOWN_OR_INVALID_CANCELLATION_FLAG'),
            'EXCLUDED', 'REJECTED')                                  AS link_outcome,
        a.anomaly_code,
        NULL::VARCHAR, NULL::VARCHAR, NULL::VARCHAR, NULL::BOOLEAN
    FROM anomaly_row a
)
SELECT * FROM (
    SELECT * FROM leg_rows
    UNION ALL
    SELECT * FROM anomaly_rows
)
ORDER BY segment_id, row_kind DESC, leg_order NULLS LAST, flight_id, anomaly_code NULLS LAST
