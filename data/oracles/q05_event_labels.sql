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
-- reproduce the declared row order without being told these labels. Reviewer
-- REVIEW-D0018 proved this independently and more sharply than the original
-- finding: on 2026-08-31 the EXACT_ADDITION block orders
-- [MKT_ENTRY_714, UNPAIR_NEW] while the UNPAIRED_ADDITION block orders the same
-- two keys inverted, so NO total order on schedule_key or on any per-key
-- attribute can produce both, and the declared member_side /
-- member_schedule_key tiebreakers yield the wrong order too.
--
-- The mnemonics are therefore carried here as a declared label table, keyed on
-- the semantic identity that the oracle computes independently:
--     (comparison_date, event_class, schedule_key, field_name)
--
-- Uniqueness of that key, stated precisely: it is collision-free over the five
-- declared-label classes (EXACT_KEY_PRESERVING_MODIFICATION, EXACT_ADDITION,
-- EXACT_REMOVAL, UNPAIRED_ADDITION, UNPAIRED_REMOVAL), all of which carry a
-- non-null schedule_key. It is NOT unique over all 35 Q05 rows: the three
-- AMBIGUOUS_GROUP_MEMBER rows collide 3-way on
-- ('2026-08-24', 'AMBIGUOUS_GROUP_MEMBER', NULL, ''). That collision is
-- harmless because SQL equality never matches NULL, so those rows cannot join
-- this table at all and take their ids from the derived ambiguous_member join.
-- comparison_date and schedule_key are load-bearing (dropping either collides).
-- event_class and field_name are individually redundant today, because
-- EXACT_ADDITION carries '__presence__' where UNPAIRED_ADDITION carries '';
-- both are kept deliberately, because that redundancy is exactly what turns a
-- misclassified event into an UNLABELLED id instead of silently re-attaching a
-- valid-looking label.
--
-- Scope limit: the key includes comparison_date, so this table labels
-- Q05-CANONICAL only. Any other parameterisation renders every event
-- UNLABELLED. That is fail-loud and intended, not a generalising oracle.
--
-- An event the oracle computes that is absent from this table gets a visible
-- 'UNLABELLED|...' event_id. That string is a DIAGNOSTIC AID, not the detector:
-- REVIEW-D0018 cases P15/P16/P17 degraded the fallback to a plausible string
-- and extra, misclassified and misattributed events were still caught, by
-- cardinality plus the fourteen derived columns.
--
-- The candidate, ambiguous-group and group-member event ids, and every
-- group_id, are computed here rather than looked up -- but only their CONTENT
-- is derived. Adopted from the frozen manifest, and stated so plainly:
--   * the string templates SYN-CAND-<YYYYMMDD>-NN, SYN-AMB-<YYYYMMDD>-NN and
--     <group_id>-M<k>, including the two-digit zero padding. Neither SYN-CAND
--     nor SYN-AMB appears in SOURCE_CONTRACT.md, ATTRIBUTE_AUTHORITY.md,
--     DEMO_QUESTIONS.md or data/SYNTHETIC_DATA_SPEC.md -- only in
--     EXPECTED_ANSWERS.yaml;
--   * the NN ordinal rule ROW_NUMBER() OVER (PARTITION BY comparison_date
--     ORDER BY signature_token). This universe holds exactly one candidate and
--     one group, so NN is always '01' and the rule is entirely unconstrained by
--     evidence;
--   * the -Mk member ordering REMOVED before ADDED then schedule_key ascending.
--     It is weakly grounded in the DV-37 side enumeration REMOVED|ADDED but is
--     nowhere stated as a sort rule; the natural alternative (schedule_key,
--     side) produces a different, failing answer, so this was fitted to the
--     manifest, not read off the contract.
-- These five ids are still held to the semantic verdict (unlike the 30
-- declared mnemonics), so a format regression in them fails loudly.
--
-- Proposed DECISION_LOG entry: this is a manifest/contract conflict, not merely
-- a non-derivable presentation column. EXPECTED_ANSWERS.yaml populates event_id
-- with values that contradict the contract's own identity definition
-- (ATTRIBUTE_AUTHORITY DV-34..37 SHA-256) and then makes that column
-- load-bearing as a sort key -- the same species of internal inconsistency that
-- D-0010 and D-0011 resolved by reviewed manifest supersession. Supersession
-- was considered and rejected here on two grounds: it would change 30 event_id
-- values, the declared row sequence and the Q05 result hash (a far larger blast
-- radius than D-0010/D-0011), and replacing legible mnemonics with SHA-256
-- digests would make the customer-facing Q05 output unreadable in a demo whose
-- point is legible temporal reconciliation. The recorded rollback is a reviewed
-- supersession of Q05's order_by to a derivable key -- for example
-- (comparison_date, event_class rank, schedule_key, field_name, member_side,
-- member_schedule_key) -- demoting event_id to a non-ordering presentation
-- column. That changes the declared row sequence but no row's content.
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
