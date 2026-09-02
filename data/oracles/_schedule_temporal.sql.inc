-- ============================================================================
-- DATA-04b independent oracle: shared schedule temporal CTE block.
--
-- Inlined by run_oracles.py into Q05, Q06 and Q07. Reads ONLY
-- PK_AVIATION_TEMPORAL.SOURCE; never MODEL_INPUT and never any DATA-04a file.
--
-- Semantics implemented here:
--   * Eligibility is exactly SC-02 is_present AND SC-03 is_complete. A missing
--     or incomplete snapshot can never open/close a segment or manufacture an
--     addition, removal, entry or exit (HT-12/HT-13).
--   * Canonical grain is at most one row per (SS-01, SS-03), selected by
--     weekly frequency DESC, total seats DESC, itinerary variation ASC then
--     normalized row hash ASC, business nulls last (NF-S01 V01/V02/DUP).
--   * The watched content set is exactly SS-04..SS-38. SS-02/SS-39/SS-40 are
--     lineage/de-duplication only and cannot alter an event.
--   * Knowledge versioning is partitioned by SS-01, never by route, so one
--     route may carry many concurrently open RouteStates.
--   * Half-open knowledge validity: valid_from <= knowledge_date < valid_to;
--     the derived open bound is model sentinel 9999-01-01.
--   * A route is directional and carrier-agnostic, identity
--     departure_station_code_iata || '->' || arrival_station_code_iata; a null
--     component is INVALID_ROUTE_KEY -- the observation still counts for exact
--     schedule-key presence/content, but yields no Route, RouteState, market
--     or capacity result.
-- ============================================================================
snapshot_calendar AS (
    SELECT expected_publish_date AS pd,
           COALESCE(is_present, FALSE)  AS is_present,
           COALESCE(is_complete, FALSE) AS is_complete,
           (COALESCE(is_present, FALSE) AND COALESCE(is_complete, FALSE)) AS is_eligible
    FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR
),
eligible_dates AS (
    SELECT pd FROM snapshot_calendar WHERE is_eligible
),
canonical_ranked AS (
    SELECT s.*,
           ROW_NUMBER() OVER (
               PARTITION BY s.schedule_key, s.publish_date
               ORDER BY s.weekly_frequency DESC NULLS LAST,
                        s.total_seats DESC NULLS LAST,
                        s.itinerary_variation_identifier ASC NULLS LAST,
                        s.normalized_row_hash ASC NULLS LAST) AS canonical_rank
    FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT s
    JOIN eligible_dates e ON e.pd = s.publish_date
    WHERE s.schedule_key IS NOT NULL
      AND s.publish_date IS NOT NULL
),
schedule_observation AS (
    SELECT
        schedule_key,
        publish_date,
        marketing_carrier_internal,
        operating_carrier_internal,
        flight_number,
        effective_date,
        discontinue_date,
        departure_station_code_iata,
        arrival_station_code_iata,
        is_operating_monday, is_operating_tuesday, is_operating_wednesday,
        is_operating_thursday, is_operating_friday, is_operating_saturday,
        is_operating_sunday,
        weekly_frequency,
        total_seats, first_class_seats, business_class_seats,
        premium_economy_seats, economy_class_seats,
        is_codeshare, codeshare_carrier_internal,
        normalized_row_hash,
        (departure_station_code_iata IS NOT NULL AND arrival_station_code_iata IS NOT NULL) AS route_valid,
        IFF(departure_station_code_iata IS NOT NULL AND arrival_station_code_iata IS NOT NULL,
            departure_station_code_iata || '->' || arrival_station_code_iata, NULL) AS route_id,
        -- SS-04..SS-38 watched set, canonicalised to typed strings, nulls kept.
        OBJECT_CONSTRUCT_KEEP_NULL(
            'marketing_carrier_internal',            marketing_carrier_internal,
            'operating_carrier_internal',            operating_carrier_internal,
            'flight_number',                         TO_VARCHAR(flight_number),
            'service_type_iata',                     service_type_iata,
            'effective_date',                        TO_VARCHAR(effective_date, 'YYYY-MM-DD'),
            'discontinue_date',                      TO_VARCHAR(discontinue_date, 'YYYY-MM-DD'),
            'departure_station_code_iata',           departure_station_code_iata,
            'arrival_station_code_iata',             arrival_station_code_iata,
            'departure_terminal',                    departure_terminal,
            'arrival_terminal',                      arrival_terminal,
            'is_operating_monday',                   LOWER(TO_VARCHAR(is_operating_monday)),
            'is_operating_tuesday',                  LOWER(TO_VARCHAR(is_operating_tuesday)),
            'is_operating_wednesday',                LOWER(TO_VARCHAR(is_operating_wednesday)),
            'is_operating_thursday',                 LOWER(TO_VARCHAR(is_operating_thursday)),
            'is_operating_friday',                   LOWER(TO_VARCHAR(is_operating_friday)),
            'is_operating_saturday',                 LOWER(TO_VARCHAR(is_operating_saturday)),
            'is_operating_sunday',                   LOWER(TO_VARCHAR(is_operating_sunday)),
            'days_pattern',                          days_pattern,
            'weekly_frequency',                      TO_VARCHAR(weekly_frequency),
            'passenger_departure_utc_time',          TO_VARCHAR(passenger_departure_utc_time, 'HH24:MI:SS'),
            'passenger_arrival_utc_time',            TO_VARCHAR(passenger_arrival_utc_time, 'HH24:MI:SS'),
            'passenger_departure_local_time',        TO_VARCHAR(passenger_departure_local_time, 'HH24:MI:SS'),
            'passenger_arrival_local_time',          TO_VARCHAR(passenger_arrival_local_time, 'HH24:MI:SS'),
            'arrival_day_indicator',                 TO_VARCHAR(arrival_day_indicator),
            'scheduled_block_minutes',               TO_VARCHAR(scheduled_block_minutes),
            'equipment_subtype_code_iata',           equipment_subtype_code_iata,
            'total_seats',                           TO_VARCHAR(total_seats),
            'first_class_seats',                     TO_VARCHAR(first_class_seats),
            'business_class_seats',                  TO_VARCHAR(business_class_seats),
            'premium_economy_seats',                 TO_VARCHAR(premium_economy_seats),
            'economy_class_seats',                   TO_VARCHAR(economy_class_seats),
            'is_codeshare',                          LOWER(TO_VARCHAR(is_codeshare)),
            'codeshare_carrier_internal',            codeshare_carrier_internal,
            'number_of_intermediate_stops',          TO_VARCHAR(number_of_intermediate_stops),
            'intermediate_stop_station_codes_iata',  intermediate_stop_station_codes_iata
        ) AS watched
    FROM canonical_ranked
    WHERE canonical_rank = 1
),
observation_signed AS (
    SELECT o.*, TO_JSON(o.watched) AS watched_signature FROM schedule_observation o
),
all_schedule_keys AS (
    SELECT DISTINCT schedule_key FROM observation_signed
),
presence_grid AS (
    -- One row per (schedule_key, eligible snapshot date), present or not.
    SELECT
        k.schedule_key,
        e.pd,
        (o.schedule_key IS NOT NULL) AS is_present_at_date,
        o.watched, o.watched_signature,
        o.marketing_carrier_internal, o.operating_carrier_internal, o.flight_number,
        o.effective_date, o.discontinue_date,
        o.departure_station_code_iata, o.arrival_station_code_iata,
        o.route_valid, o.route_id,
        o.is_operating_monday, o.is_operating_tuesday, o.is_operating_wednesday,
        o.is_operating_thursday, o.is_operating_friday, o.is_operating_saturday,
        o.is_operating_sunday,
        o.weekly_frequency, o.total_seats, o.first_class_seats, o.business_class_seats,
        o.premium_economy_seats, o.economy_class_seats, o.is_codeshare, o.codeshare_carrier_internal
    FROM all_schedule_keys k
    CROSS JOIN eligible_dates e
    LEFT JOIN observation_signed o
           ON o.schedule_key = k.schedule_key AND o.publish_date = e.pd
),
presence_marked AS (
    SELECT
        g.*,
        LAG(g.pd)                 OVER (PARTITION BY g.schedule_key ORDER BY g.pd) AS prev_eligible_pd,
        LAG(g.is_present_at_date) OVER (PARTITION BY g.schedule_key ORDER BY g.pd) AS prev_is_present,
        LAG(g.watched_signature)  OVER (PARTITION BY g.schedule_key ORDER BY g.pd) AS prev_watched_signature
    FROM presence_grid g
),
presence_boundary AS (
    SELECT
        m.*,
        (m.is_present_at_date
         AND (COALESCE(m.prev_is_present, FALSE) = FALSE
              OR m.prev_watched_signature IS DISTINCT FROM m.watched_signature)) AS opens_segment,
        (m.is_present_at_date = FALSE AND COALESCE(m.prev_is_present, FALSE))    AS closes_segment
    FROM presence_marked m
),
route_state AS (
    -- Knowledge-time segments, half-open, partitioned by schedule identity.
    SELECT
        schedule_key,
        schedule_key || '|' || TO_VARCHAR(pd, 'YYYY-MM-DD') AS route_state_key,
        pd AS knowledge_valid_from,
        COALESCE(
            LEAD(pd) OVER (PARTITION BY schedule_key ORDER BY pd),
            DATE '9999-01-01') AS knowledge_valid_to,
        marketing_carrier_internal, operating_carrier_internal, flight_number,
        effective_date, discontinue_date,
        departure_station_code_iata, arrival_station_code_iata, route_valid, route_id,
        is_operating_monday, is_operating_tuesday, is_operating_wednesday,
        is_operating_thursday, is_operating_friday, is_operating_saturday, is_operating_sunday,
        weekly_frequency, total_seats, first_class_seats, business_class_seats,
        premium_economy_seats, economy_class_seats, is_codeshare, codeshare_carrier_internal
    FROM presence_boundary
    WHERE opens_segment OR closes_segment
    QUALIFY opens_segment
)
