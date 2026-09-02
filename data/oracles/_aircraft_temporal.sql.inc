-- ============================================================================
-- DATA-04b independent oracle: shared aircraft temporal CTE block.
--
-- This fragment is textually inlined by run_oracles.py into every aircraft
-- oracle (Q01, Q02, Q03, Q04, Q08). It reads ONLY PK_AVIATION_TEMPORAL.SOURCE.
-- It never reads MODEL_INPUT and never reads any DATA-04a artifact.
--
-- Semantics implemented here (SOURCE_CONTRACT.md + SEMANTIC_DECISIONS.md):
--   * Half-open validity: valid_from <= d < valid_to.
--   * Source sentinel 9999-12-31 is unknown-future and never a finite bound.
--     Model open sentinel is 9999-01-01 and is only ever derived.
--   * Aircraft event canonical order is
--     (start_event_date, row_sequence_number, event_sequence_number,
--      aircraft_history_id). Date alone never identifies a version.
--   * AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT keeps the complete same-day audit
--     sequence; AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT keeps only the final
--     relevant observation for that aircraft/dimension/date. Both suppress
--     only *consecutive* equality, so A -> B -> A stays three assignments.
--   * Four independent dimensions: aircraft_state, aircraft_type, engine_type,
--     aircraft_status. Their clocks are never force-aligned.
--   * AH-13 raw configuration id is provenance, not a watched value; the
--     watched type/engine payloads carry the *resolution outcome* so that
--     resolved -> null/unresolved opens a gap while resolved -> different
--     configuration with an identical resolved dimension does not.
-- ============================================================================
am_eligible AS (
    SELECT
        aircraft_id,
        IFF(aircraft_start_of_life_date = DATE '9999-12-31', NULL, aircraft_start_of_life_date) AS sol_date,
        IFF(aircraft_end_of_life_date   = DATE '9999-12-31', NULL, aircraft_end_of_life_date)   AS eol_date
    FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER
    WHERE aircraft_id IS NOT NULL
      AND COALESCE(not_for_use, TRUE) = FALSE
),
ah_eligible AS (
    SELECT h.*
    FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_HISTORY h
    WHERE h.aircraft_history_id IS NOT NULL
      AND h.aircraft_id         IS NOT NULL
      AND h.start_event_date    IS NOT NULL
      AND h.row_sequence_number IS NOT NULL
      AND COALESCE(h.not_for_use, TRUE) = FALSE
      AND h.start_event_date <> DATE '9999-12-31'
),
ah_first_event AS (
    SELECT aircraft_id, MIN(start_event_date) AS first_event_date
    FROM ah_eligible
    GROUP BY aircraft_id
),
aircraft_existence AS (
    -- existence_from = normalised AM-07, falling back to the first eligible AH-05.
    -- existence_to   = normalised AM-08 (exclusive, D-0003) or the model open sentinel.
    SELECT
        m.aircraft_id,
        COALESCE(m.sol_date, f.first_event_date)   AS existence_from,
        COALESCE(m.eol_date, DATE '9999-01-01')    AS existence_to
    FROM am_eligible m
    LEFT JOIN ah_first_event f ON f.aircraft_id = m.aircraft_id
),
ah_resolved AS (
    SELECT
        h.*,
        c.aircraft_subseries        AS type_definition_id,
        c.aircraft_type             AS type_definition_label,
        c.engine_subseries          AS engine_definition_id,
        c.engine_type               AS engine_definition_label,
        c.engine_count              AS cfg_engine_count,
        c.has_multiple_engine_types AS cfg_has_multiple_engine_types,
        IFF(c.aircraft_subseries IS NOT NULL, 'EXACT', 'UNRESOLVED') AS type_resolution_status,
        IFF(c.engine_subseries   IS NOT NULL, 'EXACT', 'UNRESOLVED') AS engine_resolution_status,
        c.aircraft_family, c.aircraft_series, c.aircraft_manufacturer, c.aircraft_design_class,
        c.engine_manufacturer, c.engine_family, c.engine_series, c.engine_propulsion_type
    FROM ah_eligible h
    LEFT JOIN PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_CONFIGURATION c
           ON c.aircraft_configuration_id = h.aircraft_configuration_id
),
dim_observation AS (
    -- One row per (dimension, source event). watched_signature is a lossless,
    -- null-safe JSON encoding of exactly the contracted watched set.
    SELECT 'aircraft_state' AS dimension, r.aircraft_id, r.aircraft_history_id,
           r.start_event_date, r.row_sequence_number, r.event_sequence_number,
           TO_JSON(ARRAY_CONSTRUCT(
               r.aircraft_registration_number, r.aircraft_transponder_code,
               r.aircraft_registration_country_code_iso, r.aircraft_registration_region,
               r.aircraft_cargo, r.storage_location, r.storage_airport_code_iata,
               r.base_airport, r.base_airport_code_iata, r.base_city, r.base_country,
               r.apu_type, r.aircraft_width_m,
               r.operating_maximum_takeoff_weight_lb, r.certified_maximum_takeoff_weight_lb)) AS watched_signature,
           NULL::VARCHAR AS definition_id, NULL::VARCHAR AS definition_label,
           NULL::NUMBER(38,0) AS engine_count, NULL::BOOLEAN AS mixed_engine_set_complete,
           (r.aircraft_registration_number IS NOT NULL
            OR r.base_airport_code_iata IS NOT NULL
            OR r.aircraft_transponder_code IS NOT NULL) AS is_resolved,
           r.aircraft_registration_number AS registration_number,
           r.base_airport_code_iata       AS base_airport_code_iata,
           NULL::VARCHAR                  AS lifecycle_status
    FROM ah_resolved r
    UNION ALL
    SELECT 'aircraft_type', r.aircraft_id, r.aircraft_history_id,
           r.start_event_date, r.row_sequence_number, r.event_sequence_number,
           TO_JSON(ARRAY_CONSTRUCT(
               r.aircraft_code_iata, r.aircraft_code_icao, r.aircraft_value_sub_series,
               r.aircraft_family, r.type_definition_label, r.aircraft_series,
               r.type_definition_id, r.aircraft_manufacturer, r.aircraft_design_class,
               r.type_resolution_status)),
           r.type_definition_id, r.type_definition_label,
           NULL::NUMBER(38,0), NULL::BOOLEAN,
           (r.type_resolution_status = 'EXACT'),
           NULL::VARCHAR, NULL::VARCHAR, NULL::VARCHAR
    FROM ah_resolved r
    UNION ALL
    SELECT 'engine_type', r.aircraft_id, r.aircraft_history_id,
           r.start_event_date, r.row_sequence_number, r.event_sequence_number,
           TO_JSON(ARRAY_CONSTRUCT(
               r.cfg_engine_count, r.cfg_has_multiple_engine_types,
               r.engine_manufacturer, r.engine_family, r.engine_definition_label,
               r.engine_series, r.engine_definition_id, r.engine_propulsion_type,
               r.engine_resolution_status)),
           r.engine_definition_id, r.engine_definition_label,
           r.cfg_engine_count,
           -- D-0012/HT-40: one reported engine definition plus count; the complete
           -- mixed set is unsupported, so completeness is NOT has_multiple_engine_types.
           IFF(r.engine_resolution_status = 'EXACT', NOT COALESCE(r.cfg_has_multiple_engine_types, FALSE), NULL),
           (r.engine_resolution_status = 'EXACT'),
           NULL::VARCHAR, NULL::VARCHAR, NULL::VARCHAR
    FROM ah_resolved r
    UNION ALL
    SELECT 'aircraft_status', r.aircraft_id, r.aircraft_history_id,
           r.start_event_date, r.row_sequence_number, r.event_sequence_number,
           TO_JSON(ARRAY_CONSTRUCT(r.start_aircraft_status)),
           NULL::VARCHAR, NULL::VARCHAR, NULL::NUMBER(38,0), NULL::BOOLEAN,
           (r.start_aircraft_status IS NOT NULL),
           NULL::VARCHAR, NULL::VARCHAR, r.start_aircraft_status
    FROM ah_resolved r
),
audit_ordered AS (
    -- AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT: complete same-day audit sequence,
    -- consecutive equality suppressed, no interval assigned.
    SELECT d.*,
           LAG(d.watched_signature) OVER (
               PARTITION BY d.dimension, d.aircraft_id
               ORDER BY d.start_event_date, d.row_sequence_number,
                        d.event_sequence_number, d.aircraft_history_id) AS prev_audit_signature
    FROM dim_observation d
),
audit_assignment AS (
    SELECT * FROM audit_ordered
    WHERE prev_audit_signature IS NULL OR prev_audit_signature <> watched_signature
),
daily_final AS (
    -- Final relevant observation for aircraft/dimension/date.
    SELECT * EXCLUDE rn FROM (
        SELECT d.*,
               ROW_NUMBER() OVER (
                   PARTITION BY d.dimension, d.aircraft_id, d.start_event_date
                   ORDER BY d.row_sequence_number DESC, d.event_sequence_number DESC NULLS LAST,
                            d.aircraft_history_id DESC) AS rn
        FROM dim_observation d
    ) WHERE rn = 1
),
daily_kept AS (
    SELECT * EXCLUDE prev_signature FROM (
        SELECT f.*,
               LAG(f.watched_signature) OVER (
                   PARTITION BY f.dimension, f.aircraft_id ORDER BY f.start_event_date) AS prev_signature
        FROM daily_final f
    ) WHERE prev_signature IS NULL OR prev_signature <> watched_signature
),
daily_assignment AS (
    -- AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT with half-open validity clipped to existence.
    SELECT
        k.dimension, k.aircraft_id, k.aircraft_history_id, k.start_event_date,
        k.row_sequence_number, k.event_sequence_number,
        k.definition_id, k.definition_label, k.engine_count, k.mixed_engine_set_complete,
        k.is_resolved, k.registration_number, k.base_airport_code_iata, k.lifecycle_status,
        e.existence_from, e.existence_to,
        k.start_event_date AS valid_from,
        LEAST(
            COALESCE(
                LEAD(k.start_event_date) OVER (PARTITION BY k.dimension, k.aircraft_id ORDER BY k.start_event_date),
                e.existence_to),
            e.existence_to) AS valid_to,
        k.dimension || '|' || k.aircraft_id::VARCHAR || '|'
            || TO_VARCHAR(k.start_event_date, 'YYYY-MM-DD') || '|'
            || k.aircraft_history_id::VARCHAR AS assignment_id
    FROM daily_kept k
    JOIN aircraft_existence e ON e.aircraft_id = k.aircraft_id
    WHERE k.start_event_date < e.existence_to
)
