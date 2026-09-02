-- DATA-04a: knowledge-clock schedule comparisons, exact changes and key-shift candidates.
--
-- P0-07 / D-0006:
--   * exact key-preserving modifications and exact presence additions/removals are facts and are
--     never deleted, relabelled or merged with candidate evidence;
--   * a key-shifting amendment is only ever CANDIDATE_UNIQUE/MEDIUM or
--     AMBIGUOUS_CANDIDATE_GROUP/LOW, or an explicit UNPAIRED_REMOVAL / UNPAIRED_ADDITION;
--   * missing candidate inputs keep the exact add/remove plus explicit invalid evidence;
--   * incomplete and missing snapshots are excluded from every comparison, so they can never
--     manufacture a removal.
--
-- Comparison scope: every consecutive pair of eligible complete snapshot dates.  DV-16
-- crosses_snapshot_gap is true when at least one declared SC-01 calendar date lies strictly
-- between the two endpoints; the occurrence date inside the gap is never invented.

CREATE OR REPLACE TABLE MODEL_INPUT.SCHEDULE_COMPARISON
  COMMENT = 'One knowledge-clock comparison per consecutive pair of eligible complete snapshot dates. Grain DV-34 comparison_id = SHA-256 over the older and newer eligible endpoint dates. Carries DV-16 crosses_snapshot_gap and the skipped calendar dates.'
AS
WITH eligible_dates AS (
  SELECT expected_publish_date AS publish_date,
         ROW_NUMBER() OVER (ORDER BY expected_publish_date) AS eligible_rank
  FROM SOURCE.SCHEDULE_SNAPSHOT_CALENDAR
  WHERE is_present AND is_complete
), consecutive AS (
  SELECT
    prev.publish_date  AS previous_knowledge_date,
    cur.publish_date   AS comparison_date,
    prev.eligible_rank AS previous_eligible_rank,
    cur.eligible_rank  AS comparison_eligible_rank
  FROM eligible_dates cur
  JOIN eligible_dates prev ON prev.eligible_rank = cur.eligible_rank - 1
)
SELECT
  SHA2(MODEL_INPUT.LP(MODEL_INPUT.CANON_DATE(c.previous_knowledge_date))
       || MODEL_INPUT.LP(MODEL_INPUT.CANON_DATE(c.comparison_date)), 256) AS comparison_id,
  c.previous_knowledge_date,
  c.comparison_date,
  c.previous_eligible_rank,
  c.comparison_eligible_rank,
  DATEDIFF(DAY, c.previous_knowledge_date, c.comparison_date)             AS calendar_day_span,
  COUNT(cal.expected_publish_date)                                        AS skipped_calendar_date_count,
  COUNT(cal.expected_publish_date) > 0                                    AS crosses_snapshot_gap,
  LISTAGG(MODEL_INPUT.CANON_DATE(cal.expected_publish_date), ',')
    WITHIN GROUP (ORDER BY cal.expected_publish_date)                     AS skipped_calendar_dates,
  'CONSECUTIVE_ELIGIBLE'::VARCHAR                                         AS comparison_kind
FROM consecutive c
LEFT JOIN SOURCE.SCHEDULE_SNAPSHOT_CALENDAR cal
  ON cal.expected_publish_date > c.previous_knowledge_date
 AND cal.expected_publish_date < c.comparison_date
GROUP BY c.previous_knowledge_date, c.comparison_date,
         c.previous_eligible_rank, c.comparison_eligible_rank;

-- ---------------------------------------------------------------------------------------------
-- SCHEDULE_EXACT_CHANGE.
-- Presence additions/removals use the non-null synthetic field token `__presence__`.
-- Key-preserving modifications emit one row per changed watched field with old and new values.
-- INVALID_ROUTE_KEY observations still participate here: exact schedule-key presence and
-- watched-content evidence does not require a Route.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.SCHEDULE_EXACT_CHANGE
  COMMENT = 'Exact knowledge-clock schedule change facts. Grain (DV-34 comparison_id, SS-01, change_kind, field_name). Presence changes use the non-null synthetic field token __presence__; key-preserving modifications emit one row per changed SS-04..SS-38 watched field with old and new display values. Never replaced or relabelled by candidate evidence.'
