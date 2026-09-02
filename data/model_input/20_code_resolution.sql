-- DATA-04a: closed code-resolution method map (SOURCE_CONTRACT.md).
--
-- Resolution is source-preserving exact string equality.  No case folding, punctuation stripping,
-- fuzzy or name matching.  Null / empty raw input is INVALID_INPUT.  Candidate counts are distinct
-- AP-01 / AL-01 identities.  is_active / is_current never select a winner.  A concept link exists
-- only for EXACT cardinality one.
--
-- CODE_RESOLUTION_CODE / CODE_RESOLUTION_CODE_CANDIDATE are declared code-level derivations: they
-- hold the method map once per distinct raw code so the row-scoped contract tables and the
-- Route / AircraftFlight / fulfillment endpoint joins all read the same closed map.

CREATE OR REPLACE TABLE MODEL_INPUT.CODE_RESOLUTION_CODE_CANDIDATE
  COMMENT = 'Code-level candidate map: every distinct reference identity a raw code matches under its contracted method, with the matched code systems retained and no precedence assigned among them.'
AS
WITH airport_iata AS (
  SELECT 'AIRPORT'::VARCHAR AS domain, 'AIRPORT_IATA_EXACT'::VARCHAR AS method,
         r.airport_code_iata AS raw_code, r.airport_id AS candidate_id, 'AP-04'::VARCHAR AS matched_code_system
  FROM SOURCE.AIRPORT_REFERENCE r
  WHERE r.airport_code_iata IS NOT NULL AND r.airport_id IS NOT NULL
), airport_internal AS (
  SELECT 'AIRPORT'::VARCHAR, 'AIRPORT_INTERNAL_ID_EXACT'::VARCHAR,
         r.airport_id, r.airport_id, 'AP-01'::VARCHAR
  FROM SOURCE.AIRPORT_REFERENCE r
  WHERE r.airport_id IS NOT NULL
), airline_alias AS (
  SELECT 'AIRLINE'::VARCHAR, 'AIRLINE_ALIAS_UNION_EXACT'::VARCHAR, r.airline_id, r.airline_id, 'AL-01'::VARCHAR
  FROM SOURCE.AIRLINE_REFERENCE r WHERE r.airline_id IS NOT NULL
  UNION ALL
  SELECT 'AIRLINE', 'AIRLINE_ALIAS_UNION_EXACT', r.carrier_code_iata, r.airline_id, 'AL-04'
  FROM SOURCE.AIRLINE_REFERENCE r WHERE r.carrier_code_iata IS NOT NULL AND r.airline_id IS NOT NULL
  UNION ALL
  SELECT 'AIRLINE', 'AIRLINE_ALIAS_UNION_EXACT', r.carrier_code_icao, r.airline_id, 'AL-05'
  FROM SOURCE.AIRLINE_REFERENCE r WHERE r.carrier_code_icao IS NOT NULL AND r.airline_id IS NOT NULL
), airline_internal AS (
  SELECT 'AIRLINE'::VARCHAR, 'AIRLINE_INTERNAL_ID_EXACT'::VARCHAR, r.airline_id, r.airline_id, 'AL-01'::VARCHAR
  FROM SOURCE.AIRLINE_REFERENCE r WHERE r.airline_id IS NOT NULL
), all_candidates AS (
  SELECT * FROM airport_iata
  UNION ALL SELECT * FROM airport_internal
  UNION ALL SELECT * FROM airline_alias
  UNION ALL SELECT * FROM airline_internal
)
SELECT
  domain, method, raw_code, candidate_id,
  LISTAGG(DISTINCT matched_code_system, ',') WITHIN GROUP (ORDER BY matched_code_system) AS matched_code_systems
FROM all_candidates
GROUP BY domain, method, raw_code, candidate_id;

CREATE OR REPLACE TABLE MODEL_INPUT.CODE_RESOLUTION_CODE
  COMMENT = 'Code-level resolution outcome per (domain, method, raw code): DV-11 candidate count and DV-10 status. single_candidate_id is non-null only for EXACT cardinality one.'
AS
SELECT
  domain, method, raw_code,
  COUNT(DISTINCT candidate_id)                                        AS candidate_count,
  IFF(COUNT(DISTINCT candidate_id) = 1, MIN(candidate_id), NULL)      AS single_candidate_id,
  IFF(COUNT(DISTINCT candidate_id) = 1, 'EXACT', 'AMBIGUOUS')::VARCHAR AS resolution_status,
  LISTAGG(DISTINCT matched_code_systems, ';') WITHIN GROUP (ORDER BY matched_code_systems) AS matched_code_systems
