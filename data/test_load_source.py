#!/usr/bin/env python3
"""Local fail-closed tests for the lean SOURCE loader.  These tests never connect to Snowflake."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import load_source as loader  # noqa: E402

SCALES = ("demo", "smoke")

# The six tables whose contract-nullable identity columns cannot be a PRIMARY KEY, because
# Snowflake makes a PRIMARY KEY column physically NOT NULL even when NOT ENFORCED NORELY.
D0016_UNIQUE = {
    "AIRCRAFT_MASTER": ("UQ_AIRCRAFT_MASTER_ID", ("aircraft_id",)),
    "AIRCRAFT_HISTORY": ("UQ_AIRCRAFT_HISTORY_ID", ("aircraft_history_id",)),
    "AIRCRAFT_CONFIGURATION": ("UQ_AIRCRAFT_CONFIGURATION_ID", ("aircraft_configuration_id",)),
    "AIRCRAFT_FLIGHT": ("UQ_AIRCRAFT_FLIGHT_ID", ("flight_id",)),
    "AIRPORT_REFERENCE": ("UQ_AIRPORT_REFERENCE_ID", ("airport_id", "effective_start_date")),
    "AIRLINE_REFERENCE": ("UQ_AIRLINE_REFERENCE_ID", ("airline_id", "effective_start_date")),
}
# Pre-existing source-row-ID uniqueness that D-0016 does not change.
PASSENGER_UNIQUE = {
    "PASSENGER_FORWARD": ("UQ_PASSENGER_FORWARD_SOURCE_ID", ("forward_source_row_id",)),
    "PASSENGER_HISTORICAL": ("UQ_PASSENGER_HISTORICAL_SOURCE_ID", ("historical_source_row_id",)),
}


@pytest.fixture(autouse=True)
def no_snowflake(monkeypatch):
    """Any attempt to shell out (and therefore to reach Snowflake) fails the test."""

    def refuse(*args, **kwargs):
        raise AssertionError(f"the loader test suite must not run a subprocess: {args!r}")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(loader.subprocess, "run", refuse)


@pytest.fixture(scope="module")
def fields():
    return loader.parse_contract_fields()


def manifest_of(scale: str) -> dict:
    return json.loads((loader.package_dir(scale) / "manifest.json").read_bytes())


# --- contract parsing --------------------------------------------------------------------------


def test_contract_parses_204_fields(fields):
    assert sum(len(value) for value in fields.values()) == 204
    assert set(fields) == set(loader.TABLE_ORDER)
    for table, table_fields in fields.items():
        prefix = loader.PREFIX[table]
        assert [field.field_id for field in table_fields] == sorted(
            field.field_id for field in table_fields
        )
        assert all(field.field_id.startswith(f"{prefix}-") for field in table_fields)
        assert len({field.column for field in table_fields}) == len(table_fields)


def test_contract_field_ids_are_dense(fields):
    for table_fields in fields.values():
        numbers = [int(field.field_id.split("-")[1]) for field in table_fields]
        assert numbers == list(range(1, len(numbers) + 1))


# --- DDL ---------------------------------------------------------------------------------------


def create_statements(fields) -> dict[str, str]:
    return {
        label.removeprefix("source_"): statement
        for label, statement in loader.ddl_statements(fields)
        if label.startswith("source_")
    }


def test_ddl_is_deterministic(fields):
    first = loader.ddl_statements(fields)
    second = loader.ddl_statements(loader.parse_contract_fields())
    assert first == second
    assert loader.tagged_sql(first, "t") == loader.tagged_sql(second, "t")


def test_ddl_covers_every_table_once(fields):
    statements = loader.ddl_statements(fields)
    labels = [label for label, _ in statements]
    assert labels[:3] == ["file_format", "internal_stage", "load_manifest"]
    assert sorted(create_statements(fields)) == sorted(loader.TABLE_ORDER)
    assert labels[-2:] == ["fk_AIRCRAFT_HISTORY", "fk_SCHEDULE_SNAPSHOT"]


def test_six_d0016_unique_constraints_replace_primary_keys(fields):
    creates = create_statements(fields)
    for table, (name, columns) in D0016_UNIQUE.items():
        expected = f"CONSTRAINT {name} UNIQUE ({', '.join(columns)}) NOT ENFORCED NORELY"
        assert expected in creates[table], table
        assert "PRIMARY KEY" not in creates[table], table


def test_passenger_source_id_unique_constraints_are_kept(fields):
    creates = create_statements(fields)
    for table, (name, columns) in PASSENGER_UNIQUE.items():
        assert f"CONSTRAINT {name} UNIQUE ({', '.join(columns)}) NOT ENFORCED NORELY" in creates[table]


def test_exactly_one_primary_key_and_it_is_the_calendar(fields):
    creates = create_statements(fields)
    with_pk = [table for table, statement in creates.items() if "PRIMARY KEY" in statement]
    assert with_pk == ["SCHEDULE_SNAPSHOT_CALENDAR"]
    assert (
        "CONSTRAINT PK_SCHEDULE_SNAPSHOT_CALENDAR PRIMARY KEY (expected_publish_date) NOT ENFORCED NORELY"
        in creates["SCHEDULE_SNAPSHOT_CALENDAR"]
    )


def test_no_primary_key_column_is_contract_nullable(fields):
    """The whole point of D-0016: a PRIMARY KEY column is physically NOT NULL in Snowflake."""
    for table, statement in create_statements(fields).items():
        nullable = {field.column for field in fields[table] if field.nullable}
        for columns in re.findall(r"PRIMARY KEY \(([^)]*)\)", statement):
            for column in (part.strip() for part in columns.split(",")):
                assert column not in nullable, f"{table}.{column} is contract nullable"


def test_unique_and_foreign_keys_never_rely(fields):
    for _, statement in loader.ddl_statements(fields):
        for constraint in re.findall(r"CONSTRAINT \w+ (?:PRIMARY KEY|UNIQUE|FOREIGN KEY).*", statement):
            assert constraint.rstrip(",").endswith("NOT ENFORCED NORELY"), constraint
    assert not re.search(r"(?<!NO)RELY\b", "\n".join(s for _, s in loader.ddl_statements(fields)))


def test_two_truthful_foreign_keys_are_added_after_every_table_exists(fields):
    alters = {
        label: statement for label, statement in loader.ddl_statements(fields) if label.startswith("fk_")
    }
    assert len(alters) == 2
    assert (
        "ALTER TABLE PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_HISTORY ADD CONSTRAINT "
        "FK_AIRCRAFT_HISTORY_MASTER FOREIGN KEY (aircraft_id) REFERENCES "
        "PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER (aircraft_id) NOT ENFORCED NORELY"
    ) == alters["fk_AIRCRAFT_HISTORY"]
    assert (
        "ALTER TABLE PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT ADD CONSTRAINT "
        "FK_SCHEDULE_SNAPSHOT_CALENDAR FOREIGN KEY (publish_date) REFERENCES "
        "PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR (expected_publish_date) NOT ENFORCED NORELY"
    ) == alters["fk_SCHEDULE_SNAPSHOT"]
    # No CREATE statement carries an inline FOREIGN KEY, so replace order can never break one.
    assert all("FOREIGN KEY" not in statement for statement in create_statements(fields).values())


def test_fk_children_are_replaced_before_their_parents():
    order = list(loader.DDL_ORDER)
    assert sorted(order) == sorted(loader.TABLE_ORDER)
    assert order.index("AIRCRAFT_HISTORY") < order.index("AIRCRAFT_MASTER")
    assert order.index("SCHEDULE_SNAPSHOT") < order.index("SCHEDULE_SNAPSHOT_CALENDAR")


def test_ddl_preserves_contract_columns_types_order_nullability_and_comments(fields):
    creates = create_statements(fields)
    for table, table_fields in fields.items():
        statement = creates[table]
        body = statement.split("(\n  ", 1)[1]
        lines = [line.strip().rstrip(",") for line in body.splitlines()]
        for index, field in enumerate(table_fields):
            expected = f"{field.column} {field.type_tag}"
            if not field.nullable:
                expected += " NOT NULL"
            expected += f" COMMENT '{field.field_id} | " + field.role.replace("'", "''")
            assert lines[index].startswith(expected), (table, field.field_id, lines[index])
        assert statement.startswith(f"CREATE OR REPLACE TABLE PK_AVIATION_TEMPORAL.SOURCE.{table} (")
        assert "CHANGE_TRACKING=TRUE" in statement
        assert loader.TABLE_COMMENTS[table].replace("'", "''") in statement


def test_ddl_has_no_transaction_or_staging_ceremony(fields):
    text = "\n".join(statement for _, statement in loader.ddl_statements(fields))
    for banned in ("BEGIN", "COMMIT", "ROLLBACK", "CLONE", "INSERT OVERWRITE", "STAGING", "TRANSIENT"):
        assert banned not in text, banned
    # D-0017 keeps one scoped internal stage for the PUT/COPY path; it is not a staging-table swap.
    assert text.count("CREATE STAGE IF NOT EXISTS") == 1
    assert loader.STAGE in text
    for table in loader.TABLE_ORDER:
        assert f"{table}_STAGE" not in text


# --- CSV parsing -------------------------------------------------------------------------------


def calendar_csv(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "schedule_snapshot_calendar.csv"
    path.write_bytes(body.encode("utf-8"))
    return path


CALENDAR_HEADER = "expected_publish_date,is_present,is_complete,source_lineage_id,observed_row_count,validation_status"
CALENDAR_ROW = "2026-08-03,true,true,SC-20260803-COMPLETE,12017,COMPLETE_VALIDATED"


def test_read_csv_accepts_lf(tmp_path, fields):
    path = calendar_csv(tmp_path, f"{CALENDAR_HEADER}\n{CALENDAR_ROW}\n")
    rows = loader.read_csv(path, fields["SCHEDULE_SNAPSHOT_CALENDAR"])
    assert rows == [
        {
            "expected_publish_date": "2026-08-03",
            "is_present": "true",
            "is_complete": "true",
            "source_lineage_id": "SC-20260803-COMPLETE",
            "observed_row_count": "12017",
            "validation_status": "COMPLETE_VALIDATED",
        }
    ]


def test_read_csv_rejects_crlf(tmp_path, fields):
    path = calendar_csv(tmp_path, f"{CALENDAR_HEADER}\r\n{CALENDAR_ROW}\r\n")
    with pytest.raises(loader.GateError, match="LF"):
        loader.read_csv(path, fields["SCHEDULE_SNAPSHOT_CALENDAR"])


def test_read_csv_rejects_missing_final_newline(tmp_path, fields):
    path = calendar_csv(tmp_path, f"{CALENDAR_HEADER}\n{CALENDAR_ROW}")
    with pytest.raises(loader.GateError, match="unterminated quote or missing final LF"):
        loader.read_csv(path, fields["SCHEDULE_SNAPSHOT_CALENDAR"])


def test_read_csv_rejects_reordered_header(tmp_path, fields):
    swapped = ",".join(CALENDAR_HEADER.split(",")[::-1])
    path = calendar_csv(tmp_path, f"{swapped}\n{CALENDAR_ROW}\n")
    with pytest.raises(loader.GateError, match="header/order"):
        loader.read_csv(path, fields["SCHEDULE_SNAPSHOT_CALENDAR"])


def test_read_csv_rejects_renamed_column(tmp_path, fields):
    renamed = CALENDAR_HEADER.replace("is_present", "present")
    path = calendar_csv(tmp_path, f"{renamed}\n{CALENDAR_ROW}\n")
    with pytest.raises(loader.GateError, match="header/order"):
        loader.read_csv(path, fields["SCHEDULE_SNAPSHOT_CALENDAR"])


@pytest.mark.parametrize("row", [CALENDAR_ROW + ",extra", CALENDAR_ROW.rsplit(",", 1)[0]])
def test_read_csv_rejects_wrong_column_count(tmp_path, fields, row):
    path = calendar_csv(tmp_path, f"{CALENDAR_HEADER}\n{row}\n")
    with pytest.raises(loader.GateError, match="column-count mismatch"):
        loader.read_csv(path, fields["SCHEDULE_SNAPSHOT_CALENDAR"])


def test_read_csv_rejects_non_utf8(tmp_path, fields):
    path = tmp_path / "schedule_snapshot_calendar.csv"
    path.write_bytes(f"{CALENDAR_HEADER}\n{CALENDAR_ROW}\n".encode("utf-8").replace(b"COMPLETE_VALIDATED", b"\xff\xfe"))
    with pytest.raises(loader.GateError, match="not UTF-8"):
        loader.read_csv(path, fields["SCHEDULE_SNAPSHOT_CALENDAR"])


def test_read_csv_maps_empty_field_to_null(tmp_path, fields):
    path = calendar_csv(tmp_path, f"{CALENDAR_HEADER}\n2026-08-03,true,true,SC-X,,COMPLETE_VALIDATED\n")
    assert loader.read_csv(path, fields["SCHEDULE_SNAPSHOT_CALENDAR"])[0]["observed_row_count"] is None


# --- hashing -----------------------------------------------------------------------------------


@pytest.mark.parametrize("scale", SCALES)
def test_typed_row_hash_matches_committed_manifest(scale, fields):
    manifest = manifest_of(scale)
    for table in loader.TABLE_ORDER:
        entry = manifest["tables"][table]
        rows = loader.read_csv(loader.package_dir(scale) / entry["file"], fields[table])
        assert len(rows) == entry["rows"]
        assert loader.ordered_typed_rows_hash(table, fields[table], rows) == entry["ordered_typed_rows_sha256"]


def test_ordered_hash_is_order_sensitive_and_multiset_hash_is_not(fields):
    table_fields = fields["SCHEDULE_SNAPSHOT_CALENDAR"]
    rows = loader.read_csv(loader.package_dir("smoke") / "schedule_snapshot_calendar.csv", table_fields)
    reversed_rows = list(reversed(rows))
    assert loader.ordered_typed_rows_hash("X", table_fields, rows) != loader.ordered_typed_rows_hash(
        "X", table_fields, reversed_rows
    )
    assert loader.multiset_rows_hash(table_fields, rows) == loader.multiset_rows_hash(table_fields, reversed_rows)


def test_multiset_hash_changes_when_any_value_changes(fields):
    table_fields = fields["SCHEDULE_SNAPSHOT_CALENDAR"]
    rows = loader.read_csv(loader.package_dir("smoke") / "schedule_snapshot_calendar.csv", table_fields)
    baseline = loader.multiset_rows_hash(table_fields, rows)
    mutated = [dict(row) for row in rows]
    mutated[0]["observed_row_count"] = None
    assert loader.multiset_rows_hash(table_fields, mutated) != baseline
    mutated = [dict(row) for row in rows]
    mutated[1]["validation_status"] = "COMPLETE_VALIDATE"
    assert loader.multiset_rows_hash(table_fields, mutated) != baseline


def test_verify_scalar_matches_the_sql_rendering_contract():
    assert loader.verify_scalar("35.8", "FLOAT") == "35.800000000"
    assert loader.verify_scalar("100.0", "FLOAT") == "100.000000000"
    assert loader.verify_scalar("-420.0", "FLOAT") == "-420.000000000"
    assert loader.verify_scalar("12017", "NUMBER(38,0)") == "12017"
    assert loader.verify_scalar("true", "BOOLEAN") == "true"
    assert loader.verify_scalar("2026-08-03", "DATE") == "2026-08-03"
    assert loader.verify_scalar("16:00:00", "TIME") == "16:00:00"
    assert loader.verify_scalar("2040-01-01T09:00:00", "TIMESTAMP_NTZ") == "2040-01-01T09:00:00"


def test_verify_scalar_fails_closed_on_unverifiable_precision():
    with pytest.raises(loader.GateError, match="round-trip"):
        loader.verify_scalar("0.1234567891", "FLOAT")
    with pytest.raises(loader.GateError, match="sub-second"):
        loader.verify_scalar("16:00:00.5", "TIME")
    with pytest.raises(loader.GateError, match="sub-second"):
        loader.verify_scalar("2040-01-01T09:00:00.5", "TIMESTAMP_NTZ")
    with pytest.raises(loader.GateError, match="verifiable"):
        loader.verify_scalar("1e30", "FLOAT")


def test_content_hash_sql_is_deterministic_and_scoped(fields):
    sql = loader.content_hash_sql("SCHEDULE_SNAPSHOT_CALENDAR", fields["SCHEDULE_SNAPSHOT_CALENDAR"])
    assert sql == loader.content_hash_sql("SCHEDULE_SNAPSHOT_CALENDAR", fields["SCHEDULE_SNAPSHOT_CALENDAR"])
    assert "FROM PK_AVIATION_TEMPORAL.SOURCE.SCHEDULE_SNAPSHOT_CALENDAR" in sql
    assert "SHA2(COALESCE(LISTAGG(row_sha,'') WITHIN GROUP (ORDER BY row_sha),''),256)" in sql
    for field in fields["SCHEDULE_SNAPSHOT_CALENDAR"]:
        assert f"IFF({field.column} IS NULL, '1:N'" in sql
    assert "TO_VARCHAR(CAST(total_seats AS NUMBER(38,9)))" in loader.content_hash_sql(
        "SCHEDULE_SNAPSHOT", fields["SCHEDULE_SNAPSHOT"]
    )


# --- preflight ---------------------------------------------------------------------------------


@pytest.mark.parametrize("scale", SCALES)
def test_preflight_passes_on_the_real_package(scale):
    manifest_path = loader.package_dir(scale) / "manifest.json"
    package = loader.preflight_package(manifest_path, expect_manifest_sha256=loader.sha256_file(manifest_path))
    manifest = manifest_of(scale)
    assert package.manifest["scale"] == scale
    assert package.evidence["total_rows"] == manifest["validation"]["total_rows"]
    assert set(package.rows) == set(loader.TABLE_ORDER)
    for table in loader.TABLE_ORDER:
        entry = package.evidence["tables"][table]
        assert entry["rows"] == manifest["validation"]["counts"][table]
        assert entry["ordered_typed_rows_sha256"] == manifest["tables"][table]["ordered_typed_rows_sha256"]
        assert entry["file_sha256"] == manifest["tables"][table]["file_sha256"]


def copy_package(tmp_path: Path, scale: str = "smoke") -> Path:
    destination = tmp_path / scale
    shutil.copytree(loader.package_dir(scale), destination)
    return destination / "manifest.json"


def test_preflight_rejects_a_pinned_manifest_hash_mismatch(tmp_path):
    manifest_path = copy_package(tmp_path)
    with pytest.raises(loader.GateError, match="manifest SHA-256 mismatch"):
        loader.preflight_package(manifest_path, expect_manifest_sha256="0" * 64)


def test_preflight_rejects_a_tampered_csv(tmp_path):
    manifest_path = copy_package(tmp_path)
    target = manifest_path.parent / "schedule_snapshot_calendar.csv"
    target.write_bytes(target.read_bytes().replace(b"COMPLETE_VALIDATED", b"COMPLETE_VALIDATEX", 1))
    with pytest.raises(loader.GateError, match="file SHA-256 mismatch"):
        loader.preflight_package(manifest_path)


def test_preflight_rejects_a_tampered_csv_whose_file_hash_was_relabelled(tmp_path):
    """Relabelling file_sha256 does not help: the typed-row hash is recomputed independently."""
    manifest_path = copy_package(tmp_path)
    target = manifest_path.parent / "schedule_snapshot_calendar.csv"
    target.write_bytes(target.read_bytes().replace(b"COMPLETE_VALIDATED", b"COMPLETE_VALIDATEX", 1))
    manifest = json.loads(manifest_path.read_bytes())
    manifest["tables"]["SCHEDULE_SNAPSHOT_CALENDAR"]["file_sha256"] = loader.sha256_file(target)
    manifest_path.write_bytes(loader.canonical_json_bytes(manifest))
    with pytest.raises(loader.GateError, match="ordered typed-row SHA-256 mismatch"):
        loader.preflight_package(manifest_path)


def test_preflight_rejects_a_dropped_csv_row(tmp_path):
    manifest_path = copy_package(tmp_path)
    target = manifest_path.parent / "schedule_snapshot_calendar.csv"
    lines = target.read_bytes().split(b"\n")
    target.write_bytes(b"\n".join(lines[:-2] + lines[-1:]))
    manifest = json.loads(manifest_path.read_bytes())
    manifest["tables"]["SCHEDULE_SNAPSHOT_CALENDAR"]["file_sha256"] = loader.sha256_file(target)
    manifest_path.write_bytes(loader.canonical_json_bytes(manifest))
    with pytest.raises(loader.GateError, match="parsed row count mismatch"):
        loader.preflight_package(manifest_path)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda m: m.__setitem__("manifest_version", "2.0.0"), "unsupported manifest version"),
        (lambda m: m.__setitem__("typed_row_hash_version", "typed-row-lp-v2"), "typed-row hash version"),
        (lambda m: m["serializer"].__setitem__("version", "sf-csv-v2"), "serializer version"),
        (lambda m: m["snowflake_file_format"].__setitem__("trim_space", True), "file-format boundary"),
        (lambda m: m["tables"].pop("AIRLINE_REFERENCE"), "ten-table SOURCE contract"),
        (lambda m: m["validation"].__setitem__("total_rows", 1), "validation total"),
        (lambda m: m["tables"]["AIRLINE_REFERENCE"]["columns"].reverse(), "columns/order mismatch"),
        (lambda m: m["tables"]["AIRLINE_REFERENCE"].__setitem__("file", "airlines.csv"), "filename must be"),
        (lambda m: m["validation"]["counts"].__setitem__("AIRLINE_REFERENCE", 7), "row count disagrees"),
    ],
)
def test_preflight_fails_closed_on_a_corrupted_manifest(tmp_path, mutate, message):
    manifest_path = copy_package(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())
    mutate(manifest)
    manifest_path.write_bytes(loader.canonical_json_bytes(manifest))
    with pytest.raises(loader.GateError, match=message):
        loader.preflight_package(manifest_path)


def test_preflight_rejects_non_canonical_manifest_json(tmp_path):
    manifest_path = copy_package(tmp_path)
    manifest_path.write_bytes(json.dumps(json.loads(manifest_path.read_bytes()), indent=2).encode("utf-8"))
    with pytest.raises(loader.GateError, match="canonical JSON"):
        loader.preflight_package(manifest_path)


# --- CLI ---------------------------------------------------------------------------------------


def test_cli_requires_exactly_one_operation():
    with pytest.raises(SystemExit):
        loader.main([])
    with pytest.raises(SystemExit):
        loader.main(["--preflight", "--print-ddl"])


def test_cli_print_ddl_and_preflight_do_not_connect(capsys):
    assert loader.main(["--print-ddl"]) == 0
    assert "CREATE OR REPLACE TABLE PK_AVIATION_TEMPORAL.SOURCE.AIRCRAFT_MASTER" in capsys.readouterr().out
    assert loader.main(["--preflight", "--scale", "smoke"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASSED"


def test_cli_preflight_reports_failure_as_exit_one(tmp_path, capsys):
    manifest_path = copy_package(tmp_path)
    manifest_path.write_bytes(manifest_path.read_bytes().replace(b'"scale":"smoke"', b'"scale":"tiny"'))
    assert loader.main(["--preflight", "--manifest", str(manifest_path)]) == 1
    assert json.loads(capsys.readouterr().err)["status"] == "FAILED"


def test_scope_is_pinned():
    assert (loader.CONNECTION, loader.ROLE, loader.WAREHOUSE, loader.DATABASE) == (
        "rai",
        "RAI_DEMO_AVIATION_TEMPORAL",
        "RAI_XS",
        "PK_AVIATION_TEMPORAL",
    )
    assert loader.snow_command(Path("/tmp/x.sql")) == [
        "snow", "sql", "-c", "rai", "--role", "RAI_DEMO_AVIATION_TEMPORAL",
        "--warehouse", "RAI_XS", "--database", "PK_AVIATION_TEMPORAL",
        "--format", "JSON", "--filename", "/tmp/x.sql",
    ]