AS
WITH eligible_obs AS (
  SELECT
    o.schedule_key,
    o.publish_date,
    o.watched_content_signature,
    OBJECT_CONSTRUCT_KEEP_NULL(
      'marketing_carrier_internal',          o.marketing_carrier_internal,
      'operating_carrier_internal',          o.operating_carrier_internal,
      'flight_number',                       TO_VARCHAR(o.flight_number),
      'service_type_iata',                   o.service_type_iata,
      'effective_date',                      MODEL_INPUT.CANON_DATE(o.effective_date),
      'discontinue_date',                    MODEL_INPUT.CANON_DATE(o.discontinue_date),
      'departure_station_code_iata',         o.departure_station_code_iata,
      'arrival_station_code_iata',           o.arrival_station_code_iata,
      'departure_terminal',                  o.departure_terminal,
      'arrival_terminal',                    o.arrival_terminal,
      'is_operating_monday',                 MODEL_INPUT.CANON_BOOL(o.is_operating_monday),
      'is_operating_tuesday',                MODEL_INPUT.CANON_BOOL(o.is_operating_tuesday),
      'is_operating_wednesday',              MODEL_INPUT.CANON_BOOL(o.is_operating_wednesday),
      'is_operating_thursday',               MODEL_INPUT.CANON_BOOL(o.is_operating_thursday),
      'is_operating_friday',                 MODEL_INPUT.CANON_BOOL(o.is_operating_friday),
      'is_operating_saturday',               MODEL_INPUT.CANON_BOOL(o.is_operating_saturday),
      'is_operating_sunday',                 MODEL_INPUT.CANON_BOOL(o.is_operating_sunday),
      'days_pattern',                        o.days_pattern,
      'weekly_frequency',                    TO_VARCHAR(o.weekly_frequency),
      'passenger_departure_utc_time',        MODEL_INPUT.CANON_TIME(o.passenger_departure_utc_time),
      'passenger_arrival_utc_time',          MODEL_INPUT.CANON_TIME(o.passenger_arrival_utc_time),
      'passenger_departure_local_time',      MODEL_INPUT.CANON_TIME(o.passenger_departure_local_time),
      'passenger_arrival_local_time',        MODEL_INPUT.CANON_TIME(o.passenger_arrival_local_time),
      'arrival_day_indicator',               TO_VARCHAR(o.arrival_day_indicator),
      'scheduled_block_minutes',             TO_VARCHAR(o.scheduled_block_minutes),
      'equipment_subtype_code_iata',         o.equipment_subtype_code_iata,
      'total_seats',                         MODEL_INPUT.DISPLAY_FLOAT(o.total_seats),
      'first_class_seats',                   MODEL_INPUT.DISPLAY_FLOAT(o.first_class_seats),
      'business_class_seats',                MODEL_INPUT.DISPLAY_FLOAT(o.business_class_seats),
      'premium_economy_seats',               MODEL_INPUT.DISPLAY_FLOAT(o.premium_economy_seats),
      'economy_class_seats',                 MODEL_INPUT.DISPLAY_FLOAT(o.economy_class_seats),
      'is_codeshare',                        MODEL_INPUT.CANON_BOOL(o.is_codeshare),
      'codeshare_carrier_internal',          o.codeshare_carrier_internal,
      'number_of_intermediate_stops',        TO_VARCHAR(o.number_of_intermediate_stops),
      'intermediate_stop_station_codes_iata',o.intermediate_stop_station_codes_iata
    ) AS watched_content
  FROM MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION o
  WHERE o.is_eligible_snapshot
), first_presence AS (
  SELECT schedule_key, MIN(publish_date) AS first_eligible_presence_date
  FROM eligible_obs GROUP BY schedule_key
), sides AS (
  SELECT
    c.comparison_id, c.previous_knowledge_date, c.comparison_date, c.crosses_snapshot_gap,
    c.skipped_calendar_dates,
    o.schedule_key,
    MAX(IFF(o.publish_date = c.previous_knowledge_date, 1, 0)) = 1 AS present_before,
    MAX(IFF(o.publish_date = c.comparison_date, 1, 0)) = 1         AS present_after,
    MAX(IFF(o.publish_date = c.previous_knowledge_date, o.watched_content_signature, NULL))
                                                                   AS before_signature,
    MAX(IFF(o.publish_date = c.comparison_date, o.watched_content_signature, NULL))
                                                                   AS after_signature
  FROM MODEL_INPUT.SCHEDULE_COMPARISON c
  JOIN eligible_obs o
    ON o.publish_date IN (c.previous_knowledge_date, c.comparison_date)
  GROUP BY c.comparison_id, c.previous_knowledge_date, c.comparison_date,
           c.crosses_snapshot_gap, c.skipped_calendar_dates, o.schedule_key
), presence_change AS (
  SELECT
    s.comparison_id, s.previous_knowledge_date, s.comparison_date, s.crosses_snapshot_gap,
    s.skipped_calendar_dates, s.schedule_key,
    IFF(s.present_after, 'EXACT_ADDITION', 'EXACT_REMOVAL')::VARCHAR AS change_kind,
    '__presence__'::VARCHAR                                          AS field_name,
    IFF(s.present_after, 'ABSENT', 'PRESENT')::VARCHAR               AS old_value,
    IFF(s.present_after, 'PRESENT', 'ABSENT')::VARCHAR               AS new_value,
    -- P0-05.5: a later presence after a proven complete absence is a reappearance.
    (NOT s.present_before AND s.present_after
     AND fp.first_eligible_presence_date < s.previous_knowledge_date)  AS is_reappearance
  FROM sides s
  JOIN first_presence fp ON fp.schedule_key = s.schedule_key
  WHERE s.present_before <> s.present_after
), modification AS (
  SELECT
    s.comparison_id, s.previous_knowledge_date, s.comparison_date, s.crosses_snapshot_gap,
    s.skipped_calendar_dates, s.schedule_key,
    'EXACT_KEY_PRESERVING_MODIFICATION'::VARCHAR                     AS change_kind,
    f.KEY::VARCHAR                                                   AS field_name,
    GET(b.watched_content, f.KEY)::VARCHAR                           AS old_value,
    f.VALUE::VARCHAR                                                 AS new_value,
    FALSE                                                            AS is_reappearance
  FROM sides s
  JOIN eligible_obs b ON b.schedule_key = s.schedule_key AND b.publish_date = s.previous_knowledge_date
  JOIN eligible_obs a ON a.schedule_key = s.schedule_key AND a.publish_date = s.comparison_date
  , LATERAL FLATTEN(INPUT => a.watched_content) f
  WHERE s.present_before AND s.present_after
    AND s.before_signature <> s.after_signature
    AND NOT EQUAL_NULL(GET(b.watched_content, f.KEY)::VARCHAR, f.VALUE::VARCHAR)
)
SELECT * FROM presence_change
UNION ALL
SELECT * FROM modification;

