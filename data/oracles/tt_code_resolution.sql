-- ============================================================================
-- TT-CODE-RESOLUTION (HT-38) -- independent oracle over SOURCE.
--
-- AIRPORT_IATA_EXACT against AP-04, source-preserving exact string equality:
-- no case folding, punctuation stripping or fuzzy match. Candidate count is
-- distinct AP-01. A concept link exists only at EXACT cardinality one. Null
-- raw input is INVALID_INPUT and is never converted.
-- ============================================================================
WITH raw_inputs AS (
    SELECT 1 AS ord, 'SFO'::VARCHAR      AS raw_code UNION ALL
    SELECT 2, 'SYN-ZZZ'                             UNION ALL
    SELECT 3, 'SYN-DUP'                             UNION ALL
    SELECT 4, NULL
),
counted AS (
    SELECT r.ord, r.raw_code,
           COUNT(DISTINCT a.airport_id) AS candidate_count
    FROM raw_inputs r
    LEFT JOIN PK_AVIATION_TEMPORAL.SOURCE.AIRPORT_REFERENCE a
           ON r.raw_code IS NOT NULL AND a.airport_code_iata = r.raw_code
    GROUP BY r.ord, r.raw_code
)
SELECT
    raw_code,
    candidate_count::NUMBER(38,0) AS candidate_count,
    CASE
        WHEN raw_code IS NULL      THEN 'INVALID_INPUT'
        WHEN candidate_count = 0   THEN 'UNRESOLVED'
        WHEN candidate_count = 1   THEN 'EXACT'
        ELSE 'AMBIGUOUS'
    END AS resolution_status,
    (raw_code IS NOT NULL AND candidate_count = 1) AS concept_link_created
FROM counted
ORDER BY ord
