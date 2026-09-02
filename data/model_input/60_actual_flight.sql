-- DATA-04a: actual flown legs and rotation self-reference validation.
--
-- Actual facts never overwrite plan facts and the plan never repairs actual continuity.
-- DV-45 actual_continuity_arrival_code is exactly AF-09.  AF-10 and DV-53 are reconciliation
-- evidence only: a non-null AF-10 that disagrees with AF-09 emits DIVERSION_ENDPOINT_CONFLICT and
-- terminates continuity regardless of the diversion flag, and never repairs AF-09.
-- DV-52/DV-53 map integer 0 to false and 1 to true; null or any other value is
-- UNKNOWN_OR_INVALID and excludes the leg from the strict operated chain while staying visible.
-- DV-38 trims AF-05, accepts ASCII digits only and casts to NUMBER(38,0); every other form keeps
-- the raw AF-05, emits INVALID_FLIGHT_NUMBER and is ineligible for exact or heuristic matching.

CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_FLIGHT
  COMMENT = 'Actual flown-leg observation. Grain AF-01. Carries AF-01..AF-20 as actual facts, DV-38 normalized flight number, DV-45 continuity arrival code, DV-52/DV-53 normalized flags, optional exact aircraft/airport/airline links, their resolution statuses and the raw codes. AF-06 is the source-local selected-day basis; AF-07 is UTC lineage and never substitutes for it.'
AS
SELECT
  a.flight_id,
  a.aircraft_id,
  ae.aircraft_id IS NOT NULL                             AS aircraft_link_exists,
  a.operating_carrier_code,
  a.marketing_carrier_code,
  a.flight_number                                        AS raw_flight_number,
  IFF(REGEXP_LIKE(TRIM(a.flight_number), '^[0-9]+$'),
      CAST(TRIM(a.flight_number) AS NUMBER(38,0)), NULL) AS normalized_flight_number,
  IFF(REGEXP_LIKE(TRIM(a.flight_number), '^[0-9]+$'),
      'NORMALIZED', 'INVALID_FLIGHT_NUMBER')::VARCHAR    AS flight_number_status,
  a.flight_departure_date,
  a.flight_departure_date_utc,
  a.departure_airport_code,
  a.arrival_airport_code,
  a.arrival_airport_code                                 AS actual_continuity_arrival_code,
  a.diverted_airport_code,
  a.is_cancelled                                         AS raw_is_cancelled,
  CASE WHEN a.is_cancelled = 0 THEN FALSE WHEN a.is_cancelled = 1 THEN TRUE END
                                                         AS is_cancelled_boolean,
  IFF(a.is_cancelled IN (0, 1), 'NORMALIZED',
      'UNKNOWN_OR_INVALID_CANCELLATION_FLAG')::VARCHAR   AS cancellation_flag_status,
  a.is_diverted                                          AS raw_is_diverted,
  CASE WHEN a.is_diverted = 0 THEN FALSE WHEN a.is_diverted = 1 THEN TRUE END
                                                         AS is_diverted_boolean,
  IFF(a.is_diverted IN (0, 1), 'NORMALIZED',
      'UNKNOWN_OR_INVALID_DIVERSION_FLAG')::VARCHAR      AS diversion_flag_status,
  (a.diverted_airport_code IS NOT NULL
   AND NOT EQUAL_NULL(a.diverted_airport_code, a.arrival_airport_code))
                                                         AS diversion_endpoint_conflict,
  a.actual_gate_departure_time_utc,
  a.actual_gate_arrival_time_utc,
  a.actual_gate_departure_time_local,
  a.actual_gate_arrival_time_local,
  a.aircraft_type                                        AS actual_source_aircraft_type,
  a.aircraft_code_iata                                   AS actual_source_aircraft_code_iata,
  a.aircraft_family                                      AS actual_source_aircraft_family,
  a.next_flight_id,
  dep.single_candidate_id                                AS actual_origin_airport_id,
  CASE WHEN a.departure_airport_code IS NULL THEN 'INVALID_INPUT'
       WHEN dep.raw_code IS NULL THEN 'UNRESOLVED' ELSE dep.resolution_status END::VARCHAR
                                                         AS actual_origin_airport_resolution_status,
  arr.single_candidate_id                                AS actual_destination_airport_id,
  CASE WHEN a.arrival_airport_code IS NULL THEN 'INVALID_INPUT'
       WHEN arr.raw_code IS NULL THEN 'UNRESOLVED' ELSE arr.resolution_status END::VARCHAR
                                                         AS actual_destination_airport_resolution_status,
  div.single_candidate_id                                AS diverted_airport_id,
  CASE WHEN a.diverted_airport_code IS NULL THEN 'INVALID_INPUT'
       WHEN div.raw_code IS NULL THEN 'UNRESOLVED' ELSE div.resolution_status END::VARCHAR
                                                         AS diverted_airport_resolution_status,
  opc.single_candidate_id                                AS operating_airline_id,
  CASE WHEN a.operating_carrier_code IS NULL THEN 'INVALID_INPUT'
       WHEN opc.raw_code IS NULL THEN 'UNRESOLVED' ELSE opc.resolution_status END::VARCHAR
                                                         AS operating_airline_resolution_status,
  mkc.single_candidate_id                                AS marketing_airline_id,
  CASE WHEN a.marketing_carrier_code IS NULL THEN 'INVALID_INPUT'
       WHEN mkc.raw_code IS NULL THEN 'UNRESOLVED' ELSE mkc.resolution_status END::VARCHAR
                                                         AS marketing_airline_resolution_status