FROM MODEL_INPUT.CODE_RESOLUTION_CODE_CANDIDATE
GROUP BY domain, method, raw_code;

-- ---------------------------------------------------------------------------------------------
-- Row-scoped resolution inputs.  A source row without its contracted stable identity has no DV-46
-- source row token and therefore produces no resolution result; it is quarantined elsewhere.
-- ---------------------------------------------------------------------------------------------

-- A semantic source duplicate (NF-S01: two raw schedule rows byte-identical through SS-39, hence
-- sharing SS-40) yields the same DV-46 source row token and therefore the same resolution_id.
-- That is correct: the resolution result is a property of the row identity, not of how many times
-- the identical row arrived.  The duplicate is collapsed here and its multiplicity is retained as
-- source_occurrence_count so the resolution grain stays unique.
CREATE OR REPLACE TABLE MODEL_INPUT.CODE_RESOLUTION_INPUT
  COMMENT = 'Declared derivation: every row-scoped raw code that the closed method map resolves, with its DV-46 source row token, field role, domain and method. Semantic source duplicates sharing one DV-46 token collapse to one input row and retain an occurrence count.'
AS
SELECT
  domain, source_object, source_row_token, field_role, raw_field_id, raw_code, method,
  COUNT(*) AS source_occurrence_count
