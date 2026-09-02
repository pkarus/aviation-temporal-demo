-- ============================================================================
-- TT-PLAN-ACTUAL-DIVERSION (HT-33) -- independent oracle over SOURCE.
--
-- A valid diversion: AF-12 is set and non-null AF-10 reconciles to AF-09.
-- Planned endpoints (PH-10/PH-11, public IATA labels) and actual endpoints
-- (AF-08/AF-09, SYN-AP-* internal IDs) are both preserved; the actual never
-- overwrites the plan and the plan never repairs the actual.
-- ============================================================================
SELECT
    p.passenger_token,
    f.flight_id::NUMBER(38,0)     AS actual_flight_id,
    h.departure_station_code_iata AS planned_origin_iata,
    h.arrival_station_code_iata   AS planned_destination_iata,
    f.departure_airport_code      AS actual_origin_internal,
    f.arrival_airport_code        AS actual_destination_internal,
    f.diverted_airport_code       AS diverted_airport_internal,
    CASE
        WHEN f.is_diverted = 1 AND f.diverted_airport_code = f.arrival_airport_code
             AND (h.departure_station_code_iata <> REPLACE(f.departure_airport_code, 'SYN-AP-', '')
                  OR h.arrival_station_code_iata <> REPLACE(f.arrival_airport_code, 'SYN-AP-', ''))
             THEN 'VALID_DIVERSION_PLAN_ACTUAL_DIFFER'
        WHEN f.is_diverted = 1 AND f.diverted_airport_code IS NOT NULL
             AND f.diverted_airport_code <> f.arrival_airport_code
             THEN 'DIVERSION_ENDPOINT_CONFLICT'
        ELSE 'NO_DIVERSION'
    END AS reconciliation_status,
    (h.departure_station_code_iata IS NOT NULL AND h.arrival_station_code_iata IS NOT NULL) AS planned_values_preserved,
    (f.departure_airport_code IS NOT NULL AND f.arrival_airport_code IS NOT NULL)           AS actual_values_preserved
FROM PK_AVIATION_TEMPORAL.SOURCE.PASSENGER_HISTORICAL h
JOIN PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_FLIGHT f
  ON f.flight_id = h.historical_source_row_id
JOIN (SELECT 7200 AS pid, 'SYN-PAX-DIVERSION-01' AS passenger_token) p
  ON p.pid = h.historical_source_row_id
ORDER BY actual_flight_id