FROM SOURCE.AIRCRAFT_FLIGHT a
LEFT JOIN MODEL_INPUT.AIRCRAFT_ELIGIBLE ae ON ae.aircraft_id = a.aircraft_id
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE dep
  ON dep.method = 'AIRPORT_INTERNAL_ID_EXACT' AND dep.raw_code = a.departure_airport_code
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE arr
  ON arr.method = 'AIRPORT_INTERNAL_ID_EXACT' AND arr.raw_code = a.arrival_airport_code
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE div
  ON div.method = 'AIRPORT_INTERNAL_ID_EXACT' AND div.raw_code = a.diverted_airport_code
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE opc
  ON opc.method = 'AIRLINE_INTERNAL_ID_EXACT' AND opc.raw_code = a.operating_carrier_code
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE mkc
  ON mkc.method = 'AIRLINE_INTERNAL_ID_EXACT' AND mkc.raw_code = a.marketing_carrier_code
WHERE a.flight_id IS NOT NULL;

-- ---------------------------------------------------------------------------------------------
-- ROTATION_LINK_VALIDATION.
-- A null next link is a terminal fact, not a nullable identity, so target_token is the literal
-- NO_TARGET.
--
-- ANOMALY PRECEDENCE IS CONTRACTED, NOT DERIVED HERE (D-0021).  DV-25 is single-valued, so a
-- precedence is required for it to be well defined, and the contract supplies exactly one ordering
-- of its vocabulary, twice:
--   ATTRIBUTE_AUTHORITY.md:338 (DV-25) "Typed self/cycle/missing/different/day/time/continuity/
--     diversion-conflict/cancel/missing-time reason."
--   SOURCE_CONTRACT.md:363-366  the same sequence in prose.
-- Both ship in commit 15d8f35, before EXPECTED_ANSWERS.yaml existed, so the manifest was written
-- from this enumeration rather than the reverse.  Do not re-derive it; cite it.
--
-- Two independent supports for CYCLE above BACKWARD_TIME, neither of which needs the manifest:
--   * subsumption.  Gate times are totally ordered, so every timed directed cycle must contain at
--     least one link whose target departs before the source arrives.  BACKWARD_TIME is a necessary
--     consequence of CYCLE and never the reverse, so the consequence cannot outrank its cause.
--     Ranking time above cycle would also split one indivisible structural defect across two
--     diagnoses, one per cycle arm.
--   * actionability.  No timestamp correction can repair 8102 -> 8103 -> 8102.
--
-- Applied order, highest first:
--   leg tier   : UNKNOWN_OR_INVALID_CANCELLATION_FLAG, CANCELLED, MISSING_TIME  -> EXCLUDED.
--                Hoisted above the link classes deliberately and on contract authority: DV-52 says
--                an invalid or true cancellation flag "excludes the leg from the strict operated
--                chain", and P0-11.3 states non-cancelled plus present actual times as chain
--                membership preconditions.  The manifest's EXCLUDED versus REJECTED split cannot be
--                produced any other way.  DV-53 carries no equivalent exclusion wording.
--   link tier  : SELF_LOOP, CYCLE, MISSING_TARGET, DIFFERENT_AIRCRAFT, OUTSIDE_SELECTED_DAY,
--                BACKWARD_TIME, BROKEN_CONTINUITY, DIVERSION_ENDPOINT_CONFLICT (DV-25 rank 8),
--                then TARGET_NOT_OPERATED  -> REJECTED.
--
-- DIVERSION_ENDPOINT_CONFLICT sits at DV-25 rank 8 under D-0021 R3.  An earlier revision hoisted it
-- into the leg tier because SOURCE_CONTRACT.md:358-359 says the mismatch "terminates continuity",
-- which reads as a property of the leg.  That hoist was not contract-forced, it disagreed with both
-- DV-25 and the independent oracle, and citing DV-25 for every other class while overriding it for
-- this one is incoherent.  No result moves: 8109 clears all seven higher classes, and the raw
-- evidence is never lost because diversion_endpoint_conflict is a standalone Boolean on both
-- AIRCRAFT_FLIGHT and this table.  Rollback if a later fixture proves the conflict must outrank the
-- link classes: move the single WHEN branch back into the leg tier here and align the oracle.
--
-- The conflict branch is evaluated whether or not a target exists, so a diverted leg with a null
-- AF-20 still reports the conflict instead of a silent TERMINAL_NO_TARGET.  Every link-tier branch
-- is therefore guarded on next_flight_id rather than short-circuiting on it.
--
-- Cycle members all carry class CYCLE; all member/link evidence is retained per
-- DEMO_QUESTIONS.md:312 and is_cycle_representative marks the minimum flight_id so a consumer emits
-- exactly one component-level row.  The suppression is presentation-side; nothing is dropped here.
--
-- CYCLE SCOPE AND SELF-LOOPS ARE SETTLED BY D-0022, on one principle: Q08 reconstructs one
-- aircraft's chain for one local date, so a cycle is a property of that chain.
--   * detection is scoped to the selected (AF-02, AF-06).  A link to a different aircraft or a
--     different local date is not a cycle that happens to cross them; it is DIFFERENT_AIRCRAFT
--     (DV-25 rank 4) or OUTSIDE_SELECTED_DAY (rank 5), which is also the diagnosis an operator can
--     act on.  Global detection would let an incidental mutual reference between two aircraft mask
--     the anomaly that matters, and it would do so silently because CYCLE outranks both.
--     Rollback: widen the two join predicates on `edges` below.
--   * a self-loop is NOT a cycle component.  DV-25 ranks SELF_LOOP above CYCLE precisely to keep
--     the two classes disjoint, so counting a self-edge as a length-one component would
--     double-report one defect under two structural headings.  The self-edge is excluded from
--     `edges`, so a self-referencing leg receives no cycle_component_id and is not a
--     representative.  The degenerate case stays queryable through the dedicated
--     is_self_loop_link Boolean rather than through the cycle-component columns.
--     Rollback: drop the `f.next_flight_id <> f.flight_id` predicate on `edges`.
-- Both alignments also match the independent DATA-04b oracle, which is a corroboration rather than
-- the reason: D-0022 decides on the principle above, not on which artifact was written first.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.ROTATION_LINK_VALIDATION
  COMMENT = 'Validated actual rotation self-reference. Grain (AF-01, target_token) where target_token is AF-20 rendered as text or the literal NO_TARGET. Carries DV-24 link status, DV-25 anomaly class, the selected local date basis AF-06 and actual endpoint/time evidence only. Planned values are never used.'