FROM (
  -- AIRCRAFT_MASTER
  SELECT 'AIRPORT'::VARCHAR AS domain, 'AIRCRAFT_MASTER'::VARCHAR AS source_object,
         'AIRCRAFT_MASTER|' || TO_VARCHAR(m.aircraft_id) AS source_row_token,
         'build_airport'::VARCHAR AS field_role, 'AM-09'::VARCHAR AS raw_field_id,
         m.aircraft_build_airport_code_iata AS raw_code, 'AIRPORT_IATA_EXACT'::VARCHAR AS method
  FROM SOURCE.AIRCRAFT_MASTER m WHERE m.aircraft_id IS NOT NULL
  UNION ALL
  -- AIRCRAFT_HISTORY
  SELECT 'AIRPORT', 'AIRCRAFT_HISTORY', 'AIRCRAFT_HISTORY|' || TO_VARCHAR(h.aircraft_history_id),
         'storage_airport', 'AH-23', h.storage_airport_code_iata, 'AIRPORT_IATA_EXACT'
  FROM SOURCE.AIRCRAFT_HISTORY h WHERE h.aircraft_history_id IS NOT NULL
  UNION ALL
  SELECT 'AIRPORT', 'AIRCRAFT_HISTORY', 'AIRCRAFT_HISTORY|' || TO_VARCHAR(h.aircraft_history_id),
         'base_airport', 'AH-25', h.base_airport_code_iata, 'AIRPORT_IATA_EXACT'
  FROM SOURCE.AIRCRAFT_HISTORY h WHERE h.aircraft_history_id IS NOT NULL
  UNION ALL
  -- SCHEDULE_SNAPSHOT
  SELECT 'AIRPORT', 'SCHEDULE_SNAPSHOT',
         'SCHEDULE_SNAPSHOT|' || s.schedule_key || '|' || MODEL_INPUT.CANON_DATE(s.publish_date) || '|' || s.normalized_row_hash,
         'route_origin', 'SS-10', s.departure_station_code_iata, 'AIRPORT_IATA_EXACT'
  FROM SOURCE.SCHEDULE_SNAPSHOT s WHERE s.schedule_key IS NOT NULL AND s.publish_date IS NOT NULL
  UNION ALL
  SELECT 'AIRPORT', 'SCHEDULE_SNAPSHOT',
         'SCHEDULE_SNAPSHOT|' || s.schedule_key || '|' || MODEL_INPUT.CANON_DATE(s.publish_date) || '|' || s.normalized_row_hash,
         'route_destination', 'SS-11', s.arrival_station_code_iata, 'AIRPORT_IATA_EXACT'
  FROM SOURCE.SCHEDULE_SNAPSHOT s WHERE s.schedule_key IS NOT NULL AND s.publish_date IS NOT NULL
  UNION ALL
  SELECT 'AIRLINE', 'SCHEDULE_SNAPSHOT',
         'SCHEDULE_SNAPSHOT|' || s.schedule_key || '|' || MODEL_INPUT.CANON_DATE(s.publish_date) || '|' || s.normalized_row_hash,
         'marketing_carrier', 'SS-04', s.marketing_carrier_internal, 'AIRLINE_ALIAS_UNION_EXACT'
  FROM SOURCE.SCHEDULE_SNAPSHOT s WHERE s.schedule_key IS NOT NULL AND s.publish_date IS NOT NULL
  UNION ALL
  SELECT 'AIRLINE', 'SCHEDULE_SNAPSHOT',
         'SCHEDULE_SNAPSHOT|' || s.schedule_key || '|' || MODEL_INPUT.CANON_DATE(s.publish_date) || '|' || s.normalized_row_hash,
         'operating_carrier', 'SS-05', s.operating_carrier_internal, 'AIRLINE_ALIAS_UNION_EXACT'
  FROM SOURCE.SCHEDULE_SNAPSHOT s WHERE s.schedule_key IS NOT NULL AND s.publish_date IS NOT NULL
  UNION ALL
  SELECT 'AIRLINE', 'SCHEDULE_SNAPSHOT',
         'SCHEDULE_SNAPSHOT|' || s.schedule_key || '|' || MODEL_INPUT.CANON_DATE(s.publish_date) || '|' || s.normalized_row_hash,
         'codeshare_carrier', 'SS-36', s.codeshare_carrier_internal, 'AIRLINE_ALIAS_UNION_EXACT'
  FROM SOURCE.SCHEDULE_SNAPSHOT s WHERE s.schedule_key IS NOT NULL AND s.publish_date IS NOT NULL
  UNION ALL
  -- PASSENGER_FORWARD / PASSENGER_HISTORICAL through the typed source observation
  SELECT 'AIRPORT', p.source_system, p.source_row_token, 'planned_origin',
         IFF(p.source_system = 'FORWARD', 'PF-08', 'PH-10'), p.key_departure_station_code_iata, 'AIRPORT_IATA_EXACT'
  FROM MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION p
  UNION ALL
  SELECT 'AIRPORT', p.source_system, p.source_row_token, 'planned_destination',
         IFF(p.source_system = 'FORWARD', 'PF-09', 'PH-11'), p.key_arrival_station_code_iata, 'AIRPORT_IATA_EXACT'
  FROM MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION p
  UNION ALL
  SELECT 'AIRLINE', p.source_system, p.source_row_token, 'marketing_carrier',
         IFF(p.source_system = 'FORWARD', 'PF-02', 'PH-05'), p.key_marketing_carrier_internal, 'AIRLINE_ALIAS_UNION_EXACT'
  FROM MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION p
  UNION ALL
  SELECT 'AIRLINE', p.source_system, p.source_row_token, 'operating_carrier',
         IFF(p.source_system = 'FORWARD', 'PF-03', 'PH-06'), p.operating_carrier_internal, 'AIRLINE_ALIAS_UNION_EXACT'
  FROM MODEL_INPUT.PASSENGER_SOURCE_OBSERVATION p
  UNION ALL
  -- AIRCRAFT_FLIGHT
  SELECT 'AIRPORT', 'AIRCRAFT_FLIGHT', 'AIRCRAFT_FLIGHT|' || TO_VARCHAR(a.flight_id),
         'actual_origin', 'AF-08', a.departure_airport_code, 'AIRPORT_INTERNAL_ID_EXACT'
  FROM SOURCE.AIRCRAFT_FLIGHT a WHERE a.flight_id IS NOT NULL
  UNION ALL
  SELECT 'AIRPORT', 'AIRCRAFT_FLIGHT', 'AIRCRAFT_FLIGHT|' || TO_VARCHAR(a.flight_id),
         'actual_destination', 'AF-09', a.arrival_airport_code, 'AIRPORT_INTERNAL_ID_EXACT'
  FROM SOURCE.AIRCRAFT_FLIGHT a WHERE a.flight_id IS NOT NULL
  UNION ALL
  SELECT 'AIRPORT', 'AIRCRAFT_FLIGHT', 'AIRCRAFT_FLIGHT|' || TO_VARCHAR(a.flight_id),
         'diversion_airport', 'AF-10', a.diverted_airport_code, 'AIRPORT_INTERNAL_ID_EXACT'
  FROM SOURCE.AIRCRAFT_FLIGHT a WHERE a.flight_id IS NOT NULL
  UNION ALL
  SELECT 'AIRLINE', 'AIRCRAFT_FLIGHT', 'AIRCRAFT_FLIGHT|' || TO_VARCHAR(a.flight_id),
         'actual_operating_carrier', 'AF-03', a.operating_carrier_code, 'AIRLINE_INTERNAL_ID_EXACT'
  FROM SOURCE.AIRCRAFT_FLIGHT a WHERE a.flight_id IS NOT NULL
  UNION ALL
  SELECT 'AIRLINE', 'AIRCRAFT_FLIGHT', 'AIRCRAFT_FLIGHT|' || TO_VARCHAR(a.flight_id),
         'actual_marketing_carrier', 'AF-04', a.marketing_carrier_code, 'AIRLINE_INTERNAL_ID_EXACT'
  FROM SOURCE.AIRCRAFT_FLIGHT a WHERE a.flight_id IS NOT NULL
)
GROUP BY domain, source_object, source_row_token, field_role, raw_field_id, raw_code, method;

