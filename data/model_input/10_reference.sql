-- DATA-04a: reference projections, type/engine definitions and the month-end calendar.
--
-- AIRPORT_CURRENT / AIRLINE_CURRENT are declared derivations required by the MODEL-01 design
-- brief (G-03/G-04): v1 semantic identity is AP-01 / AL-01 while the raw source grain is
-- (AP-01, AP-02) / (AL-01, AL-02).  The projection rule is a declared deterministic order, never
-- `WHERE is_current`, because ATTRIBUTE_AUTHORITY.md forbids is_active/is_current from silently
-- selecting a winner.  Every effective-period row stays available in SOURCE as lineage.

CREATE OR REPLACE TABLE MODEL_INPUT.AIRPORT_CURRENT
  COMMENT = 'One deterministically chosen reference row per AP-01 airport identity. Declared derivation for MODEL-01 G-03; source effective periods remain lineage in SOURCE.AIRPORT_REFERENCE.'
AS
WITH ranked AS (
  SELECT
    r.*,
    COUNT(*) OVER (PARTITION BY r.airport_id) AS reference_period_count,
    ROW_NUMBER() OVER (
      PARTITION BY r.airport_id
      ORDER BY r.effective_start_date DESC NULLS LAST,
               r.airport_code_iata ASC NULLS LAST,
               r.airport_code_icao ASC NULLS LAST,
               r.airport_name ASC NULLS LAST
    ) AS projection_rank
  FROM SOURCE.AIRPORT_REFERENCE r
  WHERE r.airport_id IS NOT NULL
)
SELECT
  airport_id,
  effective_start_date        AS selected_effective_start_date,
  effective_end_date          AS selected_effective_end_date,
  airport_code_iata,
  airport_code_icao,
  airport_name,
  is_active,
  is_current,
  time_zone_name,
  reference_period_count,
  'EFFECTIVE_START_DESC_THEN_CODE_ASC'::VARCHAR AS projection_rule
FROM ranked
WHERE projection_rank = 1;

CREATE OR REPLACE TABLE MODEL_INPUT.AIRLINE_CURRENT
  COMMENT = 'One deterministically chosen reference row per AL-01 airline identity. Declared derivation for MODEL-01 G-04; source effective periods remain lineage in SOURCE.AIRLINE_REFERENCE.'
AS
WITH ranked AS (
  SELECT
    r.*,
    COUNT(*) OVER (PARTITION BY r.airline_id) AS reference_period_count,
    ROW_NUMBER() OVER (
      PARTITION BY r.airline_id
      ORDER BY r.effective_start_date DESC NULLS LAST,
               r.carrier_code_iata ASC NULLS LAST,
               r.carrier_code_icao ASC NULLS LAST,
               r.carrier_full_name ASC NULLS LAST
    ) AS projection_rank
  FROM SOURCE.AIRLINE_REFERENCE r
  WHERE r.airline_id IS NOT NULL
)
SELECT
  airline_id,
  effective_start_date        AS selected_effective_start_date,
  effective_end_date          AS selected_effective_end_date,
  carrier_code_iata,
  carrier_code_icao,
  carrier_short_name,
  carrier_full_name,
  is_iata_controlled_duplicate,
  is_active,
  is_current,
  reference_period_count,
  'EFFECTIVE_START_DESC_THEN_CODE_ASC'::VARCHAR AS projection_rule
FROM ranked
WHERE projection_rank = 1;

-- ---------------------------------------------------------------------------------------------
-- AIRCRAFT_TYPE_DEFINITION (AC-05) and ENGINE_TYPE_DEFINITION (AC-14).
-- SOURCE_CONTRACT.md requires one consistent definition per non-null subseries before either can
-- be used as a functional target.  AC-08 / AC-09 are deliberately excluded from the engine proof:
-- they are configuration/assignment payload, not properties of an engine-subseries identity.
-- A subseries with more than one distinct definition keeps its identity row but carries
-- definition_status = 'AMBIGUOUS_DEFINITION' and null definition fields, so no definition is
-- invented and downstream assignments record dimension-specific ambiguity instead of a link.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_TYPE_DEFINITION
  COMMENT = 'One row per non-null AC-05 aircraft subseries with its proven AC-02..AC-07 definition. definition_status is EXACT only when the definition functional dependency holds.'
