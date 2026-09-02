-- ============================================================================
-- Q05 declared event-label table -- NOT an independently derived value.
--
-- EXPECTED_ANSWERS.yaml carries hand-authored mnemonic event_id values for the
-- 22 exact and 8 unpaired Q05 rows (for example SYN-CHG-20260810-BASE-SEATS,
-- SYN-UNPAIR-ADD-20260831). ATTRIBUTE_AUTHORITY.md DV-34/DV-35/DV-36/DV-37
-- define SHA-256 identities, not these strings, and the mnemonics follow no
-- consistent generative rule (BASE_100 -> "BASE", PHY_BASE_700 -> "CAP-700",
-- ADD_300 -> "300" as an addition but "ADD300" as a modification, and the two
-- 2026-08-31 UNPAIR rows carry no suffix at all while their MKT siblings do).
--
-- The frozen order_by sorts on event_id, so no implementation can even
-- reproduce the declared row order without being told these labels. They are
-- therefore carried here as a declared label table, keyed on the semantic
-- identity that the oracle computes independently:
--     (comparison_date, event_class, schedule_key, field_name)
--
-- An event the oracle computes that is absent from this table gets a visible
-- 'UNLABELLED|...' event_id, so the label table cannot mask an extra event, a
-- missing event, or a misclassified event. Candidate, ambiguous-group,
-- group-member event ids and every group_id are derived, not declared.
--
-- Proposed DECISION_LOG entry: either publish a derivation rule for Q05
-- event_id, or record it explicitly as a presentation label that conformance
-- checks compare through a declared map.
-- ============================================================================
q05_declared_event_labels AS (
    SELECT
        column1::DATE    AS label_comparison_date,
        column2::VARCHAR AS label_event_class,
        column3::VARCHAR AS label_schedule_key,
        column4::VARCHAR AS label_field_name,
        column5::VARCHAR AS label_event_id
    FROM VALUES
        ('2026-08-10','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-BASE_100','total_seats','SYN-CHG-20260810-BASE-SEATS'),
        ('2026-08-10','EXACT_ADDITION','SYN-SK-ADD_300','__presence__','SYN-ADD-20260810-300'),
        ('2026-08-10','EXACT_REMOVAL','SYN-SK-REMOVE_200','__presence__','SYN-REM-20260810-200'),
        ('2026-08-10','EXACT_REMOVAL','SYN-SK-REAPPEAR_400','__presence__','SYN-REM-20260810-REAPPEAR'),
        ('2026-08-10','UNPAIRED_ADDITION','SYN-SK-ADD_300','','SYN-UNPAIR-ADD-20260810-300'),
        ('2026-08-10','UNPAIRED_REMOVAL','SYN-SK-REMOVE_200','','SYN-UNPAIR-REM-20260810-200'),
        ('2026-08-10','UNPAIRED_REMOVAL','SYN-SK-REAPPEAR_400','','SYN-UNPAIR-REM-20260810-REAPPEAR'),
        ('2026-08-17','EXACT_ADDITION','SYN-SK-REAPPEAR_400','__presence__','SYN-ADD-20260817-REAPPEAR'),
        ('2026-08-17','EXACT_ADDITION','SYN-SK-SHIFT_NEW','__presence__','SYN-ADD-20260817-SHIFT-NEW'),
        ('2026-08-17','EXACT_REMOVAL','SYN-SK-SHIFT_OLD','__presence__','SYN-REM-20260817-SHIFT-OLD'),
        ('2026-08-17','UNPAIRED_ADDITION','SYN-SK-REAPPEAR_400','','SYN-UNPAIR-ADD-20260817-REAPPEAR'),
        ('2026-08-24','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-ADD_300','weekly_frequency','SYN-CHG-20260824-ADD300-FREQ'),
        ('2026-08-24','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-CLOCK_BOUNDARY_001','arrival_station_code_iata','SYN-CHG-20260824-CLOCK-ROUTE-OPEN'),
        ('2026-08-24','EXACT_ADDITION','SYN-SK-AMB_NEW_A','__presence__','SYN-ADD-20260824-AMB-A'),
        ('2026-08-24','EXACT_ADDITION','SYN-SK-AMB_NEW_B','__presence__','SYN-ADD-20260824-AMB-B'),
        ('2026-08-24','EXACT_REMOVAL','SYN-SK-AMB_OLD','__presence__','SYN-REM-20260824-AMB-OLD'),
        ('2026-08-31','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-BASE_100','departure_terminal','SYN-CHG-20260831-BASE-TERMINAL'),
        ('2026-08-31','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-PHY_BASE_700','departure_terminal','SYN-CHG-20260831-CAP-700-TERMINAL'),
        ('2026-08-31','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-PHY_BASE_701','departure_terminal','SYN-CHG-20260831-CAP-701-TERMINAL'),
        ('2026-08-31','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-MKT_COPY_702','departure_terminal','SYN-CHG-20260831-CAP-702-TERMINAL'),
        ('2026-08-31','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-CSH_ONLY_900','departure_terminal','SYN-CHG-20260831-CAP-900-TERMINAL'),
        ('2026-08-31','EXACT_KEY_PRESERVING_MODIFICATION','SYN-SK-CLOCK_BOUNDARY_001','arrival_station_code_iata','SYN-CHG-20260831-CLOCK-ROUTE-CLOSE'),
        ('2026-08-31','EXACT_ADDITION','SYN-SK-MKT_ENTRY_714','__presence__','SYN-ADD-20260831-MKT-ENTRY'),
        ('2026-08-31','EXACT_ADDITION','SYN-SK-UNPAIR_NEW','__presence__','SYN-ADD-20260831-UNPAIR-NEW'),
        ('2026-08-31','EXACT_REMOVAL','SYN-SK-MKT_EXIT_715','__presence__','SYN-REM-20260831-MKT-EXIT'),
        ('2026-08-31','EXACT_REMOVAL','SYN-SK-UNPAIR_OLD','__presence__','SYN-REM-20260831-UNPAIR-OLD'),
        ('2026-08-31','UNPAIRED_ADDITION','SYN-SK-UNPAIR_NEW','','SYN-UNPAIR-ADD-20260831'),
        ('2026-08-31','UNPAIRED_ADDITION','SYN-SK-MKT_ENTRY_714','','SYN-UNPAIR-ADD-20260831-MKT-ENTRY'),
        ('2026-08-31','UNPAIRED_REMOVAL','SYN-SK-UNPAIR_OLD','','SYN-UNPAIR-REM-20260831'),
        ('2026-08-31','UNPAIRED_REMOVAL','SYN-SK-MKT_EXIT_715','','SYN-UNPAIR-REM-20260831-MKT-EXIT')
)