AS
WITH edges AS (
  -- D-0022: the cycle graph is the selected per-aircraft, per-local-date chain, and a self-edge is
  -- SELF_LOOP rather than a length-one cycle.  Both restrictions live here and nowhere else.
  SELECT f.flight_id AS src, f.next_flight_id AS dst
  FROM MODEL_INPUT.AIRCRAFT_FLIGHT f
  JOIN MODEL_INPUT.AIRCRAFT_FLIGHT t ON t.flight_id = f.next_flight_id
  WHERE f.next_flight_id IS NOT NULL
    AND f.next_flight_id <> f.flight_id
    AND t.aircraft_id = f.aircraft_id
    AND t.flight_departure_date = f.flight_departure_date
), reach (src, dst, depth) AS (
  SELECT e.src, e.dst, 1 FROM edges e
  UNION ALL
  SELECT r.src, e.dst, r.depth + 1
  FROM reach r JOIN edges e ON e.src = r.dst
  WHERE r.depth < 32
), cycle_component AS (
  SELECT r1.src AS flight_id, MIN(r1.dst) AS cycle_component_id
  FROM reach r1
  JOIN reach r2 ON r2.src = r1.dst AND r2.dst = r1.src
  WHERE EXISTS (SELECT 1 FROM reach rs WHERE rs.src = r1.src AND rs.dst = r1.src)
  GROUP BY r1.src
), validated AS (
  SELECT
    f.flight_id,
    COALESCE(TO_VARCHAR(f.next_flight_id), 'NO_TARGET')          AS target_token,
    f.next_flight_id,
    f.aircraft_id,
    f.flight_departure_date                                      AS selected_local_date,
    f.actual_gate_departure_time_utc,
    f.actual_gate_arrival_time_utc,
    f.departure_airport_code                                     AS actual_origin_code,
    f.actual_continuity_arrival_code,
    f.diverted_airport_code,
    f.is_cancelled_boolean,
    f.cancellation_flag_status,
    f.is_diverted_boolean,
    f.diversion_flag_status,
    f.diversion_endpoint_conflict,
    t.flight_id                                                  AS target_flight_id,
    t.aircraft_id                                                AS target_aircraft_id,
    t.flight_departure_date                                      AS target_selected_local_date,
    t.actual_gate_departure_time_utc                             AS target_departure_time_utc,
    t.departure_airport_code                                     AS target_origin_code,
    t.is_cancelled_boolean                                       AS target_is_cancelled_boolean,
    t.cancellation_flag_status                                   AS target_cancellation_flag_status,
    cc.cycle_component_id,
    CASE
      -- leg tier: DV-52 / P0-11.3 chain-membership preconditions, contract-forced above the links
      WHEN f.cancellation_flag_status = 'UNKNOWN_OR_INVALID_CANCELLATION_FLAG'
                                                       THEN 'UNKNOWN_OR_INVALID_CANCELLATION_FLAG'
      WHEN f.is_cancelled_boolean                      THEN 'CANCELLED'
      WHEN f.actual_gate_departure_time_utc IS NULL
        OR f.actual_gate_arrival_time_utc IS NULL      THEN 'MISSING_TIME'
      -- link tier, in DV-25 order.  Every branch is guarded on next_flight_id so that a leg with no
      -- target still reaches the DV-25 rank 8 diversion branch below.
      WHEN f.next_flight_id IS NOT NULL
       AND f.next_flight_id = f.flight_id              THEN 'SELF_LOOP'          -- DV-25 rank 1
      WHEN f.next_flight_id IS NOT NULL
       AND cc.cycle_component_id IS NOT NULL           THEN 'CYCLE'              -- DV-25 rank 2
      WHEN f.next_flight_id IS NOT NULL
       AND t.flight_id IS NULL                         THEN 'MISSING_TARGET'     -- DV-25 rank 3
      WHEN f.next_flight_id IS NOT NULL
       AND (f.aircraft_id IS NULL OR t.aircraft_id IS NULL
            OR t.aircraft_id <> f.aircraft_id)         THEN 'DIFFERENT_AIRCRAFT' -- DV-25 rank 4
      WHEN f.next_flight_id IS NOT NULL
       AND NOT EQUAL_NULL(t.flight_departure_date, f.flight_departure_date)
                                                       THEN 'OUTSIDE_SELECTED_DAY'  -- DV-25 rank 5
      WHEN f.next_flight_id IS NOT NULL
       AND (t.actual_gate_departure_time_utc IS NULL
            OR t.actual_gate_departure_time_utc < f.actual_gate_arrival_time_utc)
                                                       THEN 'BACKWARD_TIME'      -- DV-25 rank 6
      WHEN f.next_flight_id IS NOT NULL
       AND (f.actual_continuity_arrival_code IS NULL
            OR t.departure_airport_code IS NULL
            OR t.departure_airport_code <> f.actual_continuity_arrival_code)
                                                       THEN 'BROKEN_CONTINUITY'  -- DV-25 rank 7
      WHEN f.diversion_endpoint_conflict               THEN 'DIVERSION_ENDPOINT_CONFLICT'  -- rank 8
      -- Beyond the DV-25 vocabulary; see D-0020 A5 and the D-0021 R5 cross-reference.
      WHEN f.next_flight_id IS NOT NULL
       AND (t.cancellation_flag_status <> 'NORMALIZED'
            OR t.is_cancelled_boolean
            OR t.actual_gate_arrival_time_utc IS NULL) THEN 'TARGET_NOT_OPERATED'
      ELSE NULL
    END::VARCHAR                                                 AS rotation_anomaly_class
  FROM MODEL_INPUT.AIRCRAFT_FLIGHT f
  LEFT JOIN MODEL_INPUT.AIRCRAFT_FLIGHT t ON t.flight_id = f.next_flight_id
  LEFT JOIN cycle_component cc ON cc.flight_id = f.flight_id
)
SELECT
  v.flight_id,
  v.target_token,
  v.next_flight_id,
  v.aircraft_id,
  v.selected_local_date,
  'AF_06_SOURCE_LOCAL_DEPARTURE_DATE'::VARCHAR                   AS selected_date_basis,
  CASE
    WHEN v.rotation_anomaly_class IN ('UNKNOWN_OR_INVALID_CANCELLATION_FLAG', 'CANCELLED', 'MISSING_TIME')
                                                       THEN 'EXCLUDED'
    WHEN v.rotation_anomaly_class IS NOT NULL          THEN 'REJECTED'
    WHEN v.next_flight_id IS NULL                      THEN 'TERMINAL_NO_TARGET'
    ELSE 'ACCEPTED'
  END::VARCHAR                                                   AS rotation_link_status,
  v.rotation_anomaly_class,
  (v.rotation_anomaly_class IS NULL AND v.next_flight_id IS NOT NULL) AS is_accepted_link,
  v.cycle_component_id,
  (v.cycle_component_id IS NOT NULL AND v.cycle_component_id = v.flight_id)
                                                                 AS is_cycle_representative,
  (v.next_flight_id IS NOT NULL AND v.next_flight_id = v.flight_id)
                                                                 AS is_self_loop_link,
  v.actual_origin_code,
  v.actual_continuity_arrival_code,
  v.diverted_airport_code,
  v.diversion_endpoint_conflict,
  v.actual_gate_departure_time_utc,
  v.actual_gate_arrival_time_utc,
  v.is_cancelled_boolean,
  v.cancellation_flag_status,
  v.is_diverted_boolean,
  v.diversion_flag_status,
  v.target_flight_id,
  v.target_aircraft_id,
  v.target_selected_local_date,
  v.target_departure_time_utc,
  v.target_origin_code,
  v.target_is_cancelled_boolean
FROM validated v;