CREATE OR REPLACE TABLE MODEL_INPUT.CODE_RESOLUTION
  COMMENT = 'Row-scoped stable code-resolution result. Grain resolution_id = SHA-256 over domain, source object, DV-46 source row token, field role, raw code and method. The result exists at zero candidates and for valid PF/PH rows with a null stable source row ID. DV-10 resolution_status is EXACT|AMBIGUOUS|UNRESOLVED|INVALID_INPUT; only EXACT with DV-11 candidate_count = 1 may create a concept link.'
AS
SELECT
  SHA2(
    MODEL_INPUT.LP(i.domain) || MODEL_INPUT.LP(i.source_object)
    || MODEL_INPUT.LP(i.source_row_token) || MODEL_INPUT.LP(i.field_role)
    || MODEL_INPUT.NULL_SAFE_TOKEN(i.raw_code) || MODEL_INPUT.LP(i.method)
  , 256)                                                       AS resolution_id,
  i.domain,
  i.source_object,
  i.source_row_token,
  i.field_role,
  i.raw_field_id,
  i.raw_code,
  i.method,
  i.source_occurrence_count,
  CASE
    WHEN i.raw_code IS NULL OR i.raw_code = '' THEN 0
    ELSE COALESCE(c.candidate_count, 0)
  END                                                          AS candidate_count,
  CASE
    WHEN i.raw_code IS NULL OR i.raw_code = ''   THEN 'INVALID_INPUT'
    WHEN COALESCE(c.candidate_count, 0) = 0      THEN 'UNRESOLVED'
    WHEN c.candidate_count = 1                   THEN 'EXACT'
    ELSE 'AMBIGUOUS'
  END::VARCHAR                                                 AS resolution_status,
  CASE
    WHEN i.raw_code IS NULL OR i.raw_code = '' THEN NULL
    WHEN c.candidate_count = 1 THEN c.single_candidate_id
  END                                                          AS resolved_identity_id,
  CASE WHEN i.raw_code IS NULL OR i.raw_code = '' THEN NULL ELSE c.matched_code_systems END
                                                               AS matched_code_systems
FROM MODEL_INPUT.CODE_RESOLUTION_INPUT i
LEFT JOIN MODEL_INPUT.CODE_RESOLUTION_CODE c
  ON c.method = i.method AND c.raw_code = i.raw_code;

CREATE OR REPLACE TABLE MODEL_INPUT.CODE_RESOLUTION_CANDIDATE
  COMMENT = 'Zero, one or many reference identities associated with a stable CODE_RESOLUTION result. Grain (resolution_id, candidate_id). A nullable candidate is never used as identity, so zero-candidate resolutions contribute no rows.'
AS
SELECT
  r.resolution_id,
  cc.candidate_id,
  r.domain,
  r.method,
  r.raw_code,
  cc.matched_code_systems,
  r.candidate_count,
  r.resolution_status
FROM MODEL_INPUT.CODE_RESOLUTION r
JOIN MODEL_INPUT.CODE_RESOLUTION_CODE_CANDIDATE cc
  ON cc.method = r.method AND cc.raw_code = r.raw_code
WHERE r.raw_code IS NOT NULL AND r.raw_code <> '';