-- ---------------------------------------------------------------------------------------------
-- Key-shift candidate evidence.
-- Candidate eligibility requires every typed signature component (SS-04, SS-06, SS-10, SS-11) and
-- both inclusive operating bounds SS-08/SS-09 to be non-null and valid, plus overlapping ranges.
-- Grouping is signature-scoped, exactly as DV-36 defines its identity (comparison, typed
-- signature, sorted removed keys, sorted added keys).  This is deliberately conservative: it can
-- merge two range-disjoint pairs that share a signature into one LOW-confidence ambiguous group,
-- but it can never assert a false CANDIDATE_UNIQUE.
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE TABLE MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE
  COMMENT = 'Declared derivation: every exact presence removal and addition with its typed candidate signature, inclusive operating range and candidate eligibility verdict. Feeds the amendment candidate, group and member tables.'
AS
SELECT
  e.comparison_id,
  e.previous_knowledge_date,
  e.comparison_date,
  e.schedule_key,
  IFF(e.change_kind = 'EXACT_REMOVAL', 'REMOVED', 'ADDED')::VARCHAR   AS side,
  o.marketing_carrier_internal,
  o.flight_number,
  o.departure_station_code_iata,
  o.arrival_station_code_iata,
  o.effective_date,
  o.discontinue_date,
  o.operating_carrier_internal,
  o.days_pattern,
  o.weekly_frequency,
  o.equipment_subtype_code_iata,
  o.total_seats,
  o.passenger_departure_local_time,
  o.passenger_arrival_local_time,
  (o.marketing_carrier_internal IS NOT NULL AND o.flight_number IS NOT NULL
   AND o.departure_station_code_iata IS NOT NULL AND o.arrival_station_code_iata IS NOT NULL
   AND o.effective_date IS NOT NULL AND o.discontinue_date IS NOT NULL
   AND o.effective_date <= o.discontinue_date)                        AS candidate_eligible,
  CASE
    WHEN o.marketing_carrier_internal IS NULL OR o.flight_number IS NULL
      OR o.departure_station_code_iata IS NULL OR o.arrival_station_code_iata IS NULL
                                                        THEN 'INCOMPLETE_CANDIDATE_SIGNATURE'
    WHEN o.effective_date IS NULL OR o.discontinue_date IS NULL
                                                        THEN 'MISSING_OPERATING_RANGE'
    WHEN o.effective_date > o.discontinue_date          THEN 'INVALID_OPERATING_RANGE'
    ELSE NULL
  END::VARCHAR                                                        AS ineligibility_reason,
  CASE WHEN o.marketing_carrier_internal IS NOT NULL AND o.flight_number IS NOT NULL
        AND o.departure_station_code_iata IS NOT NULL AND o.arrival_station_code_iata IS NOT NULL
       THEN MODEL_INPUT.LP(o.marketing_carrier_internal)
            || MODEL_INPUT.LP(TO_VARCHAR(o.flight_number))
            || MODEL_INPUT.LP(o.departure_station_code_iata)
            || MODEL_INPUT.LP(o.arrival_station_code_iata)
  END                                                                 AS candidate_signature
