-- ============================================================================
-- Q05 schedule_four_week_changes -- independent SQL oracle over SOURCE
--
-- Parameters: start_knowledge_date, end_knowledge_date (DATE), cadence_days
-- Order by  : comparison_date, Q05_event_class rank, event_id,
--             member_side NULLS LAST, member_schedule_key NULLS LAST
--
-- Two strictly separated layers (D-0006):
--   1. EXACT facts over the unfiltered SYN-SCHEDULE-UNIVERSE-01: key-preserving
--      watched-field modifications and presence additions/removals between
--      adjacent ELIGIBLE COMPLETE snapshots. Exact rows are never replaced or
--      suppressed by candidate evidence and no question-private filter applies.
--   2. CONSERVATIVE amendment evidence over the same exact presence facts:
--      a unique overlapping removal/addition pair for one typed signature is
--      CANDIDATE_UNIQUE/MEDIUM, a many-member compatibility component is
--      AMBIGUOUS_CANDIDATE_GROUP/LOW plus its members, and every exact presence
--      row that no candidate or group consumes gets exactly one UNPAIRED row.
--      A key-changing amendment is never asserted as an exact modification.
--
-- The typed signature is (SS-04 marketing, SS-06 flight number, SS-10 origin,
-- SS-11 destination); both inclusive operating bounds SS-08/SS-09 must be
-- non-null and the two ranges must overlap. Missing signature inputs keep the
-- exact add/remove and fall through to explicit unpaired evidence.
-- ============================================================================
WITH
{{SCHEDULE_TEMPORAL}}
, {{Q05_EVENT_LABELS}}
, params AS (
    SELECT '{{start_knowledge_date}}'::DATE AS p_start,
           '{{end_knowledge_date}}'::DATE   AS p_end,
           {{cadence_days}}::NUMBER(38,0)   AS p_cadence_days
),
window_dates AS (
    SELECT e.pd
    FROM eligible_dates e, params p
    WHERE e.pd BETWEEN p.p_start AND p.p_end
),
adjacent_pairs AS (
    SELECT previous_knowledge_date, comparison_date FROM (
        SELECT LAG(pd) OVER (ORDER BY pd) AS previous_knowledge_date, pd AS comparison_date
        FROM window_dates
    ) WHERE previous_knowledge_date IS NOT NULL
),
pair_gap AS (
    -- crosses_snapshot_gap: an expected snapshot date strictly inside the pair
    -- exists in the calendar but is not eligible (missing or incomplete).
    SELECT ap.previous_knowledge_date, ap.comparison_date,
           COALESCE(BOOLOR_AGG(c.pd IS NOT NULL), FALSE) AS crosses_snapshot_gap
    FROM adjacent_pairs ap
    LEFT JOIN snapshot_calendar c
           ON c.pd > ap.previous_knowledge_date
          AND c.pd < ap.comparison_date
          AND c.is_eligible = FALSE
    GROUP BY ap.previous_knowledge_date, ap.comparison_date
),
paired_state AS (
    SELECT
        ap.previous_knowledge_date, ap.comparison_date,
        curr.schedule_key AS schedule_key,
        prev.is_present_at_date AS present_before,
        curr.is_present_at_date AS present_after,
        prev.watched AS watched_before, curr.watched AS watched_after,
        prev.watched_signature AS signature_before, curr.watched_signature AS signature_after,
        prev.marketing_carrier_internal AS before_marketing, prev.flight_number AS before_flight_number,
        prev.departure_station_code_iata AS before_origin, prev.arrival_station_code_iata AS before_destination,
        prev.effective_date AS before_effective, prev.discontinue_date AS before_discontinue,
        curr.marketing_carrier_internal AS after_marketing, curr.flight_number AS after_flight_number,
        curr.departure_station_code_iata AS after_origin, curr.arrival_station_code_iata AS after_destination,
        curr.effective_date AS after_effective, curr.discontinue_date AS after_discontinue
    -- presence_grid is a complete (schedule_key x eligible date) grid, so an
    -- inner join is total: absence is represented, never inferred.
    FROM adjacent_pairs ap
    JOIN presence_grid curr ON curr.pd = ap.comparison_date
    JOIN presence_grid prev ON prev.pd = ap.previous_knowledge_date
                           AND prev.schedule_key = curr.schedule_key
    WHERE curr.is_present_at_date OR prev.is_present_at_date
),
-- ---------------------------------------------------------------- exact layer
exact_modification AS (
    SELECT
        s.comparison_date, s.previous_knowledge_date, s.schedule_key,
        'EXACT_KEY_PRESERVING_MODIFICATION' AS event_class,
        fb.key::VARCHAR AS field_name,
        IFF(IS_NULL_VALUE(fb.value), NULL, fb.value::VARCHAR) AS old_value,
        IFF(IS_NULL_VALUE(fa.value), NULL, fa.value::VARCHAR) AS new_value
    FROM paired_state s,
         LATERAL FLATTEN(input => s.watched_before) fb,
         LATERAL FLATTEN(input => s.watched_after)  fa
    WHERE s.present_before AND s.present_after
      AND s.signature_before IS DISTINCT FROM s.signature_after
      AND fb.key = fa.key
      AND IFF(IS_NULL_VALUE(fb.value), NULL, fb.value::VARCHAR)
          IS DISTINCT FROM
          IFF(IS_NULL_VALUE(fa.value), NULL, fa.value::VARCHAR)
),
exact_presence AS (
    SELECT
        comparison_date, previous_knowledge_date, schedule_key,
        IFF(present_after, 'EXACT_ADDITION', 'EXACT_REMOVAL') AS event_class,
        IFF(present_after, 'ADDED', 'REMOVED')                AS side,
        '__presence__'                                        AS field_name,
        IFF(present_after, 'ABSENT', 'PRESENT')               AS old_value,
        IFF(present_after, 'PRESENT', 'ABSENT')               AS new_value,
        IFF(present_after, after_marketing,        before_marketing)        AS sig_marketing,
        IFF(present_after, after_flight_number,    before_flight_number)    AS sig_flight_number,
        IFF(present_after, after_origin,           before_origin)           AS sig_origin,
        IFF(present_after, after_destination,      before_destination)      AS sig_destination,
        IFF(present_after, after_effective,        before_effective)        AS sig_effective,
        IFF(present_after, after_discontinue,      before_discontinue)      AS sig_discontinue
    FROM paired_state
    WHERE present_before <> present_after
),
presence_signed AS (
    SELECT p.*,
           (sig_marketing IS NOT NULL AND sig_flight_number IS NOT NULL
            AND sig_origin IS NOT NULL AND sig_destination IS NOT NULL
            AND sig_effective IS NOT NULL AND sig_discontinue IS NOT NULL
            AND sig_effective <= sig_discontinue) AS signature_valid,
           sig_marketing || '|' || TO_VARCHAR(sig_flight_number) || '|'
             || sig_origin || '|' || sig_destination AS signature_token
    FROM exact_presence p
),
-- ------------------------------------------------------- amendment evidence
compatible_pair AS (
    SELECT r.comparison_date, r.previous_knowledge_date, r.signature_token,
           r.schedule_key AS removed_key, a.schedule_key AS added_key
    FROM presence_signed r
    JOIN presence_signed a
      ON a.comparison_date = r.comparison_date
     AND a.signature_token = r.signature_token
     AND r.side = 'REMOVED' AND a.side = 'ADDED'
    WHERE r.signature_valid AND a.signature_valid
      AND r.sig_effective <= a.sig_discontinue
      AND a.sig_effective <= r.sig_discontinue
),
signature_shape AS (
    SELECT comparison_date, previous_knowledge_date, signature_token,
           COUNT(DISTINCT removed_key) AS removed_count,
           COUNT(DISTINCT added_key)   AS added_count,
           MIN(removed_key)            AS only_removed_key,
           MIN(added_key)              AS only_added_key
    FROM compatible_pair
    GROUP BY 1, 2, 3
),
unique_candidate AS (
    SELECT s.*,
           'SYN-CAND-' || TO_VARCHAR(s.comparison_date, 'YYYYMMDD') || '-'
             || LPAD(ROW_NUMBER() OVER (PARTITION BY s.comparison_date ORDER BY s.signature_token)::VARCHAR, 2, '0')
             AS event_id
    FROM signature_shape s
    WHERE s.removed_count = 1 AND s.added_count = 1
),
ambiguous_group AS (
    SELECT s.*,
           'SYN-AMB-' || TO_VARCHAR(s.comparison_date, 'YYYYMMDD') || '-'
             || LPAD(ROW_NUMBER() OVER (PARTITION BY s.comparison_date ORDER BY s.signature_token)::VARCHAR, 2, '0')
             AS group_id
    FROM signature_shape s
    WHERE s.removed_count > 1 OR s.added_count > 1
),
ambiguous_member AS (
    SELECT g.comparison_date, g.previous_knowledge_date, g.group_id, m.side, m.schedule_key,
           g.group_id || '-M'
             || ROW_NUMBER() OVER (PARTITION BY g.group_id
                                   ORDER BY IFF(m.side = 'REMOVED', 0, 1), m.schedule_key)::VARCHAR AS event_id
    FROM ambiguous_group g
    JOIN (
        SELECT DISTINCT comparison_date, signature_token, 'REMOVED' AS side, removed_key AS schedule_key FROM compatible_pair
        UNION
        SELECT DISTINCT comparison_date, signature_token, 'ADDED',   added_key            FROM compatible_pair
    ) m ON m.comparison_date = g.comparison_date AND m.signature_token = g.signature_token
),
consumed AS (
    SELECT comparison_date, 'REMOVED' AS side, only_removed_key AS schedule_key FROM unique_candidate
    UNION
    SELECT comparison_date, 'ADDED',   only_added_key                            FROM unique_candidate
    UNION
    SELECT comparison_date, side, schedule_key                                   FROM ambiguous_member
),
unpaired AS (
    SELECT p.comparison_date, p.previous_knowledge_date, p.schedule_key, p.side
    FROM presence_signed p
    LEFT JOIN consumed c
           ON c.comparison_date = p.comparison_date
          AND c.side = p.side
          AND c.schedule_key = p.schedule_key
    WHERE c.schedule_key IS NULL
),
-- ------------------------------------------------------------ normalisation
events AS (
    SELECT comparison_date, previous_knowledge_date, event_class,
           schedule_key, NULL::VARCHAR AS related_schedule_key,
           field_name, old_value, new_value,
           NULL::VARCHAR AS group_id, NULL::VARCHAR AS member_side,
           NULL::VARCHAR AS member_schedule_key
    FROM exact_modification
    UNION ALL
    SELECT comparison_date, previous_knowledge_date, event_class,
           schedule_key, NULL, field_name, old_value, new_value, NULL, NULL, NULL
    FROM presence_signed
    UNION ALL
    SELECT comparison_date, previous_knowledge_date, 'CANDIDATE_UNIQUE',
           only_removed_key, only_added_key, NULL, NULL, NULL, NULL, NULL, NULL
    FROM unique_candidate
    UNION ALL
    SELECT comparison_date, previous_knowledge_date, 'AMBIGUOUS_CANDIDATE_GROUP',
           NULL, NULL, NULL, NULL, NULL, group_id, NULL, NULL
    FROM ambiguous_group
    UNION ALL
    SELECT comparison_date, previous_knowledge_date, 'AMBIGUOUS_GROUP_MEMBER',
           NULL, NULL, NULL, NULL, NULL, group_id, side, schedule_key
    FROM ambiguous_member
    UNION ALL
    SELECT comparison_date, previous_knowledge_date,
           IFF(side = 'ADDED', 'UNPAIRED_ADDITION', 'UNPAIRED_REMOVAL'),
           schedule_key, NULL, NULL, NULL, NULL, NULL, side, schedule_key
    FROM unpaired
),
labelled AS (
    SELECT
        e.*,
        COALESCE(
            uc.event_id,
            ag.group_id,
            am.event_id,
            lbl.label_event_id,
            'UNLABELLED|' || TO_VARCHAR(e.comparison_date, 'YYYY-MM-DD') || '|' || e.event_class
                || '|' || COALESCE(e.schedule_key, e.member_schedule_key, '') || '|' || COALESCE(e.field_name, '')
        ) AS event_id
    FROM events e
    LEFT JOIN q05_declared_event_labels lbl
           ON lbl.label_comparison_date = e.comparison_date
          AND lbl.label_event_class     = e.event_class
          AND lbl.label_schedule_key    = e.schedule_key
          AND lbl.label_field_name      = COALESCE(e.field_name, '')
    LEFT JOIN unique_candidate uc
           ON e.event_class = 'CANDIDATE_UNIQUE'
          AND uc.comparison_date = e.comparison_date
          AND uc.only_removed_key = e.schedule_key
          AND uc.only_added_key = e.related_schedule_key
    LEFT JOIN ambiguous_group ag
           ON e.event_class = 'AMBIGUOUS_CANDIDATE_GROUP' AND ag.group_id = e.group_id
    LEFT JOIN ambiguous_member am
           ON e.event_class = 'AMBIGUOUS_GROUP_MEMBER'
          AND am.group_id = e.group_id AND am.side = e.member_side
          AND am.schedule_key = e.member_schedule_key
)
SELECT
    TO_VARCHAR(l.comparison_date, 'YYYY-MM-DD')          AS comparison_date,
    TO_VARCHAR(l.previous_knowledge_date, 'YYYY-MM-DD')  AS previous_knowledge_date,
    l.event_id,
    l.event_class,
    CASE l.event_class
        WHEN 'EXACT_KEY_PRESERVING_MODIFICATION' THEN 'EXACT'
        WHEN 'EXACT_ADDITION'                    THEN 'EXACT'
        WHEN 'EXACT_REMOVAL'                     THEN 'EXACT'
        WHEN 'CANDIDATE_UNIQUE'                  THEN 'CANDIDATE'
        WHEN 'AMBIGUOUS_CANDIDATE_GROUP'         THEN 'AMBIGUOUS'
        WHEN 'AMBIGUOUS_GROUP_MEMBER'            THEN 'AMBIGUOUS'
        ELSE 'UNPAIRED'
    END                                                  AS exactness,
    CASE l.event_class
        WHEN 'EXACT_KEY_PRESERVING_MODIFICATION' THEN 'EXACT'
        WHEN 'EXACT_ADDITION'                    THEN 'EXACT'
        WHEN 'EXACT_REMOVAL'                     THEN 'EXACT'
        WHEN 'CANDIDATE_UNIQUE'                  THEN 'MEDIUM'
        WHEN 'AMBIGUOUS_CANDIDATE_GROUP'         THEN 'LOW'
        WHEN 'AMBIGUOUS_GROUP_MEMBER'            THEN 'LOW'
        ELSE 'NONE'
    END                                                  AS confidence,
    l.schedule_key,
    l.related_schedule_key,
    l.field_name,
    l.old_value,
    l.new_value,
    l.group_id,
    l.member_side,
    l.member_schedule_key,
    g.crosses_snapshot_gap
FROM labelled l
JOIN pair_gap g
  ON g.comparison_date = l.comparison_date
 AND g.previous_knowledge_date = l.previous_knowledge_date
ORDER BY
    l.comparison_date,
    CASE l.event_class
        WHEN 'EXACT_KEY_PRESERVING_MODIFICATION' THEN 10
        WHEN 'EXACT_ADDITION'                    THEN 20
        WHEN 'EXACT_REMOVAL'                     THEN 30
        WHEN 'CANDIDATE_UNIQUE'                  THEN 40
        WHEN 'AMBIGUOUS_CANDIDATE_GROUP'         THEN 50
        WHEN 'AMBIGUOUS_GROUP_MEMBER'            THEN 60
        WHEN 'UNPAIRED_ADDITION'                 THEN 70
        WHEN 'UNPAIRED_REMOVAL'                  THEN 80
        ELSE 999
    END,
    l.event_id,
    l.member_side NULLS LAST,
    l.member_schedule_key NULLS LAST
