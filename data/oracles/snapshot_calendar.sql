-- Snapshot-calendar eligibility (SC-01..SC-06). Eligible is exactly
-- is_present = TRUE AND is_complete = TRUE. A missing or incomplete date can
-- never open/close a segment or manufacture an addition, removal, entry or exit.
SELECT
    TO_VARCHAR(expected_publish_date, 'YYYY-MM-DD') AS expected_publish_date,
    COALESCE(is_present, FALSE)  AS is_present,
    COALESCE(is_complete, FALSE) AS is_complete,
    (COALESCE(is_present, FALSE) AND COALESCE(is_complete, FALSE)) AS is_eligible,
    source_lineage_id,
    observed_row_count,
    validation_status
FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR
ORDER BY expected_publish_date
