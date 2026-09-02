-- ============================================================================
-- TT-CABIN-QUALITY (HT-28) -- independent oracle over SOURCE.
--
-- Raw SS-30..SS-34 are retained. Premium economy is a SUBSET of economy, so
-- the exclusive economy bucket is economy - premium. exclusive_sum is only
-- evidence-backed when every cabin value is present, non-negative and premium
-- does not exceed economy; otherwise it is null and the row is flagged.
-- Quality precedence: NULL > NEGATIVE > PREMIUM_EXCEEDS > TOTAL_MISMATCH.
--
-- fixture_case is a declared label (SYN-SK-DIAG-NEGATIVE-CABIN maps to the
-- manifest case NEGATIVE_SOURCE, so the key stem is not the case name).
-- ============================================================================
WITH sources AS (
    SELECT 1 AS ord, 'CONSISTENT' AS fixture_case,
           total_seats, first_class_seats, business_class_seats,
           premium_economy_seats, economy_class_seats
    FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT
    WHERE schedule_key = 'SYN-SK-PHY_BASE_700' AND publish_date = DATE '2026-08-31'
    UNION ALL
    SELECT CASE schedule_key
               WHEN 'SYN-SK-DIAG-TOTAL-MISMATCH'  THEN 2
               WHEN 'SYN-SK-DIAG-NULL-CABIN'      THEN 3
               WHEN 'SYN-SK-DIAG-NEGATIVE-CABIN'  THEN 4
               ELSE 5 END,
           CASE schedule_key
               WHEN 'SYN-SK-DIAG-TOTAL-MISMATCH'  THEN 'TOTAL_MISMATCH'
               WHEN 'SYN-SK-DIAG-NULL-CABIN'      THEN 'NULL_CABIN'
               WHEN 'SYN-SK-DIAG-NEGATIVE-CABIN'  THEN 'NEGATIVE_SOURCE'
               ELSE 'PREMIUM_GREATER_THAN_ECONOMY' END,
           total_seats, first_class_seats, business_class_seats,
           premium_economy_seats, economy_class_seats
    FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT
    WHERE schedule_key IN ('SYN-SK-DIAG-TOTAL-MISMATCH', 'SYN-SK-DIAG-NULL-CABIN',
                           'SYN-SK-DIAG-NEGATIVE-CABIN', 'SYN-SK-DIAG-PREMIUM-EXCEEDS')
      AND publish_date = DATE '2026-10-19'
),
scored AS (
    SELECT s.*,
           (economy_class_seats - premium_economy_seats) AS economy_excluding_premium_seats,
           CASE
               WHEN total_seats IS NULL OR first_class_seats IS NULL
                 OR business_class_seats IS NULL OR premium_economy_seats IS NULL
                 OR economy_class_seats IS NULL                              THEN 'NULL_CABIN_VALUE'
               WHEN total_seats < 0 OR first_class_seats < 0
                 OR business_class_seats < 0 OR premium_economy_seats < 0
                 OR economy_class_seats < 0                                  THEN 'NEGATIVE_CABIN_VALUE'
               WHEN premium_economy_seats > economy_class_seats              THEN 'PREMIUM_EXCEEDS_ECONOMY'
               WHEN (first_class_seats + business_class_seats + economy_class_seats)
                    <> total_seats                                           THEN 'TOTAL_MISMATCH'
               ELSE 'RECONCILED'
           END AS quality_status
    FROM sources s
)
SELECT
    fixture_case,
    total_seats::FLOAT                          AS total_seats,
    first_class_seats::FLOAT                    AS first_seats,
    business_class_seats::FLOAT                 AS business_seats,
    premium_economy_seats::FLOAT                AS premium_economy_seats,
    economy_class_seats::FLOAT                  AS economy_including_premium_seats,
    economy_excluding_premium_seats::FLOAT      AS economy_excluding_premium_seats,
    IFF(quality_status IN ('RECONCILED', 'TOTAL_MISMATCH'),
        (first_class_seats + business_class_seats + premium_economy_seats
         + economy_excluding_premium_seats)::FLOAT, NULL) AS exclusive_sum,
    quality_status
FROM scored
ORDER BY ord
