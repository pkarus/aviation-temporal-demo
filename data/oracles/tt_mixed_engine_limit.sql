-- ============================================================================
-- TT-MIXED-ENGINE-LIMIT (HT-40) -- independent oracle over SOURCE.
--
-- The exact mixed-engine SET is not supplied by the schema. Only the one
-- reported engine definition, its count and the multiple-types flag exist;
-- completeness is therefore false and no second engine type is fabricated.
-- ============================================================================
SELECT
    c.engine_subseries                                       AS reported_engine_type_id,
    c.engine_count::NUMBER(38,0)                             AS reported_engine_count,
    COALESCE(c.has_multiple_engine_types, FALSE)             AS has_multiple_engine_types,
    NOT COALESCE(c.has_multiple_engine_types, FALSE)         AS mixed_engine_set_complete,
    NULL::VARCHAR                                            AS second_engine_type_id
FROM PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_HISTORY h
JOIN PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_CONFIGURATION c
  ON c.aircraft_configuration_id = h.aircraft_configuration_id
WHERE h.aircraft_id = 1005
ORDER BY 1
