#!/usr/bin/env python3
"""Tests for the DATA-04a canonical temporal model-input layer.

Two tiers:

* pure-local tests exercise SQL construction, scope pinning, idempotency shape and the column
  lineage dictionary without touching Snowflake;
* live tests are marked `live` and run the real gates against PK_AVIATION_TEMPORAL.

    .venv/bin/pytest data/test_model_input.py -m "not live"
    .venv/bin/pytest data/test_model_input.py -m live
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

import build_model_input as bmi  # noqa: E402

SQL_TEXT = {name: (bmi.SQL_DIR / name).read_text(encoding="utf-8") for name in bmi.SQL_FILES}
ALL_SQL = "\n".join(SQL_TEXT.values())


def strip_line_comments(text: str) -> str:
    """Remove `--` comments without touching text inside single-quoted literals."""
    out, quoted, index = [], False, 0
    while index < len(text):
        char = text[index]
        if char == "'":
            quoted = not quoted
            out.append(char)
        elif not quoted and text.startswith("--", index):
            end = text.find("\n", index)
            index = len(text) if end == -1 else end
            continue
        else:
            out.append(char)
        index += 1
    return "".join(out)


def split_statements(text: str) -> list[str]:
    """Split on `;` outside single-quoted literals and `$$` bodies."""
    body = strip_line_comments(text)
    statements, buffer, quoted, dollar, index = [], [], False, False, 0
    while index < len(body):
        if body.startswith("$$", index):
            dollar = not dollar
            buffer.append("$$")
            index += 2
            continue
        char = body[index]
        if char == "'" and not dollar:
            quoted = not quoted
        if char == ";" and not quoted and not dollar:
            statements.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(char)
        index += 1
    if "".join(buffer).strip():
        statements.append("".join(buffer).strip())
    return [s for s in statements if s]


ALL_SQL_NO_COMMENTS = "\n".join(strip_line_comments(text) for text in SQL_TEXT.values())


# ---------------------------------------------------------------------------------------------
# scope and safety
# ---------------------------------------------------------------------------------------------


def test_connection_scope_is_pinned():
    assert bmi.CONNECTION == "rai"
    assert bmi.ROLE == "RAI_DEMO_AVIATION_TEMPORAL"
    assert bmi.WAREHOUSE == "RAI_XS"
    assert bmi.DATABASE == "PK_AVIATION_TEMPORAL"
    assert bmi.SCHEMA == "MODEL_INPUT"


def test_no_caller_override_of_scope():
    """The CLI must not expose connection, role, warehouse or database flags."""
    source = (ROOT / "data" / "build_model_input.py").read_text(encoding="utf-8")
    for flag in ("--role", "--connection", "--warehouse", "--database", "--schema"):
        assert f'add_argument("{flag}"' not in source


def test_sql_touches_no_other_database_or_mutable_schema():
    for database, _schema in re.findall(
            r"\b([A-Z][A-Z0-9_]*)\.(SOURCE|VALIDATION|MODEL_INPUT)\b", ALL_SQL_NO_COMMENTS):
        assert database == "PK_AVIATION_TEMPORAL", database
    # Nothing may be created or altered outside MODEL_INPUT.
    for match in re.findall(
            r"(?:CREATE OR REPLACE (?:TABLE|FUNCTION)|ALTER TABLE)\s+([A-Za-z0-9_.]+)",
            ALL_SQL_NO_COMMENTS):
        assert match.split(".")[0].upper() in {"MODEL_INPUT", "PK_AVIATION_TEMPORAL"}, match
    assert "SOURCE." in ALL_SQL_NO_COMMENTS  # SOURCE is read, never written
    assert not re.search(r"(?:INSERT|UPDATE|MERGE)\s+INTO\s+\S*SOURCE\.", ALL_SQL_NO_COMMENTS, re.I)


def test_sql_contains_no_destructive_statements():
    for pattern in (r"\bDROP\s+(TABLE|SCHEMA|DATABASE)\b", r"\bTRUNCATE\b", r"\bDELETE\s+FROM\b",
                    r"\bGRANT\b", r"\bREVOKE\b", r"\bCREATE\s+ROLE\b", r"\bUSE\s+ROLE\b"):
        assert not re.search(pattern, ALL_SQL_NO_COMMENTS, re.I), pattern


def test_every_ddl_statement_is_idempotent():
    """Only CREATE OR REPLACE / CREATE IF NOT EXISTS / ALTER / COMMENT are allowed."""
    for name, text in SQL_TEXT.items():
        for statement in split_statements(text):
            head = statement.lstrip().split("\n", 1)[0].upper()
            assert (head.startswith("CREATE OR REPLACE")
                    or head.startswith("CREATE SCHEMA IF NOT EXISTS")
                    or head.startswith("ALTER TABLE")
                    or head.startswith("COMMENT ON")), f"{name}: {head[:80]}"


# ---------------------------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------------------------


def test_plan_is_deterministic_and_ordered():
    first, second = bmi.plan(), bmi.plan()
    assert first == second
    positions = [first.index(f"===== {name} ") for name in bmi.SQL_FILES]
    assert positions == sorted(positions)


def test_plan_needs_no_connection(monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("--plan must not connect to Snowflake")
    monkeypatch.setattr(bmi, "run_snow", explode)
    assert bmi.plan().startswith("-- ===== 00_setup.sql")


# ---------------------------------------------------------------------------------------------
# contract coverage and column lineage
# ---------------------------------------------------------------------------------------------


def test_contract_field_parse_is_complete():
    contract = bmi.parse_contract_fields()
    field_ids = {fid for entries in contract.values() for fid, _ in entries}
    assert len(field_ids) == 195


def test_every_contract_canonical_object_has_a_table():
    contract_text = (ROOT / "SOURCE_CONTRACT.md").read_text(encoding="utf-8")
    section = contract_text.split("## Canonical physical model-input contracts", 1)[1]
    section = section.split("## Multiplicity and integrity gates", 1)[0]
    named = set(re.findall(r"^\| `([A-Z_]+)` \|", section, flags=re.MULTILINE))
    assert named, "no canonical objects parsed from SOURCE_CONTRACT.md"
    missing = named - set(bmi.CONTRACT_OBJECTS)
    assert not missing, f"canonical objects with no MODEL_INPUT table: {sorted(missing)}"


def test_every_declared_table_is_created_by_the_sql():
    for table in set(bmi.CONTRACT_OBJECTS.values()) | set(bmi.ADDITIONAL_OBJECTS):
        assert f"CREATE OR REPLACE TABLE MODEL_INPUT.{table}\n" in ALL_SQL, table


def test_every_created_table_is_declared_and_change_tracked():
    created = set(re.findall(r"CREATE OR REPLACE TABLE MODEL_INPUT\.([A-Z_]+)", ALL_SQL))
    declared = set(bmi.CONTRACT_OBJECTS.values()) | set(bmi.ADDITIONAL_OBJECTS)
    assert created == declared, created ^ declared
    tracked = set(re.findall(r"ALTER TABLE MODEL_INPUT\.([A-Z_]+)\s+SET CHANGE_TRACKING", ALL_SQL))
    assert created == tracked, created ^ tracked
    assert created == set(bmi.TABLE_SOURCE_PREFIXES), created ^ set(bmi.TABLE_SOURCE_PREFIXES)


def test_column_comment_prefers_the_declared_source_prefix_scope():
    contract = {"PUBLISH_DATE": [("AC-16", "Reference lineage date."),
                                 ("AH-33", "Source lineage date."),
                                 ("SS-03", "Knowledge observation date.")]}
    assert bmi.column_comment("AIRCRAFT_EVENT_ELIGIBLE", "PUBLISH_DATE", contract).startswith("Field AH-33")
    assert bmi.column_comment("SCHEDULE_CANONICAL_OBSERVATION", "PUBLISH_DATE", contract).startswith("Field SS-03")


def test_column_comment_rejects_an_untraceable_column():
    with pytest.raises(bmi.GateError):
        bmi.column_comment("ROUTE_STATE", "SOMETHING_UNDOCUMENTED", {})


def test_derived_column_descriptions_are_non_empty():
    for column, description in bmi.DERIVED_COLUMNS.items():
        assert description.strip(), column
        assert len(description) > 15, column


# ---------------------------------------------------------------------------------------------
# semantic invariants visible in the SQL itself
# ---------------------------------------------------------------------------------------------


def test_sentinels_stay_distinct():
    assert bmi.MODEL_OPEN_SENTINEL == "9999-01-01"
    assert bmi.SOURCE_UNKNOWN_FUTURE == "9999-12-31"
    assert "IFF(V = DATE '9999-12-31', NULL, V)" in SQL_TEXT["00_setup.sql"]
    # The source unknown-future sentinel is only recognised in the normalizer and the aircraft
    # eligibility filter; it never reaches the schedule, passenger, flight or fulfillment layers.
    for name in ("40_schedule.sql", "41_schedule_changes.sql", "50_passenger.sql",
                 "60_actual_flight.sql", "70_fulfillment.sql"):
        assert "9999-12-31" not in SQL_TEXT[name], name
    # The model open sentinel is only ever produced as a derived upper bound.
    producing = {name for name, text in SQL_TEXT.items()
                 if re.search(r"DATE '9999-01-01'", re.sub(r"--[^\n]*|COMMENT = '[^']*'", "", text))}
    assert producing == {"30_aircraft.sql", "40_schedule.sql"}, producing
    for statement, alias in ((SQL_TEXT["30_aircraft.sql"], "existence_to"),
                             (SQL_TEXT["40_schedule.sql"], "knowledge_valid_to")):
        line = next(l for l in statement.splitlines()
                    if "DATE '9999-01-01'" in l and not l.strip().startswith("--"))
        assert alias in line, line


def test_route_state_identity_excludes_route():
    text = SQL_TEXT["40_schedule.sql"]
    assert ("seg.schedule_key || '|' || MODEL_INPUT.CANON_DATE(seg.publish_date)"
            "   AS route_state_key") in text
    assert "PARTITION BY p.schedule_key" in text
    # Versioning is never partitioned by route and the multi-open shape is documented as required.
    assert "PARTITION BY route_id" not in text
    assert "PARTITION BY seg.route_id" not in text
    assert "no one-open-per-route constraint exists anywhere here" in text.lower()


def test_audit_assignment_carries_no_interval():
    text = SQL_TEXT["31_aircraft_assignments.sql"]
    audit = text.split("CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_DIMENSION_AUDIT_ASSIGNMENT", 1)[1]
    audit = audit.split("CREATE OR REPLACE TABLE MODEL_INPUT.AIRCRAFT_DIMENSION_DAILY_ASSIGNMENT", 1)[0]
    assert "AS valid_from" not in audit and "AS valid_to" not in audit


def test_audit_identity_includes_date_sequence_and_history_id():
    text = SQL_TEXT["31_aircraft_assignments.sql"]
    assert ("r.dimension || '|' || TO_VARCHAR(r.aircraft_id) || '|'\n"
            "    || MODEL_INPUT.CANON_DATE(r.start_event_date) || '|'\n"
            "    || TO_VARCHAR(r.row_sequence_number) || '|' || TO_VARCHAR(r.aircraft_history_id)") in text


def test_change_detection_suppresses_only_consecutive_equality():
    text = SQL_TEXT["31_aircraft_assignments.sql"]
    assert "d.previous_watched_signature IS NULL" in text
    assert "d.watched_signature <> d.previous_watched_signature" in text
    # A global DISTINCT over watched values would destroy A -> B -> A.
    assert "SELECT DISTINCT" not in text.upper().replace("SELECT DISTINCT SCHEDULE_KEY", "")


def test_marketing_and_operating_roles_are_separate_columns():
    for name in ("40_schedule.sql", "50_passenger.sql", "60_actual_flight.sql"):
        text = SQL_TEXT[name]
        assert "marketing_airline_id" in text and "operating_airline_id" in text
        assert "AS airline_id" not in text


def test_only_eligible_snapshots_drive_inference():
    text = SQL_TEXT["40_schedule.sql"] + SQL_TEXT["41_schedule_changes.sql"]
    assert "WHERE is_present AND is_complete" in text
    assert "o.is_eligible_snapshot" in text


def test_exact_and_candidate_evidence_never_merge():
    text = SQL_TEXT["41_schedule_changes.sql"]
    assert "'CANDIDATE_UNIQUE'" in text and "'MEDIUM'" in text
    assert "'AMBIGUOUS_CANDIDATE_GROUP'" in text and "'LOW'" in text
    assert "'UNPAIRED_REMOVAL'" in text and "'UNPAIRED_ADDITION'" in text
    for exact_label in ("EXACT_ADDITION", "EXACT_REMOVAL", "EXACT_KEY_PRESERVING_MODIFICATION"):
        assert exact_label in text
    fulfil = SQL_TEXT["70_fulfillment.sql"]
    assert "'EXACT_FULFILLMENT'" in fulfil and "'HEURISTIC_CANDIDATE'" in fulfil
    assert "'AMBIGUOUS_GROUP_MEMBER'" in fulfil and "'UNMATCHED_ACTUAL'" in fulfil
    # The exact table is built before, and independently of, any candidate evidence.
    exact_block = fulfil.split("CREATE OR REPLACE TABLE MODEL_INPUT.FULFILLMENT_EXACT", 1)[1]
    exact_block = exact_block.split("CREATE OR REPLACE TABLE", 1)[0]
    assert "FULFILLMENT_CANDIDATE" not in exact_block
    assert "FULFILLMENT_COMPATIBILITY" not in exact_block


def test_quarantine_keys_never_invent_identity():
    aircraft = SQL_TEXT["30_aircraft.sql"]
    passenger = SQL_TEXT["50_passenger.sql"]
    assert "COALESCE(TO_VARCHAR(h.aircraft_history_id), h.typed_normalized_row_hash)" in aircraft
    assert "COUNT(*)                                                          AS occurrence_count" in aircraft
    assert "MODEL_INPUT.LP(p.typed_normalized_row_hash)" in passenger
    assert "AS occurrence_count" in passenger


def test_gate_ids_are_unique_and_cover_every_required_family():
    ids = [gate[0] for gate in bmi.GATES]
    assert len(ids) == len(set(ids))
    for prefix in ("MG-", "TG-", "XG-", "HG-", "AT-"):
        assert any(gate_id.startswith(prefix) for gate_id in ids), prefix


def test_multi_open_gate_asserts_concurrency_is_preserved():
    gate = next(g for g in bmi.GATES if g[0] == "XG-01")
    assert callable(gate[3])
    assert gate[3]("5") and not gate[3]("1")


# ---------------------------------------------------------------------------------------------
# live tests
# ---------------------------------------------------------------------------------------------


@pytest.mark.live
def test_live_gates_all_pass():
    result = bmi.verify()
    assert result["failures"] == [], result["failures"]


@pytest.mark.live
def test_live_every_contract_object_exists_and_is_populated_or_explained():
    result = bmi.verify()
    counts = {row["OBJECT_NAME"]: row["ROW_COUNT"]
              for row in result["row_counts_and_fingerprints"]}
    for name, table in bmi.CONTRACT_OBJECTS.items():
        assert table in counts, f"{name} is missing from MODEL_INPUT"
    # Only the aircraft-event quarantine is legitimately empty: the shipped fixtures contain no
    # ineligible aircraft event.  Everything else must carry rows.
    empty = {table for table, count in counts.items() if count == 0}
    assert empty <= {"AIRCRAFT_EVENT_QUARANTINE"}, empty


@pytest.mark.live
def test_live_apply_is_idempotent():
    first = bmi.verify()["row_counts_and_fingerprints"]
    bmi.apply()
    second = bmi.verify()["row_counts_and_fingerprints"]
    assert {r["OBJECT_NAME"]: (r["ROW_COUNT"], r["CONTENT_FINGERPRINT"]) for r in first} == \
           {r["OBJECT_NAME"]: (r["ROW_COUNT"], r["CONTENT_FINGERPRINT"]) for r in second}