FROM MODEL_INPUT.SCHEDULE_EXACT_CHANGE e
JOIN MODEL_INPUT.SCHEDULE_CANONICAL_OBSERVATION o
  ON o.schedule_key = e.schedule_key
 AND o.publish_date = IFF(e.change_kind = 'EXACT_REMOVAL', e.previous_knowledge_date, e.comparison_date)
WHERE e.change_kind IN ('EXACT_REMOVAL', 'EXACT_ADDITION');

CREATE OR REPLACE TABLE MODEL_INPUT.SCHEDULE_AMENDMENT_CANDIDATE
  COMMENT = 'Unique eligible removal/addition pair inside one DV-34 comparison. Grain DV-35 = SHA-256 over comparison_id, the exact removed SS-01 and the exact added SS-01. DV-18 CANDIDATE_UNIQUE with DV-19 confidence MEDIUM. Never exact; the underlying exact addition and removal always remain.'
AS
WITH pairs AS (
  SELECT
    r.comparison_id, r.candidate_signature,
    r.schedule_key AS removed_schedule_key,
    a.schedule_key AS added_schedule_key,
    r.effective_date AS removed_effective_date, r.discontinue_date AS removed_discontinue_date,
    a.effective_date AS added_effective_date,   a.discontinue_date AS added_discontinue_date,
    r.marketing_carrier_internal, r.flight_number,
    r.departure_station_code_iata, r.arrival_station_code_iata,
    r.operating_carrier_internal AS removed_operating_carrier_internal,
    a.operating_carrier_internal AS added_operating_carrier_internal,
    r.days_pattern AS removed_days_pattern, a.days_pattern AS added_days_pattern,
    r.weekly_frequency AS removed_weekly_frequency, a.weekly_frequency AS added_weekly_frequency,
    r.equipment_subtype_code_iata AS removed_equipment_subtype_code_iata,
    a.equipment_subtype_code_iata AS added_equipment_subtype_code_iata,
    r.total_seats AS removed_total_seats, a.total_seats AS added_total_seats
  FROM MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE r
  JOIN MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE a
    ON a.comparison_id = r.comparison_id
   AND a.candidate_signature = r.candidate_signature
   AND a.side = 'ADDED'
   AND r.effective_date <= a.discontinue_date
   AND a.effective_date <= r.discontinue_date
  WHERE r.side = 'REMOVED' AND r.candidate_eligible AND a.candidate_eligible
), scoped AS (
  SELECT
    p.*,
    COUNT(DISTINCT p.removed_schedule_key) OVER (PARTITION BY p.comparison_id, p.candidate_signature)
                                                                      AS signature_removed_count,
    COUNT(DISTINCT p.added_schedule_key)   OVER (PARTITION BY p.comparison_id, p.candidate_signature)
                                                                      AS signature_added_count
  FROM pairs p
)
SELECT
  SHA2(MODEL_INPUT.LP(s.comparison_id) || MODEL_INPUT.LP(s.removed_schedule_key)
       || MODEL_INPUT.LP(s.added_schedule_key), 256)                  AS amendment_candidate_id,
  s.comparison_id,
  s.removed_schedule_key,
  s.added_schedule_key,
  'CANDIDATE_UNIQUE'::VARCHAR                                         AS amendment_candidate_class,
  'MEDIUM'::VARCHAR                                                   AS amendment_confidence,
  'CANDIDATE'::VARCHAR                                                AS exactness,
  s.candidate_signature,
  s.marketing_carrier_internal,
  s.flight_number,
  s.departure_station_code_iata,
  s.arrival_station_code_iata,
  s.removed_effective_date, s.removed_discontinue_date,
  s.added_effective_date,   s.added_discontinue_date,
  s.removed_operating_carrier_internal, s.added_operating_carrier_internal,
  s.removed_days_pattern, s.added_days_pattern,
  s.removed_weekly_frequency, s.added_weekly_frequency,
  s.removed_equipment_subtype_code_iata, s.added_equipment_subtype_code_iata,
  s.removed_total_seats, s.added_total_seats