AS
WITH distinct_definition AS (
  SELECT DISTINCT
    aircraft_subseries, aircraft_family, aircraft_type, aircraft_series,
    aircraft_manufacturer, aircraft_design_class
  FROM SOURCE.AIRCRAFT_CONFIGURATION
  WHERE aircraft_subseries IS NOT NULL
), variant AS (
  SELECT aircraft_subseries, COUNT(*) AS definition_variant_count
  FROM distinct_definition GROUP BY 1
), config_count AS (
  SELECT aircraft_subseries, COUNT(*) AS source_configuration_count
  FROM SOURCE.AIRCRAFT_CONFIGURATION WHERE aircraft_subseries IS NOT NULL GROUP BY 1
)
SELECT
  v.aircraft_subseries,
  IFF(v.definition_variant_count = 1, d.aircraft_family, NULL)        AS aircraft_family,
  IFF(v.definition_variant_count = 1, d.aircraft_type, NULL)          AS aircraft_type,
  IFF(v.definition_variant_count = 1, d.aircraft_series, NULL)        AS aircraft_series,
  IFF(v.definition_variant_count = 1, d.aircraft_manufacturer, NULL)  AS aircraft_manufacturer,
  IFF(v.definition_variant_count = 1, d.aircraft_design_class, NULL)  AS aircraft_design_class,
  v.definition_variant_count,
  c.source_configuration_count,
  IFF(v.definition_variant_count = 1, 'EXACT', 'AMBIGUOUS_DEFINITION')::VARCHAR AS definition_status
FROM variant v
JOIN config_count c ON c.aircraft_subseries = v.aircraft_subseries
LEFT JOIN distinct_definition d
  ON d.aircraft_subseries = v.aircraft_subseries AND v.definition_variant_count = 1;

CREATE OR REPLACE TABLE MODEL_INPUT.ENGINE_TYPE_DEFINITION
  COMMENT = 'One row per non-null AC-14 engine subseries with its proven AC-10..AC-13/AC-15 definition. AC-08 engine count and AC-09 mixed-type flag are deliberately absent: they belong to the configuration/engine assignment, not the engine identity.'
AS
WITH distinct_definition AS (
  SELECT DISTINCT
    engine_subseries, engine_manufacturer, engine_family, engine_type,
    engine_series, engine_propulsion_type
  FROM SOURCE.AIRCRAFT_CONFIGURATION
  WHERE engine_subseries IS NOT NULL
), variant AS (
  SELECT engine_subseries, COUNT(*) AS definition_variant_count
  FROM distinct_definition GROUP BY 1
), config_count AS (
  SELECT engine_subseries, COUNT(*) AS source_configuration_count
  FROM SOURCE.AIRCRAFT_CONFIGURATION WHERE engine_subseries IS NOT NULL GROUP BY 1
)
SELECT
  v.engine_subseries,
  IFF(v.definition_variant_count = 1, d.engine_manufacturer, NULL)    AS engine_manufacturer,
  IFF(v.definition_variant_count = 1, d.engine_family, NULL)          AS engine_family,
  IFF(v.definition_variant_count = 1, d.engine_type, NULL)            AS engine_type,
  IFF(v.definition_variant_count = 1, d.engine_series, NULL)          AS engine_series,
  IFF(v.definition_variant_count = 1, d.engine_propulsion_type, NULL) AS engine_propulsion_type,
  v.definition_variant_count,
  c.source_configuration_count,
  IFF(v.definition_variant_count = 1, 'EXACT', 'AMBIGUOUS_DEFINITION')::VARCHAR AS definition_status
FROM variant v
JOIN config_count c ON c.engine_subseries = v.engine_subseries
LEFT JOIN distinct_definition d
  ON d.engine_subseries = v.engine_subseries AND v.definition_variant_count = 1;

-- ---------------------------------------------------------------------------------------------
-- MONTH_END_CALENDAR: bounded calendar entity required by the MODEL-01 design brief section 5.5,
-- so the Q03 month-end as-of join is a bounded model rule instead of an unbounded Date extension.
-- 2000-01-31 .. 2049-12-31 inclusive, 600 rows, generated deterministically.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.MONTH_END_CALENDAR
  COMMENT = 'Deterministic month-end calendar, 2000-01-31 through 2049-12-31 (600 rows). Bounded date entity for month-end as-of joins; carries no aircraft or schedule semantics.'
AS
SELECT
  LAST_DAY(DATEADD(MONTH, SEQ, DATE '2000-01-01'))                      AS month_end,
  DATE_TRUNC('MONTH', DATEADD(MONTH, SEQ, DATE '2000-01-01'))           AS month_start,
  YEAR(DATEADD(MONTH, SEQ, DATE '2000-01-01'))                          AS calendar_year,
  MONTH(DATEADD(MONTH, SEQ, DATE '2000-01-01'))                         AS calendar_month,
  SEQ                                                                   AS month_index
FROM (SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS SEQ
      FROM TABLE(GENERATOR(ROWCOUNT => 600)));
