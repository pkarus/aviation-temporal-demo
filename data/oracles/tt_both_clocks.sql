-- ============================================================================
-- TT-BOTH-CLOCKS (HT-23) -- independent oracle over SOURCE.
--
-- The state fixture is derived, not hard-coded: it is the single
-- SYN-SK-CLOCK_BOUNDARY_001 knowledge segment whose route resolves (the
-- null -> PHX -> null clock-route transition leaves exactly one valid-route
-- state, [2026-08-24, 2026-08-31)).
--
-- Knowledge validity is HALF-OPEN  (valid_from <= knowledge_date < valid_to);
-- operating bounds are INCLUSIVE   (effective <= operating_date <= discontinue)
-- plus the operating weekday flag. The two clocks are never conflated.
-- ============================================================================
WITH
{{SCHEDULE_TEMPORAL}}
, fixture AS (
    SELECT knowledge_valid_from, knowledge_valid_to, effective_date, discontinue_date,
           is_operating_monday, is_operating_tuesday, is_operating_wednesday,
           is_operating_thursday, is_operating_friday, is_operating_saturday, is_operating_sunday
    FROM route_state
    WHERE schedule_key = 'SYN-SK-CLOCK_BOUNDARY_001' AND route_valid
),
knowledge_axis AS (
    SELECT 1 AS k_ord, 'BEFORE' AS knowledge_position, DATEADD('day', -1, knowledge_valid_from) AS knowledge_date FROM fixture
    UNION ALL SELECT 2, 'INSIDE', knowledge_valid_from FROM fixture
    UNION ALL SELECT 3, 'AT_END', knowledge_valid_to   FROM fixture
),
operating_axis AS (
    SELECT 1 AS o_ord, 'BEFORE' AS operating_position, DATEADD('day', -1, effective_date) AS operating_date FROM fixture
    UNION ALL SELECT 2, 'INSIDE', effective_date    FROM fixture
    UNION ALL SELECT 3, 'AT_END', discontinue_date  FROM fixture
)
SELECT
    k.knowledge_position,
    TO_VARCHAR(k.knowledge_date, 'YYYY-MM-DD') AS knowledge_date,
    o.operating_position,
    TO_VARCHAR(o.operating_date, 'YYYY-MM-DD') AS operating_date,
    (k.knowledge_date >= f.knowledge_valid_from
     AND k.knowledge_date <  f.knowledge_valid_to
     AND o.operating_date >= f.effective_date
     AND o.operating_date <= f.discontinue_date
     AND CASE DAYOFWEEKISO(o.operating_date)
             WHEN 1 THEN COALESCE(f.is_operating_monday,    FALSE)
             WHEN 2 THEN COALESCE(f.is_operating_tuesday,   FALSE)
             WHEN 3 THEN COALESCE(f.is_operating_wednesday, FALSE)
             WHEN 4 THEN COALESCE(f.is_operating_thursday,  FALSE)
             WHEN 5 THEN COALESCE(f.is_operating_friday,    FALSE)
             WHEN 6 THEN COALESCE(f.is_operating_saturday,  FALSE)
             ELSE        COALESCE(f.is_operating_sunday,    FALSE)
         END)                                  AS eligible
FROM fixture f
CROSS JOIN knowledge_axis k
CROSS JOIN operating_axis o
ORDER BY k.k_ord, o.o_ord