FROM scoped s
WHERE s.signature_removed_count = 1 AND s.signature_added_count = 1;

CREATE OR REPLACE TABLE MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP
  COMMENT = 'Ambiguous key-shift compatibility component inside one DV-34 comparison. Grain DV-36 = SHA-256 over comparison_id, the typed candidate signature, the sorted exact removed schedule keys and the sorted exact added schedule keys. DV-18 AMBIGUOUS_CANDIDATE_GROUP with DV-19 confidence LOW and deliberately no chosen pair.'
AS
WITH pairs AS (
  SELECT DISTINCT
    r.comparison_id, r.candidate_signature,
    r.schedule_key AS removed_schedule_key,
    a.schedule_key AS added_schedule_key,
    r.marketing_carrier_internal, r.flight_number,
    r.departure_station_code_iata, r.arrival_station_code_iata
  FROM MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE r
  JOIN MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE a
    ON a.comparison_id = r.comparison_id
   AND a.candidate_signature = r.candidate_signature
   AND a.side = 'ADDED'
   AND r.effective_date <= a.discontinue_date
   AND a.effective_date <= r.discontinue_date
  WHERE r.side = 'REMOVED' AND r.candidate_eligible AND a.candidate_eligible
), grouped AS (
  SELECT
    comparison_id, candidate_signature,
    MAX(marketing_carrier_internal)      AS marketing_carrier_internal,
    MAX(flight_number)                   AS flight_number,
    MAX(departure_station_code_iata)     AS departure_station_code_iata,
    MAX(arrival_station_code_iata)       AS arrival_station_code_iata,
    COUNT(DISTINCT removed_schedule_key) AS removed_member_count,
    COUNT(DISTINCT added_schedule_key)   AS added_member_count,
    LISTAGG(DISTINCT removed_schedule_key, ',') WITHIN GROUP (ORDER BY removed_schedule_key)
                                         AS removed_schedule_keys,
    LISTAGG(DISTINCT added_schedule_key, ',') WITHIN GROUP (ORDER BY added_schedule_key)
                                         AS added_schedule_keys
  FROM pairs
  GROUP BY comparison_id, candidate_signature
)
SELECT
  SHA2(MODEL_INPUT.LP(g.comparison_id) || MODEL_INPUT.LP(g.candidate_signature)
       || MODEL_INPUT.LP(g.removed_schedule_keys) || MODEL_INPUT.LP(g.added_schedule_keys), 256)
                                                                      AS amendment_group_id,
  g.comparison_id,
  g.candidate_signature,
  g.marketing_carrier_internal,
  g.flight_number,
  g.departure_station_code_iata,
  g.arrival_station_code_iata,
  g.removed_member_count,
  g.added_member_count,
  g.removed_schedule_keys,
  g.added_schedule_keys,
  'AMBIGUOUS_CANDIDATE_GROUP'::VARCHAR                                AS amendment_candidate_class,
  'LOW'::VARCHAR                                                      AS amendment_confidence,
  'AMBIGUOUS'::VARCHAR                                                AS exactness
