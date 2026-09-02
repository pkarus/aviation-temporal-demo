-- ============================================================================
-- Q02 status_reversion_spells -- independent SQL oracle over SOURCE
--
-- Parameters: aircraft_id (NUMBER(38,0))
-- Order by  : storage_start_date, storage_start_sequence, storage_event_id,
--             return_event_id
--
-- Operates on the AUDIT assignment stream, not the daily projection, so the
-- same-day 2020-06-01 In Service -> Storage -> In Service reversion survives.
-- Ordering is (start_event_date, row_sequence_number, event_sequence_number,
-- aircraft_history_id); date alone is never the version key. Consecutive
-- equality is suppressed but global equality is not, so A -> B -> A stays
-- three assignments and every later reversion occurrence is retained.
-- ============================================================================
WITH
{{AIRCRAFT_TEMPORAL}}
, params AS (
    SELECT {{aircraft_id}}::NUMBER(38,0) AS p_aircraft_id
),
status_audit AS (
    SELECT
        a.aircraft_id, a.aircraft_history_id, a.start_event_date,
        a.row_sequence_number, a.event_sequence_number, a.lifecycle_status,
        ROW_NUMBER() OVER (
            PARTITION BY a.aircraft_id
            ORDER BY a.start_event_date, a.row_sequence_number,
                     a.event_sequence_number, a.aircraft_history_id) AS audit_ordinal
    FROM audit_assignment a
    JOIN params p ON p.p_aircraft_id = a.aircraft_id
    WHERE a.dimension = 'aircraft_status'
),
windowed AS (
    SELECT
        s.*,
        LAG(s.lifecycle_status)      OVER (PARTITION BY s.aircraft_id ORDER BY s.audit_ordinal) AS prev_status,
        LEAD(s.lifecycle_status)     OVER (PARTITION BY s.aircraft_id ORDER BY s.audit_ordinal) AS next_status,
        LEAD(s.aircraft_history_id)  OVER (PARTITION BY s.aircraft_id ORDER BY s.audit_ordinal) AS next_event_id,
        LEAD(s.start_event_date)     OVER (PARTITION BY s.aircraft_id ORDER BY s.audit_ordinal) AS next_date,
        LEAD(s.row_sequence_number)  OVER (PARTITION BY s.aircraft_id ORDER BY s.audit_ordinal) AS next_sequence
    FROM status_audit s
)
SELECT
    aircraft_id::NUMBER(38,0)                             AS aircraft_id,
    aircraft_history_id::NUMBER(38,0)                     AS storage_event_id,
    TO_VARCHAR(start_event_date, 'YYYY-MM-DD')            AS storage_start_date,
    row_sequence_number::NUMBER(38,0)                     AS storage_start_sequence,
    next_event_id::NUMBER(38,0)                           AS return_event_id,
    TO_VARCHAR(next_date, 'YYYY-MM-DD')                   AS return_date,
    next_sequence::NUMBER(38,0)                           AS return_sequence,
    DATEDIFF('day', start_event_date, next_date)::NUMBER(38,0) AS storage_days,
    (start_event_date = next_date)                        AS same_day
FROM windowed
WHERE prev_status    = 'In Service'
  AND lifecycle_status = 'Storage'
  AND next_status    = 'In Service'
ORDER BY storage_start_date, storage_start_sequence, storage_event_id, return_event_id