FROM grouped g
WHERE NOT (g.removed_member_count = 1 AND g.added_member_count = 1);

CREATE OR REPLACE TABLE MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP_MEMBER
  COMMENT = 'Every ambiguous-group member plus every unpaired removal and addition. Grain DV-37: for a group member SHA-256 over (DV-36, side, SS-01); for an unpaired side SHA-256 over (DV-34, side, SS-01) with a null group. member_class is AMBIGUOUS_GROUP_MEMBER, UNPAIRED_REMOVAL or UNPAIRED_ADDITION.'
AS
WITH pairs AS (
  SELECT DISTINCT
    r.comparison_id, r.candidate_signature,
    r.schedule_key AS removed_schedule_key,
    a.schedule_key AS added_schedule_key
  FROM MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE r
  JOIN MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE a
    ON a.comparison_id = r.comparison_id
   AND a.candidate_signature = r.candidate_signature
   AND a.side = 'ADDED'
   AND r.effective_date <= a.discontinue_date
   AND a.effective_date <= r.discontinue_date
  WHERE r.side = 'REMOVED' AND r.candidate_eligible AND a.candidate_eligible
), participants AS (
  SELECT comparison_id, candidate_signature, removed_schedule_key AS schedule_key, 'REMOVED' AS side FROM pairs
  UNION
  SELECT comparison_id, candidate_signature, added_schedule_key,                  'ADDED'    FROM pairs
), group_member AS (
  SELECT
    SHA2(MODEL_INPUT.LP(g.amendment_group_id) || MODEL_INPUT.LP(p.side)
         || MODEL_INPUT.LP(p.schedule_key), 256)                      AS amendment_group_member_id,
    g.amendment_group_id,
    p.comparison_id,
    p.side,
    p.schedule_key                                                    AS member_schedule_key,
    'AMBIGUOUS_GROUP_MEMBER'::VARCHAR                                 AS member_class,
    'LOW'::VARCHAR                                                    AS amendment_confidence,
    'AMBIGUOUS'::VARCHAR                                              AS exactness,
    g.candidate_signature,
    NULL::VARCHAR                                                     AS unpaired_reason
  FROM participants p
  JOIN MODEL_INPUT.SCHEDULE_AMENDMENT_GROUP g
    ON g.comparison_id = p.comparison_id AND g.candidate_signature = p.candidate_signature
), unpaired AS (
  SELECT
    SHA2(MODEL_INPUT.LP(s.comparison_id) || MODEL_INPUT.LP(s.side)
         || MODEL_INPUT.LP(s.schedule_key), 256)                      AS amendment_group_member_id,
    NULL::VARCHAR                                                     AS amendment_group_id,
    s.comparison_id,
    s.side,
    s.schedule_key                                                    AS member_schedule_key,
    IFF(s.side = 'REMOVED', 'UNPAIRED_REMOVAL', 'UNPAIRED_ADDITION')::VARCHAR AS member_class,
    'NONE'::VARCHAR                                                   AS amendment_confidence,
    'UNPAIRED'::VARCHAR                                               AS exactness,
    s.candidate_signature,
    COALESCE(s.ineligibility_reason, 'NO_ELIGIBLE_PARTNER')::VARCHAR  AS unpaired_reason
  FROM MODEL_INPUT.SCHEDULE_AMENDMENT_SIDE s
  LEFT JOIN participants p
    ON p.comparison_id = s.comparison_id AND p.schedule_key = s.schedule_key AND p.side = s.side
  WHERE p.schedule_key IS NULL
)
SELECT * FROM group_member
UNION ALL
SELECT * FROM unpaired;
